"""
Position Statistics Calculator

Calculates and prepares position summary statistics for storage in the position_statistics table.
This logic is extracted from the dashboard's expanded view calculation (dashboard_renderer.py lines 1893-1997)
to eliminate duplicate calculations and improve performance.

Core Principle:
- Calculate once during data collection pipeline
- Store in database
- Dashboard reads from database (no calculation)
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

from analysis.position_service import PositionService
from utils.time_helpers import to_seconds, to_datetime_str


def calculate_position_statistics(
    position_id: str,
    timestamp: int,  # Unix seconds
    service: PositionService,
    get_rate_func,  # Function to get rates from database at timestamp
    get_borrow_fee_func,  # Function to get borrow fees from database at timestamp
) -> dict:
    """
    Calculate position summary statistics for a given timestamp.

    This implements the correct calculation logic from dashboard_renderer.py (lines 1893-1997).

    Args:
        position_id: The position ID to calculate statistics for
        timestamp: Unix timestamp in seconds (the "live" time for calculation)
        service: PositionService instance for leg earnings calculations
        get_rate_func: Function(token_contract, protocol, side) -> rate (decimal)
        get_borrow_fee_func: Function(token_contract, protocol) -> fee (decimal)

    Returns:
        dict: Statistics ready to insert into position_statistics table
            {
                'position_id': str,
                'timestamp': int,  # Unix seconds
                'total_pnl': float,
                'total_earnings': float,
                'base_earnings': float,
                'reward_earnings': float,
                'total_fees': float,
                'current_value': float,
                'realized_apr': float,
                'current_apr': float,
                'live_pnl': float,
                'realized_pnl': float,
                'calculation_timestamp': int  # Unix seconds when calculated
            }
    """
    import time

    # 1. Load position data
    position = service.get_position_by_id(position_id)
    if position is None:
        raise ValueError(f"Position {position_id} not found")

    # Extract position parameters
    entry_ts = to_seconds(position['entry_timestamp'])
    deployment_usd = position['deployment_usd']
    l_a = position['l_a']
    b_a = position['b_a']
    l_b = position['l_b']
    b_b = position['b_b']

    # 2. Check for rebalances
    rebalances = service.get_rebalance_history(position_id)
    has_rebalances = not rebalances.empty

    # 3. Calculate live segment (entry or last rebalance → timestamp)
    if has_rebalances:
        segment_start_ts = to_seconds(rebalances.iloc[-1]['closing_timestamp'])
        last_rebalance = rebalances.iloc[-1]
    else:
        segment_start_ts = entry_ts
        last_rebalance = None

    # Calculate base and reward earnings for all 4 legs (live segment)
    try:
        base_1A, reward_1A = service.calculate_leg_earnings_split(
            position, '1a', 'Lend', segment_start_ts, timestamp
        )
        base_2A, reward_2A = service.calculate_leg_earnings_split(
            position, '2a', 'Borrow', segment_start_ts, timestamp
        )
        base_2B, reward_2B = service.calculate_leg_earnings_split(
            position, '2b', 'Lend', segment_start_ts, timestamp
        )
        base_3B, reward_3B = service.calculate_leg_earnings_split(
            position, '3b', 'Borrow', segment_start_ts, timestamp
        )
    except Exception as e:
        # Fallback to zeros if calculation fails
        base_1A, reward_1A = 0.0, 0.0
        base_2A, reward_2A = 0.0, 0.0
        base_2B, reward_2B = 0.0, 0.0
        base_3B, reward_3B = 0.0, 0.0

    # Calculate live segment earnings
    live_base_lend = base_1A + base_2B  # lend legs (1a, 2b)
    live_base_borrow = base_2A + base_3B  # borrow legs (2a, 3b)
    live_base_earnings = live_base_lend - live_base_borrow  # earnings - costs
    live_reward_earnings = reward_1A + reward_2A + reward_2B + reward_3B

    # Get live segment fees from calculate_position_value (already correctly calculated)
    # Only include initial fees if position has never been rebalanced
    include_initial = not has_rebalances
    pv_result = service.calculate_position_value(position, segment_start_ts, timestamp, include_initial_fees=include_initial)
    live_fees = pv_result.get('fees', 0.0)

    # Live segment totals
    live_total_earnings = live_base_earnings + live_reward_earnings
    live_pnl = live_total_earnings - live_fees

    # 4. Sum rebalanced segments (from database)
    rebalanced_pnl = 0.0
    rebalanced_total_earnings = 0.0
    rebalanced_base_earnings = 0.0
    rebalanced_reward_earnings = 0.0
    rebalanced_fees = 0.0

    if has_rebalances:
        # Iterate through all rebalance segments
        for _, rebal in rebalances.iterrows():
            # Get the segment boundaries
            opening_ts_rebal = to_seconds(rebal['opening_timestamp'])
            closing_ts_rebal = to_seconds(rebal['closing_timestamp'])

            # Use stored fees (accurate from rebalance time)
            rebalanced_fees += rebal.get('realised_fees', 0.0) or 0.0

            # DON'T use stored realised_pnl - we'll recalculate it for consistency
            # rebalanced_pnl += rebal.get('realised_pnl', 0.0) or 0.0  # ← REMOVED

            # Create position-like object for this rebalance segment
            rebal_as_pos = pd.Series({
                'deployment_usd': rebal['deployment_usd'],
                'l_a': rebal['l_a'], 'b_a': rebal['b_a'],
                'l_b': rebal['l_b'], 'b_b': rebal['b_b'],
                'token1': position['token1'], 'token2': position['token2'], 'token3': position['token3'],
                'token1_contract': position['token1_contract'],
                'token2_contract': position['token2_contract'],
                'token3_contract': position['token3_contract'],
                'protocol_a': position['protocol_a'], 'protocol_b': position['protocol_b']
            })

            # Calculate base/reward earnings for all 4 legs (REQUIRED for dashboard display)
            try:
                rebal_base_1A, rebal_reward_1A = service.calculate_leg_earnings_split(
                    rebal_as_pos, '1a', 'Lend', opening_ts_rebal, closing_ts_rebal
                )
                rebal_base_2A, rebal_reward_2A = service.calculate_leg_earnings_split(
                    rebal_as_pos, '2a', 'Borrow', opening_ts_rebal, closing_ts_rebal
                )
                rebal_base_2B, rebal_reward_2B = service.calculate_leg_earnings_split(
                    rebal_as_pos, '2b', 'Lend', opening_ts_rebal, closing_ts_rebal
                )
                rebal_base_3B, rebal_reward_3B = service.calculate_leg_earnings_split(
                    rebal_as_pos, '3b', 'Borrow', opening_ts_rebal, closing_ts_rebal
                )

                # Calculate segment base/reward breakdown
                segment_base_lend = rebal_base_1A + rebal_base_2B  # lend legs
                segment_base_borrow = rebal_base_2A + rebal_base_3B  # borrow legs
                segment_base = segment_base_lend - segment_base_borrow  # earnings - costs
                segment_reward = rebal_reward_1A + rebal_reward_2A + rebal_reward_2B + rebal_reward_3B

                # Accumulate base/reward breakdown
                rebalanced_base_earnings += segment_base
                rebalanced_reward_earnings += segment_reward

                # Calculate total earnings from base + reward
                segment_total_earnings = segment_base + segment_reward
                rebalanced_total_earnings += segment_total_earnings

                # Calculate segment PnL: earnings - fees (ensures consistency)
                segment_fees = rebal.get('realised_fees', 0.0) or 0.0
                segment_pnl = segment_total_earnings - segment_fees
                rebalanced_pnl += segment_pnl  # ← RECALCULATED for consistency

            except Exception as e:
                # If calculation fails, skip this segment
                print(f"[WARNING] Failed to calculate base/reward for rebalance segment: {e}")
                pass

    # 5. Calculate totals (Real + Unreal)
    total_pnl = live_pnl + rebalanced_pnl
    total_earnings = live_total_earnings + rebalanced_total_earnings
    base_earnings = live_base_earnings + rebalanced_base_earnings
    reward_earnings = live_reward_earnings + rebalanced_reward_earnings
    total_fees = live_fees + rebalanced_fees

    current_value = deployment_usd + total_pnl

    # 6. Calculate realized APR (annualized return from entry to now)
    days_elapsed = (timestamp - entry_ts) / 86400
    if days_elapsed > 0 and deployment_usd > 0:
        realized_apr = (total_pnl / deployment_usd) * (365 / days_elapsed)
    else:
        realized_apr = 0.0

    # 7. Calculate current APR from live rates
    # Get current rates for all 4 legs
    lend_1A = get_rate_func(position['token1_contract'], position['protocol_a'], 'lend')
    borrow_2A = get_rate_func(position['token2_contract'], position['protocol_a'], 'borrow')
    lend_2B = get_rate_func(position['token2_contract'], position['protocol_b'], 'lend')
    borrow_3B = get_rate_func(position['token3_contract'], position['protocol_b'], 'borrow')

    # Get current borrow fees
    borrow_fee_2A_current = get_borrow_fee_func(position['token2_contract'], position['protocol_a'])
    borrow_fee_3B_current = get_borrow_fee_func(position['token3_contract'], position['protocol_b'])

    # Calculate gross APR (weighted average of all legs)
    gross_apr = (l_a * lend_1A) + (l_b * lend_2B) - (b_a * borrow_2A) - (b_b * borrow_3B)

    # Calculate fee cost
    fee_cost = b_a * borrow_fee_2A_current + b_b * borrow_fee_3B_current

    # Calculate NET current APR
    current_apr = gross_apr - fee_cost

    # 8. Return statistics dict
    return {
        'position_id': position_id,
        'timestamp': timestamp,  # Unix seconds
        'total_pnl': total_pnl,
        'total_earnings': total_earnings,
        'base_earnings': base_earnings,
        'reward_earnings': reward_earnings,
        'total_fees': total_fees,
        'current_value': current_value,
        'realized_apr': realized_apr,
        'current_apr': current_apr,
        'live_pnl': live_pnl,
        'realized_pnl': rebalanced_pnl,  # Note: variable is called rebalanced_pnl in calculation
        'calculation_timestamp': int(time.time())  # Unix seconds when calculated
    }
