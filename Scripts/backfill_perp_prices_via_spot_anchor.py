#!/usr/bin/env python3
"""
Backfill Bluefin price_usd for historical rows that predate spot_perp_basis collection.

WHY THIS IS NEEDED:
    After running backfill_perp_prices_from_spot_perp_basis.py, some rates_snapshot rows
    for protocol='Bluefin' still have price_usd=10.10101 because no matching timestamp
    exists in spot_perp_basis (these are rows from before basis data collection began).

APPROACH — "Spot Anchor":
    For each perp_proxy in spot_perp_basis:
      1. Find the earliest available timestamp (MIN(timestamp)).
      2. At that timestamp, pick the spot_contract with the MINIMUM basis_mid.
         This becomes the anchor: (min_spot_contract, min_basis).

    For each unmatched perp row in rates_snapshot:
      - Look up rates_snapshot.price_usd for min_spot_contract at the SAME timestamp.
        (Spot lending protocols — Navi, Suilend, etc. — have real prices here.)
      - Derive: perp_price = spot_price × (1 + min_basis)
        (From basis_mid ≈ (perp_price − spot_price) / perp_price)
      - If no spot price exists at that timestamp, the row is left unchanged and
        reported to console.

FORMULA:
    perp_price_usd = spot_price_usd × (1.0 + anchor_basis_mid)

Usage:
    python -m Scripts.backfill_perp_prices_via_spot_anchor              # dry-run (default)
    python -m Scripts.backfill_perp_prices_via_spot_anchor --execute
"""

import sys
import argparse
from collections import defaultdict

import psycopg2

from config import settings

PLACEHOLDER_PRICE = 10.10101


def build_anchor_lookup(conn):
    """
    For each perp_proxy, find the earliest timestamp in spot_perp_basis and the
    spot_contract with the SECOND-smallest basis_mid at that timestamp.
    Falls back to rank 1 (minimum) if only one spot_contract exists for that perp.

    Returns:
        dict: { perp_proxy: (min_spot_contract, min_basis) }
    """
    cursor = conn.cursor()
    cursor.execute("""
        WITH earliest AS (
            SELECT perp_proxy, MIN(timestamp) AS min_ts
            FROM spot_perp_basis
            GROUP BY perp_proxy
        ),
        ranked AS (
            SELECT
                spb.perp_proxy,
                spb.spot_contract                                              AS min_spot_contract,
                spb.basis_mid                                                  AS min_basis,
                ROW_NUMBER() OVER (PARTITION BY spb.perp_proxy
                                   ORDER BY spb.basis_mid ASC)                AS rn,
                COUNT(*)     OVER (PARTITION BY spb.perp_proxy)               AS total_contracts
            FROM spot_perp_basis spb
            JOIN earliest e
              ON spb.perp_proxy = e.perp_proxy
             AND spb.timestamp  = e.min_ts
        )
        SELECT perp_proxy, min_spot_contract, min_basis
        FROM ranked
        WHERE rn = LEAST(5, total_contracts)
    """)
    rows = cursor.fetchall()
    cursor.close()
    return {perp_proxy: (min_spot_contract, float(min_basis))
            for perp_proxy, min_spot_contract, min_basis in rows}


