#!/usr/bin/env python3
"""
Fix analysis_cache table schema in Supabase.

This script recreates the analysis_cache table with the correct column names
to match what the code expects (timestamp_seconds).

Usage:
    python Scripts/fix_analysis_cache.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
import psycopg2


def fix_analysis_cache():
    """Recreate analysis_cache table with correct schema."""

    if not settings.USE_CLOUD_DB:
        print("ERROR: This script is only for cloud database (USE_CLOUD_DB=True)")
        print("Current setting: USE_CLOUD_DB=False")
        return 1

    if not settings.SUPABASE_URL:
        print("ERROR: SUPABASE_URL environment variable not set")
        return 1

    print(f"Connecting to Supabase...")
    print(f"Database: {settings.SUPABASE_URL.split('@')[1] if '@' in settings.SUPABASE_URL else 'hidden'}")

    try:
        conn = psycopg2.connect(settings.SUPABASE_URL)
        cursor = conn.cursor()

        print("\n1. Dropping existing analysis_cache table (if exists)...")
        cursor.execute("DROP TABLE IF EXISTS analysis_cache CASCADE")
        print("   ✓ Dropped")

        print("\n2. Creating analysis_cache table with correct schema...")
        cursor.execute("""
            CREATE TABLE analysis_cache (
                timestamp_seconds INTEGER NOT NULL,
                liquidation_distance DECIMAL(5, 4) NOT NULL,
                results_json TEXT NOT NULL,
                strategy_count INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (timestamp_seconds, liquidation_distance)
            )
        """)
        print("   ✓ Created")

        print("\n3. Creating indexes...")
        cursor.execute("""
            CREATE INDEX idx_analysis_cache_timestamp
            ON analysis_cache(timestamp_seconds, liquidation_distance)
        """)
        cursor.execute("""
            CREATE INDEX idx_analysis_cache_created
            ON analysis_cache(created_at)
        """)
        print("   ✓ Indexes created")

        print("\n4. Enabling Row Level Security...")
        cursor.execute("ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY")
        print("   ✓ RLS enabled")

        print("\n5. Creating policies...")
        cursor.execute("""
            CREATE POLICY "Service role has full access to analysis_cache"
            ON analysis_cache
            FOR ALL
            TO service_role
            USING (true)
            WITH CHECK (true)
        """)
        cursor.execute("""
            CREATE POLICY "Authenticated users can read analysis_cache"
            ON analysis_cache
            FOR SELECT
            TO authenticated
            USING (true)
        """)
        print("   ✓ Policies created")

        conn.commit()
        print("\n✓ SUCCESS: analysis_cache table recreated with correct schema")
        print("\nNote: Cache is empty - will be repopulated on next analysis run")

        cursor.close()
        conn.close()
        return 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(fix_analysis_cache())
