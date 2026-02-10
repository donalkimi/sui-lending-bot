"""
Portfolio Service - CRUD operations for portfolio management

This service manages portfolios (collections of positions):
- Creates portfolios from generated allocations
- Tracks portfolio-level performance metrics
- Calculates portfolio PnL by aggregating position PnL
- Links to existing positions table via portfolio_id

Design:
- Portfolios are collections of positions
- Reuses existing positions table with portfolio_id column
- Single positions have portfolio_id='single positions'
- Portfolio PnL = sum of individual position PnL
"""

import sqlite3
import uuid
import json
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd
from datetime import datetime
from utils.time_helpers import to_seconds

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


class PortfolioService:
    """
    Service for managing portfolios (collections of positions).

    Key principles:
    - Portfolios are metadata - actual strategies stored in positions table
    - portfolio_id links portfolios to positions
    - Single positions have portfolio_id='single positions'
    - Portfolio metrics calculated by aggregating position metrics
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

    # ==================== Portfolio Management ====================

    def save_portfolio(
        self,
        portfolio_name: str,
        portfolio_df: pd.DataFrame,
        portfolio_size: float,
        constraints: Dict,
        entry_timestamp: int,
        is_paper_trade: bool = True,
        user_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Save a generated portfolio to the database.

        This creates:
        1. A portfolio record in the portfolios table
        2. Position records in the positions table with portfolio_id set

        Args:
            portfolio_name: User-provided portfolio name
            portfolio_df: DataFrame with selected strategies (from PortfolioAllocator)
                         Must include: allocation_usd, net_apr, token columns, rates, prices
            portfolio_size: Target portfolio size in USD
            constraints: Constraint settings used for allocation
            entry_timestamp: Unix timestamp when portfolio was generated
            is_paper_trade: True for paper trading (default), False for real capital
            user_id: Optional user ID for multi-user support
            notes: Optional user notes

        Returns:
            portfolio_id: UUID of created portfolio

        Raises:
            ValueError: If portfolio_df is empty or missing required columns
        """
        if portfolio_df.empty:
            raise ValueError("Cannot save empty portfolio")

        # Validate required columns
        required_cols = [
            'allocation_usd', 'net_apr', 'token1', 'token2', 'token3',
            'token1_contract', 'token2_contract', 'token3_contract',
            'protocol_a', 'protocol_b',
            'lend_rate_1a', 'borrow_rate_2a', 'lend_rate_2b', 'borrow_rate_3b',
            'P1_A', 'P2_A', 'P2_B', 'P3_B'
        ]
        missing_cols = [col for col in required_cols if col not in portfolio_df.columns]
        if missing_cols:
            raise ValueError(f"Portfolio missing required columns: {missing_cols}")

        # Generate portfolio ID
        portfolio_id = str(uuid.uuid4())

        # Calculate portfolio metrics
        total_allocated = portfolio_df['allocation_usd'].sum()
        utilization_pct = (total_allocated / portfolio_size) * 100 if portfolio_size > 0 else 0

        # Calculate USD-weighted entry net APR
        # Formula: sum(strategy.net_apr × strategy.allocation_usd) / total_allocated
        entry_weighted_net_apr = (
            (portfolio_df['net_apr'] * portfolio_df['allocation_usd']).sum() / total_allocated
            if total_allocated > 0 else 0
        )

        # Prepare constraints JSON
        constraints_json = json.dumps(constraints)

        # Insert portfolio record
        cursor = self.conn.cursor()
        ph = self._get_placeholder()

        cursor.execute(f"""
            INSERT INTO portfolios (
                portfolio_id,
                portfolio_name,
                status,
                is_paper_trade,
                user_id,
                created_timestamp,
                entry_timestamp,
                target_portfolio_size,
                actual_allocated_usd,
                utilization_pct,
                entry_weighted_net_apr,
                constraints_json,
                notes
            ) VALUES (
                {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
                {ph}, {ph}, {ph}, {ph}, {ph}, {ph}
            )
        """, (
            portfolio_id,
            portfolio_name,
            'active',
            is_paper_trade,
            user_id,
            datetime.now(),  # created_timestamp
            datetime.fromtimestamp(to_seconds(entry_timestamp)),  # entry_timestamp - handle any timestamp format
            self._to_native_type(portfolio_size),
            self._to_native_type(total_allocated),
            self._to_native_type(utilization_pct),
            self._to_native_type(entry_weighted_net_apr),
            constraints_json,
            notes
        ))

        self.conn.commit()

        # Step 2: Create position records for each strategy in the portfolio
        # Import PositionService to create positions with portfolio_id link
        from analysis.position_service import PositionService
        position_service = PositionService(self.conn, self.engine)

        created_positions = []
        for idx, strategy_row in portfolio_df.iterrows():
            try:
                # Ensure strategy_row has timestamp (required by create_position)
                strategy_row = strategy_row.copy()
                if 'timestamp' not in strategy_row or strategy_row['timestamp'] is None:
                    strategy_row['timestamp'] = entry_timestamp

                # Extract position multipliers from strategy
                positions_dict = {
                    'l_a': strategy_row.get('l_a', strategy_row.get('L_A', 0)),
                    'b_a': strategy_row.get('b_a', strategy_row.get('B_A', 0)),
                    'l_b': strategy_row.get('l_b', strategy_row.get('L_B', 0)),
                    'b_b': strategy_row.get('b_b', strategy_row.get('B_B'))
                }

                # Create position with portfolio_id link
                position_id = position_service.create_position(
                    strategy_row=strategy_row,
                    positions=positions_dict,
                    token1=strategy_row['token1'],
                    token2=strategy_row['token2'],
                    token3=strategy_row.get('token3'),
                    token1_contract=strategy_row['token1_contract'],
                    token2_contract=strategy_row['token2_contract'],
                    token3_contract=strategy_row.get('token3_contract'),
                    protocol_a=strategy_row['protocol_a'],
                    protocol_b=strategy_row['protocol_b'],
                    deployment_usd=strategy_row['allocation_usd'],
                    is_paper_trade=is_paper_trade,
                    execution_time=entry_timestamp,
                    user_id=user_id,
                    notes=f"Portfolio: {portfolio_name}",
                    portfolio_id=portfolio_id  # Link to portfolio
                )
                created_positions.append(position_id)

            except Exception as e:
                # Log error but continue with other positions
                print(f"⚠️  Failed to create position for strategy {idx}: {e}")
                continue

        print(f"✅ Created portfolio '{portfolio_name}' with {len(created_positions)}/{len(portfolio_df)} positions")

        return portfolio_id

    def get_active_portfolios(self) -> pd.DataFrame:
        """
        Get all active portfolios.

        Returns:
            DataFrame with portfolio records
        """
        query = """
        SELECT *
        FROM portfolios
        WHERE status = 'active'
        ORDER BY entry_timestamp DESC
        """
        portfolios = pd.read_sql_query(query, self.engine)
        return portfolios

    def get_portfolio_by_id(self, portfolio_id: str) -> Optional[pd.Series]:
        """
        Get portfolio by ID.

        Args:
            portfolio_id: Portfolio UUID

        Returns:
            Series with portfolio data, or None if not found
        """
        ph = self._get_placeholder()
        query = f"""
        SELECT *
        FROM portfolios
        WHERE portfolio_id = {ph}
        """
        result = pd.read_sql_query(query, self.engine, params=(portfolio_id,))

        if result.empty:
            return None

        return result.iloc[0]

    def get_portfolio_positions(self, portfolio_id: str) -> pd.DataFrame:
        """
        Get all active positions in a portfolio.

        Args:
            portfolio_id: Portfolio UUID

        Returns:
            DataFrame with active position records linked to this portfolio
        """
        ph = self._get_placeholder()
        query = f"""
        SELECT *
        FROM positions
        WHERE portfolio_id = {ph}
          AND status = 'active'
        ORDER BY deployment_usd DESC
        """
        positions = pd.read_sql_query(query, self.engine, params=(portfolio_id,))
        return positions

    def get_standalone_positions(self) -> pd.DataFrame:
        """
        Get all standalone positions (not part of any portfolio).

        Returns:
            DataFrame with active position records where portfolio_id IS NULL
        """
        query = """
        SELECT *
        FROM positions
        WHERE portfolio_id IS NULL
          AND status = 'active'
        ORDER BY deployment_usd DESC
        """
        positions = pd.read_sql_query(query, self.engine)
        return positions

    def calculate_portfolio_pnl(
        self,
        portfolio_id: str,
        live_timestamp: int,
        position_service
    ) -> Dict:
        """
        Calculate portfolio PnL by aggregating position PnL.

        Args:
            portfolio_id: Portfolio UUID
            live_timestamp: Current timestamp for PnL calculation
            position_service: PositionService instance for PnL calculations

        Returns:
            Dict with:
            - total_pnl: Total portfolio PnL in USD
            - live_weighted_net_apr: Current USD-weighted net APR
            - position_pnls: List of {position_id, pnl} dicts
            - days_active: Days since portfolio entry
        """
        # Get portfolio metadata
        portfolio = self.get_portfolio_by_id(portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        # Get all positions in portfolio
        positions = self.get_portfolio_positions(portfolio_id)
        if positions.empty:
            return {
                'total_pnl': 0.0,
                'live_weighted_net_apr': 0.0,
                'position_pnls': [],
                'days_active': 0
            }

        # Calculate PnL for each position
        position_pnls = []
        total_pnl = 0.0

        for _, position in positions.iterrows():
            # Get position PnL (this would use PositionService.calculate_position_pnl)
            # For now, placeholder - actual implementation would call position_service
            position_pnl = 0.0  # TODO: Implement position PnL calculation
            position_pnls.append({
                'position_id': position['position_id'],
                'pnl': position_pnl
            })
            total_pnl += position_pnl

        # Calculate days active
        entry_timestamp = pd.to_datetime(portfolio['entry_timestamp']).timestamp()
        days_active = (live_timestamp - entry_timestamp) / 86400

        # Calculate live weighted net APR (current rates)
        # TODO: Fetch current rates and calculate live APR
        live_weighted_net_apr = portfolio['entry_weighted_net_apr']  # Placeholder

        return {
            'total_pnl': total_pnl,
            'live_weighted_net_apr': live_weighted_net_apr,
            'position_pnls': position_pnls,
            'days_active': days_active
        }

    def close_portfolio(
        self,
        portfolio_id: str,
        close_timestamp: int,
        close_reason: str,
        close_notes: Optional[str] = None
    ) -> None:
        """
        Close a portfolio (mark as closed).

        Note: This does NOT close the individual positions - use PositionService for that.
        This just updates the portfolio metadata.

        Args:
            portfolio_id: Portfolio UUID
            close_timestamp: Unix timestamp when closed
            close_reason: Reason for closure
            close_notes: Optional closure notes
        """
        cursor = self.conn.cursor()
        ph = self._get_placeholder()

        cursor.execute(f"""
            UPDATE portfolios
            SET
                status = 'closed',
                close_timestamp = {ph},
                close_reason = {ph},
                close_notes = {ph},
                updated_at = CURRENT_TIMESTAMP
            WHERE portfolio_id = {ph}
        """, (
            datetime.fromtimestamp(to_seconds(close_timestamp)),
            close_reason,
            close_notes,
            portfolio_id
        ))

        self.conn.commit()

    def update_portfolio_metrics(
        self,
        portfolio_id: str,
        accumulated_realised_pnl: float,
        rebalance_count: int,
        last_rebalance_timestamp: Optional[int] = None
    ) -> None:
        """
        Update portfolio performance metrics.

        Args:
            portfolio_id: Portfolio UUID
            accumulated_realised_pnl: Total realized PnL
            rebalance_count: Number of rebalances
            last_rebalance_timestamp: Most recent rebalance timestamp
        """
        cursor = self.conn.cursor()
        ph = self._get_placeholder()

        last_rebalance_dt = (
            datetime.fromtimestamp(to_seconds(last_rebalance_timestamp))
            if last_rebalance_timestamp
            else None
        )

        cursor.execute(f"""
            UPDATE portfolios
            SET
                accumulated_realised_pnl = {ph},
                rebalance_count = {ph},
                last_rebalance_timestamp = {ph},
                updated_at = CURRENT_TIMESTAMP
            WHERE portfolio_id = {ph}
        """, (
            self._to_native_type(accumulated_realised_pnl),
            rebalance_count,
            last_rebalance_dt,
            portfolio_id
        ))

        self.conn.commit()

    def delete_portfolio(self, portfolio_id: str) -> None:
        """
        Delete a portfolio permanently.

        Warning: This does NOT delete the positions - use PositionService for that.
        Positions will have their portfolio_id set to NULL due to ON DELETE SET NULL.

        Args:
            portfolio_id: Portfolio UUID
        """
        cursor = self.conn.cursor()
        ph = self._get_placeholder()

        cursor.execute(f"""
            DELETE FROM portfolios
            WHERE portfolio_id = {ph}
        """, (portfolio_id,))

        self.conn.commit()
