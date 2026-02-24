from typing import Dict, Any
from .perp_borrowing import PerpBorrowingCalculator


class PerpBorrowingRecursiveCalculator(PerpBorrowingCalculator):
    """
    Perp borrowing calculator — looped (recursive) variant.

    Recycles surplus USDC back into Protocol A each iteration.
    All positions are amplified by the geometric series factor 1/(1 - r(1-d)).

    Positions:
        q      = r * (1 - liquidation_distance)
        factor = 1 / (1 - q)

        L_A = factor          (amplified from 1.0)
        B_A = r * factor      (amplified from r)
        L_B = r * factor      (market neutral)
        B_B = 0.0

    All other logic (gross APR, net APR, analyze_strategy) is inherited
    unchanged from PerpBorrowingCalculator — the formulas are generic
    over the positions dict.
    """

    def get_strategy_type(self) -> str:
        return 'perp_borrowing_recursive'

    def calculate_positions(
        self,
        liquidation_distance: float,
        liquidation_threshold_1A: float,
        collateral_ratio_1A: float,
        borrow_weight_2A: float = 1.0,
        **kwargs
    ) -> Dict[str, float]:
        # Step 1: same base r as non-looped
        liq_max = liquidation_distance / (1.0 - liquidation_distance)
        r_safe  = liquidation_threshold_1A / ((1.0 + liq_max) * borrow_weight_2A)
        r       = min(r_safe, collateral_ratio_1A)

        # Step 2: geometric series amplifier
        # q = r(1-d), converges for any r ∈ (0,1), d ∈ (0,1)
        q      = r * (1.0 - liquidation_distance)
        factor = 1.0 / (1.0 - q)

        return {'l_a': factor, 'b_a': r * factor, 'l_b': r * factor, 'b_b': 0.0}

    def analyze_strategy(self, *args, **kwargs) -> Dict[str, Any]:
        result = super().analyze_strategy(*args, **kwargs)

        if result.get('valid'):
            # Document loop parameters for display/debugging
            liquidation_distance = kwargs.get('liquidation_distance', 0.20)
            b_a = result['b_a']
            l_a = result['l_a']
            # r = b_a / l_a  (amplifier cancels)
            r = b_a / l_a if l_a > 0 else 0.0
            q = r * (1.0 - liquidation_distance)
            result['loop_ratio']     = q
            result['loop_amplifier'] = 1.0 / (1.0 - q) if q < 1.0 else float('inf')
            result['strategy_type']  = 'perp_borrowing_recursive'

        return result
