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
    protocol_a: Optional[str]
    protocol_b: Optional[str]
    all_results: pd.DataFrame

    # Token registry update summary
    token_summary: dict

    # Auto-rebalancing
    rebalance_checks: list = None  # List of positions checked for rebalancing
    auto_rebalanced_count: int = 0  # Number of positions auto-rebalanced


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
    protocol_a: Optional[str] = None
    protocol_b: Optional[str] = None
    all_results: pd.DataFrame = pd.DataFrame()

    # Initialize rebalance tracking variables
    rebalance_checks = []
    auto_rebalanced_count = 0

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

        protocol_a, protocol_b, all_results = analyzer.find_best_protocol_pair()
        print(f"[ANALYSIS] Analysis complete - Best pair: {protocol_a} + {protocol_b}")

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

        # Check positions and auto-rebalance if needed
        print("[AUTO-REBALANCE] Checking positions for rebalancing needs...")

        try:
            from analysis.position_service import PositionService
            from config.settings import REBALANCE_THRESHOLD
            from dashboard.dashboard_utils import get_db_connection

            # Create database connection for position service
            conn = get_db_connection()  # Respects USE_CLOUD_DB setting
            service = PositionService(conn)
            rebalance_checks = service.check_positions_need_rebalancing(
                live_timestamp=current_seconds,
                rebalance_threshold=REBALANCE_THRESHOLD
            )

            # Auto-rebalance positions that exceed threshold
            if rebalance_checks:
                positions_needing_rebalance = [
                    r for r in rebalance_checks if r['needs_rebalance']
                ]

                if positions_needing_rebalance:
                    print(f"[AUTO-REBALANCE] ⚠️  {len(positions_needing_rebalance)} position(s) need rebalancing")

                    for check in positions_needing_rebalance:
                        position_id = check['position_id']
                        print(f"\n[AUTO-REBALANCE] 🔄 Auto-rebalancing position {position_id[:8]}... "
                              f"({check['token2']} in {check['protocol_a']}/{check['protocol_b']})")

                        # Log liquidation distance changes
                        if check['needs_rebalance_2A']:
                            print(f"[AUTO-REBALANCE]    Leg 2A: baseline={check['baseline_liq_dist_2A']:.2%} → "
                                  f"live={check['live_liq_dist_2A']:.2%} "
                                  f"(Δ={check['delta_2A']:.2%})")
                        if check['needs_rebalance_2B']:
                            print(f"[AUTO-REBALANCE]    Leg 2B: baseline={check['baseline_liq_dist_2B']:.2%} → "
                                  f"live={check['live_liq_dist_2B']:.2%} "
                                  f"(Δ={check['delta_2B']:.2%})")

                        # Execute rebalance
                        try:
                            rebalance_notes = (
                                f"Auto-rebalance triggered by threshold ({REBALANCE_THRESHOLD:.1%}). "
                                f"Leg 2A Δ: {check['delta_2A']:.2%}, "
                                f"Leg 2B Δ: {check['delta_2B']:.2%}"
                            )

                            rebalance_id = service.rebalance_position(
                                position_id=position_id,
                                live_timestamp=current_seconds,
                                rebalance_reason="auto_rebalance_threshold_exceeded",
                                rebalance_notes=rebalance_notes
                            )

                            print(f"[AUTO-REBALANCE]    ✅ Rebalance successful (ID: {rebalance_id[:8]}...)")
                            auto_rebalanced_count += 1

                        except Exception as rebalance_error:
                            print(f"[AUTO-REBALANCE]    ❌ Rebalance failed: {rebalance_error}")
                            # Continue to next position even if this one fails

                    if auto_rebalanced_count > 0:
                        print(f"\n[AUTO-REBALANCE] ✅ Auto-rebalanced {auto_rebalanced_count}/{len(positions_needing_rebalance)} position(s)")
                else:
                    print("[AUTO-REBALANCE] ✓ All positions within threshold")
            else:
                print("[AUTO-REBALANCE] ✓ No active positions to check")

        except Exception as rebalance_system_error:
            print(f"[AUTO-REBALANCE] Error in auto-rebalance system: {rebalance_system_error}")
            import traceback
            traceback.print_exc()
            # Don't fail entire pipeline if rebalance check fails
        finally:
            # Clean up database connection
            if 'conn' in locals():
                conn.close()

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
        protocol_a=protocol_a,
        protocol_b=protocol_b,
        all_results=all_results,
        token_summary=token_summary,
        rebalance_checks=rebalance_checks,
        auto_rebalanced_count=auto_rebalanced_count,
    )