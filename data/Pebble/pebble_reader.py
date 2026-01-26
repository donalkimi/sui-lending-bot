"""
Pebble Protocol API Reader

Pulls live pool data from Pebble's public API and builds a lending DataFrame
with clearly separated base/reward APRs and USD liquidity metrics.
"""

import pandas as pd
import requests
from typing import Tuple, Dict, List


class PebbleReader:
    """Read lending data from Pebble Protocol API."""

    # API endpoints
    BASE_URL = "https://devapi.pebble-finance.com"
    MARKET_LIST_URL = f"{BASE_URL}/market/getMarketList"
    REWARDS_URL = f"{BASE_URL}/pebbleWeb3Config/getAllMarketConfig"
    
    # Market types
    MARKET_TYPES = ["MainMarket", "XSuiMarket", "AltCoinMarket"]

    def __init__(self):
        """Initialize the Pebble reader."""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def _fetch_market_data(self, market_type: str) -> List[dict]:
        """
        Fetch market data for a specific market type.

        Args:
            market_type: One of MainMarket, XSuiMarket, AltCoinMarket

        Returns:
            List of pool data dictionaries.
        """
        try:
            response = self.session.get(
                self.MARKET_LIST_URL,
                params={"marketType": market_type, "page": 1, "size": 100},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                print(f"\tWarning: Non-zero response code for {market_type}")
                return []
            
            content = data.get("data", {}).get("content", [])
            return content
            
        except requests.exceptions.RequestException as e:
            print(f"\tFailed to fetch {market_type}: {e}")
            return []

    def _fetch_rewards_data(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch rewards data from Pebble API.

        Returns:
            Dictionary mapping (market_type, token) -> {supply_reward_apr, borrow_reward_apr}
        """
        try:
            response = self.session.get(self.REWARDS_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") != 0:
                print("\tWarning: Non-zero response code for rewards")
                return {}
            
            rewards_map = {}
            
            for market in data.get("data", []):
                market_type = market.get("marketType", "")
                
                for summary in market.get("summaries", []):
                    token = summary.get("reserveCoinType", "")
                    reward_type = summary.get("rewardType")  # 0 = supply, 1 = borrow
                    
                    # Sum up all reward APRs for this token/type
                    total_apr = 0.0
                    for reward in summary.get("rewards", []):
                        try:
                            total_apr += float(reward.get("apr", 0))
                        except (TypeError, ValueError):
                            pass
                    
                    # Create key combining market and token
                    key = (market_type, token)
                    if key not in rewards_map:
                        rewards_map[key] = {"supply_reward_apr": 0.0, "borrow_reward_apr": 0.0}
                    
                    if reward_type == 0:  # Supply reward
                        rewards_map[key]["supply_reward_apr"] += total_apr
                    elif reward_type == 1:  # Borrow reward
                        rewards_map[key]["borrow_reward_apr"] += total_apr
            
            return rewards_map
            
        except requests.exceptions.RequestException as e:
            print(f"\tFailed to fetch rewards data: {e}")
            return {}

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch all data from Pebble Protocol.

        Returns:
            Tuple of (lend_df, borrow_df, collateral_df)

        Lending DataFrame columns:
            - Token (symbol)
            - Market (market name)
            - Supply_base_apr       (supplyAPY from API, decimal)
            - Supply_reward_apr     (from rewards endpoint, decimal)
            - Supply_apr            (calculated: base + reward)
            - Borrow_base_apr       (borrowAPY from API, decimal)
            - Borrow_reward_apr     (from rewards endpoint, decimal)
            - Borrow_apr            (calculated: base - reward)
            - Price                 (USD price)
            - Total_supply
            - Total_supply_usd
            - Total_borrow
            - Total_borrow_usd
            - Available_borrow
            - Available_borrow_usd
            - Utilization
            - Token_coin_type
            - Market_type
            - Market_id
        
        Borrow DataFrame columns:
            - Token
            - Market
            - Borrow_apr            (calculated: base - reward)
            - Base_rate             (base APR)
            - Reward_rate           (reward APR)
            - Price                 (USD price)
            - Token_coin_type       (contract address)
        
        Collateral DataFrame columns:
            - Token
            - Market
            - Collateralization_factor  (maxLTV)
            - Liquidation_threshold     (liqLTV)
            - Token_coin_type           (contract address)
        """

        # First, fetch rewards data
        print("\tFetching rewards data...")
        rewards_map = self._fetch_rewards_data()
        print(f"\tFound rewards for {len(rewards_map)} token/market combinations")

        lend_rates_data = []
        borrow_rates_data = []
        collateral_ratios_data = []

        total_pools = 0

        # Fetch data from all market types
        for market_type in self.MARKET_TYPES:
            print(f"\tFetching {market_type}...")
            pools = self._fetch_market_data(market_type)
            
            for pool in pools:
                # Skip if marked for removal
                if pool.get("toBeOffShelf", False):
                    continue

                # Token info
                token_info = pool.get("tokenInfo", {}) or {}
                token_symbol = token_info.get("symbol")
                token_coin_type = pool.get("token") or token_info.get("address")
                
                if not token_symbol:
                    continue

                # Market info
                market_name = pool.get("name", market_type)
                market_id = pool.get("marketID", "")
                full_market_type = pool.get("marketType", "")

                # Price
                try:
                    price = float(token_info.get("price", 0.0))
                except (TypeError, ValueError):
                    price = 0.0

                # Token decimals
                try:
                    decimals = int(token_info.get("decimals", 0))
                except (TypeError, ValueError):
                    decimals = 0
                scale = 10 ** decimals if decimals > 0 else 1

                # Supply / borrow amounts (raw units → token amounts)
                try:
                    total_supply_raw = float(pool.get("totalSupply", 0))
                except (TypeError, ValueError):
                    total_supply_raw = 0.0
                try:
                    total_borrow_raw = float(pool.get("totalBorrow", 0))
                except (TypeError, ValueError):
                    total_borrow_raw = 0.0
                try:
                    available_borrow_raw = float(pool.get("liqAvailable", 0))
                except (TypeError, ValueError):
                    available_borrow_raw = 0.0

                total_supply = total_supply_raw / scale
                total_borrow = total_borrow_raw / scale
                available_borrow = available_borrow_raw / scale

                total_supply_usd = total_supply * price
                total_borrow_usd = total_borrow * price
                available_borrow_usd = available_borrow * price

                # Utilization
                try:
                    utilization = float(pool.get("utilization", 0))
                except (TypeError, ValueError):
                    utilization = (total_borrow / total_supply) if total_supply > 0 else 0.0

                # Base APYs (Pebble calls them APY but they appear to be base rates)
                # Note: These are already in decimal form (e.g., 0.0425 = 4.25%)
                try:
                    supply_base_apr = float(pool.get("supplyAPY", 0))
                except (TypeError, ValueError):
                    supply_base_apr = 0.0
                try:
                    borrow_base_apr = float(pool.get("borrowAPY", 0))
                except (TypeError, ValueError):
                    borrow_base_apr = 0.0

                # Get reward APRs from rewards map
                rewards_key = (full_market_type, token_coin_type)
                rewards = rewards_map.get(rewards_key, {"supply_reward_apr": 0.0, "borrow_reward_apr": 0.0})
                supply_reward_apr = rewards["supply_reward_apr"]
                borrow_reward_apr = rewards["borrow_reward_apr"]

                # LTV values (already decimal)
                try:
                    max_ltv = float(pool.get("maxLTV", 0))
                except (TypeError, ValueError):
                    max_ltv = 0.0
                try:
                    liq_ltv = float(pool.get("liqLTV", 0))
                except (TypeError, ValueError):
                    liq_ltv = 0.0

                # Store data
                lend_rates_data.append(
                    {
                        "Token": token_symbol,
                        "Market": market_name,
                        "Supply_base_apr": supply_base_apr,
                        "Supply_reward_apr": supply_reward_apr,
                        "Supply_apr": supply_base_apr + supply_reward_apr,
                        "Borrow_base_apr": borrow_base_apr,
                        "Borrow_reward_apr": borrow_reward_apr,
                        "Borrow_apr": borrow_base_apr - borrow_reward_apr,
                        "Price": price,
                        "Total_supply": total_supply,
                        "Total_supply_usd": total_supply_usd,
                        "Total_borrow": total_borrow,
                        "Total_borrow_usd": total_borrow_usd,
                        "Available_borrow": available_borrow,
                        "Available_borrow_usd": available_borrow_usd,
                        "Utilization": utilization,
                        "Token_coin_type": token_coin_type,
                        "Market_type": full_market_type,
                        "Market_id": market_id,
                    }
                )

                borrow_rates_data.append(
                    {
                        "Token": token_symbol,
                        "Market": market_name,
                        "Borrow_apr": borrow_base_apr - borrow_reward_apr,
                        "Base_rate": borrow_base_apr,
                        "Reward_rate": borrow_reward_apr,
                        "Price": price,
                        "Token_coin_type": token_coin_type,
                    }
                )

                collateral_ratios_data.append(
                    {
                        "Token": token_symbol,
                        "Market": market_name,
                        "Collateralization_factor": max_ltv,
                        "Liquidation_threshold": liq_ltv,
                        "Token_coin_type": token_coin_type,
                    }
                )

                total_pools += 1

        print(f"\tFound {total_pools} active pools across all markets")

        lend_rates = pd.DataFrame(lend_rates_data)
        borrow_rates = pd.DataFrame(borrow_rates_data)
        collateral_ratios = pd.DataFrame(collateral_ratios_data)
        
        return lend_rates, borrow_rates, collateral_ratios


# Example usage
if __name__ == "__main__":
    reader = PebbleReader()
    
    lend_df, borrow_df, collateral_df = reader.get_all_data()
    
    print("\n" + "="*80)
    print("LENDING RATES (including rewards):")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", None):
        print(lend_df)
    
    print("\n" + "="*80)
    print("BORROW RATES:")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", None):
        print(borrow_df)

    print("\n" + "="*80)
    print("COLLATERAL RATIOS (LTV):")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None, "display.width", None):
        print(collateral_df)
