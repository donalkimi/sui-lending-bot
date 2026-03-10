"""History handler for perp_lending_recursive strategy (3 legs).

Leg 1A: token1 (spot, e.g. BTC) at protocol_a  →  lend (spot collateral)
Leg 2A: token2 (stablecoin)     at protocol_a  →  borrow (against spot collateral)
Leg 4B: token4 (perp proxy)     at Bluefin     →  short perp (B_B, funding stored as borrow_total_apr)
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import logging

from .base import HistoryHandlerBase

logger = logging.getLogger(__name__)


class PerpLendingRecursiveHistoryHandler(HistoryHandlerBase):
    """Handler for perp_lending_recursive strategy (3 legs)."""

    def get_strategy_type(self) -> str:
        return 'perp_lending_recursive'

    def get_required_legs(self) -> int:
        return 3

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        """
        perp_lending_recursive needs 3 legs:
        - Leg 1A: token1 (spot) at protocol_a          — spot lending collateral
        - Leg 2A: token2 (stablecoin) at protocol_a    — stablecoin borrow
        - Leg 4B: token4 (perp proxy) at protocol_b    — short perp (B_B slot)
        """
        return [
            (strategy['token1_contract'], strategy['protocol_a']),  # Leg 1A: spot lend
            (strategy['token2_contract'], strategy['protocol_a']),  # Leg 2A: stablecoin borrow
            (strategy['token4_contract'], strategy['protocol_b']),  # Leg 4B: perp short (B_B)
        ]

    def build_market_data_dict(self, row_group: pd.DataFrame, strategy: Dict) -> Optional[Dict]:
        """
        Parse 3 rows into legs, return dict for calculator.analyze_strategy().
        Returns None if any required leg is missing or has NaN required fields.
        """
        if len(row_group) != 3:
            logger.debug(f"Expected 3 rows for perp_lending_recursive strategy, got {len(row_group)}")
            return None

        leg_1a = None
        leg_2a = None
        leg_4b = None

        for _, row in row_group.iterrows():
            contract = row['token_contract']
            protocol = row['protocol']

            if contract == strategy['token1_contract'] and protocol == strategy['protocol_a']:
                leg_1a = row
            elif contract == strategy['token2_contract'] and protocol == strategy['protocol_a']:
                leg_2a = row
            elif contract == strategy['token4_contract'] and protocol == strategy['protocol_b']:
                leg_4b = row

        if leg_1a is None or leg_2a is None or leg_4b is None:
            logger.debug("Not all legs found in row group for perp_lending_recursive")
            return None

        # Validate required fields per leg
        if pd.isna(leg_1a.get('lend_total_apr')) or pd.isna(leg_1a.get('price_usd')):
            return None
        if pd.isna(leg_1a.get('collateral_ratio')) or pd.isna(leg_1a.get('liquidation_threshold')):
            logger.warning("Missing collateral_ratio or liquidation_threshold for leg 1A (spot)")
            return None
        if pd.isna(leg_2a.get('borrow_total_apr')) or pd.isna(leg_2a.get('price_usd')):
            return None
        if pd.isna(leg_4b.get('borrow_total_apr')) or pd.isna(leg_4b.get('price_usd')):
            return None

        try:
            return {
                # Token and protocol identity
                'token1':          strategy['token1'],
                'token2':          strategy['token2'],
                'token4':          strategy['token4'],
                'token1_contract': strategy['token1_contract'],
                'token2_contract': strategy['token2_contract'],
                'token4_contract': strategy['token4_contract'],
                'protocol_a':      strategy['protocol_a'],
                'protocol_b':      strategy['protocol_b'],

                # Leg 1A — spot lending (collateral for stablecoin borrow)
                'lend_total_apr_1A':         leg_1a['lend_total_apr'],
                'price_1A':                  leg_1a['price_usd'],
                'collateral_ratio_1A':        leg_1a['collateral_ratio'],
                'liquidation_threshold_1A':   leg_1a['liquidation_threshold'],

                # Leg 2A — stablecoin borrow
                'borrow_total_apr_2A': leg_2a['borrow_total_apr'],
                'price_2A':            leg_2a['price_usd'],
                'borrow_fee_2A':       leg_2a['borrow_fee'],
                'borrow_weight_2A':    leg_2a.get('borrow_weight', 1.0),

                # Leg 4B — perp short (funding rate stored as borrow_total_apr on Bluefin)
                'borrow_total_apr_3B': leg_4b['borrow_total_apr'],
                'price_3B':            leg_4b['price_usd'],

                # Leg 4B rolling avg rates (Bluefin perp only)
                'borrow_avg8hr_apr_3B':  leg_4b.get('avg8hr_borrow_total_apr'),
                'borrow_avg24hr_apr_3B': leg_4b.get('avg24hr_borrow_total_apr'),

                # Per-leg raw rates for analysis tab display (no calculator impact)
                'raw_lend_total_apr_1A':    leg_1a['lend_total_apr'],
                'raw_borrow_total_apr_2A':  leg_2a['borrow_total_apr'],
                'raw_perp_rate_3B':         leg_4b['borrow_total_apr'],
                'raw_avg8hr_perp_rate_3B':  leg_4b.get('avg8hr_borrow_total_apr'),
                'raw_avg24hr_perp_rate_3B': leg_4b.get('avg24hr_borrow_total_apr'),

                'liquidation_distance': strategy.get('liquidation_distance', 0.20),
            }
        except KeyError as e:
            logger.error(f"Missing required field in perp_lending_recursive market data: {e}")
            logger.error(f"leg_1a fields: {list(leg_1a.index)}")
            logger.error(f"leg_2a fields: {list(leg_2a.index)}")
            logger.error(f"leg_4b fields: {list(leg_4b.index)}")
            return None

    def validate_strategy_dict(self, strategy: Dict) -> Tuple[bool, str]:
        required = [
            'token1', 'token2', 'token4',
            'token1_contract', 'token2_contract', 'token4_contract',
            'protocol_a', 'protocol_b',
        ]
        missing = [f for f in required if f not in strategy or strategy[f] is None]
        if missing:
            return False, f"Missing required fields: {', '.join(missing)}"
        return True, ""
