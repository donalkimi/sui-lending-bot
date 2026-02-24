"""
Strategy calculator registry and utilities.

This module provides a registry of all available strategy calculators and utilities
for accessing them by strategy type.
"""

from typing import Dict, List
from .base import StrategyCalculatorBase
from .stablecoin_lending import StablecoinLendingCalculator
from .noloop_cross_protocol import NoLoopCrossProtocolCalculator
from .recursive_lending import RecursiveLendingCalculator
from .perp_lending import PerpLendingCalculator
from .perp_borrowing import PerpBorrowingCalculator
from .perp_borrowing_recursive import PerpBorrowingRecursiveCalculator

# Global calculator registry
_CALCULATORS: Dict[str, StrategyCalculatorBase] = {}


def register_calculator(calculator_class: type) -> StrategyCalculatorBase:
    """
    Register a strategy calculator class in the global registry.

    Args:
        calculator_class: A class that inherits from StrategyCalculatorBase

    Returns:
        The instantiated calculator instance

    Example:
        >>> register_calculator(StablecoinLendingCalculator)
        <StablecoinLendingCalculator instance>
    """
    calc = calculator_class()
    strategy_type = calc.get_strategy_type()
    _CALCULATORS[strategy_type] = calc
    return calc


def get_calculator(strategy_type: str) -> StrategyCalculatorBase:
    """
    Get calculator by strategy type.

    Args:
        strategy_type: Strategy identifier (e.g., 'stablecoin_lending')

    Returns:
        The calculator instance for the given strategy type

    Raises:
        ValueError: If strategy type is not registered

    Example:
        >>> calc = get_calculator('stablecoin_lending')
        >>> calc.get_required_legs()
        1
    """
    if strategy_type not in _CALCULATORS:
        available = ', '.join(_CALCULATORS.keys())
        raise ValueError(
            f"Unknown strategy type: '{strategy_type}'. "
            f"Available types: {available}"
        )
    return _CALCULATORS[strategy_type]


def get_all_strategy_types() -> List[str]:
    """
    Get list of all registered strategy types.

    Returns:
        List of strategy type identifiers

    Example:
        >>> get_all_strategy_types()
        ['stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending']
    """
    return list(_CALCULATORS.keys())


def get_all_calculators() -> Dict[str, StrategyCalculatorBase]:
    """
    Get all registered calculators.

    Returns:
        Dict mapping strategy type to calculator instance

    Example:
        >>> calculators = get_all_calculators()
        >>> for strategy_type, calc in calculators.items():
        ...     print(f"{strategy_type}: {calc.get_required_legs()} legs")
    """
    return _CALCULATORS.copy()


# Auto-register built-in calculators on module import
# Order: simplest to most complex
register_calculator(StablecoinLendingCalculator)
register_calculator(NoLoopCrossProtocolCalculator)
register_calculator(RecursiveLendingCalculator)
register_calculator(PerpLendingCalculator)
register_calculator(PerpBorrowingCalculator)
register_calculator(PerpBorrowingRecursiveCalculator)

# Export public API
__all__ = [
    # Base class
    'StrategyCalculatorBase',

    # Calculator implementations
    'StablecoinLendingCalculator',
    'NoLoopCrossProtocolCalculator',
    'RecursiveLendingCalculator',
    'PerpLendingCalculator',
    'PerpBorrowingCalculator',
    'PerpBorrowingRecursiveCalculator',

    # Registry functions
    'register_calculator',
    'get_calculator',
    'get_all_strategy_types',
    'get_all_calculators',
]
