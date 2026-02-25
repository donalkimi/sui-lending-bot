#!/usr/bin/env python3
"""
Backfill Bluefin perp rates from perp_margin_rates → rates_snapshot.

WHY THIS IS NEEDED:
    The live hourly refresh pipeline inserts perp rows into rates_snapshot at the
    cron run timestamp (e.g. 14:02:17). But historical perp data lives in
    perp_margin_rates with hour-rounded timestamps (e.g. 14:00:00).

    The strategy history chart fetcher (data_fetcher.py) does an exact timestamp
    match across all 3 legs of a perp strategy. If leg 3B (Bluefin perp) has no
    row at the same timestamp as legs 1A and 2A (spot lending), that timestamp is
    silently dropped → only 1 day of history shows.

HOW IT WORKS:
    1. Load all perp_margin_rates into a lookup: {(hour_floor, token_contract): rate}
    2. Get all canonical spot timestamps from rates_snapshot (use_for_pnl = TRUE)
       These are the exact cron-run timestamps that spot lending rows use.
    3. For each canonical timestamp × each perp token:
       - Floor the canonical timestamp to the hour
       - Look up the matching perp rate for that hour
       - Apply sign convention (Design Note #17): stored_rate = -funding_rate_annual
       - Insert into rates_snapshot at the canonical timestamp with use_for_pnl = TRUE
    4. ON CONFLICT DO NOTHING — idempotent, safe to re-run

SIGN CONVENTION (Design Note #17):
    Bluefin publishes +5% funding (longs pay shorts).
    We store borrow_rate = -5% (shorts earn, negative rate = earnings).
    Same logic as bluefin_reader.py get_all_data_for_timestamp(): perp_rate = -funding_rate_annual

Usage:
    python -m Scripts.backfill_perp_to_rates_snapshot              # dry-run (default)
    python -m Scripts.backfill_perp_to_rates_snapshot --execute
    python -m Scripts.backfill_perp_to_rates_snapshot --execute --days 90
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras

from config import settings
from utils.time_helpers import to_seconds, to_datetime_str

DUMMY_PRICE = 10.10101  # Same placeholder used in live refresh path (bluefin_reader.py)
BATCH_SIZE = 1000


def build_perp_lookup(conn):
    """
    Load all perp_margin_rates into a dict keyed by (hour_floor, token_contract).

    Returns:
        dict: { (hour_floor_datetime, token_contract): (funding_rate_annual, base_token, avg_rate_8hr, avg_rate_24hr) }
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, token_contract, base_token, funding_rate_annual,
               avg_rate_8hr, avg_rate_24hr
        FROM perp_margin_rates
        WHERE protocol = 'Bluefin'
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()
    cursor.close()

    lookup = {}
    for ts, token_contract, base_token, funding_rate_annual, avg_rate_8hr, avg_rate_24hr in rows:
        # perp_margin_rates timestamps are already hour-rounded by bluefin_reader.py
        hour_floor = ts.replace(minute=0, second=0, microsecond=0)
        key = (hour_floor, token_contract)
        # Keep the most recent rate if duplicates exist for same hour/token
        lookup[key] = (
            float(funding_rate_annual),
            base_token,
            float(avg_rate_8hr)  if avg_rate_8hr  is not None else None,
            float(avg_rate_24hr) if avg_rate_24hr is not None else None,
        )

    return lookup


def get_canonical_timestamps(conn, cutoff_datetime=None):
    """
    Get all distinct timestamps from rates_snapshot.

    These are the exact cron-run timestamps that spot lending rows use.
    Perp rows must be inserted at these same timestamps to align in history charts.

    Args:
        cutoff_datetime: Only return timestamps >= this datetime (optional)

    Returns:
        list of datetime objects, sorted ascending
    """
    cursor = conn.cursor()

    if cutoff_datetime is not None:
        cursor.execute("""
            SELECT DISTINCT timestamp
            FROM rates_snapshot
            WHERE timestamp >= %s
            ORDER BY timestamp ASC
        """, (cutoff_datetime,))
    else:
        cursor.execute("""
            SELECT DISTINCT timestamp
            FROM rates_snapshot
            ORDER BY timestamp ASC
        """)

    rows = cursor.fetchall()
    cursor.close()
    return [row[0] for row in rows]


def get_pnl_timestamps(conn):
    """
    Get set of timestamps that have use_for_pnl = TRUE in rates_snapshot.

    Used to correctly set use_for_pnl on inserted perp rows: TRUE only when
    the spot rows at that timestamp are themselves use_for_pnl = TRUE.

    Returns:
        set of datetime objects
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT timestamp
        FROM rates_snapshot
        WHERE use_for_pnl = TRUE
    """)
    rows = cursor.fetchall()
    cursor.close()
    return set(row[0] for row in rows)


