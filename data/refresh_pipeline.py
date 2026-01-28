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
from typing import Optional, Tuple

import pandas as pd

from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS
from data.protocol_merger import merge_protocol_data
from analysis.rate_analyzer import RateAnalyzer
from data.rate_tracker import RateTracker
from alerts.slack_notifier import SlackNotifier
from utils.time_helpers import to_seconds, to_datetime_str


@dataclass
class RefreshResult:
    timestamp: int  # Unix timestamp in seconds

    # Raw merged protocol data
    lend_rates: pd.DataFrame
    borrow_rates: pd.DataFrame
    collateral_ratios: pd.DataFrame
    prices: pd.DataFrame
    lend_rewards: pd.DataFrame
    borrow_rewards: pd.DataFrame
    available_borrow: pd.DataFrame
    borrow_fees: pd.DataFrame
    borrow_weights: pd.DataFrame
    liquidation_thresholds: pd.DataFrame

    # Strategy outputs
    protocol_A: Optional[str]
    protocol_B: Optional[str]
    all_results: pd.DataFrame

    # Token registry update summary
    token_summary: dict


def refresh_pipeline(
    *,
    timestamp: Optional[datetime] = None,
    stablecoin_contracts=STABLECOIN_CONTRACTS,
    liquidation_distance: float = settings.DEFAULT_LIQUIDATION_DISTANCE,
    save_snapshots: bool = settings.SAVE_SNAPSHOTS,
    send_slack_notifications: bool = True,
) -> RefreshResult:
    """Run one full refresh: fetch -> merge -> (optional) save -> analyze.

    Args:
        timestamp: Optional timestamp for the refresh
        stablecoin_contracts: Contract addresses for stablecoins
        liquidation_distance: Liquidation distance setting for analysis
        save_snapshots: Whether to save snapshots to database
        send_slack_notifications: Whether to send Slack notifications (default: True)

    Returns:
        RefreshResult containing both the merged market data and the analysis outputs.
    """
    # Round timestamp to nearest minute to reduce granularity
    raw_ts = timestamp or datetime.now()
    ts = raw_ts.replace(second=0, microsecond=0)

    # Convert to seconds (Unix timestamp) - this is what we use internally
    current_seconds = int(ts.timestamp())


    notifier = SlackNotifier()
    print("[FETCH] Starting protocol data fetch...")
    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds = merge_protocol_data(
        stablecoin_contracts=stablecoin_contracts
    )
    print("[FETCH] Protocol data fetch complete")

    # Persist snapshot early, so even if analysis fails you still capture the raw state.
    token_summary = {"seen": 0, "inserted": 0, "updated": 0, "total": 0}  # Default if not saving

    # Create tracker instance (always needed for analysis cache)
    tracker = RateTracker(
        use_cloud=getattr(settings, "USE_CLOUD_DB", False),
        db_path=getattr(settings, "SQLITE_PATH", "data/lending_rates.db"),
        connection_url=getattr(settings, "SUPABASE_URL", None),
    )

    if save_snapshots:
        print("[DB] Saving snapshot to database...")
        tracker.save_snapshot(
            timestamp=ts,
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
            available_borrow=available_borrow,
            borrow_fees=borrow_fees,
            borrow_weights=borrow_weights,
            liquidation_thresholds=liquidation_thresholds,
        )
        
        # Update token registry - just use lend_rates with simple rename
        tokens_df = lend_rates[['Token', 'Contract']].copy()
        tokens_df.rename(columns={'Token': 'symbol', 'Contract': 'token_contract'}, inplace=True)
        
        token_summary = tracker.upsert_token_registry(
            tokens_df=tokens_df,
            timestamp=ts,
        )
        print("[DB] Snapshot saved successfully")

    # Initialize strategy results (always, regardless of save_snapshots)
    protocol_A: Optional[str] = None
    protocol_B: Optional[str] = None
    all_results: pd.DataFrame = pd.DataFrame()

    # Run analysis (always, regardless of save_snapshots)
    try:
        print("[ANALYSIS] Running rate analysis...")
        analyzer = RateAnalyzer(
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            liquidation_thresholds=liquidation_thresholds,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
            available_borrow=available_borrow,
            borrow_fees=borrow_fees,
            borrow_weights=borrow_weights,
            timestamp=current_seconds,  # Pass Unix timestamp in seconds (integer)
            liquidation_distance=liquidation_distance
        )

        protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()
        print(f"[ANALYSIS] Analysis complete - Best pair: {protocol_A} + {protocol_B}")

        # Save analysis to cache (always save, regardless of save_snapshots)
        tracker.save_analysis_cache(
            timestamp_seconds=current_seconds,
            liquidation_distance=liquidation_distance,
            all_results=all_results
        )
        print(f"[CACHE SAVE] Saved {len(all_results)} strategies to database")

        # Slack: notify once per run (if enabled)
        if send_slack_notifications:
            if all_results is None or all_results.empty:
                notifier.alert_error("No valid strategies found in this refresh run.")
            else:
                notifier.alert_top_strategies(
                    all_results=all_results,
                    liquidation_distance=liquidation_distance,
                    deployment_usd=100.0,
                    timestamp=current_seconds
                )

    except Exception as e:
        error_msg = f"Error during analysis: {str(e)}"
        print(f"[ERROR] {error_msg}")
        if send_slack_notifications:
            notifier.alert_error(error_msg)
    return RefreshResult(
        timestamp=current_seconds,  # Return Unix timestamp in seconds
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        available_borrow=available_borrow,
        borrow_fees=borrow_fees,
        borrow_weights=borrow_weights,
        liquidation_thresholds=liquidation_thresholds,
        protocol_A=protocol_A,
        protocol_B=protocol_B,
        all_results=all_results,
        token_summary=token_summary,
    )