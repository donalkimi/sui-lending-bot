#!/usr/bin/env python3
"""
Database cleanup script to remove bad/incomplete data snapshots.

This script identifies and removes timestamps with incomplete protocol data
(e.g., missing AlphaFi/Suilend during Sui chain downtime).

Usage:
    python Scripts/cleanup_bad_data.py           # Run cleanup (prompts for confirmation)
    python Scripts/cleanup_bad_data.py --yes     # Run cleanup (skip confirmation)
    python Scripts/cleanup_bad_data.py --dry-run # Preview only
"""

import sqlite3
import shutil
import csv
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


# Thresholds for identifying bad data
MIN_ROW_COUNT = 20  # Normal snapshots have ~47 rows
MIN_PROTOCOL_COUNT = 2  # Need at least 2 protocols for cross-protocol strategies


def get_db_path():
    """Get database path from settings"""
    return settings.SQLITE_PATH


def create_backup(db_path):
    """
    Create a timestamped backup of the database

    Returns:
        Path to backup file
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path.replace('.db', '')}_backup_{timestamp}.db"

    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created successfully\n")

    return backup_path


def export_bad_rows_to_csv(conn, bad_timestamps, db_path):
    """
    Export bad rows to CSV for review

    Returns:
        Path to CSV file
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_path = f"{db_path.replace('.db', '')}_bad_data_export_{timestamp}.csv"

    print(f"Exporting bad rows to: {csv_path}")

    # Build query with timestamp list
    placeholders = ','.join('?' * len(bad_timestamps))
    query = f"""
        SELECT * FROM rates_snapshot
        WHERE timestamp IN ({placeholders})
        ORDER BY timestamp, protocol, token
    """

    cursor = conn.execute(query, bad_timestamps)
    rows = cursor.fetchall()

    if rows:
        # Get column names
        columns = [description[0] for description in cursor.description]

        # Write to CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)

        print(f"✓ Exported {len(rows)} rows to CSV\n")
    else:
        print("No rows to export\n")

    return csv_path


def analyze_data_quality(conn):
    """
    Analyze data quality and identify bad timestamps

    Returns:
        List of bad timestamps, analysis report dict
    """
    print("=" * 80)
    print("ANALYZING DATA QUALITY")
    print("=" * 80)

    # Get row count and protocol count per timestamp
    query = """
        SELECT
            timestamp,
            COUNT(*) as row_count,
            COUNT(DISTINCT protocol) as protocol_count,
            GROUP_CONCAT(DISTINCT protocol) as protocols
        FROM rates_snapshot
        GROUP BY timestamp
        ORDER BY timestamp
    """

    cursor = conn.execute(query)
    results = cursor.fetchall()

    # Identify bad timestamps
    bad_timestamps = []
    bad_details = []

    for row in results:
        timestamp, row_count, protocol_count, protocols = row

        is_bad = row_count < MIN_ROW_COUNT or protocol_count <= MIN_PROTOCOL_COUNT

        if is_bad:
            bad_timestamps.append(timestamp)
            bad_details.append({
                'timestamp': timestamp,
                'row_count': row_count,
                'protocol_count': protocol_count,
                'protocols': protocols
            })

    # Get overall stats
    total_timestamps = len(results)
    bad_count = len(bad_timestamps)

    # Calculate total rows affected
    if bad_timestamps:
        placeholders = ','.join('?' * len(bad_timestamps))
        query = f"SELECT COUNT(*) FROM rates_snapshot WHERE timestamp IN ({placeholders})"
        cursor = conn.execute(query, bad_timestamps)
        total_bad_rows = cursor.fetchone()[0]
    else:
        total_bad_rows = 0

    # Get current database stats
    cursor = conn.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM rates_snapshot")
    total_rows, min_ts, max_ts = cursor.fetchone()

    # Print report
    print(f"\nCurrent Database State:")
    print(f"  Total rows: {total_rows}")
    print(f"  Timestamps: {total_timestamps} (from {min_ts} to {max_ts})")
    print(f"  Normal row count per timestamp: ~47")
    print(f"  Normal protocol count: 3\n")

    print(f"Bad Data Detected:")
    print(f"  Bad timestamps: {bad_count} out of {total_timestamps} ({bad_count/total_timestamps*100:.1f}%)")
    print(f"  Total bad rows: {total_bad_rows}\n")

    if bad_details:
        print("Bad Timestamp Details:")
        print("-" * 80)
        print(f"{'Timestamp':<30} | {'Rows':<6} | {'Protocols':<10} | {'Protocol List':<20}")
        print("-" * 80)

        for detail in bad_details:
            print(f"{detail['timestamp']:<30} | {detail['row_count']:<6} | "
                  f"{detail['protocol_count']:<10} | {detail['protocols']:<20}")

        print("-" * 80)

        # Calculate time window
        first_bad = bad_details[0]['timestamp']
        last_bad = bad_details[-1]['timestamp']
        print(f"\nTime Window: {first_bad} to {last_bad}")

        try:
            first_dt = datetime.fromisoformat(first_bad.replace(' ', 'T'))
            last_dt = datetime.fromisoformat(last_bad.replace(' ', 'T'))
            duration = last_dt - first_dt
            hours = duration.total_seconds() / 3600
            print(f"Duration: {hours:.2f} hours")
        except:
            pass

    print("\n")

    report = {
        'total_rows': total_rows,
        'total_timestamps': total_timestamps,
        'bad_timestamp_count': bad_count,
        'total_bad_rows': total_bad_rows,
        'min_timestamp': min_ts,
        'max_timestamp': max_ts
    }

    return bad_timestamps, report