def get_existing_perp_timestamps(conn):
    """
    Get set of (timestamp, token_contract) already in rates_snapshot for Bluefin.

    Used to skip rows that were already inserted by the live refresh pipeline.

    Returns:
        set of (datetime, token_contract) tuples
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, token_contract
        FROM rates_snapshot
        WHERE protocol = 'Bluefin'
    """)
    rows = cursor.fetchall()
    cursor.close()
    return set((row[0], row[1]) for row in rows)


def build_insert_rows(canonical_timestamps, perp_lookup, existing_perp, pnl_timestamps):
    """
    Build list of rows to insert into rates_snapshot.

    For each canonical_ts × each perp token in perp_lookup:
    - Floor canonical_ts to hour
    - Look up matching perp rate
    - Apply sign convention
    - Skip if already exists or no data for that hour

    Returns:
        (rows_to_insert, stats) where:
            rows_to_insert: list of dicts ready for INSERT
            stats: dict with counts for dry-run summary
    """
    # Collect unique tokens from lookup
    # { token_contract: base_token }
    perp_tokens = {}
    for (_, token_contract), (_, base_token) in perp_lookup.items():
        perp_tokens[token_contract] = base_token

    rows_to_insert = []
    stats = {
        'matched': 0,
        'already_exists': 0,
        'no_perp_data': 0,
        'total_canonical': len(canonical_timestamps),
        'perp_tokens': list(perp_tokens.keys()),
    }

    for canonical_ts in canonical_timestamps:
        hour_floor = canonical_ts.replace(minute=0, second=0, microsecond=0)

        for token_contract, base_token in perp_tokens.items():
            # Skip if already present (inserted by live refresh pipeline)
            if (canonical_ts, token_contract) in existing_perp:
                stats['already_exists'] += 1
                continue

            # Look up perp rate for this hour
            key = (hour_floor, token_contract)
            if key not in perp_lookup:
                stats['no_perp_data'] += 1
                continue

            funding_rate_annual, _, avg_rate_8hr, avg_rate_24hr = perp_lookup[key]

            # Apply sign convention per Design Note #17:
            # Positive funding (longs pay shorts) → negate → shorts earn → stored negative
            stored_rate = -funding_rate_annual

            symbol = f"{base_token}-USDC-PERP"

            rows_to_insert.append({
                'timestamp': canonical_ts,         # Exact cron timestamp — aligns with spot legs
                'protocol': 'Bluefin',
                'token': symbol,
                'token_contract': token_contract,
                'lend_base_apr': stored_rate,
                'lend_reward_apr': 0.0,
                'lend_total_apr': stored_rate,
                'borrow_base_apr': stored_rate,
                'borrow_reward_apr': 0.0,
                'borrow_total_apr': stored_rate,
                'avg8hr_lend_total_apr':    -avg_rate_8hr  if avg_rate_8hr  is not None else None,
                'avg8hr_borrow_total_apr':  -avg_rate_8hr  if avg_rate_8hr  is not None else None,
                'avg24hr_lend_total_apr':   -avg_rate_24hr if avg_rate_24hr is not None else None,
                'avg24hr_borrow_total_apr': -avg_rate_24hr if avg_rate_24hr is not None else None,
                'collateral_ratio': None,           # Perps have no collateral ratio
                'liquidation_threshold': None,
                'price_usd': DUMMY_PRICE,           # Placeholder, same as live path
                'utilization': None,
                'total_supply_usd': None,
                'total_borrow_usd': None,
                'available_borrow_usd': None,
                'borrow_fee': 0.0,
                'borrow_weight': None,
                'reward_token': None,
                'reward_token_contract': None,
                'reward_token_price_usd': None,
                'market': f"{base_token}-PERP",
                'side': None,
                'use_for_pnl': canonical_ts in pnl_timestamps,  # Match spot rows at this timestamp
            })
            stats['matched'] += 1

    return rows_to_insert, stats


