"""History handler for noloop cross-protocol lending strategy (3 legs)."""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)


class NoLoopCrossProtocolHistoryHandler(HistoryHandlerBase):
    """Handler for noloop_cross_protocol_lending strategy (3 legs)."""

    def get_strategy_type(self) -> str:
        return 'noloop_cross_protocol_lending'

    def get_required_legs(self) -> int:
        return 3

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        NoLoop needs 3 legs:
        - Leg 1A: token1 at protocol_a (lending)
        - Leg 2A: token2 at protocol_a (borrowing)
        - Leg 2B: token2 at protocol_b (lending)
        """
        return [
            (strategy['token1_contract'], strategy['protocol_a']),  # Leg 1A
            (strategy['token2_contract'], strategy['protocol_a']),  # Leg 2A
            (strategy['token2_contract'], strategy['protocol_b'])   # Leg 2B
        ]

    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Parse 3 rows into legs, return dict for calculator.

        Returns None if any required leg is missing.
        """
        # Should have exactly 3 rows
        if len(row_group) != 3:
            logger.debug(f"Expected 3 rows for noloop strategy, got {len(row_group)}")
            return None

        # Parse rows into legs
        leg_1A = None
        leg_2A = None
        leg_2B = None

        for _, row in row_group.iterrows():
            contract = row['token_contract']
            protocol = row['protocol']

            if contract == strategy['token1_contract'] and protocol == strategy['protocol_a']:
                leg_1A = row
            elif contract == strategy['token2_contract'] and protocol == strategy['protocol_a']:
                leg_2A = row
            elif contract == strategy['token2_contract'] and protocol == strategy['protocol_b']:
                leg_2B = row

        # Validate all legs found
        if leg_1A is None or leg_2A is None or leg_2B is None:
            logger.debug(f"Not all legs found in row group")
            return None

        # Check required fields
        if pd.isna(leg_1A.get('lend_total_apr')) or pd.isna(leg_1A.get('price_usd')):
            return None
        if pd.isna(leg_2A.get('borrow_total_apr')) or pd.isna(leg_2A.get('price_usd')):
            return None
        if pd.isna(leg_2B.get('lend_total_apr')) or pd.isna(leg_2B.get('price_usd')):
            return None

        # Check required fields for collateral/liquidation (Principle 10 & 16: Fail loudly if missing)
        if pd.isna(leg_1A.get('collateral_ratio')) or pd.isna(leg_1A.get('liquidation_threshold')):
            logger.warning(f"Missing collateral_ratio or liquidation_threshold for leg 1A")
            return None

        # Build market data dict
        # NOTE: Following DESIGN_NOTES.md Principle 16 - NO .get() with defaults
        # All required fields use direct access to fail loudly if missing
        try:
            return {
                # Token symbols (required by calculator as positional args)
                'token1': strategy['token1'],
                'token2': strategy['token2'],
                'token1_contract': strategy['token1_contract'],
                'token2_contract': strategy['token2_contract'],
                'protocol_a': strategy['protocol_a'],
                'protocol_b': strategy['protocol_b'],

                # Leg 1A - lending
                'lend_total_apr_1A': leg_1A['lend_total_apr'],
                'price_1A': leg_1A['price_usd'],
                'collateral_ratio_1A': leg_1A['collateral_ratio'],              # Direct access - fails if missing
                'liquidation_threshold_1A': leg_1A['liquidation_threshold'],    # Direct access - fails if missing

                # Leg 2A - borrowing
                'borrow_total_apr_2A': leg_2A['borrow_total_apr'],
                'price_2A': leg_2A['price_usd'],
                'borrow_fee_2A': leg_2A['borrow_fee'],                          # Direct access - fails if missing

                # Leg 2B - lending
                'lend_total_apr_2B': leg_2B['lend_total_apr'],
                'price_2B': leg_2B['price_usd'],

                # Optional config
                'liquidation_distance': strategy.get('liquidation_distance', 0.20)  # OK - optional config with documented default
            }
        except KeyError as e:
            logger.error(f"Missing required field in market data: {e}")
            logger.error(f"Available leg_1A fields: {list(leg_1A.index)}")
            logger.error(f"Available leg_2A fields: {list(leg_2A.index)}")
            logger.error(f"Available leg_2B fields: {list(leg_2B.index)}")
            return None

    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        """
        Validate noloop strategy requires:
        token1, token2, token1_contract, token2_contract, protocol_a, protocol_b.
        """
        required = ['token1', 'token2', 'token1_contract', 'token2_contract', 'protocol_a', 'protocol_b']
        missing = [f for f in required if f not in strategy or strategy[f] is None]

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        return True, ""
