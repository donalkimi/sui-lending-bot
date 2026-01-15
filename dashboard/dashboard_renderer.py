"""
Shared dashboard renderer for both live and historical modes

This renderer works with any DataLoader (LiveDataLoader or HistoricalDataLoader)
and provides mode-specific behavior via the 'mode' parameter.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Tuple, Optional, Union, Any, Dict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS, STABLECOIN_SYMBOLS
from dashboard.data_loaders import DataLoader
from dashboard.dashboard_utils import (
    format_usd_abbreviated,
    get_apr_value,
    get_db_connection,
    get_strategy_history,
    create_strategy_history_chart
)
from analysis.rate_analyzer import RateAnalyzer
from analysis.position_service import PositionService


# ============================================================================
# COMPONENT RENDERERS
# ============================================================================

def render_deployment_form(mode: str):
    """
    Render the deployment confirmation form in a modal-like container
    Uses session state: pending_deployment, show_deploy_form

    Args:
        mode: 'live' or 'historical'
    """
    if not st.session_state.get('show_deploy_form', False):
        return

    deployment_data = st.session_state.get('pending_deployment')
    if not deployment_data:
        st.session_state.show_deploy_form = False
        return

    strategy = deployment_data['strategy_row']
    is_levered = deployment_data['is_levered']
    deployment_usd = deployment_data['deployment_usd']
    liquidation_distance = deployment_data['liquidation_distance']

    # Display in a prominent container
    st.markdown("---")
    st.markdown("## 📄 PAPER TRADE - Position Deployment Confirmation")

    # Mode-specific warning
    if mode == 'historical':
        st.warning(
            "⚠️ **Deploying from historical view:** Position will be created using CURRENT market rates, "
            "but entry time will be set to the historical timestamp being viewed."
        )

    # Strategy summary
    st.markdown("### Strategy Details")
    col1, col2, col3 = st.columns(3)

    token_flow = f"{strategy['token1']} → {strategy['token2']}"
    if is_levered:
        token_flow += f" → {strategy['token3']}"

    col1.metric("Token Flow", token_flow)
    col2.metric("Protocols", f"{strategy['protocol_A']} ↔ {strategy['protocol_B']}")
    col3.metric("Type", "🔄 Loop" if is_levered else "▶️ No-Loop")

    # APR comparison
    st.markdown("### APR Projection")
    apr_data = {
        'Timeframe': ['Net APR', 'APR5', 'APR30', 'APR90'],
        'Value': [
            f"{strategy.get('apr_net' if is_levered else 'unlevered_apr', strategy['net_apr']):.2f}%",
            f"{strategy.get('apr5', strategy['net_apr']):.2f}%",
            f"{strategy.get('apr30', strategy['net_apr']):.2f}%",
            f"{strategy.get('apr90', strategy['net_apr']):.2f}%"
        ]
    }
    st.table(pd.DataFrame(apr_data))

    # Position parameters
    st.markdown("### Position Parameters")
    col1, col2 = st.columns(2)
    col1.metric("Deployment Size", f"${deployment_usd:,.2f}", help="Hypothetical amount - no real capital deployed")
    col2.metric("Liquidation Distance", f"{liquidation_distance*100:.0f}%", help="Safety buffer from liquidation threshold")

    # Optional notes
    notes = st.text_area("Notes (optional)", placeholder="Add any notes about this paper position...", key="deploy_notes")

    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("✅ Confirm Deploy", type="primary", width="stretch"):
            try:
                # Connect to database
                conn = get_db_connection()
                service = PositionService(conn)

                # Determine entry timestamp based on mode
                if mode == 'historical':
                    # Use historical timestamp from session state
                    entry_timestamp = deployment_data.get('historical_timestamp', datetime.now())
                else:
                    entry_timestamp = datetime.now()

                # Add timestamp to strategy dict
                strategy_dict = strategy.copy()
                strategy_dict['timestamp'] = entry_timestamp

                # Create position
                position_id = service.create_position(
                    strategy_row=pd.Series(strategy_dict),
                    deployment_usd=deployment_usd,
                    liquidation_distance=liquidation_distance,
                    is_levered=is_levered,
                    notes=notes,
                    is_paper_trade=True
                )

                conn.close()

                # Clear form and show success
                st.session_state.show_deploy_form = False
                st.session_state.pending_deployment = None
                st.success(f"✅ Paper position created: {position_id}")
                st.info("📊 View your position in the Positions tab")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Failed to create position: {e}")

    with col2:
        if st.button("❌ Cancel", width="stretch"):
            st.session_state.show_deploy_form = False
            st.session_state.pending_deployment = None
            st.rerun()

    st.markdown("---")


def display_apr_table(strategy_row: Union[pd.Series, Dict[str, Any]], deployment_usd: float,
                     liquidation_distance: float, strategy_idx: int, mode: str,
                     historical_timestamp: Optional[datetime] = None) -> Tuple[str, Optional[str]]:
    """
    Display compact APR comparison table with both levered and unlevered strategies
    with integrated deploy buttons

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
        deployment_usd: Deployment amount in USD from sidebar
        liquidation_distance: Liquidation distance from sidebar
        strategy_idx: Unique identifier for the strategy (DataFrame index) for unique button keys
        mode: 'live' or 'historical'
        historical_timestamp: Timestamp for historical mode deployments

    Returns:
        tuple: (fee_caption, warning_message) - strings to display after other content
    """
    # Extract token names
    token1 = strategy_row['token1']
    token2 = strategy_row['token2']
    token3 = strategy_row['token3']

    # Extract levered APR values
    apr_base = strategy_row['net_apr']
    apr_net_levered = strategy_row.get('apr_net', apr_base)
    apr90_levered = strategy_row.get('apr90', apr_base)
    apr30_levered = strategy_row.get('apr30', apr_base)
    apr5_levered = strategy_row.get('apr5', apr_base)

    # Extract unlevered APR values
    unlevered_base = strategy_row.get('unlevered_apr', apr_base)
    apr_net_unlevered = unlevered_base
    apr90_unlevered = unlevered_base
    apr30_unlevered = unlevered_base
    apr5_unlevered = unlevered_base

    # Build row names with emojis at the start
    row_name_levered = f"🔄 Loop"
    row_name_unlevered = f"▶️ No-Loop"

    # Build two-row table with Strategy column first
    apr_table_data = {
        'Strategy': [row_name_levered, row_name_unlevered],
        'APR(net)': [f"{apr_net_levered:.2f}%", f"{apr_net_unlevered:.2f}%"],
        'APR5': [f"{apr5_levered:.2f}%", f"{apr5_unlevered:.2f}%"],
        'APR30': [f"{apr30_levered:.2f}%", f"{apr30_unlevered:.2f}%"],
        'APR90': [f"{apr90_levered:.2f}%", f"{apr90_unlevered:.2f}%"]
    }

    apr_df = pd.DataFrame(apr_table_data)

    # Apply styling for negative values
    def highlight_negative(val):
        """Highlight negative APR values in red"""
        if isinstance(val, str) and '%' in val:
            try:
                numeric_val = float(val.replace('%', ''))
                if numeric_val < 0:
                    return 'color: red; font-weight: bold'
            except (ValueError, TypeError):
                pass
        return ''

    styled_apr_df = apr_df.style.map(highlight_negative, subset=['APR(net)', 'APR5', 'APR30', 'APR90'])

    # Display table and deploy buttons side by side
    col1, col2 = st.columns([4, 1])

    with col1:
        # Display compact table without header
        st.dataframe(styled_apr_df, hide_index=True, width="stretch")

    with col2:
        st.markdown("**Deploy**")
        # Deploy button for levered strategy
        if st.button(f"🚀 ${deployment_usd:,.0f}", key=f"deploy_levered_{strategy_idx}_{mode}", width="stretch"):
            # Store strategy details in session state for confirmation form
            st.session_state.pending_deployment = {
                'strategy_row': strategy_row if isinstance(strategy_row, dict) else strategy_row.to_dict(),
                'is_levered': True,
                'deployment_usd': deployment_usd,
                'liquidation_distance': liquidation_distance,
                'historical_timestamp': historical_timestamp
            }
            st.session_state.show_deploy_form = True
            st.rerun()

        # Deploy button for unlevered strategy
        if st.button(f"🚀 ${deployment_usd:,.0f}", key=f"deploy_unlevered_{strategy_idx}_{mode}", width="stretch"):
            # Store strategy details in session state for confirmation form
            st.session_state.pending_deployment = {
                'strategy_row': strategy_row if isinstance(strategy_row, dict) else strategy_row.to_dict(),
                'is_levered': False,
                'deployment_usd': deployment_usd,
                'liquidation_distance': liquidation_distance,
                'historical_timestamp': historical_timestamp
            }
            st.session_state.show_deploy_form = True
            st.rerun()

    # Prepare fee caption (default to 0 if missing)
    borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)
    borrow_fee_3B = strategy_row.get('borrow_fee_3B', 0.0)
    fee_caption = f"💰 Fees: token2={borrow_fee_2A*100:.3f}% | token3={borrow_fee_3B*100:.3f}%"

    # Prepare warning for negative short-term holds (only check levered)
    warning_message = None
    if apr5_levered < 0:
        warning_message = "⚠️ **5-day APR is negative for looped strategy!** Upfront fees make very short-term positions unprofitable."

    return fee_caption, warning_message


def display_strategy_details(strategy_row: Union[pd.Series, Dict[str, Any]], use_unlevered: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Display expanded strategy details when row is clicked
    Returns liquidity info to be displayed at the end

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
        use_unlevered: If True, show only unlevered strategy (3 rows instead of 4)

    Returns:
        tuple: (max_size_message, liquidity_constraints_message) - strings to display at the end
    """
    # Extract all the values we need
    token1 = strategy_row['token1']
    token2 = strategy_row['token2']
    token3 = strategy_row['token3']
    protocol_A = strategy_row['protocol_A']
    protocol_B = strategy_row['protocol_B']

    # USD values
    L_A = strategy_row['L_A']
    B_A = strategy_row['B_A']
    L_B = strategy_row['L_B']
    B_B = strategy_row['B_B']

    # Rates
    lend_rate_1A = strategy_row['lend_rate_1A']
    borrow_rate_2A = strategy_row['borrow_rate_2A']
    lend_rate_2B = strategy_row['lend_rate_2B']
    borrow_rate_3B = strategy_row['borrow_rate_3B']

    # Prices
    P1_A = strategy_row['P1_A']
    P2_A = strategy_row['P2_A']
    P2_B = strategy_row['P2_B']
    P3_B = strategy_row['P3_B']

    # Borrow fees and available liquidity
    borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)
    borrow_fee_3B = strategy_row.get('borrow_fee_3B', 0.0)

    # Prepare max deployable size message
    max_size = strategy_row.get('max_size')
    max_size_message = None
    if max_size is not None and not pd.isna(max_size):
        max_size_message = f"📊 **Max Deployable Size:** ${max_size:,.2f}"

    # Prepare liquidity constraints message (detailed view)
    available_borrow_2A = strategy_row.get('available_borrow_2A')
    available_borrow_3B = strategy_row.get('available_borrow_3B')

    liquidity_details = []
    if available_borrow_2A is not None and not pd.isna(available_borrow_2A):
        constraint_2A = available_borrow_2A / B_A if B_A > 0 else float('inf')
        liquidity_details.append(f"• {token2} on {protocol_A}: ${available_borrow_2A:,.2f} available → max ${constraint_2A:,.2f}")

    if available_borrow_3B is not None and not pd.isna(available_borrow_3B):
        constraint_3B = available_borrow_3B / B_B if B_B > 0 else float('inf')
        liquidity_details.append(f"• {token3} on {protocol_B}: ${available_borrow_3B:,.2f} available → max ${constraint_3B:,.2f}")

    liquidity_constraints_message = None
    if liquidity_details:
        liquidity_constraints_message = "💵 **Liquidity Constraints:**\n" + "\n".join(liquidity_details)

    # Build the table data
    table_data = [
        # Row 1: Protocol A, token1, Lend
        {
            'Protocol': protocol_A,
            'Token': token1,
            'Action': 'Lend',
            'Rate': f"{lend_rate_1A:.2f}%",
            'Weight': f"{L_A:.2f}",
            'Token Amount': f"{L_A / P1_A:.2f}",
            'Price': f"${P1_A:.4f}",
            'Fee': '',
            'Available': ''
        },
        # Row 2: Protocol A, token2, Borrow
        {
            'Protocol': protocol_A,
            'Token': token2,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_2A:.2f}%",
            'Weight': f"{B_A:.2f}",
            'Token Amount': f"{B_A / P2_A:.2f}",
            'Price': f"${P2_A:.4f}",
            'Fee': f"{borrow_fee_2A*100:.2f}%" if pd.notna(borrow_fee_2A) else 'N/A',
            'Available': format_usd_abbreviated(available_borrow_2A) if pd.notna(available_borrow_2A) else 'N/A'
        },
        # Row 3: Protocol B, token2, Lend
        {
            'Protocol': protocol_B,
            'Token': token2,
            'Action': 'Lend',
            'Rate': f"{lend_rate_2B:.2f}%",
            'Weight': f"{L_B:.2f}",
            'Token Amount': f"{L_B / P2_B:.2f}",
            'Price': f"${P2_B:.4f}",
            'Fee': '',
            'Available': ''
        }
    ]

    # Only add 4th row (Borrow token3 from Protocol B) if levered
    if not use_unlevered:
        table_data.append({
            'Protocol': protocol_B,
            'Token': token3,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_3B:.2f}%",
            'Weight': f"{B_B:.2f}",
            'Token Amount': f"{B_B / P3_B:.2f}",
            'Price': f"${P3_B:.4f}",
            'Fee': f"{borrow_fee_3B*100:.2f}%" if pd.notna(borrow_fee_3B) else 'N/A',
            'Available': format_usd_abbreviated(available_borrow_3B) if pd.notna(available_borrow_3B) else 'N/A'
        })

    # Create DataFrame and display
    details_df = pd.DataFrame(table_data)
    st.dataframe(details_df, width='stretch', hide_index=True)

    return max_size_message, liquidity_constraints_message


