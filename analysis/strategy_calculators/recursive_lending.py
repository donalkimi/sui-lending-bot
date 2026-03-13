"""
Recursive lending calculator (4-leg strategy with loop).

Extracted from existing position_calculator.py logic.
Market-neutral strategy with geometric series convergence.
"""

import logging
from typing import Dict, Any, Optional
from .base import StrategyCalculatorBase, MIN_TOKEN_DELTA, _format_lend_action, _format_borrow_action

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
            logger.debug(
                f"Adjusting r_A{context_A}: effective_LTV_A ({effective_ltv_A:.4f}) > "
                f"maxCF_A ({collateral_ratio_a:.4f}). Setting to {collateral_ratio_a * 0.995:.4f}"
            )
            r_A = (collateral_ratio_a * 0.995) / borrow_weight_a
            adjusted_A = True

        if effective_ltv_B > collateral_ratio_b:
            logger.debug(
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
            APR = (L_A × rate_token1) + (L_B × rate_token3)
                  - (B_A × rate_token2) - (B_B × rate_token4)
                  - (B_A × borrow_fee_token2) - (B_B × borrow_fee_token4)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with rate_token1, rate_token3,
                   rate_token2, rate_token4
            fees: Dict with borrow_fee_token2, borrow_fee_token4 (nullable)

        Returns:
            Net APR as decimal
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']
        b_b = positions['b_b']

        # Extract rates
        lend_total_1A = rates.get('rate_token1')
        lend_total_2B = rates.get('rate_token3')
        borrow_total_2A = rates.get('rate_token2')
        borrow_total_3B = rates.get('rate_token4')

        # Validate critical rates
        if lend_total_1A is None:
            raise ValueError("Missing rate_token1")
        if lend_total_2B is None:
            raise ValueError("Missing rate_token3")
        if borrow_total_2A is None:
            raise ValueError("Missing rate_token2")
        if borrow_total_3B is None:
            raise ValueError("Missing rate_token4")

        # Earnings from lending
        earn_A = l_a * lend_total_1A
        earn_B = l_b * lend_total_2B

        # Costs from borrowing
        cost_A = b_a * borrow_total_2A
        cost_B = b_b * borrow_total_3B

        # Gross APR (before fees)
        gross_apr = earn_A + earn_B - cost_A - cost_B

        # Borrow fees (with fallback and warnings)
        borrow_fee_token2 = fees.get('borrow_fee_token2')
        if borrow_fee_token2 is None:
            logger.warning("Missing borrow_fee_token2 - assuming 0.0")
            borrow_fee_token2 = 0.0

        borrow_fee_token4 = fees.get('borrow_fee_token4')
        if borrow_fee_token4 is None:
            logger.warning("Missing borrow_fee_token4 - assuming 0.0")
            borrow_fee_token4 = 0.0

        # Fee cost (annualized)
        fee_cost = b_a * borrow_fee_token2 + b_b * borrow_fee_token4

        # Net APR (after fees)
        return gross_apr - fee_cost

    def calculate_gross_apr(self,
                           positions: Dict[str, float],
                           rates: Dict[str, float]) -> float:
        """
        Calculate gross APR for recursive lending strategy.

        Formula:
            gross_apr = (L_A × rate_token1) + (L_B × rate_token3)
                        - (B_A × rate_token2) - (B_B × rate_token4)

        Note: Excludes upfront fees (borrow_fee_token2, borrow_fee_token4).
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']
        b_b = positions['b_b']

        # Extract and validate rates
        lend_total_1A = rates['rate_token1']
        lend_total_2B = rates['rate_token3']
        borrow_total_2A = rates['rate_token2']
        borrow_total_3B = rates['rate_token4']

        # Earnings from lending
        earn_A = l_a * lend_total_1A
        earn_B = l_b * lend_total_2B

        # Costs from borrowing
        cost_A = b_a * borrow_total_2A
        cost_B = b_b * borrow_total_3B

        return earn_A + earn_B - cost_A - cost_B

    def analyze_strategy(self,
                        token1: str,
                        token2: str,
                        token4: str,  # B_B leg: closing stablecoin (was token3)
                        protocol_a: str,
                        protocol_b: str,
                        rate_token1: float,
                        rate_token2: float,
                        rate_token3: float,
                        rate_token4: float,
                        collateral_ratio_token1: float,
                        collateral_ratio_token3: float,
                        liquidation_threshold_token1: float,
                        liquidation_threshold_token3: float,
                        price_token1: float,
                        price_token2: float,
                        price_token3: float,
                        price_token4: float,
                        available_borrow_token2: float = None,
                        available_borrow_token4: float = None,
                        borrow_fee_token2: float = None,
                        borrow_fee_token4: float = None,
                        borrow_weight_token2: float = 1.0,
                        borrow_weight_token4: float = 1.0,
                        **kwargs) -> Dict[str, Any]:
        """
        Complete analysis of recursive lending strategy.

        Args:
            token1: Stablecoin (starting lend, market neutral)
            token2: High-yield token (borrowed for yield)
            token4: Closing stablecoin (borrowed from Protocol B, converted to token1)
            protocol_a, protocol_b: Protocol names
            rate_token1, etc.: Total APRs (base + reward)
            collateral_ratio_token1, collateral_ratio_token3: Max collateral factors
            liquidation_threshold_token1, liquidation_threshold_token3: Liquidation LTVs
            price_token1, price_token2, price_token3, price_token4: Token prices
            available_borrow_token2, available_borrow_token4: Available borrow liquidity
            borrow_fee_token2, borrow_fee_token4: Upfront borrow fees (nullable)
            borrow_weight_token2, borrow_weight_token4: Borrow weight multipliers

        Returns:
            Complete strategy dict
        """
        try:
            # Calculate position sizes
            positions = self.calculate_positions(
                liquidation_threshold_a=liquidation_threshold_token1,
                liquidation_threshold_b=liquidation_threshold_token3,
                collateral_ratio_a=collateral_ratio_token1,
                collateral_ratio_b=collateral_ratio_token3,
                borrow_weight_a=borrow_weight_token2,
                borrow_weight_b=borrow_weight_token4,
                protocol_a=protocol_a,
                protocol_b=protocol_b,
                token1=token1,
                token2=token2
            )

            # Calculate max deployable size based on liquidity constraints
            max_size = float('inf')
            if available_borrow_token2 is not None and available_borrow_token4 is not None:
                b_a = positions['b_a']
                b_b = positions['b_b']

                max_size_2A = available_borrow_token2 / b_a if b_a > 0 else float('inf')
                max_size_3B = available_borrow_token4 / b_b if b_b > 0 else float('inf')

                # Take the minimum (most restrictive constraint)
                max_size = min(max_size_2A, max_size_3B)

            rates = {
                'rate_token1': rate_token1,
                'rate_token3': rate_token3,
                'rate_token2': rate_token2,
                'rate_token4': rate_token4
            }
            fees = {
                'borrow_fee_token2': borrow_fee_token2,
                'borrow_fee_token4': borrow_fee_token4
            }
            fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(positions, rates, fees)
            apr_gross = fee_adjusted_aprs['apr_gross']
            net_apr = fee_adjusted_aprs['net_apr']
            apr5 = fee_adjusted_aprs['apr5']
            apr30 = fee_adjusted_aprs['apr30']
            apr90 = fee_adjusted_aprs['apr90']
            days_to_breakeven = fee_adjusted_aprs['days_to_breakeven']

            _t2_a = positions['b_a'] / price_token2 if price_token2 > 0 else 0.0

            # Extract contracts from kwargs (passed by rate_analyzer)
            token1_contract = kwargs.get('token1_contract')
            token2_contract = kwargs.get('token2_contract')
            token4_contract = kwargs.get('token4_contract')

            return {
                # Token identity (universal leg convention)
                'token1': token1,
                'token2': token2,
                'token3': token2,           # L_B = same volatile as B_A
                'token4': token4,           # B_B = closing stablecoin
                'protocol_a': protocol_a,
                'protocol_b': protocol_b,

                # Contracts
                'token1_contract': token1_contract,
                'token2_contract': token2_contract,
                'token3_contract': token2_contract,  # Same token as token2
                'token4_contract': token4_contract,

                # Position multipliers
                'l_a': positions['l_a'],
                'b_a': positions['b_a'],
                'l_b': positions['l_b'],
                'b_b': positions['b_b'],

                # APR metrics
                'net_apr': net_apr,
                'basis_adj_net_apr': net_apr,
                'apr5': apr5,
                'apr30': apr30,
                'apr90': apr90,
                'days_to_breakeven': days_to_breakeven,

                # Risk metrics
                'liquidation_distance': self.liq_dist_input,
                'max_size': max_size,

                # Prices
                'token1_price': price_token1,
                'token2_price': price_token2,
                'token3_price': price_token3,   # L_B: volatile token at protocol_B
                'token4_price': price_token4,   # B_B: closing stablecoin

                # Token amounts (tokens per $1 deployed)
                'token1_units': positions['l_a'] / price_token1 if price_token1 > 0 else 0.0,
                'token2_units': _t2_a,
                'token3_units': _t2_a,      # same tokens as B_A (lend same volatile in B)
                'token4_units': positions['b_b'] / price_token4 if price_token4 > 0 else 0.0,

                # Rates
                'token1_rate': rate_token1,
                'token2_rate': rate_token2,
                'token3_rate': rate_token3,
                'token4_rate': rate_token4,

                # Collateral and liquidation
                'token1_collateral_ratio': collateral_ratio_token1,
                'token3_collateral_ratio': collateral_ratio_token3,
                'token1_liquidation_threshold': liquidation_threshold_token1,
                'token3_liquidation_threshold': liquidation_threshold_token3,

                # Fees and liquidity
                'token2_borrow_fee': borrow_fee_token2,
                'token4_borrow_fee': borrow_fee_token4,
                'token2_available_borrow': available_borrow_token2,
                'token4_available_borrow': available_borrow_token4,
                'token2_borrow_weight': borrow_weight_token2,
                'token4_borrow_weight': borrow_weight_token4,

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
                                   live_prices: Dict,
                                   force: bool = False) -> Dict:
        """
        Calculate rebalance amounts for 4-leg recursive strategy.

        Maintains constant USD values for L_A, B_A, L_B, B_B.
        Two liquidation thresholds to monitor (legs 2A and 3B).

        Args:
            position: Position dict with entry data
            live_rates: Current rates
            live_prices: Current prices

        Returns:
            Dict with rebalance structure (requires_rebalance, actions, exit_token*_amount, action_token*)

        Raises:
            ValueError: If position data or prices are invalid
        """
        if not position:
            raise ValueError("Position dict cannot be None or empty")
        if live_rates is None:
            raise ValueError("live_rates cannot be None")
        if live_prices is None:
            raise ValueError("live_prices cannot be None")

        D   = float(position['deployment_usd'])
        l_a = float(position['l_a'])
        b_a = float(position['b_a'])
        l_b = float(position['l_b'])
        b_b = float(position['b_b'])

        p1 = live_prices.get('price_token1')  # stablecoin (≈ $1)
        p2 = live_prices.get('price_token2')  # volatile
        p3 = live_prices.get('price_token3')  # volatile (= token2, same price)
        p4 = live_prices.get('price_token4')  # stablecoin (≈ $1)

        if not p2 or not p3:
            return {
                'requires_rebalance': True,
                'actions': [],
                'reason': 'Missing live volatile prices — cannot compute rebalance amounts',
                'exit_token1_amount': None, 'exit_token2_amount': None,
                'exit_token3_amount': None, 'exit_token4_amount': None,
                'action_token1': None, 'action_token2': None,
                'action_token3': None, 'action_token4': None,
            }

        # Target amounts (weight × deployment / price)
        exit_token1 = D * l_a / p1 if p1 else float(position['entry_token1_amount'])
        exit_token2 = D * b_a / p2
        exit_token3 = D * l_b / p3
        exit_token4 = D * b_b / p4 if (b_b and p4) else float(position['entry_token4_amount'] or 0)

        # Deltas vs current segment opening amounts
        delta1 = exit_token1 - float(position['entry_token1_amount'])
        delta2 = exit_token2 - float(position['entry_token2_amount'])
        if position['entry_token3_amount'] is None:
            raise ValueError(
                f"entry_token3_amount is NULL for recursive_lending position (l_b={l_b}) — "
                f"this leg must always have a token amount. "
                f"Position likely has wrong strategy_type or was deployed with l_b=0."
            )
        delta3 = exit_token3 - float(position['entry_token3_amount'])
        delta4 = exit_token4 - float(position['entry_token4_amount'] or 0)

        t1 = position.get('token1', 'token1')
        t2 = position.get('token2', 'token2')
        t3 = position.get('token3', 'token3')
        t4 = position.get('token4', 'token4')

        action1 = _format_lend_action(delta1, t1)
        action2 = _format_borrow_action(delta2, t2)
        action3 = _format_lend_action(delta3, t3)
        action4 = None if not b_b else _format_borrow_action(delta4, t4)

        from config.settings import REBALANCE_THRESHOLD
        from analysis.strategy_calculators.base import _liq_delta, _build_reason

        if force:
            requires_rebalance = True
        else:
            # Use per-token stored baseline liq dists (set at deployment)
            d_token2 = float(position.get('entry_liquidation_distance_token2') or 0)
            d_token3 = float(position.get('entry_liquidation_distance_token3') or 0)
            lltv_a = float(position.get('entry_token1_liquidation_threshold') or 0)
            lltv_b = float(position.get('entry_token3_liquidation_threshold') or 0)
            bw_a = float(position.get('entry_token2_borrow_weight') or 1.0)
            bw_b = float(position.get('entry_token4_borrow_weight') or 1.0)
            e1 = float(position.get('entry_token1_amount') or 0)
            e2 = float(position.get('entry_token2_amount') or 0)
            e3 = float(position.get('entry_token3_amount') or 0)
            e4 = float(position.get('entry_token4_amount') or 0)

            # token1/token2: Protocol A (stablecoin collateral vs volatile borrow)
            d1 = _liq_delta(d_token2, e1, p1, e2, p2, lltv_a, bw_a)
            # token3/token4: Protocol B (volatile collateral vs stablecoin borrow)
            d3 = _liq_delta(d_token3, e3, p3, e4, p4, lltv_b, bw_b)

            token_deltas = {}
            if d1 != 0.0:
                token_deltas['token1/token2'] = d1
            if d3 != 0.0:
                token_deltas['token3/token4'] = d3

            requires_rebalance = any(v >= REBALANCE_THRESHOLD for v in token_deltas.values())
            reason = _build_reason(token_deltas, REBALANCE_THRESHOLD) if token_deltas else 'insufficient price data'

        return {
            'requires_rebalance': requires_rebalance,
            'actions': [a for a in [action2, action3, action4] if a and a != 'No change'],
            'reason': reason,
            'exit_token1_amount': exit_token1,
            'exit_token2_amount': exit_token2,
            'exit_token3_amount': exit_token3,
            'exit_token4_amount': exit_token4 if b_b else None,
            'action_token1': action1,
            'action_token2': action2,
            'action_token3': action3,
            'action_token4': action4,
        }
