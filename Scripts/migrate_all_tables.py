"""
Complete SQLite to Supabase migration script

Migrates all core tables from SQLite to Supabase (PostgreSQL).
Skips cache tables (analysis_cache, chart_cache) as they regenerate automatically.

Usage:
    python Scripts/migrate_all_tables.py
"""

import pandas as pd
import sqlite3
import psycopg2
from sqlalchemy import create_engine
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SQLITE_PATH = 'data/lending_rates.db'
SUPABASE_URL = os.getenv('SUPABASE_URL')

# Tables to migrate (skip cache tables per user preference)
TABLES_TO_MIGRATE = [
    'rates_snapshot',      # ~28,335 rows - historical rate data
    'token_registry',      # ~60 rows - token metadata
    'positions',           # ~3 rows - position tracking
    'position_rebalances', # Event history
    'position_snapshots',  # Position snapshots (if exists)
    'reward_token_prices', # Reward token prices
]

def migrate_table(table_name, sqlite_conn, pg_engine, batch_size=1000):
    """Migrate a single table from SQLite to PostgreSQL"""
    print(f"\n{'='*60}")
    print(f"Migrating: {table_name}")
    print('='*60)

    try:
        # Read from SQLite
        df = pd.read_sql(f'SELECT * FROM {table_name}', sqlite_conn)
        row_count = len(df)
        print(f"  Source rows: {row_count:,}")

        if row_count == 0:
            print("  [WARN]Table is empty, skipping")
            return True

        # Convert column names to lowercase (PostgreSQL requirement)
        df.columns = [col.lower() for col in df.columns]

        # Get target table columns from PostgreSQL
        import sqlalchemy
        inspector = sqlalchemy.inspect(pg_engine)
        target_columns = [col['name'] for col in inspector.get_columns(table_name)]

        # Only keep columns that exist in target table
        cols_to_migrate = [col for col in df.columns if col in target_columns]
        missing_cols = [col for col in df.columns if col not in target_columns]

        if missing_cols:
            print(f"  [INFO] Skipping columns not in schema: {', '.join(missing_cols[:5])}")

        df = df[cols_to_migrate]

        # Convert timestamp columns to datetime
        for col in df.columns:
            if 'timestamp' in col.lower():
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Convert boolean columns based on schema
        # is_paper_trade is BOOLEAN in schema
        if 'is_paper_trade' in df.columns:
            df['is_paper_trade'] = df['is_paper_trade'].astype(bool)
        # seen_* columns are INTEGER in schema (keep as is)

        # Write to PostgreSQL with conflict handling
        # For tables with primary keys, skip duplicates
        if table_name in ['rates_snapshot', 'token_registry']:
            # Use raw SQL with ON CONFLICT for these tables
            from sqlalchemy import text
            with pg_engine.begin() as conn:
                for _, row in df.iterrows():
                    placeholders = ', '.join([f':{col}' for col in df.columns])
                    columns = ', '.join([f'"{col}"' if col in ['timestamp'] else col for col in df.columns])
                    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                    conn.execute(text(sql), row.to_dict())
        else:
            # Regular insert for tables without conflicts
            df.to_sql(
                name=table_name,
                con=pg_engine,
                if_exists='append',
                index=False,
                chunksize=batch_size
            )

        # Verify
        verify_df = pd.read_sql(f'SELECT COUNT(*) as count FROM {table_name}', pg_engine)
        pg_count = verify_df['count'].iloc[0]
        print(f"  Destination rows: {pg_count:,}")

        if pg_count >= row_count:
            print(f"  [OK] Success!")
            return True
        else:
            print(f"  [FAIL] Row count mismatch!")
            return False

    except Exception as e:
        if "no such table" in str(e).lower():
            print(f"  [WARN]Table doesn't exist in SQLite, skipping")
            return True
        raise

def main():
    print("="*60)
    print("SQLite to Supabase Migration")
    print("="*60)
    print(f"Start time: {datetime.now()}")
    print()

    # Validate environment
    if not SUPABASE_URL:
        print("[ERROR] SUPABASE_URL environment variable not set")
        print("   Make sure your .env file contains SUPABASE_URL")
        return

    if not os.path.exists(SQLITE_PATH):
        print(f"[ERROR] SQLite database not found at {SQLITE_PATH}")
        return

    print(f"Source: {SQLITE_PATH}")
    print(f"Destination: Supabase PostgreSQL")
    print()

    # Connect to both databases
    print("Connecting to databases...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_engine = create_engine(SUPABASE_URL)
    print("[OK] Connected")
    print()

    # Migrate each table
    results = {}
    for table in TABLES_TO_MIGRATE:
        try:
            success = migrate_table(table, sqlite_conn, pg_engine)
            results[table] = '[OK] SUCCESS' if success else '[FAIL] FAILED'
        except Exception as e:
            print(f"  [ERROR] {e}")
            results[table] = f'[FAIL] ERROR: {str(e)[:50]}'

    # Summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    for table, status in results.items():
        print(f"{table:25} {status}")

    # Cleanup
    sqlite_conn.close()
    pg_engine.dispose()

    print()
    print(f"End time: {datetime.now()}")
    print("="*60)

    # Check if all succeeded
    all_success = all('SUCCESS' in status for status in results.values())
    if all_success:
        print("\n[SUCCESS] Migration completed successfully!")
        print("\nNext steps:")
        print("1. Verify data in Supabase UI (Table Editor)")
        print("2. Update config/settings.py: USE_CLOUD_DB = True")
        print("3. Test the application with Supabase")
    else:
        print("\n[WARN] Some tables had issues - check the summary above")

if __name__ == '__main__':
    main()