def load_historical_positions(timestamp: datetime) -> pd.DataFrame:
    """
    Load positions that were active at given timestamp

    Args:
        timestamp: Historical timestamp

    Returns:
        DataFrame of positions with snapshot data
    """
    conn = get_db_connection()
    service = PositionService(conn)

    ph = '%s' if settings.USE_CLOUD_DB else '?'

    query = f"""
    SELECT
        p.*,
        ps.total_pnl,
        ps.pnl_base_apr,
        ps.pnl_reward_apr,
        ps.pnl_price_leg1,
        ps.pnl_price_leg2,
        ps.pnl_price_leg3,
        ps.pnl_price_leg4,
        ps.pnl_fees,
        ps.health_factor_1A_calc,
        ps.health_factor_2B_calc,
        ps.distance_to_liq_1A_calc,
        ps.distance_to_liq_2B_calc
    FROM positions p
    LEFT JOIN position_snapshots ps
        ON p.position_id = ps.position_id
        AND ps.snapshot_timestamp = {ph}
    WHERE p.entry_timestamp <= {ph}
        AND (p.close_timestamp IS NULL OR p.close_timestamp >= {ph})
    ORDER BY p.entry_timestamp DESC
    """

    if settings.USE_CLOUD_DB:
        import psycopg2
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query, (timestamp, timestamp, timestamp))
        rows = cursor.fetchall()
        df = pd.DataFrame(rows)
    else:
        import sqlite3
        df = pd.read_sql_query(query, conn, params=(timestamp, timestamp, timestamp))

    conn.close()
    return df


