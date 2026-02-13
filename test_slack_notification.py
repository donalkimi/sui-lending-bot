#!/usr/bin/env python3
"""
Quick script to test Slack notifications manually
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from alerts.slack_notifier import SlackNotifier
from data.refresh_pipeline import refresh_pipeline
import time

def test_simple_notification():
    """Send a simple test notification"""
    print("=" * 80)
    print("TEST 1: Simple Rebalance Notification")
    print("=" * 80)

    notifier = SlackNotifier()

    # Test rebalance notification with mock data
    success = notifier.alert_position_rebalanced(
        position_id="12345678-1234-1234-1234-123456789abc",
        token1="USDC",
        token2="DEEP",
        token3="USDC",
        protocol_a="Navi",
        protocol_b="Suilend",
        liq_dist_2a_before=0.285,  # 28.5%
        liq_dist_2a_after=0.321,   # 32.1%
        liq_dist_2b_before=0.452,  # 45.2%
        liq_dist_2b_after=0.488,   # 48.8%
        rebalance_timestamp=int(time.time())
    )

    if success:
        print("✅ Rebalance notification sent successfully!")
    else:
        print("❌ Rebalance notification failed")

    return success


def test_top_strategies_from_live_data():
    """Run analysis and send top strategies to Slack"""
    print("\n" + "=" * 80)
    print("TEST 2: Top Strategies from Live Analysis")
    print("=" * 80)

    print("\n📊 Running refresh_pipeline to get live strategies...")

    # Run the full analysis pipeline
    result = refresh_pipeline(
        save_snapshots=True,
        send_slack_notifications=True  # This will send the notification!
    )

    if result and result.timestamp:
        print(f"✅ Analysis completed at timestamp: {result.timestamp}")
        print(f"✅ Slack notification should have been sent!")
        return True
    else:
        print("❌ Analysis failed")
        return False


def test_error_notification():
    """Send a test error notification"""
    print("\n" + "=" * 80)
    print("TEST 3: Error Notification")
    print("=" * 80)

    notifier = SlackNotifier()

    success = notifier.alert_error("This is a test error message from the manual test script")

    if success:
        print("✅ Error notification sent successfully!")
    else:
        print("❌ Error notification failed")

    return success


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Slack notifications")
    parser.add_argument(
        "--test",
        choices=["rebalance", "strategies", "error", "all"],
        default="rebalance",
        help="Which notification to test"
    )

    args = parser.parse_args()

    print("\n🔔 Slack Notification Test Script")
    print("=" * 80)

    results = []

    if args.test in ["rebalance", "all"]:
        results.append(("Rebalance", test_simple_notification()))

    if args.test in ["strategies", "all"]:
        results.append(("Top Strategies", test_top_strategies_from_live_data()))

    if args.test in ["error", "all"]:
        results.append(("Error", test_error_notification()))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{name}: {status}")

    print("\n💡 Check your Slack channel: #sui_lending_bot")
    print("=" * 80)
