"""
Refresh Pipeline

Single orchestration entrypoint used by both main.py (CLI scheduler) and the Streamlit dashboard.

Responsibilities (per run):
1) Fetch + merge protocol data (Navi / AlphaFi / Suilend) via merge_protocol_data()
2) Run strategy analysis via RateAnalyzer
3) Persist snapshots to DB via RateTracker (if enabled)
4) Return data + analysis results for presentation / alerting
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

import pandas as pd

from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS
from data.protocol_merger import merge_protocol_data
from analysis.rate_analyzer import RateAnalyzer
from data.rate_tracker import RateTracker


@dataclass
class RefreshResult:
    timestamp: datetime

    # Raw merged protocol data
    lend_rates: pd.DataFrame
    borrow_rates: pd.DataFrame
    collateral_ratios: pd.DataFrame
    prices: pd.DataFrame
    lend_rewards: pd.DataFrame
    borrow_rewards: pd.DataFrame

    # Strategy outputs
    protocol_A: Optional[str]
    protocol_B: Optional[str]
    all_results: pd.DataFrame
    stablecoin_results: pd.DataFrame

    # DB / token discovery summary
    token_summary: Dict[str, Any]


def refresh_pipeline(
    *,
    timestamp: Optional[datetime] = None,
    stablecoin_contracts=STABLECOIN_CONTRACTS,
    liquidation_distance: float = settings.DEFAULT_LIQUIDATION_DISTANCE,
    save_snapshots: bool = settings.SAVE_SNAPSHOTS,
) -> RefreshResult:
    """Run one full refresh: fetch -> merge -> (optional) save -> analyze.

    Returns a RefreshResult containing both the merged market data and the analysis outputs.
    """
    ts = timestamp or datetime.now()

    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards = merge_protocol_data(
        stablecoin_contracts=stablecoin_contracts
    )

    # Persist snapshot early, so even if analysis fails you still capture the raw state.
    if save_snapshots:
        tracker = RateTracker(
            use_cloud=getattr(settings, "USE_CLOUD_DB", False),
            db_path=getattr(settings, "SQLITE_PATH", "data/lending_rates.db"),
            connection_url=getattr(settings, "SUPABASE_URL", None),
        )

        # Upsert token registry (reserve tokens + any reward token contracts available)
        tokens_df_rows = []
        def _add_tokens_from_df(df: pd.DataFrame, seen_flag: str, role_flag: str):
            if df is None or df.empty:
                return
            proto_vals = set(str(p).lower() for p in df.get('Protocol', pd.Series([], dtype=str)).dropna().unique())
            seen_on_navi = int('navi' in proto_vals)
            seen_on_alphafi = int('alphafi' in proto_vals or 'alpha' in proto_vals)
            seen_on_suilend = int('suilend' in proto_vals)
            if 'Contract' in df.columns:
                for c in df['Contract'].dropna().unique():
                    tokens_df_rows.append({
                        'token_contract': c,
                        seen_flag: 1,
                        role_flag: 1,
                        'seen_on_navi': seen_on_navi,
                        'seen_on_alphafi': seen_on_alphafi,
                        'seen_on_suilend': seen_on_suilend,
                    })

            # Heuristic: if reward token contracts are present in this df, collect them too
            for col in df.columns:
                col_l = str(col).lower()
                if 'reward' in col_l and 'contract' in col_l:
                    for c in df[col].dropna().unique():
                        tokens_df_rows.append({
                            'token_contract': c,
                            seen_flag: 1,
                            role_flag: 1,
                            'seen_on_navi': seen_on_navi,
                            'seen_on_alphafi': seen_on_alphafi,
                            'seen_on_suilend': seen_on_suilend,
                        })

        _add_tokens_from_df(lend_rates, 'seen_as_reserve', 'seen_as_reserve')
        _add_tokens_from_df(borrow_rates, 'seen_as_reserve', 'seen_as_reserve')
        _add_tokens_from_df(collateral_ratios, 'seen_as_reserve', 'seen_as_reserve')
        _add_tokens_from_df(lend_rewards, 'seen_as_reward_lend', 'seen_as_reward_lend')
        _add_tokens_from_df(borrow_rewards, 'seen_as_reward_borrow', 'seen_as_reward_borrow')

        if tokens_df_rows:
            tokens_df = pd.DataFrame(tokens_df_rows).groupby('token_contract', as_index=False).max()
        else:
            tokens_df = pd.DataFrame(columns=['token_contract'])

        token_summary = tracker.upsert_token_registry(tokens_df)

        tracker.save_snapshot(
            timestamp=ts,
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
        )

    token_summary = locals().get('token_summary', {'seen': 0, 'inserted': 0, 'updated': 0, 'total': 0})

    analyzer = RateAnalyzer(
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        liquidation_distance=liquidation_distance,
    )

    protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

    stablecoin_results = pd.DataFrame()
    if protocol_A and protocol_B:
        stablecoin_results = analyzer.find_best_stablecoin_pairs(protocol_A, protocol_B)

    return RefreshResult(
        timestamp=ts,
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        protocol_A=protocol_A,
        protocol_B=protocol_B,
        all_results=all_results,
        stablecoin_results=stablecoin_results,
        token_summary=token_summary,
    )