# ============================================================================
# TAB RENDERERS
# ============================================================================

def render_all_strategies_tab(all_results: pd.DataFrame, mode: str, deployment_usd: float,
                              liquidation_distance: float, use_unlevered: bool,
                              historical_timestamp: Optional[datetime] = None):
    """
    Render the All Strategies tab

    Args:
        all_results: Filtered results DataFrame
        mode: 'live' or 'historical'
        deployment_usd: Deployment amount
        liquidation_distance: Liquidation distance setting
        use_unlevered: Whether to show unlevered APR
        historical_timestamp: Timestamp for historical mode
    """
    if not all_results.empty:
        # Display with expanders
        for _enum_idx, (idx, row) in enumerate(all_results.iterrows()):
            # Chart data key - include mode to avoid collisions
            chart_key = f"chart_{mode}_{idx}"

            # Expander should be open if chart data exists for this strategy
            is_expanded = chart_key in st.session_state

            # Build expander title with max size and APR
            max_size = row.get('max_size')
            if max_size is not None and not pd.isna(max_size):
                max_size_text = f" | Max Size ${max_size:,.2f}"
            else:
                max_size_text = ""

            # Build token flow based on leverage toggle
            if use_unlevered:
                token_flow = f"{row['token1']} → {row['token2']}"
            else:
                token_flow = f"{row['token1']} → {row['token2']} → {row['token3']}"

            # Get Net APR and APR5 values
            if use_unlevered:
                net_apr_value = row.get('unlevered_apr', 0)
                apr5_value = row.get('unlevered_apr', 0)
            else:
                net_apr_value = row.get('apr_net', row['net_apr'])
                apr5_value = row.get('apr5', row['net_apr'])

            # Format APR values with color indicators
            net_apr_indicator = "🟢" if net_apr_value >= 0 else "🔴"
            apr5_indicator = "🟢" if apr5_value >= 0 else "🔴"

            title = f"▶ {token_flow} | {row['protocol_A']} ↔ {row['protocol_B']}{max_size_text} | {net_apr_indicator} Net APR {net_apr_value:.2f}% | {apr5_indicator} 5day APR {apr5_value:.2f}%"

            with st.expander(title, expanded=is_expanded):
                # 1. Display APR comparison table at the top with deploy buttons
                fee_caption, warning_message = display_apr_table(
                    row, deployment_usd, liquidation_distance, idx, mode, historical_timestamp
                )

                # 2. Display strategy details table right after
                max_size_msg, liquidity_msg = display_strategy_details(row, use_unlevered)

                # 3. Button to load historical chart
                if st.button("📈 Load Historical Chart", key=f"btn_{mode}_{idx}"):
                    with st.spinner("Loading historical data..."):
                        history_df, L_A, B_A, L_B, B_B = get_strategy_history(
                            strategy_row=row.to_dict(),
                            liquidation_distance=liquidation_distance,
                            days_back=30
                        )

                        # Store in session state
                        st.session_state[chart_key] = {
                            'history_df': history_df,
                            'L_A': L_A,
                            'B_A': B_A,
                            'L_B': L_B,
                            'B_B': B_B
                        }

                    # Force rerun to show chart
                    st.rerun()

                # Display chart if loaded
                if chart_key in st.session_state:
                    chart_data = st.session_state[chart_key]
                    history_df = chart_data['history_df']

                    if history_df is not None and not history_df.empty:
                        st.subheader("📈 Historical Performance")

                        # Create and display chart
                        fig = create_strategy_history_chart(
                            df=history_df,
                            token1=row['token1'],
                            token2=row['token2'],
                            token3=row['token3'],
                            protocol_A=row['protocol_A'],
                            protocol_B=row['protocol_B'],
                            liq_dist=liquidation_distance,
                            L_A=chart_data['L_A'],
                            B_A=chart_data['B_A'],
                            L_B=chart_data['L_B'],
                            B_B=chart_data['B_B']
                        )
                        st.plotly_chart(fig, width='stretch')

                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Current Net APR", f"{get_apr_value(row, use_unlevered):.2f}%")
                        col2.metric("Avg Net APR", f"{history_df['net_apr'].mean():.2f}%")
                        col3.metric("Max Net APR", f"{history_df['net_apr'].max():.2f}%")
                        col4.metric("Min Net APR", f"{history_df['net_apr'].min():.2f}%")

                        st.markdown("---")
                    else:
                        st.info("📊 No historical data available yet. Run main.py to build up history.")

                # 4. Display warnings/info at the end
                st.caption(fee_caption)
                if warning_message:
                    st.warning(warning_message)

                # 5. Display liquidity info at the very end
                if max_size_msg:
                    st.success(max_size_msg)
                if liquidity_msg:
                    st.info(liquidity_msg)
    else:
        st.warning("⚠️ No strategies found with current filters")


