#!/usr/bin/env python3
"""
Cleanup Old Cache Entries

Removes cache entries older than 48 hours to prevent database bloat.
This is now done automatically, but you can run this manually to clean up existing old entries.
"""

import sqlite3
import time
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def cleanup_old_cache(retention_hours=48, run_vacuum=False):
    """
    Remove cache entries older than retention_hours.

    Args:
        retention_hours: Number of hours to retain (default: 48)
        run_vacuum: Whether to run VACUUM to reclaim disk space (default: False)
    """
    db_path = getattr(settings, "SQLITE_PATH", "data/lending_rates.db")

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at: {db_path}")
        return

    print(f"[INFO] Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get current stats
        cursor.execute('SELECT COUNT(*), SUM(LENGTH(results_json))/1024.0/1024.0 FROM analysis_cache')
        before_count, before_mb = cursor.fetchone()
        before_mb = before_mb or 0

        cursor.execute('SELECT COUNT(*), SUM(LENGTH(chart_html))/1024.0/1024.0 FROM chart_cache')
        chart_count, chart_mb = cursor.fetchone()
        chart_mb = chart_mb or 0

        print(f'\n=== BEFORE CLEANUP ===')
        print(f'analysis_cache: {before_count} entries, {before_mb:.2f} MB')
        print(f'chart_cache: {chart_count} entries, {chart_mb:.2f} MB')
        print(f'Total cache size: {before_mb + chart_mb:.2f} MB')

        # Calculate cutoff time
        current_time = int(time.time())
        cutoff_time = current_time - (retention_hours * 3600)

        print(f'\nCutoff time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cutoff_time))}')

        # Count entries to be deleted
        cursor.execute(
            'SELECT COUNT(*), SUM(LENGTH(results_json))/1024.0/1024.0 FROM analysis_cache WHERE created_at < ?',
            (cutoff_time,)
        )
        delete_count, delete_mb = cursor.fetchone()
        delete_mb = delete_mb or 0

        print(f'\n=== CLEANUP ===')
        print(f'Entries to delete: {delete_count}')
        print(f'Space to reclaim: {delete_mb:.2f} MB')

        if delete_count == 0:
            print('\n[INFO] No old entries to delete. Cache is within retention period.')
            conn.close()
            return

        # Delete old entries
        cursor.execute('DELETE FROM analysis_cache WHERE created_at < ?', (cutoff_time,))
        deleted_analysis = cursor.rowcount

        cursor.execute('DELETE FROM chart_cache WHERE created_at < ?', (cutoff_time,))
        deleted_charts = cursor.rowcount

        conn.commit()

        # Verify
        cursor.execute('SELECT COUNT(*), SUM(LENGTH(results_json))/1024.0/1024.0 FROM analysis_cache')
        after_count, after_mb = cursor.fetchone()
        after_mb = after_mb or 0

        print(f'\n=== CLEANUP COMPLETE ===')
        print(f'Deleted {deleted_analysis} analysis entries and {deleted_charts} chart entries')
        print(f'Remaining: {after_count} entries, {after_mb:.2f} MB')
        print(f'Space reclaimed: {delete_mb:.2f} MB')

        # Run VACUUM if requested
        if run_vacuum:
            print('\n[VACUUM] Reclaiming disk space...')
            cursor.execute('VACUUM')
            print('[VACUUM] Complete')

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to cleanup cache: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Cleanup old cache entries to prevent database bloat"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Retention period in hours (default: 48)"
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM after cleanup to reclaim disk space"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("CLEANUP OLD CACHE ENTRIES")
    print("=" * 70)
    print()
    print(f"This will delete cache entries older than {args.hours} hours.")
    print("Note: Cache cleanup is now automatic for new entries.")
    print()

    cleanup_old_cache(retention_hours=args.hours, run_vacuum=args.vacuum)
