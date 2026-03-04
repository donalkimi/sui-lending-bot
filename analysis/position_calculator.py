"""
Position calculator — liquidation price analysis.

APR calculations have moved to analysis/strategy_calculators/base.py.
Position sizing is handled per-strategy in the StrategyCalculatorBase subclasses.
"""

from typing import Dict, Union


class PositionCalculator:
    """Liquidation price calculator for lending positions."""

    def __init__(self, liquidation_distance: float = 0.30):
        """
        Args:
            liquidation_distance: Minimum safety buffer as decimal (0.20 = 20% minimum).
                                  Internally transformed: liq_max = liq_dist / (1 - liq_dist)
        """
        self.liq_dist_input = liquidation_distance
        self.liq_dist = liquidation_distance / (1 - liquidation_distance)

    def calculate_liquidation_price(
        self,
        collateral_value: float,
        loan_value: float,
        lending_token_price: float,
        borrowing_token_price: float,
        lltv: float,
        side: str,
        borrow_weight: float = 1.0
    ) -> Dict[str, Union[float, str]]:
        """
        Calculate the token price at which a position would be liquidated.

        Solves for the price movement required to trigger liquidation
        by calculating when LTV equals LLTV.

        Args:
            collateral_value: Total USD value of collateral position
            loan_value: Total USD value of borrowed position
            lending_token_price: Current price of lending/collateral token (USD)
            borrowing_token_price: Current price of borrowing/loan token (USD)
            lltv: Liquidation Loan-to-Value ratio as decimal (e.g., 0.75 for 75%)
            side: Calculate for 'lending' price drop or 'borrowing' price rise
            borrow_weight: Borrow weight multiplier (default 1.0)

        Returns:
            Dict with liq_price, current_price, pct_distance, current_ltv, lltv, direction

        Raises:
            ValueError: If side is not 'lending' or 'borrowing'
            ValueError: If token prices are not positive
        """
        if side not in ['lending', 'borrowing']:
            raise ValueError(f"side must be 'lending' or 'borrowing', got '{side}'")

        if lending_token_price <= 0 or borrowing_token_price <= 0:
            raise ValueError("Token prices must be positive")

        if collateral_value <= 0:
            current_ltv = float('inf')
        else:
            current_ltv = (loan_value * borrow_weight) / collateral_value

        current_price = lending_token_price if side == 'lending' else borrowing_token_price

        if lltv <= 0:
            return {
                'liq_price': 0.0,
                'current_price': current_price,
                'pct_distance': -1.0,
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'liquidated'
            }

        if collateral_value <= 0 or loan_value <= 0:
            return {
                'liq_price': float('inf'),
                'current_price': current_price,
                'pct_distance': float('inf'),
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'impossible'
            }

        if current_ltv >= lltv:
            return {
                'liq_price': 0.0,
                'current_price': current_price,
                'pct_distance': -1.0,
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'liquidated'
            }

        if side == 'lending':
            liq_price = lending_token_price * (current_ltv / lltv)
            direction = 'down'
        else:
            liq_price = borrowing_token_price * (lltv / current_ltv)
            direction = 'up'

        if liq_price <= 0:
            return {
                'liq_price': float('inf'),
                'current_price': current_price,
                'pct_distance': float('inf'),
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'impossible'
            }

        pct_distance = (liq_price - current_price) / current_price

        return {
            'liq_price': liq_price,
            'current_price': current_price,
            'pct_distance': pct_distance,
            'current_ltv': current_ltv,
            'lltv': lltv,
            'direction': direction
        }