def delete_bad_data(conn, bad_timestamps):
    """
    Delete bad data from database

    Returns:
        Number of rows deleted
    """
    if not bad_timestamps:
        print("No bad data to delete")
        return 0

    print("=" * 80)
    print("DELETING BAD DATA")
    print("=" * 80)

    # Delete from rates_snapshot
    placeholders = ','.join('?' * len(bad_timestamps))
    query = f"DELETE FROM rates_snapshot WHERE timestamp IN ({placeholders})"

    cursor = conn.execute(query, bad_timestamps)
    rows_deleted = cursor.rowcount

    print(f"✓ Deleted {rows_deleted} rows from rates_snapshot")

    # Delete from reward_token_prices (if table exists and has matching timestamps)
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reward_token_prices'")
        if cursor.fetchone():
            query = f"DELETE FROM reward_token_prices WHERE timestamp IN ({placeholders})"
            cursor = conn.execute(query, bad_timestamps)
            reward_rows_deleted = cursor.rowcount
            if reward_rows_deleted > 0:
                print(f"✓ Deleted {reward_rows_deleted} rows from reward_token_prices")
    except Exception as e:
        print(f"Note: Could not clean reward_token_prices table: {e}")

    # Commit changes
    conn.commit()
    print("✓ Changes committed")

    # VACUUM to reclaim disk space
    print("Running VACUUM to reclaim disk space...")
    conn.execute("VACUUM")
    print("✓ VACUUM completed\n")

    return rows_deleted


def verify_cleanup(conn, bad_timestamps):
    """Verify cleanup was successful"""
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    # Check if any bad timestamps remain
    placeholders = ','.join('?' * len(bad_timestamps))
    query = f"SELECT COUNT(*) FROM rates_snapshot WHERE timestamp IN ({placeholders})"
    cursor = conn.execute(query, bad_timestamps)
    remaining = cursor.fetchone()[0]

    if remaining > 0:
        print(f"⚠️  WARNING: {remaining} rows still exist with bad timestamps!")
        return False
    else:
        print("✓ All bad timestamps successfully deleted")

    # Check for any remaining bad data
    query = f"""
        SELECT COUNT(*) FROM (
            SELECT timestamp
            FROM rates_snapshot
            GROUP BY timestamp
            HAVING COUNT(*) < {MIN_ROW_COUNT} OR COUNT(DISTINCT protocol) <= {MIN_PROTOCOL_COUNT}
        )
    """
    cursor = conn.execute(query)
    remaining_bad = cursor.fetchone()[0]

    if remaining_bad > 0:
        print(f"⚠️  WARNING: {remaining_bad} timestamps still have bad data!")
        return False
    else:
        print("✓ No bad timestamps remain")

    # Get final stats
    cursor = conn.execute("SELECT COUNT(*), COUNT(DISTINCT timestamp), MIN(timestamp), MAX(timestamp) FROM rates_snapshot")
    total_rows, total_ts, min_ts, max_ts = cursor.fetchone()

    print(f"\nFinal Database State:")
    print(f"  Total rows: {total_rows}")
    print(f"  Timestamps: {total_ts}")
    print(f"  Date range: {min_ts} to {max_ts}")

    # Calculate average rows per timestamp
    avg_rows = total_rows / total_ts if total_ts > 0 else 0
    print(f"  Average rows per timestamp: {avg_rows:.1f}")

    print("\n")

    return True


