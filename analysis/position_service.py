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
                entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
                entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B,
                notes, wallet_address, transaction_hash_open, on_chain_position_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
            entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B,
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
        Close an active position

        Args:
            position_id: UUID of position to close
            close_timestamp: Unix timestamp when position was closed (int)
            close_reason: Reason for closing (user, liquidation, rebalance, etc.)
            close_notes: Optional notes about closure
            transaction_hash_close: Optional transaction hash for closing (Phase 2)

        Raises:
            ValueError: If timestamp is missing
            TypeError: If timestamp is not int
        """
        if close_timestamp is None:
            raise ValueError("close_timestamp is required - cannot default to datetime.now()")

        if not isinstance(close_timestamp, int):
            raise TypeError(
                f"close_timestamp must be Unix seconds (int), got {type(close_timestamp).__name__}. "
                f"Use to_seconds() to convert."
            )

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

    def get_active_positions(self) -> pd.DataFrame:
        """Get all active positions"""
        query = """
        SELECT *
        FROM positions
        WHERE status = 'active'
        ORDER BY entry_timestamp DESC
        """
        positions = pd.read_sql_query(query, self.conn)

        # Convert timestamps to Unix seconds
        if not positions.empty and 'entry_timestamp' in positions.columns:
            positions['entry_timestamp'] = positions['entry_timestamp'].apply(to_seconds)

        return positions

    def get_position_by_id(self, position_id: str) -> Optional[pd.Series]:
        """Get position by ID"""
        query = """
        SELECT *
        FROM positions
        WHERE position_id = ?
        """
        result = pd.read_sql_query(query, self.conn, params=(position_id,))

        if result.empty:
            return None

        position = result.iloc[0]

        # Convert timestamps to Unix seconds
        position['entry_timestamp'] = to_seconds(position['entry_timestamp'])
        if pd.notna(position.get('close_timestamp')):
            position['close_timestamp'] = to_seconds(position['close_timestamp'])

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

        if live_timestamp < position['entry_timestamp']:
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
        entry_ts = position['entry_timestamp']
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
