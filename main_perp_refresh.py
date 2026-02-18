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
        print("\n[3/3] Registering proxy tokens in token_registry...")
        tokens_registered = tracker.register_perp_tokens(perp_rates_df)

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
