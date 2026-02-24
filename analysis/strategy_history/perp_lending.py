"""History handler for perp_lending strategy (2 legs)."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)


class PerpLendingHistoryHandler(HistoryHandlerBase):
    """
    Handler for perp_lending strategy (2 legs).

    Leg 1A: Buy and lend spot token (e.g. SUI) at protocol_a
    Leg 3B: Short equivalent perp (e.g. SUI-USDC-PERP) on Bluefin

    No borrowing on spot side, no lending on perp side.
    """

    def get_strategy_type(self) -> str:
        return 'perp_lending'

    def get_required_legs(self) -> int:
        return 2

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        perp_lending needs 2 legs:
        - Leg 1A: token1 at protocol_a (spot lending)
        - Leg 3B: token3 at protocol_b (perp short — funding rate stored as borrow_total_apr)
        """
        return [
            (strategy['token1_contract'], strategy['protocol_a']),  # Leg 1A: spot lending
            (strategy['token3_contract'], strategy['protocol_b']),  # Leg 3B: perp short
        ]

    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Parse 2 rows into legs, return dict for calculator.

        Returns None if any required leg is missing.
        """
        if len(row_group) != 2:
            logger.debug(f"Expected 2 rows for perp_lending strategy, got {len(row_group)}")
            return None

        leg_1a = None
        leg_3b = None

        for _, row in row_group.iterrows():
            contract = row['token_contract']
            protocol = row['protocol']

            if contract == strategy['token1_contract'] and protocol == strategy['protocol_a']:
                leg_1a = row
            elif contract == strategy['token3_contract'] and protocol == strategy['protocol_b']:
                leg_3b = row

        if leg_1a is None or leg_3b is None:
            logger.debug("Not all legs found in row group for perp_lending")
            return None

        if pd.isna(leg_1a.get('lend_total_apr')) or pd.isna(leg_1a.get('price_usd')):
            return None
        if pd.isna(leg_3b.get('borrow_total_apr')) or pd.isna(leg_3b.get('price_usd')):
            return None

        try:
            return {
                # Identity
                'token1':          strategy['token1'],
                'token3':          strategy['token3'],
                'token1_contract': strategy['token1_contract'],
                'token3_contract': strategy['token3_contract'],
                'protocol_a':      strategy['protocol_a'],
                'protocol_b':      strategy['protocol_b'],

                # Leg 1A — spot lending
                'lend_total_apr_1A': leg_1a['lend_total_apr'],
                'price_1A':          leg_1a['price_usd'],

                # Leg 3B — perp short (funding rate stored as borrow_total_apr on Bluefin)
                'borrow_total_apr_3B': leg_3b['borrow_total_apr'],
                'price_3B':            leg_3b['price_usd'],

                # Optional config
                'liquidation_distance': strategy.get('liquidation_distance', 0.20),
            }
        except KeyError as e:
            logger.error(f"Missing required field in perp_lending market data: {e}")
            return None

    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        """
        Validate perp_lending strategy requires:
        token1, token3, token1_contract, token3_contract, protocol_a, protocol_b.
        """
        required = ['token1', 'token3', 'token1_contract', 'token3_contract', 'protocol_a', 'protocol_b']
        missing = [f for f in required if f not in strategy or strategy[f] is None]

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        return True, ""