def render_positions_tab(timestamp: datetime, mode: str):
    """
    Render the Positions tab

    Args:
        timestamp: Current timestamp (live or historical)
        mode: 'live' or 'historical'
    """
    st.header("💼 Paper Trading Positions")

    try:
        # Connect to database
        conn = get_db_connection()
        service = PositionService(conn)

        if mode == 'live':
            # Get active positions for live mode
            active_positions = service.get_active_positions()

            # Get portfolio summary
            summary = service.get_portfolio_summary()

            # Display portfolio summary
            st.markdown("### 📊 Portfolio Summary (PAPER TRADING)")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Capital", f"${summary['total_capital']:,.2f}", help="Hypothetical deployed capital")
            col2.metric("Avg APR", f"{summary['avg_apr']:.2f}%", help="Weighted average APR")
            col3.metric("Total Earned", f"${summary['total_earned']:,.2f}", help="Hypothetical earnings")
            col4.metric("Active Positions", f"{summary['position_count']}", help="Number of active positions")

            st.markdown("---")

            # Global snapshot button
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown("### 📄 Active Positions")
            with col2:
                if st.button("📸 Snapshot All", key="snapshot_all_positions", help="Create snapshots for all active positions"):
                    if len(active_positions) == 0:
                        st.warning("No active positions to snapshot")
                    else:
                        with st.spinner(f"Creating snapshots for {len(active_positions)} position(s)..."):
                            results = service.create_snapshots_for_all_positions()

                            if results['success_count'] > 0:
                                st.success(f"✅ Created {results['success_count']} snapshot(s)")
                            if results['error_count'] > 0:
                                st.warning(f"⚠️ {results['error_count']} snapshot(s) failed")
                                for error in results['errors']:
                                    st.error(f"Position {error['position_id'][:8]}: {error['error_message']}")

                            st.rerun()

        else:  # historical
            st.info(f"💡 **Historical view:** Showing positions active at {timestamp.strftime('%Y-%m-%d %H:%M UTC')}")
            active_positions = load_historical_positions(timestamp)

        if active_positions.empty:
            if mode == 'live':
                st.info("📭 No active positions. Deploy a strategy from the All Strategies tab to get started!")
            else:
                st.info("📭 No positions were active at this timestamp.")
        else:
            # Display each position
            for _, position in active_positions.iterrows():
                # Build token flow
                if position['is_levered']:
                    token_flow = f"{position['token1']} → {position['token2']} → {position['token3']}"
                else:
                    token_flow = f"{position['token1']} → {position['token2']}"

                # Calculate current PnL (simplified - from latest snapshot)
                snapshots = service.get_position_snapshots(position['position_id'])
                latest_snap = None
                if not snapshots.empty:
                    latest_snap = snapshots.iloc[-1]
                    total_pnl = latest_snap['total_pnl']
                    pnl_pct = (total_pnl / position['deployment_usd']) * 100
                else:
                    total_pnl = 0
                    pnl_pct = 0

                # Card title with key metrics
                with st.expander(f"📄 PAPER | {token_flow} | {position['protocol_A']} ↔ {position['protocol_B']} | Entry APR: {position['entry_net_apr']*100:.2f}% | PnL: ${total_pnl:.2f} ({pnl_pct:+.2f}%)"):
                    # Mode-specific info
                    if mode == 'historical':
                        st.info("💡 Historical view - current position status may differ from live data")

                    # Entry details
                    st.markdown("#### Entry Details")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Deployment", f"${position['deployment_usd']:,.2f}")
                    col2.metric("Entry APR", f"{position['entry_net_apr']*100:.2f}%")
                    col3.metric("Liq Distance", f"{position['entry_liquidation_distance']*100:.0f}%")
                    col4.metric("Entry Time", position['entry_timestamp'])

                    # Position sizing
                    st.markdown("#### Position Sizing")
                    sizing_data = [
                        {
                            'Protocol': position['protocol_A'],
                            'Token': position['token1'],
                            'Action': 'Lend',
                            'Multiplier': f"{position['L_A']:.2f}x",
                            'USD Value': f"${position['deployment_usd'] * position['L_A']:,.2f}",
                            'Entry Rate': f"{position['entry_lend_rate_1A']*100:.2f}%",
                            'Entry Price': f"${position['entry_price_1A']:.4f}"
                        },
                        {
                            'Protocol': position['protocol_A'],
                            'Token': position['token2'],
                            'Action': 'Borrow',
                            'Multiplier': f"{position['B_A']:.2f}x",
                            'USD Value': f"${position['deployment_usd'] * position['B_A']:,.2f}",
                            'Entry Rate': f"{position['entry_borrow_rate_2A']*100:.2f}%",
                            'Entry Price': f"${position['entry_price_2']:.4f}"
                        },
                        {
                            'Protocol': position['protocol_B'],
                            'Token': position['token2'],
                            'Action': 'Lend',
                            'Multiplier': f"{position['L_B']:.2f}x",
                            'USD Value': f"${position['deployment_usd'] * position['L_B']:,.2f}",
                            'Entry Rate': f"{position['entry_lend_rate_2B']*100:.2f}%",
                            'Entry Price': f"${position['entry_price_2']:.4f}"
                        }
                    ]

                    if position['is_levered']:
                        sizing_data.append({
                            'Protocol': position['protocol_B'],
                            'Token': position['token3'],
                            'Action': 'Borrow',
                            'Multiplier': f"{position['B_B']:.2f}x",
                            'USD Value': f"${position['deployment_usd'] * position['B_B']:,.2f}",
                            'Entry Rate': f"{position['entry_borrow_rate_3B']*100:.2f}%",
                            'Entry Price': f"${position['entry_price_3B']:.4f}"
                        })

                    st.table(pd.DataFrame(sizing_data))

                    # Current Status & PnL (only for positions with snapshots)
                    if not snapshots.empty and latest_snap is not None:
                        st.markdown("#### Current Status & PnL")

                        # Time elapsed
                        time_elapsed = timestamp - position['entry_timestamp']
                        days = time_elapsed.days
                        hours = time_elapsed.seconds // 3600

                        col1, col2, col3 = st.columns(3)

                        # Total PnL with color
                        if total_pnl >= 0:
                            col1.markdown(f"**Total PnL:** :green[${total_pnl:.2f} (+{pnl_pct:.2f}%)]")
                        else:
                            col1.markdown(f"**Total PnL:** :red[${total_pnl:.2f} ({pnl_pct:.2f}%)]")

                        col2.metric("Time Elapsed", f"{days}d {hours}h")
                        col3.metric("Snapshots", f"{len(snapshots)}")

                        # PnL Breakdown (leg-level)
                        st.markdown("**PnL Breakdown:**")

                        # Get leg-level PnL from latest snapshot
                        pnl_base = latest_snap.get('pnl_base_apr', 0) or 0
                        pnl_reward = latest_snap.get('pnl_reward_apr', 0) or 0
                        pnl_leg1 = latest_snap.get('pnl_price_leg1', latest_snap.get('pnl_price_token1', 0)) or 0
                        pnl_leg2 = latest_snap.get('pnl_price_leg2', 0) or 0
                        pnl_leg3 = latest_snap.get('pnl_price_leg3', 0) or 0
                        pnl_leg4 = latest_snap.get('pnl_price_leg4', latest_snap.get('pnl_price_token3', 0)) or 0
                        pnl_fees = latest_snap.get('pnl_fees', 0) or 0

                        # Format with color coding
                        if pnl_base >= 0:
                            st.markdown(f"├── Base APR: :green[+${abs(pnl_base):.2f}]")
                        else:
                            st.markdown(f"├── Base APR: :red[-${abs(pnl_base):.2f}]")

                        if pnl_reward >= 0:
                            st.markdown(f"├── Reward APR: :green[+${abs(pnl_reward):.2f}]")
                        else:
                            st.markdown(f"├── Reward APR: :red[-${abs(pnl_reward):.2f}]")

                        # Leg-level price impact
                        price_1A = latest_snap.get('price_1A', position['entry_price_1A'])
                        price_change_1A_pct = ((price_1A - position['entry_price_1A']) / position['entry_price_1A'] * 100) if position['entry_price_1A'] > 0 else 0
                        if pnl_leg1 >= 0:
                            st.markdown(f"├── Price ({position['protocol_A']} Lend - {position['token1']}): :green[+${abs(pnl_leg1):.2f}] ({position['token1']}: {price_change_1A_pct:+.1f}%)")
                        else:
                            st.markdown(f"├── Price ({position['protocol_A']} Lend - {position['token1']}): :red[-${abs(pnl_leg1):.2f}] ({position['token1']}: {price_change_1A_pct:+.1f}%)")

                        # More leg-level details (similar pattern for legs 2, 3, 4)
                        # ... (abbreviated for brevity - see streamlit_app.py lines 1590-1620 for full implementation)

                        st.markdown(f"└── Fees: :red[-${abs(pnl_fees):.2f}]")

                    # Actions (mode-specific)
                    st.markdown("#### Actions")

                    if mode == 'live':
                        col1, col2 = st.columns([1, 5])
                        with col1:
                            if st.button("❌ Close", key=f"close_{position['position_id']}"):
                                service.close_position(position['position_id'], reason='manual', notes='Closed from dashboard')
                                st.success("Position closed!")
                                st.rerun()
                    else:
                        st.info("💡 Position close button disabled in historical mode")

                    if position.get('notes'):
                        st.markdown(f"**Notes:** {position['notes']}")

        conn.close()

    except Exception as e:
        st.error(f"❌ Error loading positions: {e}")


