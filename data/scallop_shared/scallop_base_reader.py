import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd
import requests

# Import centralized RPC URL from settings
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from config.settings import SUI_RPC_URL


@dataclass
class ScallopReaderConfig:
    node_script_path: str  # e.g. "data/scallop_shared/scallop_reader-sdk.mjs"
    rpc_url: str = SUI_RPC_URL
    debug: bool = False  # Set to True to see raw SDK output


class ScallopBaseReader:
    """
    Base reader for Scallop protocol data.
    Wraps the Scallop JS SDK via Node script and returns DataFrames.

    All APR fields are returned as DECIMAL rates (e.g. 0.0316 = 3.16% APR).
    APRs come pre-converted from the JS SDK (already divided by 100).
    No further conversion needed (unlike Suilend which divides again).
    """

    def __init__(self, config: ScallopReaderConfig):
        self.config = config

    # ---------- public API ----------

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Fetch market data and return lend, borrow, collateral DataFrames"""
        markets = self._get_all_markets()
        return self._transform_to_dataframes(markets)

    # ---------- internals ----------

    def _get_all_markets(self) -> List[Dict[str, Any]]:
        """Fetch market data with SDK-first, API-fallback strategy"""
        try:
            return self._get_markets_from_sdk()
        except Exception as sdk_error:
            print(f"\t\tSDK failed: {sdk_error}")
            print(f"\t\tTrying API fallback...")
            return self._get_markets_from_api()

    def _get_markets_from_sdk(self) -> List[Dict[str, Any]]:
        """Call Node.js SDK wrapper and parse JSON output"""
        print(f"\t\t[SDK] Starting Scallop SDK call via Node.js...")
        start_time = time.time()

        env = os.environ.copy()
        env["SUI_RPC_URL"] = self.config.rpc_url

        # Enable debug mode if requested
        if self.config.debug:
            env["SCALLOP_DEBUG"] = "1"

        try:
            res = subprocess.run(
                ["node", self.config.node_script_path],
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=60,  # 60 second timeout to prevent indefinite hangs
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Scallop node script timed out after 60 seconds (RPC may be unresponsive)")

        elapsed = time.time() - start_time
        print(f"\t\t[SDK] Scallop SDK call completed in {elapsed:.2f} seconds")

        # ALWAYS show timing logs from stderr (not just in debug mode)
        if res.stderr:
            # Print only lines that start with [SDK-JS] for timing visibility
            for line in res.stderr.splitlines():
                if line.strip().startswith("[SDK-JS]") or line.strip().startswith("Warning:"):
                    print(f"\t\t{line}")

        if res.returncode != 0:
            raise RuntimeError(
                f"Scallop node script failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}"
            )

        # Print debug output (stderr) if debug mode is on
        if self.config.debug and res.stderr:
            print("\n" + "="*80)
            print("DEBUG OUTPUT FROM NODE.JS SDK:")
            print("="*80)
            print(res.stderr)
            print("="*80 + "\n")

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Node did not return valid JSON. Raw stdout:\n{res.stdout}"
            )

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Scallop JSON shape: {type(data)}")

        return data

    def _get_markets_from_api(self) -> List[Dict[str, Any]]:
        """Fetch market data from Scallop REST API as fallback"""
        base_url = "https://sdk.api.scallop.io"

        # 1. Get pools
        pools_resp = requests.get(f"{base_url}/api/market/pools", timeout=30).json()
        pools = {p["coinName"]: p for p in pools_resp["pools"]}

        # 2. Get collaterals
        collaterals_resp = requests.get(f"{base_url}/api/market/collaterals", timeout=30).json()
        collaterals = {c["coinName"]: c for c in collaterals_resp["collaterals"]}

        # 3. For each pool, get borrow incentives
        markets = []
        for coin_name, pool in pools.items():
            coin_type = pool["coinType"]

            # Get borrow rewards for this coin
            borrow_reward_apr = 0
            try:
                incentive_resp = requests.get(
                    f"{base_url}/api/borrowIncentivePool/{coin_type}",
                    timeout=10
                ).json()

                # Sum all reward APRs
                for reward in incentive_resp["borrowIncentivePool"]["rewards"]:
                    borrow_reward_apr += reward["rewardApr"]
            except Exception:
                pass  # No borrow rewards for this coin

            # Supply rewards = 0 (ignore per user request)
            supply_reward_apr = 0

            # Get collateral data
            collateral = collaterals.get(coin_name, {})

            # Calculate APRs (matching SDK logic)
            supply_base_apr = pool["supplyApr"]
            supply_total_apr = supply_base_apr + supply_reward_apr
            borrow_base_apr = pool["borrowApr"]
            borrow_total_apr = borrow_base_apr - borrow_reward_apr  # Rewards reduce cost

            # Calculate available amount
            available_coin = pool["supplyCoin"] - pool["borrowCoin"]
            available_usd = available_coin * pool["coinPrice"]

            # Build market object (matching SDK output format)
            markets.append({
                "token_symbol": coin_name.upper(),
                "token_contract": coin_type,
                "price": str(pool["coinPrice"]),
                "lend_apr_base": str(supply_base_apr),
                "lend_apr_reward": str(supply_reward_apr),
                "lend_apr_total": str(supply_total_apr),
                "borrow_apr_base": str(borrow_base_apr),
                "borrow_apr_reward": str(borrow_reward_apr),
                "borrow_apr_total": str(borrow_total_apr),
                "total_supplied": str(pool["supplyCoin"]),
                "total_borrowed": str(pool["borrowCoin"]),
                "utilisation": str(pool["utilizationRate"]),
                "available_amount_usd": str(available_usd),
                "collateralization_factor": str(collateral.get("collateralFactor", 0)),
                "liquidation_threshold": str(collateral.get("liquidationFactor", 0)),
                "borrow_fee": str(pool["borrowFee"]),
                "borrow_weight": str(pool.get("borrowWeight", 1.0)),
            })

        return markets

    def _transform_to_dataframes(
        self, markets: List[Dict[str, Any]]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Transform market data into 3 DataFrames"""
        lend_rows: List[Dict[str, Any]] = []
        borrow_rows: List[Dict[str, Any]] = []
        collateral_rows: List[Dict[str, Any]] = []

        for m in markets:
            token = m.get("token_symbol")
            coin_type = m.get("token_contract")

            if not token or not coin_type:
                continue

            # Parse fields (APRs are already decimals from JS)
            price = self._to_float(m.get("price"))
            lend_base = self._to_float(m.get("lend_apr_base"))
            lend_reward = self._to_float(m.get("lend_apr_reward"))
            lend_total = self._to_float(m.get("lend_apr_total"))

            borrow_base = self._to_float(m.get("borrow_apr_base"))
            borrow_reward = self._to_float(m.get("borrow_apr_reward"))
            borrow_total = self._to_float(m.get("borrow_apr_total"))

            total_supplied = self._to_float(m.get("total_supplied"))
            total_borrowed = self._to_float(m.get("total_borrowed"))
            utilization = self._to_float(m.get("utilisation"))
            available_amount_usd = self._to_float(m.get("available_amount_usd"))

            # Parse collateral data (already decimals from JS)
            collateralization_factor = self._to_float(
                m.get("collateralization_factor")
            )
            liquidation_threshold = self._to_float(m.get("liquidation_threshold"))

            # Parse fee data (already decimal from JS)
            borrow_fee = self._to_float(m.get("borrow_fee"))

            # Parse borrow weight (default 1.0)
            borrow_weight = self._to_float(m.get("borrow_weight"))
            if borrow_weight is None:
                borrow_weight = 1.0

            # Lend data
            lend_rows.append(
                {
                    "Token": token,
                    "Supply_base_apr": lend_base,
                    "Supply_reward_apr": lend_reward,
                    "Supply_apr": lend_total,
                    "Price": price,
                    "Total_supply": total_supplied,
                    "Utilization": utilization,
                    "Available_borrow_usd": available_amount_usd,
                    "Borrow_fee": borrow_fee,
                    "Borrow_weight": borrow_weight,
                    "Liquidation_ltv": liquidation_threshold,
                    "Token_coin_type": coin_type,
                }
            )

            # Borrow data
            borrow_rows.append(
                {
                    "Token": token,
                    "Borrow_base_apr": borrow_base,
                    "Borrow_reward_apr": borrow_reward,
                    "Borrow_apr": borrow_total,
                    "Price": price,
                    "Total_borrow": total_borrowed,
                    "Utilization": utilization,
                    "Borrow_fee": borrow_fee,
                    "Borrow_weight": borrow_weight,
                    "Liquidation_ltv": liquidation_threshold,
                    "Token_coin_type": coin_type,
                }
            )

            # Collateral data
            collateral_rows.append(
                {
                    "Token": token,
                    "Collateralization_factor": collateralization_factor,
                    "Liquidation_threshold": liquidation_threshold,
                    "Token_coin_type": coin_type,
                }
            )

        npools = len(lend_rows)
        print(f"\t\tfound {npools} Scallop lending pools")

        lend_df = pd.DataFrame(lend_rows)
        borrow_df = pd.DataFrame(borrow_rows)
        collateral_df = pd.DataFrame(collateral_rows)

        return lend_df, borrow_df, collateral_df

    @staticmethod
    def _to_float(x: Any) -> Optional[float]:
        """Safely convert to float"""
        if x is None:
            return None
        try:
            return float(x)
        except Exception:
            return None


# Example usage
if __name__ == "__main__":
    config = ScallopReaderConfig(
        node_script_path="data/scallop_shared/scallop_reader-sdk.mjs",
        debug=True  # Set to True to see raw SDK output
    )
    reader = ScallopBaseReader(config)

    lend_df, borrow_df, collateral_df = reader.get_all_data()

    print("\n" + "=" * 80)
    print("LENDING RATES (including rewards):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(lend_df)

    print("\n" + "=" * 80)
    print("BORROW RATES:")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(borrow_df)

    print("\n" + "=" * 80)
    print("COLLATERAL RATIOS (LTV):")
    print("=" * 80)
    with pd.option_context("display.max_rows", None, "display.max_columns", None):
        print(collateral_df)
