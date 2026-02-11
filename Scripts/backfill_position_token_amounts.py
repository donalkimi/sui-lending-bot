#!/usr/bin/env python3
"""
Backfill entry_token_amount_* columns for existing positions.

This script calculates and populates entry_token_amount_1A/2A/2B/3B for all positions
that don't have these values yet.

Formula: entry_token_amount = deployment_usd * weight / entry_price

Usage (run from project root):
    python Scripts/backfill_position_token_amounts.py
"""

from dashboard.dashboard_utils import get_db_connection
from config import settings


def backfill_position_token_amounts():
    """Calculate and populate entry_token_amount_* for all existing positions."""

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("Backfilling entry_token_amount_* for existing positions")
        print("=" * 60)
        print()

        # Get all positions where token amounts are NULL
        cursor.execute("""
            SELECT position_id, deployment_usd,
                   l_a, b_a, l_b, b_b,
                   entry_price_1a, entry_price_2a, entry_price_2b, entry_price_3b
            FROM positions
            WHERE entry_token_amount_1a IS NULL
            ORDER BY entry_timestamp
        """)

        positions = cursor.fetchall()
        total_positions = len(positions)

        if total_positions == 0:
            print("✅ No positions to backfill - all positions already have token amounts")
            return

        print(f"Found {total_positions} positions to backfill")
        print()

        # Process each position
        success_count = 0
        error_count = 0

        for position in positions:
            position_id = position[0]
            deployment_usd = float(position[1]) if position[1] else 0
            l_a = float(position[2]) if position[2] else 0
            b_a = float(position[3]) if position[3] else 0
            l_b = float(position[4]) if position[4] else 0
            b_b = float(position[5]) if position[5] else None
            entry_price_1a = float(position[6]) if position[6] else 0
            entry_price_2a = float(position[7]) if position[7] else 0
            entry_price_2b = float(position[8]) if position[8] else 0
            entry_price_3b = float(position[9]) if position[9] else None

            try:
                # Calculate entry token amounts: (weight * deployment) / price
                entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
                entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
                entry_token_amount_2b = (l_b * deployment_usd) / entry_price_2b if entry_price_2b > 0 else 0
                entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if b_b and entry_price_3b and entry_price_3b > 0 else None

                # Update position
                ph = '?' if not settings.USE_CLOUD_DB else '%s'
                cursor.execute(f"""
                    UPDATE positions
                    SET entry_token_amount_1a = {ph},
                        entry_token_amount_2a = {ph},
                        entry_token_amount_2b = {ph},
                        entry_token_amount_3b = {ph}
                    WHERE position_id = {ph}
                """, (
                    entry_token_amount_1a,
                    entry_token_amount_2a,
                    entry_token_amount_2b,
                    entry_token_amount_3b,
                    position_id
                ))

                success_count += 1
                if success_count % 10 == 0:
                    print(f"Processed {success_count}/{total_positions} positions...")

            except Exception as e:
                error_count += 1
                print(f"❌ Failed to backfill position {position_id[:8]}...: {e}")
                # Continue to next position

        conn.commit()

        print()
        print("=" * 60)
        print(f"✅ Backfill complete!")
        print(f"   Total positions processed: {total_positions}")
        print(f"   Successfully backfilled: {success_count}")
        print(f"   Errors: {error_count}")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    backfill_position_token_amounts()
