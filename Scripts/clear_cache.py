#!/usr/bin/env python3
"""
Clear Analysis Cache

Deletes all cached strategies from the database. Use this when the calculation
formula has changed (e.g., switching from maxCF to LLTV-based calculations).

After running this, run refresh_pipeline.py to regenerate fresh strategies.
"""

import sqlite3
from pathlib import Path
from config import settings


def clear_cache():
    """Clear analysis_cache and chart_cache tables"""

    # Get database path from settings
    db_path = getattr(settings, "SQLITE_PATH", "data/lending_rates.db")

    if not Path(db_path).exists():
        print(f"[ERROR] Database not found at: {db_path}")
        return

    print(f"[INFO] Connecting to database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Count existing rows before deletion
        cursor.execute("SELECT COUNT(*) FROM analysis_cache")
        analysis_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM chart_cache")
        chart_count = cursor.fetchone()[0]

        print(f"[INFO] Found {analysis_count} cached strategies")
        print(f"[INFO] Found {chart_count} cached charts")

        if analysis_count == 0 and chart_count == 0:
            print("[INFO] Cache is already empty")
            return

        # Delete all rows from both cache tables
        print("[DELETE] Clearing analysis_cache...")
        cursor.execute("DELETE FROM analysis_cache")

        print("[DELETE] Clearing chart_cache...")
        cursor.execute("DELETE FROM chart_cache")

        # Commit changes
        conn.commit()

        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM analysis_cache")
        remaining_analysis = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM chart_cache")
        remaining_charts = cursor.fetchone()[0]

        print(f"\n[SUCCESS] Cache cleared!")
        print(f"  - Deleted {analysis_count} cached strategies")
        print(f"  - Deleted {chart_count} cached charts")
        print(f"  - Remaining: {remaining_analysis} strategies, {remaining_charts} charts")

        print("\n[NEXT STEPS]")
        print("  1. Run: python -m data.refresh_pipeline")
        print("  2. This will regenerate strategies with the new LLTV-based formula")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to clear cache: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 70)
    print("CLEAR ANALYSIS CACHE")
    print("=" * 70)
    print()
    print("This will delete all cached strategies from the database.")
    print("These were calculated with the old maxCF-based formula and are now")
    print("inconsistent after switching to LLTV-based calculations.")
    print()

    # Ask for confirmation
    response = input("Continue? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        print()
        clear_cache()
    else:
        print("[CANCELLED] No changes made")
