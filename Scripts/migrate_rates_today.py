#!/usr/bin/env python3
"""
Database Migration Script: Rates Snapshots (Today)

Migrates today's rates snapshots from lending_rates_partial.db to lending_rates.db
with backup and rollback capability.

Usage:
    python migrate_rates_today.py [--dry-run] [--date YYYY-MM-DD]
"""

import sqlite3
import shutil
import sys
import os
from datetime import datetime
from pathlib import Path

# Color codes for terminal output
class Color:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Color.BOLD}{Color.CYAN}{'='*60}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{text}{Color.END}")
    print(f"{Color.BOLD}{Color.CYAN}{'='*60}{Color.END}\n")

def print_success(text):
    print(f"{Color.GREEN}[OK] {text}{Color.END}")

def print_warning(text):
    print(f"{Color.YELLOW}[!] {text}{Color.END}")

def print_error(text):
    print(f"{Color.RED}[X] {text}{Color.END}")

def print_info(text):
    print(f"{Color.BLUE}[i] {text}{Color.END}")

class DatabaseMigration:
    def __init__(self, source_db, target_db, migration_date, dry_run=False):
        self.source_db = Path(source_db)
        self.target_db = Path(target_db)
        self.migration_date = migration_date
        self.dry_run = dry_run
        self.backup_path = None
        self.rollback_script_path = None
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure backups directory exists
        self.backups_dir = Path("data/backups")
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def validate_databases(self):
        """Phase 1: Pre-Migration Validation"""
        print_header("Phase 1: Pre-Migration Validation")

        # Check source database exists
        if not self.source_db.exists():
            print_error(f"Source database not found: {self.source_db}")
            return False
        print_success(f"Source database found: {self.source_db}")

        # Check target database exists
        if not self.target_db.exists():
            print_error(f"Target database not found: {self.target_db}")
            return False
        print_success(f"Target database found: {self.target_db}")

        try:
            # Query source database for records (read-only to avoid locks)
            source_uri = f"file:{self.source_db.absolute().as_posix()}?mode=ro"
            conn_source = sqlite3.connect(source_uri, uri=True)
            cursor = conn_source.cursor()

            cursor.execute("""
                SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                FROM rates_snapshot
                WHERE date(timestamp) = ?
            """, (self.migration_date,))

            source_count, min_ts, max_ts = cursor.fetchone()
            conn_source.close()

            if source_count == 0:
                print_warning(f"No records found in source DB for date: {self.migration_date}")
                return False

            print_success(f"Found {source_count} records in source DB for {self.migration_date}")
            print_info(f"  Timestamp range: {min_ts} to {max_ts}")

            # Query target database current state
            conn_target = sqlite3.connect(self.target_db)
            cursor = conn_target.cursor()

            cursor.execute("SELECT COUNT(*) FROM rates_snapshot")
            total_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM rates_snapshot
                WHERE date(timestamp) = ?
            """, (self.migration_date,))

            existing_count = cursor.fetchone()[0]
            conn_target.close()

            print_success(f"Target DB currently has {total_count} total records")
            if existing_count > 0:
                print_warning(f"Target DB already has {existing_count} records for {self.migration_date}")
                print_info("  These will be preserved (INSERT OR IGNORE strategy)")
            else:
                print_info(f"No existing records for {self.migration_date} in target DB")

            return True

        except sqlite3.Error as e:
            print_error(f"Database validation failed: {e}")
            return False

    def create_backup(self):
        """Phase 2: Backup Creation"""
        print_header("Phase 2: Backup Creation")

        if self.dry_run:
            print_info("Dry-run mode: Skipping backup creation")
            return True

        try:
            # Create timestamped backup
            backup_filename = f"lending_rates.db.backup_{self.timestamp}"
            self.backup_path = self.backups_dir / backup_filename

            print_info(f"Creating backup: {self.backup_path}")
            shutil.copy2(self.target_db, self.backup_path)

            # Verify backup integrity
            original_size = os.path.getsize(self.target_db)
            backup_size = os.path.getsize(self.backup_path)

            if original_size != backup_size:
                print_error(f"Backup verification failed: Size mismatch")
                print_error(f"  Original: {original_size} bytes")
                print_error(f"  Backup: {backup_size} bytes")
                return False

            print_success(f"Backup created successfully ({backup_size:,} bytes)")
            return True

        except Exception as e:
            print_error(f"Backup creation failed: {e}")
            return False

    def execute_migration(self):
        """Phase 3: Data Migration"""
        print_header("Phase 3: Data Migration")

        if self.dry_run:
            print_info("Dry-run mode: Showing migration strategy")
            print(f"\n{Color.YELLOW}Strategy:")
            print(f"1. Read records from source DB where date(timestamp) = '{self.migration_date}'")
            print(f"2. Insert into target DB using INSERT OR IGNORE")
            print(f"3. Transaction ensures all-or-nothing{Color.END}\n")
            return True, 0, 0

        source_conn = None
        target_conn = None

        try:
            # Read from source database (read-only)
            print_info(f"Reading records from source database...")
            source_uri = f"file:{self.source_db.absolute().as_posix()}?mode=ro"
            source_conn = sqlite3.connect(source_uri, uri=True)
            source_cursor = source_conn.cursor()

            source_cursor.execute("""
                SELECT * FROM rates_snapshot
                WHERE date(timestamp) = ?
            """, (self.migration_date,))

            records = source_cursor.fetchall()
            source_conn.close()
            source_conn = None

            print_success(f"Read {len(records)} records from source")

            # Write to target database
            print_info(f"Inserting records into target database...")
            target_conn = sqlite3.connect(self.target_db)
            target_cursor = target_conn.cursor()

            # Begin transaction
            target_conn.execute("BEGIN TRANSACTION")

            # Get initial count
            target_cursor.execute("SELECT COUNT(*) FROM rates_snapshot")
            initial_count = target_cursor.fetchone()[0]

            # Get column count to build INSERT statement
            target_cursor.execute("PRAGMA table_info(rates_snapshot)")
            columns = target_cursor.fetchall()
            num_columns = len(columns)
            placeholders = ','.join(['?' for _ in range(num_columns)])

            # Insert records
            inserted_count = 0
            for record in records:
                try:
                    target_cursor.execute(
                        f"INSERT OR IGNORE INTO rates_snapshot VALUES ({placeholders})",
                        record
                    )
                    if target_cursor.rowcount > 0:
                        inserted_count += 1
                except sqlite3.IntegrityError:
                    # Record already exists, skip it
                    pass

            # Get final count
            target_cursor.execute("SELECT COUNT(*) FROM rates_snapshot")
            final_count = target_cursor.fetchone()[0]

            actual_inserted = final_count - initial_count

            # Commit transaction
            target_conn.commit()
            target_conn.close()
            target_conn = None

            print_success(f"Migration completed successfully")
            print_info(f"  Initial count: {initial_count:,} records")
            print_info(f"  Final count: {final_count:,} records")
            print_info(f"  Records inserted: {actual_inserted:,}")
            print_info(f"  Records ignored (duplicates): {len(records) - actual_inserted}")

            return True, len(records), actual_inserted

        except sqlite3.Error as e:
            print_error(f"Migration failed: {e}")
            if source_conn:
                source_conn.close()
            if target_conn:
                target_conn.rollback()
                target_conn.close()
            return False, 0, 0

    def verify_migration(self):
        """Phase 4: Post-Migration Verification"""
        print_header("Phase 4: Post-Migration Verification")

        if self.dry_run:
            print_info("Dry-run mode: Skipping verification")
            return True

        try:
            conn = sqlite3.connect(self.target_db)
            cursor = conn.cursor()

            # Check for today's records
            cursor.execute("""
                SELECT COUNT(*), COUNT(DISTINCT timestamp)
                FROM rates_snapshot
                WHERE date(timestamp) = ?
            """, (self.migration_date,))

            count, unique_timestamps = cursor.fetchone()
            print_success(f"Found {count} records for {self.migration_date} ({unique_timestamps} unique timestamps)")

            # Show sample records
            cursor.execute("""
                SELECT timestamp, protocol, token, lend_total_apr, borrow_total_apr
                FROM rates_snapshot
                WHERE date(timestamp) = ?
                ORDER BY timestamp DESC
                LIMIT 3
            """, (self.migration_date,))

            print_info("Sample records:")
            for row in cursor.fetchall():
                ts, protocol, token, lend_apr, borrow_apr = row
                lend_str = f"{lend_apr:.2f}" if lend_apr is not None else "N/A"
                borrow_str = f"{borrow_apr:.2f}" if borrow_apr is not None else "N/A"
                print(f"    {ts} | {protocol} | {token} | Lend: {lend_str}% | Borrow: {borrow_str}%")

            # Run integrity check
            print_info("Running database integrity check...")
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]

            if result == "ok":
                print_success("Database integrity check: PASSED")
            else:
                print_error(f"Database integrity check: FAILED - {result}")
                conn.close()
                return False

            conn.close()
            return True

        except sqlite3.Error as e:
            print_error(f"Verification failed: {e}")
            return False

    def create_rollback_script(self):
        """Phase 5: Create Rollback Script"""
        print_header("Phase 5: Rollback Script Creation")

        if self.dry_run:
            print_info("Dry-run mode: Skipping rollback script creation")
            return True

        if not self.backup_path:
            print_warning("No backup was created, skipping rollback script")
            return True

        try:
            rollback_filename = f"rollback_migration_{self.timestamp}.py"
            self.rollback_script_path = Path("Scripts") / rollback_filename

            rollback_code = f'''#!/usr/bin/env python3
"""
Rollback Script for Migration {self.timestamp}

