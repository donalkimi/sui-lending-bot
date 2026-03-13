import sqlite3
import uuid
import time
from typing import Callable, Dict, List, Optional, Tuple, Union
import pandas as pd
from datetime import datetime
import sys
import os

# PostgreSQL support
try:
    import psycopg2
    import psycopg2.extensions
except ImportError:
    psycopg2 = None

# SQLAlchemy support
try:
    from sqlalchemy import Engine
except ImportError:
    Engine = None

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.time_helpers import to_datetime_str, to_seconds
from analysis.position_calculator import PositionCalculator
from analysis.strategy_calculators import get_calculator
from config import settings


class PositionService:
    """
    Service for managing paper trading positions (Phase 1) and real capital positions (Phase 2).

    Key principles:
    - Event sourcing: positions table stores immutable entry state
    - Forward-looking calculations: rates at time T apply to period [T, T+1)
    - No datetime.now() - all timestamps must be explicitly provided
    - Timestamps in Unix seconds (int) internally
    """

    def __init__(self,
                 conn: Union[sqlite3.Connection, 'psycopg2.extensions.connection'],
                 engine: Optional['Engine'] = None):
        """
        Initialize with database connection (SQLite or PostgreSQL).

        Args:
            conn: Raw database connection for cursor operations
            engine: SQLAlchemy engine for pandas operations (if None, will be created from config)
        """
        self.conn = conn
        self.engine = engine

        # If no engine provided, create one on-demand from config
        if self.engine is None:
            from dashboard.db_utils import get_db_engine
            self.engine = get_db_engine()

    def _get_placeholder(self):
        """Get SQL placeholder based on connection type"""
        if psycopg2 and isinstance(self.conn, psycopg2.extensions.connection):
            return '%s'
        return '?'
    
    @staticmethod
    def _to_native_type(value):
        """
        Convert numpy types to native Python types for database insertion.
        PostgreSQL requires native Python types and will fail with numpy types.
        """
        import numpy as np
        
        if value is None or pd.isna(value):
            return None
        
        if isinstance(value, (np.integer, np.floating)):
            return value.item()
        elif isinstance(value, np.ndarray):
            return value.tolist()
        
        return value
    
    @staticmethod
    def _to_native_type(value):
        """
        Convert numpy types to native Python types for database insertion.
        
        PostgreSQL doesn't understand numpy types and will fail with errors like:
        'schema "np" does not exist' when it encounters np.float64(...) 
        
        Args:
            value: Any value that might be a numpy type
            
        Returns:
            Native Python type (int, float, str, etc.)
        """
        import numpy as np
        
        if value is None or pd.isna(value):
            return None
        
        # Convert numpy types to native Python types
        if isinstance(value, (np.integer, np.floating)):
            # Use .item() to convert numpy scalar to Python scalar
            return value.item()
        elif isinstance(value, np.ndarray):
            # Convert array to list (should not happen in our case, but handle it)
            return value.tolist()
        
        # Already a native type
        return value

    # ==================== Position Management ====================

    def create_position(
        self,
        strategy_row: pd.Series,
        positions: Dict,
        token1: str,
        token2: Optional[str],
        token3: Optional[str],
        token1_contract: str,
        token2_contract: Optional[str],
        token3_contract: Optional[str],
        protocol_a: str,
        protocol_b: str,
        deployment_usd: float,
        strategy_type: str,
        is_paper_trade: bool = True,
        execution_time: int = -1,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
        wallet_address: Optional[str] = None,
        transaction_hash_open: Optional[str] = None,
        on_chain_position_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        token4: Optional[str] = None,
        token4_contract: Optional[str] = None,
    ) -> str:
        """
        Create a new position (Phase 1: paper trade, Phase 2: real capital)

        Args:
            strategy_row: Strategy data with timestamp, rates, prices, APRs
            positions: Position multipliers (l_a, b_a, l_b, b_b)
            token1: First token symbol
            token2: Second token symbol
            token3: Third token symbol
            token1_contract: Token1 contract address
            token2_contract: Token2 contract address
            token3_contract: Token3 contract address
            protocol_a: First protocol name
            protocol_b: Second protocol name
            deployment_usd: USD amount to deploy
            strategy_type: Strategy type — required, no default (see config/settings.py for valid values)
            is_paper_trade: True for Phase 1 (paper), False for Phase 2 (real capital)
            execution_time: Unix timestamp when executed (-1 = pending execution)
            user_id: Optional user ID for multi-user support (Phase 2)
            notes: Optional user notes
            wallet_address: Optional wallet address (Phase 2)
            transaction_hash_open: Optional transaction hash for opening (Phase 2)
            on_chain_position_id: Optional on-chain position ID (Phase 2)
            portfolio_id: Optional portfolio UUID (None = standalone position, UUID = portfolio member)

        Returns:
            position_id: UUID of created position

        Raises:
            ValueError: If timestamp is missing
            TypeError: If timestamp is not int
        """
        if not strategy_type:
            raise ValueError("strategy_type is required — received empty string or None")

        # Validate timestamp - use to_seconds() to convert at boundary (pandas Series -> int)
        # This follows DESIGN_NOTES.md principle #5: convert at boundaries
        entry_timestamp_raw = strategy_row.get('timestamp')
        if entry_timestamp_raw is None:
            raise ValueError("strategy_row must contain 'timestamp' - cannot default to datetime.now()")

        # Convert to int (handles int, float, str, datetime)
        entry_timestamp = to_seconds(entry_timestamp_raw)

        # Generate position ID
        position_id = str(uuid.uuid4())

        # Extract multipliers
        l_a = positions['l_a']
        b_a = positions['b_a']
        L_B = positions['l_b']
        b_b = positions.get('b_b', 0) or 0

        # Extract entry rates (None for unused legs)
        entry_token1_rate = strategy_row.get('token1_rate')
        entry_token2_rate = strategy_row.get('token2_rate')   # None when B_A unused
        entry_token3_rate = strategy_row.get('token3_rate')   # None when L_B unused
        entry_token4_rate = strategy_row.get('token4_rate')   # None when B_B unused

        # Extract entry prices (None for unused legs)
        entry_token1_price = strategy_row.get('token1_price')
        entry_token2_price = strategy_row.get('token2_price')  # None when B_A unused
        entry_token3_price = strategy_row.get('token3_price')  # None when L_B unused
        entry_token4_price = strategy_row.get('token4_price')  # None when B_B unused

        # Extract entry collateral ratios
        entry_token1_collateral_ratio = strategy_row.get('token1_collateral_ratio')
        entry_token3_collateral_ratio = strategy_row.get('token3_collateral_ratio')

        # Extract entry liquidation thresholds
        entry_token1_liquidation_threshold = strategy_row.get('token1_liquidation_threshold')
        entry_token3_liquidation_threshold = strategy_row.get('token3_liquidation_threshold')

        # Extract entry strategy APRs (already fee-adjusted)
        entry_net_apr = strategy_row.get('net_apr', 0)
        entry_apr5 = strategy_row.get('apr5', 0)
        entry_apr30 = strategy_row.get('apr30', 0)
        entry_apr90 = strategy_row.get('apr90', 0)
        entry_days_to_breakeven = strategy_row.get('days_to_breakeven')
        entry_liquidation_distance = strategy_row['liquidation_distance']  # fail loud if missing
        if entry_liquidation_distance == float('inf'):
            entry_liquidation_distance = None  # no borrow leg → no liq risk → store NULL

        # Extract entry liquidity & fees (None for unused legs)
        entry_max_size_usd = strategy_row.get('max_size_usd')
        entry_token2_borrow_fee = strategy_row.get('token2_borrow_fee')
        entry_token4_borrow_fee = strategy_row.get('token4_borrow_fee')

        # Extract entry borrow weights (None for unused legs)
        entry_token2_borrow_weight = strategy_row.get('token2_borrow_weight')
        entry_token4_borrow_weight = strategy_row.get('token4_borrow_weight')

        # Calculate entry token amounts (universal leg convention)
        entry_token1_amount = (l_a * deployment_usd) / entry_token1_price if entry_token1_price else 0

        # B_A: None when b_a = 0 or price is unavailable
        entry_token2_amount = (b_a * deployment_usd) / entry_token2_price \
                              if (b_a > 0 and entry_token2_price) else None

        # L_B: all current strategies where L_B > 0 share the same token count as B_A
        # (recursive/noloop: same physical tokens; perp_borrowing: market-neutral count match)
        if L_B > 0:
            entry_token3_amount = entry_token2_amount
        else:
            entry_token3_amount = None  # L_B unused

        # B_B: perp_lending uses market-neutral count match; others normal calculation
        if b_b > 0:
            if strategy_type == 'perp_lending':
                entry_token4_amount = entry_token1_amount   # short perp = spot token count
            else:
                entry_token4_amount = (b_b * deployment_usd) / entry_token4_price \
                                      if entry_token4_price else None
        else:
            entry_token4_amount = None  # B_B unused

        # Calculate entry liquidation prices per leg using PositionCalculator
        # NULL when leg is unused (no borrow leg → no collateral liq price for lend leg)
        from analysis.position_calculator import PositionCalculator
        _calc = PositionCalculator(liquidation_distance=entry_liquidation_distance if entry_liquidation_distance is not None else 9191.0)

        _collateral_A = entry_token1_amount * entry_token1_price if entry_token1_amount and entry_token1_price else 0.0
        _loan_A = entry_token2_amount * entry_token2_price if entry_token2_amount and entry_token2_price else 0.0
        if _loan_A > 0:
            _lltv_A = entry_token1_liquidation_threshold or entry_token1_collateral_ratio
            _bw_A = entry_token2_borrow_weight or 1.0
            entry_liq_price_token1 = _calc.calculate_liquidation_price(
                collateral_value=_collateral_A, loan_value=_loan_A,
                lending_token_price=entry_token1_price, borrowing_token_price=entry_token2_price,
                lltv=_lltv_A, side='lending', borrow_weight=_bw_A
            ).get('liq_price')
            entry_liq_price_token2 = _calc.calculate_liquidation_price(
                collateral_value=_collateral_A, loan_value=_loan_A,
                lending_token_price=entry_token1_price, borrowing_token_price=entry_token2_price,
                lltv=_lltv_A, side='borrowing', borrow_weight=_bw_A
            ).get('liq_price')
        else:
            entry_liq_price_token1 = None
            entry_liq_price_token2 = None

        _collateral_B = entry_token3_amount * entry_token3_price if entry_token3_amount and entry_token3_price else 0.0
        _loan_B = entry_token4_amount * entry_token4_price if entry_token4_amount and entry_token4_price else 0.0
        _lltv_B = entry_token3_liquidation_threshold or entry_token3_collateral_ratio
        _bw_B = entry_token4_borrow_weight or 1.0

        if strategy_type in settings.PERP_BORROWING_STRATEGIES and entry_token3_price:
            # Long perp (token3): exchange-side liq when price falls
            entry_liq_price_token3 = _calc.calculate_liquidation_price(
                collateral_value=0, loan_value=0,
                lending_token_price=entry_token3_price, borrowing_token_price=0,
                lltv=0, side='long_perp'
            ).get('liq_price')
            entry_liq_price_token4 = None
        elif strategy_type in settings.PERP_LENDING_STRATEGIES and entry_token4_price:
            # Short perp (token4): exchange-side liq when price rises
            entry_liq_price_token4 = _calc.calculate_liquidation_price(
                collateral_value=0, loan_value=0,
                lending_token_price=entry_token4_price, borrowing_token_price=0,
                lltv=0, side='short_perp'
            ).get('liq_price')
            # token3 is a stablecoin lend leg — LLTV-based if pair is present
            if _collateral_B > 0 and _loan_B > 0 and _lltv_B:
                entry_liq_price_token3 = _calc.calculate_liquidation_price(
                    collateral_value=_collateral_B, loan_value=_loan_B,
                    lending_token_price=entry_token3_price, borrowing_token_price=entry_token4_price,
                    lltv=_lltv_B, side='lending', borrow_weight=_bw_B
                ).get('liq_price')
            else:
                entry_liq_price_token3 = None
        elif _collateral_B > 0 and _loan_B > 0:
            # Non-perp: standard LLTV-based liq for both legs
            entry_liq_price_token3 = _calc.calculate_liquidation_price(
                collateral_value=_collateral_B, loan_value=_loan_B,
                lending_token_price=entry_token3_price, borrowing_token_price=entry_token4_price,
                lltv=_lltv_B, side='lending', borrow_weight=_bw_B
            ).get('liq_price')
            entry_liq_price_token4 = _calc.calculate_liquidation_price(
                collateral_value=_collateral_B, loan_value=_loan_B,
                lending_token_price=entry_token3_price, borrowing_token_price=entry_token4_price,
                lltv=_lltv_B, side='borrowing', borrow_weight=_bw_B
            ).get('liq_price')
        else:
            entry_liq_price_token3 = None
            entry_liq_price_token4 = None

        # Convert timestamp to datetime string for DB
        entry_timestamp_str = to_datetime_str(entry_timestamp)

        # Insert position
        cursor = self.conn.cursor()
        ph = self._get_placeholder()
        placeholders = ', '.join([ph] * 58)  # 58 values

        try:
            cursor.execute(f"""
                INSERT INTO positions (
                    position_id, status, strategy_type,
                    is_paper_trade, user_id,
                    token1, token2, token3, token4,
                    token1_contract, token2_contract, token3_contract, token4_contract,
                    protocol_a, protocol_b,
                    entry_timestamp, execution_time,
                    deployment_usd, l_a, b_a, l_b, b_b,
                    entry_token1_rate, entry_token2_rate, entry_token3_rate, entry_token4_rate,
                    entry_token1_price, entry_token2_price, entry_token3_price, entry_token4_price,
                    entry_token1_amount, entry_token2_amount, entry_token3_amount, entry_token4_amount,
                    entry_liquidation_price_token1, entry_liquidation_price_token2,
                    entry_liquidation_price_token3, entry_liquidation_price_token4,
                    entry_token1_collateral_ratio, entry_token3_collateral_ratio,
                    entry_token1_liquidation_threshold, entry_token3_liquidation_threshold,
                    entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
                    entry_max_size_usd, entry_token2_borrow_fee, entry_token4_borrow_fee,
                    entry_token2_borrow_weight, entry_token4_borrow_weight,
                    notes, wallet_address, transaction_hash_open, on_chain_position_id,
                    portfolio_id
                ) VALUES ({placeholders})
            """, (
                position_id, 'active', strategy_type,
                is_paper_trade, user_id,
                token1, token2, token3, token4,
                token1_contract, token2_contract, token3_contract, token4_contract,
                protocol_a, protocol_b,
                entry_timestamp_str, execution_time,
                self._to_native_type(deployment_usd),
                self._to_native_type(l_a),
                self._to_native_type(b_a),
                self._to_native_type(L_B),
                self._to_native_type(b_b),
                self._to_native_type(entry_token1_rate),
                self._to_native_type(entry_token2_rate),
                self._to_native_type(entry_token3_rate),
                self._to_native_type(entry_token4_rate),
                self._to_native_type(entry_token1_price),
                self._to_native_type(entry_token2_price),
                self._to_native_type(entry_token3_price),
                self._to_native_type(entry_token4_price),
                self._to_native_type(entry_token1_amount),
                self._to_native_type(entry_token2_amount),
                self._to_native_type(entry_token3_amount),
                self._to_native_type(entry_token4_amount),
                self._to_native_type(entry_liq_price_token1),
                self._to_native_type(entry_liq_price_token2),
                self._to_native_type(entry_liq_price_token3),
                self._to_native_type(entry_liq_price_token4),
                self._to_native_type(entry_token1_collateral_ratio),
                self._to_native_type(entry_token3_collateral_ratio),
                self._to_native_type(entry_token1_liquidation_threshold),
                self._to_native_type(entry_token3_liquidation_threshold),
                self._to_native_type(entry_net_apr),
                self._to_native_type(entry_apr5),
                self._to_native_type(entry_apr30),
                self._to_native_type(entry_apr90),
                self._to_native_type(entry_days_to_breakeven),
                self._to_native_type(entry_liquidation_distance),
                self._to_native_type(entry_max_size_usd),
                self._to_native_type(entry_token2_borrow_fee),
                self._to_native_type(entry_token4_borrow_fee),
                self._to_native_type(entry_token2_borrow_weight),
                self._to_native_type(entry_token4_borrow_weight),
                notes, wallet_address, transaction_hash_open, on_chain_position_id,
                portfolio_id,
            ))

            self.conn.commit()

        except Exception as e:
            # Rollback on error (especially important for PostgreSQL)
            self.conn.rollback()
            raise Exception(f"Failed to create position: {e}")

        return position_id

    def mark_position_executed(self, position_id: str, execution_time: int = -1) -> None:
        """
        Mark a pending position as executed

        Args:
            position_id: Position UUID
            execution_time: Unix timestamp when executed (defaults to current time if -1)
        """
        # If -1 passed (or default), use current timestamp
        if execution_time == -1:
            execution_time = int(time.time())

        cursor = self.conn.cursor()
        ph = self._get_placeholder()
        cursor.execute(f"""
            UPDATE positions
            SET execution_time = {ph}, updated_at = CURRENT_TIMESTAMP
            WHERE position_id = {ph}
        """, (execution_time, position_id))
        self.conn.commit()

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

        TODO: Before marking closed, ensure a final position_statistics row is written
        so that token1-4_earnings, token1-4_rewards, and accumulated_realised_pnl are
        captured at close time (these no longer live on the positions table).

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
        ph = self._get_placeholder()
        cursor.execute(f"""
            UPDATE positions
            SET status = 'closed',
                close_timestamp = {ph},
                close_reason = {ph},
                close_notes = {ph},
                transaction_hash_close = {ph},
                updated_at = CURRENT_TIMESTAMP
            WHERE position_id = {ph}
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
        ph = self._get_placeholder()
        cursor.execute(f"""
            DELETE FROM positions
            WHERE position_id = {ph}
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
        positions = pd.read_sql_query(query, self.engine)

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
                'deployment_usd', 'l_a', 'b_a', 'l_b', 'b_b',
                'entry_token1_rate', 'entry_token2_rate', 'entry_token3_rate', 'entry_token4_rate',
                'entry_token1_price', 'entry_token2_price', 'entry_token3_price', 'entry_token4_price',
                'entry_token1_collateral_ratio', 'entry_token3_collateral_ratio',
                'entry_token1_liquidation_threshold', 'entry_token3_liquidation_threshold',
                'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
                'entry_liquidation_distance', 'entry_max_size_usd',
                'entry_token2_borrow_fee', 'entry_token4_borrow_fee',
                'entry_token2_borrow_weight', 'entry_token4_borrow_weight',
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
        ph = self._get_placeholder()
        query = f"""
        SELECT *
        FROM positions
        WHERE position_id = {ph}
        """
        result = pd.read_sql_query(query, self.engine, params=(position_id,))

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
            'deployment_usd', 'l_a', 'b_a', 'l_b', 'b_b',
            'entry_token1_rate', 'entry_token2_rate', 'entry_token3_rate', 'entry_token4_rate',
            'entry_token1_price', 'entry_token2_price', 'entry_token3_price', 'entry_token4_price',
            'entry_token1_collateral_ratio', 'entry_token3_collateral_ratio',
            'entry_token1_liquidation_threshold', 'entry_token3_liquidation_threshold',
            'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
            'entry_liquidation_distance', 'entry_max_size_usd',
            'entry_token2_borrow_fee', 'entry_token4_borrow_fee',
            'entry_token2_borrow_weight', 'entry_token4_borrow_weight',
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
        start_timestamp: int,
        end_timestamp: int,
        include_initial_fees: bool = True
    ) -> Dict:
        """
        Calculate position value and PnL breakdown between two timestamps.

        Queries rates_snapshot directly for all historical rates and calculates:
        - LE(T): Total lend earnings
        - BC(T): Total borrow costs
        - FEES: One-time upfront fees
        - NET$$$: LE(T) - BC(T) - FEES
        - current_value: deployment_usd + NET$$$

        Uses forward-looking calculation: each timestamp's rates apply to
        the period [timestamp, next_timestamp).

        Args:
            position: Position record from database (contains deployment_usd, l_a, b_a, l_b, b_b, etc.)
            start_timestamp: Unix seconds - start of period
            end_timestamp: Unix seconds - end of period

        Returns:
            Dict with:
                - current_value: deployment + net_earnings
                - lend_earnings: LE(T) in $$$
                - borrow_costs: BC(T) in $$$
                - fees: Upfront fees in $$$
                - net_earnings: NET$$$ = LE(T) - BC(T) - FEES
                - holding_days: Actual holding period in days
                - periods_count: Number of time periods

        Note: This allows calculating PnL for:
            - Entire position: (entry_timestamp, live_timestamp)
            - Rebalance segment: (rebalance_opening_timestamp, rebalance_closing_timestamp)
            - Any arbitrary period for analysis
        """
        # Input validation
        if not isinstance(start_timestamp, int):
            raise TypeError(f"start_timestamp must be int (Unix seconds), got {type(start_timestamp).__name__}")
        if not isinstance(end_timestamp, int):
            raise TypeError(f"end_timestamp must be int (Unix seconds), got {type(end_timestamp).__name__}")

        if end_timestamp < start_timestamp:
            raise ValueError(
                f"end_timestamp ({end_timestamp}) cannot be before start_timestamp ({start_timestamp}). "
                f"When viewing historical data, ensure calculation periods don't reference future events."
            )

        # Extract position parameters
        deployment = position['deployment_usd']
        l_a = position['l_a']
        b_a = position['b_a']
        L_B = position['l_b']
        b_b = position['b_b']
        entry_token2_borrow_fee = position.get('entry_token2_borrow_fee') or 0
        entry_token4_borrow_fee = position.get('entry_token4_borrow_fee') or 0

        # Position legs
        token1 = position['token1']
        token2 = position['token2']
        token3 = position['token3']
        protocol_a = position['protocol_a']
        protocol_b = position['protocol_b']

        # Calculate holding period
        total_seconds = end_timestamp - start_timestamp
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

        # Query all rates for all 4 legs across the full timestamp range in one query
        start_str = to_datetime_str(start_timestamp)
        end_str = to_datetime_str(end_timestamp)

        ph = self._get_placeholder()
        all_rates_query = f"""
        SELECT timestamp, protocol, token, lend_base_apr, lend_reward_apr,
               borrow_base_apr, borrow_reward_apr
        FROM rates_snapshot
        WHERE timestamp >= {ph} AND timestamp <= {ph}
          AND use_for_pnl = TRUE
          AND ((protocol = {ph} AND token = {ph}) OR
               (protocol = {ph} AND token = {ph}) OR
               (protocol = {ph} AND token = {ph}) OR
               (protocol = {ph} AND token = {ph}))
        ORDER BY timestamp ASC
        """
        params = (start_str, end_str,
                  protocol_a, token1,
                  protocol_a, token2,
                  protocol_b, token2,
                  protocol_b, token3)
        all_rates_df = pd.read_sql_query(all_rates_query, self.engine, params=params)

        if all_rates_df.empty:
            raise ValueError(f"No rate data found between {start_str} and {end_str}")

        rates_data = [
            {
                'timestamp': to_seconds(ts),
                'timestamp_str': ts,
                'rates': all_rates_df[all_rates_df['timestamp'] == ts].copy()
            }
            for ts in sorted(all_rates_df['timestamp'].unique())
        ]

        # Helper to get rate
        def get_rate(df, protocol, token, rate_type):
            """
            Get rate from dataframe, returning NaN if missing.

            Returns:
                Dict with:
                    - 'base': base APR (float or np.nan)
                    - 'reward': reward APR (float or np.nan)
                    - 'total': base + reward (float or np.nan if either is NaN)
            """
            import numpy as np

            row = df[(df['protocol'] == protocol) & (df['token'] == token)]

            if row.empty:
                # Protocol/token not found - return all NaN
                return {
                    'base': np.nan,
                    'reward': np.nan,
                    'total': np.nan
                }

            row = row.iloc[0]
            base = row[f'{rate_type}_base_apr']
            reward = row[f'{rate_type}_reward_apr']

            # Convert None to NaN for consistency
            if base is None:
                base = np.nan
            if reward is None:
                reward = np.nan

            # Calculate total (NaN if either component is NaN)
            if pd.isna(base) or pd.isna(reward):
                total = np.nan
            else:
                total = float(base) + float(reward)

            return {
                'base': float(base) if not pd.isna(base) else np.nan,
                'reward': float(reward) if not pd.isna(reward) else np.nan,
                'total': total
            }

        # Helper to forward-fill NaN rates
        def forward_fill_rates(rates_data_input):
            """
            Forward-fill NaN rates using previous valid rate.

            Logic: If rate at timestamp T_i is NaN, use rate from T_{i-1}.
            This follows forward-looking rate principle: previous rate continues to apply.

            Args:
                rates_data_input: List of dicts with 'timestamp', 'timestamp_str', 'rates' (DataFrame)

            Returns:
                Same structure with NaN rates replaced by forward-filled values
                Adds 'forward_filled_flags' dict to each entry showing which rates were filled
            """
            import numpy as np

            # Track last valid rate for each leg
            last_valid_rates = {
                'lend_1a': {'base': None, 'reward': None},
                'borrow_2a': {'base': None, 'reward': None},
                'lend_2b': {'base': None, 'reward': None},
                'borrow_3b': {'base': None, 'reward': None}
            }

            for period_data in rates_data_input:
                rates_df = period_data['rates']
                forward_filled = {}

                # Process each leg
                for leg_key, (prot, tok, r_type) in [
                    ('lend_1a', (protocol_a, token1, 'lend')),
                    ('borrow_2a', (protocol_a, token2, 'borrow')),
                    ('lend_2b', (protocol_b, token2, 'lend')),
                    ('borrow_3b', (protocol_b, token3, 'borrow'))
                ]:
                    rate_dict = get_rate(rates_df, prot, tok, r_type)

                    # Check if NaN
                    if pd.isna(rate_dict['total']):
                        # Forward-fill from last valid rate
                        if last_valid_rates[leg_key]['base'] is not None:
                            rate_dict['base'] = last_valid_rates[leg_key]['base']
                            rate_dict['reward'] = last_valid_rates[leg_key]['reward']
                            rate_dict['total'] = rate_dict['base'] + rate_dict['reward']
                            forward_filled[leg_key] = True
                        else:
                            # No previous valid rate - use 0 as last resort
                            rate_dict['base'] = 0.0
                            rate_dict['reward'] = 0.0
                            rate_dict['total'] = 0.0
                            forward_filled[leg_key] = 'no_previous_rate'
                    else:
                        # Valid rate - update last valid
                        last_valid_rates[leg_key]['base'] = rate_dict['base']
                        last_valid_rates[leg_key]['reward'] = rate_dict['reward']
                        forward_filled[leg_key] = False

                    # Store rate back
                    period_data[f'rate_{leg_key}'] = rate_dict

                period_data['forward_filled_flags'] = forward_filled

            return rates_data_input

        # Apply forward-fill to handle NaN rates
        rates_data = forward_fill_rates(rates_data)
        missing_data_log = []

        # Calculate LE(T) - Total Lend Earnings
        lend_earnings = 0
        periods_count = 0

        for i in range(len(rates_data) - 1):
            current = rates_data[i]
            next_data = rates_data[i + 1]

            # Time delta in years
            time_delta_seconds = next_data['timestamp'] - current['timestamp']
            time_years = time_delta_seconds / (365 * 86400)

            # Use pre-filled rates from forward_fill_rates()
            rate_1a = current['rate_lend_1a']
            rate_2b = current['rate_lend_2b']

            # Lend earnings for this period (no NaN checks needed - already forward-filled)
            period_lend = deployment * (l_a * rate_1a['total'] + L_B * rate_2b['total']) * time_years
            lend_earnings += period_lend
            periods_count += 1

            # Track if this period used forward-filled rates
            if any(current['forward_filled_flags'].values()):
                missing_data_log.append({
                    'timestamp': current['timestamp_str'],
                    'forward_filled_legs': [k for k, v in current['forward_filled_flags'].items() if v]
                })

        # Calculate BC(T) - Total Borrow Costs
        borrow_costs = 0

        for i in range(len(rates_data) - 1):
            current = rates_data[i]
            next_data = rates_data[i + 1]

            time_delta_seconds = next_data['timestamp'] - current['timestamp']
            time_years = time_delta_seconds / (365 * 86400)

            # Use pre-filled rates from forward_fill_rates()
            rate_2a = current['rate_borrow_2a']
            rate_3b = current['rate_borrow_3b']

            # Borrow costs for this period (no NaN checks needed - already forward-filled)
            period_borrow = deployment * (b_a * rate_2a['total'] + b_b * rate_3b['total']) * time_years
            borrow_costs += period_borrow

        # Calculate FEES - One-Time Upfront Fees
        # For rebalance segments, fees are calculated separately based on token deltas
        if include_initial_fees:
            strategy_type = position.get('strategy_type', '')
            borrow_fees = deployment * (b_a * entry_token2_borrow_fee + b_b * entry_token4_borrow_fee)
            if strategy_type == 'perp_lending':
                perp_trading_fees = deployment * b_b * 2.0 * settings.BLUEFIN_TAKER_FEE
            elif strategy_type in ('perp_borrowing', 'perp_borrowing_recursive'):
                perp_trading_fees = deployment * L_B * 2.0 * settings.BLUEFIN_TAKER_FEE
            else:
                perp_trading_fees = 0.0
            fees = borrow_fees + perp_trading_fees
        else:
            fees = 0

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
            'periods_count': periods_count,
            # Data quality tracking
            'forward_filled_count': len(missing_data_log),
            'forward_filled_log': missing_data_log,
            'has_forward_filled_data': len(missing_data_log) > 0
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
        # Use last rebalance timestamp if available (for current segment APR only)
        if pd.notna(position.get('last_rebalance_timestamp')):
            start_ts = to_seconds(position['last_rebalance_timestamp'])
        else:
            start_ts = to_seconds(position['entry_timestamp'])
        pv_result = self.calculate_position_value(position, start_ts, live_timestamp)

        if pv_result['holding_days'] == 0:
            return 0

        # ANNUAL_NET_EARNINGS = NET$$$ / T × 365
        annual_net_earnings = pv_result['net_earnings'] / pv_result['holding_days'] * 365

        # Realized APR = ANNUAL_NET_EARNINGS / deployment_usd
        return annual_net_earnings / position['deployment_usd']

    # ==================== Per-Token Earnings Calculation ====================

    def calculate_leg_earnings_split(
        self,
        position: pd.Series,
        token: str,
        action: str,
        start_timestamp: int,
        end_timestamp: int
    ) -> Tuple[float, float]:
        """
        Calculate base and reward earnings for a single token slot over a time period.

        Args:
            position: Position record (universal convention: token1=L_A, token2=B_A,
                      token3=L_B, token4=B_B)
            token: Universal slot — 'token1', 'token2', 'token3', or 'token4'
            action: 'Lend' or 'LongPerp'  → selects lend_base_apr / lend_reward_apr
                    'Borrow' or 'ShortPerp' → selects borrow_base_apr / borrow_reward_apr
                    Perp funding rates are stored in the same lend/borrow apr columns.
            start_timestamp: Start of period (Unix seconds)
            end_timestamp: End of period (Unix seconds)

        Returns:
            Tuple of (base_amount, reward_amount) in USD.
            Returns (0.0, 0.0) for unused token slots (token_contract is None).
        """
        # Input validation
        if not isinstance(start_timestamp, int):
            raise TypeError(f"start_timestamp must be int (Unix seconds), got {type(start_timestamp).__name__}")
        if not isinstance(end_timestamp, int):
            raise TypeError(f"end_timestamp must be int (Unix seconds), got {type(end_timestamp).__name__}")

        if end_timestamp < start_timestamp:
            raise ValueError("end_timestamp cannot be before start_timestamp")

        # Derive lookup fields from universal token slot
        token_contract = position.get(f'{token}_contract')
        if token_contract is None:
            return 0.0, 0.0  # Unused slot — no contract means zero earnings

        token_amount_raw = position.get(f'entry_{token}_amount')
        if token_amount_raw is None or (isinstance(token_amount_raw, float) and pd.isna(token_amount_raw)):
            raise ValueError(
                f"Active token slot '{token}' (contract={token_contract!r}) has NULL entry amount. "
                f"Position data is incomplete."
            )
        token_amount = float(token_amount_raw)

        # Universal protocol convention: token1/token2 → protocol_a; token3/token4 → protocol_b
        protocol = position['protocol_a'] if token in ('token1', 'token2') else position['protocol_b']

        # Handle zero-duration period
        if end_timestamp == start_timestamp:
            return 0.0, 0.0

        # OPTIMIZATION: Batch load all rates for the entire segment at once
        start_str = to_datetime_str(start_timestamp)
        end_str = to_datetime_str(end_timestamp)

        ph = self._get_placeholder()

        # DESIGN PRINCIPLE: Use token_contract for lookups, not token symbol
        # LongPerp uses lend columns; ShortPerp uses borrow columns
        # (perp funding rates stored in same lend/borrow apr columns as lending rates)
        if action in ('Lend', 'LongPerp'):
            bulk_query = f"""
            SELECT timestamp, lend_base_apr, lend_reward_apr, price_usd
            FROM rates_snapshot
            WHERE timestamp >= {ph} AND timestamp <= {ph}
              AND use_for_pnl = TRUE
              AND protocol = {ph} AND token_contract = {ph}
            ORDER BY timestamp ASC
            """
        else:  # Borrow, ShortPerp
            bulk_query = f"""
            SELECT timestamp, borrow_base_apr, borrow_reward_apr, price_usd
            FROM rates_snapshot
            WHERE timestamp >= {ph} AND timestamp <= {ph}
              AND use_for_pnl = TRUE
              AND protocol = {ph} AND token_contract = {ph}
            ORDER BY timestamp ASC
            """

        # Execute ONCE - get all rates for this token's segment
        all_rates = pd.read_sql_query(bulk_query, self.engine,
                                      params=(start_str, end_str, protocol, token_contract))

        if all_rates.empty:
            return 0.0, 0.0

        # Create lookup dictionary for O(1) timestamp access
        rates_lookup = {}
        for _, row in all_rates.iterrows():
            ts = to_seconds(row['timestamp'])
            price_usd = row['price_usd']
            if action in ('Lend', 'LongPerp'):
                base_apr = row['lend_base_apr']
                reward_apr = row['lend_reward_apr']
            else:  # Borrow, ShortPerp
                base_apr = row['borrow_base_apr']
                reward_apr = row['borrow_reward_apr']

            rates_lookup[ts] = {
                'base_apr': float(base_apr) if base_apr is not None and pd.notna(base_apr) else 0.0,
                'reward_apr': float(reward_apr) if reward_apr is not None and pd.notna(reward_apr) else 0.0,
                'price_usd': float(price_usd) if price_usd is not None and pd.notna(price_usd) else 0.0
            }

        timestamps = sorted(rates_lookup.keys())

        if len(timestamps) < 2:
            return 0.0, 0.0

        base_total = 0.0
        reward_total = 0.0

        for i in range(len(timestamps) - 1):
            ts_current = timestamps[i]
            ts_next = timestamps[i + 1]
            period_years = (ts_next - ts_current) / (365.25 * 86400)

            rate_data = rates_lookup.get(ts_current, {'base_apr': 0.0, 'reward_apr': 0.0})
            base_apr = rate_data['base_apr']
            reward_apr = rate_data['reward_apr']
            price_usd = rate_data['price_usd']
            usd_value = token_amount * price_usd

            base_total += usd_value * base_apr * period_years
            reward_total += usd_value * reward_apr * period_years

        return base_total, reward_total

    # ==================== Basis PnL ====================

    def calculate_basis_pnl_at_timestamp(
        self, position: pd.Series, timestamp: int
    ) -> Optional[float]:
        """Calculate basis PnL using bid/ask prices from spot_perp_basis at timestamp."""
        strategy_type = position.get('strategy_type', '')
        if strategy_type not in settings.PERP_STRATEGIES:
            return None

        timestamp_str = to_datetime_str(timestamp)
        ph = self._get_placeholder()
        basis_query = f"""
            SELECT spot_contract, perp_bid, perp_ask, spot_bid, spot_ask
            FROM spot_perp_basis
            WHERE timestamp = {ph}
        """
        basis_df = pd.read_sql_query(basis_query, self.engine, params=(timestamp_str,))
        basis_lookup = {
            row['spot_contract']: {
                'perp_bid': row['perp_bid'],
                'perp_ask': row['perp_ask'],
                'spot_bid': row['spot_bid'],
                'spot_ask': row['spot_ask'],
            }
            for _, row in basis_df.iterrows()
        }

        def _get_basis(spot_contract):
            return basis_lookup.get(spot_contract)

        return PositionService.calculate_basis_pnl(position, _get_basis)

    @staticmethod
    def calculate_basis_pnl(
        position: pd.Series,
        get_basis: Callable
    ) -> Optional[float]:
        """
        Calculate unrealised basis PnL for perp strategies.

        Returns the dollar PnL from spot/perp price divergence since entry,
        or None if live prices are unavailable.

        Uses exit-side bid/ask prices from spot_perp_basis (via get_basis) to
        match the directional pricing used at entry.
        """
        strategy_type = position['strategy_type']

        if strategy_type == 'perp_lending':
            bd = get_basis(position['token1_contract'])
            if bd is None:
                return None
            live_spot_price = bd.get('spot_bid')   # exit: sell spot at bid
            live_perp_price = bd.get('perp_ask')   # exit: cover short at ask
            if live_spot_price is None or live_perp_price is None:
                return None
            spot_tokens      = float(position['entry_token1_amount'])
            perp_tokens      = float(position['entry_token4_amount'])
            entry_spot_price = float(position['entry_token1_price'])
            entry_perp_price = float(position['entry_token4_price'])
            return ((live_spot_price - entry_spot_price) * spot_tokens
                   - (live_perp_price - entry_perp_price) * perp_tokens)
        else:  # perp_borrowing / perp_borrowing_recursive
            bd = get_basis(position['token2_contract'])
            if bd is None:
                return None
            live_spot_price = bd.get('spot_ask')   # exit: buy spot to return at ask
            live_perp_price = bd.get('perp_bid')   # exit: close long at bid
            if live_spot_price is None or live_perp_price is None:
                return None
            spot_tokens      = float(position['entry_token2_amount'])
            perp_tokens      = float(position['entry_token3_amount'])
            entry_spot_price = float(position['entry_token2_price'])
            entry_perp_price = float(position['entry_token3_price'])
            return ((live_perp_price - entry_perp_price) * perp_tokens
                   - (live_spot_price - entry_spot_price) * spot_tokens)

    @staticmethod
    def compute_basis_adjusted_current_apr(
        position: pd.Series,
        stats: Dict,
    ) -> float:
        """
        Compute current_apr adjusted for unrealised basis PnL.

        basis_pnl / deployment_usd converts the one-time basis gain/loss to an
        APR adjustment (no time-scaling — same convention as basis_cost).

        Non-perp or zero basis_pnl: returns current_apr unchanged.
        """
        from config import settings

        if stats is None:
            return None  # no stats available yet — caller treats None as "N/A"

        current_apr = float(stats['current_apr'])

        strategy_type = position['strategy_type']
        if strategy_type not in settings.PERP_STRATEGIES:
            return current_apr

        deployment_usd = float(position['deployment_usd'])
        if deployment_usd <= 0:
            raise ValueError(
                f"Position {position['position_id']}: deployment_usd is {deployment_usd} — must be > 0."
            )

        basis_pnl = stats['basis_pnl']
        if basis_pnl is None or basis_pnl == 0:
            return current_apr

        return current_apr + basis_pnl / deployment_usd

    # ==================== Rebalance Management ====================

    def rebalance_position(
        self,
        position_id: str,
        live_timestamp: int,
        rebalance_reason: str,
        rebalance_notes: Optional[str] = None,
        force: bool = True
    ) -> Optional[str]:
        """
        Rebalance a position: snapshot current state, create rebalance record, update position.

        IMPORTANT: Weightings (l_a, b_a, L_B, b_b) remain CONSTANT.
        Only token amounts change to restore $$$ amounts to match weightings.

        Args:
            position_id: UUID of position to rebalance
            live_timestamp: Unix timestamp when rebalancing (int)
            rebalance_reason: Reason for rebalance ('manual', 'auto_rebalance_threshold_exceeded', etc.)
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

        # PHASE 6: Strategy-specific rebalance validation
        # Get calculator for this position's strategy type
        rebalance_result = None  # initialized here so it stays None if try block throws before assignment
        try:
            calculator = get_calculator(position['strategy_type'])

            # Query current rates and prices for validation
            live_rates_dict = self._query_rates_at_timestamp(position, live_timestamp)
            if live_rates_dict is None:
                raise ValueError(
                    f"No rate data found for timestamp {live_timestamp} — "
                    f"cannot compute rebalance amounts for position {position_id}"
                )

            # For perp strategies, also fetch actual AMM/orderbook bid-ask from spot_perp_basis.
            # _query_basis_at_timestamp always returns all 8 keys; non-relevant slots are None.
            live_basis_dict = self._query_basis_at_timestamp(position, live_timestamp)

            live_prices_dict = {
                'price_token1': live_rates_dict['price_token1'],
                'price_token2': live_rates_dict['price_token2'],
                'price_token3': live_rates_dict['price_token3'],
                'price_token4': live_rates_dict['price_token4'],
                'spot_price_token1_bid': live_basis_dict['spot_price_token1_bid'],
                'spot_price_token1_ask': live_basis_dict['spot_price_token1_ask'],
                'spot_price_token2_bid': live_basis_dict['spot_price_token2_bid'],
                'spot_price_token2_ask': live_basis_dict['spot_price_token2_ask'],
                'perp_price_token3_bid': live_basis_dict['perp_price_token3_bid'],
                'perp_price_token3_ask': live_basis_dict['perp_price_token3_ask'],
                'perp_price_token4_bid': live_basis_dict['perp_price_token4_bid'],
                'perp_price_token4_ask': live_basis_dict['perp_price_token4_ask'],
            }

            rebalance_result = calculator.calculate_rebalance_amounts(
                position=position.to_dict(),
                live_rates=live_rates_dict,
                live_prices=live_prices_dict,
                force=force
            )

            # FAIL LOUD: Ensure calculator never returns None
            if rebalance_result is None:
                raise ValueError(
                    f"Calculator returned None for position {position_id}! "
                    f"Strategy type: {position['strategy_type']}. "
                    "Calculators must return a dict, not None."
                )

            # Auto mode: return None if threshold not exceeded
            if not force and not rebalance_result.get('requires_rebalance', False):
                return None  # within threshold, no rebalance needed

            # Validate actions if rebalancing is needed
            if rebalance_result.get('requires_rebalance', False):
                actions = rebalance_result.get('actions', [])
                if not actions:
                    print(
                        f"[WARNING] Position {position_id} requires_rebalance=True but has no actions! "
                        "This may indicate a calculator bug."
                    )

        except (ValueError, KeyError) as e:
            # Calculator validation failed - log warning but proceed
            # (User explicitly requested rebalance, so we don't want to block it)
            print(f"[WARNING] Rebalance validation failed for position {position_id}: {e}")
            print(f"[WARNING] Proceeding with rebalance anyway (manual override)")
        except Exception as e:
            # Unexpected error - log and proceed
            print(f"[WARNING] Unexpected error in rebalance validation: {e}")
            print(f"[WARNING] Proceeding with rebalance anyway")

        # Capture snapshot of current state, passing exit amounts from the calculator.
        if rebalance_result is None:
            raise ValueError(
                f"Rebalance aborted for position {position_id}: "
                f"calculator did not run (rate/price data missing for timestamp {live_timestamp}?). "
                f"Check that rates_snapshot has data for this timestamp."
            )
        exit_amounts = rebalance_result
        snapshot = self.capture_rebalance_snapshot(
            position, live_timestamp,
            exit_token1_amount=exit_amounts.get('exit_token1_amount'),
            exit_token2_amount=exit_amounts.get('exit_token2_amount'),
            exit_token3_amount=exit_amounts.get('exit_token3_amount'),
            exit_token4_amount=exit_amounts.get('exit_token4_amount'),
            action_token1=exit_amounts.get('action_token1'),
            action_token2=exit_amounts.get('action_token2'),
            action_token3=exit_amounts.get('action_token3'),
            action_token4=exit_amounts.get('action_token4'),
        )

        # Compute per-leg earnings for this segment and add to snapshot.
        # Segment: opening_timestamp → live_timestamp.
        # Sign convention: lend slots +base, borrow slots -base; rewards always +reward.
        _st = position.get('strategy_type', '')
        _token3_action = 'LongPerp' if _st in settings.PERP_BORROWING_STRATEGIES else 'Lend'
        _token4_action = 'ShortPerp' if _st in settings.PERP_LENDING_STRATEGIES else 'Borrow'
        opening_ts = snapshot['opening_timestamp']
        try:
            base1, reward1 = self.calculate_leg_earnings_split(position, 'token1', 'Lend',       opening_ts, live_timestamp)
            base2, reward2 = self.calculate_leg_earnings_split(position, 'token2', 'Borrow',     opening_ts, live_timestamp)
            base3, reward3 = self.calculate_leg_earnings_split(position, 'token3', _token3_action, opening_ts, live_timestamp)
            base4, reward4 = self.calculate_leg_earnings_split(position, 'token4', _token4_action, opening_ts, live_timestamp)
            snapshot['token1_earnings'] =  base1
            snapshot['token1_rewards']  =  reward1
            snapshot['token2_earnings'] = -base2
            snapshot['token2_rewards']  =  reward2
            snapshot['token3_earnings'] =  base3
            snapshot['token3_rewards']  =  reward3
            snapshot['token4_earnings'] = -base4
            snapshot['token4_rewards']  =  reward4
        except Exception as _e:
            print(f"⚠️ [REBALANCE] Could not compute per-leg earnings for {position_id}: {_e}")
            # Continue — earnings will be NULL in the rebalance record

        # Create rebalance record
        rebalance_id = self.create_rebalance_record(
            position_id,
            snapshot,
            rebalance_reason,
            rebalance_notes
        )

        # Send Slack notification
        try:
            from alerts.slack_notifier import SlackNotifier
            notifier = SlackNotifier()
            notifier.alert_position_rebalanced(
                position_id=position['position_id'],
                token1=position['token1'],
                token2=position['token2'],
                token3=position.get('token4'),  # B_B = closing stablecoin for recursive_lending
                protocol_a=position['protocol_a'],
                protocol_b=position['protocol_b'],
                liq_dist_2a_before=snapshot.get('liq_dist_2a_before'),
                liq_dist_2a_after=snapshot['closing_token2_liq_dist'],
                liq_dist_2b_before=snapshot.get('liq_dist_2b_before'),
                liq_dist_2b_after=snapshot['closing_token3_liq_dist'],
                rebalance_timestamp=live_timestamp
            )
        except Exception as e:
            print(f"⚠️ Failed to send Slack notification for rebalance: {e}")
            # Continue - notification failure should not block rebalance

        return rebalance_id

    def capture_rebalance_snapshot(
        self,
        position: pd.Series,
        live_timestamp: int,
        exit_token1_amount: float = None,
        exit_token2_amount: float = None,
        exit_token3_amount: float = None,
        exit_token4_amount: float = None,
        action_token1: Optional[str] = None,
        action_token2: Optional[str] = None,
        action_token3: Optional[str] = None,
        action_token4: Optional[str] = None,
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
        is_rebalance_segment = pd.notna(position.get('last_rebalance_timestamp'))
        if is_rebalance_segment:
            opening_timestamp = to_seconds(position['last_rebalance_timestamp'])
        else:
            opening_timestamp = to_seconds(position['entry_timestamp'])

        # 2. Calculate realised PnL for entire position (all 4 legs)
        # Use opening_timestamp as start, live_timestamp as end
        # For rebalance segments, exclude initial fees (calculate separately based on deltas)
        pv_result = self.calculate_position_value(
            position,
            opening_timestamp,
            live_timestamp,
            include_initial_fees=not is_rebalance_segment
        )

        # 3. Query closing rates & prices from rates_snapshot
        closing_rates = self._query_rates_at_timestamp(position, live_timestamp)

        # 4. Token amounts for this segment
        # Read stored amounts directly — do NOT recalculate from (weight × D) / price.
        # positions.entry_token*_amount always holds the current segment's opening amounts:
        #   - Segment 1: set at position creation
        #   - Segment N+1: updated by create_rebalance_record to segment N's exit amounts
        deployment = position['deployment_usd']
        l_a = position['l_a']
        b_a = position['b_a']
        L_B = position['l_b']
        b_b = position['b_b']

        entry_token1_amount = position['entry_token1_amount']
        entry_token2_amount = position['entry_token2_amount']
        entry_token3_amount = position['entry_token3_amount']  # == token2 by design (matched at deployment)
        entry_token4_amount = position['entry_token4_amount']  # None when b_b = 0

        # Exit amounts from calculate_rebalance_amounts.
        # Use directly — do NOT fall back to entry amounts if None.
        # If None where a number is expected, fail loudly (Design Notes #15, #16).
        # exit_token4_amount=None is expected when b_b=0 (handled by downstream guards).

        # 5. Calculate $$$ sizes
        entry_token1_size_usd = entry_token1_amount * position['entry_token1_price']
        entry_token2_size_usd = (entry_token2_amount * position['entry_token2_price']) if entry_token2_amount is not None else None
        entry_token3_size_usd = (entry_token3_amount * position['entry_token3_price']) if entry_token3_amount is not None else None
        entry_token4_size_usd = (entry_token4_amount * position['entry_token4_price']) if entry_token4_amount is not None else None

        exit_token1_size_usd = exit_token1_amount * closing_rates['price_token1']
        exit_token2_size_usd = (exit_token2_amount * closing_rates['price_token2']) if exit_token2_amount is not None else None
        exit_token3_size_usd = (exit_token3_amount * closing_rates['price_token3']) if exit_token3_amount is not None else None
        exit_token4_size_usd = (exit_token4_amount * closing_rates['price_token4']) if exit_token4_amount is not None else None

        # 6. Calculate liquidation prices and distances at time of rebalance
        # Use entry token amounts with closing prices
        calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])

        # Protocol A collateral and loan values (using entry token amounts and closing prices)
        closing_collateral_A = entry_token1_amount * closing_rates['price_token1']
        closing_loan_A = entry_token2_amount * closing_rates['price_token2'] if entry_token2_amount and closing_rates.get('price_token2') else 0.0

        # Leg 1: Protocol A - Lend token1 (lending side)
        # Only calculate when Protocol A borrow leg exists (loan_value > 0 and token2 price > 0)
        _price_token2_closing = closing_rates.get('price_token2') or 0
        if closing_loan_A > 0 and _price_token2_closing > 0:
            liq_result_1a = calc.calculate_liquidation_price(
                collateral_value=closing_collateral_A,
                loan_value=closing_loan_A,
                lending_token_price=closing_rates['price_token1'],
                borrowing_token_price=_price_token2_closing,
                lltv=position.get('entry_token1_liquidation_threshold', position['entry_token1_collateral_ratio']),
                side='lending',
                borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
            )
            # Leg 2: Protocol A - Borrow token2 (borrowing side)
            liq_result_2a = calc.calculate_liquidation_price(
                collateral_value=closing_collateral_A,
                loan_value=closing_loan_A,
                lending_token_price=closing_rates['price_token1'],
                borrowing_token_price=_price_token2_closing,
                lltv=position.get('entry_token1_liquidation_threshold', position['entry_token1_collateral_ratio']),
                side='borrowing',
                borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
            )
        else:
            liq_result_1a = {'liq_price': None, 'pct_distance': None}
            liq_result_2a = {'liq_price': None, 'pct_distance': None}

        # Protocol B collateral and loan values (using entry token amounts and closing prices)
        # Only applicable when both B_B and L_B legs are active (e.g. recursive_lending).
        # perp_lending has b_b > 0 (short perp) but token3 is NULL — skip this block for perp strategies.
        if b_b > 0 and entry_token3_amount is not None:
            closing_collateral_B = entry_token3_amount * closing_rates['price_token3']
            closing_loan_B = entry_token4_amount * closing_rates['price_token4']

            # Leg 3: Protocol B - Lend token3 (lending side)
            liq_result_2b = calc.calculate_liquidation_price(
                collateral_value=closing_collateral_B,
                loan_value=closing_loan_B,
                lending_token_price=closing_rates['price_token3'],
                borrowing_token_price=closing_rates['price_token4'],
                lltv=position.get('entry_token3_liquidation_threshold', position['entry_token3_collateral_ratio']),
                side='lending',
                borrow_weight=position.get('entry_token4_borrow_weight', 1.0)
            )

            # Leg 4: Protocol B - Borrow token4 (borrowing side)
            liq_result_3b = calc.calculate_liquidation_price(
                collateral_value=closing_collateral_B,
                loan_value=closing_loan_B,
                lending_token_price=closing_rates['price_token3'],
                borrowing_token_price=closing_rates['price_token4'],
                lltv=position.get('entry_token3_liquidation_threshold', position['entry_token3_collateral_ratio']),
                side='borrowing',
                borrow_weight=position.get('entry_token4_borrow_weight', 1.0)
            )
        else:
            # No Protocol B borrow leg — check for perp long (token3)
            _snap_strategy = position.get('strategy_type', '')
            if _snap_strategy in settings.PERP_BORROWING_STRATEGIES and closing_rates.get('price_token3'):
                liq_result_2b = calc.calculate_liquidation_price(
                    collateral_value=0, loan_value=0,
                    lending_token_price=closing_rates['price_token3'], borrowing_token_price=0,
                    lltv=0, side='long_perp'
                )
            else:
                liq_result_2b = {'liq_price': None, 'pct_distance': None}
            liq_result_3b = {'liq_price': None, 'pct_distance': None}

        # 6b. Calculate "before" liquidation distances (at opening_timestamp with opening prices)
        # For Slack notification: show liquidation distances BEFORE rebalance
        # Use same token amounts but with opening prices
        opening_collateral_A = entry_token1_amount * position['entry_token1_price']
        opening_loan_A = entry_token2_amount * position['entry_token2_price'] if entry_token2_amount and position.get('entry_token2_price') else 0.0

        # Leg 2A: Protocol A - Borrow token2 (borrowing side) - BEFORE rebalance
        # Only calculate when Protocol A borrow leg exists
        _price_token2_entry = position.get('entry_token2_price') or 0
        if opening_loan_A > 0 and _price_token2_entry > 0:
            opening_liq_result_2a = calc.calculate_liquidation_price(
                collateral_value=opening_collateral_A,
                loan_value=opening_loan_A,
                lending_token_price=position['entry_token1_price'],
                borrowing_token_price=_price_token2_entry,
                lltv=position.get('entry_token1_liquidation_threshold', position['entry_token1_collateral_ratio']),
                side='borrowing',
                borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
            )
        else:
            opening_liq_result_2a = {'liq_price': None, 'pct_distance': None}

        # Protocol B "before" liq — only applicable when B_B leg is active
        if b_b > 0 and entry_token3_amount is not None:
            opening_collateral_B = entry_token3_amount * position['entry_token3_price']
            opening_loan_B = entry_token4_amount * position['entry_token4_price']

            # Leg 2B: Protocol B - Lend token3 (lending side) - BEFORE rebalance
            opening_liq_result_2b = calc.calculate_liquidation_price(
                collateral_value=opening_collateral_B,
                loan_value=opening_loan_B,
                lending_token_price=position['entry_token3_price'],
                borrowing_token_price=position['entry_token4_price'],
                lltv=position.get('entry_token3_liquidation_threshold', position['entry_token3_collateral_ratio']),
                side='lending',
                borrow_weight=position.get('entry_token4_borrow_weight', 1.0)
            )
        else:
            # No Protocol B borrow leg — check for perp long (token3)
            if _snap_strategy in settings.PERP_BORROWING_STRATEGIES and position.get('entry_token3_price'):
                opening_liq_result_2b = calc.calculate_liquidation_price(
                    collateral_value=0, loan_value=0,
                    lending_token_price=position['entry_token3_price'], borrowing_token_price=0,
                    lltv=0, side='long_perp'
                )
            else:
                opening_liq_result_2b = {'liq_price': None, 'pct_distance': None}

        # Store before/after liquidation distances for Slack notification
        liq_dist_2a_before = opening_liq_result_2a.get('pct_distance')
        liq_dist_2a_after = liq_result_2a.get('pct_distance')
        liq_dist_2b_before = opening_liq_result_2b.get('pct_distance')
        liq_dist_2b_after = liq_result_2b.get('pct_distance')

        # 7. Determine rebalance actions
        entry_action_token1 = "Initial deployment"
        entry_action_token2 = "Initial deployment"
        entry_action_token3 = "Initial deployment"
        entry_action_token4 = "Initial deployment"

        # Use calculator-provided action strings when available (correct for all legs/strategies).
        # Fall back to _determine_rebalance_action() only when not provided (e.g. close_position()).
        exit_action_token1 = action_token1 if action_token1 is not None else self._determine_rebalance_action('1a', entry_token1_amount, exit_token1_amount, 'Lend')
        exit_action_token2 = action_token2 if action_token2 is not None else self._determine_rebalance_action('2a', entry_token2_amount, exit_token2_amount, 'Borrow')
        exit_action_token3 = action_token3 if action_token3 is not None else self._determine_rebalance_action('2b', entry_token3_amount, exit_token3_amount, 'Lend')
        exit_action_token4 = action_token4 if action_token4 is not None else self._determine_rebalance_action('3b', entry_token4_amount, exit_token4_amount, 'Borrow')

        # 8. Calculate fees for rebalance segments
        # For first segment: pv_result already includes full initial fees
        # For rebalance segments: calculate fees on additional borrowing only
        if is_rebalance_segment:
            rebalance_fees = 0

            # Token2@A: Only pay fees on ADDITIONAL borrowing (currently token2 is the only rebalanced token)
            # entry_token2_amount = amount at START of this segment (from position's entry_token2_price)
            # exit_token2_amount = amount at END of this segment (same for now, will change after rebalance logic)
            # For now, token amounts don't change during the segment, so delta = 0
            # Fees will be calculated when actual rebalancing adjusts token amounts
            delta_borrow_2a = (exit_token2_amount - entry_token2_amount) if exit_token2_amount is not None and entry_token2_amount is not None else 0.0
            if delta_borrow_2a > 0:
                # Get entry fee from position record
                entry_fee_2a = position.get('entry_token2_borrow_fee', 0) or 0
                rebalance_fees += delta_borrow_2a * closing_rates['price_token2'] * entry_fee_2a

            # Token3@B: Not currently rebalanced, so no fees
            # If we rebalance token3 in the future, add similar logic here

            realised_fees = rebalance_fees
        else:
            # First segment: use fees from pv_result (full initial fees)
            realised_fees = pv_result['fees']

        return {
            'opening_timestamp': opening_timestamp,
            'closing_timestamp': live_timestamp,
            # Opening rates/prices from position record
            'opening_token1_rate': position['entry_token1_rate'],
            'opening_token2_rate': position['entry_token2_rate'],
            'opening_token3_rate': position['entry_token3_rate'],
            'opening_token4_rate': position['entry_token4_rate'],
            'opening_token1_price': position['entry_token1_price'],
            'opening_token2_price': position['entry_token2_price'],
            'opening_token3_price': position['entry_token3_price'],
            'opening_token4_price': position['entry_token4_price'],
            # Closing rates/prices from rates_snapshot
            'closing_token1_rate': closing_rates['token1_rate'],
            'closing_token2_rate': closing_rates['token2_rate'],
            'closing_token3_rate': closing_rates['token3_rate'],
            'closing_token4_rate': closing_rates['token4_rate'],
            'closing_token1_price': closing_rates['price_token1'],
            'closing_token2_price': closing_rates['price_token2'],
            'closing_token3_price': closing_rates['price_token3'],
            'closing_token4_price': closing_rates['price_token4'],
            # Liquidation prices at rebalance time (using entry token amounts + closing prices)
            'closing_token1_liq_price': liq_result_1a.get('liq_price'),
            'closing_token2_liq_price': liq_result_2a.get('liq_price'),
            'closing_token3_liq_price': liq_result_2b.get('liq_price'),
            'closing_token4_liq_price': liq_result_3b.get('liq_price'),
            # Liquidation distances at rebalance time (after)
            'closing_token1_liq_dist': liq_result_1a.get('pct_distance'),
            'closing_token2_liq_dist': liq_result_2a.get('pct_distance'),
            'closing_token3_liq_dist': liq_result_2b.get('pct_distance'),
            'closing_token4_liq_dist': liq_result_3b.get('pct_distance'),
            # Liquidation distances before rebalance (for Slack notification)
            'liq_dist_2a_before': liq_dist_2a_before,
            'liq_dist_2b_before': liq_dist_2b_before,
            # Collateral ratios
            'token1_collateral_ratio': position['entry_token1_collateral_ratio'],
            'token3_collateral_ratio': position['entry_token3_collateral_ratio'],
            # Liquidation thresholds
            'token1_liquidation_threshold': position['entry_token1_liquidation_threshold'],
            'token3_liquidation_threshold': position['entry_token3_liquidation_threshold'],
            # Token amounts
            'entry_token1_amount': entry_token1_amount,
            'entry_token2_amount': entry_token2_amount,
            'entry_token3_amount': entry_token3_amount,
            'entry_token4_amount': entry_token4_amount,
            'exit_token1_amount': exit_token1_amount,
            'exit_token2_amount': exit_token2_amount,
            'exit_token3_amount': exit_token3_amount,
            'exit_token4_amount': exit_token4_amount,
            # USD sizes
            'entry_token1_size_usd': entry_token1_size_usd,
            'entry_token2_size_usd': entry_token2_size_usd,
            'entry_token3_size_usd': entry_token3_size_usd,
            'entry_token4_size_usd': entry_token4_size_usd,
            'exit_token1_size_usd': exit_token1_size_usd,
            'exit_token2_size_usd': exit_token2_size_usd,
            'exit_token3_size_usd': exit_token3_size_usd,
            'exit_token4_size_usd': exit_token4_size_usd,
            # Actions
            'entry_action_token1': entry_action_token1,
            'entry_action_token2': entry_action_token2,
            'entry_action_token3': entry_action_token3,
            'entry_action_token4': entry_action_token4,
            'exit_action_token1': exit_action_token1,
            'exit_action_token2': exit_action_token2,
            'exit_action_token3': exit_action_token3,
            'exit_action_token4': exit_action_token4,
            # Realised PnL
            'realised_pnl': pv_result['net_earnings'] - pv_result['fees'] + realised_fees,  # Adjust for correct fees
            'realised_fees': realised_fees,
            'realised_lend_earnings': pv_result['lend_earnings'],
            'realised_borrow_costs': pv_result['borrow_costs'],
            # Weightings (constant)
            'l_a': l_a,
            'b_a': b_a,
            'l_b': L_B,
            'b_b': b_b,
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
        ph = self._get_placeholder()
        query = f"""
        SELECT protocol, token_contract, lend_base_apr, lend_reward_apr,
               borrow_base_apr, borrow_reward_apr, price_usd, collateral_ratio,
               liquidation_threshold, borrow_weight
        FROM rates_snapshot
        WHERE timestamp = {ph}
          AND ((protocol = {ph} AND token_contract = {ph}) OR
               (protocol = {ph} AND token_contract = {ph}) OR
               (protocol = {ph} AND token_contract = {ph}) OR
               (protocol = {ph} AND token_contract = {ph}))
        """
        params = (
            timestamp_str,
            position['protocol_a'], position['token1_contract'],   # token1 = L_A
            position['protocol_a'], position['token2_contract'],   # token2 = B_A
            position['protocol_b'], position['token3_contract'],   # token3 = L_B
            position['protocol_b'], position['token4_contract']    # token4 = B_B
        )

        rates_df = pd.read_sql_query(query, self.engine, params=params)

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

        leg_1a = get_leg_data(position['protocol_a'], position['token1_contract'])
        leg_2a = get_leg_data(position['protocol_a'], position['token2_contract'])
        leg_2b = get_leg_data(position['protocol_b'], position['token3_contract'])   # token3 = L_B
        leg_3b = get_leg_data(position['protocol_b'], position['token4_contract'])   # token4 = B_B

        return {
            'token1_rate': leg_1a['lend_rate'],
            'token2_rate': leg_2a['borrow_rate'],
            'token3_rate': leg_2b['lend_rate'],
            'token4_rate': leg_3b['borrow_rate'],
            'price_token1': leg_1a['price'],
            'price_token2': leg_2a['price'],
            'price_token3': leg_2b['price'],
            'price_token4': leg_3b['price'],
            'token1_collateral_ratio': leg_1a['collateral_ratio'],
            'token3_collateral_ratio': leg_2b['collateral_ratio'],
            'token1_liquidation_threshold': leg_1a['liquidation_threshold'],
            'token3_liquidation_threshold': leg_2b['liquidation_threshold'],
            'token2_borrow_weight': leg_2a['borrow_weight'],
            'token4_borrow_weight': leg_3b['borrow_weight']
        }

    def _query_basis_at_timestamp(
        self,
        position: pd.Series,
        timestamp: int
    ) -> Dict:
        """
        Query spot_perp_basis for the perp pair in this position at or before timestamp.

        Returns all bid/ask columns — caller picks the correct side based on trade direction:
            selling (Δ < 0) → use bid prices
            buying  (Δ > 0) → use ask prices

        Lookup key by strategy:
            perp_lending:                  spot_contract = token1_contract
            perp_borrowing / _recursive:   spot_contract = token2_contract

        Returns None if no row found or if called for a non-perp strategy.
        """
        strategy_type = position['strategy_type']

        if strategy_type in settings.PERP_LENDING_STRATEGIES:
            spot_contract = position['token1_contract']   # spot = token1 (B_B slot = token4)
        elif strategy_type in settings.PERP_BORROWING_STRATEGIES:
            spot_contract = position['token2_contract']   # spot = token2 (L_B slot = token3)
        else:
            return {
                'spot_price_token1_bid': None, 'spot_price_token1_ask': None,
                'spot_price_token2_bid': None, 'spot_price_token2_ask': None,
                'perp_price_token3_bid': None, 'perp_price_token3_ask': None,
                'perp_price_token4_bid': None, 'perp_price_token4_ask': None,
            }

        if not spot_contract:
            return None

        ph = self._get_placeholder()
        cursor = self.conn.cursor()
        cursor.execute(f"""
            SELECT spot_bid, spot_ask, perp_bid, perp_ask, basis_bid, basis_ask, basis_mid
            FROM spot_perp_basis
            WHERE spot_contract = {ph}
              AND timestamp <= {ph}
            ORDER BY timestamp DESC
            LIMIT 1
        """, (spot_contract, to_datetime_str(timestamp)))

        row = cursor.fetchone()

        # All 8 slots always present; only strategy-relevant ones are non-None.
        result = {
            'spot_price_token1_bid': None, 'spot_price_token1_ask': None,
            'spot_price_token2_bid': None, 'spot_price_token2_ask': None,
            'perp_price_token3_bid': None, 'perp_price_token3_ask': None,
            'perp_price_token4_bid': None, 'perp_price_token4_ask': None,
        }
        if row is None:
            return result

        spot_bid, spot_ask, perp_bid, perp_ask = row[0], row[1], row[2], row[3]

        if strategy_type in settings.PERP_LENDING_STRATEGIES:
            result['spot_price_token1_bid'] = spot_bid
            result['spot_price_token1_ask'] = spot_ask
            result['perp_price_token4_bid'] = perp_bid
            result['perp_price_token4_ask'] = perp_ask
        elif strategy_type in settings.PERP_BORROWING_STRATEGIES:
            result['spot_price_token2_bid'] = spot_bid
            result['spot_price_token2_ask'] = spot_ask
            result['perp_price_token3_bid'] = perp_bid
            result['perp_price_token3_ask'] = perp_ask

        return result

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
        if leg in ['1a', '3b']:
            return "No change"

        # Unused leg (e.g. token3 for perp_lending)
        if entry_token_amount is None and exit_token_amount is None:
            return None

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
        - Weightings (l_a, b_a, L_B, b_b) remain CONSTANT
        """
        # Generate rebalance ID
        rebalance_id = str(uuid.uuid4())

        # Get current position to determine sequence number
        position = self.get_position_by_id(position_id)
        sequence_number = (position.get('rebalance_count') or 0) + 1

        # Convert timestamps to datetime strings for DB.
        # closing_timestamp is NULL for the initial deployment record (segment still open).
        opening_timestamp_str = to_datetime_str(snapshot['opening_timestamp'])
        closing_timestamp_str = (
            to_datetime_str(snapshot['closing_timestamp'])
            if snapshot['closing_timestamp'] is not None
            else None
        )

        # Convert all numeric values to native Python types to avoid PostgreSQL errors
        # PostgreSQL doesn't understand numpy types (np.float64, etc.)
        def convert_value(key):
            """Get value from snapshot and convert numpy types to native Python types"""
            return self._to_native_type(snapshot.get(key))

        try:
            # Insert rebalance record
            cursor = self.conn.cursor()
            ph = self._get_placeholder()
            cursor.execute(f"""
                INSERT INTO position_rebalances (
                    rebalance_id, position_id, sequence_number, strategy_type,
                    opening_timestamp, closing_timestamp,
                    deployment_usd, l_a, b_a, l_b, b_b,
                    opening_token1_rate, opening_token2_rate, opening_token3_rate, opening_token4_rate,
                    opening_token1_price, opening_token2_price, opening_token3_price, opening_token4_price,
                    closing_token1_rate, closing_token2_rate, closing_token3_rate, closing_token4_rate,
                    closing_token1_price, closing_token2_price, closing_token3_price, closing_token4_price,
                    entry_liquidation_price_token1, entry_liquidation_price_token2,
                    entry_liquidation_price_token3, entry_liquidation_price_token4,
                    closing_token1_liq_price, closing_token2_liq_price, closing_token3_liq_price, closing_token4_liq_price,
                    closing_token1_liq_dist, closing_token2_liq_dist, closing_token3_liq_dist, closing_token4_liq_dist,
                    token1_collateral_ratio, token3_collateral_ratio,
                    token1_liquidation_threshold, token3_liquidation_threshold,
                    entry_action_token1, entry_action_token2, entry_action_token3, entry_action_token4,
                    exit_action_token1, exit_action_token2, exit_action_token3, exit_action_token4,
                    entry_token1_amount, entry_token2_amount, entry_token3_amount, entry_token4_amount,
                    exit_token1_amount, exit_token2_amount, exit_token3_amount, exit_token4_amount,
                    entry_token1_size_usd, entry_token2_size_usd, entry_token3_size_usd, entry_token4_size_usd,
                    exit_token1_size_usd, exit_token2_size_usd, exit_token3_size_usd, exit_token4_size_usd,
                    realised_fees, realised_pnl, realised_lend_earnings, realised_borrow_costs,
                    rebalance_reason, rebalance_notes,
                    token1_earnings, token1_rewards,
                    token2_earnings, token2_rewards,
                    token3_earnings, token3_rewards,
                    token4_earnings, token4_rewards
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """, (
                rebalance_id, position_id, sequence_number, position['strategy_type'],
                opening_timestamp_str, closing_timestamp_str,
                convert_value('deployment_usd'), convert_value('l_a'), convert_value('b_a'), convert_value('l_b'), convert_value('b_b'),
                convert_value('opening_token1_rate'), convert_value('opening_token2_rate'),
                convert_value('opening_token3_rate'), convert_value('opening_token4_rate'),
                convert_value('opening_token1_price'), convert_value('opening_token2_price'),
                convert_value('opening_token3_price'), convert_value('opening_token4_price'),
                convert_value('closing_token1_rate'), convert_value('closing_token2_rate'),
                convert_value('closing_token3_rate'), convert_value('closing_token4_rate'),
                convert_value('closing_token1_price'), convert_value('closing_token2_price'),
                convert_value('closing_token3_price'), convert_value('closing_token4_price'),
                self._to_native_type(position.get('entry_liquidation_price_token1')),
                self._to_native_type(position.get('entry_liquidation_price_token2')),
                self._to_native_type(position.get('entry_liquidation_price_token3')),
                self._to_native_type(position.get('entry_liquidation_price_token4')),
                convert_value('closing_token1_liq_price'), convert_value('closing_token2_liq_price'),
                convert_value('closing_token3_liq_price'), convert_value('closing_token4_liq_price'),
                convert_value('closing_token1_liq_dist'), convert_value('closing_token2_liq_dist'),
                convert_value('closing_token3_liq_dist'), convert_value('closing_token4_liq_dist'),
                convert_value('token1_collateral_ratio'), convert_value('token3_collateral_ratio'),
                convert_value('token1_liquidation_threshold'), convert_value('token3_liquidation_threshold'),
                snapshot.get('entry_action_token1'), snapshot.get('entry_action_token2'),
                snapshot.get('entry_action_token3'), snapshot.get('entry_action_token4'),
                snapshot.get('exit_action_token1'), snapshot.get('exit_action_token2'),
                snapshot.get('exit_action_token3'), snapshot.get('exit_action_token4'),
                convert_value('entry_token1_amount'), convert_value('entry_token2_amount'),
                convert_value('entry_token3_amount'), convert_value('entry_token4_amount'),
                convert_value('exit_token1_amount'), convert_value('exit_token2_amount'),
                convert_value('exit_token3_amount'), convert_value('exit_token4_amount'),
                convert_value('entry_token1_size_usd'), convert_value('entry_token2_size_usd'),
                convert_value('entry_token3_size_usd'), convert_value('entry_token4_size_usd'),
                convert_value('exit_token1_size_usd'), convert_value('exit_token2_size_usd'),
                convert_value('exit_token3_size_usd'), convert_value('exit_token4_size_usd'),
                convert_value('realised_fees'), convert_value('realised_pnl'),
                convert_value('realised_lend_earnings'), convert_value('realised_borrow_costs'),
                rebalance_reason, rebalance_notes,
                self._to_native_type(snapshot.get('token1_earnings')),
                self._to_native_type(snapshot.get('token1_rewards')),
                self._to_native_type(snapshot.get('token2_earnings')),
                self._to_native_type(snapshot.get('token2_rewards')),
                self._to_native_type(snapshot.get('token3_earnings')),
                self._to_native_type(snapshot.get('token3_rewards')),
                self._to_native_type(snapshot.get('token4_earnings')),
                self._to_native_type(snapshot.get('token4_rewards')),
                ))

            # Update positions table.
            # For a true rebalance (closing_timestamp set): advance the "current segment entry"
            # state to the closing values so the next live segment starts from them.
            # For the initial deployment record (closing_timestamp = None): only update
            # rebalance_count — the entry rates/prices were set at position creation and
            # must NOT be overwritten with NULL.
            ph = self._get_placeholder()
            if closing_timestamp_str is not None:
                # Recalculate entry liq prices for the new segment using exit amounts + closing prices
                from analysis.position_calculator import PositionCalculator as _PC
                _new_calc = _PC(liquidation_distance=position['entry_liquidation_distance'])

                _new_p1 = convert_value('closing_token1_price')
                _new_p2 = convert_value('closing_token2_price')
                _new_p3 = convert_value('closing_token3_price')
                _new_p4 = convert_value('closing_token4_price')
                _new_a1 = convert_value('exit_token1_amount')
                _new_a2 = convert_value('exit_token2_amount')
                _new_a3 = convert_value('exit_token3_amount')
                _new_a4 = convert_value('exit_token4_amount')

                _new_coll_A = _new_a1 * _new_p1 if _new_a1 and _new_p1 else 0.0
                _new_loan_A = _new_a2 * _new_p2 if _new_a2 and _new_p2 else 0.0
                _lltv_A = position.get('entry_token1_liquidation_threshold') or position.get('entry_token1_collateral_ratio')
                _bw_A = position.get('entry_token2_borrow_weight') or 1.0
                if _new_loan_A > 0 and _lltv_A:
                    _new_liq_p1 = _new_calc.calculate_liquidation_price(
                        collateral_value=_new_coll_A, loan_value=_new_loan_A,
                        lending_token_price=_new_p1, borrowing_token_price=_new_p2,
                        lltv=_lltv_A, side='lending', borrow_weight=_bw_A
                    ).get('liq_price')
                    _new_liq_p2 = _new_calc.calculate_liquidation_price(
                        collateral_value=_new_coll_A, loan_value=_new_loan_A,
                        lending_token_price=_new_p1, borrowing_token_price=_new_p2,
                        lltv=_lltv_A, side='borrowing', borrow_weight=_bw_A
                    ).get('liq_price')
                else:
                    _new_liq_p1 = None
                    _new_liq_p2 = None

                _new_coll_B = _new_a3 * _new_p3 if _new_a3 and _new_p3 else 0.0
                _new_loan_B = _new_a4 * _new_p4 if _new_a4 and _new_p4 else 0.0
                _lltv_B = position.get('entry_token3_liquidation_threshold') or position.get('entry_token3_collateral_ratio')
                _bw_B = position.get('entry_token4_borrow_weight') or 1.0
                _strategy_type = position.get('strategy_type', '')

                if _strategy_type in settings.PERP_BORROWING_STRATEGIES and _new_p3:
                    _new_liq_p3 = _new_calc.calculate_liquidation_price(
                        collateral_value=0, loan_value=0,
                        lending_token_price=_new_p3, borrowing_token_price=0,
                        lltv=0, side='long_perp'
                    ).get('liq_price')
                    _new_liq_p4 = None
                elif _strategy_type in settings.PERP_LENDING_STRATEGIES and _new_p4:
                    _new_liq_p4 = _new_calc.calculate_liquidation_price(
                        collateral_value=0, loan_value=0,
                        lending_token_price=_new_p4, borrowing_token_price=0,
                        lltv=0, side='short_perp'
                    ).get('liq_price')
                    if _new_coll_B > 0 and _new_loan_B > 0 and _lltv_B:
                        _new_liq_p3 = _new_calc.calculate_liquidation_price(
                            collateral_value=_new_coll_B, loan_value=_new_loan_B,
                            lending_token_price=_new_p3, borrowing_token_price=_new_p4,
                            lltv=_lltv_B, side='lending', borrow_weight=_bw_B
                        ).get('liq_price')
                    else:
                        _new_liq_p3 = None
                elif _new_coll_B > 0 and _new_loan_B > 0 and _lltv_B:
                    _new_liq_p3 = _new_calc.calculate_liquidation_price(
                        collateral_value=_new_coll_B, loan_value=_new_loan_B,
                        lending_token_price=_new_p3, borrowing_token_price=_new_p4,
                        lltv=_lltv_B, side='lending', borrow_weight=_bw_B
                    ).get('liq_price')
                    _new_liq_p4 = _new_calc.calculate_liquidation_price(
                        collateral_value=_new_coll_B, loan_value=_new_loan_B,
                        lending_token_price=_new_p3, borrowing_token_price=_new_p4,
                        lltv=_lltv_B, side='borrowing', borrow_weight=_bw_B
                    ).get('liq_price')
                else:
                    _new_liq_p3 = None
                    _new_liq_p4 = None

                cursor.execute(f"""
                    UPDATE positions
                    SET rebalance_count = {ph},
                        last_rebalance_timestamp = {ph},
                        entry_token1_rate = {ph},
                        entry_token2_rate = {ph},
                        entry_token3_rate = {ph},
                        entry_token4_rate = {ph},
                        entry_token1_price = {ph},
                        entry_token2_price = {ph},
                        entry_token3_price = {ph},
                        entry_token4_price = {ph},
                        entry_token1_amount = {ph},
                        entry_token2_amount = {ph},
                        entry_token3_amount = {ph},
                        entry_token4_amount = {ph},
                        entry_liquidation_price_token1 = {ph},
                        entry_liquidation_price_token2 = {ph},
                        entry_liquidation_price_token3 = {ph},
                        entry_liquidation_price_token4 = {ph},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE position_id = {ph}
                """, (
                    sequence_number,
                    closing_timestamp_str,
                    convert_value('closing_token1_rate'),
                    convert_value('closing_token2_rate'),
                    convert_value('closing_token3_rate'),
                    convert_value('closing_token4_rate'),
                    convert_value('closing_token1_price'),
                    convert_value('closing_token2_price'),
                    convert_value('closing_token3_price'),
                    convert_value('closing_token4_price'),
                    convert_value('exit_token1_amount'),
                    convert_value('exit_token2_amount'),
                    convert_value('exit_token3_amount'),
                    convert_value('exit_token4_amount'),
                    self._to_native_type(_new_liq_p1),
                    self._to_native_type(_new_liq_p2),
                    self._to_native_type(_new_liq_p3),
                    self._to_native_type(_new_liq_p4),
                    position_id
                ))
            else:
                # Initial deployment: only increment rebalance_count.
                cursor.execute(f"""
                    UPDATE positions
                    SET rebalance_count = {ph},
                        updated_at = CURRENT_TIMESTAMP
                    WHERE position_id = {ph}
                """, (sequence_number, position_id))

            self.conn.commit()

        except Exception as e:
            # Rollback on error (especially important for PostgreSQL)
            self.conn.rollback()
            raise Exception(f"Failed to create rebalance record: {e}")


        return rebalance_id

    def get_rebalance_history(
        self,
        position_id: str
    ) -> pd.DataFrame:
        """
        Query all rebalance records for a position.

        Returns: DataFrame ordered by sequence_number ASC
        """
        ph = self._get_placeholder()
        query = f"""
        SELECT *
        FROM position_rebalances
        WHERE position_id = {ph}
        ORDER BY sequence_number ASC
        """
        rebalances = pd.read_sql_query(query, self.engine, params=(position_id,))

        # DEFENSIVE CONVERSION: Convert bytes to proper numeric types
        # (SQLite sometimes stores DECIMAL fields as BLOB)
        if not rebalances.empty:
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

            # Integer fields
            integer_fields = ['sequence_number']

            # Float fields (DECIMAL in DB)
            float_fields = [
                'deployment_usd', 'l_a', 'b_a', 'l_b', 'b_b',
                'opening_token1_rate', 'opening_token2_rate', 'opening_token3_rate', 'opening_token4_rate',
                'opening_token1_price', 'opening_token2_price', 'opening_token3_price', 'opening_token4_price',
                'closing_token1_rate', 'closing_token2_rate', 'closing_token3_rate', 'closing_token4_rate',
                'closing_token1_price', 'closing_token2_price', 'closing_token3_price', 'closing_token4_price',
                'token1_collateral_ratio', 'token3_collateral_ratio',
                'token1_liquidation_threshold', 'token3_liquidation_threshold',
                'entry_token1_amount', 'entry_token2_amount', 'entry_token3_amount', 'entry_token4_amount',
                'exit_token1_amount', 'exit_token2_amount', 'exit_token3_amount', 'exit_token4_amount',
                'entry_token1_size_usd', 'entry_token2_size_usd', 'entry_token3_size_usd', 'entry_token4_size_usd',
                'exit_token1_size_usd', 'exit_token2_size_usd', 'exit_token3_size_usd', 'exit_token4_size_usd',
                'realised_fees', 'realised_pnl', 'realised_lend_earnings', 'realised_borrow_costs'
            ]

            # Apply conversions
            for col in integer_fields:
                if col in rebalances.columns:
                    rebalances[col] = rebalances[col].apply(safe_to_int)

            for col in float_fields:
                if col in rebalances.columns:
                    rebalances[col] = rebalances[col].apply(safe_to_float)

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
            Dictionary containing position state (l_a, b_a, l_b, b_b, rates, prices) as it
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

        ph = self._get_placeholder()
        query = f"""
        SELECT *
        FROM position_rebalances
        WHERE position_id = {ph}
        AND opening_timestamp <= {ph}
        AND closing_timestamp > {ph}
        ORDER BY sequence_number DESC
        LIMIT 1
        """
        segments = pd.read_sql_query(
            query,
            self.engine,
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
                'protocol_a': position['protocol_a'],
                'protocol_b': position['protocol_b'],
                'deployment_usd': segment['deployment_usd'],
                'l_a': segment['l_a'],
                'b_a': segment['b_a'],
                'l_b': segment['l_b'],
                'b_b': segment['b_b'],
                # Use opening rates/prices as the "current" state during this segment
                'entry_token1_rate': segment['opening_token1_rate'],
                'entry_token2_rate': segment['opening_token2_rate'],
                'entry_token3_rate': segment['opening_token3_rate'],
                'entry_token4_rate': segment['opening_token4_rate'],
                'entry_token1_price': segment['opening_token1_price'],
                'entry_token2_price': segment['opening_token2_price'],
                'entry_token3_price': segment['opening_token3_price'],
                'entry_token4_price': segment['opening_token4_price'],
                'entry_token1_collateral_ratio': segment['token1_collateral_ratio'],
                'entry_token3_collateral_ratio': segment['token3_collateral_ratio'],
                'entry_token1_liquidation_threshold': segment['token1_liquidation_threshold'],
                'entry_token3_liquidation_threshold': segment['token3_liquidation_threshold'],
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

        ph = self._get_placeholder()
        query = f"""
        SELECT COUNT(*) as count
        FROM position_rebalances
        WHERE position_id = {ph}
        AND opening_timestamp > {ph}
        """
        result = pd.read_sql_query(
            query,
            self.engine,
            params=(position_id, selected_timestamp_str)
        )

        return result['count'].iloc[0] > 0 if not result.empty else False

