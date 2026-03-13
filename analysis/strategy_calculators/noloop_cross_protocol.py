"""
No-loop cross-protocol lending calculator (3-leg strategy).

Lend token1 → Borrow token2 → Lend token2 (no loop back to token1).
"""

import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase, _format_lend_action, _format_borrow_action

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
                           borrow_weight_token2: float = 1.0) -> Dict[str, float]:
        """
        Calculate position multipliers for no-loop cross-protocol strategy.

        Args:
            liquidation_threshold_a: LTV at which liquidation occurs (e.g., 0.80 = 80%)
            collateral_ratio_a: Max collateral factor (e.g., 0.75 = 75%)
            liq_max: Transformed liquidation distance for position sizing (e.g., 0.25 from 0.20 input)
            borrow_weight_token2: Borrow weight multiplier (e.g., 1.35 = 135%)

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
        r_a = liquidation_threshold_a / ((1.0 + liq_max) * borrow_weight_token2)

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
            APR = (L_A × rate_token1) + (L_B × rate_token3)
                  - (B_A × rate_token2) - (B_A × borrow_fee_token2)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with rate_token1, rate_token3, rate_token2
            fees: Dict with borrow_fee_token2 (nullable in database)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)

        Raises:
            ValueError: If critical rates are missing
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        # Use total APRs (base + reward already combined in database)
        lend_total_1A = rates.get('rate_token1')
        lend_total_2B = rates.get('rate_token3')
        borrow_total_2A = rates.get('rate_token2')

        # Validate critical rates are present - fail fast
        if lend_total_1A is None:
            raise ValueError("Missing rate_token1")
        if lend_total_2B is None:
            raise ValueError("Missing rate_token3")
        if borrow_total_2A is None:
            raise ValueError("Missing rate_token2")

        # Calculate earnings and costs
        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        # Borrow fees - nullable in database schema
        # Use .get() with fallback but log warning for data quality tracking
        borrow_fee_token2 = fees.get('borrow_fee_token2')
        if borrow_fee_token2 is None:
            logger.warning(
                "Missing borrow_fee_token2 - assuming 0.0. "
                "This may indicate a data quality issue."
            )
            borrow_fee_token2 = 0.0

        fees_cost = b_a * borrow_fee_token2

        return earnings - costs - fees_cost

    def calculate_gross_apr(self,
                           positions: Dict[str, float],
                           rates: Dict[str, float]) -> float:
        """
        Calculate gross APR for no-loop strategy.

        Formula:
            gross_apr = (L_A × rate_token1) + (L_B × rate_token3)
                        - (B_A × rate_token2)

        Note: Excludes upfront fees (borrow_fee_token2).
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        lend_total_1A = rates['rate_token1']
        lend_total_2B = rates['rate_token3']
        borrow_total_2A = rates['rate_token2']

        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        return earnings - costs

    def analyze_strategy(self,
                        token1: str,
                        token2: str,
                        protocol_a: str,
                        protocol_b: str,
                        rate_token1: float,
                        rate_token2: float,
                        rate_token3: float,
                        collateral_ratio_token1: float,
                        liquidation_threshold_token1: float,
                        price_token1: float,
                        price_token2: float,
                        price_token3: float,
                        available_borrow_token2: float = None,
                        borrow_fee_token2: float = None,
                        liquidation_distance: float = 0.20,
                        **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis for no-loop cross-protocol lending.

        Args:
            token1: Stablecoin (e.g., 'USDC')
            token2: High-yield token (e.g., 'DEEP')
            protocol_a: First protocol (e.g., 'navi')
            protocol_b: Second protocol (e.g., 'suilend')
            rate_token1: Lending APR for token1 on protocol A
            rate_token2: Borrowing APR for token2 on protocol A
            rate_token3: Lending APR for token2 on protocol B
            collateral_ratio_token1: Max collateral factor for token1
            liquidation_threshold_token1: Liquidation LTV for token1
            price_token1, price_token2, price_token3: Token prices
            available_borrow_token2: Available borrow liquidity for token2 (optional)
            borrow_fee_token2: Upfront borrow fee for token2 (optional, nullable)
            liquidation_distance: Safety buffer (default 0.20 = 20%)
            **kwargs: Additional args (ignored)

        Returns:
            Complete strategy dict
        """
        # Validate inputs
        missing_fields = []
        if rate_token1 is None:
            missing_fields.append('rate_token1')
        if rate_token2 is None:
            missing_fields.append('rate_token2')
        if rate_token3 is None:
            missing_fields.append('rate_token3')
        if collateral_ratio_token1 is None:
            missing_fields.append('collateral_ratio_token1')
        if liquidation_threshold_token1 is None:
            missing_fields.append('liquidation_threshold_token1')

        if missing_fields:
            return {
                'valid': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }

        # Extract borrow weight from kwargs (passed by rate_analyzer)
        borrow_weight_token2 = kwargs.get('borrow_weight_token2', 1.0)

        # Transform user's liquidation distance input to liq_max for position sizing
        # This ensures the user gets AT LEAST their requested protection on the lending side
        # Formula: liq_max = liq_dist / (1 - liq_dist)
        # Example: User inputs 25% → liq_max = 0.25 / 0.75 = 0.333 (33.33%)
        liq_max = liquidation_distance / (1.0 - liquidation_distance)

        # Calculate position multipliers
        positions = self.calculate_positions(
            liquidation_threshold_a=liquidation_threshold_token1,
            collateral_ratio_a=collateral_ratio_token1,
            liq_max=liq_max,
            borrow_weight_token2=borrow_weight_token2
        )

        # Calculate ALL fee-adjusted APRs using base class methods
        rates = {
            'rate_token1': rate_token1,
            'rate_token3': rate_token3,
            'rate_token2': rate_token2
        }
        fees = {
            'borrow_fee_token2': borrow_fee_token2 or 0.0,
            'borrow_fee_token4': 0.0  # No 4th leg in noloop
        }
        fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(positions, rates, fees)

        # Extract all APR values from single source of truth
        apr_gross = fee_adjusted_aprs['apr_gross']
        apr_net = fee_adjusted_aprs['net_apr']
        apr5 = fee_adjusted_aprs['apr5']
        apr30 = fee_adjusted_aprs['apr30']
        apr90 = fee_adjusted_aprs['apr90']
        days_to_breakeven = fee_adjusted_aprs['days_to_breakeven']

        # Calculate max size based on available borrow liquidity
        max_size = float('inf')
        if available_borrow_token2 is not None:
            # Max deployment limited by borrow liquidity
            # deployment × b_a = borrow amount in USD
            # borrow amount in USD ≤ available_borrow_token2
            max_size = available_borrow_token2 / positions['b_a'] if positions['b_a'] > 0 else float('inf')

        # Extract contracts from kwargs (passed by analyzer)
        token1_contract = kwargs.get('token1_contract')
        token2_contract = kwargs.get('token2_contract')

        _t2_a = positions['b_a'] / price_token2 if price_token2 > 0 else 0.0

        return {
            # Token and protocol info (universal leg convention)
            'token1': token1,
            'token2': token2,
            'token3': token2,   # L_B = same volatile as B_A
            'token4': None,     # B_B = 0 (no loop back)
            'protocol_a': protocol_a,
            'protocol_b': protocol_b,

            # Contracts
            'token1_contract': token1_contract,
            'token2_contract': token2_contract,
            'token3_contract': token2_contract,  # Same as token2
            'token4_contract': None,             # B_B unused

            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'net_apr': apr_net,
            'basis_adj_net_apr': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': liquidation_distance,
            'max_size': max_size,

            # Prices
            'token1_price': price_token1,
            'token2_price': price_token2,
            'token3_price': price_token3,
            'token4_price': None,   # B_B unused

            # Token amounts (tokens per $1 deployed)
            'token1_units': positions['l_a'] / price_token1 if price_token1 > 0 else 0.0,
            'token2_units': _t2_a,
            'token3_units': _t2_a,  # same tokens as T2_A
            'token4_units': None,   # B_B unused

            # Rates
            'token1_rate': rate_token1,
            'token2_rate': rate_token2,
            'token3_rate': rate_token3,
            'token4_rate': None,    # B_B unused

            # Collateral and liquidation
            'token1_collateral_ratio': collateral_ratio_token1,
            'token3_collateral_ratio': 0.0,  # No borrowing on leg B
            'token1_liquidation_threshold': liquidation_threshold_token1,
            'token3_liquidation_threshold': 0.0,  # No borrowing on leg B

            # Fees and liquidity
            'token2_borrow_fee': borrow_fee_token2 or 0.0,
            'token4_borrow_fee': None,  # B_B unused
            'token2_available_borrow': available_borrow_token2,
            'token4_available_borrow': None,  # B_B unused
            'token2_borrow_weight': kwargs.get('borrow_weight_token2', 1.0),
            'token4_borrow_weight': None,  # B_B unused

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),
        }

    def calculate_rebalance_amounts(self,
                                   position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict,
                                   force: bool = False) -> Dict:
        """
        Calculate rebalance amounts for 3-leg strategy.

        Maintains constant USD values for L_A, B_A, L_B (no B_B).
        Only one liquidation threshold to monitor (leg 2A).

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

        p1 = live_prices.get('price_token1')  # stablecoin
        p2 = live_prices.get('price_token2')  # volatile
        p3 = live_prices.get('price_token3')  # volatile (= token2)

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

        exit_token1 = D * l_a / p1 if p1 else float(position['entry_token1_amount'])
        exit_token2 = D * b_a / p2
        exit_token3 = D * l_b / p3

        delta1 = exit_token1 - float(position['entry_token1_amount'])
        delta2 = exit_token2 - float(position['entry_token2_amount'])
        delta3 = exit_token3 - float(position['entry_token3_amount'])

        t1 = position.get('token1', 'token1')
        t2 = position.get('token2', 'token2')
        t3 = position.get('token3', 'token3')

        action1 = _format_lend_action(delta1, t1)
        action2 = _format_borrow_action(delta2, t2)
        action3 = _format_lend_action(delta3, t3)

        from config.settings import REBALANCE_THRESHOLD
        from analysis.strategy_calculators.base import _liq_delta, _build_reason

        if force:
            requires_rebalance = True
        else:
            # Use per-token stored baseline liq dists (set at deployment)
            # entry_liquidation_distance_token2 is the actual liq dist for the borrow leg at entry
            d_token2 = float(position.get('entry_liquidation_distance_token2') or 0)
            lltv_a = float(position.get('entry_token1_liquidation_threshold') or 0)
            bw_a = float(position.get('entry_token2_borrow_weight') or 1.0)
            e1 = float(position.get('entry_token1_amount') or 0)
            e2 = float(position.get('entry_token2_amount') or 0)

            # token1/token2: Protocol A only (no B_B borrow in noloop)
            d1 = _liq_delta(d_token2, e1, p1, e2, p2, lltv_a, bw_a)

            token_deltas = {}
            if d1 != 0.0:
                token_deltas['token1/token2'] = d1

            requires_rebalance = any(v >= REBALANCE_THRESHOLD for v in token_deltas.values())
            reason = _build_reason(token_deltas, REBALANCE_THRESHOLD) if token_deltas else 'insufficient price data'

        return {
            'requires_rebalance': requires_rebalance,
            'actions': [a for a in [action2, action3] if a and a != 'No change'],
            'reason': reason,
            'exit_token1_amount': exit_token1,
            'exit_token2_amount': exit_token2,
            'exit_token3_amount': exit_token3,
            'exit_token4_amount': None,
            'action_token1': action1,
            'action_token2': action2,
            'action_token3': action3,
            'action_token4': None,
        }
