"""
Unified dashboard renderer for Sui Lending Bot

This renderer works with UnifiedDataLoader and displays strategies,
positions, and rates in a tabbed interface for any timestamp.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Tuple, Optional, Union, Any, Dict
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS, STABLECOIN_SYMBOLS
from dashboard.data_loaders import DataLoader
from data.rate_tracker import RateTracker
from analysis.position_calculator import PositionCalculator


def format_days_to_breakeven(days: float) -> str:
    """
    Format days to breakeven for display

    Args:
        days: Days to breakeven (can be float('inf'), 0, or positive number)

    Returns:
        Formatted string for display
    """
    if days is None:
        return "N/A"

    # Handle infinity (never breaks even)
    if days == float('inf') or days > 99999:
        return "Never"

    # Handle zero fees (instant breakeven)
    if days == 0:
        return "0.0"

    # Handle very large values
    if days > 999:
        return ">999"

    # Normal case: display with 1 decimal place
    return f"{days:.1f}"
from dashboard.dashboard_utils import (
    format_usd_abbreviated,
    get_db_connection,
    get_strategy_history,
    create_strategy_history_chart
)
from analysis.rate_analyzer import RateAnalyzer
from analysis.position_service import PositionService
from utils.time_helpers import to_seconds, to_datetime_str


# ============================================================================
# COMPONENT RENDERERS
# ============================================================================

def display_apr_table(strategy_row: Union[pd.Series, Dict[str, Any]], deployment_usd: float,
                     liquidation_distance: float, strategy_idx: int, mode: str,
                     timestamp: Optional[int] = None) -> Tuple[str, Optional[str]]:
    """
    Display compact APR table for levered strategy with integrated deploy button

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
        deployment_usd: Deployment amount in USD from sidebar
        liquidation_distance: Liquidation distance from sidebar
        strategy_idx: Unique identifier for the strategy (DataFrame index) for unique button keys
        mode: 'unified' (kept for compatibility)
        timestamp: Unix timestamp in seconds (for chart caching)

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
    days_to_breakeven_levered = strategy_row.get('days_to_breakeven', float('inf'))

    # Build single-row table
    apr_table_data = {
        'APR(net)': [f"{apr_net_levered * 100:.2f}%"],
        'APR5': [f"{apr5_levered * 100:.2f}%"],
        'APR30': [f"{apr30_levered * 100:.2f}%"],
        'APR90': [f"{apr90_levered * 100:.2f}%"],
        'Days': [format_days_to_breakeven(days_to_breakeven_levered)]
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
                'deployment_usd': deployment_usd,
                'liquidation_distance': liquidation_distance,
                'timestamp': timestamp
            }
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


def display_strategy_details(strategy_row: Union[pd.Series, Dict[str, Any]], deployment_usd: float = 1.0) -> Tuple[Optional[str], Optional[str]]:
    """
    Display expanded strategy details when row is clicked
    Returns liquidity info to be displayed at the end

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
        deployment_usd: Deployment size in USD (for scaling token amounts)

    Returns:
        tuple: (max_size_message, liquidity_constraints_message) - strings to display at the end
    """
    # Extract all the values we need
    token1 = strategy_row['token1']
    token2 = strategy_row['token2']
    token3 = strategy_row['token3']
    protocol_A = strategy_row['protocol_A']
    protocol_B = strategy_row['protocol_B']

    # Contract addresses
    token1_contract = strategy_row.get('token1_contract', '')
    token2_contract = strategy_row.get('token2_contract', '')
    token3_contract = strategy_row.get('token3_contract', '')

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

    # Helper to format contract address (show first 6 and last 4 chars)
    def format_contract(contract: str) -> str:
        if not contract or len(contract) < 12:
            return contract
        return f"{contract[:6]}...{contract[-4:]}"

    # Build the table data
    table_data = [
        # Row 1: Protocol A, token1, Lend
        {
            'Protocol': protocol_A,
            'Token': token1,
            'Contract': format_contract(token1_contract),
            'Action': 'Lend',
            'Rate': f"{lend_rate_1A * 100:.2f}%",
            'Weight': f"{L_A:.2f}",
            'Token Amount': f"{(L_A * deployment_usd) / P1_A:.2f}",
            'Price': f"${P1_A:.4f}",
            'Fee': '',
            'Available': ''
        },
        # Row 2: Protocol A, token2, Borrow
        {
            'Protocol': protocol_A,
            'Token': token2,
            'Contract': format_contract(token2_contract),
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_2A * 100:.2f}%",
            'Weight': f"{B_A:.2f}",
            'Token Amount': f"{(B_A * deployment_usd) / P2_A:.2f}",
            'Price': f"${P2_A:.4f}",
            'Fee': f"{borrow_fee_2A*100:.2f}%" if pd.notna(borrow_fee_2A) else 'N/A',
            'Available': format_usd_abbreviated(available_borrow_2A) if pd.notna(available_borrow_2A) else 'N/A'
        },
        # Row 3: Protocol B, token2, Lend
        {
            'Protocol': protocol_B,
            'Token': token2,
            'Contract': format_contract(token2_contract),
            'Action': 'Lend',
            'Rate': f"{lend_rate_2B * 100:.2f}%",
            'Weight': f"{L_B:.2f}",
            'Token Amount': f"{(L_B * deployment_usd) / P2_B:.2f}",
            'Price': f"${P2_B:.4f}",
            'Fee': '',
            'Available': ''
        }
    ]

    # Add 4th row (Borrow token3 from Protocol B)
    table_data.append({
        'Protocol': protocol_B,
        'Token': token3,
        'Contract': format_contract(token3_contract),
        'Action': 'Borrow',
        'Rate': f"{borrow_rate_3B * 100:.2f}%",
        'Weight': f"{B_B:.2f}",
        'Token Amount': f"{(B_B * deployment_usd) / P3_B:.2f}",
        'Price': f"${P3_B:.4f}",
        'Fee': f"{borrow_fee_3B*100:.2f}%" if pd.notna(borrow_fee_3B) else 'N/A',
        'Available': format_usd_abbreviated(available_borrow_3B) if pd.notna(available_borrow_3B) else 'N/A'
    })

    # Create DataFrame and display
    details_df = pd.DataFrame(table_data)
    st.dataframe(details_df, width='stretch', hide_index=True)

    return max_size_message, liquidity_constraints_message




# ============================================================================
# TAB RENDERERS
# ============================================================================

