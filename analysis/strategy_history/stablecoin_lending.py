"""History handler for stablecoin lending strategy (1 leg)."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)


class StablecoinLendingHistoryHandler(HistoryHandlerBase):
    """Handler for stablecoin_lending strategy (1 leg)."""

    def get_strategy_type(self) -> str:
        return 'stablecoin_lending'

    def get_required_legs(self) -> int:
        return 1

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        Stablecoin lending only needs token1 at protocol_a.

        Returns: [(token1_contract, protocol_a)]
        """
        return [(strategy['token1_contract'], strategy['protocol_a'])]

    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Extract single leg data for stablecoin lending.

        Only needs lending rate and price for token1 at protocol_a.
        """
        # Should only have 1 row for 1-leg strategy
        if len(row_group) != 1:
            logger.debug(f"Expected 1 row for stablecoin strategy, got {len(row_group)}")
            return None

        row = row_group.iloc[0]

        # Check required fields present
        required_fields = ['lend_total_apr', 'price_usd']
        if any(pd.isna(row.get(f)) for f in required_fields):
            logger.debug(f"Missing required fields in row")
            return None

        # Build market data dict for calculator
        return {
            'token1': strategy['token1'],  # Symbol (required by calculator)
            'token1_contract': strategy['token1_contract'],
            'protocol_a': strategy['protocol_a'],
            'lend_total_apr_1A': row['lend_total_apr'],
            'price_1A': row['price_usd']
        }

    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        """
        Validate stablecoin strategy requires: token1, token1_contract, protocol_a.
        """
        required = ['token1', 'token1_contract', 'protocol_a']
        missing = [f for f in required if f not in strategy or strategy[f] is None]

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        return True, ""
