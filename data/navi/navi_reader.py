"""
Navi Protocol API Reader

Pulls live pool data from Navi's public API and builds a lending DataFrame
with clearly separated base/reward APRs and USD liquidity metrics.
"""

import pandas as pd
import requests
from typing import Tuple
from data.navi.navi_fees import get_navi_borrow_fee


class NaviReader:
    """Read lending data from Navi Protocol API."""

    # API endpoint
    API_URL = "https://open-api.naviprotocol.io/api/navi/pools?env=prod&sdk=1.3.4-dev.2"

    def __init__(self):
        """Initialize the Navi reader."""
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def _fetch_pools_data(self) -> dict:
        """
        Fetch raw pools data from Navi API.

        Returns:
            Dictionary with pools data.
        """
        try:
            response = self.session.get(self.API_URL, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch Navi data: {e}")
    
    @staticmethod
    def _parse_rate_scaled(rate_value) -> float:
        """
        Navi encodes some ratios (e.g., LTV) as integer * 1e27.
        Convert to decimal; return 0.0 on parse errors.
        """
        try:
            return int(rate_value) / 1e27
        except (TypeError, ValueError):
            return 0.0

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Fetch all data from Navi Protocol.

        Returns:
            Tuple of (lend_df, borrow_df, collateral_df)

        Lending DataFrame columns:
            - Token (symbol)
            - Supply_base_apr       (vaultApr, decimal, e.g. 0.01 for 1%)
            - Supply_reward_apr     (boostedApr, decimal)
            - Supply_apr            (calculated: base + reward)
            - Supply_apy            (apy from API, decimal)
            - Borrow_base_apr       (vaultApr on borrow side, decimal)
            - Borrow_reward_apr     (boostedApr on borrow side, decimal)
            - Borrow_apr            (calculated: base - reward)
            - Borrow_apy            (apy from API on borrow side, decimal)
            - price                 (USD price)
            - Total_supply
            - Total_supply_usd
            - Total_borrow
            - Total_borrow_usd
            - Available_borrow
            - Available_borrow_usd
            - Utilization           (Total_borrow / Total_supply)
            - Token_coin_type
            - Reserve_id
            - Pool_id
        
        Borrow DataFrame columns:
            - Token
            - Borrow_apr            (calculated: base - reward)
            - Base_rate             (base APR)
            - Reward_rate           (reward APR)
            - Borrow_apy            (API-provided APY)
            - price                 (USD price)
            - Token_coin_type       (contract address)
        
        Collateral DataFrame columns:
            - Token
            - Collateralization_factor  (LTV)
            - Liquidation_threshold
            - Token_coin_type       (contract address)
        """

        # Fetch raw data
        data = self._fetch_pools_data()

        if "data" not in data:
            raise ValueError("Unexpected API response structure")

        pools = data["data"]

        lend_rates_data = []
        borrow_rates_data = []
        collateral_ratios_data = []

        active_pools = 0
        deprecated_pools = 0

        for pool in pools:
            # Skip deprecated pools
            if pool.get("status") != "active":
                deprecated_pools += 1
                continue

            # Token info
            token_info = pool.get("token", {}) or {}
            token_symbol = token_info.get("symbol")
            token_coin_type = token_info.get("coinType")
            if not token_symbol:
                continue

            # Contract info
            contract_info = pool.get("contract", {}) or {}
            reserve_id = contract_info.get("reserveId")
            pool_id = contract_info.get("pool")

            # Oracle / price
            oracle_info = pool.get("oracle", {}) or {}
            try:
                price = float(oracle_info.get("price", 0.0))
            except (TypeError, ValueError):
                price = 0.0

            # Token decimals (for scaling raw amounts)
            try:
                decimals = int(token_info.get("decimals", 0))
            except (TypeError, ValueError):
                decimals = 0
            scale = 10 ** decimals if decimals > 0 else 1

            # Supply / borrow amounts (raw units Ã¢â€ â€™ token amounts)
            try:
                total_supply_raw = float(pool.get("totalSupply", 0))
            except (TypeError, ValueError):
                total_supply_raw = 0.0
            try:
                total_borrow_raw = float(pool.get("totalBorrow", 0))
            except (TypeError, ValueError):
                total_borrow_raw = 0.0
            try:
                available_borrow_raw = float(pool.get("availableBorrow", 0))
            except (TypeError, ValueError):
                available_borrow_raw = 0.0

            total_supply = total_supply_raw / scale
            total_borrow = total_borrow_raw / scale
            available_borrow = available_borrow_raw / 1e9  # API returns fixed 10^9 precision

            total_supply_usd = total_supply * price
            total_borrow_usd = total_borrow * price
            available_borrow_usd = available_borrow * price

            utilization = (total_borrow / total_supply) if total_supply > 0 else 0.0

            # Supply APRs (percent in API Ã¢â€ â€™ decimals)
            supply_info = pool.get("supplyIncentiveApyInfo", {}) or {}
            try:
                supply_vault_apr_pct = float(supply_info.get("vaultApr", 0))
            except (TypeError, ValueError):
                supply_vault_apr_pct = 0.0
            try:
                supply_boosted_apr_pct = float(supply_info.get("boostedApr", 0))
            except (TypeError, ValueError):
                supply_boosted_apr_pct = 0.0
            try:
                supply_apy_pct = float(supply_info.get("apy", 0))
            except (TypeError, ValueError):
                supply_apy_pct = 0.0

            supply_base_apr = supply_vault_apr_pct / 100.0
            supply_reward_apr = supply_boosted_apr_pct / 100.0
            supply_total_apy = supply_apy_pct / 100.0

            # Borrow APRs
            borrow_info = pool.get("borrowIncentiveApyInfo", {}) or {}
            try:
                borrow_vault_apr_pct = float(borrow_info.get("vaultApr", 0))
            except (TypeError, ValueError):
                borrow_vault_apr_pct = 0.0
            try:
                borrow_boosted_apr_pct = float(borrow_info.get("boostedApr", 0))
            except (TypeError, ValueError):
                borrow_boosted_apr_pct = 0.0
            try:
                borrow_apy_pct = float(borrow_info.get("apy", 0))
            except (TypeError, ValueError):
                borrow_apy_pct = 0.0

            borrow_base_apr = borrow_vault_apr_pct / 100.0
            borrow_reward_apr = borrow_boosted_apr_pct / 100.0
            borrow_total_apy = borrow_apy_pct / 100.0

            # Collateral (LTV)
            ltv = self._parse_rate_scaled(pool.get("ltv", 0))
            
            # Liquidation threshold
            liquidation_factor = pool.get("liquidationFactor", {}) or {}
            try:
                liquidation_threshold = float(liquidation_factor.get("threshold", 0))
            except (TypeError, ValueError):
                liquidation_threshold = 0.0

            # Store data (one row per pool)
            lend_rates_data.append(
                {
                    "Token": token_symbol,
                    "Supply_base_apr": supply_base_apr,
                    "Supply_reward_apr": supply_reward_apr,
                    "Supply_apr": supply_base_apr + supply_reward_apr,
                    "Supply_apy": supply_total_apy,
                    "Borrow_base_apr": borrow_base_apr,
                    "Borrow_reward_apr": borrow_reward_apr,
                    "Borrow_apr": borrow_base_apr - borrow_reward_apr,
                    "Borrow_apy": borrow_total_apy,
                    "Price": price,
                    "Total_supply": total_supply,
                    "Total_supply_usd": total_supply_usd,
                    "Total_borrow": total_borrow,
                    "Total_borrow_usd": total_borrow_usd,
                    "Available_borrow": available_borrow,
                    "Available_borrow_usd": available_borrow_usd,
                    "Utilization": utilization,
                    "Borrow_fee": get_navi_borrow_fee(token_symbol=token_symbol, token_contract=token_coin_type),
                    "Borrow_weight": 1.0,  # Navi does not have borrow weights
                    "Liquidation_ltv": liquidation_threshold,
                    "Token_coin_type": token_coin_type,
                    "Reserve_id": reserve_id,
                    "Pool_id": pool_id,
                }
            )

            borrow_rates_data.append(
                {
                    "Token": token_symbol,
                    "Borrow_apr": borrow_base_apr - borrow_reward_apr,
                    "Base_rate": borrow_base_apr,
                    "Reward_rate": borrow_reward_apr,
                    "Borrow_apy": borrow_total_apy,
                    "Price": price,
                    "Borrow_fee": get_navi_borrow_fee(token_symbol=token_symbol, token_contract=token_coin_type),
                    "Borrow_weight": 1.0,  # Navi does not have borrow weights
                    "Liquidation_ltv": liquidation_threshold,
                    "Token_coin_type": token_coin_type,
                }
            )

            collateral_ratios_data.append(
                {
                    "Token": token_symbol,
                    "Collateralization_factor": ltv,
                    "Liquidation_threshold": liquidation_threshold,
                    "Token_coin_type": token_coin_type,
                }
            )

            active_pools += 1

        print(f"\t\tfound {active_pools} active pools")
        if deprecated_pools > 0:
            print(f"\t\tSkipped {deprecated_pools} deprecated pools")

        lend_rates = pd.DataFrame(lend_rates_data)
        borrow_rates = pd.DataFrame(borrow_rates_data)
        collateral_ratios = pd.DataFrame(collateral_ratios_data)
        return lend_rates, borrow_rates, collateral_ratios


# Example usage
if __name__ == "__main__":
    reader = NaviReader()
    
    lend_df, borrow_df, collateral_df = reader.get_all_data()
    
    print("\n" + "="*80)
    print("LENDING RATES (including rewards):")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(lend_df)
    
    print("\n" + "="*80)
    print("BORROW RATES:")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(borrow_df)

    print("\n" + "="*80)
    print("COLLATERAL RATIOS (LTV):")
    print("="*80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(collateral_df)