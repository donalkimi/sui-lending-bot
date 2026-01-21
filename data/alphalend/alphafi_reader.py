import json
import os
import subprocess
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any, Optional

import pandas as pd

# Import centralized RPC URL from settings
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from config.settings import SUI_RPC_URL


@dataclass
class AlphaFiReaderConfig:
    node_script_path: str  # e.g. "data/alphalend/alphalend_reader-sdk.mjs" or absolute path
    rpc_url: str = SUI_RPC_URL
    network: str = "mainnet"


class AlphaFiReader:
    """
    Wraps the AlphaFi JS SDK (getAllMarkets) via a Node script and returns
    Navi-shaped DataFrames for lend / borrow / collateral.

    All APR fields are returned as DECIMAL rates (e.g. 0.0316 = 3.16% APR).
    """

    def __init__(self, config: AlphaFiReaderConfig):
        self.config = config

    # ---------- public API ----------

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        markets = self._get_all_markets()

        lend_rows: List[Dict[str, Any]] = []
        borrow_rows: List[Dict[str, Any]] = []
        collateral_rows: List[Dict[str, Any]] = []

        for m in markets:
            coin_type = m.get("coinType")
            if not coin_type:
                continue

            token = self._symbol_from_coin_type(coin_type)

            # Common fields
            price = self._to_float(m.get("price"))
            total_supply = self._to_float(m.get("totalSupply"))
            total_borrow = self._to_float(m.get("totalBorrow"))
            # Use allowedBorrowAmount (not availableLiquidity) for available borrow
            allowed_borrow_amount = self._to_float(m.get("allowedBorrowAmount"))
            utilization = self._to_float(m.get("utilizationRate"))  # already 0..1 in output
            # Extract borrow fee (as decimal, e.g., 0.003 = 0.3%)
            borrow_fee = self._to_float(m.get("borrowFee"))

            # Derived USD (only if we have both pieces)
            total_supply_usd = (total_supply * price) if (total_supply is not None and price is not None) else None
            total_borrow_usd = (total_borrow * price) if (total_borrow is not None and price is not None) else None
            # Calculate available_borrow_usd from allowedBorrowAmount * price
            available_borrow_usd = (allowed_borrow_amount * price) if (allowed_borrow_amount is not None and price is not None) else None

            # ----- Supply APR components -----
            supply_apr_obj = m.get("supplyApr") or {}
            supply_interest_pct = self._to_float(supply_apr_obj.get("interestApr")) or 0.0
            supply_staking_pct = self._to_float(supply_apr_obj.get("stakingApr")) or 0.0
            supply_rewards_pct = self._sum_reward_apr_pct(supply_apr_obj.get("rewards"))

            supply_base_apr = (supply_interest_pct + supply_staking_pct) / 100.0
            supply_reward_apr = supply_rewards_pct / 100.0
            supply_apr = supply_base_apr + supply_reward_apr

            lend_rows.append({
                "Token": token,
                "Supply_base_apr": supply_base_apr,
                "Supply_reward_apr": supply_reward_apr,
                "Supply_apr": supply_apr,
                "Price": price,
                "Total_supply": total_supply,
                "Total_supply_usd": total_supply_usd,
                "Available_borrow": allowed_borrow_amount,
                "Available_borrow_usd": available_borrow_usd,
                "Utilization": utilization,
                "Borrow_fee": borrow_fee,  # Same fee applies to both lend and borrow
                "Token_coin_type": coin_type,
            })

            # ----- Borrow APR components -----
            borrow_apr_obj = m.get("borrowApr") or {}
            borrow_interest_pct = self._to_float(borrow_apr_obj.get("interestApr")) or 0.0
            borrow_rewards_pct = self._sum_reward_apr_pct(borrow_apr_obj.get("rewards"))

            borrow_base_apr = borrow_interest_pct / 100.0
            borrow_reward_apr = borrow_rewards_pct / 100.0
            borrow_apr = borrow_base_apr - borrow_reward_apr

            borrow_rows.append({
                "Token": token,
                "Borrow_base_apr": borrow_base_apr,
                "Borrow_reward_apr": borrow_reward_apr,
                "Borrow_apr": borrow_apr,
                "Price": price,
                "Total_borrow": total_borrow,
                "Total_borrow_usd": total_borrow_usd,
                "Available_borrow": allowed_borrow_amount,
                "Available_borrow_usd": available_borrow_usd,
                "Utilization": utilization,
                "Borrow_fee": borrow_fee,  # Decimal format (0.003 = 0.3%)
                "Token_coin_type": coin_type,
            })

            # ----- Collateral (LTV/threshold) -----
            ltv_pct = self._to_float(m.get("ltv"))
            liq_thresh_pct = self._to_float(m.get("liquidationThreshold"))

            collateral_rows.append({
                "Token": token,
                "Collateralization_factor": (ltv_pct / 100.0) if ltv_pct is not None else None,
                "Liquidation_threshold": (liq_thresh_pct / 100.0) if liq_thresh_pct is not None else None,
                "Token_coin_type": coin_type,
            })
        
        npools = len(lend_rows)
        print(f"\t\tfound {npools} lending pools")
        lend_df = pd.DataFrame(lend_rows)
        borrow_df = pd.DataFrame(borrow_rows)
        collateral_df = pd.DataFrame(collateral_rows)

        return lend_df, borrow_df, collateral_df

    # ---------- internals ----------

    def _get_all_markets(self) -> List[Dict[str, Any]]:
        env = os.environ.copy()
        env["SUI_RPC_URL"] = self.config.rpc_url
        env["ALPHAFI_NETWORK"] = self.config.network

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
            raise RuntimeError(f"AlphaFi node script timed out after 60 seconds (RPC may be unresponsive)")

        if res.returncode != 0:
            raise RuntimeError(f"AlphaFi node script failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"Node did not return valid JSON. Raw stdout:\n{res.stdout}")

        # Accept either list-of-markets or {"markets":[...]}
        if isinstance(data, dict) and "markets" in data:
            data = data["markets"]

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected getAllMarkets() JSON shape: {type(data)}")

        return data

    @staticmethod
    def _symbol_from_coin_type(coin_type: str) -> str:
        # Best-effort: last segment after ::
        # e.g. 0x..::lbtc::LBTC -> LBTC
        parts = str(coin_type).split("::")
        return parts[-1] if parts else str(coin_type)

    @staticmethod
    def _to_float(x: Any) -> Optional[float]:
        if x is None:
            return None
        try:
            return float(x)
        except Exception:
            return None

    @staticmethod
    def _sum_reward_apr_pct(rewards: Any) -> float:
        """
        AlphaFi rewards are usually a list of objects, often with 'rewardApr'.
        Return sum in PERCENT units (not decimal).
        """
        if not rewards:
            return 0.0
        total = 0.0
        if isinstance(rewards, list):
            for r in rewards:
                if isinstance(r, dict):
                    total += float(r.get("rewardApr", 0) or 0)
                else:
                    # if reward list is numeric for some reason
                    try:
                        total += float(r)
                    except Exception:
                        pass
        return total


# Example usage
if __name__ == "__main__":
    from dataclasses import dataclass
    
    config = AlphaFiReaderConfig(
        node_script_path="data/alphalend/alphalend_reader-sdk.mjs"
    )
    reader = AlphaFiReader(config)
    
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