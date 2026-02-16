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
                           liq_max: float,
                           borrow_weight_2A: float = 1.0) -> Dict[str, float]:
        """
        Calculate position multipliers for no-loop cross-protocol strategy.

        Args:
            liquidation_threshold_a: LTV at which liquidation occurs (e.g., 0.80 = 80%)
            collateral_ratio_a: Max collateral factor (e.g., 0.75 = 75%)
            liq_max: Transformed liquidation distance for position sizing (e.g., 0.25 from 0.20 input)
            borrow_weight_2A: Borrow weight multiplier (e.g., 1.35 = 135%)

        Returns:
            Dict with l_a, b_a, l_b, b_b multipliers

        Example:
            liq_threshold = 0.80, liq_max = 0.25 (from 20% input), borrow_weight = 1.0
            → r_a = 0.80 / (1.25 × 1.0) = 0.64
            → borrow up to 64% base LTV
            → effective LTV = 64% × 1.0 = 64% (staying 20% away from 80%)

            With borrow_weight = 1.35:
            → r_a = 0.80 / (1.25 × 1.35) = 0.474
            → borrow up to 47.4% base LTV
            → effective LTV = 47.4% × 1.35 = 64% (still 20% away from 80%)
        """
        # No recursive leverage - linear calculation
        l_a = 1.0

        # Borrow up to liquidation_threshold with safety buffer
        # Formula: borrow_ratio = liq_threshold / ((1 + liq_max) × borrow_weight)
        # The liq_max is the transformed liquidation distance
        # The borrow_weight adjusts effective LTV, so we must divide by it
        r_a = liquidation_threshold_a / ((1.0 + liq_max) * borrow_weight_2A)

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

    def calculate_gross_apr(self,
                           positions: Dict[str, float],
                           rates: Dict[str, float]) -> float:
        """
        Calculate gross APR for no-loop strategy.

        Formula:
            gross_apr = (L_A × lend_total_apr_1A) + (L_B × lend_total_apr_2B)
                        - (B_A × borrow_total_apr_2A)

        Note: Excludes upfront fees (borrow_fee_2A).
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        lend_total_1A = rates['lend_total_apr_1A']
        lend_total_2B = rates['lend_total_apr_2B']
        borrow_total_2A = rates['borrow_total_apr_2A']

        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        return earnings - costs

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

        # Extract borrow weight from kwargs (passed by rate_analyzer)
        borrow_weight_2A = kwargs.get('borrow_weight_2A', 1.0)

        # Transform user's liquidation distance input to liq_max for position sizing
        # This ensures the user gets AT LEAST their requested protection on the lending side
        # Formula: liq_max = liq_dist / (1 - liq_dist)
        # Example: User inputs 25% → liq_max = 0.25 / 0.75 = 0.333 (33.33%)
        liq_max = liquidation_distance / (1.0 - liquidation_distance)

        # Calculate position multipliers
        positions = self.calculate_positions(
            liquidation_threshold_a=liquidation_threshold_1A,
            collateral_ratio_a=collateral_ratio_1A,
            liq_max=liq_max,
            borrow_weight_2A=borrow_weight_2A
        )

        # Calculate ALL fee-adjusted APRs using base class methods
        rates = {
            'lend_total_apr_1A': lend_total_apr_1A,
            'lend_total_apr_2B': lend_total_apr_2B,
            'borrow_total_apr_2A': borrow_total_apr_2A
        }
        fees = {
            'borrow_fee_2A': borrow_fee_2A or 0.0,
            'borrow_fee_3B': 0.0  # No 4th leg in noloop
        }
        fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(positions, rates, fees)

        # Extract all APR values from single source of truth
        apr_gross = fee_adjusted_aprs['apr_gross']
        apr_net = fee_adjusted_aprs['apr_net']
        apr5 = fee_adjusted_aprs['apr5']
        apr30 = fee_adjusted_aprs['apr30']
        apr90 = fee_adjusted_aprs['apr90']
        days_to_breakeven = fee_adjusted_aprs['days_to_breakeven']

        # Calculate max size based on available borrow liquidity
        max_size = float('inf')
        if available_borrow_2A is not None and available_borrow_2A > 0:
            # Max deployment limited by borrow liquidity
            # deployment × b_a = borrow amount in USD
            # borrow amount in USD ≤ available_borrow_2A
            max_size = available_borrow_2A / positions['b_a'] if positions['b_a'] > 0 else float('inf')

        # Extract contracts from kwargs (passed by analyzer)
        token1_contract = kwargs.get('token1_contract')
        token2_contract = kwargs.get('token2_contract')

        return {
            # Token and protocol info
            'token1': token1,
            'token2': token2,
            'token3': token2,  # NoLoop doesn't loop back, so token3 = token2
            'protocol_a': protocol_a,
            'protocol_b': protocol_b,

            # Contracts (for historical chart queries)
            'token1_contract': token1_contract,
            'token2_contract': token2_contract,
            'token3_contract': token2_contract,  # Same as token2

            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'apr_net': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': liquidation_distance,  # Store original user input for display
            'max_size': max_size,

            # Prices (required by dashboard)
            'P1_A': price_1A,
            'P2_A': price_2A,
            'P2_B': price_2B,
            'P3_B': price_2B,  # Same as P2_B since token3 = token2

            # Rates (required by dashboard)
            'lend_rate_1a': lend_total_apr_1A,
            'borrow_rate_2a': borrow_total_apr_2A,
            'lend_rate_2b': lend_total_apr_2B,
            'borrow_rate_3b': 0.0,  # No 4th leg

            # Collateral and liquidation (required by dashboard)
            'collateral_ratio_1a': collateral_ratio_1A,
            'collateral_ratio_2b': 0.0,  # No borrowing on leg B
            'liquidation_threshold_1a': liquidation_threshold_1A,
            'liquidation_threshold_2b': 0.0,  # No borrowing on leg B

            # Fees and liquidity (required by dashboard)
            'borrow_fee_2a': borrow_fee_2A or 0.0,
            'borrow_fee_3b': 0.0,  # No 4th leg
            'available_borrow_2a': available_borrow_2A,
            'available_borrow_3b': 0.0,  # No 4th leg
            'borrow_weight_2a': kwargs.get('borrow_weight_2A', 1.0),
            'borrow_weight_3b': 1.0,  # No 4th leg

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
        Only one liquidation threshold to monitor (leg 2A).

        Args:
            position: Position dict with entry data
            live_rates: Current rates
            live_prices: Current prices

        Returns:
            Dict with rebalance structure (requires_rebalance, actions, etc.)

        Raises:
            ValueError: If position data or prices are invalid

        TODO: Full implementation pending - needs tolerance threshold logic
        """
        # FAIL LOUD: Validate inputs
        if not position:
            raise ValueError("Position dict cannot be None or empty")
        if live_rates is None:
            raise ValueError("live_rates cannot be None")
        if live_prices is None:
            raise ValueError("live_prices cannot be None")

        # TODO: Implement full rebalancing logic
        # 1. Calculate target USD values: deployment × L_A, deployment × B_A, deployment × L_B
        # 2. Calculate current USD values using live prices
        # 3. Calculate drift percentage
        # 4. Check if drift exceeds tolerance threshold (e.g., 5%)
        # 5. If yes, calculate token amount deltas to restore targets
        # 6. Check liquidation distance on leg 2A

        # STUB: For now, always return no rebalancing needed
        # This will be replaced with actual tolerance-check logic
        return {
            "requires_rebalance": False,
            "actions": [],
            "reason": "Position weights within acceptable tolerance (stub implementation)"
        }
