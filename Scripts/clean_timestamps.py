#!/usr/bin/env python3
"""
Database Timestamp Cleanup Script

This script normalizes all timestamps in the rates_snapshot table to minute precision
by truncating seconds and microseconds to 0. This matches the system's design where
refresh_pipeline.py enforces minute-level precision with .replace(second=0, microsecond=0).

Usage:
    python scripts/clean_timestamps.py --preview   # Show what would change
    python scripts/clean_timestamps.py --apply     # Actually update the database

Safety features:
- Creates backup before making changes (SQLite only)
- Shows preview of affected rows
- Requires explicit confirmation before updating
- Works with both SQLite and PostgreSQL/Supabase
"""

import sys
import os
from datetime import datetime
from pathlib import Path
import shutil

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def create_backup(db_path: str) -> str:
    """
    Create a timestamped backup of the SQLite database file.

    Args:
        db_path: Path to the database file

    Returns:
        Path to the backup file
    """
    backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{backup_timestamp}"

    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created successfully")

    return backup_path


def preview_sqlite_changes(conn):
    """Show what would be changed in SQLite database"""
    cursor = conn.cursor()

    # Find affected rows - show distinct examples
    query = """
    SELECT DISTINCT
        timestamp,
        strftime('%Y-%m-%d %H:%M:00', timestamp) as rounded_timestamp
    FROM rates_snapshot
    WHERE strftime('%S', timestamp) != '00'
       OR length(timestamp) > 19
    ORDER BY timestamp DESC
    LIMIT 20
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("\n✓ No timestamps need cleaning! All timestamps are already at minute precision.")
        return 0

    print("\n" + "="*80)
    print("PREVIEW: Timestamps that will be changed (showing first 20)")
    print("="*80)
    print(f"{'Original Timestamp':<35} → {'Cleaned Timestamp':<30}")
    print("-"*80)

    for original, cleaned in rows:
        cleaned_str = cleaned if cleaned is not None else "ERROR"
        # Show full original timestamp to display microseconds
        print(f"{str(original):<35} → {cleaned_str:<30}")

    # Count total affected rows
    count_query = """
    SELECT COUNT(*) FROM rates_snapshot
    WHERE strftime('%S', timestamp) != '00'
       OR length(timestamp) > 19
    """
    cursor.execute(count_query)
    total_count = cursor.fetchone()[0]

    # Check for duplicates within the same minute
    duplicate_query = """
    SELECT COUNT(*) - COUNT(DISTINCT strftime('%Y-%m-%d %H:%M', timestamp) || '|' || protocol || '|' || token_contract)
    FROM rates_snapshot
    WHERE strftime('%S', timestamp) != '00'
       OR length(timestamp) > 19
    """
    cursor.execute(duplicate_query)
    duplicate_count = cursor.fetchone()[0]

    print("-"*80)
    print(f"Total rows with seconds/microseconds: {total_count}")
    if duplicate_count > 0:
        print(f"Duplicate records to remove: {duplicate_count}")
        print(f"  (Multiple snapshots within same minute - will keep latest)")
    print("="*80 + "\n")

    return total_count


def preview_postgres_changes(conn):
    """Show what would be changed in PostgreSQL database"""
    cursor = conn.cursor()

    # Find affected rows
    query = """
    SELECT
        timestamp,
        date_trunc('minute', timestamp) as rounded_timestamp
    FROM rates_snapshot
    WHERE EXTRACT(SECOND FROM timestamp) != 0
    ORDER BY timestamp DESC
    LIMIT 20
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("\n✓ No timestamps need cleaning! All timestamps are already at minute precision.")
        return 0

    print("\n" + "="*80)
    print("PREVIEW: Timestamps that will be changed (showing first 20)")
    print("="*80)
    print(f"{'Original Timestamp':<30} → {'Cleaned Timestamp':<30}")
    print("-"*80)

    for original, cleaned in rows:
        print(f"{str(original):<30} → {str(cleaned):<30}")

    # Count total affected rows
    count_query = """
    SELECT COUNT(*) FROM rates_snapshot
    WHERE EXTRACT(SECOND FROM timestamp) != 0
    """
    cursor.execute(count_query)
    total_count = cursor.fetchone()[0]

    print("-"*80)
    print(f"Total rows to update: {total_count}")
    print("="*80 + "\n")

    return total_count