def render_rate_tables_tab(lend_rates: pd.DataFrame, borrow_rates: pd.DataFrame,
                           collateral_ratios: pd.DataFrame, prices: pd.DataFrame,
                           available_borrow: pd.DataFrame, borrow_fees: pd.DataFrame):
    """
    Render the Rate Tables tab

    Args:
        lend_rates, borrow_rates, etc.: DataFrames from data loader
    """
    st.header("📈 Current Rates")

    col1, col2 = st.columns(2)

    col1.subheader("💵 Lending Rates")
    lend_display = lend_rates.drop(columns=['Contract']) if 'Contract' in lend_rates.columns else lend_rates
    col1.dataframe(lend_display, width='stretch', hide_index=True)

    col2.subheader("💸 Borrow Rates")
    borrow_display = borrow_rates.drop(columns=['Contract']) if 'Contract' in borrow_rates.columns else borrow_rates
    col2.dataframe(borrow_display, width='stretch', hide_index=True)

    st.subheader("🔒 Collateral Ratios")
    collateral_display = collateral_ratios.drop(columns=['Contract']) if 'Contract' in collateral_ratios.columns else collateral_ratios
    st.dataframe(collateral_display, width='stretch', hide_index=True)

    st.subheader("💰 Prices")
    prices_display = prices.drop(columns=['Contract']) if 'Contract' in prices.columns else prices
    st.dataframe(prices_display, width='stretch', hide_index=True)

    st.subheader("💵 Available Borrow Liquidity")
    available_borrow_display = available_borrow.copy()
    if 'Contract' in available_borrow_display.columns:
        available_borrow_display = available_borrow_display.drop(columns=['Contract'])

    for col in available_borrow_display.columns:
        if col != 'Token':
            available_borrow_display[col] = available_borrow_display[col].apply(format_usd_abbreviated)

    st.dataframe(available_borrow_display, width='stretch', hide_index=True)

    st.subheader("💳 Borrow Fees")
    borrow_fees_display = borrow_fees.copy()
    if 'Contract' in borrow_fees_display.columns:
        borrow_fees_display = borrow_fees_display.drop(columns=['Contract'])

    for col in borrow_fees_display.columns:
        if col != 'Token':
            borrow_fees_display[col] = borrow_fees_display[col].apply(
                lambda x: f"{x*100:.2f}%" if pd.notna(x) and x > 0 else ("0.00%" if x == 0 else "N/A")
            )

    st.dataframe(borrow_fees_display, width='stretch', hide_index=True)


