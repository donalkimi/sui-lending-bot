"""
Migration Script: Add position_rebalances table and extend positions table

This script adds:
1. position_rebalances table for storing rebalance history
2. Three new columns to positions table:
   - accumulated_realised_pnl
   - rebalance_count
   - last_rebalance_timestamp
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path(__file__).parent / "lending_rates.db"

def migrate():
    """Apply migration"""
    print("=" * 70)
    print("MIGRATION: Add Rebalance Support")
    print("=" * 70)
    print(f"Database: {db_path}\n")

    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if already migrated
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='position_rebalances'
        """)
        if cursor.fetchone():
            print("[INFO] position_rebalances table already exists")
            print("[INFO] Migration may have already been applied")
            conn.close()
            return True

        print("Step 1: Adding new columns to positions table...")

        # Add accumulated_realised_pnl
        try:
            cursor.execute("""
                ALTER TABLE positions
                ADD COLUMN accumulated_realised_pnl DECIMAL(20, 10) DEFAULT 0.0
            """)
            print("  - Added accumulated_realised_pnl column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  - accumulated_realised_pnl already exists")
            else:
                raise

        # Add rebalance_count
        try:
            cursor.execute("""
                ALTER TABLE positions
                ADD COLUMN rebalance_count INTEGER DEFAULT 0
            """)
            print("  - Added rebalance_count column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  - rebalance_count already exists")
            else:
                raise

        # Add last_rebalance_timestamp
        try:
            cursor.execute("""
                ALTER TABLE positions
                ADD COLUMN last_rebalance_timestamp TIMESTAMP
            """)
            print("  - Added last_rebalance_timestamp column")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("  - last_rebalance_timestamp already exists")
            else:
                raise

        print("\nStep 2: Creating position_rebalances table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_rebalances (
                -- Rebalance Identification
                rebalance_id TEXT PRIMARY KEY,
                position_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,

                -- Timing
                opening_timestamp TIMESTAMP NOT NULL,
                closing_timestamp TIMESTAMP NOT NULL,

                -- Position State (multipliers - constant during segment)
                deployment_usd DECIMAL(20, 10) NOT NULL,
                L_A DECIMAL(10, 6) NOT NULL,
                B_A DECIMAL(10, 6) NOT NULL,
                L_B DECIMAL(10, 6) NOT NULL,
                B_B DECIMAL(10, 6) NOT NULL,

                -- Opening State (rates, prices)
                opening_lend_rate_1A DECIMAL(10, 6) NOT NULL,
                opening_borrow_rate_2A DECIMAL(10, 6) NOT NULL,
                opening_lend_rate_2B DECIMAL(10, 6) NOT NULL,
                opening_borrow_rate_3B DECIMAL(10, 6) NOT NULL,
                opening_price_1A DECIMAL(20, 10) NOT NULL,
                opening_price_2A DECIMAL(20, 10) NOT NULL,
                opening_price_2B DECIMAL(20, 10) NOT NULL,
                opening_price_3B DECIMAL(20, 10) NOT NULL,

                -- Closing State (rates, prices)
                closing_lend_rate_1A DECIMAL(10, 6) NOT NULL,
                closing_borrow_rate_2A DECIMAL(10, 6) NOT NULL,
                closing_lend_rate_2B DECIMAL(10, 6) NOT NULL,
                closing_borrow_rate_3B DECIMAL(10, 6) NOT NULL,
                closing_price_1A DECIMAL(20, 10) NOT NULL,
                closing_price_2A DECIMAL(20, 10) NOT NULL,
                closing_price_2B DECIMAL(20, 10) NOT NULL,
                closing_price_3B DECIMAL(20, 10) NOT NULL,

                -- Collateral Ratios
                collateral_ratio_1A DECIMAL(10, 6) NOT NULL,
                collateral_ratio_2B DECIMAL(10, 6) NOT NULL,

                -- Rebalance Actions (text descriptions)
                entry_action_1A TEXT,
                entry_action_2A TEXT,
                entry_action_2B TEXT,
                entry_action_3B TEXT,
                exit_action_1A TEXT,
                exit_action_2A TEXT,
                exit_action_2B TEXT,
                exit_action_3B TEXT,

                -- Token Amounts
                entry_token_amount_1A DECIMAL(20, 10) NOT NULL,
                entry_token_amount_2A DECIMAL(20, 10) NOT NULL,
                entry_token_amount_2B DECIMAL(20, 10) NOT NULL,
                entry_token_amount_3B DECIMAL(20, 10) NOT NULL,
                exit_token_amount_1A DECIMAL(20, 10) NOT NULL,
                exit_token_amount_2A DECIMAL(20, 10) NOT NULL,
                exit_token_amount_2B DECIMAL(20, 10) NOT NULL,
                exit_token_amount_3B DECIMAL(20, 10) NOT NULL,

                -- USD Sizes
                entry_size_usd_1A DECIMAL(20, 10) NOT NULL,
                entry_size_usd_2A DECIMAL(20, 10) NOT NULL,
                entry_size_usd_2B DECIMAL(20, 10) NOT NULL,
                entry_size_usd_3B DECIMAL(20, 10) NOT NULL,
                exit_size_usd_1A DECIMAL(20, 10) NOT NULL,
                exit_size_usd_2A DECIMAL(20, 10) NOT NULL,
                exit_size_usd_2B DECIMAL(20, 10) NOT NULL,
                exit_size_usd_3B DECIMAL(20, 10) NOT NULL,

                -- Realised Metrics (calculated once at rebalance time)
                realised_fees DECIMAL(20, 10) NOT NULL,
                realised_pnl DECIMAL(20, 10) NOT NULL,
                realised_lend_earnings DECIMAL(20, 10) NOT NULL,
                realised_borrow_costs DECIMAL(20, 10) NOT NULL,

                -- Metadata
                rebalance_reason TEXT,
                rebalance_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE CASCADE,
                UNIQUE (position_id, sequence_number)
            )
        """)
        print("  - Created position_rebalances table")

        print("\nStep 3: Creating indexes...")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rebalances_position
            ON position_rebalances(position_id)
        """)
        print("  - Created idx_rebalances_position")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rebalances_sequence
            ON position_rebalances(position_id, sequence_number)
        """)
        print("  - Created idx_rebalances_sequence")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rebalances_timestamps
            ON position_rebalances(opening_timestamp, closing_timestamp)
        """)
        print("  - Created idx_rebalances_timestamps")

        # Commit changes
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        print("\nVerifying migration...")

        # Verify
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='position_rebalances'
        """)
        if cursor.fetchone():
            print("  [PASS] position_rebalances table exists")
        else:
            print("  [FAIL] position_rebalances table NOT found")
            conn.close()
            return False

        cursor.execute("PRAGMA table_info(positions)")
        positions_columns = {row[1] for row in cursor.fetchall()}
        new_columns = {'accumulated_realised_pnl', 'rebalance_count', 'last_rebalance_timestamp'}

        if new_columns.issubset(positions_columns):
            print("  [PASS] All new columns added to positions table")
        else:
            missing = new_columns - positions_columns
            print(f"  [FAIL] Missing columns: {missing}")
            conn.close()
            return False

        conn.close()
        print("\n" + "=" * 70)
        print("[SUCCESS] Migration verified successfully!")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False


if __name__ == "__main__":
    success = migrate()
    if not success:
        print("\n[ERROR] Migration failed. Please review errors above.")
        exit(1)
    else:
        print("\nYou can now run the test script:")
        print("  python tests/test_rebalance_phase1_phase2.py")