def display_strategies_table(
    all_results: pd.DataFrame,
    mode: str = 'unified'
) -> Optional[Dict]:
    """
    Display strategies as sortable data table with clickable rows.

    Args:
        all_results: DataFrame with strategy results
        mode: Display mode (kept for compatibility)

    Returns:
        Selected strategy dict or None
    """
    import time
    start_time = time.time()

    if all_results.empty:
        st.info("No strategies found matching filters")
        return None

    # Prepare data for table
    prep_start = time.time()
    table_data = []
    for idx, row in all_results.iterrows():
        # Get token symbols for display (logic uses contracts)
        token_pair = f"{row['token1']}/{row['token2']}/{row['token3']}"

        table_data.append({
            '_idx': idx,  # Hidden index for selection
            'Token Pair': token_pair,
            'Protocol A': row['protocol_A'],
            'Protocol B': row['protocol_B'],
            'Net APR': row['net_apr'] * 100,  # Convert decimal to percentage
            'APR 5d': row.get('apr5', 0) * 100,  # APR if exit after 5 days
            'APR 30d': row.get('apr30', 0) * 100,  # 30-day average
            'Days to Breakeven': row.get('days_to_breakeven', 0),  # Days to recover fees
            'Max Size': row.get('max_size', 0),  # Max position size
        })

    df = pd.DataFrame(table_data)
    prep_time = (time.time() - prep_start) * 1000
    print(f"[{(time.time() - start_time) * 1000:7.1f}ms] [TABLE] Prepared {len(table_data)} rows in {prep_time:.1f}ms")

    # Display table with sortable columns
    render_start = time.time()
    event = st.dataframe(
        df.drop(columns=['_idx']),  # Hide index column
        width="stretch",
        hide_index=True,
        column_config={
            "Net APR": st.column_config.NumberColumn(
                "Net APR",
                format="%.2f%%",
                help="Current instantaneous APR after all fees"
            ),
            "APR 5d": st.column_config.NumberColumn(
                "APR 5d",
                format="%.2f%%",
                help="Annualized return if you exit after 5 days (includes upfront fees)"
            ),
            "APR 30d": st.column_config.NumberColumn(
                "APR 30d",
                format="%.2f%%",
                help="Annualized return if you exit after 30 days (includes upfront fees)"
            ),
            "Days to Breakeven": st.column_config.NumberColumn(
                "Days to Breakeven",
                format="%.1f days",
                help="Days until upfront fees are recovered"
            ),
            "Max Size": st.column_config.NumberColumn(
                "Max Size",
                format="$%,.0f",
                help="Maximum deployable position size"
            ),
        },
        on_select="rerun",
        selection_mode="single-row"
    )
    render_time = (time.time() - render_start) * 1000
    total_time = (time.time() - start_time) * 1000
    print(f"[{total_time:7.1f}ms] [TABLE] Rendered table in {render_time:.1f}ms (total: {total_time:.1f}ms)")

    # Check if user selected a row
    if event.selection and event.selection.rows:
        selected_idx = df.iloc[event.selection.rows[0]]['_idx']
        print(f"[TABLE] Row selected: {selected_idx}")
        return all_results.loc[selected_idx].to_dict()

    return None


def calculate_position_returns(strategy: Dict, deployment_usd: float) -> Dict:
    """
    Calculate position sizes and expected returns for a given deployment amount.

    Args:
        strategy: Strategy dict with multipliers (L_A, B_A, L_B, B_B) and net_apr
        deployment_usd: USD amount to deploy

    Returns:
        Dict with:
        - lend_a_usd: Lend A position size (USD)
        - borrow_a_usd: Borrow A position size (USD)
        - lend_b_usd: Lend B position size (USD)
        - borrow_b_usd: Borrow B position size (USD)
        - lend_a_pct: Percentage of deployment
        - borrow_a_pct: Percentage of deployment
        - lend_b_pct: Percentage of deployment
        - borrow_b_pct: Percentage of deployment
        - daily_return_usd: Expected daily return (USD)
        - monthly_return_usd: Expected monthly return (USD)
        - yearly_return_usd: Expected yearly return (USD)
        - total_fees_usd: Total upfront fees
        - days_to_breakeven: Days to recover fees

    Design Notes:
    - All rates stored as decimals (DESIGN_NOTES.md #7)
    - Position sizes = multiplier × deployment_usd (DESIGN_NOTES.md #3)
    """
    net_apr = strategy['net_apr']  # Decimal (0.1185 = 11.85%)

    # Position sizes (multiplier × deployment)
    # All strategies are 4-leg levered strategies
    lend_a_usd = strategy['L_A'] * deployment_usd
    borrow_a_usd = strategy['B_A'] * deployment_usd
    lend_b_usd = strategy['L_B'] * deployment_usd
    borrow_b_usd = strategy['B_B'] * deployment_usd

    # Percentages (for display)
    lend_a_pct = strategy['L_A'] * 100
    borrow_a_pct = strategy['B_A'] * 100
    lend_b_pct = strategy['L_B'] * 100
    borrow_b_pct = strategy['B_B'] * 100

    # Expected returns (based on net APR)
    yearly_return_usd = deployment_usd * net_apr
    daily_return_usd = yearly_return_usd / 365
    monthly_return_usd = daily_return_usd * 30

    # Fees and breakeven (from strategy calculation)
    total_fees_usd = strategy.get('total_fees_usd', 0)
    days_to_breakeven = strategy.get('days_to_breakeven', 0)

    return {
        'lend_a_usd': lend_a_usd,
        'borrow_a_usd': borrow_a_usd,
        'lend_b_usd': lend_b_usd,
        'borrow_b_usd': borrow_b_usd,
        'lend_a_pct': lend_a_pct,
        'borrow_a_pct': borrow_a_pct,
        'lend_b_pct': lend_b_pct,
        'borrow_b_pct': borrow_b_pct,
        'daily_return_usd': daily_return_usd,
        'monthly_return_usd': monthly_return_usd,
        'yearly_return_usd': yearly_return_usd,
        'total_fees_usd': total_fees_usd,
        'days_to_breakeven': days_to_breakeven
    }


