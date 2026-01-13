import json
import os
import subprocess
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd


@dataclass
class SuilendReaderConfig:
    node_script_path: str  # e.g. "data/suilend_reader-sdk.mjs"
    rpc_url: str = "https://rpc.mainnet.sui.io"


class SuilendReader:
    """
    Wraps the Suilend JS SDK via a Node script and returns
    Navi-shaped DataFrames for lend / borrow / collateral.

    All APR fields are returned as DECIMAL rates (e.g. 0.0316 = 3.16% APR).
    Collateralization factors are returned as DECIMALS (e.g. 0.70 = 70% LTV).
    """

    def __init__(self, config: SuilendReaderConfig):
        self.config = config

    # ---------- public API ----------

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        reserves = self._get_all_reserves()

        lend_rows: List[Dict[str, Any]] = []
        borrow_rows: List[Dict[str, Any]] = []
        collateral_rows: List[Dict[str, Any]] = []

        for r in reserves:
            token = r.get("token_symbol")
            coin_type = r.get("token_contract")
            
            if not token or not coin_type:
                continue

            # Parse APRs from the SDK output (they're in percent strings)
            price = self._to_float(r.get("price"))
            lend_base = self._parse_percent(r.get("lend_apr_base"))
            lend_reward = self._parse_percent(r.get("lend_apr_reward"))
            lend_total = self._parse_percent(r.get("lend_apr_total"))
            
            borrow_base = self._parse_percent(r.get("borrow_apr_base"))
            borrow_reward = self._parse_percent(r.get("borrow_apr_reward"))
            borrow_total = self._parse_percent(r.get("borrow_apr_total"))
            
            total_supplied = self._to_float(r.get("total_supplied"))
            total_borrowed = self._to_float(r.get("total_borrowed"))
            utilization = self._parse_percent(r.get("utilisation"))
            available_amount_usd = self._to_float(r.get("available_amount_usd"))

            # Parse collateral data (these come as percentages, convert to decimals)
            collateralization_factor = self._parse_percent(r.get("collateralization_factor"))
            liquidation_threshold = self._parse_percent(r.get("liquidation_threshold"))
            
            # Parse fee data (in basis points)
            borrow_fee_bps = self._to_float(r.get("borrow_fee_bps"))
            spread_fee_bps = self._to_float(r.get("spread_fee_bps"))

            # Lend data
            lend_rows.append({
                "Token": token,
                "Supply_base_apr": lend_base,
                "Supply_reward_apr": lend_reward,
                "Supply_apr": lend_total,
                "Price": price,
                "Total_supply": total_supplied,
                "Utilization": utilization,
                "Available_borrow_usd": available_amount_usd,
                "Token_coin_type": coin_type,
            })

            # Borrow data
            borrow_rows.append({
                "Token": token,
                "Borrow_base_apr": borrow_base,
                "Borrow_reward_apr": borrow_reward,
                "Borrow_apr": borrow_total,
                "Price": price,
                "Total_borrow": total_borrowed,
                "Utilization": utilization,
                "Borrow_fee_bps": borrow_fee_bps,
                "Spread_fee_bps": spread_fee_bps,
                "Token_coin_type": coin_type,
            })

            # Collateral data
            collateral_rows.append({
                "Token": token,
                "Collateralization_factor": collateralization_factor,
                "Liquidation_threshold": liquidation_threshold,
                "Token_coin_type": coin_type,
            })

        npools = len(lend_rows)
        print(f"\t\tfound {npools} lending pools")
        lend_df = pd.DataFrame(lend_rows)
        borrow_df = pd.DataFrame(borrow_rows)
        collateral_df = pd.DataFrame(collateral_rows)

        return lend_df, borrow_df, collateral_df

    # ---------- internals ----------

    def _get_all_reserves(self) -> List[Dict[str, Any]]:
        env = os.environ.copy()
        env["SUI_RPC_URL"] = self.config.rpc_url

        res = subprocess.run(
            ["node", self.config.node_script_path],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        if res.returncode != 0:
            raise RuntimeError(f"Suilend node script failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Node did not return valid JSON. Raw stdout:\n{res.stdout}")

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Suilend JSON shape: {type(data)}")

        return data

    @staticmethod
    def _to_float(x: Any) -> Optional[float]:
        if x is None:
            return None
        try:
            return float(x)
        except Exception:
            return None

    @staticmethod
    def _parse_percent(x: Any) -> Optional[float]:
        """Convert percent string to decimal (e.g. '3.160' -> 0.03160 or '70.000' -> 0.70)"""
        if x is None:
            return None
        try:
            return float(x) / 100.0
        except Exception:
            return None

# Example usage
if __name__ == "__main__":
    from dataclasses import dataclass
    
    config = SuilendReaderConfig(
        node_script_path="data/suilend/suilend_reader-sdk.mjs"
    )
    reader = SuilendReader(config)
    
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