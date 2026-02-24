"""
Strategy history handlers registry.

This module provides a registry pattern for strategy-specific historical data handlers,
mirroring the design of analysis/strategy_calculators/.
"""

from typing import Dict, List
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)

# Import handler implementations
from .stablecoin_lending import StablecoinLendingHistoryHandler
from .noloop_cross_protocol import NoLoopCrossProtocolHistoryHandler
from .recursive_lending import RecursiveLendingHistoryHandler
from .perp_borrowing import PerpBorrowingHistoryHandler
from .perp_lending import PerpLendingHistoryHandler


# Global handler registry
_HANDLERS: Dict[str, HistoryHandlerBase] = {}


def register_handler(handler_class: type) -> HistoryHandlerBase:
    """
    Register a history handler class in the global registry.

    Args:
        handler_class: Class that inherits from HistoryHandlerBase

    Returns:
        Instantiated handler instance
    """
    handler = handler_class()
    strategy_type = handler.get_strategy_type()

    if strategy_type in _HANDLERS:
        logger.warning(f"Overwriting existing handler for strategy type: {strategy_type}")

    _HANDLERS[strategy_type] = handler
    logger.debug(f"Registered history handler: {strategy_type}")

    return handler


def get_handler(strategy_type: str) -> HistoryHandlerBase:
    """
    Get handler by strategy type.

    Args:
        strategy_type: Strategy type identifier

    Returns:
        Handler instance for the strategy type

    Raises:
        ValueError: If strategy_type is not registered
    """
    if strategy_type not in _HANDLERS:
        available = ', '.join(_HANDLERS.keys())
        raise ValueError(
            f"Unknown strategy type: '{strategy_type}'. "
            f"Available types: {available}"
        )
    return _HANDLERS[strategy_type]


def get_all_strategy_types() -> List[str]:
    """Get list of all registered strategy types."""
    return list(_HANDLERS.keys())


def get_all_handlers() -> Dict[str, HistoryHandlerBase]:
    """Get dictionary of all registered handlers."""
    return _HANDLERS.copy()


# Auto-register built-in handlers on module import
register_handler(StablecoinLendingHistoryHandler)
register_handler(NoLoopCrossProtocolHistoryHandler)
register_handler(RecursiveLendingHistoryHandler)
register_handler(PerpBorrowingHistoryHandler)                          # registers 'perp_borrowing'
_HANDLERS['perp_borrowing_recursive'] = _HANDLERS['perp_borrowing']   # reuse same 3-leg handler
register_handler(PerpLendingHistoryHandler)                            # registers 'perp_lending'

logger.info(f"Registered {len(_HANDLERS)} strategy history handlers: {get_all_strategy_types()}")


__all__ = [
    'HistoryHandlerBase',
    'StablecoinLendingHistoryHandler',
    'NoLoopCrossProtocolHistoryHandler',
    'RecursiveLendingHistoryHandler',
    'PerpBorrowingHistoryHandler',
    'PerpLendingHistoryHandler',
    'register_handler',
    'get_handler',
    'get_all_strategy_types',
    'get_all_handlers',
]
