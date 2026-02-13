"""
Backfill initial rebalance records for positions that are missing sequence_number=1.

This script creates initial rebalance records (sequence_number=1) for positions
that don't have any rebalance history. This is needed because the rendering
system expects all positions to have at least one rebalance record representing
the initial deployment.

Design Principle #4: Event Sourcing - Every position should have an initial
rebalance record capturing the entry state.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings
from dashboard.dashboard_utils import get_db_connection
from analysis.position_service import PositionService
from utils.time_helpers import to_seconds, to_datetime_str
import pandas as pd


def backfill_initial_rebalances():
    """
    Create initial rebalance records for positions missing sequence_number=1.
    """
    print("=" * 80)
    print("BACKFILL INITIAL REBALANCES")
    print("=" * 80)

    conn = get_db_connection()
    service = PositionService(conn)

    # Get all active positions
    print("\n1. Loading all active positions...")
    query = "SELECT * FROM positions WHERE status = 'active'"
    positions_df = pd.read_sql_query(query, conn)
    print(f"   Found {len(positions_df)} active positions")

    # Check which positions are missing initial rebalance records
    positions_to_fix = []

    for idx, position in positions_df.iterrows():
        position_id = position['position_id']

        # Check if position has any rebalances
        rebalances = service.get_rebalance_history(position_id)

        if rebalances.empty:
            positions_to_fix.append(position)
            print(f"   ⚠️  Position {position_id[:8]}... has NO rebalance records")
        else:
            # Check if has sequence_number=1
            if 1 not in rebalances['sequence_number'].values:
                positions_to_fix.append(position)
                print(f"   ⚠️  Position {position_id[:8]}... missing sequence_number=1")

    if not positions_to_fix:
        print("\n✅ All positions have initial rebalance records. Nothing to backfill.")
        conn.close()
        return

    print(f"\n2. Found {len(positions_to_fix)} positions needing initial rebalance records")
    print("   Creating initial rebalance records...")

    success_count = 0
    error_count = 0

    for position in positions_to_fix:
        position_id = position['position_id']
        position_short_id = position_id[:8]

        try:
            # Create initial rebalance record using position entry data
            entry_timestamp = to_seconds(position['entry_timestamp'])

            # Build initial snapshot from position entry data
            snapshot = {
                'opening_timestamp': entry_timestamp,
                'closing_timestamp': entry_timestamp,  # Same as opening for initial record
                'deployment_usd': position['deployment_usd'],
                'l_a': position['l_a'],
                'b_a': position['b_a'],
                'l_b': position['l_b'],
                'b_b': position['b_b'],

                # Opening state (from position entry)
                'opening_lend_rate_1a': position['entry_lend_rate_1a'],
                'opening_borrow_rate_2a': position['entry_borrow_rate_2a'],
                'opening_lend_rate_2b': position['entry_lend_rate_2b'],
                'opening_borrow_rate_3b': position['entry_borrow_rate_3b'],

                'opening_price_1a': position['entry_price_1a'],
                'opening_price_2a': position['entry_price_2a'],
                'opening_price_2b': position['entry_price_2b'],
                'opening_price_3b': position['entry_price_3b'],

                # Closing state (same as opening for initial record)
                'closing_lend_rate_1a': position['entry_lend_rate_1a'],
                'closing_borrow_rate_2a': position['entry_borrow_rate_2a'],
                'closing_lend_rate_2b': position['entry_lend_rate_2b'],
                'closing_borrow_rate_3b': position['entry_borrow_rate_3b'],

                'closing_price_1a': position['entry_price_1a'],
                'closing_price_2a': position['entry_price_2a'],
                'closing_price_2b': position['entry_price_2b'],
                'closing_price_3b': position['entry_price_3b'],

                # Token amounts (from position entry)
                'entry_token_amount_1a': position.get('entry_token_amount_1a'),
                'entry_token_amount_2a': position.get('entry_token_amount_2a'),
                'entry_token_amount_2b': position.get('entry_token_amount_2b'),
                'entry_token_amount_3b': position.get('entry_token_amount_3b'),

                # Exit amounts (same as entry for initial record)
                'exit_token_amount_1a': position.get('entry_token_amount_1a'),
                'exit_token_amount_2a': position.get('entry_token_amount_2a'),
                'exit_token_amount_2b': position.get('entry_token_amount_2b'),
                'exit_token_amount_3b': position.get('entry_token_amount_3b'),

                # Zero metrics for initial record (no earnings yet)
                'realised_pnl': 0.0,
                'realised_fees': 0.0,
                'realised_lend_earnings': 0.0,
                'realised_borrow_costs': 0.0,
            }

            # Create rebalance record with sequence_number=1
            service.create_rebalance_record(
                position_id=position_id,
                snapshot=snapshot,
                rebalance_reason='initial_deployment',
                rebalance_notes='Initial rebalance record created during backfill'
            )

            print(f"   ✅ Created initial rebalance for {position_short_id}...")
            success_count += 1

        except Exception as e:
            print(f"   ❌ Failed for {position_short_id}...: {e}")
            error_count += 1

    print(f"\n3. Backfill complete:")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Errors: {error_count}")

    conn.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        backfill_initial_rebalances()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