@st.dialog("Strategy Details", width="large")
def show_strategy_modal(strategy: Dict, timestamp_seconds: int):
    """
    Strategy details modal with APR summary and token-level details tables.

    Redesigned to match Active Positions expanded row styling.

    Args:
        strategy: Strategy dict from all_results DataFrame
        timestamp_seconds: Current timestamp (Unix seconds) - DESIGN_NOTES.md #5
    """
    import streamlit as st
    import math

    print("=" * 80)
    print("[MODAL] show_strategy_modal called")
    print(f"[MODAL] strategy tokens: {strategy.get('token1')}/{strategy.get('token2')}/{strategy.get('token3')}")
    print("=" * 80)

    # Helper function for token precision
    def get_token_precision(price: float, target_usd: float = 10.0) -> int:
        """Calculate decimal places to show ~$10 worth of precision."""
        if price <= 0:
            return 3
        decimal_places = math.ceil(-math.log10(price / target_usd))
        return max(3, min(8, decimal_places))

    # ========================================
    # HEADER SECTION
    # ========================================
    st.markdown(f"## 📊 {strategy['token1']} / {strategy['token2']} / {strategy['token3']}")

    # ========================================
    # APR SUMMARY TABLE
    # ========================================
    # Calculate upfront fees percentage
    upfront_fees_pct = (
        strategy['B_A'] * strategy['borrow_fee_2A'] +
        strategy['B_B'] * strategy['borrow_fee_3B']
    )

    # Build display strings
    token_flow = f"{strategy['token1']} → {strategy['token2']} → {strategy['token3']}"
    protocol_pair = f"{strategy['protocol_A']} ↔ {strategy['protocol_B']}"

    # Create summary table
    summary_data = [{
        'Time': to_datetime_str(timestamp_seconds),
        'Token Flow': token_flow,
        'Protocols': protocol_pair,
        'Net APR': f"{strategy['net_apr'] * 100:.2f}%",
        'APR 5d': f"{strategy.get('apr5', 0) * 100:.2f}%",
        'APR 30d': f"{strategy.get('apr30', 0) * 100:.2f}%",
        'Liq Dist': f"{strategy['liquidation_distance'] * 100:.2f}%",
        'Upfront Fees (%)': f"{upfront_fees_pct * 100:.2f}%",
        'Days to Breakeven': f"{strategy.get('days_to_breakeven', 0):.1f}",
        'Max Liquidity': f"${strategy['max_size']:,.2f}",
    }]
    summary_df = pd.DataFrame(summary_data)

    # Apply color formatting to APR columns
    def color_apr(val):
        """Color positive APRs green, negative red"""
        if isinstance(val, str) and '%' in val:
            try:
                numeric_val = float(val.replace('%', ''))
                if numeric_val > 0:
                    return 'color: green'
                elif numeric_val < 0:
                    return 'color: red'
            except (ValueError, TypeError):
                pass
        return ''

    styled_summary_df = summary_df.style.map(color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
    st.dataframe(styled_summary_df, width='stretch', hide_index=True)

    st.markdown("")  # Tighter spacing instead of divider

    # ========================================
    # POSITION CALCULATOR - DEPLOYMENT INPUT
    # ========================================
    st.markdown("### 💰 Position Calculator")

    # Default deployment amount: min of $10k or max_size
    max_size = float(strategy.get('max_size', 1000000))
    default_deployment = min(10000.0, max_size)

    # Use column to constrain width of input
    col1, col2 = st.columns([1, 2])
    with col1:
        deployment_usd = st.number_input(
            "Deployment Amount (USD)",
            min_value=100.0,
            max_value=max_size,
            value=default_deployment,
            step=100.0,
            help="USD amount to deploy in this strategy"
        )

    st.markdown("")  # Tighter spacing instead of divider

    # ========================================
    # TOKEN-LEVEL DETAILS TABLE
    # ========================================
    # Calculate token amounts (with zero-division protection)
    entry_token_amount_1A = (strategy['L_A'] * deployment_usd) / strategy['P1_A'] if strategy['P1_A'] > 0 else 0
    entry_token_amount_2A = (strategy['B_A'] * deployment_usd) / strategy['P2_A'] if strategy['P2_A'] > 0 else 0
    entry_token_amount_2B = (strategy['L_B'] * deployment_usd) / strategy['P2_B'] if strategy['P2_B'] > 0 else 0
    entry_token_amount_3B = (strategy['B_B'] * deployment_usd) / strategy['P3_B'] if strategy['P3_B'] > 0 else 0

    # Calculate position sizes in USD (weight * deployment_usd)
    position_size_1A = strategy['L_A'] * deployment_usd
    position_size_2A = strategy['B_A'] * deployment_usd
    position_size_2B = strategy['L_B'] * deployment_usd
    position_size_3B = strategy['B_B'] * deployment_usd

    # Calculate fee amounts in USD
    fee_usd_2A = strategy['B_A'] * strategy['borrow_fee_2A'] * deployment_usd
    fee_usd_3B = strategy['B_B'] * strategy['borrow_fee_3B'] * deployment_usd

    # Calculate dynamic precision
    precision_1A = get_token_precision(strategy['P1_A'])
    precision_2A = get_token_precision(strategy['P2_A'])
    precision_2B = get_token_precision(strategy['P2_B'])
    precision_3B = get_token_precision(strategy['P3_B'])

    # Create position calculator for liquidation analysis
    position_calculator = PositionCalculator()

    # Calculate liquidation data for Row 1 (lending side - Protocol A)
    liq_result_1 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_1A,
        loan_value=position_size_2A,
        lending_token_price=strategy['P1_A'],
        borrowing_token_price=strategy['P2_A'],
        lltv=strategy['collateral_ratio_1A'],
        side='lending'
    )

    # Calculate liquidation data for Row 2 (borrowing side - Protocol A)
    liq_result_2 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_1A,
        loan_value=position_size_2A,
        lending_token_price=strategy['P1_A'],
        borrowing_token_price=strategy['P2_A'],
        lltv=strategy['collateral_ratio_1A'],
        side='borrowing'
    )

    # Calculate liquidation data for Row 3 (lending side - Protocol B)
    liq_result_3 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_2B,
        loan_value=position_size_3B,
        lending_token_price=strategy['P2_B'],
        borrowing_token_price=strategy['P3_B'],
        lltv=strategy['collateral_ratio_2B'],
        side='lending'
    )

    # Calculate liquidation data for Row 4 (borrowing side - Protocol B)
    liq_result_4 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_2B,
        loan_value=position_size_3B,
        lending_token_price=strategy['P2_B'],
        borrowing_token_price=strategy['P3_B'],
        lltv=strategy['collateral_ratio_2B'],
        side='borrowing'
    )

    # Build detail table
    st.markdown("**Position Details:**")
    detail_data = []

    # Row 1: Protocol A - Lend token1
    detail_data.append({
        'Protocol': strategy['protocol_A'],
        'Token': strategy['token1'],
        'Action': 'Lend',
        'Weight': f"{strategy['L_A']:.4f}",
        'Rate': f"{strategy['lend_rate_1A'] * 100:.2f}%" if strategy['lend_rate_1A'] > 0 else "",
        'Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}",
        'Size ($$$)': f"${position_size_1A:,.2f}",
        'Price': f"${strategy['P1_A']:.4f}",
        'Fees (%)': "",
        'Fees ($$$)': "",
        'Collateral Factor': f"{strategy['collateral_ratio_1A'] * 100:.2f}%",
        'Liquidation Price': f"${liq_result_1['liq_price']:.4f}" if liq_result_1['liq_price'] != float('inf') and liq_result_1['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_1['pct_distance'] * 100:.2f}%" if liq_result_1['liq_price'] != float('inf') and liq_result_1['liq_price'] > 0 else "N/A",
        'Max Borrow': "",
    })

    # Row 2: Protocol A - Borrow token2
    detail_data.append({
        'Protocol': strategy['protocol_A'],
        'Token': strategy['token2'],
        'Action': 'Borrow',
        'Weight': f"{strategy['B_A']:.4f}",
        'Rate': f"{strategy['borrow_rate_2A'] * 100:.2f}%" if strategy['borrow_rate_2A'] > 0 else "",
        'Token Amount': f"{entry_token_amount_2A:,.{precision_2A}f}",
        'Size ($$$)': f"${position_size_2A:,.2f}",
        'Price': f"${strategy['P2_A']:.4f}",
        'Fees (%)': f"{strategy['borrow_fee_2A'] * 100:.2f}%" if strategy['borrow_fee_2A'] > 0 else "",
        'Fees ($$$)': f"${fee_usd_2A:.2f}" if fee_usd_2A > 0 else "",
        'Collateral Factor': "",
        'Liquidation Price': f"${liq_result_2['liq_price']:.4f}" if liq_result_2['liq_price'] != float('inf') and liq_result_2['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_2['pct_distance'] * 100:.2f}%" if liq_result_2['liq_price'] != float('inf') and liq_result_2['liq_price'] > 0 else "N/A",
        'Max Borrow': f"${strategy['available_borrow_2A']:,.2f}" if strategy['available_borrow_2A'] > 0 else "",
    })

    # Row 3: Protocol B - Lend token2
    detail_data.append({
        'Protocol': strategy['protocol_B'],
        'Token': strategy['token2'],
        'Action': 'Lend',
        'Weight': f"{strategy['L_B']:.4f}",
        'Rate': f"{strategy['lend_rate_2B'] * 100:.2f}%" if strategy['lend_rate_2B'] > 0 else "",
        'Token Amount': f"{entry_token_amount_2B:,.{precision_2B}f}",
        'Size ($$$)': f"${position_size_2B:,.2f}",
        'Price': f"${strategy['P2_B']:.4f}",
        'Fees (%)': "",
        'Fees ($$$)': "",
        'Collateral Factor': f"{strategy['collateral_ratio_2B'] * 100:.2f}%",
        'Liquidation Price': f"${liq_result_3['liq_price']:.4f}" if liq_result_3['liq_price'] != float('inf') and liq_result_3['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_3['pct_distance'] * 100:.2f}%" if liq_result_3['liq_price'] != float('inf') and liq_result_3['liq_price'] > 0 else "N/A",
        'Max Borrow': "",
    })

    # Row 4: Protocol B - Borrow token3
    detail_data.append({
        'Protocol': strategy['protocol_B'],
        'Token': strategy['token3'],
        'Action': 'Borrow',
        'Weight': f"{strategy['B_B']:.4f}",
        'Rate': f"{strategy['borrow_rate_3B'] * 100:.2f}%" if strategy['borrow_rate_3B'] > 0 else "",
        'Token Amount': f"{entry_token_amount_3B:,.{precision_3B}f}",
        'Size ($$$)': f"${position_size_3B:,.2f}",
        'Price': f"${strategy['P3_B']:.4f}",
        'Fees (%)': f"{strategy['borrow_fee_3B'] * 100:.2f}%" if strategy['borrow_fee_3B'] > 0 else "",
        'Fees ($$$)': f"${fee_usd_3B:.2f}" if fee_usd_3B > 0 else "",
        'Collateral Factor': "",
        'Liquidation Price': f"${liq_result_4['liq_price']:.4f}" if liq_result_4['liq_price'] != float('inf') and liq_result_4['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_4['pct_distance'] * 100:.2f}%" if liq_result_4['liq_price'] != float('inf') and liq_result_4['liq_price'] > 0 else "N/A",
        'Max Borrow': f"${strategy['available_borrow_3B']:,.2f}" if strategy['available_borrow_3B'] > 0 else "",
    })

    # Display detail table with color formatting
    detail_df = pd.DataFrame(detail_data)

    # Apply color formatting to Rate column
    def color_rate(val):
        """Color positive rates green"""
        if isinstance(val, str) and '%' in val and val != "":
            try:
                numeric_val = float(val.replace('%', ''))
                if numeric_val > 0:
                    return 'color: green'
            except (ValueError, TypeError):
                pass
        return ''

    # Apply color formatting to Liquidation Distance column
    def color_liq_distance(val):
        """Color liquidation distance based on risk level"""
        if isinstance(val, str) and '%' in val and val != "N/A":
            try:
                numeric_val = abs(float(val.replace('%', '')))  # Use absolute value
                if numeric_val < 10:
                    return 'color: red'
                elif numeric_val < 30:
                    return 'color: orange'
                else:
                    return 'color: green'
            except (ValueError, TypeError):
                pass
        return ''

    styled_detail_df = detail_df.style.map(color_rate, subset=['Rate']).map(color_liq_distance, subset=['Liq Distance'])
    st.dataframe(styled_detail_df, width='stretch', hide_index=True)

    st.markdown("")  # Tighter spacing instead of divider

    # ========================================
    # ACTION BUTTON
    # ========================================
    if st.button("🚀 Deploy Position", type="primary", use_container_width=True):
        print("[DEPLOY BUTTON] Deploy button clicked!")
        try:
            # Connect to database
            conn = get_db_connection()
            service = PositionService(conn)

            # Get liquidation distance from strategy
            liquidation_distance = strategy.get('liquidation_distance', 0.20)

            # Get position multipliers from strategy history calculation
            _, L_A, B_A, L_B, B_B = get_strategy_history(
                strategy_row=strategy,
                liquidation_distance=liquidation_distance
            )

            # Build positions dict
            positions = {
                'L_A': L_A,
                'B_A': B_A,
                'L_B': L_B,
                'B_B': B_B
            }

            # Create position (all strategies are 4-leg levered)
            position_id = service.create_position(
                strategy_row=pd.Series(strategy) if isinstance(strategy, dict) else strategy,
                positions=positions,
                token1=strategy['token1'],
                token2=strategy['token2'],
                token3=strategy.get('token3'),
                token1_contract=strategy['token1_contract'],
                token2_contract=strategy['token2_contract'],
                token3_contract=strategy.get('token3_contract'),
                protocol_A=strategy['protocol_A'],
                protocol_B=strategy['protocol_B'],
                deployment_usd=deployment_usd,
                is_paper_trade=True,
                notes=""
            )

            conn.close()

            print(f"[DEPLOY BUTTON] Position created successfully: {position_id}")

            # Store success info in session state
            st.session_state.deployment_success = {
                'position_id': position_id,
                'timestamp': time.time()
            }

            print("[DEPLOY BUTTON] Success - triggering rerun to close modal and refresh dashboard")

            # Set flag to prevent modal from reopening
            st.session_state.skip_modal_reopen = True

            # Trigger rerun to close modal and refresh dashboard
            st.rerun()

        except Exception as e:
            import traceback
            print(f"[DEPLOY BUTTON] ERROR: {e}")
            traceback.print_exc()
            st.error(f"❌ Failed to create position: {e}")


def render_rate_tables_tab(lend_rates: pd.DataFrame, borrow_rates: pd.DataFrame,
                           collateral_ratios: pd.DataFrame, prices: pd.DataFrame,
                           available_borrow: pd.DataFrame, borrow_fees: pd.DataFrame):
    """
    Render the Rate Tables tab

    Args:
        lend_rates, borrow_rates, etc.: DataFrames from data loader
    """
    # Helper to format contract address (show first 6 and last 4 chars)
    def format_contract(contract: str) -> str:
        if not contract or len(contract) < 12:
            return contract
        return f"{contract[:6]}...{contract[-4:]}"

    st.header("📈 Current Rates")

    col1, col2 = st.columns(2)

    col1.subheader("💵 Lending Rates")
    lend_display = lend_rates.copy()
    if 'Contract' in lend_display.columns:
        # Format contract addresses to be more readable
        lend_display['Contract'] = lend_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in lend_display.columns if c not in ['Token', 'Contract']]
        lend_display = lend_display[cols]
    col1.dataframe(lend_display, width='stretch', hide_index=True)

    col2.subheader("💸 Borrow Rates")
    borrow_display = borrow_rates.copy()
    if 'Contract' in borrow_display.columns:
        # Format contract addresses to be more readable
        borrow_display['Contract'] = borrow_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in borrow_display.columns if c not in ['Token', 'Contract']]
        borrow_display = borrow_display[cols]
    col2.dataframe(borrow_display, width='stretch', hide_index=True)

    st.subheader("🔒 Collateral Ratios")
    collateral_display = collateral_ratios.copy()
    if 'Contract' in collateral_display.columns:
        # Format contract addresses to be more readable
        collateral_display['Contract'] = collateral_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in collateral_display.columns if c not in ['Token', 'Contract']]
        collateral_display = collateral_display[cols]
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


def render_positions_table_tab():
    """
    Render simple positions table showing all active positions
    """
    st.header("💼 Active Positions")

    try:
        # Connect to database
        conn = get_db_connection()
        service = PositionService(conn)

        # Get active positions
        active_positions = service.get_active_positions()

        if active_positions.empty:
            st.info("📭 No active positions. Deploy a strategy from the All Strategies tab to get started!")
            conn.close()
            return

        # Get latest rates from rates_snapshot table
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(timestamp) FROM rates_snapshot")
        latest_timestamp_str = cursor.fetchone()[0]
        latest_timestamp = to_seconds(latest_timestamp_str)  # Convert to Unix timestamp

        # Query all rates and prices at latest timestamp
        rates_query = """
        SELECT protocol, token, lend_total_apr, borrow_total_apr, borrow_fee, price_usd
        FROM rates_snapshot
        WHERE timestamp = ?
        """
        rates_df = pd.read_sql_query(rates_query, conn, params=(latest_timestamp_str,))

        # Helper function to get rate
        def get_rate(token, protocol, rate_type):
            """Get lend or borrow rate for token/protocol, return 0 if not found"""
            row = rates_df[(rates_df['token'] == token) & (rates_df['protocol'] == protocol)]
            if row.empty:
                return 0.0
            return float(row[f'{rate_type}_total_apr'].iloc[0])

        # Helper function to get borrow fee
        def get_borrow_fee(token, protocol):
            """Get borrow fee for token/protocol, return 0 if not found"""
            row = rates_df[(rates_df['token'] == token) & (rates_df['protocol'] == protocol)]
            if row.empty:
                return 0.0
            return float(row['borrow_fee'].iloc[0]) if pd.notna(row['borrow_fee'].iloc[0]) else 0.0

        # Helper function to get price
        def get_price(token, protocol):
            """Get current price for token/protocol, return 0 if not found"""
            row = rates_df[(rates_df['token'] == token) & (rates_df['protocol'] == protocol)]
            if row.empty:
                return 0.0
            return float(row['price_usd'].iloc[0]) if pd.notna(row['price_usd'].iloc[0]) else 0.0

        # Helper function to calculate token amount precision
        def get_token_precision(price: float, target_usd: float = 10.0) -> int:
            """
            Calculate decimal places needed to show at least target_usd worth of precision.

            Args:
                price: Token price in USD
                target_usd: Target USD value for precision (default $10)

            Returns:
                Number of decimal places to display (minimum 3)

            Examples:
                - BTC @ $100,000 → 4 decimals (0.0001 BTC = $10)
                - ETH @ $3,000 → 3 decimals (0.001 ETH = $3)
                - SUI @ $1 → 3 decimals (minimum)
                - DEEP @ $0.01 → 3 decimals (1.000 DEEP = $0.01)
            """
            import math

            if price <= 0:
                return 3  # Default fallback (minimum 3)

            # Calculate: decimal_places = ceil(-log10(price / target_usd))
            decimal_places = math.ceil(-math.log10(price / target_usd))

            # Clamp between 3 and 8 (minimum 3 decimals, maximum 8)
            return max(3, min(8, decimal_places))

        # Render expandable rows (Stages 1-4)
        for _, position in active_positions.iterrows():
            # Build token flow string (all positions are 4-leg levered)
            token_flow = f"{position['token1']} → {position['token2']} → {position['token3']}"

            # Build protocol pair string
            protocol_pair = f"{position['protocol_A']} ↔ {position['protocol_B']}"

            # Get current rates for all 4 legs from rates_snapshot
            lend_1A = get_rate(position['token1'], position['protocol_A'], 'lend')
            borrow_2A = get_rate(position['token2'], position['protocol_A'], 'borrow')
            lend_2B = get_rate(position['token2'], position['protocol_B'], 'lend')
            borrow_3B = get_rate(position['token3'], position['protocol_B'], 'borrow')

            # Get borrow fees
            borrow_fee_2A = get_borrow_fee(position['token2'], position['protocol_A'])
            borrow_fee_3B = get_borrow_fee(position['token3'], position['protocol_B'])

            # Calculate GROSS APR using position multipliers
            # Rates are already in decimal format (0.05 = 5%)
            gross_apr = (
                (position['L_A'] * lend_1A) +
                (position['L_B'] * lend_2B) -
                (position['B_A'] * borrow_2A) -
                (position['B_B'] * borrow_3B)
            )

            # Calculate fee cost (keep as decimal per DESIGN_NOTES.md Rule #7)
            fee_cost = position['B_A'] * borrow_fee_2A + position['B_B'] * borrow_fee_3B

            # Calculate NET APR (in decimal)
            current_net_apr_decimal = gross_apr - fee_cost

            # Calculate position value and realized APR
            pv_result = service.calculate_position_value(position, latest_timestamp)
            realized_apr = service.calculate_realized_apr(position, latest_timestamp)

            # STAGE 1: Build summary title for expander
            title = f"▶ {to_datetime_str(position['entry_timestamp'])} | {token_flow} | {protocol_pair} | Entry {position['entry_net_apr'] * 100:.2f}% | Current {current_net_apr_decimal * 100:.2f}% | Realized {realized_apr * 100:.2f}% | Value ${pv_result['current_value']:.2f}"

            # STAGE 2-3: Build detail table inside expander
            with st.expander(title, expanded=False):
                # Summary table (1 row with key metrics)
                summary_data = [{
                    'Entry Time': to_datetime_str(position['entry_timestamp']),
                    'Token Flow': token_flow,
                    'Protocols': protocol_pair,
                    'Start Capital': f"${position['deployment_usd']:,.2f}",
                    'Entry APR': f"{position['entry_net_apr'] * 100:.2f}%",
                    'Current APR': f"{current_net_apr_decimal * 100:.2f}%",
                    'Realized APR': f"{realized_apr * 100:.2f}%",
                    'Current Value': f"${pv_result['current_value']:,.2f}",
                    'Entry Liq Distance': f"{position['entry_liquidation_distance'] * 100:.2f}%",
                }]
                summary_df = pd.DataFrame(summary_data)

                # Apply color formatting to APR columns
                def color_apr(val):
                    """Color positive APRs green, negative red"""
                    if isinstance(val, str) and '%' in val:
                        try:
                            numeric_val = float(val.replace('%', ''))
                            if numeric_val > 0:
                                return 'color: green'
                            elif numeric_val < 0:
                                return 'color: red'
                        except (ValueError, TypeError):
                            pass
                    return ''

                styled_summary_df = summary_df.style.map(
                    color_apr,
                    subset=['Entry APR', 'Current APR', 'Realized APR']
                )
                st.dataframe(styled_summary_df, width='stretch', hide_index=True)

                # Add spacing
                st.markdown("---")

                # Detail table (4 legs breakdown)
                detail_data = []

                # Calculate entry token amounts (Stage 3) with zero-division protection
                entry_token_amount_1A = (position['L_A'] * position['deployment_usd']) / position['entry_price_1A'] if position['entry_price_1A'] > 0 else 0
                entry_token_amount_2A = (position['B_A'] * position['deployment_usd']) / position['entry_price_2A'] if position['entry_price_2A'] > 0 else 0
                entry_token_amount_2B = (position['L_B'] * position['deployment_usd']) / position['entry_price_2B'] if position['entry_price_2B'] > 0 else 0
                entry_token_amount_3B = (position['B_B'] * position['deployment_usd']) / position['entry_price_3B'] if position['entry_price_3B'] > 0 else 0

                # STAGE 4: Get live prices for all tokens
                live_price_1A = get_price(position['token1'], position['protocol_A'])
                live_price_2A = get_price(position['token2'], position['protocol_A'])
                live_price_2B = get_price(position['token2'], position['protocol_B'])
                live_price_3B = get_price(position['token3'], position['protocol_B'])

                # STAGE 4: Calculate current token amounts (price-rebalanced to maintain USD values)
                current_token_amount_1A = (position['L_A'] * position['deployment_usd']) / live_price_1A if live_price_1A > 0 else 0
                current_token_amount_2A = (position['B_A'] * position['deployment_usd']) / live_price_2A if live_price_2A > 0 else 0
                current_token_amount_2B = (position['L_B'] * position['deployment_usd']) / live_price_2B if live_price_2B > 0 else 0
                current_token_amount_3B = (position['B_B'] * position['deployment_usd']) / live_price_3B if live_price_3B > 0 else 0

                # Calculate dynamic precision for token amounts (based on live prices)
                precision_1A = get_token_precision(live_price_1A)
                precision_2A = get_token_precision(live_price_2A)
                precision_2B = get_token_precision(live_price_2B)
                precision_3B = get_token_precision(live_price_3B)

                # Calculate liquidation prices for all 4 legs
                from analysis.position_calculator import PositionCalculator
                calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])

                # Helper function to format liquidation price
                def format_liq_price(liq_result):
                    if liq_result['direction'] == 'liquidated':
                        return "LIQUIDATED"
                    elif liq_result['direction'] == 'impossible':
                        return ""
                    else:
                        return f"${liq_result['liq_price']:.4f}"

                # Helper function to format liquidation distance
                def format_liq_distance(liq_result):
                    if liq_result['direction'] == 'liquidated':
                        return "0.00%"
                    elif liq_result['direction'] == 'impossible':
                        return ""
                    else:
                        return f"{liq_result['pct_distance'] * 100:.2f}%"

                # Helper function to format target liquidation distance
                def get_target_liq_distance_display(target_liq_dist_input: float, action: str) -> str:
                    """
                    Get the appropriate liquidation distance to display based on action type.

                    Args:
                        target_liq_dist_input: User's target liquidation distance (e.g., 0.20)
                        action: 'Lend' or 'Borrow'

                    Returns:
                        Formatted percentage string
                    """
                    if action == 'Lend':
                        # Show original user input (lending protection)
                        return f"{target_liq_dist_input * 100:.2f}%"
                    else:  # action == 'Borrow'
                        # Transform and show liq_max (borrowing protection)
                        liq_max = target_liq_dist_input / (1 - target_liq_dist_input)
                        return f"{liq_max * 100:.2f}%"

                # Calculate target weights using PositionCalculator with entry liquidation distance
                target_calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])
                target_positions = target_calc.calculate_positions(
                    collateral_ratio_A=position['entry_collateral_ratio_1A'],
                    collateral_ratio_B=position['entry_collateral_ratio_2B']
                )

                # Calculate current collateral and loan values using ENTRY token amounts and LIVE PRICES
                # Token amounts don't change - only prices change
                # Protocol A (Lend token1, Borrow token2)
                # Collateral value = entry token amount × live price
                current_collateral_A = entry_token_amount_1A * live_price_1A
                current_loan_A = entry_token_amount_2A * live_price_2A

                # Leg 1: Liquidation price for token1 (lending side - price must drop)
                liq_1A = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_A,
                    loan_value=current_loan_A,
                    lending_token_price=live_price_1A,
                    borrowing_token_price=live_price_2A,
                    lltv=position['entry_collateral_ratio_1A'],
                    side='lending'
                )

                # Leg 2: Liquidation price for token2 (borrowing side - price must rise)
                liq_2A = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_A,
                    loan_value=current_loan_A,
                    lending_token_price=live_price_1A,
                    borrowing_token_price=live_price_2A,
                    lltv=position['entry_collateral_ratio_1A'],
                    side='borrowing'
                )

                # Protocol B (Lend token2, Borrow token3)
                # Collateral value = entry token amount × live price
                current_collateral_B = entry_token_amount_2B * live_price_2B
                current_loan_B = entry_token_amount_3B * live_price_3B

                # Leg 3: Liquidation price for token2 (lending side - price must drop)
                liq_2B = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_B,
                    loan_value=current_loan_B,
                    lending_token_price=live_price_2B,
                    borrowing_token_price=live_price_3B,
                    lltv=position['entry_collateral_ratio_2B'],
                    side='lending'
                )

                # Leg 4: Liquidation price for token3 (borrowing side - price must rise)
                liq_3B = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_B,
                    loan_value=current_loan_B,
                    lending_token_price=live_price_2B,
                    borrowing_token_price=live_price_3B,
                    lltv=position['entry_collateral_ratio_2B'],
                    side='borrowing'
                )

                # Row 1: Protocol A - Lend token1
                detail_data.append({
                    'Protocol': position['protocol_A'],
                    'Token': position['token1'],
                    'Action': 'Lend',
                    'Weight': f"{position['L_A']:.4f}",
                    'Target Weight': f"{target_positions['L_A']:.4f}",
                    'Entry Rate': f"{position['entry_lend_rate_1A'] * 100:.2f}%",
                    'Entry Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}",
                    'Current Token Amount': f"{current_token_amount_1A:,.{precision_1A}f}",
                    'Entry Price': f"${position['entry_price_1A']:.4f}",
                    'Live Price': f"${live_price_1A:.4f}",
                    'Live Rate': f"{lend_1A * 100:.2f}%",
                    'Current Liq Price': format_liq_price(liq_1A),
                    'Liq Distance': format_liq_distance(liq_1A),
                    'Target Liq Dist': get_target_liq_distance_display(position['entry_liquidation_distance'], 'Lend'),
                })

                # Row 2: Protocol A - Borrow token2
                detail_data.append({
                    'Protocol': position['protocol_A'],
                    'Token': position['token2'],
                    'Action': 'Borrow',
                    'Weight': f"{position['B_A']:.4f}",
                    'Target Weight': f"{target_positions['B_A']:.4f}",
                    'Entry Rate': f"{position['entry_borrow_rate_2A'] * 100:.2f}%",
                    'Entry Token Amount': f"{entry_token_amount_2A:,.{precision_2A}f}",
                    'Current Token Amount': f"{current_token_amount_2A:,.{precision_2A}f}",
                    'Entry Price': f"${position['entry_price_2A']:.4f}",
                    'Live Price': f"${live_price_2A:.4f}",
                    'Live Rate': f"{borrow_2A * 100:.2f}%",
                    'Current Liq Price': format_liq_price(liq_2A),
                    'Liq Distance': format_liq_distance(liq_2A),
                    'Target Liq Dist': get_target_liq_distance_display(position['entry_liquidation_distance'], 'Borrow'),
                })

                # Row 3: Protocol B - Lend token2
                detail_data.append({
                    'Protocol': position['protocol_B'],
                    'Token': position['token2'],
                    'Action': 'Lend',
                    'Weight': f"{position['L_B']:.4f}",
                    'Target Weight': f"{target_positions['L_B']:.4f}",
                    'Entry Rate': f"{position['entry_lend_rate_2B'] * 100:.2f}%",
                    'Entry Token Amount': f"{entry_token_amount_2B:,.{precision_2B}f}",
                    'Current Token Amount': f"{current_token_amount_2B:,.{precision_2B}f}",
                    'Entry Price': f"${position['entry_price_2B']:.4f}",
                    'Live Price': f"${live_price_2B:.4f}",
                    'Live Rate': f"{lend_2B * 100:.2f}%",
                    'Current Liq Price': format_liq_price(liq_2B),
                    'Liq Distance': format_liq_distance(liq_2B),
                    'Target Liq Dist': get_target_liq_distance_display(position['entry_liquidation_distance'], 'Lend'),
                })

                # Row 4: Protocol B - Borrow token3 (4th leg)
                detail_data.append({
                    'Protocol': position['protocol_B'],
                    'Token': position['token3'],
                    'Action': 'Borrow',
                    'Weight': f"{position['B_B']:.4f}",
                    'Target Weight': f"{target_positions['B_B']:.4f}",
                    'Entry Rate': f"{position['entry_borrow_rate_3B'] * 100:.2f}%",
                    'Entry Token Amount': f"{entry_token_amount_3B:,.{precision_3B}f}",
                    'Current Token Amount': f"{current_token_amount_3B:,.{precision_3B}f}",
                    'Entry Price': f"${position['entry_price_3B']:.4f}",
                    'Live Price': f"${live_price_3B:.4f}",
                    'Live Rate': f"{borrow_3B * 100:.2f}%",
                    'Current Liq Price': format_liq_price(liq_3B),
                    'Liq Distance': format_liq_distance(liq_3B),
                    'Target Liq Dist': get_target_liq_distance_display(position['entry_liquidation_distance'], 'Borrow'),
                })

                # Display detail table with styling
                detail_df = pd.DataFrame(detail_data)

                # Apply modal style guide formatting
                def color_rate(val):
                    """Color positive rates green, negative red"""
                    if isinstance(val, str) and '%' in val:
                        try:
                            numeric_val = float(val.replace('%', ''))
                            if numeric_val > 0:
                                return 'color: green'
                            elif numeric_val < 0:
                                return 'color: red'
                        except (ValueError, TypeError):
                            pass
                    return ''

                def color_liq_price(val):
                    """Color liquidation prices - red for LIQUIDATED"""
                    if isinstance(val, str):
                        if val == "LIQUIDATED":
                            return 'color: red; font-weight: bold'
                    return ''

                def color_liq_distance(val):
                    """Color liquidation distance based on risk level"""
                    if isinstance(val, str) and '%' in val and val != "":
                        try:
                            numeric_val = abs(float(val.replace('%', '')))  # Use absolute value
                            if numeric_val < 10:
                                return 'color: red; font-weight: bold'
                            elif numeric_val < 30:
                                return 'color: orange'
                            else:
                                return 'color: green'
                        except (ValueError, TypeError):
                            pass
                    return ''

                # Apply styling to rates and liquidation columns
                styled_detail_df = detail_df.style.map(
                    color_rate,
                    subset=['Entry Rate', 'Live Rate']
                ).map(
                    color_liq_price,
                    subset=['Current Liq Price']
                ).map(
                    color_liq_distance,
                    subset=['Liq Distance']
                )

                st.dataframe(styled_detail_df, width='stretch', hide_index=True)

        conn.close()

    except Exception as e:
        st.error(f"❌ Error loading positions: {e}")


