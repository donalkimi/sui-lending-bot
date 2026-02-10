#!/usr/bin/env python3
"""
Revert portfolio_id from 'single positions' back to NULL for standalone positions.

This script:
1. Updates positions with portfolio_id='single positions' to NULL
2. Deletes the fake 'single positions' portfolio record from portfolios table

Usage:
    python Scripts/revert_to_null_portfolio_id.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection
from config import settings


def revert_to_null():
    """Revert 'single positions' back to NULL for standalone positions."""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Check how many positions have 'single positions'
        cursor.execute("SELECT COUNT(*) FROM positions WHERE portfolio_id = 'single positions'")
        count = cursor.fetchone()[0]

        print(f"Found {count} positions with portfolio_id='single positions'")

        if count > 0:
            # Step 2: Update 'single positions' to NULL
            print(f"Reverting {count} positions to portfolio_id=NULL...")
            cursor.execute("""
                UPDATE positions
                SET portfolio_id = NULL
                WHERE portfolio_id = 'single positions'
            """)

        # Step 3: Delete the fake portfolio record
        cursor.execute("SELECT COUNT(*) FROM portfolios WHERE portfolio_id = 'single positions'")
        portfolio_exists = cursor.fetchone()[0]

        if portfolio_exists > 0:
            print("Deleting fake 'single positions' portfolio record...")
            cursor.execute("""
                DELETE FROM portfolios
                WHERE portfolio_id = 'single positions'
            """)

        conn.commit()

        # Verify the changes
        cursor.execute("""
            SELECT
                COUNT(*) as total_positions,
                SUM(CASE WHEN portfolio_id IS NULL THEN 1 ELSE 0 END) as null_positions,
                SUM(CASE WHEN portfolio_id IS NOT NULL THEN 1 ELSE 0 END) as portfolio_positions
            FROM positions
        """)

        result = cursor.fetchone()
        total, null_count, portfolio_count = result

        print("\n✅ Migration complete!")
        print(f"   Total positions: {total}")
        print(f"   Standalone positions (NULL): {null_count}")
        print(f"   Portfolio positions: {portfolio_count}")

        # Check portfolios table
        cursor.execute("SELECT COUNT(*) FROM portfolios WHERE portfolio_id = 'single positions'")
        fake_portfolio_count = cursor.fetchone()[0]

        if fake_portfolio_count > 0:
            print(f"\n⚠️  Warning: Still have {fake_portfolio_count} fake portfolio records")
        else:
            print("   Fake portfolio record removed: ✓")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Reverting to NULL for standalone positions")
    print("=" * 60)
    print()

    revert_to_null()
