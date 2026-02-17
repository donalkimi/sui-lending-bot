#!/usr/bin/env python3
"""
One-time script to seed historical Bluefin funding rates.
Fetches maximum available history with pagination.

Usage:
    python scripts/backfill_bluefin_funding_rates.py         # Max history
    python scripts/backfill_bluefin_funding_rates.py --days 90  # Last 90 days
"""

import sys
import argparse
from datetime import datetime
from data.bluefin.bluefin_reader import BluefinReader
from data.rate_tracker import RateTracker
from config import settings


def backfill_historical_rates(lookback_days: int = None):
    """
    Backfill historical funding rates from Bluefin.

    This is a ONE-TIME operation. After initial seeding, the hourly
    job (main_perp_refresh.py) will keep data up-to-date by fetching
    the last 100 rates each hour.

    Args:
        lookback_days: Number of days to fetch (None = maximum available)

    Returns:
        Exit code (0 = success, 1 = error)
    """
    print("=== Bluefin Historical Rate Backfill (ONE-TIME) ===\n")
    print(f"Tracking markets: {', '.join(settings.BLUEFIN_PERP_MARKETS)}\n")

    if lookback_days:
        print(f"Lookback period: Last {lookback_days} days")
    else:
        print("Lookback period: Maximum available history")

    try:
        reader = BluefinReader()
        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

        # 1. Fetch historical rates for all whitelisted markets with pagination
        print("\n[1/3] Fetching historical rates (this may take several minutes)...")
        historical_df = reader.get_all_markets_historical(
            lookback_days=lookback_days
        )

        if historical_df.empty:
            print("⚠️  No historical rates fetched. Exiting.")
            return 1

        print(f"\n✅ Fetched {len(historical_df)} historical rate snapshots")
        print(f"Date range: {historical_df['timestamp'].min()} to {historical_df['timestamp'].max()}")

        # Show summary per market
        for base_token in historical_df['base_token'].unique():
            token_df = historical_df[historical_df['base_token'] == base_token]
            min_ts = token_df['timestamp'].min()
            max_ts = token_df['timestamp'].max()
            print(f"  {base_token}-USDC-PERP: {len(token_df)} rates from {min_ts} to {max_ts}")

        # 2. Save to perp_margin_rates table (batch inserts)
        print("\n[2/3] Saving to database with ON CONFLICT DO UPDATE (overwrites existing)...")
        rows_saved = tracker.save_perp_rates(historical_df)

        if rows_saved == 0:
            print("⚠️  No rates saved. Exiting.")
            return 1

        print(f"✅ Saved/updated {rows_saved} historical rates in perp_margin_rates")

        # 2b. Register proxy tokens
        print("\nRegistering proxy tokens in token_registry...")
        tokens_registered = tracker.register_perp_tokens(historical_df)
        print(f"✅ Registered {tokens_registered} perp tokens")

        # 3. Backfill rates_snapshot with interpolated perp rates
        print("\n[3/3] Backfilling rates_snapshot.perp_margin_rate column...")

        earliest_date = historical_df['timestamp'].min()
        latest_date = historical_df['timestamp'].max()

        # Explicitly pass current time for end_date (following Principle #2)
        current_time = datetime.now()

        rows_updated = tracker.backfill_perp_rates_to_snapshot(
            start_date=earliest_date,
            end_date=latest_date if latest_date < current_time else current_time
        )

        print(f"✅ Updated {rows_updated} rates_snapshot rows")

        print("\n=== Backfill Complete ===")
        print(f"\nSummary:")
        print(f"  • Total rates fetched: {len(historical_df)}")
        print(f"  • Rates saved to perp_margin_rates: {rows_saved}")
        print(f"  • Tokens registered: {tokens_registered}")
        print(f"  • rates_snapshot rows updated: {rows_updated}")
        print(f"\n✅ Historical data successfully seeded!")
        print(f"   The hourly cron job (main_perp_refresh.py) will maintain data going forward.\n")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: Backfill failed")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Backfill historical Bluefin perpetual funding rates'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of days to backfill (None = maximum available)'
    )

    args = parser.parse_args()

    exit_code = backfill_historical_rates(lookback_days=args.days)
    sys.exit(exit_code)
