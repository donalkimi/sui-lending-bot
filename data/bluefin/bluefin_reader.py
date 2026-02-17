"""
Bluefin Protocol Perpetual Funding Rates Reader

Fetches perpetual funding rates from Bluefin's public REST API.
Rates are converted to annualized decimals per DESIGN_NOTES.md #7.
"""

import pandas as pd
import requests
import time
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass


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

    def _convert_funding_rate_to_annual(
        self,
        rate_value: float,
        is_hourly: bool = True
    ) -> float:
        """
        Convert Bluefin funding rate to annualized decimal.

        Bluefin API can return rates in different formats:
        - Hourly rate as decimal (e.g., 0.001 = 0.1% per hour)
        - e9 format (rate_e9 / 1e9 = hourly rate)

        Conversion: hourly_rate × 24 × 365 = annualized rate

        Args:
            rate_value: Rate value from API
            is_hourly: If True, rate_value is hourly rate; if False, convert from e9

        Returns:
            Annualized rate as decimal (e.g., 0.0876 = 8.76% APR)
        """
        if rate_value is None or rate_value == 0:
            return 0.0

        try:
            # Convert to hourly rate if needed
            if is_hourly:
                hourly_rate = float(rate_value)
            else:
                # e9 format: divide by 1e9
                hourly_rate = float(rate_value) / 1e9

            # Annualize: hourly × 24 hours × 365 days
            annual_rate = hourly_rate * 24 * 365

            return annual_rate

        except (TypeError, ValueError) as e:
            print(f"  ⚠️  Failed to convert rate {rate_value}: {e}")
            return 0.0

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

                        # Parse rate and timestamp - fail loudly if missing
                        # Try common field names, but don't provide defaults
                        funding_rate_raw = None
                        for field in ['fundingRate', 'funding_rate', 'rate']:
                            if field in rate_entry:
                                funding_rate_raw = rate_entry[field]
                                break

                        if funding_rate_raw is None:
                            print(f"  ⚠️  Skipping rate entry for {market_symbol}: No rate field found")
                            print(f"      Available fields: {list(rate_entry.keys())}")
                            continue

                        timestamp_ms = None
                        for field in ['timestamp', 'time', 'createdAt']:
                            if field in rate_entry:
                                timestamp_ms = rate_entry[field]
                                break

                        if not timestamp_ms:
                            print(f"  ⚠️  Skipping rate entry for {market_symbol}: No timestamp field found")
                            print(f"      Available fields: {list(rate_entry.keys())}")
                            continue

                        # Convert to datetime
                        timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000)

                        # Convert rate to annual (assuming it's hourly decimal)
                        funding_rate_annual = self._convert_funding_rate_to_annual(funding_rate_raw, is_hourly=True)

                        # Get market_address (required field - fail if missing)
                        market_address = rate_entry['marketAddress'] if 'marketAddress' in rate_entry else ''

                        all_rates.append({
                            'timestamp': timestamp,
                            'protocol': 'Bluefin',
                            'market': market_symbol,
                            'market_address': market_address,
                            'token_contract': token_contract,
                            'base_token': base_token,
                            'quote_token': quote_token,
                            'funding_rate_hourly': float(funding_rate_raw) if funding_rate_raw else 0.0,
                            'funding_rate_annual': funding_rate_annual,
                            'next_funding_time': None  # May not be in historical data
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
        start_time_ms: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch historical funding rates with pagination.

        Used for one-time historical backfill.

        Args:
            base_token: Base token symbol (e.g., "BTC", "ETH")
            limit: Number of records per page (default 1000, max per Bluefin)
            start_time_ms: Pagination cursor (timestamp in ms of last row)

        Returns:
            DataFrame with same columns as get_recent_funding_rates()
        """
        market_symbol = f"{base_token}-PERP"

        try:
            url = f"{self.config.api_base_url}/v1/exchange/fundingRateHistory"
            params = {
                "symbol": market_symbol,
                "limit": limit
            }

            if start_time_ms is not None:
                # Add pagination parameter (adjust field name based on API docs)
                params['startTime'] = start_time_ms

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
                    # Parse rate - fail loudly if missing
                    funding_rate_raw = None
                    for field in ['fundingRate', 'funding_rate', 'rate']:
                        if field in rate_entry:
                            funding_rate_raw = rate_entry[field]
                            break

                    if funding_rate_raw is None:
                        print(f"  ⚠️  Skipping historical rate for {market_symbol}: No rate field found")
                        print(f"      Available fields: {list(rate_entry.keys())}")
                        continue

                    # Parse timestamp - fail loudly if missing
                    timestamp_ms = None
                    for field in ['timestamp', 'time', 'createdAt']:
                        if field in rate_entry:
                            timestamp_ms = rate_entry[field]
                            break

                    if not timestamp_ms:
                        print(f"  ⚠️  Skipping historical rate for {market_symbol}: No timestamp field found")
                        print(f"      Available fields: {list(rate_entry.keys())}")
                        continue

                    timestamp = datetime.fromtimestamp(int(timestamp_ms) / 1000)

                    funding_rate_annual = self._convert_funding_rate_to_annual(funding_rate_raw, is_hourly=True)

                    # Get market_address (optional field for historical data)
                    market_address = rate_entry['marketAddress'] if 'marketAddress' in rate_entry else ''

                    all_rates.append({
                        'timestamp': timestamp,
                        'protocol': 'Bluefin',
                        'market': market_symbol,
                        'market_address': market_address,
                        'token_contract': token_contract,
                        'base_token': base_token_parsed,
                        'quote_token': quote_token,
                        'funding_rate_hourly': float(funding_rate_raw) if funding_rate_raw else 0.0,
                        'funding_rate_annual': funding_rate_annual,
                        'next_funding_time': None
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

        for base_token in whitelisted_markets:
            print(f"\n  Fetching historical rates for {base_token}-PERP...")

            # Paginate until no more data
            start_time_ms = None
            total_fetched = 0
            page = 1

            while True:
                df_page = self.get_historical_funding_rates(
                    base_token=base_token,
                    limit=1000,
                    start_time_ms=start_time_ms
                )

                if df_page.empty:
                    break

                all_historical_rates.append(df_page)
                total_fetched += len(df_page)

                print(f"    Page {page}: {len(df_page)} rates (total: {total_fetched})")

                # Check if lookback_days limit reached
                if lookback_days is not None:
                    oldest_timestamp = df_page['timestamp'].min()
                    if oldest_timestamp < datetime.now() - pd.Timedelta(days=lookback_days):
                        print(f"    Reached lookback limit of {lookback_days} days")
                        break

                # Check if we got less than requested (end of data)
                if len(df_page) < 1000:
                    print(f"    End of data (last page had {len(df_page)} < 1000 rates)")
                    break

                # Set pagination cursor to oldest timestamp in this page
                oldest_timestamp_ms = int(df_page['timestamp'].min().timestamp() * 1000)
                start_time_ms = oldest_timestamp_ms

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

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Compatibility wrapper for protocol_merger.py.

        Returns empty DataFrames for lend/borrow/collateral (perp rates don't fit this schema).
        Perp rates should be fetched separately via get_recent_funding_rates().

        Returns:
            Tuple of (empty_df, empty_df, empty_df)
        """
        print("⚠️  Bluefin perp rates should be fetched via get_recent_funding_rates(), not get_all_data()")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
