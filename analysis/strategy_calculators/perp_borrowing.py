from typing import Dict, Any
from .base import StrategyCalculatorBase
from config import settings


class PerpBorrowingCalculator(StrategyCalculatorBase):
    """
    Perp borrowing calculator (3-leg strategy, non-looped).

    Legs:
        1A: Lend token1 (stablecoin) at Protocol A
        2A: Borrow token2 (volatile) at Protocol A, sell spot
        3B: Long token3 perp on Bluefin (market-neutral offset to short spot)

    Positions:
        L_A = 1.0,  B_A = r,  L_B = r,  B_B = 0.0

    Where:
        liq_max = liquidation_distance / (1 - liquidation_distance)
        r_safe  = liquidation_threshold_1A / ((1 + liq_max) * borrow_weight_2A)
        r       = min(r_safe, collateral_ratio_1A)

    Liquidation risks:
        - Protocol A: token2 price rises (debt value exceeds collateral)
        - Bluefin long perp: token2 price drops (margin call on long)
    """

    def get_strategy_type(self) -> str:
        return 'perp_borrowing'

    def get_required_legs(self) -> int:
        return 3

    def calculate_positions(
        self,
        liquidation_distance: float,
        liquidation_threshold_1A: float,
        collateral_ratio_1A: float,
        borrow_weight_2A: float = 1.0,
        **kwargs
    ) -> Dict[str, float]:
        liq_max = liquidation_distance / (1.0 - liquidation_distance)
        r_safe  = liquidation_threshold_1A / ((1.0 + liq_max) * borrow_weight_2A)
        r       = min(r_safe, collateral_ratio_1A)

        return {'l_a': 1.0, 'b_a': r, 'l_b': r, 'b_b': 0.0}

    def calculate_gross_apr(self, positions: Dict, rates: Dict) -> float:
        """
        gross = L_A × lend_1A + L_B × lend_3B − B_A × borrow_2A

        lend_total_apr_3B is the stored Bluefin rate for the long perp.
        Positive = longs earn. Negative = longs pay.
        """
        earnings = (positions['l_a'] * rates['lend_total_apr_1A']
                  + positions['l_b'] * rates['lend_total_apr_3B'])
        costs    =  positions['b_a'] * rates['borrow_total_apr_2A']
        return earnings - costs

    def calculate_net_apr(self, positions: Dict, rates: Dict, fees: Dict) -> float:
        """
        net = gross
            − L_B × 2 × BLUEFIN_TAKER_FEE   (long perp entry + exit)
            − B_A × borrow_fee_2A             (upfront borrow fee at Protocol A)
        """
        gross      = self.calculate_gross_apr(positions, rates)
        perp_fees  = positions['l_b'] * 2.0 * settings.BLUEFIN_TAKER_FEE
        borrow_fee = (fees.get('borrow_fee_2A') or 0.0) * positions['b_a']
        return gross - perp_fees - borrow_fee

    def analyze_strategy(
        self,
        token1: str,
        token2: str,
        token3: str,
        protocol_a: str,
        protocol_b: str,
        lend_total_apr_1A: float,
        borrow_total_apr_2A: float,
        lend_total_apr_3B: float,
        collateral_ratio_1A: float,
        liquidation_threshold_1A: float,
        price_1A: float,
        price_2A: float,
        price_3B: float,
        liquidation_distance: float = 0.20,
        **kwargs
    ) -> Dict[str, Any]:
        # Validate required inputs
        missing = [n for n, v in [
            ('lend_total_apr_1A', lend_total_apr_1A),
            ('borrow_total_apr_2A', borrow_total_apr_2A),
            ('lend_total_apr_3B', lend_total_apr_3B),
            ('collateral_ratio_1A', collateral_ratio_1A),
            ('liquidation_threshold_1A', liquidation_threshold_1A),
        ] if v is None]
        if missing:
            return {'valid': False, 'error': f"Missing: {', '.join(missing)}"}

        borrow_weight_2A = kwargs.get('borrow_weight_2A', 1.0)
        borrow_fee_2A    = kwargs.get('borrow_fee_2A') or 0.0
        available_borrow = kwargs.get('available_borrow_2A')

        positions = self.calculate_positions(
            liquidation_distance=liquidation_distance,
            liquidation_threshold_1A=liquidation_threshold_1A,
            collateral_ratio_1A=collateral_ratio_1A,
            borrow_weight_2A=borrow_weight_2A,
        )
        rates = {
            'lend_total_apr_1A':   lend_total_apr_1A,
            'borrow_total_apr_2A': borrow_total_apr_2A,
            'lend_total_apr_3B':   lend_total_apr_3B,
        }
        fees = {'borrow_fee_2A': borrow_fee_2A}

        l_a, b_a, l_b = positions['l_a'], positions['b_a'], positions['l_b']
        gross_apr = self.calculate_gross_apr(positions, rates)
        net_apr   = self.calculate_net_apr(positions, rates, fees)

        # Time-adjusted APRs: borrow origination fee + perp entry/exit fee
        perp_fee = l_b * 2.0 * settings.BLUEFIN_TAKER_FEE
        total_upfront_fee = b_a * borrow_fee_2A + perp_fee
        apr5  = gross_apr - total_upfront_fee * 365.0 / 5
        apr30 = gross_apr - total_upfront_fee * 365.0 / 30
        apr90 = gross_apr - total_upfront_fee * 365.0 / 90
        days_to_breakeven = (total_upfront_fee * 365.0 / gross_apr) if gross_apr > 0 else float('inf')

        max_size = (available_borrow / b_a) if (available_borrow and b_a > 0) else float('inf')

        return {
            # Identity
            'token1': token1, 'token2': token2, 'token3': token3,
            'protocol_a': protocol_a, 'protocol_b': protocol_b,
            'token1_contract': kwargs.get('token1_contract'),
            'token2_contract': kwargs.get('token2_contract'),
            'token3_contract': kwargs.get('token3_contract'),

            # Positions
            'l_a': l_a, 'b_a': b_a, 'l_b': l_b, 'b_b': 0.0,

            # APR
            'apr_gross': gross_apr,
            'apr_net':   net_apr,
            'stablecoin_lending_apr': l_a * lend_total_apr_1A,
            'token2_borrow_apr':      b_a * borrow_total_apr_2A,
            'funding_rate_apr':       l_b * lend_total_apr_3B,
            'perp_fees_apr':          l_b * 2.0 * settings.BLUEFIN_TAKER_FEE,
            'apr5':  apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk
            'liquidation_distance': liquidation_distance,
            'has_lending_liq_risk': True,   # Protocol A liq if token2 price rises
            'has_perp_liq_risk':    True,   # Bluefin long liq if token2 price drops
            'max_size':             max_size,

            # Prices
            'P1_A': price_1A,
            'P2_A': price_2A,
            'P2_B': price_2A,   # token2 not on Bluefin spot; reuse same price
            'P3_B': price_3B,

            # Rates
            'lend_rate_1a':   lend_total_apr_1A,
            'borrow_rate_2a': borrow_total_apr_2A,
            'lend_rate_2b':   0.0,
            'borrow_rate_3b': lend_total_apr_3B,

            # Collateral / liquidation
            'collateral_ratio_1a':      collateral_ratio_1A,
            'liquidation_threshold_1a': liquidation_threshold_1A,

            # Fees / liquidity
            'borrow_fee_2a':       borrow_fee_2A,
            'available_borrow_2a': available_borrow,
            'borrow_weight_2a':    borrow_weight_2A,

            # Metadata
            'valid':         True,
            'strategy_type': self.get_strategy_type(),
        }

    def calculate_rebalance_amounts(self, position, current_prices,
                                    target_liquidation_distance, **kwargs):
        return {'requires_rebalance': False}
