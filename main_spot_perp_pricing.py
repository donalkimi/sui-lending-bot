#!/usr/bin/env python3
"""
Spot/Perp Pricing Refresh Pipeline

Runs independently (separate from main lending rate refresh).
Fetches perp orderbook and spot index prices from Bluefin.

Usage:
    python main_spot_perp_pricing.py
"""

import sys
from datetime import datetime, timezone
from data.bluefin.bluefin_pricing_reader import BluefinPricingReader
from data.rate_tracker import RateTracker
from config import settings
from utils.time_helpers import to_seconds


def main():
    """
    Main entry point for spot/perp pricing refresh.

    Flow:
        1. Fetch perp ticker + spot index data from Bluefin API
        2. Save to spot_perp_pricing table
    """
    print("\n" + "="*60)
    print("Spot/Perp Pricing Refresh Started")
    print("="*60)

    # Get current timestamp (rounded to hour)
    current_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    timestamp_seconds = to_seconds(current_time)

    print(f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Timestamp: {timestamp_seconds}")
    print(f"Markets: {', '.join(settings.BLUEFIN_PERP_MARKETS)}\n")

    try:
        # Step 1: Fetch pricing data
        print("[1/2] Fetching spot and perp pricing from Bluefin API...")
        reader = BluefinPricingReader()
        pricing_df = reader.get_spot_perp_pricing(timestamp=timestamp_seconds)

        if pricing_df.empty:
            print("\n[WARN] No pricing data fetched. Exiting.")
            print("    This may indicate API issues or incorrect endpoint format.")
            print("    Check the Bluefin API documentation and update BluefinPricingReader.")
            return 1

        # Step 2: Save to database
        print("\n[2/2] Saving to spot_perp_pricing table...")
        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

        rows_saved = tracker.save_spot_perp_pricing(pricing_df)
        if rows_saved == 0:
            print("[WARN] No rows saved. Check for errors above.")
            return 1

        print("\n" + "="*60)
        print(f"[SUCCESS] Pricing Refresh Complete - {rows_saved} rows saved")
        print("="*60 + "\n")
        return 0

    except Exception as e:
        print("\n" + "="*60)
        print("[ERROR] Pricing refresh failed")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