def insert_rows(conn, rows):
    """
    Batch insert rows into rates_snapshot using ON CONFLICT DO NOTHING.

    Args:
        conn: psycopg2 connection
        rows: list of row dicts from build_insert_rows()

    Returns:
        int: number of rows actually inserted (conflicts excluded)
    """
    if not rows:
        return 0

    cursor = conn.cursor()
    total_inserted = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO rates_snapshot (
                timestamp, protocol, token, token_contract,
                lend_base_apr, lend_reward_apr, lend_total_apr,
                borrow_base_apr, borrow_reward_apr, borrow_total_apr,
                collateral_ratio, liquidation_threshold,
                price_usd,
                utilization, total_supply_usd, total_borrow_usd, available_borrow_usd,
                borrow_fee, borrow_weight,
                reward_token, reward_token_contract, reward_token_price_usd,
                market, side,
                use_for_pnl,
                avg8hr_lend_total_apr, avg8hr_borrow_total_apr,
                avg24hr_lend_total_apr, avg24hr_borrow_total_apr
            ) VALUES (
                %(timestamp)s, %(protocol)s, %(token)s, %(token_contract)s,
                %(lend_base_apr)s, %(lend_reward_apr)s, %(lend_total_apr)s,
                %(borrow_base_apr)s, %(borrow_reward_apr)s, %(borrow_total_apr)s,
                %(collateral_ratio)s, %(liquidation_threshold)s,
                %(price_usd)s,
                %(utilization)s, %(total_supply_usd)s, %(total_borrow_usd)s, %(available_borrow_usd)s,
                %(borrow_fee)s, %(borrow_weight)s,
                %(reward_token)s, %(reward_token_contract)s, %(reward_token_price_usd)s,
                %(market)s, %(side)s,
                %(use_for_pnl)s,
                %(avg8hr_lend_total_apr)s, %(avg8hr_borrow_total_apr)s,
                %(avg24hr_lend_total_apr)s, %(avg24hr_borrow_total_apr)s
            )
            ON CONFLICT (timestamp, protocol, token_contract) DO NOTHING
        """, batch)

        total_inserted += cursor.rowcount
        print(f"  Inserted batch {batch_start // BATCH_SIZE + 1}: "
              f"{batch_start + 1}–{min(batch_start + BATCH_SIZE, len(rows))} of {len(rows)}")

    conn.commit()
    cursor.close()
    return total_inserted


def print_summary(stats, rows_to_insert, dry_run):
    """Print a clear summary of what was / will be done."""
    print("\n" + "=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"Perp tokens found: {len(stats['perp_tokens'])}")
    for tc in stats['perp_tokens']:
        print(f"  • {tc}")
    print(f"\nCanonical spot timestamps:  {stats['total_canonical']:>8,}")
    print(f"Rows to insert:             {stats['matched']:>8,}")
    print(f"Already in rates_snapshot:  {stats['already_exists']:>8,}  (skipped)")
    print(f"No perp data for hour:      {stats['no_perp_data']:>8,}  (skipped — before collection started)")

    if rows_to_insert:
        ts_list = [r['timestamp'] for r in rows_to_insert]
        print(f"\nDate range: {min(ts_list).date()} → {max(ts_list).date()}")

    if dry_run:
        print("\n⚠️  DRY RUN — no rows written.")
        print("    Run with --execute to insert.")
    else:
        print(f"\n✅ Inserted {stats['matched']:,} rows into rates_snapshot.")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Bluefin perp rates from perp_margin_rates into rates_snapshot'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        default=False,
        help='Actually insert rows (default: dry-run only)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Only backfill the last N days (default: all available history)'
    )
    args = parser.parse_args()

    dry_run = not args.execute

    print("=== Backfill Bluefin Perp Rates → rates_snapshot ===")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    if args.days:
        print(f"Lookback: last {args.days} days")
    else:
        print("Lookback: full history")

    # Calculate cutoff if --days specified
    cutoff_datetime = None
    if args.days is not None:
        cutoff_datetime = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=args.days)
        print(f"Cutoff: {cutoff_datetime}")

    conn = psycopg2.connect(settings.SUPABASE_URL)

    try:
        print("\n[1/4] Loading perp_margin_rates...")
        perp_lookup = build_perp_lookup(conn)
        print(f"  {len(perp_lookup):,} perp rate entries loaded")

        if not perp_lookup:
            print("❌ No data in perp_margin_rates. Run backfill_bluefin_funding_rates.py first.")
            return 1

        print("\n[2/4] Loading all distinct timestamps from rates_snapshot...")
        canonical_timestamps = get_canonical_timestamps(conn, cutoff_datetime)
        print(f"  {len(canonical_timestamps):,} timestamps found")

        if not canonical_timestamps:
            print("❌ No timestamps found in rates_snapshot.")
            return 1

        print("\n[3/4] Loading existing Bluefin rows and pnl timestamps from rates_snapshot...")
        existing_perp = get_existing_perp_timestamps(conn)
        pnl_timestamps = get_pnl_timestamps(conn)
        print(f"  {len(existing_perp):,} existing Bluefin rows (will be skipped)")
        print(f"  {len(pnl_timestamps):,} timestamps with use_for_pnl = TRUE")

        print("\n[4/4] Building insert rows...")
        rows_to_insert, stats = build_insert_rows(
            canonical_timestamps, perp_lookup, existing_perp, pnl_timestamps
        )

        print_summary(stats, rows_to_insert, dry_run)

        if not dry_run and rows_to_insert:
            print(f"\nInserting {len(rows_to_insert):,} rows in batches of {BATCH_SIZE}...")
            inserted = insert_rows(conn, rows_to_insert)
            stats['matched'] = inserted
            print_summary(stats, rows_to_insert, dry_run=False)

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
