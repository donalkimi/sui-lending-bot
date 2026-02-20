"""
Bluefin Spot/Perp Pricing Reader

Fetches perp orderbook data and spot index prices from Bluefin API.
Completely independent from BluefinReader (which handles funding rates).

API Response Format (verified 2026-02-20):
- All prices in E9 format (divide by 1e9)
- Field names: bestBidPriceE9, bestAskPriceE9, bestBidQuantityE9, bestAskQuantityE9
- Index price: oraclePriceE9 (spot reference from external markets)
- Mark price: markPriceE9 (perp mark price)
- Timestamp: updatedAtMillis (milliseconds)
"""

import pandas as pd
import requests
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from dataclasses import dataclass
from utils.time_helpers import to_datetime_str, to_datetime_utc, to_seconds


@dataclass
class BluefinPricingReaderConfig:
    """Configuration for Bluefin pricing API client."""
    api_base_url: str = "https://api.sui-prod.bluefin.io"
    timeout: int = 30
    max_retries: int = 3
    retry_delay_base: float = 2.0


class BluefinPricingReader:
    """
    Fetches spot and perp pricing data for arbitrage analysis.

    Data sources:
    - Perp prices: Bluefin /v1/exchange/ticker endpoint (orderbook bid/ask)
    - Spot prices: Bluefin perp index prices (tracks external spot markets via oracle)
    """

    def __init__(self, config: BluefinPricingReaderConfig = None):
        """Initialize pricing reader."""
        self.config = config or BluefinPricingReaderConfig()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'SuiLendingBot/1.0',
            'Accept': 'application/json'
        })

    def _make_request_with_retry(self, url: str, params: Optional[dict] = None) -> dict:
        """Make HTTP GET request with retry logic."""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.config.timeout)

                if response.status_code in (429, 503):
                    if attempt < self.config.max_retries:
                        delay = self.config.retry_delay_base * attempt
                        print(f"  [WARN] Rate limit, retrying in {delay}s")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Rate limit after {self.config.max_retries} retries")

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay_base * attempt
                    print(f"  [WARN] Timeout, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                else:
                    raise Exception(f"Timeout after {self.config.max_retries} retries")

            except requests.exceptions.RequestException as e:
                raise Exception(f"HTTP request failed: {e}")

        raise Exception("Request failed after all retries")

    def fetch_perp_ticker(self, market_symbol: str) -> Optional[Dict]:
        """
        Fetch ticker data for a perp market from Bluefin.

        Args:
            market_symbol: Market symbol (e.g., "BTC-PERP")

        Returns:
            Dict with bid, ask, sizes, index_price, mark_price, timestamp or None if failed

        Response format (all values in E9 - divide by 1e9):
            - bestBidPriceE9, bestAskPriceE9: Orderbook bid/ask
            - bestBidQuantityE9, bestAskQuantityE9: Size at bid/ask
            - oraclePriceE9: Index price (spot reference from external markets)
            - markPriceE9: Perp mark price
            - updatedAtMillis: Timestamp in milliseconds
        """
        try:
            url = f"{self.config.api_base_url}/v1/exchange/ticker"
            params = {'symbol': market_symbol}

            data = self._make_request_with_retry(url, params)

            # Parse E9 format fields
            result = {
                'bid': float(data['bestBidPriceE9']) / 1e9 if 'bestBidPriceE9' in data else None,
                'ask': float(data['bestAskPriceE9']) / 1e9 if 'bestAskPriceE9' in data else None,
                'bid_size': float(data['bestBidQuantityE9']) / 1e9 if 'bestBidQuantityE9' in data else None,
                'ask_size': float(data['bestAskQuantityE9']) / 1e9 if 'bestAskQuantityE9' in data else None,
                'index_price': float(data['oraclePriceE9']) / 1e9 if 'oraclePriceE9' in data else None,
                'mark_price': float(data['markPriceE9']) / 1e9 if 'markPriceE9' in data else None,
                'timestamp': int(data['updatedAtMillis']) if 'updatedAtMillis' in data else None
            }

            # Validate we got at least bid/ask
            if result['bid'] is None and result['ask'] is None:
                print(f"  [WARN] No bid/ask data in response for {market_symbol}")
                print(f"      Response keys: {list(data.keys())}")
                return None

            return result

        except KeyError as e:
            print(f"  [ERROR] Missing expected field for {market_symbol}: {e}")
            print(f"      Response keys: {list(data.keys()) if 'data' in locals() else 'No response'}")
            return None
        except Exception as e:
            print(f"  [ERROR] Failed to fetch ticker for {market_symbol}: {e}")
            return None

    def get_spot_perp_pricing(
        self,
        timestamp: int,
        protocol: str = 'Bluefin'
    ) -> pd.DataFrame:
        """
        Fetch spot and perp pricing for all markets in BLUEFIN_PERP_MARKETS.

        Args:
            timestamp: Unix timestamp (seconds) for pipeline coordination
                      This is the timestamp that will be stored in DB
                      (NOT the actual fetch time - that goes in actual_fetch_time)
            protocol: Protocol name (default 'Bluefin')

        Returns:
            DataFrame with columns:
                - timestamp, protocol, ticker, token_address, market_symbol
                - bid, offer, mid_price, spread_bps
                - bid_size, ask_size
                - is_perp, price_type, actual_fetch_time, source
        """
        from config import settings

        # Round timestamp to nearest hour for consistency
        ts_datetime = to_datetime_utc(timestamp)
        rounded_time = ts_datetime.replace(minute=0, second=0, microsecond=0)

        all_pricing = []
        current_fetch_time = datetime.now(timezone.utc)

        print(f"[PRICING] Fetching spot/perp pricing for {len(settings.BLUEFIN_PERP_MARKETS)} markets...")

        for base_token in settings.BLUEFIN_PERP_MARKETS:
            market_symbol = f"{base_token}-PERP"
            perp_proxy = f"0x{base_token}-USDC-PERP_bluefin"

            print(f"\n  Fetching {market_symbol} ticker...")
            ticker_data = self.fetch_perp_ticker(market_symbol)

            if not ticker_data:
                print(f"    [WARN] Skipping {market_symbol} - no data")
                continue

            # Determine actual fetch time (use API timestamp if available)
            if ticker_data.get('timestamp'):
                # Timestamp is in milliseconds - convert to seconds
                api_fetch_time = to_datetime_utc(int(ticker_data['timestamp'] / 1000))
            else:
                api_fetch_time = current_fetch_time

            # Extract perp orderbook pricing
            bid = ticker_data.get('bid')
            ask = ticker_data.get('ask')

            if bid and ask:
                mid_price = (bid + ask) / 2
                spread_bps = ((ask - bid) / mid_price * 10000) if mid_price > 0 else None

                # Add perp orderbook row
                all_pricing.append({
                    'timestamp': rounded_time,
                    'protocol': protocol,
                    'ticker': base_token,
                    'token_address': perp_proxy,
                    'market_symbol': market_symbol,
                    'bid': bid,
                    'offer': ask,
                    'mid_price': mid_price,
                    'spread_bps': spread_bps,
                    'bid_size': ticker_data.get('bid_size'),
                    'ask_size': ticker_data.get('ask_size'),
                    'is_perp': True,
                    'price_type': 'orderbook',
                    'actual_fetch_time': api_fetch_time,
                    'source': 'bluefin_ticker'
                })

                print(f"    [OK] Perp orderbook: bid=${bid:.2f}, ask=${ask:.2f}, spread={spread_bps:.2f}bps")

            # Extract spot index price (if available)
            index_price = ticker_data.get('index_price')

            # Use index price as "spot" reference
            if index_price:
                # Create synthetic token address for index price
                index_token_address = f"0x{base_token}-USDC-INDEX_{protocol.lower()}"

                all_pricing.append({
                    'timestamp': rounded_time,
                    'protocol': protocol,
                    'ticker': base_token,
                    'token_address': index_token_address,
                    'market_symbol': f"{base_token}-INDEX",
                    'bid': index_price,  # Index price has no spread
                    'offer': index_price,
                    'mid_price': index_price,
                    'spread_bps': 0.0,
                    'bid_size': None,
                    'ask_size': None,
                    'is_perp': False,
                    'price_type': 'index',
                    'actual_fetch_time': api_fetch_time,
                    'source': 'bluefin_index'
                })

                print(f"    [OK] Spot index: ${index_price:.2f}")

        if not all_pricing:
            print("  [WARN] No pricing data fetched")
            return pd.DataFrame()

        df = pd.DataFrame(all_pricing)
        perp_count = len(df[df['is_perp']])
        spot_count = len(df[~df['is_perp']])
        print(f"\n[PRICING] Fetched {len(df)} total records ({perp_count} perp, {spot_count} spot/index)")

        return df
