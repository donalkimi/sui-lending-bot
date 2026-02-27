"""
Bluefin Protocol Perpetual Funding Rates Reader

Fetches perpetual funding rates from Bluefin's public REST API.
Rates are converted to annualized decimals per DESIGN_NOTES.md #7.
"""

import pandas as pd
import requests
import time
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from dataclasses import dataclass
from utils.time_helpers import to_datetime_str, to_datetime_utc, to_seconds


@dataclass
class BluefinReaderConfig:
    """Configuration for Bluefin API client."""
    api_base_url: str = "https://api.sui-prod.bluefin.io"
    timeout: int = 30  # Longer timeout for historical pagination
    max_retries: int = 3
    retry_delay_base: float = 2.0  # Exponential backoff base (seconds)


class BluefinReader:
    """
    Fetches perpetual funding rates from Bluefin REST API.

    Only fetches whitelisted markets from config/settings.py BLUEFIN_PERP_MARKETS.
    Generates proxy token_contract for each market.
    """

    def __init__(self, config: BluefinReaderConfig = None):
        """
        Initialize Bluefin reader.

        Args:
            config: Configuration object (uses defaults if None)
        """
        self.config = config or BluefinReaderConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SuiLendingBot/1.0',
            'Accept': 'application/json'
        })

    def _make_request_with_retry(
        self,
        url: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make HTTP GET request with retry logic for rate limits.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.timeout
                )

                # Check for rate limit or service unavailable
                if response.status_code in (429, 503):
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay_base * attempt
                        print(f"  ⚠️  Rate limit/unavailable (status {response.status_code}), "
                              f"retrying in {delay}s (attempt {attempt}/{self.config.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {self.config.max_retries} retries")

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay_base * attempt
                    print(f"  ⚠️  Request timeout, retrying in {delay}s (attempt {attempt}/{self.config.max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Request timeout after {self.config.max_retries} retries")

            except requests.exceptions.RequestException as e:
                raise Exception(f"HTTP request failed: {e}")

        raise Exception("Request failed after all retries")

    def _generate_perp_token_contract(
        self,
        base_token: str,
        quote_token: str = "USDC",
        protocol: str = "bluefin"
    ) -> str:
        """
        Generate proxy token contract for perp market.

        Format: "0x<base>-<quote>-PERP_<protocol>"

        Args:
            base_token: Base token symbol (e.g., "BTC")
            quote_token: Quote token symbol (default "USDC")
            protocol: Protocol name (default "bluefin")

        Returns:
            Proxy token contract (e.g., "0xBTC-USDC-PERP_bluefin")
        """
        return f"0x{base_token.upper()}-{quote_token.upper()}-PERP_{protocol.lower()}"

    def _parse_market_symbol(self, market_symbol: str) -> Tuple[str, str]:
        """
        Parse Bluefin market symbol into base and quote tokens.

        Args:
            market_symbol: Market symbol from API (e.g., "BTC-PERP", "ETH-PERP")

        Returns:
            (base_token, quote_token) tuple

        Raises:
            ValueError: If market symbol format is invalid
        """
        if market_symbol.endswith("-PERP"):
            base_token = market_symbol.replace("-PERP", "").upper()
            quote_token = "USDC"  # All Bluefin perps are vs USDC
            return base_token, quote_token
        raise ValueError(f"Invalid market symbol: {market_symbol}")

    def get_recent_funding_rates(
        self,
        limit: int = 100,
        whitelisted_markets: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch recent funding rates for whitelisted markets.

        Fetches last N rates per market to catch up on missed data.
        This is used by the hourly cron job.

        Args:
            limit: Number of recent rates to fetch per market (default 100)
            whitelisted_markets: List of base tokens to fetch (e.g., ["BTC", "ETH"])
                                If None, imports from settings

        Returns:
            DataFrame with columns:
                - timestamp: Funding rate timestamp
                - protocol: 'Bluefin'
                - market: Market symbol (e.g., 'BTC-PERP')
                - market_address: Contract address from Bluefin
                - token_contract: Proxy format ("0xBTC-USDC-PERP_bluefin")
                - base_token: Base token symbol (e.g., 'BTC')
                - quote_token: Quote token symbol (e.g., 'USDC')
                - funding_rate_hourly: Raw hourly rate (decimal)
                - funding_rate_annual: Annualized rate (decimal)
                - next_funding_time: Next funding update timestamp
        """
        if whitelisted_markets is None:
            # Import here to avoid circular dependency
            from config import settings
            whitelisted_markets = settings.BLUEFIN_PERP_MARKETS

        all_rates = []

        for base_token in whitelisted_markets:
            market_symbol = f"{base_token}-PERP"

            try:
                # Fetch from fundingRateHistory endpoint
                url = f"{self.config.api_base_url}/v1/exchange/fundingRateHistory"
                params = {
                    "symbol": market_symbol,
                    "limit": limit
                }

                data = self._make_request_with_retry(url, params)

                # Parse response (adjust based on actual Bluefin API response format)
                if isinstance(data, list):
                    rates_list = data
                elif isinstance(data, dict) and 'data' in data:
                    rates_list = data['data']
                else:
                    print(f"  ⚠️  Unexpected response format for {market_symbol}")
                    continue

                if not rates_list:
                    print(f"  ⚠️  No rates found for {market_symbol}")
                    continue

                # Process each rate
                for rate_entry in rates_list:
                    try:
                        base_token, quote_token = self._parse_market_symbol(market_symbol)
                        token_contract = self._generate_perp_token_contract(base_token, quote_token)

                        # Parse rate and timestamp - fail fast with clear errors
                        # Bluefin API returns: fundingRateE9, fundingTimeAtMillis, symbol
                        if 'fundingRateE9' not in rate_entry:
                            raise KeyError(
                                f"Missing required field 'fundingRateE9' for {market_symbol}. "
                                f"Available fields: {list(rate_entry.keys())}"
                            )

                        if 'fundingTimeAtMillis' not in rate_entry:
                            raise KeyError(
                                f"Missing required field 'fundingTimeAtMillis' for {market_symbol}. "
                                f"Available fields: {list(rate_entry.keys())}"
                            )

                        # Extract raw fields from Bluefin API
                        funding_rate_e9 = int(rate_entry['fundingRateE9'])
                        funding_time_ms = int(rate_entry['fundingTimeAtMillis'])
                        market_address = rate_entry.get('marketAddress', '')

                        # Convert timestamp from milliseconds to seconds
                        funding_time_seconds = int(funding_time_ms / 1000)

                        # Cap funding rates at ±10 bps (0.001 = 0.1%) per hour
                        # Reference: https://learn.bluefin.io/bluefin/bluefin-perps-exchange/trading/funding
                        # 10 bps in E9 format = 0.001 * 1e9 = 1,000,000
                        MAX_FUNDING_RATE_E9 = 1_000_000  # +10 bps
                        MIN_FUNDING_RATE_E9 = -1_000_000  # -10 bps

                        if funding_rate_e9 > MAX_FUNDING_RATE_E9:
                            print(f"\n⚠️  EXTREME RATE DETECTED - CAPPING TO +10 bps:")
                            print(f"   Market: {market_symbol}")
                            print(f"   Timestamp (ms): {funding_time_ms}")
                            print(f"   Timestamp (UTC): {to_datetime_str(funding_time_seconds)}")
                            print(f"   Original fundingRateE9: {funding_rate_e9:,}")
                            print(f"   Capped to: {MAX_FUNDING_RATE_E9:,} (+10 bps)")
                            funding_rate_e9 = MAX_FUNDING_RATE_E9
                        elif funding_rate_e9 < MIN_FUNDING_RATE_E9:
                            print(f"\n⚠️  EXTREME RATE DETECTED - CAPPING TO -10 bps:")
                            print(f"   Market: {market_symbol}")
                            print(f"   Timestamp (ms): {funding_time_ms}")
                            print(f"   Timestamp (UTC): {to_datetime_str(funding_time_seconds)}")
                            print(f"   Original fundingRateE9: {funding_rate_e9:,}")
                            print(f"   Capped to: {MIN_FUNDING_RATE_E9:,} (-10 bps)")
                            funding_rate_e9 = MIN_FUNDING_RATE_E9

                        # Convert to UTC datetime and round down to nearest hour
                        # Use helper to ensure UTC consistency (no DST issues)
                        raw_timestamp = to_datetime_utc(funding_time_seconds)
                        funding_time = raw_timestamp.replace(minute=0, second=0, microsecond=0)

                        # Convert e9 format to hourly rate: fundingRateE9 / 1e9
                        funding_rate_hourly = float(funding_rate_e9) / 1e9

                        # Annualize: hourly × 24 hours × 365 days
                        # Round to 5 decimal places to avoid floating point precision issues
                        funding_rate_annual = round(float(funding_rate_hourly) * 24.0 * 365.0, 5)

                        all_rates.append({
                            'timestamp': funding_time,  # Rounded to nearest hour
                            'protocol': 'Bluefin',
                            'market': market_symbol,
                            'market_address': market_address,
                            'token_contract': token_contract,
                            'base_token': base_token,
                            'quote_token': quote_token,
                            'funding_rate_hourly': funding_rate_hourly,
                            'funding_rate_annual': funding_rate_annual,
                            'next_funding_time': None,
                            'raw_timestamp_ms': funding_time_ms  # Raw timestamp from API
                        })

                    except KeyError as e:
                        print(f"  ⚠️  KeyError processing rate entry for {market_symbol}: {e}")
                        print(f"      Available fields: {list(rate_entry.keys())}")
                        continue
                    except Exception as e:
                        print(f"  ⚠️  Error processing rate entry for {market_symbol}: {e}")
                        continue

                print(f"  ✅ Fetched {len(rates_list)} rates for {market_symbol}")

            except Exception as e:
                print(f"  ❌ Failed to fetch {market_symbol}: {e}")
                continue

        if not all_rates:
            print("  ⚠️  No rates fetched for any market")
            return pd.DataFrame()

        return pd.DataFrame(all_rates)

    def get_historical_funding_rates(
        self,
        base_token: str,
        limit: int = 1000,
        page: int = 1
    ) -> pd.DataFrame:
        """
        Fetch historical funding rates with page-based pagination.

        Used for one-time historical backfill.

        Args:
            base_token: Base token symbol (e.g., "BTC", "ETH")
            limit: Number of records per page (default 1000, max per Bluefin)
            page: Page number (1-indexed)

        Returns:
            DataFrame with same columns as get_recent_funding_rates()
        """
        market_symbol = f"{base_token}-PERP"

        try:
            url = f"{self.config.api_base_url}/v1/exchange/fundingRateHistory"
            params = {
                "symbol": market_symbol,
                "limit": limit,
                "page": page
            }

            data = self._make_request_with_retry(url, params)

            # Parse response
            if isinstance(data, list):
                rates_list = data
            elif isinstance(data, dict) and 'data' in data:
                rates_list = data['data']
            else:
                return pd.DataFrame()

            if not rates_list:
                return pd.DataFrame()

            # Process rates (same as get_recent_funding_rates)
            all_rates = []
            base_token_parsed, quote_token = self._parse_market_symbol(market_symbol)
            token_contract = self._generate_perp_token_contract(base_token_parsed, quote_token)

            for rate_entry in rates_list:
                try:
                    # Parse rate and timestamp - fail fast with clear errors
                    # Bluefin API returns: fundingRateE9, fundingTimeAtMillis, symbol
                    if 'fundingRateE9' not in rate_entry:
                        raise KeyError(
                            f"Missing required field 'fundingRateE9' for {market_symbol}. "
                            f"Available fields: {list(rate_entry.keys())}"
                        )

                    if 'fundingTimeAtMillis' not in rate_entry:
                        raise KeyError(
                            f"Missing required field 'fundingTimeAtMillis' for {market_symbol}. "
                            f"Available fields: {list(rate_entry.keys())}"
                        )

                    # Extract raw fields from Bluefin API
                    funding_rate_e9 = int(rate_entry['fundingRateE9'])
                    funding_time_ms = int(rate_entry['fundingTimeAtMillis'])
                    market_address = rate_entry.get('marketAddress', '')

                    # Convert timestamp from milliseconds to seconds
                    funding_time_seconds = int(funding_time_ms / 1000)

                    # Cap funding rates at ±10 bps (0.001 = 0.1%) per hour
                    # Reference: https://learn.bluefin.io/bluefin/bluefin-perps-exchange/trading/funding
                    # 10 bps in E9 format = 0.001 * 1e9 = 1,000,000
                    MAX_FUNDING_RATE_E9 = 1_000_000  # +10 bps
                    MIN_FUNDING_RATE_E9 = -1_000_000  # -10 bps

                    if funding_rate_e9 > MAX_FUNDING_RATE_E9:
                        print(f"\n⚠️  EXTREME RATE DETECTED - CAPPING TO +10 bps:")
                        print(f"   Market: {market_symbol}")
                        print(f"   Timestamp (ms): {funding_time_ms}")
                        print(f"   Timestamp (UTC): {to_datetime_str(funding_time_seconds)}")
                        print(f"   Original fundingRateE9: {funding_rate_e9:,}")
                        print(f"   Capped to: {MAX_FUNDING_RATE_E9:,} (+10 bps)")
                        funding_rate_e9 = MAX_FUNDING_RATE_E9
                    elif funding_rate_e9 < MIN_FUNDING_RATE_E9:
                        print(f"\n⚠️  EXTREME RATE DETECTED - CAPPING TO -10 bps:")
                        print(f"   Market: {market_symbol}")
                        print(f"   Timestamp (ms): {funding_time_ms}")
                        print(f"   Timestamp (UTC): {to_datetime_str(funding_time_seconds)}")
                        print(f"   Original fundingRateE9: {funding_rate_e9:,}")
                        print(f"   Capped to: {MIN_FUNDING_RATE_E9:,} (-10 bps)")
                        funding_rate_e9 = MIN_FUNDING_RATE_E9

                    # Convert to UTC datetime and round down to nearest hour
                    # Use helper to ensure UTC consistency (no DST issues)
                    raw_timestamp = to_datetime_utc(funding_time_seconds)
                    funding_time = raw_timestamp.replace(minute=0, second=0, microsecond=0)

                    # Convert e9 format to hourly rate: fundingRateE9 / 1e9
                    funding_rate_hourly = float(funding_rate_e9) / 1e9

                    # Annualize: hourly × 24 hours × 365 days
                    # Round to 5 decimal places to avoid floating point precision issues
                    funding_rate_annual = round(float(funding_rate_hourly) * 24.0 * 365.0, 5)

                    all_rates.append({
                        'timestamp': funding_time,  # Rounded to nearest hour
                        'protocol': 'Bluefin',
                        'market': market_symbol,
                        'market_address': market_address,
                        'token_contract': token_contract,
                        'base_token': base_token_parsed,
                        'quote_token': quote_token,
                        'funding_rate_hourly': funding_rate_hourly,
                        'funding_rate_annual': funding_rate_annual,
                        'next_funding_time': None,
                        'raw_timestamp_ms': funding_time_ms  # Raw timestamp from API
                    })

                except KeyError as e:
                    print(f"  ⚠️  KeyError processing historical rate for {market_symbol}: {e}")
                    print(f"      Available fields: {list(rate_entry.keys())}")
                    continue
                except Exception as e:
                    print(f"  ⚠️  Error processing historical rate for {market_symbol}: {e}")
                    continue

            return pd.DataFrame(all_rates)

        except Exception as e:
            print(f"  ❌ Failed to fetch historical rates for {base_token}: {e}")
            return pd.DataFrame()

    def get_all_markets_historical(
        self,
        lookback_days: Optional[int] = None,
        whitelisted_markets: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Fetch historical rates for whitelisted markets with pagination.

        Used for one-time historical backfill. Paginates to fetch all available history.

        Args:
            lookback_days: Number of days to fetch (None = maximum available)
            whitelisted_markets: List of base tokens (if None, imports from settings)

        Returns:
            DataFrame with all historical rates for all markets
        """
        if whitelisted_markets is None:
            from config import settings
            whitelisted_markets = settings.BLUEFIN_PERP_MARKETS

        all_historical_rates = []

        # Calculate reference time once for lookback comparison
        # This is a one-time backfill: "fetch last N days from when script runs"
        if lookback_days is not None:
            reference_seconds = int(datetime.now(timezone.utc).timestamp())
            cutoff_seconds = reference_seconds - (lookback_days * 24 * 3600)
        else:
            cutoff_seconds = None

        for base_token in whitelisted_markets:
            print(f"\n  Fetching historical rates for {base_token}-PERP...")

            # Paginate through pages until API returns empty/zero rates
            total_fetched = 0
            page = 1

            while True:
                df_page = self.get_historical_funding_rates(
                    base_token=base_token,
                    limit=1000,
                    page=page
                )

                # Stop if API returns no data (end of history)
                if df_page.empty or len(df_page) == 0:
                    print(f"    End of data (page {page} returned 0 rates)")
                    break

                all_historical_rates.append(df_page)
                total_fetched += len(df_page)

                # Check if lookback_days limit reached
                # Compare Unix seconds (timezone-agnostic integers)
                if cutoff_seconds is not None:
                    oldest_seconds = to_seconds(df_page['timestamp'].min())
                    if oldest_seconds < cutoff_seconds:
                        break

                # Increment page number for next iteration
                page += 1

                # Add small delay to avoid rate limits
                time.sleep(0.5)

            print(f"  ✅ Total fetched for {base_token}-PERP: {total_fetched} rates")

        if not all_historical_rates:
            return pd.DataFrame()

        # Combine all DataFrames
        combined_df = pd.concat(all_historical_rates, ignore_index=True)

        # Remove duplicates (in case of overlap)
        combined_df = combined_df.drop_duplicates(subset=['timestamp', 'token_contract'])

        # Sort by timestamp
        combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)

        return combined_df

    def get_all_data_for_timestamp(self, timestamp: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch perp funding rates from perp_margin_rates table for protocol merger.

        This method is called by protocol_merger.py during snapshot creation.
        It reads from the perp_margin_rates database table (populated by main_perp_refresh.py).

        Args:
            timestamp: Unix timestamp in seconds (REQUIRED per DESIGN_NOTES.md #1)

        Returns:
            (lend_df, borrow_df, collateral_df) in protocol format
        """
        from data.rate_tracker import RateTracker
        from config import settings

        # Get rates for the current hour (rounded down)
        ts_datetime = datetime.fromtimestamp(timestamp)
        rates_hour = ts_datetime.replace(minute=0, second=0, microsecond=0)
        rates_hour_str = to_datetime_str(to_seconds(rates_hour))

        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            connection_url=settings.SUPABASE_URL
        )

        conn = tracker._get_connection()

        try:
            cursor = conn.cursor()

            # Query perp_margin_rates table
            ph = '%s' if tracker.use_cloud else '?'
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

            # Fetch real perp mid prices from spot_perp_basis (perp_bid/ask are identical
            # across all spot_contract rows for a given perp_proxy, so any row suffices)
            price_query = f"""
                SELECT perp_proxy, perp_bid, perp_ask
                FROM spot_perp_basis
                WHERE timestamp = (
                    SELECT MAX(timestamp) FROM spot_perp_basis WHERE timestamp <= {ph}
                )
            """
            cursor.execute(price_query, (rates_hour_str,))
            perp_prices = {}
            for perp_proxy, perp_bid, perp_ask in cursor.fetchall():
                if perp_bid is not None and perp_ask is not None:
                    perp_prices[perp_proxy] = (float(perp_bid) + float(perp_ask)) / 2.0

            # Build DataFrames
            lend_rows = []
            borrow_rows = []
            collateral_rows = []

            for token_contract, base_token, funding_rate_annual in rows:
                price = perp_prices.get(token_contract)
                if price is None:
                    print(f"\t\t  WARNING: No spot_perp_basis price for {token_contract} ({base_token}) — price_usd will be NULL in rates_snapshot")
                symbol = f"{base_token}-USDC-PERP"

                # CRITICAL: Sign convention
                # Funding rate is stored as-is from Bluefin API
                # We need to NEGATE it for our system:
                # - Positive funding (+5%) = longs pay shorts → store as -5% (shorts earn)
                # - Negative funding (-3%) = shorts pay longs → store as +3% (shorts pay)
                perp_rate = -funding_rate_annual

                lend_rows.append({
                    'Token': symbol,
                    'Supply_base_apr': perp_rate,
                    'Supply_reward_apr': 0.0,
                    'Supply_apr': perp_rate,
                    'Price': price,
                    'Token_coin_type': token_contract
                })

                borrow_rows.append({
                    'Token': symbol,
                    'Borrow_base_apr': perp_rate,
                    'Borrow_reward_apr': 0.0,
                    'Borrow_apr': perp_rate,
                    'Price': price,
                    'Token_coin_type': token_contract
                })

                collateral_rows.append({
                    'Token': symbol,
                    'Collateralization_factor': None,
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