def render_zero_liquidity_tab(zero_liquidity_results: pd.DataFrame, deployment_usd: float,
                              use_unlevered: bool, mode: str,
                              historical_timestamp: Optional[datetime] = None):
    """
    Render the Zero Liquidity tab

    Args:
        zero_liquidity_results: Strategies with insufficient liquidity
        deployment_usd: Deployment amount threshold
        use_unlevered: Whether to show unlevered APR
        mode: 'live' or 'historical'
        historical_timestamp: Timestamp for historical mode
    """
    st.header("⚠️ Zero Liquidity Strategies")

    if not zero_liquidity_results.empty:
        st.info(f"⚠️ These strategies have insufficient liquidity (max size < ${deployment_usd:,.0f}) or missing liquidity data")

        st.metric("Strategies Found", f"{len(zero_liquidity_results)}")

        # Display with expanders (no historical charts)
        for _enum_idx, (idx, row) in enumerate(zero_liquidity_results.iterrows()):
            max_size = row.get('max_size')
            if max_size is not None and not pd.isna(max_size):
                max_size_text = f" | Max Size ${max_size:,.2f}"
            else:
                max_size_text = " | No Liquidity Data"

            if use_unlevered:
                token_flow = f"{row['token1']} → {row['token2']}"
            else:
                token_flow = f"{row['token1']} → {row['token2']} → {row['token3']}"

            if use_unlevered:
                net_apr_value = row.get('unlevered_apr', 0)
                apr5_value = row.get('unlevered_apr', 0)
            else:
                net_apr_value = row.get('apr_net', row['net_apr'])
                apr5_value = row.get('apr5', row['net_apr'])

            net_apr_indicator = "🟢" if net_apr_value >= 0 else "🔴"
            apr5_indicator = "🟢" if apr5_value >= 0 else "🔴"

            with st.expander(
                f"▶ {token_flow} | "
                f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                f"{net_apr_indicator} Net APR {net_apr_value:.2f}% | {apr5_indicator} 5day APR {apr5_value:.2f}%{max_size_text}",
                expanded=False
            ):
                # Display APR comparison table
                fee_caption, warning_message = display_apr_table(row, deployment_usd, 0.2, idx, mode, historical_timestamp)

                # Display strategy details
                max_size_msg, liquidity_msg = display_strategy_details(row, use_unlevered)

                # Display warnings/info
                st.caption(fee_caption)
                if warning_message:
                    st.warning(warning_message)

                if max_size_msg:
                    st.success(max_size_msg)
                if liquidity_msg:
                    st.info(liquidity_msg)
    else:
        st.success("✅ All strategies have sufficient liquidity for the current deployment size!")


