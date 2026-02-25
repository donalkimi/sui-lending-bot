"""History handler for perp borrowing strategy (3 legs).

Shared by both perp_borrowing and perp_borrowing_recursive — leg structure is identical.

Legs:
    1A: token1 (stablecoin) at protocol_a  →  lend (USDC collateral)
    2A: token2 (volatile)   at protocol_a  →  borrow (token sold spot)
    3B: token3 (perp)       at Bluefin     →  lend rate = long perp funding
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)


class PerpBorrowingHistoryHandler(HistoryHandlerBase):
    """Handler for perp_borrowing and perp_borrowing_recursive strategies (3 legs)."""

    def get_strategy_type(self) -> str:
        return 'perp_borrowing'

    def get_required_legs(self) -> int:
        return 3

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        Perp borrowing needs 3 legs:
        - Leg 1A: token1 (stablecoin) at protocol_a  (lending USDC as collateral)
        - Leg 2A: token2 (volatile)   at protocol_a  (borrowing token2 to sell)
        - Leg 3B: token3 (perp)       at protocol_b  (long perp on Bluefin)
        """
        return [
            (strategy['token1_contract'], strategy['protocol_a']),  # Leg 1A: stablecoin lend
            (strategy['token2_contract'], strategy['protocol_a']),  # Leg 2A: token2 borrow
            (strategy['token3_contract'], strategy['protocol_b']),  # Leg 3B: perp long (Bluefin)
        ]

    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Parse 3 rows into legs, return dict for calculator.analyze_strategy().

        Returns None if any required leg is missing or has NaN required fields.
        """
        if len(row_group) != 3:
            logger.debug(f"Expected 3 rows for perp_borrowing strategy, got {len(row_group)}")
            return None

        leg_1A = None
        leg_2A = None
        leg_3B = None

        for _, row in row_group.iterrows():
            contract = row['token_contract']
            protocol = row['protocol']

            if contract == strategy['token1_contract'] and protocol == strategy['protocol_a']:
                leg_1A = row
            elif contract == strategy['token2_contract'] and protocol == strategy['protocol_a']:
                leg_2A = row
            elif contract == strategy['token3_contract'] and protocol == strategy['protocol_b']:
                leg_3B = row

        if leg_1A is None or leg_2A is None or leg_3B is None:
            logger.debug("Not all legs found in row group for perp_borrowing")
            return None

        # Validate required fields per leg
        if pd.isna(leg_1A.get('lend_total_apr')) or pd.isna(leg_1A.get('price_usd')):
            return None
        if pd.isna(leg_1A.get('collateral_ratio')) or pd.isna(leg_1A.get('liquidation_threshold')):
            logger.warning("Missing collateral_ratio or liquidation_threshold for leg 1A")
            return None
        if pd.isna(leg_2A.get('borrow_total_apr')) or pd.isna(leg_2A.get('price_usd')):
            return None
        if pd.isna(leg_3B.get('lend_total_apr')) or pd.isna(leg_3B.get('price_usd')):
            return None

        # Build dict matching PerpBorrowingCalculator.analyze_strategy() signature
        # Direct field access per DESIGN_NOTES.md — fails loudly on missing fields
        try:
            return {
                # Token and protocol identity
                'token1': strategy['token1'],
                'token2': strategy['token2'],
                'token3': strategy['token3'],
                'token1_contract': strategy['token1_contract'],
                'token2_contract': strategy['token2_contract'],
                'token3_contract': strategy['token3_contract'],
                'protocol_a': strategy['protocol_a'],
                'protocol_b': strategy['protocol_b'],

                # Leg 1A — stablecoin lend
                'lend_total_apr_1A': leg_1A['lend_total_apr'],
                'price_1A': leg_1A['price_usd'],
                'collateral_ratio_1A': leg_1A['collateral_ratio'],
                'liquidation_threshold_1A': leg_1A['liquidation_threshold'],

                # Leg 2A — token2 borrow
                'borrow_total_apr_2A': leg_2A['borrow_total_apr'],
                'price_2A': leg_2A['price_usd'],
                'borrow_fee_2A': leg_2A['borrow_fee'],

                # Leg 3B — long perp (Bluefin)
                'lend_total_apr_3B': leg_3B['lend_total_apr'],
                'price_3B': leg_3B['price_usd'],

                # Leg 3B rolling avg rates (Bluefin perp only — None for other protocols)
                'lend_avg8hr_apr_3B':  leg_3B.get('avg8hr_lend_total_apr'),
                'lend_avg24hr_apr_3B': leg_3B.get('avg24hr_lend_total_apr'),

                # Per-leg raw rates for analysis tab display (no calculator impact)
                'raw_lend_total_apr_1A':    leg_1A['lend_total_apr'],
                'raw_borrow_total_apr_2A':  leg_2A['borrow_total_apr'],
                'raw_perp_rate_3B':         leg_3B['lend_total_apr'],
                'raw_avg8hr_perp_rate_3B':  leg_3B.get('avg8hr_lend_total_apr'),
                'raw_avg24hr_perp_rate_3B': leg_3B.get('avg24hr_lend_total_apr'),

                # Optional config with documented default
                'liquidation_distance': strategy.get('liquidation_distance', 0.20),
            }
        except KeyError as e:
            logger.error(f"Missing required field in perp_borrowing market data: {e}")
            logger.error(f"leg_1A fields: {list(leg_1A.index)}")
            logger.error(f"leg_2A fields: {list(leg_2A.index)}")
            logger.error(f"leg_3B fields: {list(leg_3B.index)}")
            return None

    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        """
        Validate perp_borrowing strategy dict.

        Requires: token1, token2, token3 (perp), all three contracts, protocol_a, protocol_b.
        """
        required = [
            'token1', 'token2', 'token3',
            'token1_contract', 'token2_contract', 'token3_contract',
            'protocol_a', 'protocol_b',
        ]
        missing = [f for f in required if f not in strategy or strategy[f] is None]

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"

        return True, ""
