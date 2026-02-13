"""
Base class for strategy-specific calculations.

All strategy calculators must inherit from StrategyCalculatorBase and implement
the abstract methods for position calculation, APR calculation, and rebalancing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class StrategyCalculatorBase(ABC):
    """Base class for strategy-specific calculations"""

    @abstractmethod
    def get_strategy_type(self) -> str:
        """
        Returns strategy type identifier.

        Examples: 'stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending'
        """
        pass

    @abstractmethod
    def get_required_legs(self) -> int:
        """
        Returns number of legs (1, 3, or 4).

        - 1 leg: Stablecoin lending (single lend)
        - 3 legs: No-loop cross-protocol (lend, borrow, lend)
        - 4 legs: Recursive lending (lend, borrow, lend, borrow with loop)
        """
        pass

    @abstractmethod
    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers/weights for this strategy.

        Returns:
            Dict with keys: l_a, b_a, l_b, b_b (all float, use 0.0 for unused legs)

        Example:
            {
                'l_a': 1.0,   # Lend multiplier at protocol A
                'b_a': 0.67,  # Borrow multiplier at protocol A
                'l_b': 0.67,  # Lend multiplier at protocol B
                'b_b': 0.0    # Borrow multiplier at protocol B (0 if not used)
            }
        """
        pass

    @abstractmethod
    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for this strategy.

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_*, borrow_total_apr_* (base + reward combined)
            fees: Dict with borrow_fee_* (nullable, may need fallback)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        pass

    @abstractmethod
    def analyze_strategy(self, **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis returning all metrics.

        Must return dict with at minimum:
            - l_a, b_a, l_b, b_b: Position multipliers (float)
            - net_apr: Decimal net APR (float)
            - liquidation_distance: Safety buffer from liquidation (float, could be inf)
            - max_size: Max deployable size in USD (float, could be inf)
            - valid: Whether strategy is valid (bool)
            - strategy_type: Strategy identifier (str)

        Optional but recommended:
            - apr5, apr30, apr90: Time-adjusted APRs
            - days_to_breakeven: Days to recover upfront fees
            - error: Error message if not valid
        """
        pass

    @abstractmethod
    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Calculate token amounts needed to restore target weights.

        Args:
            position: Position dict with entry state
            live_rates: Current market rates
            live_prices: Current token prices

        Returns:
            Dict with rebalance instructions, or None if no rebalancing needed
        """
        pass
