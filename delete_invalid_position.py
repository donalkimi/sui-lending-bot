#!/usr/bin/env python3
"""Delete position with invalid LLTV data"""

import sqlite3
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from analysis.position_service import PositionService

def main():
    position_id = '3edf1701-3059-48e0-bb14-3b81de5eb81f'
    db_path = 'data/lending_rates.db'

    # Connect to database
    conn = sqlite3.connect(db_path)
    service = PositionService(conn)

    # Verify position exists and has LLTV = 0
    position = service.get_position_by_id(position_id)
    if position is None:
        print(f"Position {position_id} not found")
        return

    print(f"Found position:")
    print(f"  Position ID: {position_id}")
    print(f"  Strategy: {position['protocol_A']} ({position['token1']} → {position['token2']}) / "
          f"{position['protocol_B']} ({position['token2']} → {position['token3']})")
    print(f"  Entry Time: {position['entry_timestamp']}")
    print(f"  Protocol A LLTV: {position['entry_collateral_ratio_1A']}")
    print(f"  Protocol B LLTV: {position['entry_collateral_ratio_2B']}")

    # Verify LLTV = 0 issue
    if position['entry_collateral_ratio_2B'] != 0:
        print(f"\nWARNING: Protocol B LLTV is not 0 ({position['entry_collateral_ratio_2B']})")
        print("This position may not be the problematic one. Aborting.")
        return

    # Delete position
    print(f"\nDeleting position {position_id}...")
    service.delete_position(position_id)
    print("✓ Position deleted successfully")

    # Verify deletion
    verify = service.get_position_by_id(position_id)
    if verify is None:
        print("✓ Verified: Position no longer exists in database")
    else:
        print("✗ ERROR: Position still exists after deletion")

    # Show remaining active positions
    remaining = service.get_active_positions()
    print(f"\n{len(remaining)} active positions remaining")

    conn.close()

if __name__ == '__main__':
    main()
