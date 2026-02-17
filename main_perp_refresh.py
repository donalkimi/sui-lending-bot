#!/usr/bin/env python3
"""
Perp Margin Rate Refresh Pipeline

Runs independently at 5 minutes after the hour (separate from main lending rate refresh).
Fetches last 100 perp funding rates from Bluefin to catch up on missed data.
"""

import sys
from datetime import datetime, timedelta
from data.bluefin.bluefin_reader import BluefinReader
from data.rate_tracker import RateTracker
from config import settings


def main():
    """
    Main entry point for perp rate refresh.

    Flow:
        1. Fetch last 100 rates per whitelisted market from Bluefin
        2. Save to perp_margin_rates table (ON CONFLICT DO UPDATE)
        3. Register proxy tokens in token_registry
        4. Interpolate to latest rates_snapshot
        5. Backfill recent snapshots if new markets detected
    """
    print("\n=== Perp Margin Rate Refresh Started ===")
    print(f"Time: {datetime.now()}")
    print(f"Tracking markets: {', '.join(settings.BLUEFIN_PERP_MARKETS)}\n")

    try:
        # Step 1: Fetch last 100 perp rates from Bluefin
        print("[1/5] Fetching last 100 perp rates per market from Bluefin...")
        reader = BluefinReader()
        perp_rates_df = reader.get_recent_funding_rates(limit=100)

        if perp_rates_df.empty:
            print("⚠️  No perp rates fetched. Exiting.")
            return 1

        print(f"✅ Fetched {len(perp_rates_df)} perp rates\n")

        # Show summary per market
        for base_token in perp_rates_df['base_token'].unique():
            token_df = perp_rates_df[perp_rates_df['base_token'] == base_token]
            min_ts = token_df['timestamp'].min()
            max_ts = token_df['timestamp'].max()
            latest_rate = token_df[token_df['timestamp'] == max_ts]['funding_rate_annual'].iloc[0]
            print(f"  {base_token}-USDC-PERP: {len(token_df)} rates from {min_ts} to {max_ts}")
            print(f"    Latest rate: {latest_rate * 100:.4f}% APR")

        # Step 2: Save to perp_margin_rates table
        print("\n[2/5] Saving to perp_margin_rates table...")
        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

        rows_saved = tracker.save_perp_rates(perp_rates_df)
        if rows_saved == 0:
            print("⚠️  No rates saved. Exiting.")
            return 1

        # Step 3: Register proxy tokens in token_registry
        print("\n[3/5] Registering proxy tokens in token_registry...")
        tokens_registered = tracker.register_perp_tokens(perp_rates_df)

        # Step 4: Interpolate to latest rates_snapshot
        print("\n[4/5] Interpolating perp rates to latest rates_snapshot...")
        latest_snapshot_time = tracker.get_latest_snapshot_timestamp()

        if latest_snapshot_time:
            print(f"  Latest snapshot: {latest_snapshot_time}")
            rows_updated = tracker.interpolate_perp_rates_to_snapshot(
                timestamp=latest_snapshot_time,
                backfill_existing=False  # Only populate new NULL values
            )
            print(f"  ✅ Updated {rows_updated} rates_snapshot rows")
        else:
            print("  ⚠️  No rates_snapshot found (table may be empty)")

        # Step 5: Check for new markets and backfill if needed
        print("\n[5/5] Checking for new markets...")
        new_markets = tracker.detect_new_perp_markets(perp_rates_df)

        if new_markets:
            print(f"  🆕 New markets detected: {', '.join(new_markets)}")
            print("  ⏳ Backfilling historical rates_snapshot rows (last 7 days)...")

            current_time = datetime.now()
            rows_backfilled = tracker.backfill_perp_rates_to_snapshot(
                start_date=current_time - timedelta(days=7),
                end_date=current_time
            )
            print(f"  ✅ Backfilled {rows_backfilled} rows")
        else:
            print("  No new markets detected")

        print("\n=== Perp Margin Rate Refresh Complete ===\n")
        return 0

    except Exception as e:
        print(f"\n❌ ERROR: Perp refresh failed")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
