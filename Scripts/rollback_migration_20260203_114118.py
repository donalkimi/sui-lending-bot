#!/usr/bin/env python3
"""
Rollback Script for Migration 20260203_114118

This script will restore lending_rates.db from the backup created
before the migration on 2026-02-03 11:41:18.

Usage:
    python rollback_migration_20260203_114118.py [--confirm]
"""

import shutil
import sys
from pathlib import Path

BACKUP_PATH = Path(r"c:\Dev\sui-lending-bot\data\backups\lending_rates.db.backup_20260203_114118")
TARGET_PATH = Path(r"c:\Dev\sui-lending-bot\data\lending_rates.db")
SAFETY_BACKUP = TARGET_PATH.parent / "lending_rates.db.pre_rollback_20260203_114118"

def main():
    if "--confirm" not in sys.argv:
        print("[!] WARNING: This will replace the current database with the backup!")
        print(f"  Current DB: {TARGET_PATH}")
        print(f"  Backup: {BACKUP_PATH}")
        print("\nRun with --confirm flag to proceed:")
        print(f"  python {Path(__file__).name} --confirm")
        sys.exit(1)

    # Check backup exists
    if not BACKUP_PATH.exists():
        print(f"[X] Backup not found: {BACKUP_PATH}")
        sys.exit(1)

    # Create safety backup of current state
    print(f"Creating safety backup: {SAFETY_BACKUP}")
    shutil.copy2(TARGET_PATH, SAFETY_BACKUP)

    # Restore from backup
    print(f"Restoring from backup: {BACKUP_PATH}")
    shutil.copy2(BACKUP_PATH, TARGET_PATH)

    print("[OK] Rollback completed successfully")
    print(f"  Safety backup: {SAFETY_BACKUP}")
    print(f"  You can delete it once you verify the rollback")

if __name__ == "__main__":
    main()
