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

import re
import pandas as pd
import requests
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict
from dataclasses import dataclass
from utils.time_helpers import to_datetime_str, to_seconds


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

    def _fetch_amm_quote(self, token_in: str, token_out: str, amount_raw: int) -> Optional[dict]:
        """
        Fetch a best-price quote from the Bluefin AMM aggregator.

        Aggregates across all major SUI DEXes (Cetus, Turbos, Aftermath, etc.)
        to return the optimal route for the given token swap.

        Args:
            token_in: Contract address of the input token
            token_out: Contract address of the output token
            amount_raw: Integer amount of token_in in raw on-chain units

        Returns:
            Raw API response dict, or None on failure.
            Key fields:
                - effectivePrice: tokenIn / tokenOut (e.g. USDC per X for USDC→X)
                - effectivePriceReserved: tokenOut / tokenIn (inverse of effectivePrice)
                - returnAmountWithDecimal: raw integer amount of tokenOut received
                - swapAmount / returnAmount: human-readable decimal amounts
                - warning: e.g. "PriceImpactTooHigh" (logged but not fatal)
        """
        from config import settings

        url = f"{settings.BLUEFIN_AGGREGATOR_BASE_URL}/v3/quote"
        params = {
            'amount': str(amount_raw),
            'from': token_in,
            'to': token_out,
            'sources': ','.join(settings.BLUEFIN_AGGREGATOR_SOURCES),
        }

        try:
            data = self._make_request_with_retry(url, params)

            if data.get('warning'):
                print(f"    [WARN] Aggregator warning for {token_in[:20]}...→{token_out[:20]}...: {data['warning']}")

            return data

        except Exception as e:
            print(f"    [ERROR] AMM quote failed ({token_in[:20]}...→{token_out[:20]}...): {e}")
            return None

    def get_spot_perp_basis(self, timestamp: int) -> pd.DataFrame:
        """
        Fetch spot/perp basis for all (perp, spot_contract) pairs in BLUEFIN_TO_LENDINGS.

        For each perp market:
          - Fetches the perp orderbook bid/ask from the Bluefin ticker API (one call per perp)
        For each associated spot token:
          - Fetches the AMM offer price: USDC → spot_contract (best ask price in USDC per token)
          - Fetches the AMM bid price:   spot_contract → USDC (best bid price in USDC per token)
        Then computes:
          - basis_bid = (perp_bid - spot_ask) / perp_bid   [exit: sell perp at bid, cover short spot at ask]
          - basis_ask = (perp_ask - spot_bid) / perp_ask   [entry: buy perp at ask, short spot at bid]
          - basis_mid = (basis_bid + basis_ask) / 2

        Args:
            timestamp: Unix seconds — pipeline snapshot time, passed from caller.
                       NEVER call datetime.now() or time.time() for this value.

        Returns:
            DataFrame with one row per (perp_proxy, spot_contract) with columns:
                timestamp, perp_proxy, perp_ticker, spot_contract,
                spot_bid, spot_ask, perp_bid, perp_ask,
                basis_bid, basis_ask, basis_mid, actual_fetch_time
        """
        from config import settings
        from config.stablecoins import STABLECOINS

        usdc_contract = STABLECOINS['USDC']
        timestamp_str = to_datetime_str(timestamp)
        actual_fetch_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        rows = []
        total_pairs = sum(len(v) for v in settings.BLUEFIN_TO_LENDINGS.values())
        print(f"[BASIS] Fetching spot/perp basis for {len(settings.BLUEFIN_TO_LENDINGS)} perps, "
              f"{total_pairs} spot contracts...")

        for perp_proxy, spot_contracts in settings.BLUEFIN_TO_LENDINGS.items():
            # Extract ticker from proxy address: '0xBTC-USDC-PERP_bluefin' → 'BTC'
            match = re.search(r'0x(\w+)-USDC-PERP', perp_proxy)
            if not match:
                print(f"  [WARN] Cannot parse ticker from perp proxy: {perp_proxy}")
                continue

            ticker = match.group(1)
            market_symbol = f"{ticker}-PERP"

            print(f"\n  [{ticker}] Fetching perp ticker {market_symbol}...")
            perp_data = self.fetch_perp_ticker(market_symbol)

            if not perp_data or perp_data.get('bid') is None or perp_data.get('ask') is None:
                print(f"    [WARN] No perp bid/ask for {market_symbol}, skipping all spot contracts")
                continue

            perp_bid = perp_data['bid']
            perp_ask = perp_data['ask']
            print(f"    [OK] Perp: bid=${perp_bid:.4f}, ask=${perp_ask:.4f}")

            # Append index price row (zero spread — index_price == oraclePriceE9 on Bluefin)
            index_price = perp_data.get('index_price')
            if index_price is None:
                print(f"    [WARN] No index_price for {market_symbol}, skipping index row")
            else:
                index_contract = f"0x{ticker}-USDC-INDEX_bluefin"
                basis_bid = (perp_bid - index_price) / perp_bid
                basis_ask = (perp_ask - index_price) / perp_ask
                basis_mid = (basis_bid + basis_ask) / 2
                print(f"    [OK] Index: ${index_price:.4f}, "
                      f"basis_bid={basis_bid*100:.3f}%, basis_ask={basis_ask*100:.3f}%")
                rows.append({
                    'timestamp': timestamp_str,
                    'perp_proxy': perp_proxy,
                    'perp_ticker': ticker,
                    'spot_contract': index_contract,
                    'spot_bid': index_price,
                    'spot_ask': index_price,
                    'perp_bid': perp_bid,
                    'perp_ask': perp_ask,
                    'basis_bid': basis_bid,
                    'basis_ask': basis_ask,
                    'basis_mid': basis_mid,
                    'actual_fetch_time': actual_fetch_time,
                })

            for spot_contract in spot_contracts:
                short_addr = spot_contract[:30] + '...'
                print(f"    Spot {short_addr}")

                # Step 1: USDC → spot (offer query) — how much USDC to pay per spot token
                offer_data = self._fetch_amm_quote(usdc_contract, spot_contract,
                                                   settings.BLUEFIN_AMM_USDC_AMOUNT_RAW)
                if offer_data is None:
                    print(f"      [WARN] No offer quote, skipping")
                    continue

                return_raw = offer_data.get('returnAmountWithDecimal', '0')
                if not return_raw or str(return_raw) == '0':
                    print(f"      [WARN] Zero returnAmount for USDC→spot, skipping (no AMM liquidity)")
                    continue

                spot_ask = float(offer_data['effectivePrice'])
                x_amount_raw = int(return_raw)

                # Step 2: spot → USDC (bid query) — how much USDC received per spot token sold
                bid_data = self._fetch_amm_quote(spot_contract, usdc_contract, x_amount_raw)
                if bid_data is None:
                    print(f"      [WARN] No bid quote, skipping")
                    continue

                spot_bid = float(bid_data['effectivePriceReserved'])

                if spot_bid <= 0 or spot_ask <= 0:
                    print(f"      [WARN] Invalid spot prices (bid={spot_bid}, ask={spot_ask}), skipping")
                    continue

                basis_bid = (perp_bid - spot_ask) / perp_bid
                basis_ask = (perp_ask - spot_bid) / perp_ask
                basis_mid = (basis_bid + basis_ask) / 2

                print(f"      [OK] spot_bid=${spot_bid:.4f}, spot_ask=${spot_ask:.4f}, "
                      f"basis_bid={basis_bid*100:.3f}%, basis_ask={basis_ask*100:.3f}%")

                rows.append({
                    'timestamp': timestamp_str,
                    'perp_proxy': perp_proxy,
                    'perp_ticker': ticker,
                    'spot_contract': spot_contract,
                    'spot_bid': spot_bid,
                    'spot_ask': spot_ask,
                    'perp_bid': perp_bid,
                    'perp_ask': perp_ask,
                    'basis_bid': basis_bid,
                    'basis_ask': basis_ask,
                    'basis_mid': basis_mid,
                    'actual_fetch_time': actual_fetch_time,
                })

        if not rows:
            print("[BASIS] No basis rows collected")
            return pd.DataFrame()

        print(f"\n[BASIS] Collected {len(rows)} spot/perp basis rows")
        return pd.DataFrame(rows)
