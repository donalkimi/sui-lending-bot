#!/usr/bin/env python3
"""
Backfill Bluefin price_usd in rates_snapshot from spot_perp_basis.

WHY THIS IS NEEDED:
    Rows in rates_snapshot for protocol='Bluefin' were inserted with a placeholder
    price_usd = 10.10101 (defined as DUMMY_PRICE in backfill_perp_to_rates_snapshot.py
    and the live bluefin_reader.py path).

    The correct price comes from spot_perp_basis, joined on:
        rates_snapshot.timestamp     = spot_perp_basis.timestamp
        rates_snapshot.token_contract = spot_perp_basis.perp_proxy

    Because spot_perp_basis can have multiple rows per (timestamp, perp_proxy) —
    one per spot_contract — we use DISTINCT ON (timestamp, perp_proxy) ordered by
    actual_fetch_time DESC to select the freshest row.

PRICE USED:
    (perp_bid + perp_ask) / 2  — perp mid-market price (confirmed with user).

Usage:
    python -m Scripts.backfill_perp_prices_from_spot_perp_basis              # dry-run (default)
    python -m Scripts.backfill_perp_prices_from_spot_perp_basis --execute
    python -m Scripts.backfill_perp_prices_from_spot_perp_basis --execute --days 90
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone

import psycopg2

from config import settings

PLACEHOLDER_PRICE = 10.10101


def get_placeholder_count(conn, cutoff_datetime=None):
    """
    Count all rates_snapshot rows for Bluefin with the placeholder price.

    Returns:
        int: total number of placeholder rows in scope
    """
    cursor = conn.cursor()
    if cutoff_datetime is not None:
        cursor.execute("""
            SELECT COUNT(*)
            FROM rates_snapshot
            WHERE protocol = 'Bluefin'
              AND price_usd = %s
              AND timestamp >= %s
        """, (PLACEHOLDER_PRICE, cutoff_datetime))
    else:
        cursor.execute("""
            SELECT COUNT(*)
            FROM rates_snapshot
            WHERE protocol = 'Bluefin'
              AND price_usd = %s
        """, (PLACEHOLDER_PRICE,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def get_matched_count(conn, cutoff_datetime=None):
    """
    Count how many placeholder rows have a matching row in spot_perp_basis.

    Returns:
        int: number of rows that will be updated on --execute
    """
    cursor = conn.cursor()
    if cutoff_datetime is not None:
        cursor.execute("""
            SELECT COUNT(*)
            FROM rates_snapshot rs
            JOIN (
                SELECT DISTINCT ON (timestamp, perp_proxy)
                    timestamp,
                    perp_proxy,
                    (perp_bid + perp_ask) / 2.0 AS mid_price
                FROM spot_perp_basis
                ORDER BY timestamp, perp_proxy, actual_fetch_time DESC
            ) spb
              ON rs.timestamp      = spb.timestamp
             AND rs.token_contract = spb.perp_proxy
            WHERE rs.protocol  = 'Bluefin'
              AND rs.price_usd = %s
              AND rs.timestamp >= %s
        """, (PLACEHOLDER_PRICE, cutoff_datetime))
    else:
        cursor.execute("""
            SELECT COUNT(*)
            FROM rates_snapshot rs
            JOIN (
                SELECT DISTINCT ON (timestamp, perp_proxy)
                    timestamp,
                    perp_proxy,
                    (perp_bid + perp_ask) / 2.0 AS mid_price
                FROM spot_perp_basis
                ORDER BY timestamp, perp_proxy, actual_fetch_time DESC
            ) spb
              ON rs.timestamp      = spb.timestamp
             AND rs.token_contract = spb.perp_proxy
            WHERE rs.protocol  = 'Bluefin'
              AND rs.price_usd = %s
        """, (PLACEHOLDER_PRICE,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def execute_update(conn, cutoff_datetime=None):
    """
    UPDATE rates_snapshot.price_usd for all matched Bluefin placeholder rows.

    Returns:
        int: number of rows actually updated
    """
    cursor = conn.cursor()
    if cutoff_datetime is not None:
        cursor.execute("""
            UPDATE rates_snapshot rs
            SET price_usd = spb.mid_price
            FROM (
                SELECT DISTINCT ON (timestamp, perp_proxy)
                    timestamp,
                    perp_proxy,
                    (perp_bid + perp_ask) / 2.0 AS mid_price
                FROM spot_perp_basis
                ORDER BY timestamp, perp_proxy, actual_fetch_time DESC
            ) spb
            WHERE rs.timestamp      = spb.timestamp
              AND rs.token_contract = spb.perp_proxy
              AND rs.protocol       = 'Bluefin'
              AND rs.price_usd      = %s
              AND rs.timestamp     >= %s
        """, (PLACEHOLDER_PRICE, cutoff_datetime))
    else:
        cursor.execute("""
            UPDATE rates_snapshot rs
            SET price_usd = spb.mid_price
            FROM (
                SELECT DISTINCT ON (timestamp, perp_proxy)
                    timestamp,
                    perp_proxy,
                    (perp_bid + perp_ask) / 2.0 AS mid_price
                FROM spot_perp_basis
                ORDER BY timestamp, perp_proxy, actual_fetch_time DESC
            ) spb
            WHERE rs.timestamp      = spb.timestamp
              AND rs.token_contract = spb.perp_proxy
              AND rs.protocol       = 'Bluefin'
              AND rs.price_usd      = %s
        """, (PLACEHOLDER_PRICE,))
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    return updated


def print_summary(total, matched, dry_run):
    """Print a clear summary of what was / will be done."""
    no_match = total - matched
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"Rows with placeholder price ({PLACEHOLDER_PRICE}):  {total:>8,}")
    print(f"  Matched in spot_perp_basis:                      {matched:>8,}  <- will be updated")
    print(f"  No match (no basis data):                        {no_match:>8,}  <- left unchanged")

    if dry_run:
        print("\n  DRY RUN -- no rows written.")
        print("  Run with --execute to apply changes.")
    else:
        print(f"\n  Updated {matched:,} rows.")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Bluefin price_usd in rates_snapshot from spot_perp_basis'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        default=False,
        help='Actually update rows (default: dry-run only)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Only fix rows in the last N days (default: full history)'
    )
    args = parser.parse_args()

    dry_run = not args.execute

    print("=== Backfill Bluefin price_usd from spot_perp_basis ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    if args.days:
        print(f"Lookback: last {args.days} days")
    else:
        print("Lookback: full history")

    cutoff_datetime = None
    if args.days is not None:
        cutoff_datetime = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.days)
        print(f"Cutoff: {cutoff_datetime}")

    conn = psycopg2.connect(settings.SUPABASE_URL)

    try:
        print("\n[1/2] Counting placeholder rows...")
        total = get_placeholder_count(conn, cutoff_datetime)
        print(f"  {total:,} rows with price_usd = {PLACEHOLDER_PRICE}")

        if total == 0:
            print("\nNothing to do — no placeholder rows found.")
            return 0

        print("\n[2/2] Counting rows with matching spot_perp_basis entry...")
        matched = get_matched_count(conn, cutoff_datetime)
        print(f"  {matched:,} rows can be updated")

        print_summary(total, matched, dry_run)

        if not dry_run and matched > 0:
            print(f"\nApplying UPDATE...")
            updated = execute_update(conn, cutoff_datetime)
            print_summary(total, updated, dry_run=False)

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
