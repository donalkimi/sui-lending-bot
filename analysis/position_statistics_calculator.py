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
from config import settings


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

    # 2. Check for rebalances.
    # get_rebalance_history returns ALL records including the initial open segment
    # (closing_timestamp = NULL). We need to find the last CLOSED segment to determine
    # the live segment start and its opening token amounts.
    rebalances = service.get_rebalance_history(position_id)

    # Separate closed segments (closing_timestamp is set) from the open segment.
    if not rebalances.empty:
        closed_mask = rebalances['closing_timestamp'].notna()
        closed_rebalances = rebalances[closed_mask]
    else:
        closed_rebalances = rebalances  # empty

    has_rebalances = not closed_rebalances.empty

    # 3. Calculate live segment (entry or last rebalance → timestamp).
    # The live segment starts at the closing_timestamp of the last CLOSED rebalance,
    # which equals the opening_timestamp of the current open segment.
    if has_rebalances:
        last_rebalance = closed_rebalances.iloc[-1]
        segment_start_ts = to_seconds(last_rebalance['closing_timestamp'])

        # Use exit token amounts from last closed rebalance as starting point for live segment
        live_position = pd.Series({
            'deployment_usd': position['deployment_usd'],
            'l_a': position['l_a'], 'b_a': position['b_a'],
            'l_b': position['l_b'], 'b_b': position['b_b'],
            'strategy_type': position.get('strategy_type'),
            'token1': position['token1'], 'token2': position['token2'],
            'token3': position['token3'], 'token4': position.get('token4'),
            'token1_contract': position['token1_contract'],
            'token2_contract': position.get('token2_contract'),
            'token3_contract': position.get('token3_contract'),
            'token4_contract': position.get('token4_contract'),
            'protocol_a': position['protocol_a'], 'protocol_b': position['protocol_b'],
            'entry_token1_amount': last_rebalance['exit_token1_amount'],
            'entry_token2_amount': last_rebalance['exit_token2_amount'],
            'entry_token3_amount': last_rebalance['exit_token3_amount'],
            'entry_token4_amount': last_rebalance['exit_token4_amount']
        })
    else:
        # No closed rebalances — position is in its initial state.
        # Live segment started at entry_ts; use position's entry token amounts.
        segment_start_ts = entry_ts
        last_rebalance = None
        live_position = position

    # Determine perp actions from strategy type (universal: token3=L_B, token4=B_B)
    _strategy_type = live_position.get('strategy_type', '')
    token3_action = 'LongPerp' if _strategy_type in ('perp_borrowing', 'perp_borrowing_recursive') else 'Lend'
    token4_action = 'ShortPerp' if _strategy_type == 'perp_lending' else 'Borrow'

    # Calculate earnings for all 4 token slots (live segment)
    base_1, reward_1 = service.calculate_leg_earnings_split(
        live_position, 'token1', 'Lend', segment_start_ts, timestamp
    )
    base_2, reward_2 = service.calculate_leg_earnings_split(
        live_position, 'token2', 'Borrow', segment_start_ts, timestamp
    )
    base_3, reward_3 = service.calculate_leg_earnings_split(
        live_position, 'token3', token3_action, segment_start_ts, timestamp
    )
    base_4, reward_4 = service.calculate_leg_earnings_split(
        live_position, 'token4', token4_action, segment_start_ts, timestamp
    )

    # Calculate live segment earnings
    live_base_lend = base_1 + base_3      # lend slots (token1, token3)
    live_base_borrow = base_2 + base_4    # borrow slots (token2, token4)
    live_base_earnings = live_base_lend - live_base_borrow
    live_reward_earnings = reward_1 + reward_2 + reward_3 + reward_4

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
        # Iterate through all CLOSED rebalance segments only (open segment has no closing data)
        for _, rebal in closed_rebalances.iterrows():
            # Get the segment boundaries
            opening_ts_rebal = to_seconds(rebal['opening_timestamp'])
            closing_ts_rebal = to_seconds(rebal['closing_timestamp'])

            # Use stored fees (accurate from rebalance time)
            rebalanced_fees += rebal.get('realised_fees', 0.0) or 0.0

            # DON'T use stored realised_pnl - we'll recalculate it for consistency
            # rebalanced_pnl += rebal.get('realised_pnl', 0.0) or 0.0  # ← REMOVED

            # Create position-like object for this rebalance segment
            # Use entry token amounts from the rebalance record (amounts at start of this segment)
            rebal_as_pos = pd.Series({
                'deployment_usd': rebal['deployment_usd'],
                'l_a': rebal['l_a'], 'b_a': rebal['b_a'],
                'l_b': rebal['l_b'], 'b_b': rebal['b_b'],
                'strategy_type': position.get('strategy_type'),
                'token1': position['token1'], 'token2': position['token2'],
                'token3': position['token3'], 'token4': position.get('token4'),
                'token1_contract': position['token1_contract'],
                'token2_contract': position.get('token2_contract'),
                'token3_contract': position.get('token3_contract'),
                'token4_contract': position.get('token4_contract'),
                'protocol_a': position['protocol_a'], 'protocol_b': position['protocol_b'],
                'entry_token1_amount': rebal['entry_token1_amount'],
                'entry_token2_amount': rebal['entry_token2_amount'],
                'entry_token3_amount': rebal['entry_token3_amount'],
                'entry_token4_amount': rebal['entry_token4_amount']
            })

            # Determine perp actions for this segment
            _seg_strategy_type = rebal_as_pos.get('strategy_type', '')
            seg_token3_action = 'LongPerp' if _seg_strategy_type in ('perp_borrowing', 'perp_borrowing_recursive') else 'Lend'
            seg_token4_action = 'ShortPerp' if _seg_strategy_type == 'perp_lending' else 'Borrow'

            # Calculate earnings for all 4 token slots (rebalance segment)
            rebal_base_1, rebal_reward_1 = service.calculate_leg_earnings_split(
                rebal_as_pos, 'token1', 'Lend', opening_ts_rebal, closing_ts_rebal
            )
            rebal_base_2, rebal_reward_2 = service.calculate_leg_earnings_split(
                rebal_as_pos, 'token2', 'Borrow', opening_ts_rebal, closing_ts_rebal
            )
            rebal_base_3, rebal_reward_3 = service.calculate_leg_earnings_split(
                rebal_as_pos, 'token3', seg_token3_action, opening_ts_rebal, closing_ts_rebal
            )
            rebal_base_4, rebal_reward_4 = service.calculate_leg_earnings_split(
                rebal_as_pos, 'token4', seg_token4_action, opening_ts_rebal, closing_ts_rebal
            )

            # Calculate segment base/reward breakdown
            segment_base_lend = rebal_base_1 + rebal_base_3    # lend slots (token1, token3)
            segment_base_borrow = rebal_base_2 + rebal_base_4  # borrow slots (token2, token4)
            segment_base = segment_base_lend - segment_base_borrow
            segment_reward = rebal_reward_1 + rebal_reward_2 + rebal_reward_3 + rebal_reward_4

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

    # 7. Calculate current APR from live rates (universal leg convention — no strategy branching)
    # token1=L_A, token2=B_A, token3=L_B, token4=B_B; None contract = leg unused → 0.0
    lend_1A = get_rate_func(position['token1_contract'], position['protocol_a'], 'lend')

    borrow_2A = get_rate_func(position['token2_contract'], position['protocol_a'], 'borrow') \
                if position.get('token2_contract') else 0.0
    borrow_fee_2A_current = get_borrow_fee_func(position['token2_contract'], position['protocol_a']) \
                            if position.get('token2_contract') else 0.0

    lend_2B = get_rate_func(position['token3_contract'], position['protocol_b'], 'lend') \
              if position.get('token3_contract') else 0.0

    borrow_3B = get_rate_func(position['token4_contract'], position['protocol_b'], 'borrow') \
                if position.get('token4_contract') else 0.0
    borrow_fee_3B_current = get_borrow_fee_func(position['token4_contract'], position['protocol_b']) \
                            if position.get('token4_contract') else 0.0

    # Calculate gross APR (weighted average of all legs)
    gross_apr = (l_a * lend_1A) + (l_b * lend_2B) - (b_a * borrow_2A) - (b_b * borrow_3B)

    # Calculate fee cost (borrow protocol fees)
    fee_cost = b_a * borrow_fee_2A_current + b_b * borrow_fee_3B_current

    # Perp trading fees: annualised entry + exit taker fee cost
    # perp_lending:             perp leg = b_b (short perp)
    # perp_borrowing/recursive: perp leg = l_b (long perp)
    # all other strategies:     0.0
    _strategy_type = position.get('strategy_type', '')
    if _strategy_type == 'perp_lending':
        perp_trading_fee_apr = b_b * 2.0 * settings.BLUEFIN_TAKER_FEE
    elif _strategy_type in ('perp_borrowing', 'perp_borrowing_recursive'):
        perp_trading_fee_apr = l_b * 2.0 * settings.BLUEFIN_TAKER_FEE
    else:
        perp_trading_fee_apr = 0.0

    # Calculate NET current APR
    current_apr = gross_apr - fee_cost - perp_trading_fee_apr

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
