#!/usr/bin/env python3
"""
Delete all positions created on or after a specific date.

Usage:
    python Scripts/delete_positions_by_date.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection
from datetime import datetime


def delete_positions_by_date(cutoff_date_str: str):
    """
    Delete all positions with entry_timestamp >= cutoff_date.

    Args:
        cutoff_date_str: Date string in format "YYYY-MM-DD HH:MM"
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Convert cutoff date to timestamp format
        cutoff_datetime = datetime.strptime(cutoff_date_str, "%Y-%m-%d %H:%M")

        print(f"Cutoff date: {cutoff_datetime}")
        print("=" * 60)

        # First, show what will be deleted
        cursor.execute("""
            SELECT
                position_id,
                token1,
                token2,
                token3,
                protocol_a,
                protocol_b,
                deployment_usd,
                entry_timestamp,
                portfolio_id
            FROM positions
            WHERE entry_timestamp >= %s
            ORDER BY entry_timestamp
        """, (cutoff_datetime,))

        positions = cursor.fetchall()

        if not positions:
            print("✅ No positions found matching the criteria")
            return

        print(f"Found {len(positions)} position(s) to delete:")
        print()

        total_deployed = 0
        for pos in positions:
            position_id, token1, token2, token3, protocol_a, protocol_b, deployment, entry_ts, portfolio_id = pos
            total_deployed += deployment

            print(f"  Position ID: {position_id}")
            print(f"    Tokens: {token1} → {token2} → {token3 or 'N/A'}")
            print(f"    Protocols: {protocol_a} ↔ {protocol_b}")
            print(f"    Deployment: ${deployment:,.2f}")
            print(f"    Entry: {entry_ts}")
            print(f"    Portfolio: {portfolio_id or 'NULL (standalone)'}")
            print()

        print(f"Total deployment to delete: ${total_deployed:,.2f}")
        print("=" * 60)

        # Confirm deletion
        response = input("\n⚠️  Proceed with deletion? (yes/no): ").strip().lower()

        if response != 'yes':
            print("❌ Deletion cancelled")
            return

        # Delete positions
        cursor.execute("""
            DELETE FROM positions
            WHERE entry_timestamp >= %s
        """, (cutoff_datetime,))

        deleted_count = cursor.rowcount
        conn.commit()

        print()
        print("=" * 60)
        print(f"✅ Successfully deleted {deleted_count} position(s)")
        print(f"   Total deployment removed: ${total_deployed:,.2f}")

        # Verify
        cursor.execute("SELECT COUNT(*) FROM positions")
        remaining = cursor.fetchone()[0]
        print(f"   Remaining positions: {remaining}")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Delete Positions by Date")
    print("=" * 60)
    print()

    # Cutoff date: 2026-02-10 15:01
    cutoff_date = "2026-02-10 15:01"

    print(f"This will delete all positions created on or after:")
    print(f"  {cutoff_date}")
    print()

    delete_positions_by_date(cutoff_date)