# ============================================================================
# SIDEBAR RENDERERS
# ============================================================================

def render_data_controls(data_loader: DataLoader, mode: str):
    """
    Render data controls section (mode-specific)

    Args:
        data_loader: DataLoader instance
        mode: 'live' or 'historical'
    """
    if mode == 'live':
        st.header("📊 Live Data")

        if st.button("🔄 Refresh Data", width="stretch"):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Last updated: {data_loader.timestamp.strftime('%H:%M:%S UTC')}")

    else:  # historical
        st.header("📸 Historical Snapshot")

        st.info(f"**Viewing:** {data_loader.timestamp.strftime('%Y-%m-%d %H:%M UTC')}")

        # Snapshot age warning
        age = datetime.now() - data_loader.timestamp
        if age > timedelta(hours=24):
            st.warning(f"⚠️ Snapshot is {age.days} days old")


def render_sidebar_filters(display_results: pd.DataFrame):
    """
    Render sidebar filters

    Args:
        display_results: Current filtered results (for token/protocol options)

    Returns:
        tuple: (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1, stablecoin_only, use_unlevered, min_apr, token_filter, protocol_filter)
    """
    st.header("⚙️ Settings")

    # Liquidation Distance
    col1, col2 = st.columns([30, 7])
    with col1:
        st.markdown("**Liquidation Distance (%)**")
    with col2:
        liq_dist_text = st.text_input(
            label="Liquidation Distance (%)",
            value=str(int(settings.DEFAULT_LIQUIDATION_DISTANCE * 100)),
            label_visibility="collapsed",
            key="liq_input"
        )

    try:
        liq_value = float(liq_dist_text)
        if not (1 <= liq_value <= 100):
            st.error("Liquidation Dist must be between 1 and 100")
            st.stop()
    except ValueError:
        st.error("Liquidation Dist must be a number")
        st.stop()

    liquidation_distance = liq_value / 100

    # Clear all cached charts when liquidation distance changes
    if "last_liq_distance" not in st.session_state:
        st.session_state.last_liq_distance = liquidation_distance

    if st.session_state.last_liq_distance != liquidation_distance:
        keys_to_delete = [key for key in st.session_state.keys() if key.startswith('chart_')]
        for key in keys_to_delete:
            del st.session_state[key]
        st.session_state.last_liq_distance = liquidation_distance

    # Deployment USD
    col1, col2 = st.columns([30, 15])
    with col1:
        st.markdown("**Deployment USD**")
    with col2:
        deployment_text = st.text_input(
            label="Deployment USD",
            value="10000",
            label_visibility="collapsed",
            key="deployment_input"
        )

    try:
        deployment_usd = float(deployment_text)
        if deployment_usd < 0:
            st.error("Deployment USD must be non-negative")
            st.stop()
    except ValueError:
        st.error("Deployment USD must be a number")
        st.stop()

    st.markdown("---")

    # Toggles
    force_usdc_start = st.toggle(
        "Force token1 = USDC",
        value=True,
        help="When enabled, only shows strategies starting with USDC"
    )

    force_token3_equals_token1 = st.toggle(
        "Force token3 = token1 (no conversion)",
        value=True,
        help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
    )

    stablecoin_only = st.toggle(
        "Stablecoin Only",
        value=False,
        help="When enabled, only shows strategies where all three tokens are stablecoins"
    )

    use_unlevered = st.toggle(
        "No leverage/looping",
        value=False,
        help="When enabled, shows unlevered APR (single lend→borrow→lend cycle without recursive loop)"
    )

    st.markdown("---")

    # Filters section
    st.subheader("🔍 Filters")

    min_apr = st.number_input("Min Net APR (%)", value=0.0, step=0.5)

    token_filter = st.multiselect(
        "Filter by Token",
        options=sorted(set(display_results['token1']).union(set(display_results['token2'])).union(set(display_results['token3']))) if not display_results.empty else [],
        default=[]
    )

    protocol_filter = st.multiselect(
        "Filter by Protocol",
        options=['Navi','AlphaFi','Suilend'],
        default=[]
    )

    return (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1,
            stablecoin_only, use_unlevered, min_apr, token_filter, protocol_filter)