This script will restore lending_rates.db from the backup created
before the migration on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.

Usage:
    python {rollback_filename} [--confirm]
"""

import shutil
import sys
from pathlib import Path

BACKUP_PATH = Path(r"{self.backup_path.absolute()}")
TARGET_PATH = Path(r"{self.target_db.absolute()}")
SAFETY_BACKUP = TARGET_PATH.parent / f"lending_rates.db.pre_rollback_{self.timestamp}"

def main():
    if "--confirm" not in sys.argv:
        print("[!] WARNING: This will replace the current database with the backup!")
        print(f"  Current DB: {{TARGET_PATH}}")
        print(f"  Backup: {{BACKUP_PATH}}")
        print("\\nRun with --confirm flag to proceed:")
        print(f"  python {{Path(__file__).name}} --confirm")
        sys.exit(1)

    # Check backup exists
    if not BACKUP_PATH.exists():
        print(f"[X] Backup not found: {{BACKUP_PATH}}")
        sys.exit(1)

    # Create safety backup of current state
    print(f"Creating safety backup: {{SAFETY_BACKUP}}")
    shutil.copy2(TARGET_PATH, SAFETY_BACKUP)

    # Restore from backup
    print(f"Restoring from backup: {{BACKUP_PATH}}")
    shutil.copy2(BACKUP_PATH, TARGET_PATH)

    print("[OK] Rollback completed successfully")
    print(f"  Safety backup: {{SAFETY_BACKUP}}")
    print(f"  You can delete it once you verify the rollback")

if __name__ == "__main__":
    main()
'''

            with open(self.rollback_script_path, 'w') as f:
                f.write(rollback_code)

            print_success(f"Rollback script created: {self.rollback_script_path}")
            print_info(f"  To rollback: python {self.rollback_script_path} --confirm")

            return True

        except Exception as e:
            print_error(f"Failed to create rollback script: {e}")
            return False

    def run(self):
        """Execute full migration workflow"""
        print_header(f"Database Migration: {self.migration_date}")

        if self.dry_run:
            print_warning("DRY-RUN MODE: No changes will be made")

        # Phase 1: Validation
        if not self.validate_databases():
            print_error("Pre-migration validation failed")
            return 1

        # Phase 2: Backup
        if not self.create_backup():
            print_error("Backup creation failed")
            return 2

        # Phase 3: Migration
        success, rows_attempted, rows_inserted = self.execute_migration()
        if not success:
            print_error("Migration failed")
            if self.backup_path and not self.dry_run:
                print_warning("Database should be automatically rolled back")
                print_info(f"  If not, restore from: {self.backup_path}")
            return 2

        # Phase 4: Verification
        if not self.verify_migration():
            print_error("Post-migration verification failed")
            if self.backup_path and not self.dry_run:
                print_warning(f"Consider rolling back from: {self.backup_path}")
            return 2

        # Phase 5: Rollback Script
        if not self.create_rollback_script():
            print_warning("Rollback script creation failed (migration succeeded)")

        # Summary
        print_header("Migration Summary")
        if self.dry_run:
            print_success("Dry-run completed - no changes made")
        else:
            print_success("Migration completed successfully!")
            print_info(f"  Records inserted: {rows_inserted}")
            print_info(f"  Backup location: {self.backup_path}")
            if self.rollback_script_path:
                print_info(f"  Rollback script: {self.rollback_script_path}")

        return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate today's rates snapshots from partial DB to main DB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without making changes"
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date to migrate (YYYY-MM-DD), defaults to today"
    )
    parser.add_argument(
        "--source",
        default="data/lending_rates_partial.db",
        help="Source database path"
    )
    parser.add_argument(
        "--target",
        default="data/lending_rates.db",
        help="Target database path"
    )

    args = parser.parse_args()

    migration = DatabaseMigration(
        source_db=args.source,
        target_db=args.target,
        migration_date=args.date,
        dry_run=args.dry_run
    )

    sys.exit(migration.run())


if __name__ == "__main__":
    main()