def get_unmatched_count(conn):
    """
    Count rates_snapshot rows for Bluefin with the placeholder price and
    no matching row in spot_perp_basis at that timestamp.

    Returns:
        int
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM rates_snapshot rs
        WHERE rs.protocol  = 'Bluefin'
          AND rs.price_usd = %s
          AND NOT EXISTS (
            SELECT 1 FROM spot_perp_basis spb
            WHERE spb.timestamp  = rs.timestamp
              AND spb.perp_proxy = rs.token_contract
          )
    """, (PLACEHOLDER_PRICE,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def get_unresolvable_rows(conn, anchor):
    """
    Fetch rows that have neither a spot_perp_basis match nor a spot price in
    rates_snapshot for the anchor contract at that timestamp.

    These cannot be priced and will remain at 10.10101.

    Returns:
        dict: { token_contract: [(timestamp, min_spot_contract), ...] }
    """
    if not anchor:
        return {}

    # Build VALUES clause for the anchor lookup
    anchor_values = ", ".join(
        f"('{perp_proxy}', '{min_spot}')"
        for perp_proxy, (min_spot, _) in anchor.items()
    )

    cursor = conn.cursor()
    cursor.execute(f"""
        WITH anchor(perp_proxy, min_spot_contract) AS (
            VALUES {anchor_values}
        )
        SELECT rs_perp.timestamp, rs_perp.token_contract, anchor.min_spot_contract
        FROM rates_snapshot rs_perp
        JOIN anchor ON anchor.perp_proxy = rs_perp.token_contract
        WHERE rs_perp.protocol  = 'Bluefin'
          AND rs_perp.price_usd = %s
          AND NOT EXISTS (
            SELECT 1 FROM spot_perp_basis spb
            WHERE spb.timestamp  = rs_perp.timestamp
              AND spb.perp_proxy = rs_perp.token_contract
          )
          AND NOT EXISTS (
            SELECT 1 FROM rates_snapshot rs_spot
            WHERE rs_spot.token_contract = anchor.min_spot_contract
              AND rs_spot.timestamp      = rs_perp.timestamp
          )
        ORDER BY rs_perp.token_contract, rs_perp.timestamp
    """, (PLACEHOLDER_PRICE,))
    rows = cursor.fetchall()
    cursor.close()

    result = defaultdict(list)
    for ts, token_contract, min_spot_contract in rows:
        result[token_contract].append((ts, min_spot_contract))
    return dict(result)


def get_updatable_count(conn, anchor):
    """
    Count unmatched rows that CAN be priced (anchor spot contract has a price at
    that timestamp in rates_snapshot).

    Returns:
        int
    """
    if not anchor:
        return 0

    # Only need (perp_proxy, min_spot_contract) for the count — min_basis not needed
    anchor_values = ", ".join(
        f"('{perp_proxy}', '{min_spot}')"
        for perp_proxy, (min_spot, _) in anchor.items()
    )

    cursor = conn.cursor()
    # Use EXISTS (not JOIN) to avoid row-multiplication when multiple protocols
    # track the same min_spot_contract at the same timestamp.
    cursor.execute(f"""
        WITH anchor(perp_proxy, min_spot_contract) AS (
            VALUES {anchor_values}
        )
        SELECT COUNT(*)
        FROM rates_snapshot rs_perp
        JOIN anchor ON anchor.perp_proxy = rs_perp.token_contract
        WHERE rs_perp.protocol  = 'Bluefin'
          AND rs_perp.price_usd = %s
          AND NOT EXISTS (
            SELECT 1 FROM spot_perp_basis spb
            WHERE spb.timestamp  = rs_perp.timestamp
              AND spb.perp_proxy = rs_perp.token_contract
          )
          AND EXISTS (
            SELECT 1 FROM rates_snapshot rs_spot
            WHERE rs_spot.token_contract = anchor.min_spot_contract
              AND rs_spot.timestamp      = rs_perp.timestamp
          )
    """, (PLACEHOLDER_PRICE,))
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def execute_update(conn, anchor):
    """
    UPDATE rates_snapshot.price_usd = spot_price × (1 + anchor_basis_mid)
    for all unmatched Bluefin placeholder rows where the anchor spot price exists.

    Returns:
        int: number of rows updated
    """
    if not anchor:
        return 0

    anchor_values = ", ".join(
        f"('{perp_proxy}', '{min_spot}', {min_basis})"
        for perp_proxy, (min_spot, min_basis) in anchor.items()
    )

    cursor = conn.cursor()
    # PostgreSQL UPDATE...FROM cannot reference the update target table (rs_perp) in
    # JOIN conditions on FROM-clause tables. Instead, use a correlated subquery in SET
    # (which CAN reference rs_perp) and guard with EXISTS in WHERE.
    # LIMIT 1 in the subquery handles the case where multiple protocols track the same
    # spot contract at the same timestamp — all have the same price_usd so any row is fine.
    cursor.execute(f"""
        WITH anchor(perp_proxy, min_spot_contract, min_basis) AS (
            VALUES {anchor_values}
        )
        UPDATE rates_snapshot rs_perp
        SET price_usd = (
            SELECT rs_spot.price_usd * (1.0 + anc.min_basis)
            FROM anchor anc
            JOIN rates_snapshot rs_spot
              ON rs_spot.token_contract = anc.min_spot_contract
             AND rs_spot.timestamp      = rs_perp.timestamp
            WHERE anc.perp_proxy = rs_perp.token_contract
            LIMIT 1
        )
        FROM anchor
        WHERE rs_perp.token_contract = anchor.perp_proxy
          AND rs_perp.protocol       = 'Bluefin'
          AND rs_perp.price_usd      = %s
          AND EXISTS (
            SELECT 1 FROM rates_snapshot rs_spot2
            WHERE rs_spot2.token_contract = anchor.min_spot_contract
              AND rs_spot2.timestamp      = rs_perp.timestamp
          )
          AND NOT EXISTS (
            SELECT 1 FROM spot_perp_basis spb
            WHERE spb.timestamp  = rs_perp.timestamp
              AND spb.perp_proxy = rs_perp.token_contract
          )
    """, (PLACEHOLDER_PRICE,))
    updated = cursor.rowcount
    conn.commit()
    cursor.close()
    return updated


def print_unresolvable(unresolvable, anchor):
    """Print unresolvable rows grouped by token_contract."""
    if not unresolvable:
        return
    total = sum(len(rows) for rows in unresolvable.values())
    print(f"\nWARNING: Cannot resolve price for {total:,} rows "
          f"(no spot anchor price at these timestamps):")
    for token_contract, rows in sorted(unresolvable.items()):
        min_spot = anchor[token_contract][0]
        short_min_spot = min_spot.split("::")[-1] if "::" in min_spot else min_spot[:20]
        print(f"  {token_contract}  (min_spot=...{short_min_spot}):")
        for ts, _ in rows[:20]:
            print(f"    {ts}")
        if len(rows) > 20:
            print(f"    ... ({len(rows)} total)")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill unmatched Bluefin price_usd via spot anchor from spot_perp_basis'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        default=False,
        help='Actually update rows (default: dry-run only)'
    )
    args = parser.parse_args()

    dry_run = not args.execute

    print("=== Backfill Unmatched Bluefin price_usd via Spot Anchor ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")

    conn = psycopg2.connect(settings.SUPABASE_URL)

    try:
        print("\n[1/4] Building anchor lookup from spot_perp_basis...")
        anchor = build_anchor_lookup(conn)
        if not anchor:
            print("  No data in spot_perp_basis — nothing to anchor from.")
            return 1
        print(f"  {len(anchor)} perp contracts found:")
        for perp_proxy, (min_spot, min_basis) in sorted(anchor.items()):
            short_spot = min_spot.split("::")[-1] if "::" in min_spot else min_spot[:30]
            print(f"    {perp_proxy:<35}  min_spot=...{short_spot:<12}  basis={min_basis:+.6f}")

        print("\n[2/4] Counting unmatched placeholder rows...")
        unmatched = get_unmatched_count(conn)
        print(f"  {unmatched:,} rows with price_usd={PLACEHOLDER_PRICE} and no spot_perp_basis entry")

        if unmatched == 0:
            print("\nNothing to do — no unmatched placeholder rows.")
            return 0

        print("\n[3/4] Checking which rows can be priced via anchor...")
        updatable = get_updatable_count(conn, anchor)
        unresolvable_count = unmatched - updatable
        print(f"  Can be priced via spot anchor:         {updatable:>8,}")
        print(f"  Spot price also missing at timestamp:  {unresolvable_count:>8,}  <- left unchanged")

        print("\n[4/4] Fetching unresolvable rows for inspection...")
        unresolvable = get_unresolvable_rows(conn, anchor)
        print_unresolvable(unresolvable, anchor)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Unmatched placeholder rows:            {unmatched:>8,}")
        print(f"  Will be updated (spot anchor found): {updatable:>8,}")
        print(f"  Cannot be resolved (no spot price):  {unresolvable_count:>8,}")

        if dry_run:
            print("\n  DRY RUN -- no rows written.")
            print("  Run with --execute to apply changes.")
        else:
            if updatable > 0:
                print(f"\nApplying UPDATE...")
                updated = execute_update(conn, anchor)
                print(f"  Updated {updated:,} rows.")
            else:
                print("\nNo rows to update.")

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
