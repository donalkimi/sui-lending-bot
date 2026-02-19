"""
Bluefin Perpetual Markets Reader

Fetches perp funding rates from perp_margin_rates table (not from Bluefin API directly).
The table is populated by main_perp_refresh.py which runs hourly.
"""
import pandas as pd
from typing import Tuple
from datetime import datetime
from data.rate_tracker import RateTracker
from config import settings
from utils.time_helpers import to_datetime_str, to_seconds


class BluefinReader:
    """
    Reader for Bluefin perpetual funding rates.

    Unlike other protocol readers that fetch from APIs, this queries the
    perp_margin_rates database table.
    """

    def __init__(self, timestamp: int):
        """
        Initialize BluefinReader.

        Args:
            timestamp: Unix timestamp in seconds (REQUIRED per DESIGN_NOTES.md #1)
        """
        self.timestamp = timestamp
        self.tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch perp funding rates from perp_margin_rates table.

        Returns DataFrames in the same format as other protocols.

        Returns:
            (lend_df, borrow_df, collateral_df)
        """
        # Get rates for the current hour (rounded down)
        # Examples: at 13:01 → 13:00, at 13:00 → 13:00, at 12:59 → 12:00
        ts_datetime = datetime.fromtimestamp(self.timestamp)
        rates_hour = ts_datetime.replace(minute=0, second=0, microsecond=0)
        rates_hour_str = to_datetime_str(to_seconds(rates_hour))

        conn = self.tracker._get_connection()

        try:
            cursor = conn.cursor()

            # Query perp_margin_rates table
            # Use placeholder pattern for database compatibility
            ph = '%s' if self.tracker.use_cloud else '?'
            query = f"""
                SELECT token_contract, base_token, funding_rate_annual
                FROM perp_margin_rates
                WHERE timestamp = {ph} AND protocol = {ph}
            """
            cursor.execute(query, (rates_hour_str, 'Bluefin'))

            rows = cursor.fetchall()

            if not rows:
                print(f"\t\t  No funding rates found for {rates_hour_str}")
                # Return empty DataFrames with correct columns
                return self._empty_dataframes()

            # Build DataFrames
            lend_rows = []
            borrow_rows = []
            collateral_rows = []

            dummy_price = 10.10101  # Placeholder price for perp tokens

            for token_contract, base_token, funding_rate_annual in rows:
                symbol = f"{base_token}-USDC-PERP"

                # CRITICAL: Sign convention
                # In our system: positive = you PAY, negative = you EARN
                # Funding rate +5% means: longs pay 5%, shorts earn 5%
                # - Longing (lending): paying 5% → -5% in our system (negative earning = paying)
                # - Shorting (borrowing): earning 5% → -5% in our system (negative = earning)

                # Both lend and borrow use NEGATIVE of published rate
                perp_rate = -funding_rate_annual

                lend_rows.append({
                    'Token': symbol,
                    'Supply_base_apr': perp_rate,  # All in base, no rewards for perps
                    'Supply_reward_apr': 0.0,
                    'Supply_apr': perp_rate,  # NEGATIVE of published rate
                    'Price': dummy_price,
                    'Token_coin_type': token_contract
                })

                borrow_rows.append({
                    'Token': symbol,
                    'Borrow_base_apr': perp_rate,  # All in base, no rewards for perps
                    'Borrow_reward_apr': 0.0,
                    'Borrow_apr': perp_rate,  # ALSO NEGATIVE of published rate
                    'Price': dummy_price,
                    'Token_coin_type': token_contract
                })

                collateral_rows.append({
                    'Token': symbol,
                    'Collateralization_factor': None,  # Perps don't have collateral ratios
                    'Liquidation_threshold': None,
                    'Token_coin_type': token_contract
                })

            lend_df = pd.DataFrame(lend_rows)
            borrow_df = pd.DataFrame(borrow_rows)
            collateral_df = pd.DataFrame(collateral_rows)

            print(f"\t\t  found {len(lend_df)} perp markets")

            return lend_df, borrow_df, collateral_df

        finally:
            conn.close()

    def _empty_dataframes(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Return empty DataFrames with correct column structure."""
        return (
            pd.DataFrame(columns=['Token', 'Supply_base_apr', 'Supply_reward_apr',
                                 'Supply_apr', 'Price', 'Token_coin_type']),
            pd.DataFrame(columns=['Token', 'Borrow_base_apr', 'Borrow_reward_apr',
                                 'Borrow_apr', 'Price', 'Token_coin_type']),
            pd.DataFrame(columns=['Token', 'Collateralization_factor',
                                 'Liquidation_threshold', 'Token_coin_type'])
        )
