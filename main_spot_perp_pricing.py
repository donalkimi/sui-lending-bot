#!/usr/bin/env python3
"""
Spot/Perp Pricing Refresh Pipeline

Runs independently (separate from main lending rate refresh).
Fetches perp orderbook and spot index prices from Bluefin, then computes
the AMM spot/perp basis for all (perp, spot_contract) pairs.

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
        1. Fetch AMM spot/perp basis (aggregator quotes) for all (perp, spot_contract) pairs
        2. Save to spot_perp_basis table
    """
    print("\n" + "="*60)
    print("Spot/Perp Pricing Refresh Started")
    print("="*60)

    # Get current timestamp (rounded to hour)
    # This is the snapshot time passed to all downstream functions — never use datetime.now()
    # inside those functions for the timestamp field.
    current_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    timestamp_seconds = to_seconds(current_time)

    print(f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Timestamp: {timestamp_seconds}")
    print(f"Markets: {', '.join(settings.BLUEFIN_PERP_MARKETS)}\n")

    try:
        reader = BluefinPricingReader()
        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

        # Step 1: Fetch AMM spot/perp basis for all (perp, spot_contract) pairs
        print("[1/2] Fetching spot/perp basis via Bluefin aggregator...")
        basis_df = reader.get_spot_perp_basis(timestamp=timestamp_seconds)

        if basis_df.empty:
            print("[WARN] No basis data fetched.")
            return 1

        # Step 2: Save basis rows
        print("\n[2/2] Saving to spot_perp_basis table...")
        rows_saved_basis = tracker.save_spot_perp_basis(basis_df)
        if rows_saved_basis == 0:
            print("[WARN] No basis rows saved. Check for errors above.")
            return 1

        print("\n" + "="*60)
        print(f"[SUCCESS] Pricing Refresh Complete")
        print(f"          spot_perp_basis: {rows_saved_basis} rows")
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
