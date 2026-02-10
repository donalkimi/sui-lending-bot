#!/usr/bin/env python3
"""
Backfill portfolio_id for existing standalone positions.

This script updates all positions with NULL portfolio_id to 'single positions'
to match the design pattern where:
- Standalone positions have portfolio_id='single positions'
- Portfolio positions have portfolio_id=<UUID>

Usage:
    python Scripts/backfill_single_positions.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection
from config import settings


def backfill_single_positions():
    """Update existing positions with NULL portfolio_id to 'single positions'."""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Get count before
        cursor.execute("SELECT COUNT(*) FROM positions WHERE portfolio_id IS NULL")
        null_count = cursor.fetchone()[0]

        print(f"Found {null_count} positions with NULL portfolio_id")

        if null_count == 0:
            print("✅ No positions to update - all positions already have portfolio_id set")
            return

        # Step 1: Create special portfolio record for 'single positions' if it doesn't exist
        print("Creating special 'single positions' portfolio record...")
        cursor.execute("""
            INSERT INTO portfolios (
                portfolio_id,
                portfolio_name,
                status,
                is_paper_trade,
                created_timestamp,
                entry_timestamp,
                target_portfolio_size,
                actual_allocated_usd,
                utilization_pct,
                entry_weighted_net_apr,
                constraints_json
            )
            SELECT
                'single positions',
                'Single Positions',
                'active',
                TRUE,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                0.0,
                0.0,
                0.0,
                0.0,
                '{}'
            WHERE NOT EXISTS (
                SELECT 1 FROM portfolios WHERE portfolio_id = 'single positions'
            )
        """)

        # Step 2: Update NULL portfolio_id to 'single positions'
        print(f"Updating {null_count} positions to portfolio_id='single positions'...")
        cursor.execute("""
            UPDATE positions
            SET portfolio_id = 'single positions'
            WHERE portfolio_id IS NULL
        """)

        conn.commit()

        # Verify the update
        cursor.execute("""
            SELECT
                COUNT(*) as total_positions,
                SUM(CASE WHEN portfolio_id = 'single positions' THEN 1 ELSE 0 END) as standalone_positions,
                SUM(CASE WHEN portfolio_id != 'single positions' AND portfolio_id IS NOT NULL THEN 1 ELSE 0 END) as portfolio_positions,
                SUM(CASE WHEN portfolio_id IS NULL THEN 1 ELSE 0 END) as null_positions
            FROM positions
        """)

        result = cursor.fetchone()
        total, standalone, portfolio, null = result

        print("\n✅ Migration complete!")
        print(f"   Total positions: {total}")
        print(f"   Standalone positions: {standalone}")
        print(f"   Portfolio positions: {portfolio}")
        print(f"   NULL portfolio_id: {null}")

        if null > 0:
            print(f"\n⚠️  Warning: Still have {null} positions with NULL portfolio_id")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Backfilling portfolio_id for standalone positions")
    print("=" * 60)
    print()

    backfill_single_positions()
