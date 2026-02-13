"""
Stablecoin lending calculator (1-leg strategy).

Simplest strategy: just lend a stablecoin in one protocol.
No borrowing, no leverage, no liquidation risk.
"""

import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)


class StablecoinLendingCalculator(StrategyCalculatorBase):
    """
    Stablecoin lending calculator (1-leg strategy).

    Mechanics:
        - Lend stablecoin in one protocol
        - No borrowing, no cross-protocol activity
        - Just earn base lending APR + rewards

    Position multipliers:
        - L_A = 1.0 (lend $1 for every $1 deployed)
        - B_A = 0.0 (no borrowing)
        - L_B = 0.0 (no second lending)
        - B_B = 0.0 (no second borrowing)

    Risk profile:
        - No liquidation risk
        - No rebalancing needed
        - No price exposure (stablecoin only)
        - Protocol risk only
    """

    def get_strategy_type(self) -> str:
        return 'stablecoin_lending'

    def get_required_legs(self) -> int:
        return 1

    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers (trivial for stablecoin lending).

        Returns:
            Dict with l_a=1.0, all others=0.0
        """
        return {
            'l_a': 1.0,
            'b_a': 0.0,
            'l_b': 0.0,
            'b_b': 0.0  # Consistent with other strategies (use 0.0 not None)
        }

    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for stablecoin lending.

        APR = lend_total_apr_1A (base + reward already combined in database)

        Args:
            positions: Not used (only one leg, no multiplier effects)
            rates: Dict with 'lend_total_apr_1A'
            fees: Not used (no borrowing)

        Returns:
            Net APR as decimal (e.g., 0.04 = 4%)

        Raises:
            ValueError: If lend_total_apr_1A is missing
        """
        lend_total_apr = rates.get('lend_total_apr_1A')

        # Validate data quality - fail fast if missing
        if lend_total_apr is None:
            raise ValueError(
                "Missing lend_total_apr_1A for stablecoin lending strategy. "
                "This is a critical data quality issue."
            )

        return lend_total_apr

    def analyze_strategy(self,
                        token1: str,
                        protocol_a: str,
                        lend_total_apr_1A: float,
                        price_1A: float,
                        **kwargs) -> Dict[str, Any]:
        """
        Analyze stablecoin lending strategy.

        Args:
            token1: Stablecoin symbol (e.g., 'USDC')
            protocol_a: Protocol name (e.g., 'navi')
            lend_total_apr_1A: Total lending APR (base + reward)
            price_1A: Token price (should be ~$1 for stablecoins)
            **kwargs: Ignored (other strategies need more params)

        Returns:
            Strategy dict with all required fields
        """
        # Validate inputs
        if lend_total_apr_1A is None:
            return {
                'valid': False,
                'error': 'Missing lend_total_apr_1A'
            }

        if price_1A is None or price_1A <= 0:
            return {
                'valid': False,
                'error': 'Invalid or missing price_1A'
            }

        # Calculate positions (trivial)
        positions = self.calculate_positions()

        return {
            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics (no fees to amortize, so all time horizons are the same)
            'net_apr': lend_total_apr_1A,
            'apr5': lend_total_apr_1A,
            'apr30': lend_total_apr_1A,
            'apr90': lend_total_apr_1A,
            'days_to_breakeven': 0.0,  # No upfront fees

            # Risk metrics
            'liquidation_distance': float('inf'),  # No liquidation risk
            'max_size': float('inf'),  # Not limited by liquidity constraints

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),

            # Note: We don't track lending supply caps in database
            # Only borrow liquidity limits (available_borrow_usd)
            # Future: Will add supply_cap tracking
        }

    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        No rebalancing needed for stablecoin lending (no borrowed assets).

        Returns:
            None (signals no rebalancing required)
        """
        return None
