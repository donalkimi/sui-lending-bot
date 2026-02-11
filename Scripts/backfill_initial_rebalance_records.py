#!/usr/bin/env python3
"""
Backfill initial rebalance records (sequence_number=1) for existing positions.

This script creates initial rebalance records for positions that don't have any rebalances.
This is needed because:
- Old positions were created before the code auto-created sequence_number=1
- Liquidation calculations require token amounts from rebalance records
- Without sequence_number=1, positions show "N/A" for all liquidation data

Usage:
    python Scripts/backfill_initial_rebalance_records.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dashboard.dashboard_utils import get_db_connection
from analysis.position_service import PositionService
from config import settings


def backfill_initial_rebalance_records():
    """Create initial rebalance records for positions without any rebalances."""

    conn = get_db_connection()
    service = PositionService(conn)
    cursor = conn.cursor()

    try:
        # Find positions with rebalance_count=0 (no rebalances)
        cursor.execute("""
            SELECT position_id, entry_timestamp, deployment_usd,
                   l_a, b_a, l_b, b_b,
                   entry_lend_rate_1a, entry_borrow_rate_2a, entry_lend_rate_2b, entry_borrow_rate_3b,
                   entry_price_1a, entry_price_2a, entry_price_2b, entry_price_3b,
                   entry_collateral_ratio_1a, entry_collateral_ratio_2b,
                   entry_liquidation_threshold_1a, entry_liquidation_threshold_2b
            FROM positions
            WHERE rebalance_count = 0 OR rebalance_count IS NULL
            ORDER BY entry_timestamp
        """)

        positions = cursor.fetchall()
        total_positions = len(positions)

        if total_positions == 0:
            print("✅ No positions to backfill - all positions already have rebalances")
            return

        print(f"Found {total_positions} positions without initial rebalance records")
        print()

        # Process each position
        success_count = 0
        error_count = 0

        for position in positions:
            position_id = position[0]
            entry_timestamp = position[1]
            deployment_usd = position[2]
            l_a, b_a, l_b, b_b = position[3], position[4], position[5], position[6]
            entry_lend_rate_1a, entry_borrow_rate_2a, entry_lend_rate_2b, entry_borrow_rate_3b = position[7], position[8], position[9], position[10]
            entry_price_1a, entry_price_2a, entry_price_2b, entry_price_3b = position[11], position[12], position[13], position[14]
            entry_collateral_ratio_1a, entry_collateral_ratio_2b = position[15], position[16]
            entry_liquidation_threshold_1a, entry_liquidation_threshold_2b = position[17], position[18]

            try:
                print(f"Processing position {position_id[:8]}... ({success_count + 1}/{total_positions})")

                # Calculate entry token amounts: (weight * deployment) / price
                entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a and entry_price_1a > 0 else 0
                entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a and entry_price_2a > 0 else 0
                entry_token_amount_2b = (l_b * deployment_usd) / entry_price_2b if entry_price_2b and entry_price_2b > 0 else 0
                entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if b_b and entry_price_3b and entry_price_3b > 0 else 0

                # Calculate entry size USD: weight * deployment
                entry_size_usd_1a = l_a * deployment_usd
                entry_size_usd_2a = b_a * deployment_usd
                entry_size_usd_2b = l_b * deployment_usd
                entry_size_usd_3b = b_b * deployment_usd if b_b else 0

                # Build snapshot for initial deployment (rebalance with opening but no closing)
                # Convert timestamp string to integer (Unix seconds)
                import datetime
                if isinstance(entry_timestamp, str):
                    dt = datetime.datetime.fromisoformat(entry_timestamp.replace('Z', '+00:00'))
                    entry_timestamp_int = int(dt.timestamp())
                else:
                    entry_timestamp_int = int(entry_timestamp)

                initial_snapshot = {
                    'opening_timestamp': entry_timestamp_int,  # Unix seconds (int)
                    'closing_timestamp': None,  # Still open
                    'deployment_usd': deployment_usd,
                    'l_a': l_a,
                    'b_a': b_a,
                    'l_b': l_b,
                    'b_b': b_b,

                    # Opening rates/prices (from position entry)
                    'opening_lend_rate_1a': entry_lend_rate_1a,
                    'opening_borrow_rate_2a': entry_borrow_rate_2a,
                    'opening_lend_rate_2b': entry_lend_rate_2b,
                    'opening_borrow_rate_3b': entry_borrow_rate_3b,
                    'opening_price_1a': entry_price_1a,
                    'opening_price_2a': entry_price_2a,
                    'opening_price_2b': entry_price_2b,
                    'opening_price_3b': entry_price_3b,

                    # Closing rates/prices (NULL for initial deployment)
                    'closing_lend_rate_1a': None,
                    'closing_borrow_rate_2a': None,
                    'closing_lend_rate_2b': None,
                    'closing_borrow_rate_3b': None,
                    'closing_price_1a': None,
                    'closing_price_2a': None,
                    'closing_price_2b': None,
                    'closing_price_3b': None,

                    # Closing liquidation prices/distances (NULL for initial deployment)
                    'closing_liq_price_1a': None,
                    'closing_liq_price_2a': None,
                    'closing_liq_price_2b': None,
                    'closing_liq_price_3b': None,
                    'closing_liq_dist_1a': None,
                    'closing_liq_dist_2a': None,
                    'closing_liq_dist_2b': None,
                    'closing_liq_dist_3b': None,

                    # Collateral ratios and liquidation thresholds
                    'collateral_ratio_1a': entry_collateral_ratio_1a,
                    'collateral_ratio_2b': entry_collateral_ratio_2b,
                    'liquidation_threshold_1a': entry_liquidation_threshold_1a,
                    'liquidation_threshold_2b': entry_liquidation_threshold_2b,

                    # Entry actions (what this position does)
                    'entry_action_1a': 'lend',
                    'entry_action_2a': 'borrow',
                    'entry_action_2b': 'lend',
                    'entry_action_3b': 'borrow' if b_b else None,

                    # Exit actions (NULL for initial deployment)
                    'exit_action_1a': None,
                    'exit_action_2a': None,
                    'exit_action_2b': None,
                    'exit_action_3b': None,

                    # Entry token amounts (calculated above)
                    'entry_token_amount_1a': entry_token_amount_1a,
                    'entry_token_amount_2a': entry_token_amount_2a,
                    'entry_token_amount_2b': entry_token_amount_2b,
                    'entry_token_amount_3b': entry_token_amount_3b,

                    # Exit token amounts (NULL for initial deployment)
                    'exit_token_amount_1a': None,
                    'exit_token_amount_2a': None,
                    'exit_token_amount_2b': None,
                    'exit_token_amount_3b': None,

                    # Entry size USD (calculated above)
                    'entry_size_usd_1a': entry_size_usd_1a,
                    'entry_size_usd_2a': entry_size_usd_2a,
                    'entry_size_usd_2b': entry_size_usd_2b,
                    'entry_size_usd_3b': entry_size_usd_3b,

                    # Exit size USD (NULL for initial deployment)
                    'exit_size_usd_1a': None,
                    'exit_size_usd_2a': None,
                    'exit_size_usd_2b': None,
                    'exit_size_usd_3b': None,

                    # Realised values (all 0 for initial deployment)
                    'realised_fees': 0,
                    'realised_pnl': 0,
                    'realised_lend_earnings': 0,
                    'realised_borrow_costs': 0,
                }

                # Create the initial rebalance record
                service.create_rebalance_record(
                    position_id=position_id,
                    snapshot=initial_snapshot,
                    rebalance_reason='backfill_initial_deployment',
                    rebalance_notes='Backfilled initial deployment (sequence_number=1) for positions created before auto-creation was implemented'
                )

                success_count += 1
                print(f"  ✅ Created initial rebalance record (sequence_number=1)")

            except Exception as e:
                error_count += 1
                print(f"  ❌ Failed: {e}")
                # Continue to next position

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
    print("=" * 60)
    print("Backfilling initial rebalance records (sequence_number=1)")
    print("=" * 60)
    print()

    backfill_initial_rebalance_records()
