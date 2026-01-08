# migration/sqlite_to_supabase.py
"""
Migrate SQLite database to Supabase PostgreSQL using pandas.
Simple, clean, no shell commands.

Usage:
    export SUPABASE_URL="postgresql://postgres.xxx:[password]@host:5432/postgres"
    python migration/sqlite_to_supabase.py
"""

import pandas as pd
import sqlite3
from sqlalchemy import create_engine
import os

# ============================================================================
# CONFIGURATION - Update these variables
# ============================================================================

# SQLite (source)
SQLITE_DB_PATH = 'data/lending_rates.db'
SQLITE_TABLE_NAME = 'rates_snapshot'

# Supabase PostgreSQL (destination)
SUPABASE_URL = os.getenv('SUPABASE_URL')  # Get from environment
# Or hardcode for testing (NOT recommended for production):
# SUPABASE_URL = "postgresql://postgres.xxx:[password]@host:5432/postgres"

# PostgreSQL table name (usually same as SQLite)
PG_TABLE_NAME = 'rates_snapshot'

# Migration options
BATCH_SIZE = 1000  # Rows per batch (for progress tracking)
IF_EXISTS = 'append'  # 'append' | 'replace' | 'fail'


# ============================================================================
# MIGRATION FUNCTION
# ============================================================================

def migrate():
    """Migrate all data from SQLite to Supabase PostgreSQL"""
    
    print("🚀 Starting migration: SQLite → Supabase")
    print("="*60)
    
    # Validate configuration
    if not SUPABASE_URL:
        print("❌ Error: SUPABASE_URL not set")
        print("   Set environment variable:")
        print("   export SUPABASE_URL='postgresql://...'")
        return False
    
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ Error: SQLite database not found: {SQLITE_DB_PATH}")
        return False
    
    print(f"📂 Source: {SQLITE_DB_PATH}")
    print(f"🌐 Destination: {SUPABASE_URL[:40]}...")
    print()
    
    try:
        # Step 1: Read from SQLite
        print(f"📖 Reading data from SQLite table: {SQLITE_TABLE_NAME}")
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        df = pd.read_sql(f'SELECT * FROM {SQLITE_TABLE_NAME}', sqlite_conn)
        sqlite_conn.close()
        
        total_rows = len(df)
        print(f"   ✅ Loaded {total_rows:,} rows")
        
        if total_rows == 0:
            print("⚠️  No data to migrate")
            return True
        
        # Step 2: Convert data types (if needed)
        print("\n🔧 Converting data types...")
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            print("   ✅ Converted timestamp to datetime")
        
        # Step 3: Connect to Supabase
        print("\n🌐 Connecting to Supabase...")
        pg_engine = create_engine(SUPABASE_URL)
        print("   ✅ Connected!")
        
        # Step 4: Write to PostgreSQL
        print(f"\n📝 Writing to PostgreSQL table: {PG_TABLE_NAME}")
        print(f"   Mode: {IF_EXISTS}")
        
        df.to_sql(
            name=PG_TABLE_NAME,
            con=pg_engine,
            if_exists=IF_EXISTS,
            index=False,
            chunksize=BATCH_SIZE
        )
        
        print(f"   ✅ Wrote {total_rows:,} rows")
        
        # Step 5: Verify
        print("\n✅ Verifying migration...")
        verify_query = f'SELECT COUNT(*) as count FROM {PG_TABLE_NAME}'
        result = pd.read_sql(verify_query, pg_engine)
        pg_count = result['count'].iloc[0]
        
        print(f"   SQLite rows:   {total_rows:,}")
        print(f"   Supabase rows: {pg_count:,}")
        
        if pg_count >= total_rows:
            print("   ✅ Migration successful!")
        else:
            print(f"   ⚠️  Warning: Row count mismatch")
        
        # Cleanup
        pg_engine.dispose()
        
        print("\n" + "="*60)
        print("🎉 Migration complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def test_connection():
    """Test Supabase connection without migrating"""
    print("🔍 Testing Supabase connection...")
    
    if not SUPABASE_URL:
        print("❌ SUPABASE_URL not set")
        return False
    
    try:
        engine = create_engine(SUPABASE_URL)
        with engine.connect() as conn:
            result = pd.read_sql('SELECT 1 as test', conn)
            print("✅ Connection successful!")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def preview_data(limit=5):
    """Preview SQLite data before migrating"""
    print(f"👀 Previewing first {limit} rows from SQLite...")
    
    try:
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        df = pd.read_sql(f'SELECT * FROM {SQLITE_TABLE_NAME} LIMIT {limit}', sqlite_conn)
        sqlite_conn.close()
        
        print(df)
        print(f"\nTotal columns: {len(df.columns)}")
        print(f"Data types:\n{df.dtypes}")
        
    except Exception as e:
        print(f"❌ Preview failed: {e}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import sys
    
    # Simple CLI
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'test':
            test_connection()
        elif command == 'preview':
            preview_data()
        else:
            print(f"Unknown command: {command}")
            print("Usage: python sqlite_to_supabase.py [test|preview]")
    else:
        # Default: run migration
        migrate()