def render_zero_liquidity_tab(zero_liquidity_results: pd.DataFrame, deployment_usd: float,
                              mode: str,
                              timestamp: Optional[int] = None):
    """
    Render the Zero Liquidity tab

    Args:
        zero_liquidity_results: Strategies with insufficient liquidity
        deployment_usd: Deployment amount threshold
        mode: 'unified' (kept for compatibility)
        timestamp: Unix timestamp in seconds (for chart caching)
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

            token_flow = f"{row['token1']} → {row['token2']} → {row['token3']}"
            net_apr_value = row.get('apr_net', row['net_apr'])
            apr5_value = row.get('apr5', row['net_apr'])

            net_apr_indicator = "🟢" if net_apr_value >= 0 else "🔴"
            apr5_indicator = "🟢" if apr5_value >= 0 else "🔴"

            with st.expander(
                f"▶ {token_flow} | "
                f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                f"{net_apr_indicator} Net APR {net_apr_value * 100:.2f}% | {apr5_indicator} 5day APR {apr5_value * 100:.2f}%{max_size_text}",
                expanded=False
            ):
                # Display APR comparison table
                fee_caption, warning_message = display_apr_table(row, deployment_usd, 0.2, idx, mode, timestamp)

                # Display strategy details
                max_size_msg, liquidity_msg = display_strategy_details(row, deployment_usd)

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
        tuple: (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1, stablecoin_only, min_apr, token_filter, protocol_filter)
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
        value=False,
        help="When enabled, only shows strategies starting with USDC"
    )

    force_token3_equals_token1 = st.toggle(
        "Force token3 = token1 (no conversion)",
        value=False,
        help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
    )

    stablecoin_only = st.toggle(
        "Stablecoin Only",
        value=False,
        help="When enabled, only shows strategies where all three tokens are stablecoins"
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
        options=['Navi', 'AlphaFi', 'Suilend', 'ScallopLend', 'ScallopBorrow'],
        default=[]
    )

    return (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1,
            stablecoin_only, min_apr, token_filter, protocol_filter)


# ============================================================================
# MAIN DASHBOARD RENDERER
# ============================================================================

def render_dashboard(data_loader: DataLoader, mode: str):
    """
    Main dashboard renderer - unified mode for all timestamps

    Args:
        data_loader: DataLoader instance (UnifiedDataLoader)
        mode: 'unified' (kept for backward compatibility, no longer used for branching logic)
    """
    import time
    dashboard_start = time.time()
    print(f"\n[{'0.0':>7}ms] [DASHBOARD] Starting render")

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
        # Data controls now handled in streamlit_app.py

        # Placeholder for filters (will populate after data load)
        filter_placeholder = st.container()

        st.markdown("---")

        st.subheader("📊 Data Source")
        st.info("Historical snapshot from database (use 'Get Live Data' button to refresh)")

        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # === LOAD DATA ===
    load_start = time.time()
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Loading data...")
    with st.spinner("Loading data..."):
        (lend_rates, borrow_rates, collateral_ratios, prices,
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp) = data_loader.load_data()

    load_time = (time.time() - load_start) * 1000
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Data loaded in {load_time:.1f}ms")

    # IMMEDIATELY convert timestamp to seconds (Unix timestamp)
    # DataLoader may return datetime, pandas.Timestamp, or string - convert to int
    timestamp_seconds = to_seconds(timestamp)
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Timestamp converted: {timestamp_seconds}")

    if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # === POPULATE SIDEBAR FILTERS ===
    with filter_placeholder:
        # Get empty results for initial render
        empty_df = pd.DataFrame()

        (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1,
         stablecoin_only, min_apr, token_filter, protocol_filter) = render_sidebar_filters(empty_df)

    # === RUN ANALYSIS WITH DATABASE CACHING ===
    analysis_start = time.time()
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Starting analysis...")

    # Initialize RateTracker for database cache
    tracker = RateTracker()

    # Check database cache FIRST
    print(f"[CACHE] Checking: timestamp={timestamp_seconds}, liq_dist={liquidation_distance}")
    cached_results = tracker.load_analysis_cache(timestamp_seconds, liquidation_distance)

    if cached_results is not None:
        # Use cached analysis from database (returns DataFrame only)
        all_results = cached_results
        # Extract protocol_A and protocol_B from the best strategy (first row, sorted by net_apr desc)
        if not all_results.empty:
            best_strategy = all_results.iloc[0]
            protocol_A = best_strategy['protocol_A']
            protocol_B = best_strategy['protocol_B']
        else:
            protocol_A = None
            protocol_B = None

        st.sidebar.caption("✅ Using cached analysis from database")
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] ✅ Cache HIT: {len(all_results)} strategies")
    else:
        # Run analysis (expensive operation)
        st.sidebar.caption("⏳ Running strategy analysis...")
        print(f"[CACHE MISS] No cached analysis found")
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] ❌ Cache MISS - running analysis...")

        analyzer_init_start = time.time()
        print(f"[ANALYSIS START] Running analyzer.find_best_protocol_pair()")
        analyzer = RateAnalyzer(
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
            available_borrow=available_borrow,
            borrow_fees=borrow_fees,
            timestamp=timestamp_seconds,  # Pass Unix seconds (int)
            liquidation_distance=liquidation_distance
        )
        analyzer_init_time = (time.time() - analyzer_init_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] RateAnalyzer initialized in {analyzer_init_time:.1f}ms")

        analysis_run_start = time.time()
        protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()
        analysis_run_time = (time.time() - analysis_run_start) * 1000
        print(f"[ANALYSIS COMPLETE] Found {len(all_results)} valid strategies")
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Analysis completed: {len(all_results)} strategies in {analysis_run_time:.1f}ms")

        # Save to database cache
        tracker.save_analysis_cache(timestamp_seconds, liquidation_distance, all_results)
        print(f"[CACHE SAVE] Saved to database")
        analysis_time = (time.time() - analysis_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Total analysis time: {analysis_time:.1f}ms")

    # Apply filters
    filter_start = time.time()
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
    apr_col = 'apr_net'

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

    filter_time = (time.time() - filter_start) * 1000
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Filtering complete in {filter_time:.1f}ms: {len(display_results)}/{len(all_results)} strategies")

    # Update sidebar with strategy count
    with filter_placeholder:
        st.metric("Strategies Found", f"{len(display_results)} / {len(all_results)}")

    # Display deployment success banner if present
    if 'deployment_success' in st.session_state:
        success_info = st.session_state.deployment_success
        position_id = success_info['position_id']

        # Show success banner
        st.success(f"✅ **Position Deployed Successfully!** Position ID: `{position_id}`")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("📊 View your position details in the **Positions** tab")
        with col2:
            if st.button("✓ Dismiss", type="secondary"):
                del st.session_state.deployment_success
                st.rerun()

        st.markdown("---")

    # === TABS ===
    tabs_start = time.time()
    print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Rendering tabs...")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 All Strategies",
        "📈 Rate Tables",
        "⚠️ 0 Liquidity",
        "💼 Positions"
    ])

    with tab1:
        tab1_start = time.time()
        st.markdown("### Top Lending Strategies")
        st.markdown("Click column headers to sort. Click checkbox to view details.")

        # Display sortable table
        selected_strategy = display_strategies_table(display_results, mode=mode)

        # Check if we should skip reopening modal after deployment
        skip_reopen = st.session_state.get('skip_modal_reopen', False)
        if skip_reopen:
            print("[TAB1] Skipping modal reopen after deployment")
            st.session_state.skip_modal_reopen = False
            selected_strategy = None  # Clear selection

        # If user clicked a row, show strategy modal
        if selected_strategy:
            print(f"[TAB1] Opening strategy modal for selected strategy")
            show_strategy_modal(selected_strategy, timestamp_seconds)

        tab1_time = (time.time() - tab1_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab1 (Strategies) rendered in {tab1_time:.1f}ms")

    with tab2:
        tab2_start = time.time()
        render_rate_tables_tab(
            lend_rates, borrow_rates, collateral_ratios, prices,
            available_borrow, borrow_fees
        )
        tab2_time = (time.time() - tab2_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab2 (Rate Tables) rendered in {tab2_time:.1f}ms")

    with tab3:
        tab3_start = time.time()
        render_zero_liquidity_tab(
            zero_liquidity_results, deployment_usd, mode, timestamp_seconds
        )
        tab3_time = (time.time() - tab3_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab3 (Zero Liquidity) rendered in {tab3_time:.1f}ms")

    with tab4:
        tab4_start = time.time()
        render_positions_table_tab()
        tab4_time = (time.time() - tab4_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab4 (Positions) rendered in {tab4_time:.1f}ms")

    total_dashboard_time = (time.time() - dashboard_start) * 1000
    print(f"[{total_dashboard_time:7.1f}ms] [DASHBOARD] ✅ Dashboard render complete (total: {total_dashboard_time:.1f}ms)\n")
