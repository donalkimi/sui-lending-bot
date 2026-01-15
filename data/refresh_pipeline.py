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
    available_borrow: pd.DataFrame
    borrow_fees: pd.DataFrame

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
    create_position_snapshots: bool = False,
) -> RefreshResult:
    """Run one full refresh: fetch -> merge -> (optional) save -> analyze.

    Returns a RefreshResult containing both the merged market data and the analysis outputs.
    """
    ts = timestamp or datetime.now()


    notifier = SlackNotifier()
    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees = merge_protocol_data(
        stablecoin_contracts=stablecoin_contracts
    )

    # Persist snapshot early, so even if analysis fails you still capture the raw state.
    token_summary = {"seen": 0, "inserted": 0, "updated": 0, "total": 0}  # Default if not saving
    
    if save_snapshots:
        tracker = RateTracker(
            use_cloud=getattr(settings, "USE_CLOUD_DB", False),
            db_path=getattr(settings, "SQLITE_PATH", "data/lending_rates.db"),
            connection_url=getattr(settings, "SUPABASE_URL", None),
        )
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
        )
        
        # Update token registry - just use lend_rates with simple rename
        tokens_df = lend_rates[['Token', 'Contract']].copy()
        tokens_df.rename(columns={'Token': 'symbol', 'Contract': 'token_contract'}, inplace=True)
        
        token_summary = tracker.upsert_token_registry(
            tokens_df=tokens_df,
            timestamp=ts,
        )

    # Position snapshot automation (Step 5 enhancement)
    if create_position_snapshots:
        try:
            from analysis.position_service import PositionService

            # Use same connection as RateTracker (if snapshots were saved)
            if save_snapshots:
                position_service = PositionService(tracker.conn)
                active_positions = position_service.get_active_positions()

                if not active_positions.empty:
                    print(f"Creating snapshots for {len(active_positions)} active positions...")

                    for _, position in active_positions.iterrows():
                        try:
                            snapshot_id = position_service.create_snapshot(
                                position['position_id'],
                                snapshot_timestamp=ts  # Use same timestamp as rates_snapshot
                            )
                            print(f"  ✓ Created snapshot {snapshot_id[:8]} for position {position['position_id'][:8]}")
                        except Exception as e:
                            print(f"  ✗ Failed to create snapshot for {position['position_id'][:8]}: {e}")
                            # Continue to next position - don't block pipeline

        except Exception as e:
            print(f"⚠️  Position snapshot automation failed: {e}")
            # Don't raise - snapshot failures shouldn't break the pipeline

    # Initialize strategy results (always, regardless of save_snapshots)
    protocol_A: Optional[str] = None
    protocol_B: Optional[str] = None
    all_results: pd.DataFrame = pd.DataFrame()

    # Run analysis (always, regardless of save_snapshots)
    try:
        analyzer = RateAnalyzer(
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
            available_borrow=available_borrow,
            borrow_fees=borrow_fees,
            liquidation_distance=liquidation_distance,
        )

        protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

        # Slack: always notify once per run
        if all_results is None or all_results.empty:
            notifier.alert_error("No valid strategies found in this refresh run.")
        else:
            notifier.alert_top_strategies(
                all_results=all_results,
                liquidation_distance=liquidation_distance,
                deployment_usd=100.0,
                timestamp=ts
            )

    except Exception as e:
        error_msg = f"Error during analysis: {str(e)}"
        print(f"✗ {error_msg}")
        notifier.alert_error(error_msg)
    return RefreshResult(
        timestamp=ts,
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        available_borrow=available_borrow,
        borrow_fees=borrow_fees,
        protocol_A=protocol_A,
        protocol_B=protocol_B,
        all_results=all_results,
        token_summary=token_summary,
    )