def apply_sqlite_cleanup(conn):
    """Apply timestamp cleanup to SQLite database"""
    cursor = conn.cursor()

    print("Applying changes to database...")
    print("Step 1: Identifying records to keep (latest within each minute)...")

    # Strategy: Keep the LATEST record within each (minute, protocol, token_contract) group
    # Delete all others, then update the remaining ones to remove microseconds

    # First, delete duplicates - keep only the MAX timestamp within each minute
    delete_query = """
    DELETE FROM rates_snapshot
    WHERE rowid NOT IN (
        SELECT MAX(rowid)
        FROM rates_snapshot
        GROUP BY
            strftime('%Y-%m-%d %H:%M', timestamp),
            protocol,
            token_contract
    )
    """

    cursor.execute(delete_query)
    deleted_count = cursor.rowcount
    print(f"  ✓ Deleted {deleted_count} duplicate records (kept latest within each minute)")

    # Now update the remaining timestamps to clean format
    print("\nStep 2: Cleaning timestamps to minute precision...")
    update_query = """
    UPDATE rates_snapshot
    SET timestamp = strftime('%Y-%m-%d %H:%M:00', timestamp)
    WHERE strftime('%S', timestamp) != '00'
       OR length(timestamp) > 19
    """

    cursor.execute(update_query)
    rows_updated = cursor.rowcount
    conn.commit()

    print(f"  ✓ Updated {rows_updated} timestamps to minute precision")
    print(f"\nTotal changes: Deleted {deleted_count} duplicates, Updated {rows_updated} timestamps")

    # Verify
    verify_query = """
    SELECT COUNT(*) FROM rates_snapshot
    WHERE strftime('%S', timestamp) != '00'
       OR length(timestamp) > 19
    """
    cursor.execute(verify_query)
    remaining = cursor.fetchone()[0]

    if remaining == 0:
        print("✓ Verification passed: All timestamps now have minute precision")
    else:
        print(f"⚠ Warning: {remaining} timestamps still have seconds/microseconds")

    return rows_updated


def apply_postgres_cleanup(conn):
    """Apply timestamp cleanup to PostgreSQL database"""
    cursor = conn.cursor()

    # Update timestamps
    update_query = """
    UPDATE rates_snapshot
    SET timestamp = date_trunc('minute', timestamp)
    WHERE EXTRACT(SECOND FROM timestamp) != 0
    """

    print("Applying changes to database...")
    cursor.execute(update_query)
    rows_updated = cursor.rowcount
    conn.commit()

    print(f"✓ Successfully updated {rows_updated} rows")

    # Verify
    verify_query = """
    SELECT COUNT(*) FROM rates_snapshot
    WHERE EXTRACT(SECOND FROM timestamp) != 0
    """
    cursor.execute(verify_query)
    remaining = cursor.fetchone()[0]

    if remaining == 0:
        print("✓ Verification passed: All timestamps now have minute precision")
    else:
        print(f"⚠ Warning: {remaining} timestamps still have seconds/microseconds")

    return rows_updated


def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean database timestamps to minute precision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes without modifying database
  python scripts/clean_timestamps.py --preview

  # Apply changes to database (creates backup for SQLite)
  python scripts/clean_timestamps.py --apply
        """
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Show what would be changed without modifying the database'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply the changes to the database'
    )

    args = parser.parse_args()

    if not args.preview and not args.apply:
        parser.print_help()
        sys.exit(1)

    # Connect to database
    print("\n" + "="*80)
    print("DATABASE TIMESTAMP CLEANUP")
    print("="*80)

    if settings.USE_CLOUD_DB:
        print(f"Database: PostgreSQL/Supabase")
        print(f"Connection: {settings.SUPABASE_URL[:50]}...")

        import psycopg2
        conn = psycopg2.connect(settings.SUPABASE_URL)
        is_sqlite = False
    else:
        print(f"Database: SQLite")
        print(f"Path: {settings.SQLITE_PATH}")

        import sqlite3
        conn = sqlite3.connect(settings.SQLITE_PATH)
        is_sqlite = True

    print("="*80 + "\n")

    try:
        # Preview mode
        if args.preview:
            print("MODE: Preview (no changes will be made)")
            print("-"*80 + "\n")

            if is_sqlite:
                count = preview_sqlite_changes(conn)
            else:
                count = preview_postgres_changes(conn)

            if count > 0:
                print("\nTo apply these changes, run:")
                print("  python scripts/clean_timestamps.py --apply")

            return

        # Apply mode
        if args.apply:
            print("MODE: Apply (will modify database)")
            print("-"*80 + "\n")

            # Show preview first
            if is_sqlite:
                count = preview_sqlite_changes(conn)
            else:
                count = preview_postgres_changes(conn)

            if count == 0:
                print("\nNothing to do!")
                return

            # Create backup for SQLite
            backup_path = None
            if is_sqlite:
                backup_path = create_backup(settings.SQLITE_PATH)
                print(f"\n✓ Backup created at: {backup_path}")
                print("  (You can restore with: cp {backup_path} {settings.SQLITE_PATH})\n")

            # Confirmation
            print("\n" + "!"*80)
            print("WARNING: This will modify the database!")
            if is_sqlite and backup_path:
                print(f"A backup has been created at: {backup_path}")
            else:
                print("PostgreSQL database - make sure you have a backup!")
            print("\nWhat will happen:")
            print("  1. Delete duplicate snapshots within the same minute (keeps latest)")
            print("  2. Truncate remaining timestamps to minute precision (remove seconds/microseconds)")
            print("!"*80 + "\n")

            response = input(f"Are you sure you want to proceed? (yes/no): ")

            if response.lower() != 'yes':
                print("\nCancelled. No changes were made.")
                return

            print()

            # Apply changes
            if is_sqlite:
                rows_updated = apply_sqlite_cleanup(conn)
            else:
                rows_updated = apply_postgres_cleanup(conn)

            print("\n" + "="*80)
            print(f"✓ Cleanup completed successfully!")
            print(f"  Rows updated: {rows_updated}")
            if backup_path:
                print(f"  Backup location: {backup_path}")
            print("="*80 + "\n")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
