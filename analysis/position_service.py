import sqlite3
import uuid
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.time_helpers import to_datetime_str, to_seconds
from analysis.position_calculator import PositionCalculator


class PositionService:
    """
    Service for managing paper trading positions (Phase 1) and real capital positions (Phase 2).

    Key principles:
    - Event sourcing: positions table stores immutable entry state
    - Forward-looking calculations: rates at time T apply to period [T, T+1)
    - No datetime.now() - all timestamps must be explicitly provided
    - Timestamps in Unix seconds (int) internally
    """

    def __init__(self, conn: sqlite3.Connection):
        """Initialize with database connection"""
        self.conn = conn

    # ==================== Position Management ====================

    def create_position(
        self,
        strategy_row: pd.Series,
        positions: Dict,
        token1: str,
        token2: str,
        token3: Optional[str],
        token1_contract: str,
        token2_contract: str,
        token3_contract: Optional[str],
        protocol_A: str,
        protocol_B: str,
        deployment_usd: float,
        is_paper_trade: bool = True,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
        wallet_address: Optional[str] = None,
        transaction_hash_open: Optional[str] = None,
        on_chain_position_id: Optional[str] = None
    ) -> str:
        """
        Create a new position (Phase 1: paper trade, Phase 2: real capital)

        Args:
            strategy_row: Strategy data with timestamp, rates, prices, APRs
            positions: Position multipliers (L_A, B_A, L_B, B_B)
            token1: First token symbol
            token2: Second token symbol
            token3: Third token symbol
            token1_contract: Token1 contract address
            token2_contract: Token2 contract address
            token3_contract: Token3 contract address
            protocol_A: First protocol name
            protocol_B: Second protocol name
            deployment_usd: USD amount to deploy
            is_paper_trade: True for Phase 1 (paper), False for Phase 2 (real capital)
            user_id: Optional user ID for multi-user support (Phase 2)
            notes: Optional user notes
            wallet_address: Optional wallet address (Phase 2)
            transaction_hash_open: Optional transaction hash for opening (Phase 2)
            on_chain_position_id: Optional on-chain position ID (Phase 2)

        Returns:
            position_id: UUID of created position

        Raises:
            ValueError: If timestamp is missing
            TypeError: If timestamp is not int
        """
        # Validate timestamp
        entry_timestamp = strategy_row.get('timestamp')
        if entry_timestamp is None:
            raise ValueError("strategy_row must contain 'timestamp' - cannot default to datetime.now()")

        if not isinstance(entry_timestamp, int):
            raise TypeError(
                f"entry_timestamp must be Unix seconds (int), got {type(entry_timestamp).__name__}. "
                f"Use to_seconds() to convert."
            )

        # Generate position ID
        position_id = str(uuid.uuid4())

        # Extract multipliers
        L_A = positions['L_A']
        B_A = positions['B_A']
        L_B = positions['L_B']
        B_B = positions.get('B_B')

        # Extract entry rates (already in decimal format: 0.0316 = 3.16%)
        entry_lend_rate_1A = strategy_row.get('lend_rate_1A', 0)
        entry_borrow_rate_2A = strategy_row.get('borrow_rate_2A', 0)
        entry_lend_rate_2B = strategy_row.get('lend_rate_2B', 0)
        entry_borrow_rate_3B = strategy_row.get('borrow_rate_3B')

        # Extract entry prices (leg-level)
        entry_price_1A = strategy_row.get('P1_A', 0)
        entry_price_2A = strategy_row.get('P2_A', 0)
        entry_price_2B = strategy_row.get('P2_B', 0)
        entry_price_3B = strategy_row.get('P3_B')

        # Extract entry collateral ratios
        entry_collateral_ratio_1A = strategy_row.get('collateral_ratio_1A', 0)
        entry_collateral_ratio_2B = strategy_row.get('collateral_ratio_2B', 0)

        # Extract entry liquidation thresholds
        entry_liquidation_threshold_1A = strategy_row.get('liquidation_threshold_1A', 0)
        entry_liquidation_threshold_2B = strategy_row.get('liquidation_threshold_2B', 0)

        # Extract entry strategy APRs (already fee-adjusted)
        entry_net_apr = strategy_row.get('net_apr', 0)
        entry_apr5 = strategy_row.get('apr5', 0)
        entry_apr30 = strategy_row.get('apr30', 0)
        entry_apr90 = strategy_row.get('apr90', 0)
        entry_days_to_breakeven = strategy_row.get('days_to_breakeven')
        entry_liquidation_distance = strategy_row.get('liquidation_distance', 0)

        # Extract entry liquidity & fees
        entry_max_size_usd = strategy_row.get('max_size_usd')
        entry_borrow_fee_2A = strategy_row.get('borrow_fee_2A')
        entry_borrow_fee_3B = strategy_row.get('borrow_fee_3B')

        # Extract entry borrow weights (default 1.0)
        entry_borrow_weight_2A = strategy_row.get('borrow_weight_2A', 1.0)
        entry_borrow_weight_3B = strategy_row.get('borrow_weight_3B', 1.0)

        # Convert timestamp to datetime string for DB
        entry_timestamp_str = to_datetime_str(entry_timestamp)

        # Insert position
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO positions (
                position_id, status, strategy_type,
                is_paper_trade, user_id,
                token1, token2, token3,
                token1_contract, token2_contract, token3_contract,
                protocol_A, protocol_B,
                entry_timestamp,
                deployment_usd, L_A, B_A, L_B, B_B,
                entry_lend_rate_1A, entry_borrow_rate_2A, entry_lend_rate_2B, entry_borrow_rate_3B,
                entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B,
                entry_collateral_ratio_1A, entry_collateral_ratio_2B,
                entry_liquidation_threshold_1A, entry_liquidation_threshold_2B,
                entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
                entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B,
                entry_borrow_weight_2A, entry_borrow_weight_3B,
                notes, wallet_address, transaction_hash_open, on_chain_position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            position_id, 'active', 'recursive_lending',
            is_paper_trade, user_id,
            token1, token2, token3,
            token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B,
            entry_timestamp_str,
            deployment_usd, L_A, B_A, L_B, B_B,
            entry_lend_rate_1A, entry_borrow_rate_2A, entry_lend_rate_2B, entry_borrow_rate_3B,
            entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B,
            entry_collateral_ratio_1A, entry_collateral_ratio_2B,
            entry_liquidation_threshold_1A, entry_liquidation_threshold_2B,
            entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
            entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B,
            entry_borrow_weight_2A, entry_borrow_weight_3B,
            notes, wallet_address, transaction_hash_open, on_chain_position_id
        ))

        self.conn.commit()

        return position_id

    def close_position(
        self,
        position_id: str,
        close_timestamp: int,
        close_reason: str,
        close_notes: Optional[str] = None,
        transaction_hash_close: Optional[str] = None
    ) -> None:
        """
        Close an active position and create final rebalance record.

        Args:
            position_id: UUID of position to close
            close_timestamp: Unix timestamp when position was closed (int)
            close_reason: Reason for closing (user, liquidation, rebalance, etc.)
            close_notes: Optional notes about closure
            transaction_hash_close: Optional transaction hash for closing (Phase 2)

        Raises:
            ValueError: If timestamp is missing or position not found
            TypeError: If timestamp is not int
        """
        if close_timestamp is None:
            raise ValueError("close_timestamp is required - cannot default to datetime.now()")

        if not isinstance(close_timestamp, int):
            raise TypeError(
                f"close_timestamp must be Unix seconds (int), got {type(close_timestamp).__name__}. "
                f"Use to_seconds() to convert."
            )

        # Get position to verify it exists and is active
        position = self.get_position_by_id(position_id)
        if position is None:
            raise ValueError(f"Position {position_id} not found")

        if position['status'] != 'active':
            raise ValueError(f"Position {position_id} is not active (status: {position['status']})")

        # Capture final snapshot and create rebalance record
        try:
            snapshot = self.capture_rebalance_snapshot(position, close_timestamp)
            self.create_rebalance_record(
                position_id,
                snapshot,
                rebalance_reason=f'position_closed:{close_reason}',
                rebalance_notes=close_notes
            )
        except Exception as e:
            # If rebalance record creation fails, log but don't block closure
            print(f"Warning: Failed to create final rebalance record: {e}")

        # Convert to datetime string for DB
        close_timestamp_str = to_datetime_str(close_timestamp)

        # Update position
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE positions
            SET status = 'closed',
                close_timestamp = ?,
                close_reason = ?,
                close_notes = ?,
                transaction_hash_close = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE position_id = ?
        """, (close_timestamp_str, close_reason, close_notes, transaction_hash_close, position_id))

        self.conn.commit()

    def delete_position(self, position_id: str) -> None:
        """
        Permanently delete a position from the database.

        Use with caution - this is irreversible. Prefer close_position()
        for normal position lifecycle management.

        Args:
            position_id: UUID of position to delete
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM positions
            WHERE position_id = ?
        """, (position_id,))

        self.conn.commit()

    def get_active_positions(self, live_timestamp: Optional[int] = None) -> pd.DataFrame:
        """
        Get all active positions, optionally filtered by timestamp.

        DESIGN PRINCIPLE: Always return timestamps as Unix seconds (int), not strings.
        Implements the "timestamp as current time" principle - when live_timestamp is provided,
        only returns positions where entry_timestamp <= live_timestamp.

        Args:
            live_timestamp: Optional Unix seconds timestamp representing "current time".
                           If provided, only returns positions where entry_timestamp <= live_timestamp.
                           If None, returns all active positions (backward compatible).

        Returns:
            DataFrame of active positions (may be empty if no positions match filter)
        """
        query = """
        SELECT *
        FROM positions
        WHERE status = 'active'
        ORDER BY entry_timestamp DESC
        """
        positions = pd.read_sql_query(query, self.conn)

        # Convert timestamps to Unix seconds (DESIGN_NOTES principle)
        # IMPORTANT: Use Int64 dtype to handle nulls without converting to float64
        def safe_to_seconds(value):
            """Safely convert value to Unix seconds, handling bytes and other edge cases."""
            if pd.isna(value):
                return pd.NA
            if isinstance(value, bytes):
                # Skip bytes data - likely corrupted, treat as missing
                return pd.NA
            try:
                return int(to_seconds(value))
            except Exception:
                # If conversion fails, treat as missing data
                return pd.NA

        if not positions.empty:
            if 'entry_timestamp' in positions.columns:
                positions['entry_timestamp'] = positions['entry_timestamp'].apply(safe_to_seconds)
                # Remove rows with invalid entry_timestamp (critical field)
                positions = positions[pd.notna(positions['entry_timestamp'])].copy()
                # Convert to int after filtering out NAs
                if not positions.empty:
                    positions['entry_timestamp'] = positions['entry_timestamp'].astype(int)

            if 'close_timestamp' in positions.columns:
                # Use Int64 (nullable integer) to prevent float64 conversion with NaN
                positions['close_timestamp'] = positions['close_timestamp'].apply(safe_to_seconds).astype('Int64')

            if 'last_rebalance_timestamp' in positions.columns:
                # Use Int64 (nullable integer) to prevent float64 conversion with NaN
                positions['last_rebalance_timestamp'] = positions['last_rebalance_timestamp'].apply(safe_to_seconds).astype('Int64')

            # Convert all numeric fields defensively (handle bytes/corrupted data)
            def safe_to_int_df(value, default=0):
                """Convert bytes, NaN, or string to int for DataFrame columns"""
                if pd.isna(value):
                    return default
                if isinstance(value, bytes):
                    try:
                        return int.from_bytes(value, byteorder='little')
                    except Exception:
                        return default
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return default

            def safe_to_float_df(value, default=0.0):
                """Convert bytes, NaN, or string to float for DataFrame columns"""
                if pd.isna(value):
                    return default
                if isinstance(value, bytes):
                    try:
                        return float(int.from_bytes(value, byteorder='little'))
                    except Exception:
                        return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default

            # Convert integer fields
            integer_fields = ['rebalance_count']
            for field in integer_fields:
                if field in positions.columns:
                    positions[field] = positions[field].apply(safe_to_int_df)

            # Convert float fields
            float_fields = [
                'deployment_usd', 'L_A', 'B_A', 'L_B', 'B_B',
                'entry_lend_rate_1A', 'entry_borrow_rate_2A', 'entry_lend_rate_2B', 'entry_borrow_rate_3B',
                'entry_price_1A', 'entry_price_2A', 'entry_price_2B', 'entry_price_3B',
                'entry_collateral_ratio_1A', 'entry_collateral_ratio_2B',
                'entry_liquidation_threshold_1A', 'entry_liquidation_threshold_2B',
                'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
                'entry_liquidation_distance', 'entry_max_size_usd',
                'entry_borrow_fee_2A', 'entry_borrow_fee_3B',
                'entry_borrow_weight_2A', 'entry_borrow_weight_3B',
                'accumulated_realised_pnl', 'expected_slippage_bps', 'actual_slippage_bps'
            ]
            for field in float_fields:
                if field in positions.columns:
                    positions[field] = positions[field].apply(safe_to_float_df)

        # Apply timestamp filter if provided (Python-level filtering after conversion)
        if live_timestamp is not None:
            if not isinstance(live_timestamp, int):
                raise TypeError(f"live_timestamp must be int (Unix seconds), got {type(live_timestamp).__name__}")

            if not positions.empty:
                # Filter: only include positions that existed at the selected timestamp
                positions = positions[positions['entry_timestamp'] <= live_timestamp].copy()

        return positions

    def get_position_by_id(self, position_id: str) -> Optional[pd.Series]:
        """Get position by ID with defensive bytes-to-numeric conversion"""
        query = """
        SELECT *
        FROM positions
        WHERE position_id = ?
        """
        result = pd.read_sql_query(query, self.conn, params=(position_id,))

        if result.empty:
            return None

        position = result.iloc[0].copy()

        # Helper function to safely convert bytes/corrupted data to int
        def safe_to_int(value, default=0):
            """Convert bytes, NaN, or string to int"""
            if pd.isna(value):
                return default
            if isinstance(value, bytes):
                try:
                    return int.from_bytes(value, byteorder='little')
                except Exception:
                    return default
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        # Helper function to safely convert bytes/corrupted data to float
        def safe_to_float(value, default=0.0):
            """Convert bytes, NaN, or string to float"""
            if pd.isna(value):
                return default
            if isinstance(value, bytes):
                try:
                    # Try interpreting as integer first, then convert to float
                    return float(int.from_bytes(value, byteorder='little'))
                except Exception:
                    return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        # Convert timestamps to Unix seconds
        position['entry_timestamp'] = int(to_seconds(position['entry_timestamp']))
        if pd.notna(position.get('close_timestamp')):
            position['close_timestamp'] = int(to_seconds(position['close_timestamp']))
        if pd.notna(position.get('last_rebalance_timestamp')):
            position['last_rebalance_timestamp'] = int(to_seconds(position['last_rebalance_timestamp']))

        # Convert all numeric fields (integer fields)
        integer_fields = ['rebalance_count']
        for field in integer_fields:
            if field in position:
                position[field] = safe_to_int(position[field])

        # Convert all numeric fields (float fields)
        float_fields = [
            'deployment_usd', 'L_A', 'B_A', 'L_B', 'B_B',
            'entry_lend_rate_1A', 'entry_borrow_rate_2A', 'entry_lend_rate_2B', 'entry_borrow_rate_3B',
            'entry_price_1A', 'entry_price_2A', 'entry_price_2B', 'entry_price_3B',
            'entry_collateral_ratio_1A', 'entry_collateral_ratio_2B',
            'entry_liquidation_threshold_1A', 'entry_liquidation_threshold_2B',
            'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
            'entry_liquidation_distance', 'entry_max_size_usd',
            'entry_borrow_fee_2A', 'entry_borrow_fee_3B',
            'entry_borrow_weight_2A', 'entry_borrow_weight_3B',
            'accumulated_realised_pnl', 'expected_slippage_bps', 'actual_slippage_bps'
        ]
        for field in float_fields:
            if field in position:
                position[field] = safe_to_float(position[field])

        return position

    # ==================== Valuation & PnL ====================

    def calculate_position_value(
        self,
        position: pd.Series,
        live_timestamp: int
    ) -> Dict:
        """
        Calculate current position value and PnL breakdown.

        Queries rates_snapshot directly for all historical rates and calculates:
        - LE(T): Total lend earnings
        - BC(T): Total borrow costs
        - FEES: One-time upfront fees
        - NET$$$: LE(T) - BC(T) - FEES
        - current_value: deployment_usd + NET$$$

        Uses forward-looking calculation: each timestamp's rates apply to
        the period [timestamp, next_timestamp).

        Args:
            position: Position record from database
            live_timestamp: Dashboard selected timestamp in Unix seconds (int)

        Returns:
            Dict with:
                - current_value: deployment + net_earnings
                - lend_earnings: LE(T) in $$$
                - borrow_costs: BC(T) in $$$
                - fees: Upfront fees in $$$
                - net_earnings: NET$$$ = LE(T) - BC(T) - FEES
                - holding_days: Actual holding period in days
                - periods_count: Number of time periods
        """
        # Input validation
        if not isinstance(live_timestamp, int):
            raise TypeError(f"live_timestamp must be int (Unix seconds), got {type(live_timestamp).__name__}")

        # Convert entry_timestamp from DB (string) to Unix seconds (int)
        entry_ts = to_seconds(position['entry_timestamp'])

        if live_timestamp < entry_ts:
            raise ValueError("live_timestamp cannot be before entry_timestamp")

        # Extract position parameters
        deployment = position['deployment_usd']
        L_A = position['L_A']
        B_A = position['B_A']
        L_B = position['L_B']
        B_B = position['B_B']
        entry_fee_2A = position.get('entry_borrow_fee_2A') or 0
        entry_fee_3B = position.get('entry_borrow_fee_3B') or 0

        # Position legs
        token1 = position['token1']
        token2 = position['token2']
        token3 = position['token3']
        protocol_A = position['protocol_A']
        protocol_B = position['protocol_B']

        # Calculate holding period
        total_seconds = live_timestamp - entry_ts
        holding_days = total_seconds / 86400

        if total_seconds == 0:
            return {
                'current_value': deployment,
                'lend_earnings': 0,
                'borrow_costs': 0,
                'fees': 0,
                'net_earnings': 0,
                'holding_days': 0,
                'periods_count': 0
            }

        # Query all unique timestamps from rates_snapshot
        entry_str = to_datetime_str(entry_ts)
        live_str = to_datetime_str(live_timestamp)

        query_timestamps = """
        SELECT DISTINCT timestamp
        FROM rates_snapshot
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC
        """
        timestamps_df = pd.read_sql_query(query_timestamps, self.conn, params=(entry_str, live_str))

        if timestamps_df.empty:
            raise ValueError(f"No rate data found between {entry_str} and {live_str}")

        # For each timestamp, get rates for all 4 legs
        rates_data = []
        for ts_str in timestamps_df['timestamp']:
            # Build query for all 4 legs (levered)
            leg_query = """
            SELECT protocol, token, lend_base_apr, lend_reward_apr,
                   borrow_base_apr, borrow_reward_apr
            FROM rates_snapshot
            WHERE timestamp = ?
              AND ((protocol = ? AND token = ?) OR
                   (protocol = ? AND token = ?) OR
                   (protocol = ? AND token = ?) OR
                   (protocol = ? AND token = ?))
            """
            params = (ts_str,
                     protocol_A, token1,
                     protocol_A, token2,
                     protocol_B, token2,
                     protocol_B, token3)

            leg_rates = pd.read_sql_query(leg_query, self.conn, params=params)

            rates_data.append({
                'timestamp': to_seconds(ts_str),
                'rates': leg_rates
            })

        # Helper to get rate
        def get_rate(df, protocol, token, rate_type):
            """Get total rate (base + reward) for a protocol/token/type"""
            row = df[(df['protocol'] == protocol) & (df['token'] == token)]
            if row.empty:
                return 0
            base = row[f'{rate_type}_base_apr'].iloc[0] or 0
            reward = row[f'{rate_type}_reward_apr'].iloc[0] or 0
            return base + reward

        # Calculate LE(T) - Total Lend Earnings
        lend_earnings = 0
        periods_count = 0

        for i in range(len(rates_data) - 1):
            current = rates_data[i]
            next_data = rates_data[i + 1]

            # Time delta in years
            time_delta_seconds = next_data['timestamp'] - current['timestamp']
            time_years = time_delta_seconds / (365 * 86400)

            # Get forward-looking rates from current timestamp
            current_rates = current['rates']
            lend_rate_1A = get_rate(current_rates, protocol_A, token1, 'lend')
            lend_rate_2B = get_rate(current_rates, protocol_B, token2, 'lend')

            # Lend earnings for this period
            period_lend = deployment * (L_A * lend_rate_1A + L_B * lend_rate_2B) * time_years
            lend_earnings += period_lend
            periods_count += 1

        # Calculate BC(T) - Total Borrow Costs
        borrow_costs = 0

        for i in range(len(rates_data) - 1):
            current = rates_data[i]
            next_data = rates_data[i + 1]

            time_delta_seconds = next_data['timestamp'] - current['timestamp']
            time_years = time_delta_seconds / (365 * 86400)

            current_rates = current['rates']
            borrow_rate_2A = get_rate(current_rates, protocol_A, token2, 'borrow')
            borrow_rate_3B = get_rate(current_rates, protocol_B, token3, 'borrow')

            # Borrow costs for this period
            period_borrow = deployment * (B_A * borrow_rate_2A + B_B * borrow_rate_3B) * time_years
            borrow_costs += period_borrow

        # Calculate FEES - One-Time Upfront Fees
        fees = deployment * (B_A * entry_fee_2A + B_B * entry_fee_3B)

        # Calculate NET$$$ and Current Value
        net_earnings = lend_earnings - borrow_costs - fees
        current_value = deployment + net_earnings

        return {
            'current_value': current_value,
            'lend_earnings': lend_earnings,
            'borrow_costs': borrow_costs,
            'fees': fees,
            'net_earnings': net_earnings,
            'holding_days': holding_days,
            'periods_count': periods_count
        }

    def calculate_realized_apr(self, position: pd.Series, live_timestamp: int) -> float:
        """
        Calculate realized APR = (NET$$$ / T × 365) / deployment_usd

        Simply calls calculate_position_value() and annualizes the result.

        Args:
            position: Position record from database
            live_timestamp: Dashboard selected timestamp in Unix seconds (int)

        Returns:
            Realized APR as decimal (e.g., 0.05 = 5%)
        """
        pv_result = self.calculate_position_value(position, live_timestamp)

        if pv_result['holding_days'] == 0:
            return 0

        # ANNUAL_NET_EARNINGS = NET$$$ / T × 365
        annual_net_earnings = pv_result['net_earnings'] / pv_result['holding_days'] * 365

        # Realized APR = ANNUAL_NET_EARNINGS / deployment_usd
        return annual_net_earnings / position['deployment_usd']

    # ==================== Rebalance Management ====================

    def rebalance_position(
        self,
        position_id: str,
        live_timestamp: int,
        rebalance_reason: str,
        rebalance_notes: Optional[str] = None
    ) -> str:
        """
        Rebalance a position: snapshot current state, create rebalance record, update position.

        IMPORTANT: Weightings (L_A, B_A, L_B, B_B) remain CONSTANT.
        Only token amounts change to restore $$$ amounts to match weightings.

        Args:
            position_id: UUID of position to rebalance
            live_timestamp: Unix timestamp when rebalancing (int)
            rebalance_reason: Reason for rebalance ('manual', 'liquidation_risk', etc.)
            rebalance_notes: Optional notes about rebalance

        Returns:
            rebalance_id: UUID of created rebalance record

        Raises:
            TypeError: If timestamp is not int
            ValueError: If position not found or already closed
        """
        # Validate timestamp
        if not isinstance(live_timestamp, int):
            raise TypeError(
                f"live_timestamp must be Unix seconds (int), got {type(live_timestamp).__name__}. "
                f"Use to_seconds() to convert."
            )

        # Get position
        position = self.get_position_by_id(position_id)
        if position is None:
            raise ValueError(f"Position {position_id} not found")

        if position['status'] != 'active':
            raise ValueError(f"Position {position_id} is not active (status: {position['status']})")

        # Capture snapshot of current state
        snapshot = self.capture_rebalance_snapshot(position, live_timestamp)

        # Create rebalance record
        rebalance_id = self.create_rebalance_record(
            position_id,
            snapshot,
            rebalance_reason,
            rebalance_notes
        )

        return rebalance_id

    def capture_rebalance_snapshot(
        self,
        position: pd.Series,
        live_timestamp: int
    ) -> Dict:
        """
        Capture current position state before rebalancing.

        DESIGN PRINCIPLES:
        - live_timestamp is Unix seconds (int), no defaults
        - Query by token_contract, not symbol
        - Rates stored as decimals (0.05 = 5%)
        - All timestamps in dict are Unix seconds (int)

        Returns:
            Dict with complete snapshot including realised PnL
        """
        # 1. Determine segment opening time
        if pd.notna(position.get('last_rebalance_timestamp')):
            opening_timestamp = to_seconds(position['last_rebalance_timestamp'])
        else:
            opening_timestamp = to_seconds(position['entry_timestamp'])

        # 2. Calculate realised PnL for entire position (all 4 legs)
        pv_result = self.calculate_position_value(position, live_timestamp)

        # 3. Query closing rates & prices from rates_snapshot
        closing_rates = self._query_rates_at_timestamp(position, live_timestamp)

        # 4. Calculate current token amounts for all 4 legs
        # Token amounts = (weight × deployment_usd) / price
        deployment = position['deployment_usd']
        L_A = position['L_A']
        B_A = position['B_A']
        L_B = position['L_B']
        B_B = position['B_B']

        # Entry token amounts (based on entry prices from position record)
        entry_token_amount_1A = (L_A * deployment) / position['entry_price_1A']
        entry_token_amount_2A = (B_A * deployment) / position['entry_price_2A']
        entry_token_amount_2B = (L_B * deployment) / position['entry_price_2B']
        entry_token_amount_3B = (B_B * deployment) / position['entry_price_3B']

        # Exit token amounts (token amounts don't change during rebalancing - only $$$ changes with price)
        # For rebalancing: token2 amounts will be adjusted to restore liq distance
        # For now, exit amounts = entry amounts (will be adjusted by rebalance logic)
        exit_token_amount_1A = entry_token_amount_1A  # No change for token1
        exit_token_amount_2A = entry_token_amount_2A  # Will be adjusted
        exit_token_amount_2B = entry_token_amount_2B  # Will be adjusted
        exit_token_amount_3B = entry_token_amount_3B  # No change for token3

        # 5. Calculate $$$ sizes
        entry_size_usd_1A = entry_token_amount_1A * position['entry_price_1A']
        entry_size_usd_2A = entry_token_amount_2A * position['entry_price_2A']
        entry_size_usd_2B = entry_token_amount_2B * position['entry_price_2B']
        entry_size_usd_3B = entry_token_amount_3B * position['entry_price_3B']

        exit_size_usd_1A = exit_token_amount_1A * closing_rates['price_1A']
        exit_size_usd_2A = exit_token_amount_2A * closing_rates['price_2A']
        exit_size_usd_2B = exit_token_amount_2B * closing_rates['price_2B']
        exit_size_usd_3B = exit_token_amount_3B * closing_rates['price_3B']

        # 6. Calculate liquidation prices and distances at time of rebalance
        # Use entry token amounts with closing prices
        calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])

        # Protocol A collateral and loan values (using entry token amounts and closing prices)
        closing_collateral_A = entry_token_amount_1A * closing_rates['price_1A']
        closing_loan_A = entry_token_amount_2A * closing_rates['price_2A']

        # Leg 1: Protocol A - Lend token1 (lending side)
        liq_result_1A = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_A,
            loan_value=closing_loan_A,
            lending_token_price=closing_rates['price_1A'],
            borrowing_token_price=closing_rates['price_2A'],
            lltv=position.get('entry_liquidation_threshold_1A', position['entry_collateral_ratio_1A']),
            side='lending',
            borrow_weight=position.get('entry_borrow_weight_2A', 1.0)
        )

        # Leg 2: Protocol A - Borrow token2 (borrowing side)
        liq_result_2A = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_A,
            loan_value=closing_loan_A,
            lending_token_price=closing_rates['price_1A'],
            borrowing_token_price=closing_rates['price_2A'],
            lltv=position.get('entry_liquidation_threshold_1A', position['entry_collateral_ratio_1A']),
            side='borrowing',
            borrow_weight=position.get('entry_borrow_weight_2A', 1.0)
        )

        # Protocol B collateral and loan values (using entry token amounts and closing prices)
        closing_collateral_B = entry_token_amount_2B * closing_rates['price_2B']
        closing_loan_B = entry_token_amount_3B * closing_rates['price_3B']

        # Leg 3: Protocol B - Lend token2 (lending side)
        liq_result_2B = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_B,
            loan_value=closing_loan_B,
            lending_token_price=closing_rates['price_2B'],
            borrowing_token_price=closing_rates['price_3B'],
            lltv=position.get('entry_liquidation_threshold_2B', position['entry_collateral_ratio_2B']),
            side='lending',
            borrow_weight=position.get('entry_borrow_weight_3B', 1.0)
        )

        # Leg 4: Protocol B - Borrow token3 (borrowing side)
        liq_result_3B = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_B,
            loan_value=closing_loan_B,
            lending_token_price=closing_rates['price_2B'],
            borrowing_token_price=closing_rates['price_3B'],
            lltv=position.get('entry_liquidation_threshold_2B', position['entry_collateral_ratio_2B']),
            side='borrowing',
            borrow_weight=position.get('entry_borrow_weight_3B', 1.0)
        )

        # 7. Determine rebalance actions
        entry_action_1A = "Initial deployment"
        entry_action_2A = "Initial deployment"
        entry_action_2B = "Initial deployment"
        entry_action_3B = "Initial deployment"

        exit_action_1A = self._determine_rebalance_action('1A', entry_token_amount_1A, exit_token_amount_1A, 'Lend')
        exit_action_2A = self._determine_rebalance_action('2A', entry_token_amount_2A, exit_token_amount_2A, 'Borrow')
        exit_action_2B = self._determine_rebalance_action('2B', entry_token_amount_2B, exit_token_amount_2B, 'Lend')
        exit_action_3B = self._determine_rebalance_action('3B', entry_token_amount_3B, exit_token_amount_3B, 'Borrow')

        return {
            'opening_timestamp': opening_timestamp,
            'closing_timestamp': live_timestamp,
            # Opening rates/prices from position record
            'opening_lend_rate_1A': position['entry_lend_rate_1A'],
            'opening_borrow_rate_2A': position['entry_borrow_rate_2A'],
            'opening_lend_rate_2B': position['entry_lend_rate_2B'],
            'opening_borrow_rate_3B': position['entry_borrow_rate_3B'],
            'opening_price_1A': position['entry_price_1A'],
            'opening_price_2A': position['entry_price_2A'],
            'opening_price_2B': position['entry_price_2B'],
            'opening_price_3B': position['entry_price_3B'],
            # Closing rates/prices from rates_snapshot
            'closing_lend_rate_1A': closing_rates['lend_rate_1A'],
            'closing_borrow_rate_2A': closing_rates['borrow_rate_2A'],
            'closing_lend_rate_2B': closing_rates['lend_rate_2B'],
            'closing_borrow_rate_3B': closing_rates['borrow_rate_3B'],
            'closing_price_1A': closing_rates['price_1A'],
            'closing_price_2A': closing_rates['price_2A'],
            'closing_price_2B': closing_rates['price_2B'],
            'closing_price_3B': closing_rates['price_3B'],
            # Liquidation prices at rebalance time (using entry token amounts + closing prices)
            'closing_liq_price_1A': liq_result_1A.get('liq_price'),
            'closing_liq_price_2A': liq_result_2A.get('liq_price'),
            'closing_liq_price_2B': liq_result_2B.get('liq_price'),
            'closing_liq_price_3B': liq_result_3B.get('liq_price'),
            # Liquidation distances at rebalance time
            'closing_liq_dist_1A': liq_result_1A.get('pct_distance'),
            'closing_liq_dist_2A': liq_result_2A.get('pct_distance'),
            'closing_liq_dist_2B': liq_result_2B.get('pct_distance'),
            'closing_liq_dist_3B': liq_result_3B.get('pct_distance'),
            # Collateral ratios
            'collateral_ratio_1A': position['entry_collateral_ratio_1A'],
            'collateral_ratio_2B': position['entry_collateral_ratio_2B'],
            # Liquidation thresholds
            'liquidation_threshold_1A': position['entry_liquidation_threshold_1A'],
            'liquidation_threshold_2B': position['entry_liquidation_threshold_2B'],
            # Token amounts
            'entry_token_amount_1A': entry_token_amount_1A,
            'entry_token_amount_2A': entry_token_amount_2A,
            'entry_token_amount_2B': entry_token_amount_2B,
            'entry_token_amount_3B': entry_token_amount_3B,
            'exit_token_amount_1A': exit_token_amount_1A,
            'exit_token_amount_2A': exit_token_amount_2A,
            'exit_token_amount_2B': exit_token_amount_2B,
            'exit_token_amount_3B': exit_token_amount_3B,
            # USD sizes
            'entry_size_usd_1A': entry_size_usd_1A,
            'entry_size_usd_2A': entry_size_usd_2A,
            'entry_size_usd_2B': entry_size_usd_2B,
            'entry_size_usd_3B': entry_size_usd_3B,
            'exit_size_usd_1A': exit_size_usd_1A,
            'exit_size_usd_2A': exit_size_usd_2A,
            'exit_size_usd_2B': exit_size_usd_2B,
            'exit_size_usd_3B': exit_size_usd_3B,
            # Actions
            'entry_action_1A': entry_action_1A,
            'entry_action_2A': entry_action_2A,
            'entry_action_2B': entry_action_2B,
            'entry_action_3B': entry_action_3B,
            'exit_action_1A': exit_action_1A,
            'exit_action_2A': exit_action_2A,
            'exit_action_2B': exit_action_2B,
            'exit_action_3B': exit_action_3B,
            # Realised PnL
            'realised_pnl': pv_result['net_earnings'],
            'realised_fees': pv_result['fees'],
            'realised_lend_earnings': pv_result['lend_earnings'],
            'realised_borrow_costs': pv_result['borrow_costs'],
            # Weightings (constant)
            'L_A': L_A,
            'B_A': B_A,
            'L_B': L_B,
            'B_B': B_B,
            'deployment_usd': deployment
        }

    def _query_rates_at_timestamp(
        self,
        position: pd.Series,
        timestamp: int
    ) -> Dict:
        """
        Query rates_snapshot for all 4 legs at given timestamp.

        DESIGN PRINCIPLE: Use token CONTRACT addresses for queries, not symbols.
        DESIGN PRINCIPLE: Use Unix timestamp (int), convert to datetime string for SQL.
        """
        # Convert timestamp to datetime string for query
        timestamp_str = to_datetime_str(timestamp)

        # Query rates for all 4 legs
        query = """
        SELECT protocol, token_contract, lend_base_apr, lend_reward_apr,
               borrow_base_apr, borrow_reward_apr, price_usd, collateral_ratio,
               liquidation_threshold, borrow_weight
        FROM rates_snapshot
        WHERE timestamp = ?
          AND ((protocol = ? AND token_contract = ?) OR
               (protocol = ? AND token_contract = ?) OR
               (protocol = ? AND token_contract = ?) OR
               (protocol = ? AND token_contract = ?))
        """
        params = (
            timestamp_str,
            position['protocol_A'], position['token1_contract'],
            position['protocol_A'], position['token2_contract'],
            position['protocol_B'], position['token2_contract'],
            position['protocol_B'], position['token3_contract']
        )

        rates_df = pd.read_sql_query(query, self.conn, params=params)

        # Extract rates for each leg
        def get_leg_data(protocol, token_contract):
            row = rates_df[
                (rates_df['protocol'] == protocol) &
                (rates_df['token_contract'] == token_contract)
            ]
            if row.empty:
                return {
                    'lend_rate': 0,
                    'borrow_rate': 0,
                    'price': 0,
                    'collateral_ratio': 0,
                    'liquidation_threshold': 0,
                    'borrow_weight': 1.0
                }
            row = row.iloc[0]
            return {
                'lend_rate': (row['lend_base_apr'] or 0) + (row['lend_reward_apr'] or 0),
                'borrow_rate': (row['borrow_base_apr'] or 0) + (row['borrow_reward_apr'] or 0),
                'price': row['price_usd'] or 0,
                'collateral_ratio': row['collateral_ratio'] or 0,
                'liquidation_threshold': row['liquidation_threshold'] or 0,
                'borrow_weight': row.get('borrow_weight', 1.0) or 1.0
            }

        leg_1A = get_leg_data(position['protocol_A'], position['token1_contract'])
        leg_2A = get_leg_data(position['protocol_A'], position['token2_contract'])
        leg_2B = get_leg_data(position['protocol_B'], position['token2_contract'])
        leg_3B = get_leg_data(position['protocol_B'], position['token3_contract'])

        return {
            'lend_rate_1A': leg_1A['lend_rate'],
            'borrow_rate_2A': leg_2A['borrow_rate'],
            'lend_rate_2B': leg_2B['lend_rate'],
            'borrow_rate_3B': leg_3B['borrow_rate'],
            'price_1A': leg_1A['price'],
            'price_2A': leg_2A['price'],
            'price_2B': leg_2B['price'],
            'price_3B': leg_3B['price'],
            'collateral_ratio_1A': leg_1A['collateral_ratio'],
            'collateral_ratio_2B': leg_2B['collateral_ratio'],
            'liquidation_threshold_1A': leg_1A['liquidation_threshold'],
            'liquidation_threshold_2B': leg_2B['liquidation_threshold'],
            'borrow_weight_2A': leg_2A['borrow_weight'],
            'borrow_weight_3B': leg_3B['borrow_weight']
        }

    def _determine_rebalance_action(
        self,
        leg: str,
        entry_token_amount: float,
        exit_token_amount: float,
        action_type: str
    ) -> str:
        """
        Determine action text for a specific leg.

        For token1 and token3 (1A, 3B): These don't change during rebalancing, return "No change"
        For token2 (2A, 2B): Calculate delta and determine action

        Returns: Action string (e.g., "Repay 100.0", "No change")
        """
        # Token1 and token3 don't change during rebalancing
        if leg in ['1A', '3B']:
            return "No change"

        # Token2 legs - calculate delta
        delta = exit_token_amount - entry_token_amount
        abs_delta = abs(delta)

        if abs_delta < 0.0001:  # Essentially no change
            return "No change"

        if delta > 0:
            # Increasing token amount
            if action_type == 'Lend':
                return f"Add {abs_delta:.4f}"
            else:  # Borrow
                return f"Borrow {abs_delta:.4f}"
        else:
            # Decreasing token amount
            if action_type == 'Lend':
                return f"Withdraw {abs_delta:.4f}"
            else:  # Borrow
                return f"Repay {abs_delta:.4f}"

    def create_rebalance_record(
        self,
        position_id: str,
        snapshot: Dict,
        rebalance_reason: str,
        rebalance_notes: Optional[str] = None
    ) -> str:
        """
        Insert rebalance record into position_rebalances table and update positions table.

        DESIGN PRINCIPLES:
        - Convert Unix seconds (int) to datetime strings using to_datetime_str() for DB insertion
        - Store rates as decimals (not percentages)
        - Weightings (L_A, B_A, L_B, B_B) remain CONSTANT
        """
        # Generate rebalance ID
        rebalance_id = str(uuid.uuid4())

        # Get current position to determine sequence number
        position = self.get_position_by_id(position_id)
        sequence_number = (position.get('rebalance_count') or 0) + 1

        # Convert timestamps to datetime strings for DB
        opening_timestamp_str = to_datetime_str(snapshot['opening_timestamp'])
        closing_timestamp_str = to_datetime_str(snapshot['closing_timestamp'])

        # Insert rebalance record
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO position_rebalances (
                rebalance_id, position_id, sequence_number,
                opening_timestamp, closing_timestamp,
                deployment_usd, L_A, B_A, L_B, B_B,
                opening_lend_rate_1A, opening_borrow_rate_2A, opening_lend_rate_2B, opening_borrow_rate_3B,
                opening_price_1A, opening_price_2A, opening_price_2B, opening_price_3B,
                closing_lend_rate_1A, closing_borrow_rate_2A, closing_lend_rate_2B, closing_borrow_rate_3B,
                closing_price_1A, closing_price_2A, closing_price_2B, closing_price_3B,
                closing_liq_price_1A, closing_liq_price_2A, closing_liq_price_2B, closing_liq_price_3B,
                closing_liq_dist_1A, closing_liq_dist_2A, closing_liq_dist_2B, closing_liq_dist_3B,
                collateral_ratio_1A, collateral_ratio_2B,
                liquidation_threshold_1A, liquidation_threshold_2B,
                entry_action_1A, entry_action_2A, entry_action_2B, entry_action_3B,
                exit_action_1A, exit_action_2A, exit_action_2B, exit_action_3B,
                entry_token_amount_1A, entry_token_amount_2A, entry_token_amount_2B, entry_token_amount_3B,
                exit_token_amount_1A, exit_token_amount_2A, exit_token_amount_2B, exit_token_amount_3B,
                entry_size_usd_1A, entry_size_usd_2A, entry_size_usd_2B, entry_size_usd_3B,
                exit_size_usd_1A, exit_size_usd_2A, exit_size_usd_2B, exit_size_usd_3B,
                realised_fees, realised_pnl, realised_lend_earnings, realised_borrow_costs,
                rebalance_reason, rebalance_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rebalance_id, position_id, sequence_number,
            opening_timestamp_str, closing_timestamp_str,
            snapshot['deployment_usd'], snapshot['L_A'], snapshot['B_A'], snapshot['L_B'], snapshot['B_B'],
            snapshot['opening_lend_rate_1A'], snapshot['opening_borrow_rate_2A'],
            snapshot['opening_lend_rate_2B'], snapshot['opening_borrow_rate_3B'],
            snapshot['opening_price_1A'], snapshot['opening_price_2A'],
            snapshot['opening_price_2B'], snapshot['opening_price_3B'],
            snapshot['closing_lend_rate_1A'], snapshot['closing_borrow_rate_2A'],
            snapshot['closing_lend_rate_2B'], snapshot['closing_borrow_rate_3B'],
            snapshot['closing_price_1A'], snapshot['closing_price_2A'],
            snapshot['closing_price_2B'], snapshot['closing_price_3B'],
            snapshot['closing_liq_price_1A'], snapshot['closing_liq_price_2A'],
            snapshot['closing_liq_price_2B'], snapshot['closing_liq_price_3B'],
            snapshot['closing_liq_dist_1A'], snapshot['closing_liq_dist_2A'],
            snapshot['closing_liq_dist_2B'], snapshot['closing_liq_dist_3B'],
            snapshot['collateral_ratio_1A'], snapshot['collateral_ratio_2B'],
            snapshot['liquidation_threshold_1A'], snapshot['liquidation_threshold_2B'],
            snapshot['entry_action_1A'], snapshot['entry_action_2A'],
            snapshot['entry_action_2B'], snapshot['entry_action_3B'],
            snapshot['exit_action_1A'], snapshot['exit_action_2A'],
            snapshot['exit_action_2B'], snapshot['exit_action_3B'],
            snapshot['entry_token_amount_1A'], snapshot['entry_token_amount_2A'],
            snapshot['entry_token_amount_2B'], snapshot['entry_token_amount_3B'],
            snapshot['exit_token_amount_1A'], snapshot['exit_token_amount_2A'],
            snapshot['exit_token_amount_2B'], snapshot['exit_token_amount_3B'],
            snapshot['entry_size_usd_1A'], snapshot['entry_size_usd_2A'],
            snapshot['entry_size_usd_2B'], snapshot['entry_size_usd_3B'],
            snapshot['exit_size_usd_1A'], snapshot['exit_size_usd_2A'],
            snapshot['exit_size_usd_2B'], snapshot['exit_size_usd_3B'],
            snapshot['realised_fees'], snapshot['realised_pnl'],
            snapshot['realised_lend_earnings'], snapshot['realised_borrow_costs'],
            rebalance_reason, rebalance_notes
        ))

        # Update positions table
        current_accumulated_pnl = position.get('accumulated_realised_pnl') or 0
        cursor.execute("""
            UPDATE positions
            SET accumulated_realised_pnl = ?,
                rebalance_count = ?,
                last_rebalance_timestamp = ?,
                entry_lend_rate_1A = ?,
                entry_borrow_rate_2A = ?,
                entry_lend_rate_2B = ?,
                entry_borrow_rate_3B = ?,
                entry_price_1A = ?,
                entry_price_2A = ?,
                entry_price_2B = ?,
                entry_price_3B = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE position_id = ?
        """, (
            current_accumulated_pnl + snapshot['realised_pnl'],
            sequence_number,
            closing_timestamp_str,
            snapshot['closing_lend_rate_1A'],
            snapshot['closing_borrow_rate_2A'],
            snapshot['closing_lend_rate_2B'],
            snapshot['closing_borrow_rate_3B'],
            snapshot['closing_price_1A'],
            snapshot['closing_price_2A'],
            snapshot['closing_price_2B'],
            snapshot['closing_price_3B'],
            position_id
        ))

        self.conn.commit()

        return rebalance_id

    def get_rebalance_history(
        self,
        position_id: str
    ) -> pd.DataFrame:
        """
        Query all rebalance records for a position.

        Returns: DataFrame ordered by sequence_number ASC
        """
        query = """
        SELECT *
        FROM position_rebalances
        WHERE position_id = ?
        ORDER BY sequence_number ASC
        """
        rebalances = pd.read_sql_query(query, self.conn, params=(position_id,))

        return rebalances

    def get_position_state_at_timestamp(
        self,
        position_id: str,
        selected_timestamp: int
    ) -> Optional[Dict]:
        """
        Retrieve position state as it existed at a specific timestamp.

        Handles rebalanced positions by checking historical segments in position_rebalances table.
        Implements the "timestamp as current time" design principle for time-travel functionality.

        DESIGN PRINCIPLE: Timestamps are Unix seconds (int) internally.

        Args:
            position_id: Position ID to query
            selected_timestamp: Unix seconds timestamp representing "current time"

        Returns:
            Dictionary containing position state (L_A, B_A, L_B, B_B, rates, prices) as it
            existed at selected_timestamp. Returns None if position doesn't exist.

        Logic:
            - If position has never been rebalanced (rebalance_count == 0):
              Use current state from positions table
            - If position has been rebalanced:
              Query position_rebalances for segment covering selected_timestamp
              (opening_timestamp <= selected_timestamp < closing_timestamp)
            - If no segment matches: use current state from positions table
              (selected_timestamp is before first rebalance or at/after last rebalance)
        """
        # Get current position
        position = self.get_position_by_id(position_id)
        if position is None:
            return None

        # Check if position has been rebalanced
        # Note: get_position_by_id() already converts bytes to proper types
        rebalance_count = position.get('rebalance_count', 0)

        if pd.isna(rebalance_count) or rebalance_count == 0:
            # Never rebalanced - use current state from positions table
            return position.to_dict()

        # Query for historical segment covering selected_timestamp
        # Convert selected_timestamp to datetime string for DB query
        selected_timestamp_str = to_datetime_str(selected_timestamp)

        query = """
        SELECT *
        FROM position_rebalances
        WHERE position_id = ?
        AND opening_timestamp <= ?
        AND closing_timestamp > ?
        ORDER BY sequence_number DESC
        LIMIT 1
        """
        segments = pd.read_sql_query(
            query,
            self.conn,
            params=(position_id, selected_timestamp_str, selected_timestamp_str)
        )

        if not segments.empty:
            # Found historical segment - use its state
            segment = segments.iloc[0]

            # Build state dictionary combining segment data with position metadata
            state = {
                'position_id': position_id,
                'token1': position['token1'],
                'token2': position['token2'],
                'token3': position['token3'],
                'token1_contract': position['token1_contract'],
                'token2_contract': position['token2_contract'],
                'token3_contract': position['token3_contract'],
                'protocol_A': position['protocol_A'],
                'protocol_B': position['protocol_B'],
                'deployment_usd': segment['deployment_usd'],
                'L_A': segment['L_A'],
                'B_A': segment['B_A'],
                'L_B': segment['L_B'],
                'B_B': segment['B_B'],
                # Use opening rates/prices as the "current" state during this segment
                'entry_lend_rate_1A': segment['opening_lend_rate_1A'],
                'entry_borrow_rate_2A': segment['opening_borrow_rate_2A'],
                'entry_lend_rate_2B': segment['opening_lend_rate_2B'],
                'entry_borrow_rate_3B': segment['opening_borrow_rate_3B'],
                'entry_price_1A': segment['opening_price_1A'],
                'entry_price_2A': segment['opening_price_2A'],
                'entry_price_2B': segment['opening_price_2B'],
                'entry_price_3B': segment['opening_price_3B'],
                'entry_collateral_ratio_1A': segment['collateral_ratio_1A'],
                'entry_collateral_ratio_2B': segment['collateral_ratio_2B'],
                'entry_liquidation_threshold_1A': segment['liquidation_threshold_1A'],
                'entry_liquidation_threshold_2B': segment['liquidation_threshold_2B'],
                'entry_timestamp': to_seconds(segment['opening_timestamp']),
                'is_historical_segment': True,  # Flag to indicate this is from a segment
            }
            return state
        else:
            # No segment covers this timestamp - use current state from positions table
            # This occurs when:
            # - selected_timestamp is before first rebalance, OR
            # - selected_timestamp is at/after last rebalance
            state = position.to_dict()
            state['is_historical_segment'] = False
            return state

    def has_future_rebalances(
        self,
        position_id: str,
        selected_timestamp: int
    ) -> bool:
        """
        Check if position has any rebalances that occurred AFTER the selected timestamp.

        This prevents time-travel paradoxes: if viewing Wednesday but position was
        rebalanced on Thursday, user cannot rebalance at Wednesday (would break the timeline).

        DESIGN PRINCIPLE: Timestamps are Unix seconds (int) internally.

        Args:
            position_id: Position ID to check
            selected_timestamp: Unix seconds timestamp representing "current time"

        Returns:
            True if there are rebalances with opening_timestamp > selected_timestamp,
            False otherwise (safe to rebalance at selected_timestamp)
        """
        # Convert to datetime string for DB query
        selected_timestamp_str = to_datetime_str(selected_timestamp)

        query = """
        SELECT COUNT(*) as count
        FROM position_rebalances
        WHERE position_id = ?
        AND opening_timestamp > ?
        """
        result = pd.read_sql_query(
            query,
            self.conn,
            params=(position_id, selected_timestamp_str)
        )

        return result['count'].iloc[0] > 0 if not result.empty else False
