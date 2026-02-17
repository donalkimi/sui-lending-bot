"""Base class for strategy-specific historical data handlers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
import pandas as pd


class HistoryHandlerBase(ABC):
    """
    Base class for strategy-specific historical data fetching.

    Each strategy type (stablecoin_lending, noloop_cross_protocol_lending,
    recursive_lending) has its own handler that knows how to:
    - Identify which tokens/protocols to query
    - Transform raw database rows into calculator-compatible format
    - Validate strategy configuration
    """

    @abstractmethod
    def get_strategy_type(self) -> str:
        """
        Return strategy type identifier.

        Returns:
            One of: 'stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending'
        """
        pass

    @abstractmethod
    def get_required_legs(self) -> int:
        """
        Return number of legs for this strategy.

        Returns:
            1 for stablecoin, 3 for noloop, 4 for recursive
        """
        pass

    @abstractmethod
    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        Return list of (token_contract, protocol) pairs to query from database.

        Args:
            strategy: Strategy configuration dict

        Returns:
            List of tuples, e.g.:
            - 1-leg: [(token1_contract, protocol_a)]
            - 3-leg: [(token1_contract, protocol_a), (token2_contract, protocol_a),
                      (token2_contract, protocol_b)]
            - 4-leg: [(token1_contract, protocol_a), (token2_contract, protocol_a),
                      (token2_contract, protocol_b), (token3_contract, protocol_b)]
        """
        pass

    @abstractmethod
    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Transform raw database rows for one timestamp into market_data dict.

        This dict will be passed to calculator.analyze_strategy() to compute APR.

        Args:
            row_group: All rate rows for a single timestamp (filtered to required legs)
            strategy: Strategy configuration dict

        Returns:
            Dict with keys needed by calculator.analyze_strategy():
            - lend_total_apr_1A, borrow_total_apr_2A, etc.
            - price_1A, price_2A, etc.
            - collateral_ratio_1A, liquidation_threshold_1A (if applicable)
            - borrow_fee_2A, borrow_fee_3B (if applicable)

            Returns None if required data is missing (timestamp will be skipped)
        """
        pass

    @abstractmethod
    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        """
        Validate that strategy dict contains required fields for this handler.

        Args:
            strategy: Strategy configuration dict

        Returns:
            Tuple of (is_valid, error_message)
            If valid: (True, "")
            If invalid: (False, "Missing required field: token2_contract")
        """
        pass
