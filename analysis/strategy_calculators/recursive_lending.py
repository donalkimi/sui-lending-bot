"""
Recursive lending calculator (4-leg strategy with loop).

Extracted from existing position_calculator.py logic.
Market-neutral strategy with geometric series convergence.
"""

import logging
from typing import Dict, Any, Optional
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)


class RecursiveLendingCalculator(StrategyCalculatorBase):
    """
    Recursive lending calculator (4-leg strategy with loop).

    Mechanics:
        1. Lend token1 (stablecoin) in Protocol A
        2. Borrow token2 (high-yield) from Protocol A
        3. Lend token2 in Protocol B
        4. Borrow token3 (stablecoin) from Protocol B
        5. Loop back: Convert token3 → token1 (1:1 for stablecoins)
        6. Geometric series convergence creates recursive leverage

    Position multipliers:
        - L_A = 1 / (1 - r_A × r_B) (recursive leverage formula)
        - B_A = L_A × r_A
        - L_B = B_A
        - B_B = L_B × r_B

    Risk profile:
        - Liquidation risk on both legs (2A and 3B)
        - Complex rebalancing (4 legs)
        - Market neutral (token1 = token3, cancels price exposure)
        - Two protocol risks
        - Higher leverage magnifies APR
    """

    def __init__(self, liquidation_distance: float = 0.20):
        """
        Initialize the recursive lending calculator.

        Args:
            liquidation_distance: Minimum safety buffer as decimal (0.20 = 20% minimum)
                                This is transformed internally to ensure proper protection.
        """
        # Store original user input for display/reporting
        self.liq_dist_input = liquidation_distance

        # Transform user's minimum liquidation distance to liq_max for internal use
        # Formula: liq_max = liq_dist / (1 - liq_dist)
        # Example: 0.20 → 0.25
        self.liq_dist = liquidation_distance / (1 - liquidation_distance)

    def get_strategy_type(self) -> str:
        return 'recursive_lending'

    def get_required_legs(self) -> int:
        return 4

    def calculate_positions(self,
                           liquidation_threshold_a: float,
                           liquidation_threshold_b: float,
                           collateral_ratio_a: float,
                           collateral_ratio_b: float,
                           borrow_weight_a: float = 1.0,
                           borrow_weight_b: float = 1.0,
                           protocol_a: Optional[str] = None,
                           protocol_b: Optional[str] = None,
                           token1: Optional[str] = None,
                           token2: Optional[str] = None,
                           **kwargs) -> Dict[str, float]:
        """
        Calculate recursive position sizes that converge to steady state.

        Strategy (market neutral - token1 must be stablecoin):
            1. Lend l_a(0) = 1.0 of token1 (STABLECOIN) in Protocol A
            2. Borrow b_a(0) = l_a * r_A of token2 (HIGH-YIELD) from Protocol A
            3. Lend l_b(0) = b_a of token2 (HIGH-YIELD) in Protocol B
            4. Borrow b_b(0) = l_b * r_B of token1 (STABLECOIN) from Protocol B
            5. Deposit b_b as l_a(1) back into Protocol A
            6. Repeat infinitely...

        Args:
            liquidation_threshold_a: Liquidation LTV for Protocol A (e.g., 0.75 = 75%)
            liquidation_threshold_b: Liquidation LTV for Protocol B (e.g., 0.80 = 80%)
            collateral_ratio_a: Max LTV for Protocol A (e.g., 0.70 = 70%)
            collateral_ratio_b: Max LTV for Protocol B (e.g., 0.75 = 75%)
            borrow_weight_a: Borrow weight multiplier for token2 (default 1.0)
            borrow_weight_b: Borrow weight multiplier for token3 (default 1.0)
            protocol_a, protocol_b: Protocol names (optional, for debug messages)
            token1, token2: Token names (optional, for debug messages)

        Returns:
            Dict with l_a, b_a, l_b, b_b multipliers
        """
        # Use liquidation threshold with safety buffer and borrow weights
        r_A = (liquidation_threshold_a / borrow_weight_a) / (1 + self.liq_dist)
        r_B = (liquidation_threshold_b / borrow_weight_b) / (1 + self.liq_dist)

        # Geometric series convergence
        # l_a = 1 + r_A*r_B + (r_A*r_B)^2 + ... = 1 / (1 - r_A*r_B)
        l_a = 1.0 / (1.0 - r_A * r_B)
        b_a = l_a * r_A
        l_b = b_a  # All borrowed token2 is lent in Protocol B
        b_b = l_b * r_B

        # Calculate effective LTV
        effective_ltv_A = (b_a / l_a) * borrow_weight_a
        effective_ltv_B = (b_b / l_b) * borrow_weight_b

        # AUTO-ADJUSTMENT: Bring effective LTV down to 99.5% of maxCF if exceeded
        adjusted_A = False
        adjusted_B = False

        # Build context strings for debug messages
        context_A = f" [{protocol_a} - Lend {token1}]" if protocol_a and token1 else ""
        context_B = f" [{protocol_b} - Lend {token2}]" if protocol_b and token2 else ""

        if effective_ltv_A > collateral_ratio_a:
            logger.warning(
                f"Adjusting r_A{context_A}: effective_LTV_A ({effective_ltv_A:.4f}) > "
                f"maxCF_A ({collateral_ratio_a:.4f}). Setting to {collateral_ratio_a * 0.995:.4f}"
            )
            r_A = (collateral_ratio_a * 0.995) / borrow_weight_a
            adjusted_A = True

        if effective_ltv_B > collateral_ratio_b:
            logger.warning(
                f"Adjusting r_B{context_B}: effective_LTV_B ({effective_ltv_B:.4f}) > "
                f"maxCF_B ({collateral_ratio_b:.4f}). Setting to {collateral_ratio_b * 0.995:.4f}"
            )
            r_B = (collateral_ratio_b * 0.995) / borrow_weight_b
            adjusted_B = True

        # Recalculate positions if any adjustment was made
        if adjusted_A or adjusted_B:
            l_a = 1.0 / (1.0 - r_A * r_B)
            b_a = l_a * r_A
            l_b = b_a
            b_b = l_b * r_B

        return {
            'l_a': l_a,
            'b_a': b_a,
            'l_b': l_b,
            'b_b': b_b
        }

    def calculate_net_apr(self,
                         positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for recursive lending strategy.

        Formula:
            APR = (L_A × lend_total_apr_1A) + (L_B × lend_total_apr_2B)
                  - (B_A × borrow_total_apr_2A) - (B_B × borrow_total_apr_3B)
                  - (B_A × borrow_fee_2A) - (B_B × borrow_fee_3B)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_1A, lend_total_apr_2B,
                   borrow_total_apr_2A, borrow_total_apr_3B
            fees: Dict with borrow_fee_2A, borrow_fee_3B (nullable)

        Returns:
            Net APR as decimal
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']
        b_b = positions['b_b']

        # Extract rates
        lend_total_1A = rates.get('lend_total_apr_1A')
        lend_total_2B = rates.get('lend_total_apr_2B')
        borrow_total_2A = rates.get('borrow_total_apr_2A')
        borrow_total_3B = rates.get('borrow_total_apr_3B')

        # Validate critical rates
        if lend_total_1A is None:
            raise ValueError("Missing lend_total_apr_1A")
        if lend_total_2B is None:
            raise ValueError("Missing lend_total_apr_2B")
        if borrow_total_2A is None:
            raise ValueError("Missing borrow_total_apr_2A")
        if borrow_total_3B is None:
            raise ValueError("Missing borrow_total_apr_3B")

        # Earnings from lending
        earn_A = l_a * lend_total_1A
        earn_B = l_b * lend_total_2B

        # Costs from borrowing
        cost_A = b_a * borrow_total_2A
        cost_B = b_b * borrow_total_3B

        # Gross APR (before fees)
        gross_apr = earn_A + earn_B - cost_A - cost_B

        # Borrow fees (with fallback and warnings)
        borrow_fee_2A = fees.get('borrow_fee_2A')
        if borrow_fee_2A is None:
            logger.warning("Missing borrow_fee_2A - assuming 0.0")
            borrow_fee_2A = 0.0

        borrow_fee_3B = fees.get('borrow_fee_3B')
        if borrow_fee_3B is None:
            logger.warning("Missing borrow_fee_3B - assuming 0.0")
            borrow_fee_3B = 0.0

        # Fee cost (annualized)
        fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B

        # Net APR (after fees)
        return gross_apr - fee_cost

    def analyze_strategy(self,
                        token1: str,
                        token2: str,
                        token3: str,
                        protocol_a: str,
                        protocol_b: str,
                        lend_total_apr_1A: float,
                        borrow_total_apr_2A: float,
                        lend_total_apr_2B: float,
                        borrow_total_apr_3B: float,
                        collateral_ratio_1A: float,
                        collateral_ratio_2B: float,
                        liquidation_threshold_1A: float,
                        liquidation_threshold_2B: float,
                        price_1A: float,
                        price_2A: float,
                        price_2B: float,
                        price_3B: float,
                        available_borrow_2A: float = None,
                        available_borrow_3B: float = None,
                        borrow_fee_2A: float = None,
                        borrow_fee_3B: float = None,
                        borrow_weight_2A: float = 1.0,
                        borrow_weight_3B: float = 1.0,
                        **kwargs) -> Dict[str, Any]:
        """
        Complete analysis of recursive lending strategy.

        Args:
            token1: Stablecoin (starting lend, market neutral)
            token2: High-yield token (borrowed for yield)
            token3: Closing stablecoin (borrowed from Protocol B, converted to token1)
            protocol_a, protocol_b: Protocol names
            lend_total_apr_1A, etc.: Total APRs (base + reward)
            collateral_ratio_1A, collateral_ratio_2B: Max collateral factors
            liquidation_threshold_1A, liquidation_threshold_2B: Liquidation LTVs
            price_1A, price_2A, price_2B, price_3B: Token prices
            available_borrow_2A, available_borrow_3B: Available borrow liquidity
            borrow_fee_2A, borrow_fee_3B: Upfront borrow fees (nullable)
            borrow_weight_2A, borrow_weight_3B: Borrow weight multipliers

        Returns:
            Complete strategy dict
        """
        try:
            # Calculate position sizes
            positions = self.calculate_positions(
                liquidation_threshold_a=liquidation_threshold_1A,
                liquidation_threshold_b=liquidation_threshold_2B,
                collateral_ratio_a=collateral_ratio_1A,
                collateral_ratio_b=collateral_ratio_2B,
                borrow_weight_a=borrow_weight_2A,
                borrow_weight_b=borrow_weight_3B,
                protocol_a=protocol_a,
                protocol_b=protocol_b,
                token1=token1,
                token2=token2
            )

            # Calculate max deployable size based on liquidity constraints
            max_size = float('inf')
            if available_borrow_2A is not None and available_borrow_3B is not None:
                b_a = positions['b_a']
                b_b = positions['b_b']

                max_size_2A = available_borrow_2A / b_a if b_a > 0 else float('inf')
                max_size_3B = available_borrow_3B / b_b if b_b > 0 else float('inf')

                # Take the minimum (most restrictive constraint)
                max_size = min(max_size_2A, max_size_3B)

            # Calculate net APR
            rates = {
                'lend_total_apr_1A': lend_total_apr_1A,
                'lend_total_apr_2B': lend_total_apr_2B,
                'borrow_total_apr_2A': borrow_total_apr_2A,
                'borrow_total_apr_3B': borrow_total_apr_3B
            }
            fees = {
                'borrow_fee_2A': borrow_fee_2A or 0.0,
                'borrow_fee_3B': borrow_fee_3B or 0.0
            }
            net_apr = self.calculate_net_apr(positions, rates, fees)

            # TODO: Calculate fee-adjusted APRs for different time horizons
            # For now, use net_apr as placeholder
            apr5 = net_apr
            apr30 = net_apr
            apr90 = net_apr
            days_to_breakeven = 0.0

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
                'liquidation_distance': self.liq_dist_input,
                'max_size': max_size,

                # Metadata
                'valid': True,
                'strategy_type': self.get_strategy_type(),
                'error': None
            }

        except (ValueError, ZeroDivisionError) as e:
            return {
                'valid': False,
                'error': str(e),
                'strategy_type': self.get_strategy_type()
            }

    def calculate_rebalance_amounts(self,
                                   position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Calculate rebalance amounts for 4-leg recursive strategy.

        Maintains constant USD values for L_A, B_A, L_B, B_B.

        Args:
            position: Position dict with entry data
            live_rates: Current rates
            live_prices: Current prices

        Returns:
            Dict with rebalance instructions

        Note:
            Not yet implemented - placeholder for future development
        """
        # TODO: Implement rebalancing logic for 4 legs
        # Most complex: maintain all 4 leg USD values
        # Two liquidation thresholds to monitor (legs 2A and 3B)
        raise NotImplementedError("Rebalancing logic not yet implemented for recursive_lending")
