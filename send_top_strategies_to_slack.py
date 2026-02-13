#!/usr/bin/env python3
"""
Simple script to analyze strategies and send top ones to Slack
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.refresh_pipeline import refresh_pipeline

if __name__ == "__main__":
    print("🚀 Running strategy analysis and sending to Slack...")
    print("=" * 80)

    # Run the full pipeline with Slack notifications enabled
    result = refresh_pipeline(
        save_snapshots=True,
        send_slack_notifications=True  # Enable Slack notifications
    )

    if result and result.timestamp:
        print(f"\n✅ SUCCESS!")
        print(f"   - Analysis completed at: {result.timestamp}")
        print(f"   - Data saved to database")
        print(f"   - Notification sent to Slack")
        print("\n💡 Check your Slack channel: #sui_lending_bot")
    else:
        print(f"\n❌ FAILED - Check error logs above")

    print("=" * 80)
