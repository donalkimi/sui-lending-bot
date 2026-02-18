#!/usr/bin/env python3
"""
Interpolate perp margin rates into rates_snapshot table.

Creates new rows for each perp market (BTC-USDC-PERP, etc.) at each
existing timestamp in rates_snapshot.
"""
import argparse
from datetime import datetime
from config import settings
from data.rate_tracker import RateTracker
from psycopg2.extras import execute_values
from utils.time_helpers import to_datetime_str, to_seconds, to_datetime_utc

BLUEFIN_PERP_MARKETS = settings.BLUEFIN_PERP_MARKETS


def fetch_unique_timestamps(tracker, start_date=None, end_date=None):
    """Fetch all unique timestamps from rates_snapshot."""
    conn = tracker._get_connection()
    cursor = conn.cursor()

    query = "SELECT DISTINCT timestamp FROM rates_snapshot"
    params = []

    print(f"\n[DEBUG] Fetching timestamps:")
    print(f"  start_date input: {start_date} (type: {type(start_date)})")
    print(f"  end_date input: {end_date} (type: {type(end_date)})")

    if start_date or end_date:
        query += " WHERE"
        if start_date:
            query += " timestamp >= %s"
            params.append(start_date)
        if end_date:
            if start_date:
                query += " AND"
            query += " timestamp <= %s"
            params.append(end_date)

    query += " ORDER BY timestamp"

    print(f"  SQL query: {query}")
    print(f"  Parameters: {params}")

    cursor.execute(query, params)
    timestamps = [row[0] for row in cursor.fetchall()]

    print(f"  Found {len(timestamps)} timestamps")
    if timestamps:
        print(f"  First timestamp: {timestamps[0]}")
        print(f"  Last timestamp: {timestamps[-1]}")

    conn.close()

    return timestamps


