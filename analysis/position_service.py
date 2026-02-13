import sqlite3
import uuid
import time
from typing import Dict, List, Optional, Tuple, Union
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
        token2: str,
        token3: Optional[str],
        token1_contract: str,
        token2_contract: str,
        token3_contract: Optional[str],
        protocol_a: str,
        protocol_b: str,
        deployment_usd: float,
        is_paper_trade: bool = True,
        execution_time: int = -1,
        user_id: Optional[str] = None,
        notes: Optional[str] = None,
        wallet_address: Optional[str] = None,
        transaction_hash_open: Optional[str] = None,
        on_chain_position_id: Optional[str] = None,
        portfolio_id: Optional[str] = None
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
        l_a = positions['l_a']
        b_a = positions['b_a']
        L_B = positions['l_b']
        b_b = positions.get('b_b')

        # Extract entry rates (already in decimal format: 0.0316 = 3.16%)
        entry_lend_rate_1a = strategy_row.get('lend_rate_1a', 0)
        entry_borrow_rate_2a = strategy_row.get('borrow_rate_2a', 0)
        entry_lend_rate_2b = strategy_row.get('lend_rate_2b', 0)
        entry_borrow_rate_3b = strategy_row.get('borrow_rate_3b', 0)

        # Extract entry prices (leg-level)
        entry_price_1a = strategy_row.get('P1_A', 0)
        entry_price_2a = strategy_row.get('P2_A', 0)
        entry_price_2b = strategy_row.get('P2_B', 0)
        entry_price_3b = strategy_row.get('P3_B')

        # Extract entry collateral ratios
        entry_collateral_ratio_1a = strategy_row.get('collateral_ratio_1a', 0)
        entry_collateral_ratio_2b = strategy_row.get('collateral_ratio_2b', 0)

        # Extract entry liquidation thresholds
        entry_liquidation_threshold_1a = strategy_row.get('liquidation_threshold_1a', 0)
        entry_liquidation_threshold_2b = strategy_row.get('liquidation_threshold_2b', 0)

        # Extract entry strategy APRs (already fee-adjusted)
        entry_net_apr = strategy_row.get('net_apr', 0)
        entry_apr5 = strategy_row.get('apr5', 0)
        entry_apr30 = strategy_row.get('apr30', 0)
        entry_apr90 = strategy_row.get('apr90', 0)
        entry_days_to_breakeven = strategy_row.get('days_to_breakeven')
        entry_liquidation_distance = strategy_row.get('liquidation_distance', 0)

        # Extract entry liquidity & fees
        entry_max_size_usd = strategy_row.get('max_size_usd')
        entry_borrow_fee_2a = strategy_row.get('borrow_fee_2a')
        entry_borrow_fee_3b = strategy_row.get('borrow_fee_3b')

        # Extract entry borrow weights (default 1.0)
        entry_borrow_weight_2a = strategy_row.get('borrow_weight_2a', 1.0)
        entry_borrow_weight_3b = strategy_row.get('borrow_weight_3b', 1.0)

        # Calculate entry token amounts: (weight * deployment) / price
        entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
        entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
        entry_token_amount_2b = (L_B * deployment_usd) / entry_price_2b if entry_price_2b > 0 else 0
        entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if b_b and entry_price_3b and entry_price_3b > 0 else 0

        # Convert timestamp to datetime string for DB
        entry_timestamp_str = to_datetime_str(entry_timestamp)

        # Insert position
        cursor = self.conn.cursor()
        ph = self._get_placeholder()
        placeholders = ', '.join([ph] * 52)  # 52 values (added portfolio_id + 4 token amounts)

        try:
            cursor.execute(f"""
                INSERT INTO positions (
                    position_id, status, strategy_type,
                    is_paper_trade, user_id,
                    token1, token2, token3,
                    token1_contract, token2_contract, token3_contract,
                    protocol_a, protocol_b,
                    entry_timestamp, execution_time,
                    deployment_usd, l_a, b_a, l_b, b_b,
                    entry_lend_rate_1a, entry_borrow_rate_2a, entry_lend_rate_2b, entry_borrow_rate_3b,
                    entry_price_1a, entry_price_2a, entry_price_2b, entry_price_3b,
                    entry_token_amount_1a, entry_token_amount_2a, entry_token_amount_2b, entry_token_amount_3b,
                    entry_collateral_ratio_1a, entry_collateral_ratio_2b,
                    entry_liquidation_threshold_1a, entry_liquidation_threshold_2b,
                    entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_days_to_breakeven, entry_liquidation_distance,
                    entry_max_size_usd, entry_borrow_fee_2a, entry_borrow_fee_3b,
                    entry_borrow_weight_2a, entry_borrow_weight_3b,
                    notes, wallet_address, transaction_hash_open, on_chain_position_id,
                    portfolio_id
                ) VALUES ({placeholders})
            """, (
                position_id, 'active', 'recursive_lending',
                is_paper_trade, user_id,
                token1, token2, token3,
                token1_contract, token2_contract, token3_contract,
                protocol_a, protocol_b,
                entry_timestamp_str, execution_time,
                self._to_native_type(deployment_usd),
                self._to_native_type(l_a),
                self._to_native_type(b_a),
                self._to_native_type(L_B),
                self._to_native_type(b_b),
                self._to_native_type(entry_lend_rate_1a),
                self._to_native_type(entry_borrow_rate_2a),
                self._to_native_type(entry_lend_rate_2b),
                self._to_native_type(entry_borrow_rate_3b),
                self._to_native_type(entry_price_1a),
                self._to_native_type(entry_price_2a),
                self._to_native_type(entry_price_2b),
                self._to_native_type(entry_price_3b),
                self._to_native_type(entry_token_amount_1a),
                self._to_native_type(entry_token_amount_2a),
                self._to_native_type(entry_token_amount_2b),
                self._to_native_type(entry_token_amount_3b),
                self._to_native_type(entry_collateral_ratio_1a),
                self._to_native_type(entry_collateral_ratio_2b),
                self._to_native_type(entry_liquidation_threshold_1a),
                self._to_native_type(entry_liquidation_threshold_2b),
                self._to_native_type(entry_net_apr),
                self._to_native_type(entry_apr5),
                self._to_native_type(entry_apr30),
                self._to_native_type(entry_apr90),
                self._to_native_type(entry_days_to_breakeven),
                self._to_native_type(entry_liquidation_distance),
                self._to_native_type(entry_max_size_usd),
                self._to_native_type(entry_borrow_fee_2a),
                self._to_native_type(entry_borrow_fee_3b),
                self._to_native_type(entry_borrow_weight_2a),
                self._to_native_type(entry_borrow_weight_3b),
                notes, wallet_address, transaction_hash_open, on_chain_position_id,
                portfolio_id
            ))

            self.conn.commit()

        except Exception as e:
            # Rollback on error (especially important for PostgreSQL)
            self.conn.rollback()
            raise Exception(f"Failed to create position: {e}")

        # Create initial rebalance record (sequence_number=1) for this position
        # This ensures all positions have baseline token amounts for liquidation calculations
        try:
            # Calculate entry token amounts: (weight * deployment) / price
            entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
            entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
            entry_token_amount_2b = (L_B * deployment_usd) / entry_price_2b if entry_price_2b > 0 else 0
            entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if b_b and entry_price_3b and entry_price_3b > 0 else 0

            # Calculate entry size USD: weight * deployment
            entry_size_usd_1a = l_a * deployment_usd
            entry_size_usd_2a = b_a * deployment_usd
            entry_size_usd_2b = L_B * deployment_usd
            entry_size_usd_3b = b_b * deployment_usd if b_b else 0

            # Build snapshot for initial deployment (rebalance with opening but no closing)
            initial_snapshot = {
                'opening_timestamp': entry_timestamp,  # Unix seconds (int)
                'closing_timestamp': None,  # Still open
                'deployment_usd': deployment_usd,
                'l_a': l_a,
                'b_a': b_a,
                'l_b': L_B,
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
            self.create_rebalance_record(
                position_id=position_id,
                snapshot=initial_snapshot,
                rebalance_reason='initial_deployment',
                rebalance_notes='Initial position deployment (sequence_number=1)'
            )

            print(f"[CREATE POSITION] Created initial rebalance record (sequence_number=1) for position {position_id[:8]}...")

        except Exception as e:
            # Log error but don't fail position creation
            # The position is already committed, just the rebalance record failed
            print(f"[CREATE POSITION] Warning: Failed to create initial rebalance record for position {position_id[:8]}...: {e}")
            import traceback
            traceback.print_exc()

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
                'entry_lend_rate_1a', 'entry_borrow_rate_2a', 'entry_lend_rate_2b', 'entry_borrow_rate_3b',
                'entry_price_1a', 'entry_price_2a', 'entry_price_2b', 'entry_price_3b',
                'entry_collateral_ratio_1a', 'entry_collateral_ratio_2b',
                'entry_liquidation_threshold_1a', 'entry_liquidation_threshold_2b',
                'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
                'entry_liquidation_distance', 'entry_max_size_usd',
                'entry_borrow_fee_2a', 'entry_borrow_fee_3b',
                'entry_borrow_weight_2a', 'entry_borrow_weight_3b',
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
            'entry_lend_rate_1a', 'entry_borrow_rate_2a', 'entry_lend_rate_2b', 'entry_borrow_rate_3b',
            'entry_price_1a', 'entry_price_2a', 'entry_price_2b', 'entry_price_3b',
            'entry_collateral_ratio_1a', 'entry_collateral_ratio_2b',
            'entry_liquidation_threshold_1a', 'entry_liquidation_threshold_2b',
            'entry_net_apr', 'entry_apr5', 'entry_apr30', 'entry_apr90', 'entry_days_to_breakeven',
            'entry_liquidation_distance', 'entry_max_size_usd',
            'entry_borrow_fee_2a', 'entry_borrow_fee_3b',
            'entry_borrow_weight_2a', 'entry_borrow_weight_3b',
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
        entry_fee_2a = position.get('entry_borrow_fee_2a') or 0
        entry_fee_3b = position.get('entry_borrow_fee_3b') or 0

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

        # Query all unique timestamps from rates_snapshot
        start_str = to_datetime_str(start_timestamp)
        end_str = to_datetime_str(end_timestamp)

        ph = self._get_placeholder()
        query_timestamps = f"""
        SELECT DISTINCT timestamp
        FROM rates_snapshot
        WHERE timestamp >= {ph} AND timestamp <= {ph}
          AND use_for_pnl = TRUE
        ORDER BY timestamp ASC
        """
        timestamps_df = pd.read_sql_query(query_timestamps, self.engine, params=(start_str, end_str))

        if timestamps_df.empty:
            raise ValueError(f"No rate data found between {start_str} and {end_str}")

        # For each timestamp, get rates for all 4 legs
        rates_data = []
        for ts_str in timestamps_df['timestamp']:
            # Build query for all 4 legs (levered)
            ph = self._get_placeholder()
            leg_query = f"""
            SELECT protocol, token, lend_base_apr, lend_reward_apr,
                   borrow_base_apr, borrow_reward_apr
            FROM rates_snapshot
            WHERE timestamp = {ph}
              AND use_for_pnl = TRUE
              AND ((protocol = {ph} AND token = {ph}) OR
                   (protocol = {ph} AND token = {ph}) OR
                   (protocol = {ph} AND token = {ph}) OR
                   (protocol = {ph} AND token = {ph}))
            """
            params = (ts_str,
                     protocol_a, token1,
                     protocol_a, token2,
                     protocol_b, token2,
                     protocol_b, token3)

            leg_rates = pd.read_sql_query(leg_query, self.engine, params=params)

            rates_data.append({
                'timestamp': to_seconds(ts_str),
                'timestamp_str': ts_str,
                'rates': leg_rates
            })

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

            for i, period_data in enumerate(rates_data_input):
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
            fees = deployment * (b_a * entry_fee_2a + b_b * entry_fee_3b)
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

    # ==================== Per-Leg Earnings Calculation ====================

    def _get_token_for_leg(self, position: pd.Series, leg: str) -> str:
        """Get token symbol for a specific leg."""
        leg_token_map = {
            '1a': 'token1',
            '2a': 'token2',
            '2b': 'token2',
            '3b': 'token3'
        }
        return position[leg_token_map[leg]]

    def _get_token_contract_for_leg(self, position: pd.Series, leg: str) -> str:
        """Get token contract address for a specific leg."""
        leg_token_contract_map = {
            '1a': 'token1_contract',
            '2a': 'token2_contract',
            '2b': 'token2_contract',
            '3b': 'token3_contract'
        }
        return position[leg_token_contract_map[leg]]

    def _get_protocol_for_leg(self, position: pd.Series, leg: str) -> str:
        """Get protocol for a specific leg."""
        leg_protocol_map = {
            '1a': 'protocol_a',
            '2a': 'protocol_a',
            '2b': 'protocol_b',
            '3b': 'protocol_b'
        }
        return position[leg_protocol_map[leg]]

    def _get_weight_for_leg(self, position: pd.Series, leg: str) -> float:
        """Get weight multiplier for a specific leg."""
        leg_weight_map = {
            '1a': 'l_a',
            '2a': 'b_a',
            '2b': 'l_b',
            '3b': 'b_b'
        }
        return position[leg_weight_map[leg]]
    
    def _get_token_amount_for_leg(self, position: pd.Series, leg: str) -> float:
        leg_token_amount_map = {
            '1a': 'entry_token_amount_1a',
            '2a': 'entry_token_amount_2a',
            '2b': 'entry_token_amount_2b',
            '3b': 'entry_token_amount_3b'
        }
        return float(position[leg_token_amount_map[leg]])

    def calculate_leg_earnings_split(
        self,
        position: pd.Series,
        leg: str,
        action: str,
        start_timestamp: int,
        end_timestamp: int
    ) -> Tuple[float, float]:
        """
        Calculate base and reward earnings for a single leg over a time period.

        Args:
            position: Position record with deployment_usd, weights, tokens, protocols
            leg: Leg identifier ('1a', '2a', '2b', '3b')
            action: 'Lend' or 'Borrow'
            start_timestamp: Start of period (Unix seconds)
            end_timestamp: End of period (Unix seconds)

        Returns:
            Tuple of (base_amount, reward_amount) in USD
            - For Lend legs: both positive (earnings)
            - For Borrow legs: base positive (cost), reward negative (reduces cost)
        """
        # Input validation
        if not isinstance(start_timestamp, int):
            raise TypeError(f"start_timestamp must be int (Unix seconds), got {type(start_timestamp).__name__}")
        if not isinstance(end_timestamp, int):
            raise TypeError(f"end_timestamp must be int (Unix seconds), got {type(end_timestamp).__name__}")

        if end_timestamp < start_timestamp:
            raise ValueError("end_timestamp cannot be before start_timestamp")

        # Extract leg parameters
        #print(f"position element in position_service.py / calculate_leg_earnings_split:")
        #print(position)
        #deployment = position['deployment_usd']
        token_contract = self._get_token_contract_for_leg(position, leg)
        protocol = self._get_protocol_for_leg(position, leg)
        #weight = self._get_weight_for_leg(position, leg)
        token_amount = self._get_token_amount_for_leg(position, leg)

        # Handle zero-duration period
        if end_timestamp == start_timestamp:
            return 0.0, 0.0

        # OPTIMIZATION: Batch load all rates for the entire segment at once
        # This replaces the N+1 query problem with a single bulk query
        start_str = to_datetime_str(start_timestamp)
        end_str = to_datetime_str(end_timestamp)

        ph = self._get_placeholder()

        # Single bulk query for all rates in the period
        # DESIGN PRINCIPLE: Use token_contract for lookups, not token symbol
        if action == 'Lend':
            bulk_query = f"""
            SELECT timestamp, lend_base_apr, lend_reward_apr, price_usd
            FROM rates_snapshot
            WHERE timestamp >= {ph} AND timestamp <= {ph}
              AND use_for_pnl = TRUE
              AND protocol = {ph} AND token_contract = {ph}
            ORDER BY timestamp ASC
            """
        else:  # Borrow
            bulk_query = f"""
            SELECT timestamp, borrow_base_apr, borrow_reward_apr, price_usd
            FROM rates_snapshot
            WHERE timestamp >= {ph} AND timestamp <= {ph}
              AND use_for_pnl = TRUE
              AND protocol = {ph} AND token_contract = {ph}
            ORDER BY timestamp ASC
            """

        # Execute ONCE - get all rates for this leg's segment
        all_rates = pd.read_sql_query(bulk_query, self.engine,
                                       params=(start_str, end_str, protocol, token_contract))

        if all_rates.empty:
            # No rate data available, return zeros
            return 0.0, 0.0

        # Create lookup dictionary for O(1) timestamp access
        rates_lookup = {}
        for _, row in all_rates.iterrows():
            ts = to_seconds(row['timestamp'])
            price_usd = row['price_usd']
            if action == 'Lend':
                base_apr = row['lend_base_apr']
                reward_apr = row['lend_reward_apr']
            else:  # Borrow
                base_apr = row['borrow_base_apr']
                reward_apr = row['borrow_reward_apr']

            # Handle None/NULL values defensively
            rates_lookup[ts] = {
                'base_apr': float(base_apr) if base_apr is not None and pd.notna(base_apr) else 0.0,
                'reward_apr': float(reward_apr) if reward_apr is not None and pd.notna(reward_apr) else 0.0,
                'price_usd': float(price_usd) if price_usd is not None and pd.notna(price_usd) else 0.0
            }

        # Get all timestamps for period calculation
        timestamps = sorted(rates_lookup.keys())

        if len(timestamps) < 2:
            # Need at least 2 timestamps to calculate a period
            return 0.0, 0.0

        base_total = 0.0
        reward_total = 0.0

        # Loop through periods - NO QUERIES in this loop (optimization)
        for i in range(len(timestamps) - 1):
            ts_current = timestamps[i]
            ts_next = timestamps[i + 1]
            period_years = (ts_next - ts_current) / (365.25 * 86400)

            # O(1) lookup - no database query
            rate_data = rates_lookup.get(ts_current, {'base_apr': 0.0, 'reward_apr': 0.0})
            base_apr = rate_data['base_apr']
            reward_apr = rate_data['reward_apr']
            price_usd = rate_data['price_usd']
            usd_value = token_amount * price_usd
            # Accumulate earnings
            if action == 'Lend':
                # Lend earnings are positive
                base_total += usd_value* base_apr * period_years
                reward_total += usd_value * reward_apr * period_years
            else:  # Borrow
                # Borrow costs are accumulated as positive
                base_total += usd_value * base_apr * period_years
                # Borrow rewards are earnings, accumulated as positive
                reward_total += usd_value * reward_apr * period_years

        return base_total, reward_total

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

        IMPORTANT: Weightings (l_a, b_a, L_B, b_b) remain CONSTANT.
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

        # Send Slack notification
        try:
            from alerts.slack_notifier import SlackNotifier
            notifier = SlackNotifier()
            notifier.alert_position_rebalanced(
                position_id=position['position_id'],
                token1=position['token1'],
                token2=position['token2'],
                token3=position['token3'],  # Always exists for recursive_lending
                protocol_a=position['protocol_a'],
                protocol_b=position['protocol_b'],
                liq_dist_2a_before=snapshot.get('liq_dist_2a_before'),
                liq_dist_2a_after=snapshot['closing_liq_dist_2a'],
                liq_dist_2b_before=snapshot.get('liq_dist_2b_before'),
                liq_dist_2b_after=snapshot['closing_liq_dist_2b'],
                rebalance_timestamp=live_timestamp
            )
        except Exception as e:
            print(f"⚠️ Failed to send Slack notification for rebalance: {e}")
            # Continue - notification failure should not block rebalance

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

        # 4. Calculate current token amounts for all 4 legs
        # Token amounts = (weight × deployment_usd) / price
        deployment = position['deployment_usd']
        l_a = position['l_a']
        b_a = position['b_a']
        L_B = position['l_b']
        b_b = position['b_b']

        # Entry token amounts (based on entry prices from position record)
        entry_token_amount_1a = (l_a * deployment) / position['entry_price_1a']
        entry_token_amount_2a = (b_a * deployment) / position['entry_price_2a']
        entry_token_amount_2b = entry_token_amount_2a  # Same tokens moved from A to B
        entry_token_amount_3b = (b_b * deployment) / position['entry_price_3b']

        # Exit token amounts (token amounts don't change during rebalancing - only $$$ changes with price)
        # For rebalancing: token2 amounts will be adjusted to restore liq distance
        # For now, exit amounts = entry amounts (will be adjusted by rebalance logic)
        exit_token_amount_1a = entry_token_amount_1a  # No change for token1
        exit_token_amount_2a = entry_token_amount_2a  # Will be adjusted
        exit_token_amount_2b = entry_token_amount_2b  # Will be adjusted
        exit_token_amount_3b = entry_token_amount_3b  # No change for token3

        # 5. Calculate $$$ sizes
        entry_size_usd_1a = entry_token_amount_1a * position['entry_price_1a']
        entry_size_usd_2a = entry_token_amount_2a * position['entry_price_2a']
        entry_size_usd_2b = entry_token_amount_2b * position['entry_price_2b']
        entry_size_usd_3b = entry_token_amount_3b * position['entry_price_3b']

        exit_size_usd_1a = exit_token_amount_1a * closing_rates['price_1a']
        exit_size_usd_2a = exit_token_amount_2a * closing_rates['price_2a']
        exit_size_usd_2b = exit_token_amount_2b * closing_rates['price_2b']
        exit_size_usd_3b = exit_token_amount_3b * closing_rates['price_3b']

        # 6. Calculate liquidation prices and distances at time of rebalance
        # Use entry token amounts with closing prices
        calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])

        # Protocol A collateral and loan values (using entry token amounts and closing prices)
        closing_collateral_A = entry_token_amount_1a * closing_rates['price_1a']
        closing_loan_A = entry_token_amount_2a * closing_rates['price_2a']

        # Leg 1: Protocol A - Lend token1 (lending side)
        liq_result_1a = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_A,
            loan_value=closing_loan_A,
            lending_token_price=closing_rates['price_1a'],
            borrowing_token_price=closing_rates['price_2a'],
            lltv=position.get('entry_liquidation_threshold_1a', position['entry_collateral_ratio_1a']),
            side='lending',
            borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
        )

        # Leg 2: Protocol A - Borrow token2 (borrowing side)
        liq_result_2a = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_A,
            loan_value=closing_loan_A,
            lending_token_price=closing_rates['price_1a'],
            borrowing_token_price=closing_rates['price_2a'],
            lltv=position.get('entry_liquidation_threshold_1a', position['entry_collateral_ratio_1a']),
            side='borrowing',
            borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
        )

        # Protocol B collateral and loan values (using entry token amounts and closing prices)
        closing_collateral_B = entry_token_amount_2b * closing_rates['price_2b']
        closing_loan_B = entry_token_amount_3b * closing_rates['price_3b']

        # Leg 3: Protocol B - Lend token2 (lending side)
        liq_result_2b = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_B,
            loan_value=closing_loan_B,
            lending_token_price=closing_rates['price_2b'],
            borrowing_token_price=closing_rates['price_3b'],
            lltv=position.get('entry_liquidation_threshold_2b', position['entry_collateral_ratio_2b']),
            side='lending',
            borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
        )

        # Leg 4: Protocol B - Borrow token3 (borrowing side)
        liq_result_3b = calc.calculate_liquidation_price(
            collateral_value=closing_collateral_B,
            loan_value=closing_loan_B,
            lending_token_price=closing_rates['price_2b'],
            borrowing_token_price=closing_rates['price_3b'],
            lltv=position.get('entry_liquidation_threshold_2b', position['entry_collateral_ratio_2b']),
            side='borrowing',
            borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
        )

        # 6b. Calculate "before" liquidation distances (at opening_timestamp with opening prices)
        # For Slack notification: show liquidation distances BEFORE rebalance
        # Use same token amounts but with opening prices
        opening_collateral_A = entry_token_amount_1a * position['entry_price_1a']
        opening_loan_A = entry_token_amount_2a * position['entry_price_2a']

        # Leg 2A: Protocol A - Borrow token2 (borrowing side) - BEFORE rebalance
        opening_liq_result_2a = calc.calculate_liquidation_price(
            collateral_value=opening_collateral_A,
            loan_value=opening_loan_A,
            lending_token_price=position['entry_price_1a'],
            borrowing_token_price=position['entry_price_2a'],
            lltv=position.get('entry_liquidation_threshold_1a', position['entry_collateral_ratio_1a']),
            side='borrowing',
            borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
        )

        # Protocol B collateral and loan values with opening prices
        opening_collateral_B = entry_token_amount_2b * position['entry_price_2b']
        opening_loan_B = entry_token_amount_3b * position['entry_price_3b']

        # Leg 2B: Protocol B - Lend token2 (lending side) - BEFORE rebalance
        opening_liq_result_2b = calc.calculate_liquidation_price(
            collateral_value=opening_collateral_B,
            loan_value=opening_loan_B,
            lending_token_price=position['entry_price_2b'],
            borrowing_token_price=position['entry_price_3b'],
            lltv=position.get('entry_liquidation_threshold_2b', position['entry_collateral_ratio_2b']),
            side='lending',
            borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
        )

        # Store before/after liquidation distances for Slack notification
        liq_dist_2a_before = opening_liq_result_2a.get('pct_distance')
        liq_dist_2a_after = liq_result_2a.get('pct_distance')
        liq_dist_2b_before = opening_liq_result_2b.get('pct_distance')
        liq_dist_2b_after = liq_result_2b.get('pct_distance')

        # 7. Determine rebalance actions
        entry_action_1a = "Initial deployment"
        entry_action_2a = "Initial deployment"
        entry_action_2b = "Initial deployment"
        entry_action_3b = "Initial deployment"

        exit_action_1a = self._determine_rebalance_action('1a', entry_token_amount_1a, exit_token_amount_1a, 'Lend')
        exit_action_2a = self._determine_rebalance_action('2a', entry_token_amount_2a, exit_token_amount_2a, 'Borrow')
        exit_action_2b = self._determine_rebalance_action('2b', entry_token_amount_2b, exit_token_amount_2b, 'Lend')
        exit_action_3b = self._determine_rebalance_action('3b', entry_token_amount_3b, exit_token_amount_3b, 'Borrow')

        # 8. Calculate fees for rebalance segments
        # For first segment: pv_result already includes full initial fees
        # For rebalance segments: calculate fees on additional borrowing only
        if is_rebalance_segment:
            rebalance_fees = 0

            # Token2@A: Only pay fees on ADDITIONAL borrowing (currently token2 is the only rebalanced token)
            # entry_token_amount_2a = amount at START of this segment (from position's entry_price_2a)
            # exit_token_amount_2a = amount at END of this segment (same for now, will change after rebalance logic)
            # For now, token amounts don't change during the segment, so delta = 0
            # Fees will be calculated when actual rebalancing adjusts token amounts
            delta_borrow_2a = exit_token_amount_2a - entry_token_amount_2a
            if delta_borrow_2a > 0:
                # Get entry fee from position record
                entry_fee_2a = position.get('entry_borrow_fee_2a', 0) or 0
                rebalance_fees += delta_borrow_2a * closing_rates['price_2a'] * entry_fee_2a

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
            'opening_lend_rate_1a': position['entry_lend_rate_1a'],
            'opening_borrow_rate_2a': position['entry_borrow_rate_2a'],
            'opening_lend_rate_2b': position['entry_lend_rate_2b'],
            'opening_borrow_rate_3b': position['entry_borrow_rate_3b'],
            'opening_price_1a': position['entry_price_1a'],
            'opening_price_2a': position['entry_price_2a'],
            'opening_price_2b': position['entry_price_2b'],
            'opening_price_3b': position['entry_price_3b'],
            # Closing rates/prices from rates_snapshot
            'closing_lend_rate_1a': closing_rates['lend_rate_1a'],
            'closing_borrow_rate_2a': closing_rates['borrow_rate_2a'],
            'closing_lend_rate_2b': closing_rates['lend_rate_2b'],
            'closing_borrow_rate_3b': closing_rates['borrow_rate_3b'],
            'closing_price_1a': closing_rates['price_1a'],
            'closing_price_2a': closing_rates['price_2a'],
            'closing_price_2b': closing_rates['price_2b'],
            'closing_price_3b': closing_rates['price_3b'],
            # Liquidation prices at rebalance time (using entry token amounts + closing prices)
            'closing_liq_price_1a': liq_result_1a.get('liq_price'),
            'closing_liq_price_2a': liq_result_2a.get('liq_price'),
            'closing_liq_price_2b': liq_result_2b.get('liq_price'),
            'closing_liq_price_3b': liq_result_3b.get('liq_price'),
            # Liquidation distances at rebalance time (after)
            'closing_liq_dist_1a': liq_result_1a.get('pct_distance'),
            'closing_liq_dist_2a': liq_result_2a.get('pct_distance'),
            'closing_liq_dist_2b': liq_result_2b.get('pct_distance'),
            'closing_liq_dist_3b': liq_result_3b.get('pct_distance'),
            # Liquidation distances before rebalance (for Slack notification)
            'liq_dist_2a_before': liq_dist_2a_before,
            'liq_dist_2b_before': liq_dist_2b_before,
            # Collateral ratios
            'collateral_ratio_1a': position['entry_collateral_ratio_1a'],
            'collateral_ratio_2b': position['entry_collateral_ratio_2b'],
            # Liquidation thresholds
            'liquidation_threshold_1a': position['entry_liquidation_threshold_1a'],
            'liquidation_threshold_2b': position['entry_liquidation_threshold_2b'],
            # Token amounts
            'entry_token_amount_1a': entry_token_amount_1a,
            'entry_token_amount_2a': entry_token_amount_2a,
            'entry_token_amount_2b': entry_token_amount_2b,
            'entry_token_amount_3b': entry_token_amount_3b,
            'exit_token_amount_1a': exit_token_amount_1a,
            'exit_token_amount_2a': exit_token_amount_2a,
            'exit_token_amount_2b': exit_token_amount_2b,
            'exit_token_amount_3b': exit_token_amount_3b,
            # USD sizes
            'entry_size_usd_1a': entry_size_usd_1a,
            'entry_size_usd_2a': entry_size_usd_2a,
            'entry_size_usd_2b': entry_size_usd_2b,
            'entry_size_usd_3b': entry_size_usd_3b,
            'exit_size_usd_1a': exit_size_usd_1a,
            'exit_size_usd_2a': exit_size_usd_2a,
            'exit_size_usd_2b': exit_size_usd_2b,
            'exit_size_usd_3b': exit_size_usd_3b,
            # Actions
            'entry_action_1a': entry_action_1a,
            'entry_action_2a': entry_action_2a,
            'entry_action_2b': entry_action_2b,
            'entry_action_3b': entry_action_3b,
            'exit_action_1a': exit_action_1a,
            'exit_action_2a': exit_action_2a,
            'exit_action_2b': exit_action_2b,
            'exit_action_3b': exit_action_3b,
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
            position['protocol_a'], position['token1_contract'],
            position['protocol_a'], position['token2_contract'],
            position['protocol_b'], position['token2_contract'],
            position['protocol_b'], position['token3_contract']
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
        leg_2b = get_leg_data(position['protocol_b'], position['token2_contract'])
        leg_3b = get_leg_data(position['protocol_b'], position['token3_contract'])

        return {
            'lend_rate_1a': leg_1a['lend_rate'],
            'borrow_rate_2a': leg_2a['borrow_rate'],
            'lend_rate_2b': leg_2b['lend_rate'],
            'borrow_rate_3b': leg_3b['borrow_rate'],
            'price_1a': leg_1a['price'],
            'price_2a': leg_2a['price'],
            'price_2b': leg_2b['price'],
            'price_3b': leg_3b['price'],
            'collateral_ratio_1a': leg_1a['collateral_ratio'],
            'collateral_ratio_2b': leg_2b['collateral_ratio'],
            'liquidation_threshold_1a': leg_1a['liquidation_threshold'],
            'liquidation_threshold_2b': leg_2b['liquidation_threshold'],
            'borrow_weight_2a': leg_2a['borrow_weight'],
            'borrow_weight_3b': leg_3b['borrow_weight']
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
        if leg in ['1a', '3b']:
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
        - Weightings (l_a, b_a, L_B, b_b) remain CONSTANT
        """
        # Generate rebalance ID
        rebalance_id = str(uuid.uuid4())

        # Get current position to determine sequence number
        position = self.get_position_by_id(position_id)
        sequence_number = (position.get('rebalance_count') or 0) + 1

        # Convert timestamps to datetime strings for DB
        opening_timestamp_str = to_datetime_str(snapshot['opening_timestamp'])
        closing_timestamp_str = to_datetime_str(snapshot['closing_timestamp'])

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
                    rebalance_id, position_id, sequence_number,
                    opening_timestamp, closing_timestamp,
                    deployment_usd, l_a, b_a, l_b, b_b,
                    opening_lend_rate_1a, opening_borrow_rate_2a, opening_lend_rate_2b, opening_borrow_rate_3b,
                    opening_price_1a, opening_price_2a, opening_price_2b, opening_price_3b,
                    closing_lend_rate_1a, closing_borrow_rate_2a, closing_lend_rate_2b, closing_borrow_rate_3b,
                    closing_price_1a, closing_price_2a, closing_price_2b, closing_price_3b,
                    closing_liq_price_1a, closing_liq_price_2a, closing_liq_price_2b, closing_liq_price_3b,
                    closing_liq_dist_1a, closing_liq_dist_2a, closing_liq_dist_2b, closing_liq_dist_3b,
                    collateral_ratio_1a, collateral_ratio_2b,
                    liquidation_threshold_1a, liquidation_threshold_2b,
                    entry_action_1a, entry_action_2a, entry_action_2b, entry_action_3b,
                    exit_action_1a, exit_action_2a, exit_action_2b, exit_action_3b,
                    entry_token_amount_1a, entry_token_amount_2a, entry_token_amount_2b, entry_token_amount_3b,
                    exit_token_amount_1a, exit_token_amount_2a, exit_token_amount_2b, exit_token_amount_3b,
                    entry_size_usd_1a, entry_size_usd_2a, entry_size_usd_2b, entry_size_usd_3b,
                    exit_size_usd_1a, exit_size_usd_2a, exit_size_usd_2b, exit_size_usd_3b,
                    realised_fees, realised_pnl, realised_lend_earnings, realised_borrow_costs,
                    rebalance_reason, rebalance_notes
                ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            """, (
                rebalance_id, position_id, sequence_number,
                opening_timestamp_str, closing_timestamp_str,
                convert_value('deployment_usd'), convert_value('l_a'), convert_value('b_a'), convert_value('l_b'), convert_value('b_b'),
                convert_value('opening_lend_rate_1a'), convert_value('opening_borrow_rate_2a'),
                convert_value('opening_lend_rate_2b'), convert_value('opening_borrow_rate_3b'),
                convert_value('opening_price_1a'), convert_value('opening_price_2a'),
                convert_value('opening_price_2b'), convert_value('opening_price_3b'),
                convert_value('closing_lend_rate_1a'), convert_value('closing_borrow_rate_2a'),
                convert_value('closing_lend_rate_2b'), convert_value('closing_borrow_rate_3b'),
                convert_value('closing_price_1a'), convert_value('closing_price_2a'),
                convert_value('closing_price_2b'), convert_value('closing_price_3b'),
                convert_value('closing_liq_price_1a'), convert_value('closing_liq_price_2a'),
                convert_value('closing_liq_price_2b'), convert_value('closing_liq_price_3b'),
                convert_value('closing_liq_dist_1a'), convert_value('closing_liq_dist_2a'),
                convert_value('closing_liq_dist_2b'), convert_value('closing_liq_dist_3b'),
                convert_value('collateral_ratio_1a'), convert_value('collateral_ratio_2b'),
                convert_value('liquidation_threshold_1a'), convert_value('liquidation_threshold_2b'),
                snapshot.get('entry_action_1a'), snapshot.get('entry_action_2a'),
                snapshot.get('entry_action_2b'), snapshot.get('entry_action_3b'),
                snapshot.get('exit_action_1a'), snapshot.get('exit_action_2a'),
                snapshot.get('exit_action_2b'), snapshot.get('exit_action_3b'),
                convert_value('entry_token_amount_1a'), convert_value('entry_token_amount_2a'),
                convert_value('entry_token_amount_2b'), convert_value('entry_token_amount_3b'),
                convert_value('exit_token_amount_1a'), convert_value('exit_token_amount_2a'),
                convert_value('exit_token_amount_2b'), convert_value('exit_token_amount_3b'),
                convert_value('entry_size_usd_1a'), convert_value('entry_size_usd_2a'),
                convert_value('entry_size_usd_2b'), convert_value('entry_size_usd_3b'),
                convert_value('exit_size_usd_1a'), convert_value('exit_size_usd_2a'),
                convert_value('exit_size_usd_2b'), convert_value('exit_size_usd_3b'),
                convert_value('realised_fees'), convert_value('realised_pnl'),
                convert_value('realised_lend_earnings'), convert_value('realised_borrow_costs'),
                rebalance_reason, rebalance_notes
                ))

            # Update positions table
            current_accumulated_pnl = position.get('accumulated_realised_pnl') or 0
            ph = self._get_placeholder()
            cursor.execute(f"""
                UPDATE positions
                SET accumulated_realised_pnl = {ph},
                    rebalance_count = {ph},
                    last_rebalance_timestamp = {ph},
                    entry_lend_rate_1a = {ph},
                    entry_borrow_rate_2a = {ph},
                    entry_lend_rate_2b = {ph},
                    entry_borrow_rate_3b = {ph},
                    entry_price_1a = {ph},
                    entry_price_2a = {ph},
                    entry_price_2b = {ph},
                    entry_price_3b = {ph},
                    updated_at = CURRENT_TIMESTAMP
                WHERE position_id = {ph}
            """, (
                self._to_native_type(current_accumulated_pnl + convert_value('realised_pnl')),
                sequence_number,
                closing_timestamp_str,
                convert_value('closing_lend_rate_1a'),
                convert_value('closing_borrow_rate_2a'),
                convert_value('closing_lend_rate_2b'),
                convert_value('closing_borrow_rate_3b'),
                convert_value('closing_price_1a'),
                convert_value('closing_price_2a'),
                convert_value('closing_price_2b'),
                convert_value('closing_price_3b'),
                position_id
            ))

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
                'opening_lend_rate_1a', 'opening_borrow_rate_2a', 'opening_lend_rate_2b', 'opening_borrow_rate_3b',
                'opening_price_1a', 'opening_price_2a', 'opening_price_2b', 'opening_price_3b',
                'closing_lend_rate_1a', 'closing_borrow_rate_2a', 'closing_lend_rate_2b', 'closing_borrow_rate_3b',
                'closing_price_1a', 'closing_price_2a', 'closing_price_2b', 'closing_price_3b',
                'collateral_ratio_1a', 'collateral_ratio_2b',
                'liquidation_threshold_1a', 'liquidation_threshold_2b',
                'entry_token_amount_1a', 'entry_token_amount_2a', 'entry_token_amount_2b', 'entry_token_amount_3b',
                'exit_token_amount_1a', 'exit_token_amount_2a', 'exit_token_amount_2b', 'exit_token_amount_3b',
                'entry_size_usd_1a', 'entry_size_usd_2a', 'entry_size_usd_2b', 'entry_size_usd_3b',
                'exit_size_usd_1a', 'exit_size_usd_2a', 'exit_size_usd_2b', 'exit_size_usd_3b',
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
                'entry_lend_rate_1a': segment['opening_lend_rate_1a'],
                'entry_borrow_rate_2a': segment['opening_borrow_rate_2a'],
                'entry_lend_rate_2b': segment['opening_lend_rate_2b'],
                'entry_borrow_rate_3b': segment['opening_borrow_rate_3b'],
                'entry_price_1a': segment['opening_price_1a'],
                'entry_price_2a': segment['opening_price_2a'],
                'entry_price_2b': segment['opening_price_2b'],
                'entry_price_3b': segment['opening_price_3b'],
                'entry_collateral_ratio_1a': segment['collateral_ratio_1a'],
                'entry_collateral_ratio_2b': segment['collateral_ratio_2b'],
                'entry_liquidation_threshold_1a': segment['liquidation_threshold_1a'],
                'entry_liquidation_threshold_2b': segment['liquidation_threshold_2b'],
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

    def check_positions_need_rebalancing(
        self,
        live_timestamp: int,
        rebalance_threshold: float = 0.02
    ) -> List[Dict]:
        """
        Check all active positions to see if rebalancing is needed based on liquidation distance changes.

        Logic: For each position, check if liquidation distance has changed significantly
        for token2 in both protocols (legs 2A and 2B).

        Formula: abs(baseline_liq_dist) - abs(live_liq_dist) >= rebalance_threshold

        DESIGN PRINCIPLES:
        - Timestamps are Unix seconds (int) internally
        - Baseline liquidation distances calculated from entry token amounts at entry prices
        - These entry distances represent the TARGET maintained through rebalancing
        - Live liquidation distances calculated using current market prices
        - Check both leg 2A (borrow from protocol A) and leg 2B (lend to protocol B)

        Args:
            live_timestamp: Current timestamp (Unix seconds)
            rebalance_threshold: Minimum change to trigger rebalance (default 0.02 = 2%)

        Returns:
            List of dicts with position info and rebalance recommendation:
            [
                {
                    'position_id': str,
                    'token2': str,
                    'protocol_a': str,
                    'protocol_b': str,
                    'baseline_liq_dist_2a': float,  # Entry target (calculated from entry data)
                    'live_liq_dist_2a': float,
                    'baseline_liq_dist_2b': float,  # Entry target (calculated from entry data)
                    'live_liq_dist_2b': float,
                    'needs_rebalance_2a': bool,
                    'needs_rebalance_2b': bool,
                    'needs_rebalance': bool  # True if either leg needs rebalancing
                },
                ...
            ]
        """
        from analysis.position_calculator import PositionCalculator

        # Get all active positions at live_timestamp
        active_positions = self.get_active_positions(live_timestamp=live_timestamp)

        if active_positions.empty:
            return []

        results = []
        calculator = PositionCalculator()

        # Convert timestamp for DB queries
        live_timestamp_str = to_datetime_str(live_timestamp)

        for _, position in active_positions.iterrows():
            position_id = position['position_id']

            # ALWAYS calculate baseline from entry data
            # Entry liquidation distances are the TARGET maintained through rebalancing
            use_entry_calc = True

            # Get current market data at live_timestamp
            try:
                # Query rates and prices for all 4 legs
                ph = self._get_placeholder()
                query_rates = f"""
                SELECT protocol, token_contract, lend_total_apr, borrow_total_apr, price_usd,
                       collateral_ratio, liquidation_threshold, borrow_weight
                FROM rates_snapshot
                WHERE timestamp = {ph}
                AND ((protocol = {ph} AND token_contract = {ph}) OR
                     (protocol = {ph} AND token_contract = {ph}) OR
                     (protocol = {ph} AND token_contract = {ph}) OR
                     (protocol = {ph} AND token_contract = {ph}))
                """
                rates_df = pd.read_sql_query(
                    query_rates,
                    self.engine,
                    params=(
                        live_timestamp_str,
                        position['protocol_a'], position['token1_contract'],  # Leg 1A
                        position['protocol_a'], position['token2_contract'],  # Leg 2A
                        position['protocol_b'], position['token2_contract'],  # Leg 2B
                        position['protocol_b'], position['token3_contract'],  # Leg 3B
                    )
                )

                if rates_df.empty:
                    # No market data at this timestamp - skip position
                    continue

                # Extract rates/prices for each leg
                def get_market_data(protocol, token_contract):
                    row = rates_df[
                        (rates_df['protocol'] == protocol) &
                        (rates_df['token_contract'] == token_contract)
                    ]
                    if row.empty:
                        return None
                    return row.iloc[0]

                data_1a = get_market_data(position['protocol_a'], position['token1_contract'])
                data_2a = get_market_data(position['protocol_a'], position['token2_contract'])
                data_2b = get_market_data(position['protocol_b'], position['token2_contract'])

                if data_1a is None or data_2a is None or data_2b is None:
                    # Missing data for some legs - skip position
                    continue

                # Calculate entry token amounts (token amounts stay constant, assuming no interest accrual in paper trading)
                deployment_usd = float(position['deployment_usd'])
                l_a = float(position['l_a'])
                b_a = float(position['b_a'])
                L_B = float(position['l_b'])
                b_b = float(position['b_b'])

                entry_price_1a = float(position['entry_price_1a'])
                entry_price_2a = float(position['entry_price_2a'])
                entry_price_2b = float(position['entry_price_2b'])
                entry_price_3b = float(position['entry_price_3b'])

                # Token amounts (constant throughout position life, unless manually rebalanced)
                entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
                entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
                entry_token_amount_2b = entry_token_amount_2a  # Same tokens moved from A to B
                entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if entry_price_3b > 0 else 0

                # Calculate baseline liquidation distances if needed
                if use_entry_calc:
                    # Baseline uses entry token amounts valued at entry prices
                    baseline_collateral_A = entry_token_amount_1a * entry_price_1a
                    baseline_loan_A = entry_token_amount_2a * entry_price_2a
                    baseline_collateral_B = entry_token_amount_2b * entry_price_2b
                    baseline_loan_B = entry_token_amount_3b * entry_price_3b

                    # Leg 2A: Borrow token2 from Protocol A
                    # Collateral: token1 lent (1A), Loan: token2 borrowed (2A)
                    baseline_result_2a = calculator.calculate_liquidation_price(
                        collateral_value=baseline_collateral_A,
                        loan_value=baseline_loan_A,
                        lending_token_price=entry_price_1a,
                        borrowing_token_price=entry_price_2a,
                        lltv=float(position['entry_liquidation_threshold_1a']),
                        side='borrowing',  # Token2 price rise causes liquidation
                        borrow_weight=float(position.get('entry_borrow_weight_2a', 1.0))
                    )
                    baseline_liq_dist_2a = baseline_result_2a['pct_distance']

                    # Leg 2B: Lend token2 to Protocol B
                    # Collateral: token2 lent (2B), Loan: token3 borrowed (3B)
                    baseline_result_2b = calculator.calculate_liquidation_price(
                        collateral_value=baseline_collateral_B,
                        loan_value=baseline_loan_B,
                        lending_token_price=entry_price_2b,
                        borrowing_token_price=entry_price_3b,
                        lltv=float(position['entry_liquidation_threshold_2b']),
                        side='lending',  # Token2 price drop causes liquidation
                        borrow_weight=float(position.get('entry_borrow_weight_3b', 1.0))
                    )
                    baseline_liq_dist_2b = baseline_result_2b['pct_distance']

                # Calculate live liquidation distances using entry token amounts valued at live prices
                live_price_1a = float(data_1a['price_usd'])
                live_price_2a = float(data_2a['price_usd'])
                live_price_2b = float(data_2b['price_usd'])

                # Need to get token3 data for leg 3B
                data_3b = get_market_data(position['protocol_b'], position['token3_contract'])
                if data_3b is None:
                    continue
                live_price_3b = float(data_3b['price_usd'])

                # Current USD values = entry token amounts × live prices
                current_collateral_A = entry_token_amount_1a * live_price_1a
                current_loan_A = entry_token_amount_2a * live_price_2a
                current_collateral_B = entry_token_amount_2b * live_price_2b
                current_loan_B = entry_token_amount_3b * live_price_3b

                # Leg 2A: Borrow token2 from Protocol A
                live_result_2a = calculator.calculate_liquidation_price(
                    collateral_value=current_collateral_A,
                    loan_value=current_loan_A,
                    lending_token_price=live_price_1a,
                    borrowing_token_price=live_price_2a,
                    lltv=float(data_1a['liquidation_threshold']),
                    side='borrowing',
                    borrow_weight=float(data_2a.get('borrow_weight', 1.0))
                )
                live_liq_dist_2a = live_result_2a['pct_distance']

                # Leg 2B: Lend token2 to Protocol B
                live_result_2b = calculator.calculate_liquidation_price(
                    collateral_value=current_collateral_B,
                    loan_value=current_loan_B,
                    lending_token_price=live_price_2b,
                    borrowing_token_price=live_price_3b,
                    lltv=float(data_2b['liquidation_threshold']),
                    side='lending',
                    borrow_weight=float(data_3b.get('borrow_weight', 1.0))
                )
                live_liq_dist_2b = live_result_2b['pct_distance']

                # Check if rebalancing is needed
                # Formula: abs(baseline) - abs(live) >= threshold
                delta_2a = abs(baseline_liq_dist_2a) - abs(live_liq_dist_2a)
                delta_2b = abs(baseline_liq_dist_2b) - abs(live_liq_dist_2b)

                needs_rebalance_2a = delta_2a >= rebalance_threshold
                needs_rebalance_2b = delta_2b >= rebalance_threshold
                needs_rebalance = needs_rebalance_2a or needs_rebalance_2b

                # Store result
                results.append({
                    'position_id': position_id,
                    'token2': position['token2'],
                    'protocol_a': position['protocol_a'],
                    'protocol_b': position['protocol_b'],
                    'baseline_liq_dist_2a': baseline_liq_dist_2a,
                    'live_liq_dist_2a': live_liq_dist_2a,
                    'baseline_liq_dist_2b': baseline_liq_dist_2b,
                    'live_liq_dist_2b': live_liq_dist_2b,
                    'delta_2a': delta_2a,
                    'delta_2b': delta_2b,
                    'needs_rebalance_2a': needs_rebalance_2a,
                    'needs_rebalance_2b': needs_rebalance_2b,
                    'needs_rebalance': needs_rebalance
                })

            except Exception as e:
                # Log error but continue checking other positions
                print(f"Error checking position {position_id}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return results