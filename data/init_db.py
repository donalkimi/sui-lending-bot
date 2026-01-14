"""
Database Initialization Script

Creates SQLite or PostgreSQL database with schema.

Usage:
    python data/init_db.py              # Initialize SQLite (default)
    python data/init_db.py --cloud      # Initialize Supabase PostgreSQL
"""

import os
import sqlite3
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def init_sqlite(db_path='data/lending_rates.db'):
    """Initialize SQLite database with schema"""
    
    # Ensure data directory exists
    Path(db_path).parent.mkdir(exist_ok=True)
    
    # Read schema
    schema_path = Path(__file__).parent / 'schema.sql'
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Create database
    print(f"📂 Creating SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Execute schema
    conn.executescript(schema_sql)
    conn.commit()
    
    # Verify tables created
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"✅ Created tables: {', '.join(tables)}")
    
    # Verify views created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
    views = [row[0] for row in cursor.fetchall()]
    
    print(f"✅ Created views: {', '.join(views)}")
    
    conn.close()
    print(f"✅ Database initialized: {db_path}\n")


def init_postgres(connection_url):
    """Initialize PostgreSQL database with schema"""

    if psycopg2 is None:
        print("❌ Error: psycopg2 not installed")
        print("   Install with: pip install psycopg2-binary")
        return

    if not connection_url:
        print("❌ Error: SUPABASE_URL not set")
        print("   Set environment variable:")
        print("   export SUPABASE_URL='postgresql://...'")
        return

    # Read schema
    schema_path = Path(__file__).parent / 'schema.sql'
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    # Create database
    print(f"🌐 Connecting to PostgreSQL...")
    conn = psycopg2.connect(connection_url)
    cursor = conn.cursor()
    
    # Execute schema
    cursor.execute(schema_sql)
    conn.commit()
    
    # Verify tables created
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"✅ Created tables: {', '.join(tables)}")
    
    # Verify views created
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
          AND table_type = 'VIEW'
    """)
    views = [row[0] for row in cursor.fetchall()]
    
    print(f"✅ Created views: {', '.join(views)}")
    
    conn.close()
    print(f"✅ Database initialized: Supabase PostgreSQL\n")


def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--cloud':
        # Initialize cloud PostgreSQL
        connection_url = os.getenv('SUPABASE_URL')
        init_postgres(connection_url)
    else:
        # Initialize local SQLite (default)
        init_sqlite()


if __name__ == '__main__':
    main()