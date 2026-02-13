"""
No-loop cross-protocol lending calculator (3-leg strategy).

Lend token1 → Borrow token2 → Lend token2 (no loop back to token1).
"""

import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)


class NoLoopCrossProtocolCalculator(StrategyCalculatorBase):
    """
    No-loop cross-protocol lending calculator (3-leg strategy).

    Mechanics:
        1. Lend token1 (stablecoin) in Protocol A
        2. Borrow token2 (high-yield) from Protocol A (using token1 as collateral)
        3. Lend token2 in Protocol B
        4. No loop back - position stays exposed to token2

    Position multipliers:
        - L_A = 1.0 (lend token1)
        - B_A = L_A × liquidation_threshold_A / (1 + liq_dist)
        - L_B = B_A (lend borrowed token2)
        - B_B = 0.0 (no borrow back)

    Risk profile:
        - Liquidation risk on leg 2A (if token2 price drops)
        - Rebalancing needed (token2 price changes)
        - Token2 price exposure
        - Two protocol risks
    """

    def get_strategy_type(self) -> str:
        return 'noloop_cross_protocol_lending'

    def get_required_legs(self) -> int:
        return 3

    def calculate_positions(self,
                           liquidation_threshold_a: float,
                           collateral_ratio_a: float,
                           liquidation_distance: float = 0.20) -> Dict[str, float]:
        """
        Calculate position multipliers for no-loop cross-protocol strategy.

        Args:
            liquidation_threshold_a: LTV at which liquidation occurs (e.g., 0.80 = 80%)
            collateral_ratio_a: Max collateral factor (e.g., 0.75 = 75%)
            liquidation_distance: Safety buffer (default 0.20 = 20%)

        Returns:
            Dict with l_a, b_a, l_b, b_b multipliers

        Example:
            liq_threshold = 0.80, liq_dist = 0.20
            → r_a = 0.80 / 1.20 = 0.667
            → borrow up to 66.7% LTV (staying 20% away from 80% liquidation)
        """
        # No recursive leverage - linear calculation
        l_a = 1.0

        # Borrow up to liquidation_threshold with safety buffer
        # Formula: borrow_ratio = liq_threshold / (1 + safety_buffer)
        r_a = liquidation_threshold_a / (1.0 + liquidation_distance)

        # Use minimum of calculated ratio and collateral factor
        # (Collateral factor is typically lower than liquidation threshold)
        b_a = l_a * min(r_a, collateral_ratio_a)

        # Lend all borrowed tokens in protocol B
        l_b = b_a

        return {
            'l_a': l_a,
            'b_a': b_a,
            'l_b': l_b,
            'b_b': 0.0  # No 4th leg - no loop back (use 0.0 not None for consistency)
        }

    def calculate_net_apr(self,
                         positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for no-loop cross-protocol strategy.

        Formula:
            APR = (L_A × lend_total_apr_1A) + (L_B × lend_total_apr_2B)
                  - (B_A × borrow_total_apr_2A) - (B_A × borrow_fee_2A)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_1A, lend_total_apr_2B, borrow_total_apr_2A
            fees: Dict with borrow_fee_2A (nullable in database)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)

        Raises:
            ValueError: If critical rates are missing
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        # Use total APRs (base + reward already combined in database)
        lend_total_1A = rates.get('lend_total_apr_1A')
        lend_total_2B = rates.get('lend_total_apr_2B')
        borrow_total_2A = rates.get('borrow_total_apr_2A')

        # Validate critical rates are present - fail fast
        if lend_total_1A is None:
            raise ValueError("Missing lend_total_apr_1A")
        if lend_total_2B is None:
            raise ValueError("Missing lend_total_apr_2B")
        if borrow_total_2A is None:
            raise ValueError("Missing borrow_total_apr_2A")

        # Calculate earnings and costs
        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        # Borrow fees - nullable in database schema
        # Use .get() with fallback but log warning for data quality tracking
        borrow_fee_2A = fees.get('borrow_fee_2A')
        if borrow_fee_2A is None:
            logger.warning(
                "Missing borrow_fee_2A - assuming 0.0. "
                "This may indicate a data quality issue."
            )
            borrow_fee_2A = 0.0

        fees_cost = b_a * borrow_fee_2A

        return earnings - costs - fees_cost

    def analyze_strategy(self,
                        token1: str,
                        token2: str,
                        protocol_a: str,
                        protocol_b: str,
                        lend_total_apr_1A: float,
                        borrow_total_apr_2A: float,
                        lend_total_apr_2B: float,
                        collateral_ratio_1A: float,
                        liquidation_threshold_1A: float,
                        price_1A: float,
                        price_2A: float,
                        price_2B: float,
                        available_borrow_2A: float = None,
                        borrow_fee_2A: float = None,
                        liquidation_distance: float = 0.20,
                        **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis for no-loop cross-protocol lending.

        Args:
            token1: Stablecoin (e.g., 'USDC')
            token2: High-yield token (e.g., 'DEEP')
            protocol_a: First protocol (e.g., 'navi')
            protocol_b: Second protocol (e.g., 'suilend')
            lend_total_apr_1A: Lending APR for token1 on protocol A
            borrow_total_apr_2A: Borrowing APR for token2 on protocol A
            lend_total_apr_2B: Lending APR for token2 on protocol B
            collateral_ratio_1A: Max collateral factor for token1
            liquidation_threshold_1A: Liquidation LTV for token1
            price_1A, price_2A, price_2B: Token prices
            available_borrow_2A: Available borrow liquidity for token2 (optional)
            borrow_fee_2A: Upfront borrow fee for token2 (optional, nullable)
            liquidation_distance: Safety buffer (default 0.20 = 20%)
            **kwargs: Additional args (ignored)

        Returns:
            Complete strategy dict
        """
        # Validate inputs
        missing_fields = []
        if lend_total_apr_1A is None:
            missing_fields.append('lend_total_apr_1A')
        if borrow_total_apr_2A is None:
            missing_fields.append('borrow_total_apr_2A')
        if lend_total_apr_2B is None:
            missing_fields.append('lend_total_apr_2B')
        if collateral_ratio_1A is None:
            missing_fields.append('collateral_ratio_1A')
        if liquidation_threshold_1A is None:
            missing_fields.append('liquidation_threshold_1A')

        if missing_fields:
            return {
                'valid': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }

        # Calculate position multipliers
        positions = self.calculate_positions(
            liquidation_threshold_a=liquidation_threshold_1A,
            collateral_ratio_a=collateral_ratio_1A,
            liquidation_distance=liquidation_distance
        )

        # Calculate net APR
        rates = {
            'lend_total_apr_1A': lend_total_apr_1A,
            'lend_total_apr_2B': lend_total_apr_2B,
            'borrow_total_apr_2A': borrow_total_apr_2A
        }
        fees = {
            'borrow_fee_2A': borrow_fee_2A or 0.0
        }
        net_apr = self.calculate_net_apr(positions, rates, fees)

        # Calculate max size based on available borrow liquidity
        max_size = float('inf')
        if available_borrow_2A is not None and available_borrow_2A > 0:
            # Max deployment limited by borrow liquidity
            # deployment × b_a = borrow amount in USD
            # borrow amount in USD ≤ available_borrow_2A
            max_size = available_borrow_2A / positions['b_a'] if positions['b_a'] > 0 else float('inf')

        # Calculate fee-adjusted APRs (simplified for now)
        # TODO: Implement time-adjusted APRs (5/30/90 day horizons) - needs fee amortization logic
        apr5 = net_apr  # Placeholder
        apr30 = net_apr
        apr90 = net_apr
        days_to_breakeven = 0.0  # Placeholder

        return {
            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'net_apr': net_apr,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': liquidation_distance,
            'max_size': max_size,

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),
        }

    def calculate_rebalance_amounts(self,
                                   position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Calculate rebalance amounts for 3-leg strategy.

        Maintains constant USD values for L_A, B_A, L_B (no B_B).

        Args:
            position: Position dict with entry data
            live_rates: Current rates
            live_prices: Current prices

        Returns:
            Dict with rebalance token amounts for each leg

        Note:
            Not yet implemented - placeholder for future development
        """
        # TODO: Implement rebalancing logic
        # Calculate target USD values based on multipliers
        # Calculate current USD values using live prices
        # Return token amount deltas to restore targets
        raise NotImplementedError("Rebalancing logic not yet implemented for noloop_cross_protocol")