def round_to_hour(timestamp):
    """Round timestamp down to nearest hour (UTC)."""
    ts_seconds = to_seconds(timestamp)
    hour_seconds = (ts_seconds // 3600) * 3600
    return to_datetime_str(hour_seconds)


def fetch_perp_rates_bulk(tracker, hour_timestamps, perp_markets):
    """
    Fetch perp funding rates for multiple timestamps in bulk using SQL WHERE IN.

    Returns a dictionary: {(token_contract, hour_timestamp): funding_rate}
    """
    conn = tracker._get_connection()
    cursor = conn.cursor()

    # Build a lookup dictionary
    rates_dict = {}

    try:
        # Build list of token contracts
        token_contracts = [f"0x{base_token}-USDC-PERP_bluefin" for base_token in perp_markets]

        # Fetch ALL matching rates in one query using WHERE IN
        if tracker.use_cloud:
            # PostgreSQL - use %s placeholders
            token_placeholders = ','.join(['%s'] * len(token_contracts))
            timestamp_placeholders = ','.join(['%s'] * len(hour_timestamps))

            query = f"""
                SELECT token_contract, timestamp, funding_rate_annual
                FROM perp_margin_rates
                WHERE token_contract IN ({token_placeholders})
                  AND timestamp IN ({timestamp_placeholders})
            """
            params = token_contracts + hour_timestamps
        else:
            # SQLite - use ? placeholders
            token_placeholders = ','.join(['?'] * len(token_contracts))
            timestamp_placeholders = ','.join(['?'] * len(hour_timestamps))

            query = f"""
                SELECT token_contract, timestamp, funding_rate_annual
                FROM perp_margin_rates
                WHERE token_contract IN ({token_placeholders})
                  AND timestamp IN ({timestamp_placeholders})
            """
            params = token_contracts + hour_timestamps

        cursor.execute(query, params)
        results = cursor.fetchall()

        # Build dictionary from results
        # Convert timestamp to string format to match hour_timestamp keys
        for token_contract, timestamp, funding_rate in results:
            timestamp_str = to_datetime_str(to_seconds(timestamp))
            rates_dict[(token_contract, timestamp_str)] = funding_rate

    finally:
        conn.close()

    return rates_dict


def interpolate_perp_rates(
    tracker,
    start_date=None,
    end_date=None,
    batch_size=1000
):
    """
    Interpolate perp margin rates into rates_snapshot.

    Args:
        tracker: RateTracker instance
        start_date: Optional start date filter
        end_date: Optional end date filter
        batch_size: Number of timestamps to process per batch

    Returns:
        Number of rows inserted
    """
    print(f"\n[1/3] Fetching unique timestamps from rates_snapshot...")

    # First check: how many timestamps exist in total?
    conn = tracker._get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(DISTINCT timestamp) FROM rates_snapshot")
        total_count = cursor.fetchone()[0]
        print(f"  Total unique timestamps in rates_snapshot: {total_count}")

        # Second check: what's the date range?
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM rates_snapshot")
        min_ts, max_ts = cursor.fetchone()
        print(f"  Date range in database: {min_ts} to {max_ts}")

        # Third check: sample some timestamps to see their format
        cursor.execute("SELECT timestamp FROM rates_snapshot LIMIT 5")
        sample_timestamps = cursor.fetchall()
        print(f"  Sample timestamps:")
        for ts in sample_timestamps:
            print(f"    {ts[0]} (type: {type(ts[0])})")

    except Exception as e:
        print(f"  ERROR checking rates_snapshot: {e}")
    finally:
        conn.close()

    timestamps = fetch_unique_timestamps(tracker, start_date, end_date)
    print(f"  Found {len(timestamps)} unique timestamps in requested range")

    print(f"\n[2/3] Processing timestamps in batches of {batch_size}...")

    rows_inserted = 0

    for i in range(0, len(timestamps), batch_size):
        batch = timestamps[i:i+batch_size]
        rows_to_insert = []

        # Get all unique hour timestamps for this batch
        hour_timestamps_set = set()
        timestamp_to_hour = {}
        for timestamp in batch:
            hour_timestamp = round_to_hour(timestamp)
            hour_timestamps_set.add(hour_timestamp)
            timestamp_to_hour[str(timestamp)] = hour_timestamp

        # Fetch all perp rates for this batch in bulk
        print(f"  Fetching perp rates for {len(hour_timestamps_set)} unique hours...")
        rates_dict = fetch_perp_rates_bulk(tracker, list(hour_timestamps_set), BLUEFIN_PERP_MARKETS)

        # Build insert rows using the pre-fetched rates
        for timestamp in batch:
            hour_timestamp = timestamp_to_hour[str(timestamp)]

            for base_token in BLUEFIN_PERP_MARKETS:
                token_contract = f"0x{base_token}-USDC-PERP_bluefin"
                funding_rate = rates_dict.get((token_contract, hour_timestamp))

                if funding_rate is not None:
                    rows_to_insert.append((
                        to_datetime_str(to_seconds(timestamp)),  # timestamp
                        'Bluefin',  # protocol
                        f'{base_token}-USDC-PERP',  # token
                        token_contract,  # token_contract
                        f'{base_token}-PERP',  # market
                        funding_rate  # perp_margin_rate
                        # All other columns will be NULL (use_for_pnl, price_usd, etc.)
                    ))

        if rows_to_insert:
            conn = tracker._get_connection()
            cursor = conn.cursor()

            if tracker.use_cloud:
                execute_values(
                    cursor,
                    """
                    INSERT INTO rates_snapshot (
                        timestamp, protocol, token, token_contract, market,
                        perp_margin_rate
                    ) VALUES %s
                    ON CONFLICT (timestamp, protocol, token_contract) DO NOTHING
                    """,
                    rows_to_insert
                )
            else:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO rates_snapshot (
                        timestamp, protocol, token, token_contract, market,
                        perp_margin_rate
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows_to_insert
                )

            conn.commit()
            rows_inserted += len(rows_to_insert)
            conn.close()

            print(f"  Processed {i+len(batch)}/{len(timestamps)} timestamps " +
                  f"({rows_inserted} rows inserted)")

    print(f"\n[3/3] Complete! Inserted {rows_inserted} perp market rows")
    return rows_inserted


def main():
    parser = argparse.ArgumentParser(
        description='Interpolate perp margin rates into rates_snapshot'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date (YYYY-MM-DD HH:MM:SS) - optional'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date (YYYY-MM-DD HH:MM:SS) - optional'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Number of timestamps to process per batch (default: 1000)'
    )

    args = parser.parse_args()

    tracker = RateTracker(
        use_cloud=settings.USE_CLOUD_DB,
        connection_url=settings.SUPABASE_URL
    )

    rows = interpolate_perp_rates(
        tracker,
        start_date=args.start_date,
        end_date=args.end_date,
        batch_size=args.batch_size
    )

    print(f"\n✅ Interpolation complete: {rows} rows inserted")


if __name__ == '__main__':
    main()
