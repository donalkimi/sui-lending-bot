"""
Fix BLOB deployment_usd values in position_rebalances table.

The issue: deployment_usd stored as 8-byte little-endian integers (BLOB)
The fix: Convert to proper SQLite INTEGER type
"""
import sqlite3
import struct
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

def fix_blob_deployments():
    """Convert BLOB deployment_usd values to INTEGER."""
    conn = sqlite3.connect(settings.SQLITE_PATH)
    cursor = conn.cursor()

    try:
        # Get all rebalance records
        cursor.execute("""
            SELECT rebalance_id, deployment_usd, typeof(deployment_usd)
            FROM position_rebalances
        """)

        records = cursor.fetchall()
        fixed_count = 0

        for rebalance_id, deployment_value, value_type in records:
            if value_type == 'blob':
                # Decode 8-byte little-endian integer
                if isinstance(deployment_value, bytes) and len(deployment_value) == 8:
                    decoded_value = struct.unpack('<Q', deployment_value)[0]

                    # Update with proper integer
                    cursor.execute("""
                        UPDATE position_rebalances
                        SET deployment_usd = ?
                        WHERE rebalance_id = ?
                    """, (decoded_value, rebalance_id))

                    fixed_count += 1
                    print(f"Fixed rebalance {rebalance_id[:8]}: {deployment_value!r} -> {decoded_value}")

        conn.commit()
        print(f"\n[SUCCESS] Fixed {fixed_count} records")

        # Verify fix
        cursor.execute("""
            SELECT COUNT(*)
            FROM position_rebalances
            WHERE typeof(deployment_usd) = 'blob'
        """)
        remaining_blobs = cursor.fetchone()[0]

        if remaining_blobs > 0:
            print(f"[WARNING] {remaining_blobs} BLOB values still remain")
        else:
            print("[SUCCESS] All deployment_usd values are now proper numeric types")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("Starting BLOB to INTEGER conversion...")
    fix_blob_deployments()
