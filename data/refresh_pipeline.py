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
from analysis.strategy_calculators import get_all_strategy_types
from data.rate_tracker import RateTracker
from alerts.slack_notifier import SlackNotifier
from utils.time_helpers import to_seconds, to_datetime_str
from analysis.position_statistics_calculator import calculate_position_statistics


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

    # Create tracker instance early (needed for perp check)
    tracker = RateTracker(
        use_cloud=getattr(settings, "USE_CLOUD_DB", False),
        db_path=getattr(settings, "SQLITE_PATH", "data/lending_rates.db"),
        connection_url=getattr(settings, "SUPABASE_URL", None),
    )

    # STEP 1: Ensure perp funding rates exist for this hour
    from data.bluefin.bluefin_reader import BluefinReader

    # Round timestamp to nearest hour (for perp data matching)
    rates_ts_hour = ts.replace(minute=0, second=0, microsecond=0)
    rates_ts_hour_str = to_datetime_str(int(rates_ts_hour.timestamp()))

    print(f"[PERP CHECK] Checking perp data for hour: {rates_ts_hour_str}")

    # Check if perp data exists for this hour
    conn = tracker._get_connection()
    cursor = conn.cursor()

    if tracker.use_cloud:
        cursor.execute(
            "SELECT COUNT(*) FROM perp_margin_rates WHERE timestamp = %s",
            (rates_ts_hour_str,)
        )
    else:
        cursor.execute(
            "SELECT COUNT(*) FROM perp_margin_rates WHERE timestamp = ?",
            (rates_ts_hour_str,)
        )

    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        print(f"[PERP CHECK] No perp data found for {rates_ts_hour_str}")
        print("[PERP FETCH] Fetching from Bluefin...")

        # Fetch from Bluefin API
        bluefin_reader = BluefinReader()
        perp_rates_df = bluefin_reader.get_recent_funding_rates(limit=1)  # Just need latest

        if not perp_rates_df.empty:
            # Save to perp_margin_rates
            rows_saved = tracker.save_perp_rates(perp_rates_df)
            print(f"[PERP FETCH] Saved {rows_saved} perp rates")

            # Register proxy tokens
            tracker.register_perp_tokens(perp_rates_df)
        else:
            print("[PERP FETCH] WARNING: No perp rates fetched from Bluefin")
    else:
        print(f"[PERP CHECK] ✓ Perp data exists ({count} markets)")

    notifier = SlackNotifier()
    print("[FETCH] Starting protocol data fetch...")
    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds = merge_protocol_data(
        stablecoin_contracts=stablecoin_contracts
    )
    print("[FETCH] Protocol data fetch complete")

    # Persist snapshot early, so even if analysis fails you still capture the raw state.
    token_summary = {"seen": 0, "inserted": 0, "updated": 0, "total": 0}  # Default if not saving

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

        # Auto-populate oracle IDs for new tokens
        if token_summary and token_summary.get('inserted', 0) > 0:
            new_count = token_summary['inserted']
            print(f"[ORACLE] {new_count} new token(s) detected")
            print("[ORACLE] Auto-populating oracle IDs...")

            try:
                from utils.populate_coingecko_ids import populate_coingecko_ids_auto
                from utils.populate_pyth_ids import populate_pyth_ids_auto

                cg_matches = populate_coingecko_ids_auto(engine=tracker.engine, dry_run=False, force=False)
                pyth_matches = populate_pyth_ids_auto(engine=tracker.engine, dry_run=False, force=False)

                print(f"[ORACLE] CoinGecko: {cg_matches} newly matched")
                print(f"[ORACLE] Pyth: {pyth_matches} newly matched")
                print("[ORACLE] Oracle ID population complete")
            except Exception as e:
                print(f"[ORACLE] Auto-population failed: {e}")
                print("[ORACLE] Continuing with refresh - oracle IDs can be populated manually")
                # Continue with refresh - not a critical failure

        # STEP 2: Insert perp market rows into rates_snapshot
        print("[PERP SNAPSHOT] Inserting perp market rows...")

        from psycopg2.extras import execute_values

        # Fetch all perp rates in one query (EXACT match on timestamp)
        token_contracts = [f"0x{base_token}-USDC-PERP_bluefin" for base_token in settings.BLUEFIN_PERP_MARKETS]

        conn_perp = tracker._get_connection()
        cursor_perp = conn_perp.cursor()

        if tracker.use_cloud:
            # PostgreSQL - use %s placeholders
            placeholders = ','.join(['%s'] * len(token_contracts))
            cursor_perp.execute(
                f"""
                SELECT token_contract, funding_rate_annual
                FROM perp_margin_rates
                WHERE token_contract IN ({placeholders})
                  AND timestamp = %s
                """,
                token_contracts + [rates_ts_hour_str]
            )
        else:
            # SQLite - use ? placeholders
            placeholders = ','.join(['?'] * len(token_contracts))
            cursor_perp.execute(
                f"""
                SELECT token_contract, funding_rate_annual
                FROM perp_margin_rates
                WHERE token_contract IN ({placeholders})
                  AND timestamp = ?
                """,
                token_contracts + [rates_ts_hour_str]
            )

        perp_rates = cursor_perp.fetchall()
        conn_perp.close()

        # Build dictionary for quick lookup
        rates_dict = {token_contract: rate for token_contract, rate in perp_rates}

        # Verify all markets have data (fail loudly if missing)
        missing_markets = []
        for token_contract in token_contracts:
            if token_contract not in rates_dict:
                missing_markets.append(token_contract)

        if missing_markets:
            raise ValueError(
                f"PERP DATA ERROR: No funding rates found for {len(missing_markets)} market(s) "
                f"at {rates_ts_hour_str}: {missing_markets}. This should never happen - perp data "
                f"should have been populated in STEP 1."
            )

        # Build rows for all 6 perp markets
        perp_rows = []
        for base_token in settings.BLUEFIN_PERP_MARKETS:
            token_contract = f"0x{base_token}-USDC-PERP_bluefin"
            funding_rate = rates_dict[token_contract]

            perp_rows.append((
                to_datetime_str(current_seconds),  # timestamp (original rates_ts)
                'Bluefin',                         # protocol
                f'{base_token}-USDC-PERP',         # token
                token_contract,                    # token_contract
                f'{base_token}-PERP',              # market
                funding_rate                       # perp_margin_rate
            ))

        # Bulk insert perp rows
        conn_insert = tracker._get_connection()
        cursor_insert = conn_insert.cursor()

        if tracker.use_cloud:
            execute_values(
                cursor_insert,
                """
                INSERT INTO rates_snapshot (
                    timestamp, protocol, token, token_contract, market, perp_margin_rate
                ) VALUES %s
                ON CONFLICT (timestamp, protocol, token_contract) DO NOTHING
                """,
                perp_rows
            )
        else:
            cursor_insert.executemany(
                """
                INSERT OR IGNORE INTO rates_snapshot (
                    timestamp, protocol, token, token_contract, market, perp_margin_rate
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                perp_rows
            )

        conn_insert.commit()
        conn_insert.close()

        print(f"[PERP SNAPSHOT] ✓ Inserted {len(perp_rows)} perp market rows")

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
            liquidation_distance=liquidation_distance,
            strategy_types=get_all_strategy_types()  # Generate all strategy types
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
                        if check['needs_rebalance_2a']:
                            print(f"[AUTO-REBALANCE]    Leg 2A: baseline={check['baseline_liq_dist_2a']:.2%} → "
                                  f"live={check['live_liq_dist_2a']:.2%} "
                                  f"(Δ={check['delta_2a']:.2%})")
                        if check['needs_rebalance_2b']:
                            print(f"[AUTO-REBALANCE]    Leg 2B: baseline={check['baseline_liq_dist_2b']:.2%} → "
                                  f"live={check['live_liq_dist_2b']:.2%} "
                                  f"(Δ={check['delta_2b']:.2%})")

                        # Execute rebalance
                        try:
                            rebalance_notes = (
                                f"Auto-rebalance triggered by threshold ({REBALANCE_THRESHOLD:.1%}). "
                                f"Leg 2A Δ: {check['delta_2a']:.2%}, "
                                f"Leg 2B Δ: {check['delta_2b']:.2%}"
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

        # Calculate and save position statistics (AFTER rebalancing so stats include new rebalances)
        print("[POSITION STATS] Calculating position statistics...")
        try:
            from analysis.position_service import PositionService
            from dashboard.dashboard_utils import get_db_connection

            # Create database connection for position service
            conn = get_db_connection()  # Respects USE_CLOUD_DB setting
            service = PositionService(conn)

            # Get all active positions at this timestamp
            active_positions = service.get_active_positions(live_timestamp=current_seconds)

            if not active_positions.empty:
                # Helper functions for rate lookups
                def get_rate(token_contract: str, protocol: str, side: str) -> float:
                    """Get rate from merged data for a specific token/protocol/side"""
                    if side == 'lend':
                        row = lend_rates[lend_rates['Contract'] == token_contract]
                        if not row.empty and protocol in row.columns:
                            rate = row.iloc[0][protocol]
                            return rate if pd.notna(rate) else 0.0
                    else:  # borrow
                        row = borrow_rates[borrow_rates['Contract'] == token_contract]
                        if not row.empty and protocol in row.columns:
                            rate = row.iloc[0][protocol]
                            return rate if pd.notna(rate) else 0.0
                    return 0.0

                def get_borrow_fee(token_contract: str, protocol: str) -> float:
                    """Get borrow fee from merged data for a specific token/protocol"""
                    row = borrow_fees[borrow_fees['Contract'] == token_contract]
                    if not row.empty and protocol in row.columns:
                        fee = row.iloc[0][protocol]
                        return fee if pd.notna(fee) else 0.0
                    return 0.0

                # Calculate statistics for each active position
                stats_saved = 0
                for _, position in active_positions.iterrows():
                    try:
                        stats = calculate_position_statistics(
                            position_id=position['position_id'],
                            timestamp=current_seconds,
                            service=service,
                            get_rate_func=get_rate,
                            get_borrow_fee_func=get_borrow_fee
                        )

                        # Save to database
                        tracker.save_position_statistics(stats)
                        stats_saved += 1

                    except Exception as e:
                        print(f"[POSITION STATS] Failed to calculate/save stats for position {position['position_id'][:8]}...: {e}")
                        # Continue to next position even if this one fails

                print(f"[POSITION STATS] Successfully calculated and saved statistics for {stats_saved}/{len(active_positions)} position(s)")
            else:
                print("[POSITION STATS] No active positions to calculate statistics for")

            # Clean up database connection
            conn.close()

        except Exception as e:
            print(f"[POSITION STATS] Error in position statistics calculation: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail entire pipeline if position statistics fails

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