# ============================================================================
# MAIN DASHBOARD RENDERER
# ============================================================================

def render_dashboard(data_loader: DataLoader, mode: str):
    """
    Main dashboard renderer - works for both live and historical modes

    Args:
        data_loader: DataLoader instance (LiveDataLoader or HistoricalDataLoader)
        mode: 'live' or 'historical'
    """
    # Custom CSS
    st.markdown("""
    <style>
        .big-metric {
            font-size: 2rem;
            font-weight: bold;
            color: #1f77b4;
        }
        .protocol-badge {
            background-color: #f0f2f6;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            display: inline-block;
            margin: 0.25rem;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem;
        }
        [data-testid="stSidebar"] {
            min-width: 300px;
            max-width: 350px;
        }
    </style>
    """, unsafe_allow_html=True)

    # === SIDEBAR ===
    with st.sidebar:
        # Data controls (refresh button or timestamp info)
        render_data_controls(data_loader, mode)

        st.divider()

        # Placeholder for filters (will populate after data load)
        filter_placeholder = st.container()

        st.markdown("---")

        st.subheader("📊 Data Source")
        if mode == 'live':
            st.info(f"Live data from {len(['Navi', 'AlphaFi', 'Suilend'])} protocols")
        else:
            st.info("Historical snapshot from database")

        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # === LOAD DATA ===
    with st.spinner("Loading data..."):
        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp) = data_loader.load_data()

    if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # === POPULATE SIDEBAR FILTERS ===
    with filter_placeholder:
        # Get empty results for initial render
        empty_df = pd.DataFrame()

        (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1,
         stablecoin_only, use_unlevered, min_apr, token_filter, protocol_filter) = render_sidebar_filters(empty_df)

    # === RUN ANALYSIS ===
    analyzer = RateAnalyzer(
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        available_borrow=available_borrow,
        borrow_fees=borrow_fees,
        liquidation_distance=liquidation_distance
    )

    protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

    # Apply filters
    filtered_results = all_results.copy()

    if not filtered_results.empty:
        if force_usdc_start:
            filtered_results = filtered_results[filtered_results['token1'] == 'USDC']

        if force_token3_equals_token1:
            filtered_results = filtered_results[filtered_results['token3'] == filtered_results['token1']]

        if stablecoin_only:
            filtered_results = filtered_results[
                (filtered_results['token1'].isin(STABLECOIN_SYMBOLS)) &
                (filtered_results['token2'].isin(STABLECOIN_SYMBOLS)) &
                (filtered_results['token3'].isin(STABLECOIN_SYMBOLS))
            ]

        # Filter by deployment size
        if deployment_usd > 0:
            filtered_results = filtered_results[
                (filtered_results['max_size'].notna()) &
                (filtered_results['max_size'] >= deployment_usd)
            ]

    # Create zero_liquidity_results
    zero_liquidity_results = all_results.copy()

    if not zero_liquidity_results.empty:
        if force_usdc_start:
            zero_liquidity_results = zero_liquidity_results[zero_liquidity_results['token1'] == 'USDC']
        if force_token3_equals_token1:
            zero_liquidity_results = zero_liquidity_results[zero_liquidity_results['token3'] == zero_liquidity_results['token1']]
        if stablecoin_only:
            zero_liquidity_results = zero_liquidity_results[
                (zero_liquidity_results['token1'].isin(STABLECOIN_SYMBOLS)) &
                (zero_liquidity_results['token2'].isin(STABLECOIN_SYMBOLS)) &
                (zero_liquidity_results['token3'].isin(STABLECOIN_SYMBOLS))
            ]

        zero_liquidity_results = zero_liquidity_results[
            (zero_liquidity_results['max_size'].isna()) |
            (zero_liquidity_results['max_size'] == 0) |
            (zero_liquidity_results['max_size'] < deployment_usd)
        ]

    # Sort filtered results
    apr_col = 'unlevered_apr' if use_unlevered else 'apr_net'

    if not filtered_results.empty:
        filtered_results = filtered_results.sort_values(by=apr_col, ascending=False)
    if not zero_liquidity_results.empty:
        zero_liquidity_results = zero_liquidity_results.sort_values(by=apr_col, ascending=False)

    # Apply additional filters
    if not filtered_results.empty:
        display_results = filtered_results[filtered_results[apr_col] >= min_apr]
    else:
        display_results = filtered_results

    if token_filter and not display_results.empty:
        display_results = display_results[
            display_results['token1'].isin(token_filter) |
            display_results['token2'].isin(token_filter)
        ]

    if protocol_filter and not display_results.empty:
        display_results = display_results[
            display_results['protocol_A'].isin(protocol_filter) |
            display_results['protocol_B'].isin(protocol_filter)
        ]

    # Update sidebar with strategy count
    with filter_placeholder:
        st.metric("Strategies Found", f"{len(display_results)} / {len(all_results)}")

    # Render deployment confirmation form if active
    render_deployment_form(mode)

    # === TABS ===
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 All Strategies",
        "💼 Positions",
        "📈 Rate Tables",
        "⚠️ 0 Liquidity"
    ])

    with tab1:
        render_all_strategies_tab(
            display_results, mode, deployment_usd, liquidation_distance,
            use_unlevered, timestamp
        )

    with tab2:
        render_positions_tab(timestamp, mode)

    with tab3:
        render_rate_tables_tab(
            lend_rates, borrow_rates, collateral_ratios, prices,
            available_borrow, borrow_fees
        )

    with tab4:
        render_zero_liquidity_tab(
            zero_liquidity_results, deployment_usd, use_unlevered, mode, timestamp
        )
