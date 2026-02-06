#!/usr/bin/env python3
"""
Purge all positions, rebalances, and statistics from the database

This script deletes:
- All statistics from the position_statistics table
- All rebalances from the position_rebalances table
- All positions from the positions table

Use this to start fresh after major calculation changes (e.g., LLTV switch).
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.dashboard_utils import get_db_connection


def purge_all_positions(force=False):
    """Delete all positions, rebalances, and statistics from the database

    Args:
        force: If True, skip confirmation prompt
    """
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to connect to database")
        return

    cursor = conn.cursor()

    try:
        # Get counts before deletion
        cursor.execute("SELECT COUNT(*) FROM positions")
        position_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM position_rebalances")
        rebalance_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM position_statistics")
        statistics_count = cursor.fetchone()[0]

        print(f"\n📊 Current Database Status:")
        print(f"   Positions: {position_count}")
        print(f"   Rebalances: {rebalance_count}")
        print(f"   Statistics: {statistics_count}")

        if position_count == 0 and rebalance_count == 0 and statistics_count == 0:
            print("\n✅ Database is already empty - nothing to delete")
            conn.close()
            return

        # Confirm before deletion (unless forced)
        if not force:
            print("\n⚠️  WARNING: This will delete ALL positions, rebalances, and statistics!")
            print("   This action cannot be undone.")
            response = input("\nAre you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Operation cancelled")
                conn.close()
                return
        else:
            print("\n⚠️  Force flag enabled - skipping confirmation")

        # Delete in order: statistics → rebalances → positions
        # (Statistics may reference positions, rebalances reference positions)
        print("\n🗑️  Deleting all statistics...")
        cursor.execute("DELETE FROM position_statistics")

        print("🗑️  Deleting all rebalances...")
        cursor.execute("DELETE FROM position_rebalances")

        print("🗑️  Deleting all positions...")
        cursor.execute("DELETE FROM positions")

        conn.commit()

        print(f"\n✅ Successfully deleted:")
        print(f"   - {statistics_count} statistics records")
        print(f"   - {rebalance_count} rebalances")
        print(f"   - {position_count} positions")

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM positions")
        remaining_positions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM position_rebalances")
        remaining_rebalances = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM position_statistics")
        remaining_statistics = cursor.fetchone()[0]

        print(f"\n📊 Final Database Status:")
        print(f"   Positions: {remaining_positions}")
        print(f"   Rebalances: {remaining_rebalances}")
        print(f"   Statistics: {remaining_statistics}")

        if remaining_positions == 0 and remaining_rebalances == 0 and remaining_statistics == 0:
            print("\n✅ Database successfully purged!")
        else:
            print("\n⚠️  Warning: Some records may still remain")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Purge all positions, rebalances, and statistics from the database"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()
    purge_all_positions(force=args.force)
