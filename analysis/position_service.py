"""
Position Service - Core position management logic for paper trading (Phase 1)

This service handles:
- Creating/closing positions (paper trading only, no blockchain transactions)
- Calculating position PnL with detailed breakdown
- Managing position snapshots (lazy creation)
- Calculating liquidation risk metrics
- Querying positions and portfolio summaries
"""

import sqlite3
import pandas as pd
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import sys
import os

try:
    import psycopg2
except ImportError:
    psycopg2 = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


class PositionService:
    """Service for managing paper trading positions"""

    def __init__(self, conn):
        """
        Initialize the position service

        Args:
            conn: Database connection (sqlite3 or psycopg2)
        """
        self.conn = conn
        self.is_postgres = psycopg2 is not None and isinstance(conn, psycopg2.extensions.connection)

    def _get_placeholder(self):
        """Get the correct parameter placeholder for SQL queries"""
        return '%s' if self.is_postgres else '?'

    def _execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        """Execute a query and return results as DataFrame"""
        try:
            return pd.read_sql_query(query, self.conn, params=params)
        except Exception as e:
            print(f"Query error: {e}")
            return pd.DataFrame()

    def _execute_write(self, query: str, params: tuple = None) -> bool:
        """Execute a write query (INSERT/UPDATE/DELETE)"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, params or ())
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Write error: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    # ==================== Lifecycle Management ====================

    def create_position(
        self,
        strategy_row: pd.Series,
        deployment_usd: float,
        liquidation_distance: float,
        is_levered: bool,
        notes: str = "",
        is_paper_trade: bool = True,
        user_id: Optional[str] = None
    ) -> str:
        """
        Create a new paper trading position

        Args:
            strategy_row: Row from RateAnalyzer results containing strategy data
            deployment_usd: Deployment size in USD
            liquidation_distance: Liquidation distance threshold
            is_levered: True if levered (4 legs), False if unlevered (3 legs)
            notes: Optional user notes
            is_paper_trade: Always True for Phase 1
            user_id: Optional user ID (for multi-user support in future)

        Returns:
            position_id: UUID of created position
        """
        # Generate position ID
        position_id = str(uuid.uuid4())

        # Extract strategy data
        token1 = strategy_row['token1']
        token2 = strategy_row['token2']
        token3 = strategy_row.get('token3')
        token1_contract = strategy_row.get('token1_contract', '')
        token2_contract = strategy_row.get('token2_contract', '')
        token3_contract = strategy_row.get('token3_contract')
        protocol_A = strategy_row['protocol_A']
        protocol_B = strategy_row['protocol_B']

        # Entry timestamp (should match the rates_snapshot timestamp being displayed)
        # Round to nearest minute to match rates_snapshot granularity
        raw_timestamp = strategy_row.get('timestamp', datetime.now())
        entry_timestamp = raw_timestamp.replace(second=0, microsecond=0) if raw_timestamp else datetime.now().replace(second=0, microsecond=0)

        # Position multipliers (normalized)
        L_A = strategy_row.get('L_A', 0) or 0
        B_A = strategy_row.get('B_A', 0) or 0
        L_B = strategy_row.get('L_B', 0) or 0
        B_B = (strategy_row.get('B_B', 0) or 0) if is_levered else 0

        # Entry rates
        entry_lend_rate_1A = strategy_row.get('lend_rate_1A', 0)
        entry_borrow_rate_2A = strategy_row.get('borrow_rate_2A', 0)
        entry_lend_rate_2B = strategy_row.get('lend_rate_2B', 0)
        entry_borrow_rate_3B = strategy_row.get('borrow_rate_3B') if is_levered else None

        # Entry prices (leg-level for Step 6)
        entry_price_1A = strategy_row.get('price_1A', 0)
        entry_price_2A = strategy_row.get('price_2A', strategy_row.get('price_2', 0))  # Fallback to price_2
        entry_price_2B = strategy_row.get('price_2B', strategy_row.get('price_2', 0))  # Fallback to price_2
        entry_price_3B = strategy_row.get('price_3B') if is_levered else None

        # Entry collateral ratios
        entry_collateral_ratio_1A = strategy_row.get('collateral_ratio_1A', 0)
        entry_collateral_ratio_2B = strategy_row.get('collateral_ratio_2B', 0)

        # Entry APRs (fee-adjusted)
        entry_net_apr = strategy_row.get('net_apr', 0)
        entry_apr5 = strategy_row.get('apr5', 0)
        entry_apr30 = strategy_row.get('apr30', 0)
        entry_apr90 = strategy_row.get('apr90', 0)

        # Entry liquidity & fees
        entry_max_size_usd = strategy_row.get('max_size', 0)
        entry_borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0)
        entry_borrow_fee_3B = strategy_row.get('borrow_fee_3B') if is_levered else None

        # Insert position
        ph = self._get_placeholder()
        query = f"""
        INSERT INTO positions (
            position_id, status, strategy_type, is_paper_trade, is_levered, user_id,
            token1, token2, token3, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, entry_timestamp, deployment_usd,
            L_A, B_A, L_B, B_B,
            entry_lend_rate_1A, entry_borrow_rate_2A, entry_lend_rate_2B, entry_borrow_rate_3B,
            entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B,
            entry_collateral_ratio_1A, entry_collateral_ratio_2B,
            entry_net_apr, entry_apr5, entry_apr30, entry_apr90, entry_liquidation_distance,
            entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B, notes
        ) VALUES (
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph}
        )
        """

        params = (
            position_id, 'active', 'recursive_lending', is_paper_trade, is_levered, user_id,
            token1, token2, token3, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, entry_timestamp, deployment_usd,
            L_A, B_A, L_B, B_B,
            entry_lend_rate_1A, entry_borrow_rate_2A, entry_lend_rate_2B, entry_borrow_rate_3B,
            entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B,
            entry_collateral_ratio_1A, entry_collateral_ratio_2B,
            entry_net_apr, entry_apr5, entry_apr30, entry_apr90, liquidation_distance,
            entry_max_size_usd, entry_borrow_fee_2A, entry_borrow_fee_3B, notes
        )

        if not self._execute_write(query, params):
            raise Exception("Failed to create position")

        # Create initial snapshot
        self.create_snapshot(position_id, snapshot_timestamp=entry_timestamp)

        print(f"✅ Created paper position: {position_id}")
        print(f"   {token1} → {token2} → {token3 if is_levered else 'N/A'}")
        print(f"   {protocol_A} ↔ {protocol_B}")
        print(f"   Deployment: ${deployment_usd:,.2f}")
        print(f"   Entry APR: {entry_net_apr:.2f}%")
        print(f"   Levered: {is_levered}")

        return position_id

    def close_position(
        self,
        position_id: str,
        reason: str = 'manual',
        notes: str = ""
    ) -> bool:
        """
        Close a position

        Args:
            position_id: Position UUID
            reason: Closure reason ('manual', 'liquidated', 'take_profit', etc.)
            notes: Optional closure notes

        Returns:
            bool: True if successful
        """
        # Update position status
        ph = self._get_placeholder()
        query = f"""
        UPDATE positions
        SET status = {ph}, close_timestamp = {ph}, close_reason = {ph}, close_notes = {ph}, updated_at = {ph}
        WHERE position_id = {ph}
        """

        # Round to nearest minute to match rates_snapshot granularity
        close_timestamp = datetime.now().replace(second=0, microsecond=0)
        params = ('closed', close_timestamp, reason, notes, close_timestamp, position_id)

        if not self._execute_write(query, params):
            return False

        # Create final snapshot
        self.create_snapshot(position_id, snapshot_timestamp=close_timestamp)

        print(f"✅ Closed position: {position_id}")
        print(f"   Reason: {reason}")

        return True

    # ==================== Price Helper Functions (Step 6) ====================

    def get_pnl_price(
        self,
        token: str,
        protocol: str,
        timestamp: Optional[datetime] = None,
        token_contract: Optional[str] = None
    ) -> float:
        """
        Get price for PnL calculation purposes.

        Phase 1: Returns protocol-reported price from rates_snapshot
        Phase 2: Can be extended to query AMM (Cetus) or oracle (Pyth, CoinGecko)

        Args:
            token: Token symbol (e.g., 'SUI', 'USDC')
            protocol: Protocol name (e.g., 'navi', 'suilend', 'alphafi')
            timestamp: Optional timestamp (None = latest snapshot)
            token_contract: Optional token contract address (more reliable than symbol)

        Returns:
            float: Price in USD

        Design notes:
            - Centralizes price source logic for easy upgrade
            - Can add fallback chain: AMM -> Oracle -> Protocol
            - Can add price staleness checks
            - Can add multiple AMM averaging (TWAP, etc.)
        """
        ph = self._get_placeholder()

        if timestamp:
            if token_contract:
                query = f"""
                    SELECT price_usd
                    FROM rates_snapshot
                    WHERE token_contract = {ph} AND protocol = {ph} AND timestamp = {ph}
                    LIMIT 1
                """
                params = (token_contract, protocol, timestamp)
            else:
                query = f"""
                    SELECT price_usd
                    FROM rates_snapshot
                    WHERE token = {ph} AND protocol = {ph} AND timestamp = {ph}
                    LIMIT 1
                """
                params = (token, protocol, timestamp)
        else:
            if token_contract:
                query = f"""
                    SELECT price_usd
                    FROM rates_snapshot
                    WHERE token_contract = {ph} AND protocol = {ph}
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                params = (token_contract, protocol)
            else:
                query = f"""
                    SELECT price_usd
                    FROM rates_snapshot
                    WHERE token = {ph} AND protocol = {ph}
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                params = (token, protocol)

        result = self._execute_query(query, params)

        if not result.empty:
            return float(result.iloc[0]['price_usd'])
        else:
            raise ValueError(f"No price found for {token} on {protocol} at {timestamp or 'latest'}")

    def get_leg_price_for_pnl(
        self,
        position: pd.Series,
        leg: str,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Get price for a specific position leg for PnL calculation.

        Args:
            position: Position record with token/protocol info
            leg: Leg identifier ('1A', '2A', '2B', '3B')
            timestamp: Optional timestamp (uses latest if None)

        Returns:
            float: Price in USD for that leg

        Usage:
            price_1A = get_leg_price_for_pnl(position, '1A', latest_snapshot['snapshot_timestamp'])
        """
        leg_config = {
            '1A': ('token1', 'token1_contract', 'protocol_A'),
            '2A': ('token2', 'token2_contract', 'protocol_A'),
            '2B': ('token2', 'token2_contract', 'protocol_B'),
            '3B': ('token3', 'token3_contract', 'protocol_B'),
        }

        if leg not in leg_config:
            raise ValueError(f"Invalid leg: {leg}")

        token_field, contract_field, protocol_field = leg_config[leg]
        token = position[token_field]
        token_contract = position.get(contract_field)
        protocol = position[protocol_field]

        return self.get_pnl_price(token, protocol, timestamp, token_contract)

    # ==================== Valuation & PnL ====================

    def calculate_position_value(
        self,
        position: pd.Series,
        latest_snapshot: Optional[pd.Series] = None
    ) -> Dict:
        """
        Calculate current position value and PnL breakdown with leg-level price impacts (Step 6)

        This uses forward-looking calculation: each snapshot's APR applies to
        the period AFTER that snapshot until the next snapshot.

        For active positions, the latest snapshot's rates apply to the period
        from latest snapshot to "now" (current calculation time).

        Args:
            position: Position record from database
            latest_snapshot: Optional latest snapshot (will query if not provided)

        Returns:
            Dict with PnL breakdown:
                - total_value: Current total value
                - total_pnl: Total PnL
                - pnl_base_apr: Earnings from base APR (before fees)
                - pnl_reward_apr: Earnings from reward APR
                - pnl_price_leg1: PnL from Leg 1 (Protocol A Lend, Token1)
                - pnl_price_leg2: PnL from Leg 2 (Protocol A Borrow, Token2)
                - pnl_price_leg3: PnL from Leg 3 (Protocol B Lend, Token2)
                - pnl_price_leg4: PnL from Leg 4 (Protocol B Borrow, Token3, NULL if unlevered)
                - pnl_fees: Fee costs (negative)
                - net_token2_hedge: Net Token2 price impact (leg2 + leg3, for hedge validation)
        """
        # Get all snapshots for this position
        snapshots = self.get_position_snapshots(position['position_id'])

        if snapshots.empty:
            return {
                'total_value': position['deployment_usd'],
                'total_pnl': 0,
                'pnl_base_apr': 0,
                'pnl_reward_apr': 0,
                'pnl_price_leg1': 0,
                'pnl_price_leg2': 0,
                'pnl_price_leg3': 0,
                'pnl_price_leg4': 0,
                'pnl_fees': 0,
                'net_token2_hedge': 0
            }

        # Extract position parameters
        deployment = position['deployment_usd']
        L_A = position['L_A']
        B_A = position['B_A']
        L_B = position['L_B']
        B_B = position.get('B_B', 0) or 0
        is_levered = position['is_levered']
        is_active = position['status'] == 'active'

        # Calculate Base APR PnL (forward-looking)
        pnl_base_apr = 0
        loop_end = len(snapshots) if is_active else len(snapshots) - 1

        for i in range(loop_end):
            current_snap = snapshots.iloc[i]

            # For active positions, last iteration uses "now" as end time
            if is_active and i == len(snapshots) - 1:
                # Round to nearest minute for consistency
                now = datetime.now().replace(second=0, microsecond=0)
                time_delta = (now - current_snap['snapshot_timestamp']).total_seconds()
            else:
                next_snap = snapshots.iloc[i + 1]
                time_delta = (next_snap['snapshot_timestamp'] - current_snap['snapshot_timestamp']).total_seconds()

            time_years = time_delta / (365 * 86400)

            # Forward-looking base rates from current snapshot
            base_lend_1A = current_snap['lend_base_apr_1A'] or 0
            base_borrow_2A = current_snap['borrow_base_apr_2A'] or 0
            base_lend_2B = current_snap['lend_base_apr_2B'] or 0
            base_borrow_3B = (current_snap['borrow_base_apr_3B'] or 0) if is_levered else 0

            # Calculate base earnings for this period (BEFORE fees)
            earn_A = deployment * L_A * base_lend_1A * time_years
            earn_B = deployment * L_B * base_lend_2B * time_years
            cost_A = deployment * B_A * base_borrow_2A * time_years
            cost_B = deployment * B_B * base_borrow_3B * time_years if is_levered else 0

            period_base = earn_A + earn_B - cost_A - cost_B
            pnl_base_apr += period_base

        # Calculate Reward APR PnL (forward-looking)
        pnl_reward_apr = 0
        for i in range(loop_end):
            current_snap = snapshots.iloc[i]

            # For active positions, last iteration uses "now" as end time
            if is_active and i == len(snapshots) - 1:
                # Round to nearest minute for consistency
                now = datetime.now().replace(second=0, microsecond=0)
                time_delta = (now - current_snap['snapshot_timestamp']).total_seconds()
            else:
                next_snap = snapshots.iloc[i + 1]
                time_delta = (next_snap['snapshot_timestamp'] - current_snap['snapshot_timestamp']).total_seconds()

            time_years = time_delta / (365 * 86400)

            # Forward-looking reward rates from current snapshot
            reward_lend_1A = current_snap['lend_reward_apr_1A'] or 0
            reward_borrow_2A = current_snap['borrow_reward_apr_2A'] or 0
            reward_lend_2B = current_snap['lend_reward_apr_2B'] or 0
            reward_borrow_3B = (current_snap['borrow_reward_apr_3B'] or 0) if is_levered else 0

            # Calculate reward earnings for this period
            reward_A = deployment * L_A * reward_lend_1A * time_years
            reward_B_borrow = deployment * B_A * reward_borrow_2A * time_years
            reward_B_lend = deployment * L_B * reward_lend_2B * time_years
            reward_C = deployment * B_B * reward_borrow_3B * time_years if is_levered else 0

            period_reward = reward_A + reward_B_borrow + reward_B_lend + reward_C
            pnl_reward_apr += period_reward

        # Calculate Price Impact PnL (leg-level for Step 6)
        # Use latest snapshot (for active) or final snapshot (for closed)
        if latest_snapshot is None:
            latest_snapshot = snapshots.iloc[-1]

        # Get latest prices for each leg
        try:
            latest_price_1A = float(latest_snapshot['price_1A']) if pd.notna(latest_snapshot.get('price_1A')) else position['entry_price_1A']
            latest_price_2A = float(latest_snapshot['price_2A']) if pd.notna(latest_snapshot.get('price_2A')) else position['entry_price_2A']
            latest_price_2B = float(latest_snapshot['price_2B']) if pd.notna(latest_snapshot.get('price_2B')) else position['entry_price_2B']
            latest_price_3B = float(latest_snapshot['price_3B']) if pd.notna(latest_snapshot.get('price_3B')) and is_levered else (position.get('entry_price_3B', 0) or 0)
        except (KeyError, TypeError):
            # Fallback to entry prices if snapshot doesn't have leg-level prices
            latest_price_1A = position['entry_price_1A']
            latest_price_2A = position.get('entry_price_2A', position['entry_price_1A'])
            latest_price_2B = position.get('entry_price_2B', position.get('entry_price_2A', position['entry_price_1A']))
            latest_price_3B = position.get('entry_price_3B', 0) or 0 if is_levered else 0

        # Leg 1: Protocol A Lend (Token1 exposure = +L_A)
        leg1_exposure_usd = deployment * L_A
        price_change_leg1 = (latest_price_1A - position['entry_price_1A']) / position['entry_price_1A'] if position['entry_price_1A'] > 0 else 0
        pnl_price_leg1 = leg1_exposure_usd * price_change_leg1

        # Leg 2: Protocol A Borrow (Token2 exposure = -B_A, short)
        leg2_exposure_usd = -deployment * B_A
        entry_price_2A = position.get('entry_price_2A', position['entry_price_1A'])  # Fallback for old data
        price_change_leg2 = (latest_price_2A - entry_price_2A) / entry_price_2A if entry_price_2A > 0 else 0
        pnl_price_leg2 = leg2_exposure_usd * price_change_leg2

        # Leg 3: Protocol B Lend (Token2 exposure = +L_B)
        leg3_exposure_usd = deployment * L_B
        entry_price_2B = position.get('entry_price_2B', entry_price_2A)  # Fallback for old data
        price_change_leg3 = (latest_price_2B - entry_price_2B) / entry_price_2B if entry_price_2B > 0 else 0
        pnl_price_leg3 = leg3_exposure_usd * price_change_leg3

        # Leg 4: Protocol B Borrow (Token3 exposure = -B_B, short, NULL if unlevered)
        if is_levered and B_B > 0:
            leg4_exposure_usd = -deployment * B_B
            entry_price_3B = position.get('entry_price_3B', 0) or 0
            price_change_leg4 = (latest_price_3B - entry_price_3B) / entry_price_3B if entry_price_3B > 0 else 0
            pnl_price_leg4 = leg4_exposure_usd * price_change_leg4
        else:
            pnl_price_leg4 = 0

        # Calculate Fee Costs (one-time upfront)
        fee_cost_2A = deployment * B_A * (position.get('entry_borrow_fee_2A', 0) or 0)
        fee_cost_3B = (deployment * B_B * (position.get('entry_borrow_fee_3B', 0) or 0)) if is_levered else 0
        pnl_fees = -(fee_cost_2A + fee_cost_3B)

        # Net Token2 Hedge (for validation)
        net_token2_hedge = pnl_price_leg2 + pnl_price_leg3

        # Total PnL
        total_pnl = pnl_base_apr + pnl_reward_apr + pnl_price_leg1 + pnl_price_leg2 + pnl_price_leg3 + pnl_price_leg4 + pnl_fees
        total_value = deployment + total_pnl

        return {
            'total_value': total_value,
            'total_pnl': total_pnl,
            'pnl_base_apr': pnl_base_apr,
            'pnl_reward_apr': pnl_reward_apr,
            'pnl_price_leg1': pnl_price_leg1,
            'pnl_price_leg2': pnl_price_leg2,
            'pnl_price_leg3': pnl_price_leg3,
            'pnl_price_leg4': pnl_price_leg4,
            'pnl_fees': pnl_fees,
            'net_token2_hedge': net_token2_hedge
        }

    def calculate_liquidation_levels(
        self,
        position: pd.Series,
        current_prices: Dict[str, float],
        current_collateral_ratios: Dict[Tuple[str, str], float],
        protocol_risk_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate liquidation risk metrics (Steps 7 & 8)

        Args:
            position: Position record
            current_prices: Current token prices
            current_collateral_ratios: Current collateral ratios {(token, protocol): ratio}
            protocol_risk_data: Optional protocol-sourced risk data (Phase 2)

        Returns:
            Dict with risk metrics including:
                - health_factor_1A_calc, health_factor_2B_calc
                - ltv_1A_calc, ltv_2B_calc
                - distance_to_liq_1A_calc, distance_to_liq_2B_calc
                - liquidation_price_1A_calc, liquidation_price_2B_calc
                - collateral_ratio_change_1A, collateral_ratio_change_2B
                - collateral_warning
        """
        deployment = position['deployment_usd']
        L_A = position['L_A']
        B_A = position['B_A']
        L_B = position['L_B']
        B_B = position.get('B_B', 0) or 0

        # Protocol A: Lend Token1, Borrow Token2
        collateral_1A_usd = deployment * L_A * current_prices.get(position['token1'], position['entry_price_1A'])
        borrow_2A_usd = deployment * B_A * current_prices.get(position['token2'], position.get('entry_price_2A', position['entry_price_1A']))

        health_factor_1A = collateral_1A_usd / borrow_2A_usd if borrow_2A_usd > 0 else float('inf')
        ltv_1A = borrow_2A_usd / collateral_1A_usd if collateral_1A_usd > 0 else 0

        # Get collateral ratio thresholds
        liq_threshold_1A = current_collateral_ratios.get((position['token1'], position['protocol_A']), position['entry_collateral_ratio_1A'])
        max_ltv_1A = 1 / liq_threshold_1A if liq_threshold_1A > 0 else 0  # Max LTV before liquidation

        # Distance to liquidation = % buffer remaining
        distance_to_liq_1A = (max_ltv_1A - ltv_1A) / max_ltv_1A if max_ltv_1A > 0 else float('inf')

        # Liquidation price: Token1 price at which LTV hits threshold
        # At liquidation: (L_A * liq_price_1A) / (B_A * price_2A) = liq_threshold_1A
        # Solving for liq_price_1A:
        price_2A = current_prices.get(position['token2'], position.get('entry_price_2A', position['entry_price_1A']))
        liquidation_price_1A = (liq_threshold_1A * borrow_2A_usd) / (deployment * L_A) if L_A > 0 else 0

        # Collateral ratio drift from entry (Step 8)
        entry_ratio_1A = position['entry_collateral_ratio_1A']
        current_ratio_1A = current_collateral_ratios.get((position['token1'], position['protocol_A']), entry_ratio_1A)
        ratio_change_1A = (current_ratio_1A - entry_ratio_1A) / entry_ratio_1A if entry_ratio_1A > 0 else 0

        # Protocol B: Lend Token2, Borrow Token3 (if levered)
        if position['is_levered'] and B_B > 0:
            collateral_2B_usd = deployment * L_B * current_prices.get(position['token2'], position.get('entry_price_2B', position.get('entry_price_2A', position['entry_price_1A'])))
            borrow_3B_usd = deployment * B_B * current_prices.get(position['token3'], position.get('entry_price_3B', 0))

            health_factor_2B = collateral_2B_usd / borrow_3B_usd if borrow_3B_usd > 0 else float('inf')
            ltv_2B = borrow_3B_usd / collateral_2B_usd if collateral_2B_usd > 0 else 0

            liq_threshold_2B = current_collateral_ratios.get((position['token2'], position['protocol_B']), position['entry_collateral_ratio_2B'])
            max_ltv_2B = 1 / liq_threshold_2B if liq_threshold_2B > 0 else 0

            distance_to_liq_2B = (max_ltv_2B - ltv_2B) / max_ltv_2B if max_ltv_2B > 0 else float('inf')

            # Liquidation price: Token2 price at which LTV hits threshold
            liquidation_price_2B = (liq_threshold_2B * borrow_3B_usd) / (deployment * L_B) if L_B > 0 else 0

            entry_ratio_2B = position['entry_collateral_ratio_2B']
            current_ratio_2B = current_collateral_ratios.get((position['token2'], position['protocol_B']), entry_ratio_2B)
            ratio_change_2B = (current_ratio_2B - entry_ratio_2B) / entry_ratio_2B if entry_ratio_2B > 0 else 0
        else:
            # Unlevered position has no Protocol B borrow
            health_factor_2B = float('inf')
            ltv_2B = 0
            distance_to_liq_2B = 1.0  # 100% safe (no borrow)
            liquidation_price_2B = 0
            ratio_change_2B = 0

        # Step 8: Collateral warning if >5% change from entry
        collateral_warning = abs(ratio_change_1A) > 0.05 or abs(ratio_change_2B) > 0.05

        return {
            'health_factor_1A_calc': health_factor_1A,
            'health_factor_2B_calc': health_factor_2B,
            'distance_to_liq_1A_calc': distance_to_liq_1A,
            'distance_to_liq_2B_calc': distance_to_liq_2B,
            'ltv_1A_calc': ltv_1A,
            'ltv_2B_calc': ltv_2B,
            'liquidation_price_1A_calc': liquidation_price_1A,
            'liquidation_price_2B_calc': liquidation_price_2B,
            'collateral_ratio_change_1A': ratio_change_1A,
            'collateral_ratio_change_2B': ratio_change_2B,
            'collateral_warning': collateral_warning
        }

    # ==================== Query Methods ====================

    def get_active_positions(self, user_id: Optional[str] = None) -> pd.DataFrame:
        """Get all active positions (optionally filtered by user)"""
        ph = self._get_placeholder()
        if user_id is not None:
            query = f"SELECT * FROM positions WHERE status = {ph} AND user_id = {ph} ORDER BY entry_timestamp DESC"
            params = ('active', user_id)
        else:
            query = f"SELECT * FROM positions WHERE status = {ph} ORDER BY entry_timestamp DESC"
            params = ('active',)

        return self._execute_query(query, params)

    def get_position_by_id(self, position_id: str) -> Optional[pd.Series]:
        """Get position by ID"""
        ph = self._get_placeholder()
        query = f"SELECT * FROM positions WHERE position_id = {ph}"
        df = self._execute_query(query, (position_id,))
        return df.iloc[0] if not df.empty else None

    def get_position_snapshots(self, position_id: str) -> pd.DataFrame:
        """Get all snapshots for a position, ordered by timestamp"""
        ph = self._get_placeholder()
        query = f"SELECT * FROM position_snapshots WHERE position_id = {ph} ORDER BY snapshot_timestamp ASC"
        return self._execute_query(query, (position_id,))

    def get_portfolio_summary(self, user_id: Optional[str] = None) -> Dict:
        """Get portfolio summary (optionally filtered by user)"""
        active_positions = self.get_active_positions(user_id)

        if active_positions.empty:
            return {
                'total_capital': 0,
                'avg_apr': 0,
                'total_earned': 0,
                'position_count': 0
            }

        total_capital = active_positions['deployment_usd'].sum()
        weighted_apr = (active_positions['deployment_usd'] * active_positions['entry_net_apr']).sum() / total_capital if total_capital > 0 else 0

        # Get latest PnL for each position from snapshots
        total_earned = 0
        for _, position in active_positions.iterrows():
            snapshots = self.get_position_snapshots(position['position_id'])
            if not snapshots.empty:
                latest_snapshot = snapshots.iloc[-1]
                total_earned += latest_snapshot.get('total_pnl', 0) or 0

        return {
            'total_capital': total_capital,
            'avg_apr': weighted_apr,
            'total_earned': total_earned,
            'position_count': len(active_positions)
        }

    # ==================== Snapshot Management ====================

    def create_snapshot(
        self,
        position_id: str,
        snapshot_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Create a snapshot for a position

        Args:
            position_id: Position UUID
            snapshot_timestamp: Optional timestamp (defaults to now, or uses rates_snapshot timestamp)

        Returns:
            snapshot_id: UUID of created snapshot
        """
        # Get position
        position = self.get_position_by_id(position_id)
        if position is None:
            raise Exception(f"Position not found: {position_id}")

        # Use provided timestamp or current time, rounded to nearest minute
        if snapshot_timestamp is None:
            snapshot_timestamp = datetime.now().replace(second=0, microsecond=0)

        # Generate snapshot ID
        snapshot_id = str(uuid.uuid4())

        # Fetch current market data from rates_snapshot at this timestamp (Step 6)
        # Fetch leg-level prices using price helper functions
        try:
            price_1A = self.get_leg_price_for_pnl(position, '1A', snapshot_timestamp)
            price_2A = self.get_leg_price_for_pnl(position, '2A', snapshot_timestamp)
            price_2B = self.get_leg_price_for_pnl(position, '2B', snapshot_timestamp)
            price_3B = self.get_leg_price_for_pnl(position, '3B', snapshot_timestamp) if position['is_levered'] else None
        except ValueError as e:
            # Fallback to entry prices if rates_snapshot doesn't have data
            print(f"Warning: Could not fetch prices for snapshot, using entry prices: {e}")
            price_1A = position['entry_price_1A']
            price_2A = position.get('entry_price_2A', position['entry_price_1A'])
            price_2B = position.get('entry_price_2B', position.get('entry_price_2A', position['entry_price_1A']))
            price_3B = position.get('entry_price_3B') if position['is_levered'] else None

        # Fetch current rates from rates_snapshot
        # TODO: Query rates_snapshot for actual rates at snapshot_timestamp
        # For now, use entry rates as placeholder
        current_rates = {
            'lend_base_apr_1A': position['entry_lend_rate_1A'],
            'lend_reward_apr_1A': 0,
            'borrow_base_apr_2A': position['entry_borrow_rate_2A'],
            'borrow_reward_apr_2A': 0,
            'lend_base_apr_2B': position['entry_lend_rate_2B'],
            'lend_reward_apr_2B': 0,
            'borrow_base_apr_3B': position.get('entry_borrow_rate_3B'),
            'borrow_reward_apr_3B': 0
        }

        # Fetch current collateral ratios
        # TODO: Query rates_snapshot for actual collateral ratios at snapshot_timestamp
        current_collateral_ratios = {
            (position['token1'], position['protocol_A']): position['entry_collateral_ratio_1A'],
            (position['token2'], position['protocol_B']): position['entry_collateral_ratio_2B']
        }

        # Build snapshot record to pass to calculate_position_value
        temp_snapshot = pd.Series({
            'price_1A': price_1A,
            'price_2A': price_2A,
            'price_2B': price_2B,
            'price_3B': price_3B,
            'snapshot_timestamp': snapshot_timestamp,
            'lend_base_apr_1A': current_rates['lend_base_apr_1A'],
            'lend_reward_apr_1A': current_rates['lend_reward_apr_1A'],
            'borrow_base_apr_2A': current_rates['borrow_base_apr_2A'],
            'borrow_reward_apr_2A': current_rates['borrow_reward_apr_2A'],
            'lend_base_apr_2B': current_rates['lend_base_apr_2B'],
            'lend_reward_apr_2B': current_rates['lend_reward_apr_2B'],
            'borrow_base_apr_3B': current_rates['borrow_base_apr_3B'],
            'borrow_reward_apr_3B': current_rates['borrow_reward_apr_3B']
        })

        # Calculate PnL (with leg-level breakdown)
        pnl = self.calculate_position_value(position, temp_snapshot)

        # Calculate risk metrics
        current_prices_dict = {
            position['token1']: price_1A,
            position['token2']: price_2A,  # Using protocol A price for risk calc
            position['token3']: price_3B if position['is_levered'] else 0
        }
        risk = self.calculate_liquidation_levels(position, current_prices_dict, current_collateral_ratios)

        # Insert snapshot (with leg-level prices, PnL, and risk metrics - Steps 6, 7, 8)
        ph = self._get_placeholder()
        query = f"""
        INSERT INTO position_snapshots (
            snapshot_id, position_id, snapshot_timestamp,
            lend_base_apr_1A, lend_reward_apr_1A, borrow_base_apr_2A, borrow_reward_apr_2A,
            lend_base_apr_2B, lend_reward_apr_2B, borrow_base_apr_3B, borrow_reward_apr_3B,
            price_1A, price_2A, price_2B, price_3B,
            current_collateral_ratio_1A, current_collateral_ratio_2B,
            total_pnl, pnl_base_apr, pnl_reward_apr,
            pnl_price_leg1, pnl_price_leg2, pnl_price_leg3, pnl_price_leg4, pnl_fees,
            health_factor_1A_calc, health_factor_2B_calc,
            distance_to_liq_1A_calc, distance_to_liq_2B_calc,
            ltv_1A_calc, ltv_2B_calc,
            liquidation_price_1A_calc, liquidation_price_2B_calc,
            collateral_ratio_change_1A, collateral_ratio_change_2B, collateral_warning,
            risk_data_source
        ) VALUES (
            {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph}, {ph},
            {ph}, {ph}, {ph}, {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph},
            {ph}, {ph}, {ph},
            {ph}
        )
        """

        params = (
            snapshot_id, position_id, snapshot_timestamp,
            current_rates['lend_base_apr_1A'], current_rates['lend_reward_apr_1A'],
            current_rates['borrow_base_apr_2A'], current_rates['borrow_reward_apr_2A'],
            current_rates['lend_base_apr_2B'], current_rates['lend_reward_apr_2B'],
            current_rates['borrow_base_apr_3B'], current_rates['borrow_reward_apr_3B'],
            price_1A, price_2A, price_2B, price_3B,
            current_collateral_ratios.get((position['token1'], position['protocol_A'])),
            current_collateral_ratios.get((position['token2'], position['protocol_B'])),
            pnl['total_pnl'], pnl['pnl_base_apr'], pnl['pnl_reward_apr'],
            pnl['pnl_price_leg1'], pnl['pnl_price_leg2'], pnl['pnl_price_leg3'], pnl['pnl_price_leg4'], pnl['pnl_fees'],
            risk['health_factor_1A_calc'], risk['health_factor_2B_calc'],
            risk['distance_to_liq_1A_calc'], risk['distance_to_liq_2B_calc'],
            risk['ltv_1A_calc'], risk['ltv_2B_calc'],
            risk['liquidation_price_1A_calc'], risk['liquidation_price_2B_calc'],
            risk['collateral_ratio_change_1A'], risk['collateral_ratio_change_2B'], risk['collateral_warning'],
            'calculated'
        )

        if not self._execute_write(query, params):
            raise Exception("Failed to create snapshot")

        return snapshot_id

    def create_snapshots_for_all_positions(
        self,
        user_id: Optional[str] = None,
        snapshot_timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Create snapshots for all active positions

        Args:
            user_id: Optional user filter (None = all users, for multi-user support later)
            snapshot_timestamp: Optional timestamp (None = use latest rates_snapshot)

        Returns:
            dict: {
                'success_count': int,
                'error_count': int,
                'snapshot_ids': list[str],
                'errors': list[dict]  # {position_id, error_message}
            }
        """
        active_positions = self.get_active_positions(user_id=user_id)

        results = {
            'success_count': 0,
            'error_count': 0,
            'snapshot_ids': [],
            'errors': []
        }

        for _, position in active_positions.iterrows():
            try:
                snapshot_id = self.create_snapshot(
                    position['position_id'],
                    snapshot_timestamp=snapshot_timestamp
                )
                results['snapshot_ids'].append(snapshot_id)
                results['success_count'] += 1
            except Exception as e:
                results['errors'].append({
                    'position_id': position['position_id'],
                    'error_message': str(e)
                })
                results['error_count'] += 1

        return results

    def backfill_snapshots(
        self,
        position_id: str,
        frequency: str = 'hourly',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        Backfill snapshots for a position

        Args:
            position_id: Position UUID
            frequency: 'hourly' or 'daily'
            start_time: Start time (defaults to position entry_timestamp)
            end_time: End time (defaults to now or close_timestamp)

        Returns:
            int: Number of snapshots created
        """
        # Get position
        position = self.get_position_by_id(position_id)
        if position is None:
            raise Exception(f"Position not found: {position_id}")

        # Determine time range
        if start_time is None:
            start_time = position['entry_timestamp']
        if end_time is None:
            end_time = position.get('close_timestamp') or datetime.now().replace(second=0, microsecond=0)

        # Generate timestamps
        delta = timedelta(hours=1) if frequency == 'hourly' else timedelta(days=1)
        timestamps = []
        current = start_time
        while current <= end_time:
            timestamps.append(current)
            current += delta

        # Create snapshots
        count = 0
        for ts in timestamps:
            # Check if snapshot already exists
            existing = self._execute_query(
                f"SELECT snapshot_id FROM position_snapshots WHERE position_id = {self._get_placeholder()} AND snapshot_timestamp = {self._get_placeholder()}",
                (position_id, ts)
            )
            if existing.empty:
                try:
                    self.create_snapshot(position_id, snapshot_timestamp=ts)
                    count += 1
                except Exception as e:
                    print(f"Failed to create snapshot at {ts}: {e}")

        print(f"✅ Backfilled {count} snapshots for position {position_id}")
        return count
