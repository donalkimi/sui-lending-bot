#!/usr/bin/env python3
"""
Purge all positions from the database
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.dashboard_utils import get_db_connection


def purge_all_positions(force=False):
    """Delete all positions from the database

    Args:
        force: If True, skip confirmation prompt
    """
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to connect to database")
        return

    cursor = conn.cursor()

    try:
        # Get count before deletion
        cursor.execute("SELECT COUNT(*) FROM positions")
        position_count = cursor.fetchone()[0]

        print(f"\n📊 Current Database Status:")
        print(f"   Positions: {position_count}")

        if position_count == 0:
            print("\n✅ Database is already empty - nothing to delete")
            return

        # Confirm before deletion (unless forced)
        if not force:
            print("\n⚠️  WARNING: This will delete ALL positions!")
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Operation cancelled")
                return
        else:
            print("\n⚠️  Force flag enabled - skipping confirmation")

        # Delete all positions
        print("\n🗑️  Deleting positions...")
        cursor.execute("DELETE FROM positions")
        conn.commit()

        print(f"\n✅ Successfully deleted:")
        print(f"   - {position_count} positions")

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM positions")
        remaining_positions = cursor.fetchone()[0]

        print(f"\n📊 Final Database Status:")
        print(f"   Positions: {remaining_positions}")

        if remaining_positions == 0:
            print("\n✅ Database successfully purged!")
        else:
            print("\n⚠️  Warning: Some records may still remain")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    # Check for --force flag
    force = "--force" in sys.argv or "-f" in sys.argv
    purge_all_positions(force=force)
