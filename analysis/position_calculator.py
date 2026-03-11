"""
Position calculator — liquidation price analysis.

APR calculations have moved to analysis/strategy_calculators/base.py.
Position sizing is handled per-strategy in the StrategyCalculatorBase subclasses.
"""

from typing import Dict, Union, Optional


class PositionCalculator:
    """Liquidation price calculator for lending and perp positions."""

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
    ) -> Dict[str, Union[float, str, None]]:
        """
        Calculate the token price at which a position would be liquidated.

        For lending/borrowing legs: solves for the price movement required to trigger
        liquidation by calculating when LTV equals LLTV.

        For perp legs: uses exchange-side liquidation distance from the constructor.
          - 'long_perp':  liq_price = lending_token_price * (1 - liq_dist_input)
          - 'short_perp': liq_price = lending_token_price * (1 + liq_dist_input)
        For perp sides, collateral_value/loan_value/borrowing_token_price/lltv are unused.

        Args:
            collateral_value: Total USD value of collateral position (unused for perp sides)
            loan_value: Total USD value of borrowed position (unused for perp sides)
            lending_token_price: Current price of lending/collateral/perp token (USD)
            borrowing_token_price: Current price of borrowing/loan token (unused for perp sides)
            lltv: Liquidation Loan-to-Value ratio as decimal (unused for perp sides)
            side: 'lending', 'borrowing', 'long_perp', or 'short_perp'
            borrow_weight: Borrow weight multiplier (default 1.0, unused for perp sides)

        Returns:
            Dict with liq_price, current_price, pct_distance, current_ltv, lltv, direction
            (current_ltv and lltv are None for perp sides)

        Raises:
            ValueError: If side is not one of the four valid values
            ValueError: If lending_token_price is not positive
        """
        # Perp legs: exchange-side liquidation, only needs the entry price
        if side in ('long_perp', 'short_perp'):
            if not lending_token_price or lending_token_price <= 0:
                raise ValueError("lending_token_price must be positive for perp liq calculation")
            if side == 'long_perp':
                liq_price = lending_token_price * (1.0 - self.liq_dist_input)
                direction = 'down'
            else:
                liq_price = lending_token_price * (1.0 + self.liq_dist_input)
                direction = 'up'
            return {
                'liq_price': liq_price,
                'current_price': lending_token_price,
                'pct_distance': (liq_price - lending_token_price) / lending_token_price,
                'current_ltv': None,
                'lltv': None,
                'direction': direction,
            }

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