def main():
    """Main cleanup workflow"""
    # Parse arguments
    dry_run = '--dry-run' in sys.argv
    skip_confirmation = '--yes' in sys.argv or '-y' in sys.argv

    if dry_run:
        print("=" * 80)
        print("DRY RUN MODE - NO CHANGES WILL BE MADE")
        print("=" * 80)
        print()

    # Get database path
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"❌ Error: Database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}")
    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f"Database size: {db_size_mb:.2f} MB\n")

    # Connect to database
    conn = sqlite3.connect(db_path)

    try:
        # Phase 1: Analyze data quality
        bad_timestamps, report = analyze_data_quality(conn)

        if not bad_timestamps:
            print("✓ No bad data found! Database is clean.")
            return

        # Phase 2: Create backup (unless dry run)
        if not dry_run:
            backup_path = create_backup(db_path)
            csv_path = export_bad_rows_to_csv(conn, bad_timestamps, db_path)
        else:
            print("Skipping backup and CSV export (dry run mode)\n")

        # Phase 3: Confirm deletion
        if not dry_run:
            print("=" * 80)
            print("DELETION SUMMARY")
            print("=" * 80)
            print(f"Timestamps to delete: {len(bad_timestamps)}")
            print(f"Total rows to delete: {report['total_bad_rows']}")
            print(f"Rows remaining: {report['total_rows'] - report['total_bad_rows']}")
            print(f"Timestamps remaining: {report['total_timestamps'] - len(bad_timestamps)}")
            print()

            # Require confirmation (unless --yes flag is provided)
            if skip_confirmation:
                print("Proceeding with deletion (--yes flag provided)...\n")
            else:
                try:
                    response = input("Proceed with deletion? (yes/no): ").strip().lower()
                    if response != 'yes':
                        print("\n❌ Cleanup cancelled by user")
                        print(f"Backup saved at: {backup_path}")
                        return
                except EOFError:
                    print("\n❌ Unable to read user input. Use --yes flag to skip confirmation.")
                    print(f"Backup saved at: {backup_path}")
                    return

            print()

        # Phase 4: Delete bad data (unless dry run)
        if not dry_run:
            rows_deleted = delete_bad_data(conn, bad_timestamps)

            # Phase 5: Verify
            success = verify_cleanup(conn, bad_timestamps)

            if success:
                print("=" * 80)
                print("✓ CLEANUP COMPLETED SUCCESSFULLY")
                print("=" * 80)
                print(f"Deleted: {rows_deleted} rows from {len(bad_timestamps)} timestamps")
                print(f"Backup: {backup_path}")
                print(f"Export: {csv_path}")

                # Get final size
                conn.close()
                final_size_mb = os.path.getsize(db_path) / (1024 * 1024)
                print(f"Database size: {db_size_mb:.2f} MB → {final_size_mb:.2f} MB")

                print("\n💡 Tip: Run verification queries from the plan to double-check")
                print("💡 To restore: cp {} {}".format(backup_path, db_path))
            else:
                print("❌ Verification failed! Check warnings above")
                print(f"Backup available at: {backup_path}")
        else:
            print("=" * 80)
            print("DRY RUN COMPLETE - NO CHANGES MADE")
            print("=" * 80)
            print(f"Would delete: {report['total_bad_rows']} rows from {len(bad_timestamps)} timestamps")
            print("\nRun without --dry-run to perform actual cleanup")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
