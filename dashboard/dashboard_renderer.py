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
    protocol_a = strategy_row['protocol_a']
    protocol_b = strategy_row['protocol_b']

    # Contract addresses
    token1_contract = strategy_row.get('token1_contract', '')
    token2_contract = strategy_row.get('token2_contract', '')
    token3_contract = strategy_row.get('token3_contract', '')

    # USD values
    l_a = strategy_row.get('l_a', 0.0)
    b_a = strategy_row.get('b_a', 0.0)
    l_b = strategy_row.get('l_b', 0.0)
    b_b = strategy_row.get('b_b', 0.0)

    # Rates
    lend_rate_1a = strategy_row.get('lend_rate_1a', 0.0)
    borrow_rate_2a = strategy_row.get('borrow_rate_2a', 0.0)
    lend_rate_2b = strategy_row.get('lend_rate_2b', 0.0)
    borrow_rate_3b = strategy_row.get('borrow_rate_3b', 0.0)

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
    available_borrow_2A = strategy_row.get('available_borrow_2a')
    available_borrow_3B = strategy_row.get('available_borrow_3b')

    liquidity_details = []
    if available_borrow_2A is not None and not pd.isna(available_borrow_2A):
        constraint_2A = available_borrow_2A / b_a if b_a > 0 else float('inf')
        liquidity_details.append(f"• {token2} on {protocol_a}: ${available_borrow_2A:,.2f} available → max ${constraint_2A:,.2f}")

    if available_borrow_3B is not None and not pd.isna(available_borrow_3B):
        constraint_3B = available_borrow_3B / b_b if b_b > 0 else float('inf')
        liquidity_details.append(f"• {token3} on {protocol_b}: ${available_borrow_3B:,.2f} available → max ${constraint_3B:,.2f}")

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
            'Protocol': protocol_a,
            'Token': token1,
            'Contract': format_contract(token1_contract),
            'Action': 'Lend',
            'Rate': f"{lend_rate_1a * 100:.2f}%",
            'Weight': f"{l_a:.2f}",
            'Token Amount': f"{(l_a * deployment_usd) / P1_A:.2f}",
            'Price': f"${P1_A:.4f}",
            'Fee': '',
            'Available': ''
        },
        # Row 2: Protocol A, token2, Borrow
        {
            'Protocol': protocol_a,
            'Token': token2,
            'Contract': format_contract(token2_contract),
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_2a * 100:.2f}%",
            'Weight': f"{b_a:.2f}",
            'Token Amount': f"{(b_a * deployment_usd) / P2_A:.2f}",
            'Price': f"${P2_A:.4f}",
            'Fee': f"{borrow_fee_2A*100:.2f}%" if pd.notna(borrow_fee_2A) else 'N/A',
            'Available': format_usd_abbreviated(available_borrow_2A) if pd.notna(available_borrow_2A) else 'N/A'
        },
        # Row 3: Protocol B, token2, Lend
        {
            'Protocol': protocol_b,
            'Token': token2,
            'Contract': format_contract(token2_contract),
            'Action': 'Lend',
            'Rate': f"{lend_rate_2b * 100:.2f}%",
            'Weight': f"{l_b:.2f}",
            'Token Amount': f"{(l_b * deployment_usd) / P2_B:.2f}",
            'Price': f"${P2_B:.4f}",
            'Fee': '',
            'Available': ''
        }
    ]

    # Add 4th row (Borrow token3 from Protocol B)
    table_data.append({
        'Protocol': protocol_b,
        'Token': token3,
        'Contract': format_contract(token3_contract),
        'Action': 'Borrow',
        'Rate': f"{borrow_rate_3b * 100:.2f}%",
        'Weight': f"{b_b:.2f}",
        'Token Amount': f"{(b_b * deployment_usd) / P3_B:.2f}",
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
        #print(row)
        table_data.append({
            '_idx': idx,  # Hidden index for selection
            'Token Pair': token_pair,
            'Protocol A': row['protocol_a'],
            'Protocol B': row['protocol_b'],
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
        strategy: Strategy dict with multipliers (l_a, b_a, l_b, b_b) and net_apr
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
    lend_a_usd = strategy.get('l_a', 0.0) * deployment_usd
    borrow_a_usd = strategy.get('b_a', 0.0) * deployment_usd
    lend_b_usd = strategy.get('l_b', 0.0) * deployment_usd
    borrow_b_usd = strategy.get('b_b', 0.0) * deployment_usd

    # Percentages (for display)
    lend_a_pct = strategy.get('l_a', 0.0) * 100
    borrow_a_pct = strategy.get('b_a', 0.0) * 100
    lend_b_pct = strategy.get('l_b', 0.0) * 100
    borrow_b_pct = strategy.get('b_b', 0.0) * 100

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
            return 5
        decimal_places = math.ceil(-math.log10(price / target_usd))
        return max(5, min(8, decimal_places))

    # ========================================
    # HEADER SECTION
    # ========================================
    st.markdown(f"## 📊 {strategy['token1']} / {strategy['token2']} / {strategy['token3']}")

    # ========================================
    # APR SUMMARY TABLE
    # ========================================
    # Calculate upfront fees percentage
    upfront_fees_pct = (
        strategy.get('b_a', 0.0) * strategy.get('borrow_fee_2a', 0.0) +
        strategy.get('b_b', 0.0) * strategy.get('borrow_fee_3b', 0.0)
    )

    # Build display strings
    token_flow = f"{strategy['token1']} → {strategy['token2']} → {strategy['token3']}"
    protocol_pair = f"{strategy['protocol_a']} ↔ {strategy['protocol_b']}"

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
    entry_token_amount_1A = (strategy.get('l_a', 0.0) * deployment_usd) / strategy['P1_A'] if strategy['P1_A'] > 0 else 0
    # Token 2: Calculate using Protocol A price (source of borrowed tokens)
    # This ensures the same token quantity is used for both Protocol A and Protocol B
    entry_token_amount_2 = (strategy.get('b_a', 0.0) * deployment_usd) / strategy['P2_A'] if strategy['P2_A'] > 0 else 0
    entry_token_amount_2A = entry_token_amount_2  # Borrowed from Protocol A
    entry_token_amount_2B = entry_token_amount_2  # Same tokens lent to Protocol B
    entry_token_amount_3B = (strategy.get('b_b', 0.0) * deployment_usd) / strategy['P3_B'] if strategy['P3_B'] > 0 else 0

    # Calculate position sizes in USD (weight * deployment_usd)
    position_size_1A = strategy.get('l_a', 0.0) * deployment_usd
    position_size_2A = strategy.get('b_a', 0.0) * deployment_usd
    position_size_2B = strategy.get('l_b', 0.0) * deployment_usd
    position_size_3B = strategy.get('b_b', 0.0) * deployment_usd

    # Calculate fee amounts in USD
    fee_usd_2A = strategy.get('b_a', 0.0) * strategy.get('borrow_fee_2a', 0.0) * deployment_usd
    fee_usd_3B = strategy.get('b_b', 0.0) * strategy.get('borrow_fee_3b', 0.0) * deployment_usd

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
        lltv=strategy.get('liquidation_threshold_1a', strategy.get('collateral_ratio_1a', 0.0)),
        side='lending',
        borrow_weight=strategy.get('borrow_weight_2a', 1.0)
    )

    # Calculate liquidation data for Row 2 (borrowing side - Protocol A)
    liq_result_2 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_1A,
        loan_value=position_size_2A,
        lending_token_price=strategy['P1_A'],
        borrowing_token_price=strategy['P2_A'],
        lltv=strategy.get('liquidation_threshold_1a', strategy.get('collateral_ratio_1a', 0.0)),
        side='borrowing',
        borrow_weight=strategy.get('borrow_weight_2a', 1.0)
    )

    # Calculate liquidation data for Row 3 (lending side - Protocol B)
    liq_result_3 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_2B,
        loan_value=position_size_3B,
        lending_token_price=strategy['P2_B'],
        borrowing_token_price=strategy['P3_B'],
        lltv=strategy.get('liquidation_threshold_2b', strategy.get('collateral_ratio_2b', 0.0)),
        side='lending',
        borrow_weight=strategy.get('borrow_weight_3b', 1.0)
    )

    # Calculate liquidation data for Row 4 (borrowing side - Protocol B)
    liq_result_4 = position_calculator.calculate_liquidation_price(
        collateral_value=position_size_2B,
        loan_value=position_size_3B,
        lending_token_price=strategy['P2_B'],
        borrowing_token_price=strategy['P3_B'],
        lltv=strategy.get('liquidation_threshold_2b', strategy.get('collateral_ratio_2b', 0.0)),
        side='borrowing',
        borrow_weight=strategy.get('borrow_weight_3b', 1.0)
    )

    # Build detail table
    st.markdown("**Position Details:**")
    detail_data = []

    # Calculate effective LTV on-the-fly
    effective_ltv_1A = (strategy.get('b_a', 0.0) / strategy.get('l_a', 1.0)) * strategy.get('borrow_weight_2a', 1.0) if strategy.get('l_a', 0.0) > 0 else 0.0
    effective_ltv_2B = (strategy.get('b_b', 0.0) / strategy.get('l_b', 1.0)) * strategy.get('borrow_weight_3b', 1.0) if strategy.get('l_b', 0.0) > 0 else 0.0

    # Row 1: Protocol A - Lend token1
    lltv_1A = strategy.get('liquidation_threshold_1a', 0.0)
    detail_data.append({
        'Protocol': strategy['protocol_a'],
        'Token': strategy['token1'],
        'Action': 'Lend',
        'maxCF': f"{strategy.get('collateral_ratio_1a', 0.0):.2%}",
        'LLTV': f"{lltv_1A:.2%}" if lltv_1A > 0 else "",
        'Effective LTV': f"{effective_ltv_1A:.2%}",
        'Borrow Weight': "-",
        'Weight': f"{strategy.get('l_a', 0.0):.4f}",
        'Rate': f"{strategy.get('lend_rate_1a', 0.0) * 100:.2f}%",
        'Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}",
        'Size ($$$)': f"${position_size_1A:,.2f}",
        'Price': f"${strategy['P1_A']:.4f}",
        'Fees (%)': "",
        'Fees ($$$)': "",
        'Liquidation Price': f"${liq_result_1['liq_price']:.4f}" if liq_result_1['liq_price'] != float('inf') and liq_result_1['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_1['pct_distance'] * 100:.2f}%" if liq_result_1['liq_price'] != float('inf') and liq_result_1['liq_price'] > 0 else "N/A",
        'Max Borrow': "",
    })

    # Row 2: Protocol A - Borrow token2
    detail_data.append({
        'Protocol': strategy['protocol_a'],
        'Token': strategy['token2'],
        'Action': 'Borrow',
        'maxCF': "-",
        'LLTV': "-",
        'Effective LTV': "-",
        'Borrow Weight': f"{strategy.get('borrow_weight_2a', 1.0):.2f}x",
        'Weight': f"{strategy.get('b_a', 0.0):.4f}",
        'Rate': f"{strategy.get('borrow_rate_2a', 0.0) * 100:.2f}%",
        'Token Amount': f"{entry_token_amount_2A:,.{precision_2A}f}",
        'Size ($$$)': f"${position_size_2A:,.2f}",
        'Price': f"${strategy['P2_A']:.4f}",
        'Fees (%)': f"{strategy.get('borrow_fee_2a', 0.0) * 100:.2f}%" if strategy.get('borrow_fee_2a', 0.0) > 0 else "",
        'Fees ($$$)': f"${fee_usd_2A:.2f}" if fee_usd_2A > 0 else "",
        'Liquidation Price': f"${liq_result_2['liq_price']:.4f}" if liq_result_2['liq_price'] != float('inf') and liq_result_2['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_2['pct_distance'] * 100:.2f}%" if liq_result_2['liq_price'] != float('inf') and liq_result_2['liq_price'] > 0 else "N/A",
        'Max Borrow': f"${strategy.get('available_borrow_2a', 0.0):,.2f}" if strategy.get('available_borrow_2a', 0.0) > 0 else "",
    })

    # Row 3: Protocol B - Lend token2
    lltv_2B = strategy.get('liquidation_threshold_2b', 0.0)
    detail_data.append({
        'Protocol': strategy['protocol_b'],
        'Token': strategy['token2'],
        'Action': 'Lend',
        'maxCF': f"{strategy.get('collateral_ratio_2b', 0.0):.2%}",
        'LLTV': f"{lltv_2B:.2%}" if lltv_2B > 0 else "",
        'Effective LTV': f"{effective_ltv_2B:.2%}",
        'Borrow Weight': "-",
        'Weight': f"{strategy.get('l_b', 0.0):.4f}",
        'Rate': f"{strategy.get('lend_rate_2b', 0.0) * 100:.2f}%",
        'Token Amount': f"{entry_token_amount_2B:,.{precision_2B}f}",
        'Size ($$$)': f"${position_size_2B:,.2f}",
        'Price': f"${strategy['P2_B']:.4f}",
        'Fees (%)': "",
        'Fees ($$$)': "",
        'Liquidation Price': f"${liq_result_3['liq_price']:.4f}" if liq_result_3['liq_price'] != float('inf') and liq_result_3['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_3['pct_distance'] * 100:.2f}%" if liq_result_3['liq_price'] != float('inf') and liq_result_3['liq_price'] > 0 else "N/A",
        'Max Borrow': "",
    })

    # Row 4: Protocol B - Borrow token3
    detail_data.append({
        'Protocol': strategy['protocol_b'],
        'Token': strategy['token3'],
        'Action': 'Borrow',
        'maxCF': "-",
        'LLTV': "-",
        'Effective LTV': "-",
        'Borrow Weight': f"{strategy.get('borrow_weight_3b', 1.0):.2f}x",
        'Weight': f"{strategy.get('b_b', 0.0):.4f}",
        'Rate': f"{strategy.get('borrow_rate_3b', 0.0) * 100:.2f}%",
        'Token Amount': f"{entry_token_amount_3B:,.{precision_3B}f}",
        'Size ($$$)': f"${position_size_3B:,.2f}",
        'Price': f"${strategy['P3_B']:.4f}",
        'Fees (%)': f"{strategy.get('borrow_fee_3b', 0.0) * 100:.2f}%" if strategy.get('borrow_fee_3b', 0.0) > 0 else "",
        'Fees ($$$)': f"${fee_usd_3B:.2f}" if fee_usd_3B > 0 else "",
        'Liquidation Price': f"${liq_result_4['liq_price']:.4f}" if liq_result_4['liq_price'] != float('inf') and liq_result_4['liq_price'] > 0 else "N/A",
        'Liq Distance': f"{liq_result_4['pct_distance'] * 100:.2f}%" if liq_result_4['liq_price'] != float('inf') and liq_result_4['liq_price'] > 0 else "N/A",
        'Max Borrow': f"${strategy.get('available_borrow_3b', 0.0):,.2f}" if strategy.get('available_borrow_3b', 0.0) > 0 else "",
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
            _, l_a, b_a, l_b, b_b = get_strategy_history(
                strategy_row=strategy,
                liquidation_distance=liquidation_distance
            )

            # Build positions dict
            positions = {
                'l_a': l_a,
                'b_a': b_a,
                'l_b': l_b,
                'b_b': b_b
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
                protocol_a=strategy['protocol_a'],
                protocol_b=strategy['protocol_b'],
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
                           available_borrow: pd.DataFrame, borrow_fees: pd.DataFrame,
                           borrow_weights: pd.DataFrame, liquidation_thresholds: pd.DataFrame):
    """
    Render the Rate Tables tab

    Args:
        lend_rates, borrow_rates, collateral_ratios, prices, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds: DataFrames from data loader
    """
    # Helper to format contract address (show first 6 and last 4 chars)
    def format_contract(contract: str) -> str:
        if not contract or len(contract) < 12:
            return contract
        return f"{contract[:6]}...{contract[-4:]}"

    st.header("📈 Current Rates")

    # Row 1: Lending Rates | Borrow Rates
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

    st.markdown("---")

    # Row 2: Collateral Ratios | LLTV (Liquidation Threshold)
    col3, col4 = st.columns(2)

    col3.subheader("🔒 Collateral Ratios (Max LTV)")
    collateral_display = collateral_ratios.copy()
    if 'Contract' in collateral_display.columns:
        # Format contract addresses to be more readable
        collateral_display['Contract'] = collateral_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in collateral_display.columns if c not in ['Token', 'Contract']]
        collateral_display = collateral_display[cols]
    col3.dataframe(collateral_display, width='stretch', hide_index=True)

    col4.subheader("⚠️ LLTV (Liquidation Threshold)")
    lltv_display = liquidation_thresholds.copy()
    if 'Contract' in lltv_display.columns:
        # Format contract addresses to be more readable
        lltv_display['Contract'] = lltv_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in lltv_display.columns if c not in ['Token', 'Contract']]
        lltv_display = lltv_display[cols]
    col4.dataframe(lltv_display, width='stretch', hide_index=True)

    st.markdown("---")

    # Row 3: Borrow Weights | Borrow Fees
    col5, col6 = st.columns(2)

    col5.subheader("⚖️ Borrow Weights")
    borrow_weights_display = borrow_weights.copy()
    if 'Contract' in borrow_weights_display.columns:
        # Format contract addresses to be more readable
        borrow_weights_display['Contract'] = borrow_weights_display['Contract'].apply(format_contract)
        # Reorder columns to put Contract after Token
        cols = ['Token', 'Contract'] + [c for c in borrow_weights_display.columns if c not in ['Token', 'Contract']]
        borrow_weights_display = borrow_weights_display[cols]
    col5.dataframe(borrow_weights_display, width='stretch', hide_index=True)

    col6.subheader("💳 Borrow Fees")
    borrow_fees_display = borrow_fees.copy()
    if 'Contract' in borrow_fees_display.columns:
        borrow_fees_display = borrow_fees_display.drop(columns=['Contract'])

    for col in borrow_fees_display.columns:
        if col != 'Token':
            borrow_fees_display[col] = borrow_fees_display[col].apply(
                lambda x: f"{x*100:.2f}%" if pd.notna(x) and x > 0 else ("0.00%" if x == 0 else "N/A")
            )

    col6.dataframe(borrow_fees_display, width='stretch', hide_index=True)

    st.markdown("---")

    # Row 4: Available Borrow Liquidity | Prices
    col7, col8 = st.columns(2)

    col7.subheader("💵 Available Borrow Liquidity")
    available_borrow_display = available_borrow.copy()
    if 'Contract' in available_borrow_display.columns:
        available_borrow_display = available_borrow_display.drop(columns=['Contract'])

    for col in available_borrow_display.columns:
        if col != 'Token':
            available_borrow_display[col] = available_borrow_display[col].apply(format_usd_abbreviated)

    col7.dataframe(available_borrow_display, width='stretch', hide_index=True)

    col8.subheader("💰 Prices")
    prices_display = prices.drop(columns=['Contract']) if 'Contract' in prices.columns else prices
    col8.dataframe(prices_display, width='stretch', hide_index=True)


def render_positions_table_tab(timestamp_seconds: int):
    """
    Render simple positions table showing all active positions

    Args:
        timestamp_seconds: Dashboard-selected timestamp (Unix seconds) representing "current time"
    """
    st.header("💼 Active Positions")

    try:
        # Connect to database
        conn = get_db_connection()
        service = PositionService(conn)

        # Get active positions (filtered by selected timestamp)
        active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

        

        if active_positions.empty:
            # Provide context-aware messaging based on whether viewing historical timestamp
            from dashboard.db_utils import get_db_engine
            engine = get_db_engine()
            latest_ts_query = "SELECT MAX(timestamp) FROM rates_snapshot"
            latest_ts_result = pd.read_sql_query(latest_ts_query, engine)

            if not latest_ts_result.empty and latest_ts_result.iloc[0, 0] is not None:
                latest_ts = to_seconds(latest_ts_result.iloc[0, 0])

                if timestamp_seconds < latest_ts:
                    # Historical view with no positions
                    st.info(f"📭 No active positions at {to_datetime_str(timestamp_seconds)}. "
                           "Positions may have been deployed later, or you can view a different timestamp.")
                else:
                    # Current view with no positions
                    st.info("📭 No active positions. Deploy a strategy from the All Strategies tab to get started!")
            else:
                st.info("📭 No active positions. Deploy a strategy from the All Strategies tab to get started!")

            conn.close()
            return

        # Use dashboard-selected timestamp as "current time"
        latest_timestamp = timestamp_seconds
        latest_timestamp_str = to_datetime_str(timestamp_seconds)

        # Query all rates and prices at latest timestamp
        from dashboard.db_utils import get_db_engine
        engine = get_db_engine()
        ph = service._get_placeholder()
        rates_query = f"""
        SELECT protocol, token, lend_total_apr, borrow_total_apr, borrow_fee, price_usd
        FROM rates_snapshot
        WHERE timestamp = {ph}
        """
        rates_df = pd.read_sql_query(rates_query, engine, params=(latest_timestamp_str,))

        # Helper function to get rate
        def get_rate(token, protocol, rate_type):
            """Get lend or borrow rate for token/protocol, return 0 if not found"""
            # OPTIMIZED: O(1) dictionary lookup instead of O(n) DataFrame filtering
            key = (token, protocol)
            data = rate_lookup.get(key, {})
            return data.get(rate_type, 0.0)

        # Helper function to get borrow fee
        def get_borrow_fee(token, protocol):
            """Get borrow fee for token/protocol, return 0 if not found"""
            # OPTIMIZED: O(1) dictionary lookup instead of O(n) DataFrame filtering
            key = (token, protocol)
            data = rate_lookup.get(key, {})
            return data.get('borrow_fee', 0.0)

        # Helper function to get price
        def get_price(token, protocol):
            """Get current price for token/protocol, return 0 if not found"""
            # OPTIMIZED: O(1) dictionary lookup instead of O(n) DataFrame filtering
            key = (token, protocol)
            data = rate_lookup.get(key, {})
            return data.get('price', 0.0)

        # Helper function to calculate token amount precision
        def get_token_precision(price: float, target_usd: float = 10.0) -> int:
            """
            Calculate decimal places needed to show at least target_usd worth of precision.

            Args:
                price: Token price in USD
                target_usd: Target USD value for precision (default $10)

            Returns:
                Number of decimal places to display (minimum 5)

            Examples:
                - BTC @ $100,000 → 5 decimals (0.00010 BTC = $10)
                - ETH @ $3,000 → 5 decimals (0.00333 ETH = $10)
                - SUI @ $1 → 5 decimals (minimum)
                - DEEP @ $0.01 → 5 decimals (1.00000 DEEP = $0.01)
            """
            import math

            if price <= 0:
                return 5  # Default fallback (minimum 5)

            # Calculate: decimal_places = ceil(-log10(price / target_usd))
            decimal_places = math.ceil(-math.log10(price / target_usd))

            # Clamp between 5 and 8 (minimum 5 decimals, maximum 8)
            return max(5, min(8, decimal_places))

        def safe_float(value, default=0.0):
            """Safely convert value to float, handling bytes and other edge cases."""
            if pd.isna(value):
                return default
            if isinstance(value, bytes):
                # Try to convert bytes to int first, then to float
                try:
                    return float(int.from_bytes(value, byteorder='little'))
                except Exception:
                    return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        # OPTIMIZATION: Build rate lookup dictionary once for O(1) access
        # This replaces O(n) DataFrame filtering with O(1) dictionary lookups
        rate_lookup = {}
        for _, row in rates_df.iterrows():
            key = (row['token'], row['protocol'])
            rate_lookup[key] = {
                'lend': float(row['lend_total_apr']) if pd.notna(row['lend_total_apr']) else 0.0,
                'borrow': float(row['borrow_total_apr']) if pd.notna(row['borrow_total_apr']) else 0.0,
                'borrow_fee': float(row['borrow_fee']) if pd.notna(row['borrow_fee']) else 0.0,
                'price': float(row['price_usd']) if pd.notna(row['price_usd']) else 0.0
            }

        # Render expandable rows (Stages 1-4)
        for _, position in active_positions.iterrows():
            # Build token flow string (all positions are 4-leg levered)
            token_flow = f"{position['token1']} → {position['token2']} → {position['token3']}"

            # Build protocol pair string
            protocol_pair = f"{position['protocol_a']} ↔ {position['protocol_b']}"

            # Get current rates for all 4 legs from rates_snapshot
            lend_1A = get_rate(position['token1'], position['protocol_a'], 'lend')
            borrow_2A = get_rate(position['token2'], position['protocol_a'], 'borrow')
            lend_2B = get_rate(position['token2'], position['protocol_b'], 'lend')
            borrow_3B = get_rate(position['token3'], position['protocol_b'], 'borrow')

            # Get borrow fees
            borrow_fee_2A = get_borrow_fee(position['token2'], position['protocol_a'])
            borrow_fee_3B = get_borrow_fee(position['token3'], position['protocol_b'])

            # Safely extract position multipliers and numeric fields (handle bytes/corrupted data)
            l_a = safe_float(position['l_a'])
            b_a = safe_float(position['b_a'])
            l_b = safe_float(position['l_b'])
            b_b = safe_float(position['b_b'])
            deployment_usd = safe_float(position['deployment_usd'])

            # Safely extract entry rates
            entry_lend_rate_1a = safe_float(position['entry_lend_rate_1a'])
            entry_borrow_rate_2a = safe_float(position['entry_borrow_rate_2a'])
            entry_lend_rate_2b = safe_float(position['entry_lend_rate_2b'])
            entry_borrow_rate_3b = safe_float(position['entry_borrow_rate_3b'])

            # Safely extract entry prices
            entry_price_1a = safe_float(position['entry_price_1a'])
            entry_price_2a = safe_float(position['entry_price_2a'])
            entry_price_2b = safe_float(position['entry_price_2b'])
            entry_price_3b = safe_float(position['entry_price_3b'])

            # Calculate GROSS APR using position multipliers
            # Rates are already in decimal format (0.05 = 5%)
            gross_apr = (
                (l_a * lend_1A) +
                (l_b * lend_2B) -
                (b_a * borrow_2A) -
                (b_b * borrow_3B)
            )

            # Calculate fee cost (keep as decimal per DESIGN_NOTES.md Rule #7)
            fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B

            # Calculate NET APR (in decimal)
            current_net_apr_decimal = gross_apr - fee_cost

            # Calculate position value and realized APR
            # For historical views, only use rebalance timestamp if it's before the viewing timestamp
            if pd.notna(position.get('last_rebalance_timestamp')):
                last_rebal_ts = to_seconds(position['last_rebalance_timestamp'])
                # Only use last rebalance if it occurred before or at the viewing timestamp
                if last_rebal_ts <= latest_timestamp:
                    start_ts = last_rebal_ts
                else:
                    # Rebalance is in the "future" for this historical view
                    # Calculate from entry instead
                    start_ts = to_seconds(position['entry_timestamp'])
            else:
                start_ts = to_seconds(position['entry_timestamp'])
            pv_result = service.calculate_position_value(position, start_ts, latest_timestamp)

            # Display data quality info if rates were forward-filled
            if pv_result.get('has_forward_filled_data', False):
                filled_count = pv_result['forward_filled_count']
                st.info(f"""
ℹ️ **Forward-filled rates**: {filled_count} period(s) used forward-filled rates.

When a rate was missing, the previous valid rate was carried forward (following forward-looking rate logic).
                """)

                # Expandable details
                with st.expander("View forward-filled periods"):
                    filled_log = pv_result.get('forward_filled_log', [])
                    if filled_log:
                        filled_df = pd.DataFrame(filled_log)
                        st.dataframe(filled_df, width="stretch")
                    else:
                        st.write("No details available")

            # STAGE 1: Build summary title for expander
            # Calculate strategy-level metrics for title (from entry to current)
            # Calculate days from entry to current timestamp
            entry_ts = to_seconds(position['entry_timestamp'])
            strategy_days = (latest_timestamp - entry_ts) / 86400

            # For title: We need to calculate strategy_pnl from strategy summary
            # This requires calculating all segments. We'll do a simplified calculation here.
            # Calculate from ENTRY to CURRENT (not from last rebalance)
            strategy_pv_result = service.calculate_position_value(position, entry_ts, latest_timestamp)
            strategy_total_pnl = strategy_pv_result['net_earnings']

            # Calculate strategy value: deployment + total PnL
            strategy_value = deployment_usd + strategy_total_pnl

            # Calculate Net APR from strategy start
            if strategy_days > 0 and deployment_usd > 0:
                # Net APR = (Total PnL / deployment) * (365 / days)
                strategy_net_apr = (strategy_total_pnl / deployment_usd) * (365 / strategy_days)
            else:
                strategy_net_apr = 0.0

            title = f"▶ {to_datetime_str(position['entry_timestamp'])} | {token_flow} | {protocol_pair} | Entry {position['entry_net_apr'] * 100:.2f}% | Current {current_net_apr_decimal * 100:.2f}% | Net APR {strategy_net_apr * 100:.2f}% | Value ${strategy_value:,.2f}"

            # STAGE 2-3: Build detail table inside expander
            with st.expander(title, expanded=False):
                # Detail table (4 legs breakdown)
                detail_data = []

                # Calculate entry token amounts (Stage 3) with zero-division protection
                entry_token_amount_1A = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
                # Token 2: Calculate using Protocol A price (source of borrowed tokens)
                # This ensures the same token quantity is used for both Protocol A and Protocol B
                entry_token_amount_2 = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
                entry_token_amount_2A = entry_token_amount_2  # Borrowed from Protocol A
                entry_token_amount_2B = entry_token_amount_2  # Same tokens lent to Protocol B
                entry_token_amount_3B = (b_b * deployment_usd) / entry_price_3b if entry_price_3b > 0 else 0

                # STAGE 4: Get live prices for all tokens
                live_price_1A = get_price(position['token1'], position['protocol_a'])
                live_price_2A = get_price(position['token2'], position['protocol_a'])
                live_price_2B = get_price(position['token2'], position['protocol_b'])
                live_price_3B = get_price(position['token3'], position['protocol_b'])

                # Calculate dynamic precision for token amounts (based on live prices)
                precision_1A = get_token_precision(live_price_1A)
                precision_2A = get_token_precision(live_price_2A)
                precision_2B = get_token_precision(live_price_2B)
                precision_3B = get_token_precision(live_price_3B)

                # Calculate dynamic precision for token amounts
                # Stablecoins always get 6 decimal places, others use price-based calculation
                precision_1A = 6 if position['token1'] in STABLECOIN_SYMBOLS else get_token_precision(live_price_1A)
                precision_2A = 6 if position['token2'] in STABLECOIN_SYMBOLS else get_token_precision(live_price_2A)
                precision_2B = 6 if position['token2'] in STABLECOIN_SYMBOLS else get_token_precision(live_price_2B)
                precision_3B = 6 if position['token3'] in STABLECOIN_SYMBOLS else get_token_precision(live_price_3B)

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

                # Check if this is a legacy position (created before LLTV system upgrade)
                is_legacy_position = (position.get('entry_liquidation_threshold_1a', 0) == 0 or
                                     position.get('entry_liquidation_threshold_2b', 0) == 0)

                if is_legacy_position:
                    # Legacy position - show warning and use collateral ratios for calculations
                    st.warning("⚠️ **Legacy Position**: This position was created before the LLTV system upgrade (Jan 2026). "
                             "Liquidation calculations use collateral ratios instead of liquidation thresholds and may be less accurate. "
                             "Consider closing and redeploying for full accuracy.")

                    # For legacy positions, use collateral ratios as fallback for LLTV
                    # and set borrow weights to 1.0 (default)
                    lltv_1A = position['entry_collateral_ratio_1a']
                    lltv_2B = position['entry_collateral_ratio_2b']
                    borrow_weight_2A = 1.0
                    borrow_weight_3B = 1.0
                else:
                    # New position with proper LLTV values
                    lltv_1A = position['entry_liquidation_threshold_1a']
                    lltv_2B = position['entry_liquidation_threshold_2b']
                    borrow_weight_2A = position.get('entry_borrow_weight_2a', 1.0)
                    borrow_weight_3B = position.get('entry_borrow_weight_3b', 1.0)

                # Calculate target weights using PositionCalculator with entry liquidation distance
                target_calc = PositionCalculator(liquidation_distance=position['entry_liquidation_distance'])
                target_positions = target_calc.calculate_positions(
                    liquidation_threshold_a=lltv_1A,
                    liquidation_threshold_b=lltv_2B,
                    collateral_ratio_a=position['entry_collateral_ratio_1a'],
                    collateral_ratio_b=position['entry_collateral_ratio_2b'],
                    borrow_weight_a=borrow_weight_2A,
                    borrow_weight_b=borrow_weight_3B
                )

                # Calculate CURRENT token amounts using TARGET weights and LIVE prices
                # This shows what the position SHOULD be at current market conditions
                current_token_amount_1A = (target_positions['l_a'] * deployment_usd) / live_price_1A if live_price_1A > 0 else 0
                # Token 2: Calculate using Protocol A price and TARGET weight
                # This ensures the same token quantity is used for both Protocol A and Protocol B
                current_token_amount_2 = (target_positions['b_a'] * deployment_usd) / live_price_2A if live_price_2A > 0 else 0
                current_token_amount_2A = current_token_amount_2  # Borrowed from Protocol A
                current_token_amount_2B = current_token_amount_2  # Same tokens lent to Protocol B
                current_token_amount_3B = (target_positions['b_b'] * deployment_usd) / live_price_3B if live_price_3B > 0 else 0

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
                    lltv=lltv_1A,
                    side='lending',
                    borrow_weight=borrow_weight_2A
                )

                # Leg 2: Liquidation price for token2 (borrowing side - price must rise)
                liq_2A = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_A,
                    loan_value=current_loan_A,
                    lending_token_price=live_price_1A,
                    borrowing_token_price=live_price_2A,
                    lltv=lltv_1A,
                    side='borrowing',
                    borrow_weight=borrow_weight_2A
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
                    lltv=lltv_2B,
                    side='lending',
                    borrow_weight=borrow_weight_3B
                )

                # Leg 4: Liquidation price for token3 (borrowing side - price must rise)
                liq_3B = calc.calculate_liquidation_price(
                    collateral_value=current_collateral_B,
                    loan_value=current_loan_B,
                    lending_token_price=live_price_2B,
                    borrowing_token_price=live_price_3B,
                    lltv=lltv_2B,
                    side='borrowing',
                    borrow_weight=borrow_weight_3B
                )

                # Calculate entry liquidation distances (using entry prices instead of live prices)
                # Protocol A (using entry collateral and loan values)
                entry_collateral_A = entry_token_amount_1A * position['entry_price_1a']
                entry_loan_A = entry_token_amount_2A * position['entry_price_2a']

                entry_liq_1A = calc.calculate_liquidation_price(
                    collateral_value=entry_collateral_A,
                    loan_value=entry_loan_A,
                    lending_token_price=position['entry_price_1a'],
                    borrowing_token_price=position['entry_price_2a'],
                    lltv=lltv_1A,
                    side='lending',
                    borrow_weight=borrow_weight_2A
                )

                entry_liq_2A = calc.calculate_liquidation_price(
                    collateral_value=entry_collateral_A,
                    loan_value=entry_loan_A,
                    lending_token_price=position['entry_price_1a'],
                    borrowing_token_price=position['entry_price_2a'],
                    lltv=lltv_1A,
                    side='borrowing',
                    borrow_weight=borrow_weight_2A
                )

                # Protocol B (using entry collateral and loan values)
                entry_collateral_B = entry_token_amount_2B * position['entry_price_2b']
                entry_loan_B = entry_token_amount_3B * position['entry_price_3b']

                entry_liq_2B = calc.calculate_liquidation_price(
                    collateral_value=entry_collateral_B,
                    loan_value=entry_loan_B,
                    lending_token_price=position['entry_price_2b'],
                    borrowing_token_price=position['entry_price_3b'],
                    lltv=lltv_2B,
                    side='lending',
                    borrow_weight=borrow_weight_3B
                )

                entry_liq_3B = calc.calculate_liquidation_price(
                    collateral_value=entry_collateral_B,
                    loan_value=entry_loan_B,
                    lending_token_price=position['entry_price_2b'],
                    borrowing_token_price=position['entry_price_3b'],
                    lltv=lltv_2B,
                    side='borrowing',
                    borrow_weight=borrow_weight_3B
                )

                # Helper function to format token rebalance display
                def format_token_rebalance(rebalance_amount: float, action: str, precision: int) -> str:
                    """
                    Format token rebalance display based on action type.

                    Args:
                        rebalance_amount: current_token_amount - entry_token_amount
                        action: 'Lend' or 'Borrow'
                        precision: Decimal places for token amount

                    Returns:
                        Formatted string with action and amount
                    """
                    abs_amount = abs(rebalance_amount)

                    if action == 'Lend':
                        if rebalance_amount > 0:
                            return f"Add {abs_amount:,.{precision}f}"
                        elif rebalance_amount < 0:
                            return f"Withdraw {abs_amount:,.{precision}f}"
                        else:
                            return "No change"
                    else:  # action == 'Borrow'
                        if rebalance_amount > 0:
                            return f"Borrow {abs_amount:,.{precision}f}"
                        elif rebalance_amount < 0:
                            return f"Repay {abs_amount:,.{precision}f}"
                        else:
                            return "No change"

                # Calculate token rebalance amounts for all legs
                token_rebalance_1A = current_token_amount_1A - entry_token_amount_1A
                token_rebalance_2A = current_token_amount_2A - entry_token_amount_2A
                token_rebalance_2B = current_token_amount_2B - entry_token_amount_2B
                token_rebalance_3B = current_token_amount_3B - entry_token_amount_3B

                # Calculate rebalance size in USD for all legs
                rebalance_usd_1A = token_rebalance_1A * live_price_1A
                rebalance_usd_2A = token_rebalance_2A * live_price_2A
                rebalance_usd_2B = token_rebalance_2B * live_price_2B
                rebalance_usd_3B = token_rebalance_3B * live_price_3B

                # Calculate rebalanced token amounts (only token2 changes - rows 2 and 3)
                rebalanced_token_amount_1A = entry_token_amount_1A  # No change
                rebalanced_token_amount_2A = entry_token_amount_2A + token_rebalance_2A  # Changed
                rebalanced_token_amount_2B = entry_token_amount_2B + token_rebalance_2B  # Changed
                rebalanced_token_amount_3B = entry_token_amount_3B  # No change

                # Calculate rebalanced collateral and loan values
                # Protocol A (with rebalanced token2 borrow amount)
                rebalanced_collateral_A = rebalanced_token_amount_1A * live_price_1A
                rebalanced_loan_A = rebalanced_token_amount_2A * live_price_2A

                # Protocol B (with rebalanced token2 lend amount)
                rebalanced_collateral_B = rebalanced_token_amount_2B * live_price_2B
                rebalanced_loan_B = rebalanced_token_amount_3B * live_price_3B

                # Calculate rebalanced liquidation distances for all 4 legs
                # Leg 1: Protocol A - Lend token1 (lending side)
                rebalanced_liq_1A = calc.calculate_liquidation_price(
                    collateral_value=rebalanced_collateral_A,
                    loan_value=rebalanced_loan_A,
                    lending_token_price=live_price_1A,
                    borrowing_token_price=live_price_2A,
                    lltv=position.get('entry_liquidation_threshold_1a', position['entry_collateral_ratio_1a']),
                    side='lending',
                    borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
                )

                # Leg 2: Protocol A - Borrow token2 (borrowing side)
                rebalanced_liq_2A = calc.calculate_liquidation_price(
                    collateral_value=rebalanced_collateral_A,
                    loan_value=rebalanced_loan_A,
                    lending_token_price=live_price_1A,
                    borrowing_token_price=live_price_2A,
                    lltv=position.get('entry_liquidation_threshold_1a', position['entry_collateral_ratio_1a']),
                    side='borrowing',
                    borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
                )

                # Leg 3: Protocol B - Lend token2 (lending side)
                rebalanced_liq_2B = calc.calculate_liquidation_price(
                    collateral_value=rebalanced_collateral_B,
                    loan_value=rebalanced_loan_B,
                    lending_token_price=live_price_2B,
                    borrowing_token_price=live_price_3B,
                    lltv=position.get('entry_liquidation_threshold_2b', position['entry_collateral_ratio_2b']),
                    side='lending',
                    borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
                )

                # Leg 4: Protocol B - Borrow token3 (borrowing side)
                rebalanced_liq_3B = calc.calculate_liquidation_price(
                    collateral_value=rebalanced_collateral_B,
                    loan_value=rebalanced_loan_B,
                    lending_token_price=live_price_2B,
                    borrowing_token_price=live_price_3B,
                    lltv=position.get('entry_liquidation_threshold_2b', position['entry_collateral_ratio_2b']),
                    side='borrowing',
                    borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
                )

                # Helper function to format rebalance size in USD
                def format_rebalance_usd(rebalance_usd: float, action: str) -> str:
                    """
                    Format rebalance size in USD based on action type.

                    Args:
                        rebalance_usd: token_rebalance × live_price
                        action: 'Lend' or 'Borrow'

                    Returns:
                        Formatted string with action prefix and USD amount
                    """
                    abs_amount = abs(rebalance_usd)

                    if action == 'Lend':
                        if rebalance_usd > 0:
                            return f"Add ${abs_amount:,.2f}"
                        elif rebalance_usd < 0:
                            return f"Withdraw ${abs_amount:,.2f}"
                        else:
                            return "$0.00"
                    else:  # action == 'Borrow'
                        if rebalance_usd > 0:
                            return f"Borrow ${abs_amount:,.2f}"
                        elif rebalance_usd < 0:
                            return f"Repay ${abs_amount:,.2f}"
                        else:
                            return "$0.00"

                # Check if position has been rebalanced and get last rebalance if exists
                last_rebalance = None
                has_rebalances = position.get('rebalance_count', 0) > 0
                if has_rebalances:
                    rebalances_temp = service.get_rebalance_history(position['position_id'])
                    if not rebalances_temp.empty:
                        last_rebalance = rebalances_temp.iloc[-1]  # Get the last rebalance

                # Calculate base and reward earnings for all legs
                # For rebalanced positions, use last_rebalance_timestamp as start (current segment only)
                # For non-rebalanced positions, use entry_timestamp
                if pd.notna(position.get('last_rebalance_timestamp')):
                    segment_start_ts = to_seconds(position['last_rebalance_timestamp'])
                else:
                    segment_start_ts = to_seconds(position['entry_timestamp'])
                live_ts = timestamp_seconds

                # Calculate for all 4 legs
                try:
                    base_1A, reward_1A = service.calculate_leg_earnings_split(position, '1a', 'Lend', segment_start_ts, live_ts)
                    base_2A, reward_2A = service.calculate_leg_earnings_split(position, '2a', 'Borrow', segment_start_ts, live_ts)
                    base_2B, reward_2B = service.calculate_leg_earnings_split(position, '2b', 'Lend', segment_start_ts, live_ts)
                    base_3B, reward_3B = service.calculate_leg_earnings_split(position, '3b', 'Borrow', segment_start_ts, live_ts)
                except Exception as e:
                    # Fallback to zeros if calculation fails
                    base_1A, reward_1A = 0.0, 0.0
                    base_2A, reward_2A = 0.0, 0.0
                    base_2B, reward_2B = 0.0, 0.0
                    base_3B, reward_3B = 0.0, 0.0

                # Row 1: Protocol A - Lend token1
                detail_data.append({
                    'Protocol': position['protocol_a'],
                    'Token': position['token1'],
                    'Action': 'Lend',
                    'Weight': f"{l_a:.4f}",
                    'Entry Rate': f"{entry_lend_rate_1a * 100:.2f}%",
                    'Live Rate': f"{lend_1A * 100:.2f}%",
                    'Entry Price': f"${entry_price_1a:.4f}",
                    'Live Price': f"${live_price_1A:.4f}",
                    'Liquidation Price': format_liq_price(liq_1A),
                    'Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}",
                    'Token Rebalance': format_token_rebalance(token_rebalance_1A, 'Lend', precision_1A),
                    'Lend/Borrow Base $$$': f"${base_1A:,.2f}",
                    'Reward $$$': f"${reward_1A:,.2f}",
                    'Rebalance Size $$$': format_rebalance_usd(rebalance_usd_1A, 'Lend'),
                    'Entry Liq Dist': format_liq_distance(entry_liq_1A),
                    'Live Liq Dist': format_liq_distance(liq_1A),
                    'Rebalance Liq Dist': format_liq_distance(rebalanced_liq_1A),
                    'Fee Rate': '',  # NEW: No fee for Lend
                })

                # Calculate fees for leg 2a (delta if rebalanced, full if first segment)
                if borrow_fee_2A > 0:
                    if last_rebalance is not None:
                        # Delta fees: only on ADDITIONAL borrowing since last rebalance
                        prev_borrow_2A = last_rebalance['entry_token_amount_2a']
                        delta_borrow_2A = entry_token_amount_2A - prev_borrow_2A
                        if delta_borrow_2A > 0:
                            fees_2A = borrow_fee_2A * delta_borrow_2A * entry_price_2a
                        else:
                            fees_2A = 0.0  # Repayment or no change - no fees
                    else:
                        # First segment - full entry fees
                        fees_2A = borrow_fee_2A * entry_token_amount_2A * entry_price_2a
                else:
                    fees_2A = 0.0

                # Row 2: Protocol A - Borrow token2
                detail_data.append({
                    'Protocol': position['protocol_a'],
                    'Token': position['token2'],
                    'Action': 'Borrow',
                    'Weight': f"{b_a:.4f}",
                    'Entry Rate': f"{entry_borrow_rate_2a * 100:.2f}%",
                    'Live Rate': f"{borrow_2A * 100:.2f}%",
                    'Entry Price': f"${entry_price_2a:.4f}",
                    'Live Price': f"${live_price_2A:.4f}",
                    'Liquidation Price': format_liq_price(liq_2A),
                    'Token Amount': f"{entry_token_amount_2A:,.{precision_2A}f}",
                    'Token Rebalance': format_token_rebalance(token_rebalance_2A, 'Borrow', precision_2A),
                    'Lend/Borrow Base $$$': f"${base_2A:,.2f}",
                    'Reward $$$': f"${reward_2A:,.2f}",
                    'Rebalance Size $$$': format_rebalance_usd(rebalance_usd_2A, 'Borrow'),
                    'Entry Liq Dist': format_liq_distance(entry_liq_2A),
                    'Live Liq Dist': format_liq_distance(liq_2A),
                    'Rebalance Liq Dist': format_liq_distance(rebalanced_liq_2A),
                    'Fee Rate': f"{borrow_fee_2A * 100:.2f}%" if borrow_fee_2A > 0 else '',
                })

                # Row 3: Protocol B - Lend token2
                detail_data.append({
                    'Protocol': position['protocol_b'],
                    'Token': position['token2'],
                    'Action': 'Lend',
                    'Weight': f"{l_b:.4f}",
                    'Entry Rate': f"{entry_lend_rate_2b * 100:.2f}%",
                    'Live Rate': f"{lend_2B * 100:.2f}%",
                    'Entry Price': f"${entry_price_2b:.4f}",
                    'Live Price': f"${live_price_2B:.4f}",
                    'Liquidation Price': format_liq_price(liq_2B),
                    'Token Amount': f"{entry_token_amount_2B:,.{precision_2B}f}",
                    'Token Rebalance': format_token_rebalance(token_rebalance_2B, 'Lend', precision_2B),
                    'Lend/Borrow Base $$$': f"${base_2B:,.2f}",
                    'Reward $$$': f"${reward_2B:,.2f}",
                    'Rebalance Size $$$': format_rebalance_usd(rebalance_usd_2B, 'Lend'),
                    'Entry Liq Dist': format_liq_distance(entry_liq_2B),
                    'Live Liq Dist': format_liq_distance(liq_2B),
                    'Rebalance Liq Dist': format_liq_distance(rebalanced_liq_2B),
                    'Fee Rate': '',  # NEW: No fee for Lend
                })

                # Calculate fees for leg 3b (delta if rebalanced, full if first segment)
                if borrow_fee_3B > 0:
                    if last_rebalance is not None:
                        # Delta fees: only on ADDITIONAL borrowing since last rebalance
                        prev_borrow_3B = last_rebalance['entry_token_amount_3B']
                        delta_borrow_3B = entry_token_amount_3B - prev_borrow_3B
                        if delta_borrow_3B > 0:
                            fees_3B = borrow_fee_3B * delta_borrow_3B * entry_price_3b
                        else:
                            fees_3B = 0.0  # Repayment or no change - no fees
                    else:
                        # First segment - full entry fees
                        fees_3B = borrow_fee_3B * entry_token_amount_3B * entry_price_3b
                else:
                    fees_3B = 0.0

                # Row 4: Protocol B - Borrow token3 (4th leg)
                detail_data.append({
                    'Protocol': position['protocol_b'],
                    'Token': position['token3'],
                    'Action': 'Borrow',
                    'Weight': f"{b_b:.4f}",
                    'Entry Rate': f"{entry_borrow_rate_3b * 100:.2f}%",
                    'Live Rate': f"{borrow_3B * 100:.2f}%",
                    'Entry Price': f"${entry_price_3b:.4f}",
                    'Live Price': f"${live_price_3B:.4f}",
                    'Liquidation Price': format_liq_price(liq_3B),
                    'Token Amount': f"{entry_token_amount_3B:,.{precision_3B}f}",
                    'Token Rebalance': format_token_rebalance(token_rebalance_3B, 'Borrow', precision_3B),
                    'Lend/Borrow Base $$$': f"${base_3B:,.2f}",
                    'Reward $$$': f"${reward_3B:,.2f}",
                    'Rebalance Size $$$': format_rebalance_usd(rebalance_usd_3B, 'Borrow'),
                    'Entry Liq Dist': format_liq_distance(entry_liq_3B),
                    'Live Liq Dist': format_liq_distance(liq_3B),
                    'Rebalance Liq Dist': format_liq_distance(rebalanced_liq_3B),
                    'Fee Rate': f"{borrow_fee_3B * 100:.2f}%" if borrow_fee_3B > 0 else '',
                })

                # Calculate Strategy Summary (sum of all segments: rebalanced + live)
                # Live segment totals - separate lend/borrow, then combine
                live_base_lend = base_1A + base_2B  # lend legs (1a, 2b)
                live_base_borrow = base_2A + base_3B  # borrow legs (2a, 3b)
                live_base_earnings = live_base_lend - live_base_borrow  # earnings - costs
                live_reward_earnings = reward_1A + reward_2A + reward_2B + reward_3B
                live_fees = fees_2A + fees_3B
                live_total_earnings = live_base_earnings + live_reward_earnings
                live_pnl = live_total_earnings - live_fees

                # Sum rebalanced segments
                rebalanced_pnl = 0.0
                rebalanced_total_earnings = 0.0
                rebalanced_base_earnings = 0.0
                rebalanced_reward_earnings = 0.0
                rebalanced_fees = 0.0

                if has_rebalances:
                    # Iterate through all rebalance segments
                    for idx, rebal in rebalances_temp.iterrows():
                        # For each rebalance, we need to calculate its segment summary
                        # We'll need to query the base/reward earnings for each leg in that segment
                        # However, we already have these calculated when rendering rebalance history
                        # For now, we can use the stored database values as an approximation
                        # TODO: In future, we should store per-leg base/reward earnings in the database

                        # Calculate segment summary using SAME logic as Segment Summary display
                        # Get the segment boundaries
                        opening_ts_rebal = to_seconds(rebal['opening_timestamp'])
                        closing_ts_rebal = to_seconds(rebal['closing_timestamp'])

                        # Create position-like object for this rebalance
                        rebal_as_pos = pd.Series({
                            'deployment_usd': rebal['deployment_usd'],
                            'l_a': rebal['l_a'], 'b_a': rebal['b_a'],
                            'l_b': rebal['l_b'], 'b_b': rebal['b_b'],
                            'token1': position['token1'], 'token2': position['token2'], 'token3': position['token3'],
                            'token1_contract': position['token1_contract'],
                            'token2_contract': position['token2_contract'],
                            'token3_contract': position['token3_contract'],
                            'protocol_a': position['protocol_a'], 'protocol_b': position['protocol_b']
                        })

                        # Calculate base/reward earnings for all 4 legs
                        try:
                            rebal_base_1A, rebal_reward_1A = service.calculate_leg_earnings_split(rebal_as_pos, '1a', 'Lend', opening_ts_rebal, closing_ts_rebal)
                            rebal_base_2A, rebal_reward_2A = service.calculate_leg_earnings_split(rebal_as_pos, '2a', 'Borrow', opening_ts_rebal, closing_ts_rebal)
                            rebal_base_2B, rebal_reward_2B = service.calculate_leg_earnings_split(rebal_as_pos, '2b', 'Lend', opening_ts_rebal, closing_ts_rebal)
                            rebal_base_3B, rebal_reward_3B = service.calculate_leg_earnings_split(rebal_as_pos, '3b', 'Borrow', opening_ts_rebal, closing_ts_rebal)

                            # Calculate segment summary values (same logic as Segment Summary)
                            # Separate lend and borrow, then combine
                            segment_base_lend = rebal_base_1A + rebal_base_2B  # lend legs
                            segment_base_borrow = rebal_base_2A + rebal_base_3B  # borrow legs
                            segment_base = segment_base_lend - segment_base_borrow  # earnings - costs
                            # Rewards are all positive, just sum
                            segment_reward = rebal_reward_1A + rebal_reward_2A + rebal_reward_2B + rebal_reward_3B

                            # Calculate fees for this segment (same logic as Segment Summary)
                            segment_fees = 0.0
                            # Get previous rebalance for delta fee calculation
                            prev_rebal = None
                            if idx > 0:
                                prev_rebal = rebalances_temp.iloc[idx - 1]

                            # Leg 2a fees (borrow)
                            borrow_fee_2A_seg = position.get('entry_borrow_fee_2a', 0) or 0
                            if borrow_fee_2A_seg > 0:
                                if prev_rebal is not None:
                                    delta_borrow_2A = rebal['entry_token_amount_2a'] - prev_rebal['entry_token_amount_2a']
                                    if delta_borrow_2A > 0:
                                        segment_fees += borrow_fee_2A_seg * delta_borrow_2A * rebal['opening_price_2a']
                                else:
                                    segment_fees += borrow_fee_2A_seg * rebal['entry_token_amount_2a'] * rebal['opening_price_2a']

                            # Leg 3b fees (borrow)
                            borrow_fee_3B_seg = position.get('entry_borrow_fee_3b', 0) or 0
                            if borrow_fee_3B_seg > 0:
                                if prev_rebal is not None:
                                    delta_borrow_3B = rebal['entry_token_amount_3b'] - prev_rebal['entry_token_amount_3b']
                                    if delta_borrow_3B > 0:
                                        segment_fees += borrow_fee_3B_seg * delta_borrow_3B * rebal['opening_price_3b']
                                else:
                                    segment_fees += borrow_fee_3B_seg * rebal['entry_token_amount_3b'] * rebal['opening_price_3b']

                            # Segment totals (same as Segment Summary display)
                            segment_total_earnings = segment_base + segment_reward
                            segment_pnl = segment_total_earnings - segment_fees

                            # Accumulate
                            rebalanced_base_earnings += segment_base
                            rebalanced_reward_earnings += segment_reward
                            rebalanced_fees += segment_fees
                            rebalanced_total_earnings += segment_total_earnings
                            rebalanced_pnl += segment_pnl
                        except Exception as e:
                            # If calculation fails, skip this segment
                            pass

                # Strategy totals (Real + Unreal)
                strategy_pnl = live_pnl + rebalanced_pnl
                strategy_total_earnings = live_total_earnings + rebalanced_total_earnings
                strategy_base_earnings = live_base_earnings + rebalanced_base_earnings
                strategy_reward_earnings = live_reward_earnings + rebalanced_reward_earnings
                strategy_fees = live_fees + rebalanced_fees

                # Display Strategy Summary
                st.markdown("**Strategy Summary (Real + Unreal)**")
                deployment = position['deployment_usd']

                # GUARD: Check for zero deployment
                if deployment > 0:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        strategy_pnl_pct = (strategy_pnl / deployment) * 100
                        st.metric("Total PnL", f"${strategy_pnl:,.2f} ({strategy_pnl_pct:.2f}%)")
                    with col2:
                        strategy_earnings_pct = (strategy_total_earnings / deployment) * 100
                        st.metric("Total Earnings", f"${strategy_total_earnings:,.2f} ({strategy_earnings_pct:.2f}%)")
                    with col3:
                        strategy_base_pct = (strategy_base_earnings / deployment) * 100
                        st.metric("Base Earnings", f"${strategy_base_earnings:,.2f} ({strategy_base_pct:.2f}%)")
                    with col4:
                        strategy_reward_pct = (strategy_reward_earnings / deployment) * 100
                        st.metric("Reward Earnings", f"${strategy_reward_earnings:,.2f} ({strategy_reward_pct:.2f}%)")
                    with col5:
                        strategy_fees_pct = (strategy_fees / deployment) * 100
                        st.metric("Fees", f"${strategy_fees:,.2f} ({strategy_fees_pct:.2f}%)")
                else:
                    st.warning("Invalid deployment amount - cannot calculate percentages")

                st.markdown("---")

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

                def color_rebalance(val):
                    """Color rebalance actions: Add/Repay green, Withdraw/Borrow red"""
                    if isinstance(val, str):
                        if 'Add' in val or 'Repay' in val:
                            return 'color: green'
                        elif 'Withdraw' in val or 'Borrow' in val:
                            return 'color: red'
                    return ''

                # Apply styling to rates and liquidation columns
                styled_detail_df = detail_df.style.map(
                    color_rate,
                    subset=['Entry Rate', 'Live Rate']
                ).map(
                    color_liq_price,
                    subset=['Liquidation Price']
                ).map(
                    color_liq_distance,
                    subset=['Entry Liq Dist']
                ).map(
                    color_liq_distance,
                    subset=['Live Liq Dist']
                ).map(
                    color_liq_distance,
                    subset=['Rebalance Liq Dist']
                ).map(
                    color_rebalance,
                    subset=['Token Rebalance']
                ).map(
                    color_rebalance,
                    subset=['Rebalance Size $$$']
                )

                st.dataframe(styled_detail_df, width='stretch', hide_index=True)

                # Live Position Summary
                st.markdown("**Live Position Summary**")

                # Calculate summary values from token table
                # Separate lend and borrow for base, then combine: earnings - costs
                base_lend = base_1A + base_2B  # lend legs (1a, 2b)
                base_borrow = base_2A + base_3B  # borrow legs (2a, 3b)
                total_base_earnings = base_lend - base_borrow  # earnings - costs
                # Rewards are all positive, just sum
                total_reward_earnings = reward_1A + reward_2A + reward_2B + reward_3B
                total_fees = fees_2A + fees_3B
                total_earnings = total_base_earnings + total_reward_earnings
                realised_pnl = total_earnings - total_fees

                # Get deployment for percentage calculation
                deployment = position['deployment_usd']

                # GUARD: Check for zero deployment
                if deployment > 0:
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        pnl_pct = (realised_pnl / deployment) * 100
                        st.metric("Realised PnL", f"${realised_pnl:,.2f} ({pnl_pct:.2f}%)")
                    with col2:
                        earnings_pct = (total_earnings / deployment) * 100
                        st.metric("Total Earnings", f"${total_earnings:,.2f} ({earnings_pct:.2f}%)")
                    with col3:
                        base_pct = (total_base_earnings / deployment) * 100
                        st.metric("Base Earnings", f"${total_base_earnings:,.2f} ({base_pct:.2f}%)")
                    with col4:
                        reward_pct = (total_reward_earnings / deployment) * 100
                        st.metric("Reward Earnings", f"${total_reward_earnings:,.2f} ({reward_pct:.2f}%)")
                    with col5:
                        fees_pct = (total_fees / deployment) * 100
                        st.metric("Fees", f"${total_fees:,.2f} ({fees_pct:.2f}%)")
                else:
                    st.warning("Invalid deployment amount - cannot calculate percentages")

                # Add separator
                st.markdown("---")

                # Check if there's a pending action for THIS position
                has_pending_rebalance = ('pending_rebalance' in st.session_state and
                                        st.session_state.pending_rebalance.get('position_id') == position['position_id'])
                has_pending_close = ('pending_close' in st.session_state and
                                    st.session_state.pending_close.get('position_id') == position['position_id'])

                # Check if viewing a historical timestamp with future rebalances
                has_future_rebalances = service.has_future_rebalances(
                    position['position_id'],
                    latest_timestamp
                )

                # Only show buttons if NO pending action for this position
                if not has_pending_rebalance and not has_pending_close:
                    # Buttons for rebalance and close
                    col1, col2 = st.columns(2)

                    with col1:
                        # Show warning if time-traveling with future rebalances
                        if has_future_rebalances:
                            st.button(
                                "🔄 Rebalance Position",
                                key=f"rebalance_{position['position_id']}",
                                disabled=True,
                                use_container_width=True
                            )
                            st.caption("⏰ Cannot rebalance: You are viewing a historical timestamp, "
                                     "and this position was already rebalanced in the future. "
                                     "Time-traveling rebalances would break the universe! 🌌")
                        else:
                            if st.button(
                                "🔄 Rebalance Position",
                                key=f"rebalance_{position['position_id']}",
                                help="Snapshot current PnL and adjust token2 amounts to restore liquidation distance to target",
                                use_container_width=True
                            ):
                                st.session_state.pending_rebalance = {
                                    'position_id': position['position_id'],
                                    'timestamp': latest_timestamp
                                }
                                st.rerun()

                    with col2:
                        if st.button(
                            "❌ Close Position",
                            key=f"close_{position['position_id']}",
                            help="Close position and realize all PnL",
                            use_container_width=True
                        ):
                            st.session_state.pending_close = {
                                'position_id': position['position_id'],
                                'timestamp': latest_timestamp
                            }
                            st.rerun()

                # Check for pending rebalance confirmation (only for this specific position)
                if has_pending_rebalance:
                    pending = st.session_state.pending_rebalance
                    st.warning("⚠️ Confirm Rebalance")
                    st.write("This will:")
                    st.write("1. Snapshot current position state and realised PnL (all 4 legs)")
                    st.write("2. Adjust token2 amounts to restore $$$ balance to target weightings")
                    st.write("3. Add rebalance record to history")
                    st.write("4. Move token2 between Protocol A (borrow) and Protocol B (lend)")
                    st.write("")
                    st.info("Note: Weightings (l_a, b_a, l_b, b_b) remain constant. Only token amounts adjust.")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Confirm Rebalance", key=f"confirm_rebalance_{position['position_id']}"):
                            # Double-check for time-travel paradox before executing
                            if service.has_future_rebalances(pending['position_id'], pending['timestamp']):
                                st.error("❌ Cannot rebalance: This position has already been rebalanced in the future. "
                                        "Time-traveling rebalances would break the universe! 🌌")
                                del st.session_state.pending_rebalance
                                st.session_state.skip_modal_reopen = True
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                try:
                                    rebalance_id = service.rebalance_position(
                                        position_id=pending['position_id'],
                                        live_timestamp=pending['timestamp'],
                                        rebalance_reason='manual'
                                    )
                                    st.success(f"✅ Position rebalanced successfully! Rebalance ID: {rebalance_id[:8]}...")
                                    del st.session_state.pending_rebalance
                                    st.session_state.skip_modal_reopen = True  # Prevent strategy modal from appearing
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error: {e}")
                                    import traceback
                                    st.code(traceback.format_exc())

                    with col2:
                        if st.button("❌ Cancel", key=f"cancel_rebalance_{position['position_id']}"):
                            del st.session_state.pending_rebalance
                            st.session_state.skip_modal_reopen = True  # Prevent strategy modal from appearing
                            st.rerun()

                # Check for pending close confirmation (only for this specific position)
                if has_pending_close:
                    pending = st.session_state.pending_close
                    st.warning("⚠️ Confirm Close Position")
                    st.write("This will:")
                    st.write("1. Create final rebalance snapshot with current PnL")
                    st.write("2. Mark position as closed")
                    st.write("3. All PnL will be realized and recorded")
                    st.write("")
                    st.info("This action cannot be undone.")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Confirm Close", key=f"confirm_close_{position['position_id']}"):
                            try:
                                service.close_position_with_snapshot(
                                    position_id=pending['position_id'],
                                    close_timestamp=pending['timestamp'],
                                    close_reason='manual_close',
                                    close_notes='Closed via dashboard'
                                )
                                st.success("✅ Position closed successfully!")
                                del st.session_state.pending_close
                                st.session_state.skip_modal_reopen = True  # Prevent strategy modal from appearing
                                import time
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                                import traceback
                                st.code(traceback.format_exc())

                    with col2:
                        if st.button("❌ Cancel", key=f"cancel_close_{position['position_id']}"):
                            del st.session_state.pending_close
                            st.session_state.skip_modal_reopen = True  # Prevent strategy modal from appearing
                            st.rerun()

                # Display rebalance history
                rebalances = service.get_rebalance_history(position['position_id'])

                if not rebalances.empty:
                    st.markdown("---")
                    st.markdown("### 📊 Rebalance History")

                    for idx, rebalance in rebalances.iterrows():
                        # Helper to get protocol for each leg
                        def get_protocol_for_leg(leg_id):
                            if leg_id in ['1a', '2a']:
                                return position['protocol_a']
                            else:  # '2b', '3b'
                                return position['protocol_b']

                        # Helper to get action for each leg
                        def get_action_for_leg(leg_id):
                            if leg_id in ['1a', '2b']:
                                return 'Lend'
                            else:  # '2a', '3b'
                                return 'Borrow'

                        # Calculate segment summary metrics BEFORE creating title
                        # Initialize accumulators (separate lend/borrow for base)
                        base_lend_total = 0.0
                        base_borrow_total = 0.0
                        total_reward_earnings = 0.0
                        total_fees = 0.0

                        # Get current sequence for timestamp determination
                        current_seq = int(rebalance['sequence_number'])
                        is_latest_segment = (current_seq == len(rebalances))

                        # Get previous rebalance for fee calculation
                        prev_rebalance = None
                        if current_seq > 1:
                            prev_rebalance_df = rebalances[rebalances['sequence_number'] == current_seq - 1]
                            if not prev_rebalance_df.empty:
                                prev_rebalance = prev_rebalance_df.iloc[0]

                        # Build position-like Series for earnings calculation
                        rebalance_as_position = pd.Series({
                            'deployment_usd': rebalance['deployment_usd'],
                            'l_a': rebalance['l_a'],
                            'b_a': rebalance['b_a'],
                            'l_b': rebalance['l_b'],
                            'b_b': rebalance['b_b'],
                            'token1': position['token1'],
                            'token2': position['token2'],
                            'token3': position['token3'],
                            'token1_contract': position['token1_contract'],
                            'token2_contract': position['token2_contract'],
                            'token3_contract': position['token3_contract'],
                            'protocol_a': position['protocol_a'],
                            'protocol_b': position['protocol_b']
                        })

                        opening_ts = to_seconds(rebalance['opening_timestamp'])
                        if is_latest_segment:
                            closing_ts = timestamp_seconds
                        else:
                            closing_ts = to_seconds(rebalance['closing_timestamp'])

                        # Loop through all 4 legs to calculate base/reward earnings and fees
                        for leg in ['1a', '2a', '2b', '3b']:
                            action = get_action_for_leg(leg)

                            # Calculate base and reward earnings for this leg
                            try:
                                base_amount, reward_amount = service.calculate_leg_earnings_split(
                                    rebalance_as_position, leg, action, opening_ts, closing_ts
                                )
                                # Separate lend and borrow base amounts
                                if action == 'Lend':
                                    base_lend_total += base_amount
                                else:  # Borrow
                                    base_borrow_total += base_amount
                                # Rewards are all positive, just accumulate
                                total_reward_earnings += reward_amount
                            except Exception:
                                pass  # Skip if calculation fails

                            # Calculate fees for borrow legs
                            if action == 'Borrow':
                                if leg == '2a':
                                    borrow_fee = position.get('entry_borrow_fee_2a', 0) or 0
                                else:  # '3b'
                                    borrow_fee = position.get('entry_borrow_fee_3b', 0) or 0

                                if borrow_fee > 0:
                                    if prev_rebalance is not None:
                                        current_borrow = rebalance[f'entry_token_amount_{leg}']
                                        prev_borrow = prev_rebalance[f'entry_token_amount_{leg}']
                                        delta_borrow = current_borrow - prev_borrow
                                        if delta_borrow > 0:
                                            leg_fees = borrow_fee * delta_borrow * rebalance[f'opening_price_{leg}']
                                            total_fees += leg_fees
                                    else:
                                        leg_fees = borrow_fee * rebalance[f'entry_token_amount_{leg}'] * rebalance[f'opening_price_{leg}']
                                        total_fees += leg_fees

                        # After loop: combine lend and borrow base totals
                        total_base_earnings = base_lend_total - base_borrow_total  # earnings - costs

                        # Calculate duration in days
                        opening_ts = to_seconds(rebalance['opening_timestamp'])
                        closing_ts_for_apr = to_seconds(rebalance['closing_timestamp'])
                        duration_days = (closing_ts_for_apr - opening_ts) / 86400

                        # Calculate APR from realized PnL
                        realised_pnl = rebalance['realised_pnl']
                        deployment = rebalance['deployment_usd']
                        if duration_days > 0 and deployment > 0:
                            apr = (realised_pnl / deployment) * (365 / duration_days) * 100
                        else:
                            apr = 0.0

                        # Build enhanced expander title (using same format as position expander)
                        rebalance_title = f"▼ Rebalance #{int(rebalance['sequence_number'])}: {rebalance['opening_timestamp']} → {rebalance['closing_timestamp']} ({duration_days:.1f} days) | Realised PnL: \\${realised_pnl:,.2f} (APR: {apr:,.2f}%) | base earnings \\${total_base_earnings:.2f}, rewards \\${total_reward_earnings:.2f}, Fees \\${total_fees:.2f}"
#title = f"▶ {to_datetime_str(position['entry_timestamp'])} | {token_flow} | {protocol_pair} | Entry {position['entry_net_apr'] * 100:.2f}% | Current {current_net_apr_decimal * 100:.2f}% | Net APR {strategy_net_apr * 100:.2f}% | Value ${strategy_value:,.2f}"

                        with st.expander(rebalance_title, expanded=False):
                            # Get next rebalance for "Rebalance Out" calculation
                            next_rebalance = None
                            if current_seq < len(rebalances):
                                next_rebalance = rebalances[rebalances['sequence_number'] == current_seq + 1]
                                if not next_rebalance.empty:
                                    next_rebalance = next_rebalance.iloc[0]
                                else:
                                    next_rebalance = None

                            # Build rebalance detail table with all 4 legs
                            rebalance_data = []

                            # Helper to get token symbol for each leg
                            def get_token_for_leg(leg_id):
                                if leg_id == '1a':
                                    return position['token1']
                                elif leg_id in ['2a', '2b']:
                                    return position['token2']
                                else:  # '3b'
                                    return position['token3']

                            # Helper to format liquidation price
                            def format_rebalance_liq_price(liq_price):
                                """Format liquidation price from rebalance record"""
                                if pd.isna(liq_price) or liq_price is None:
                                    return ""
                                return f"${liq_price:.4f}"

                            # Helper to format liquidation distance
                            def format_rebalance_liq_dist(liq_dist):
                                """Format liquidation distance from rebalance record"""
                                if pd.isna(liq_dist) or liq_dist is None:
                                    return ""
                                return f"{liq_dist * 100:.2f}%"

                            # Reuse pre-calculated segment summary values (calculated before title)
                            # total_base_earnings, total_reward_earnings, total_fees are already available

                            # Build rows for all 4 legs
                            for leg in ['1a', '2a', '2b', '3b']:
                                action = get_action_for_leg(leg)

                                # Determine rate column names based on action
                                if action == 'Lend':
                                    opening_rate_col = f'opening_lend_rate_{leg}'
                                    closing_rate_col = f'closing_lend_rate_{leg}'
                                    weight_col = f'l_{"a" if leg in ["1a", "2a"] else "b"}'
                                else:  # Borrow
                                    opening_rate_col = f'opening_borrow_rate_{leg}'
                                    closing_rate_col = f'closing_borrow_rate_{leg}'
                                    weight_col = f'b_{"b" if leg in ["1a", "2a"] else "b"}'

                                # Token Rebalance Action: Show for all legs (future-proof)
                                # Compare current entry_token_amount to previous rebalance's entry_token_amount
                                token_rebalance_action = ''
                                if prev_rebalance is not None:
                                    current_amount = rebalance[f'entry_token_amount_{leg}']
                                    prev_amount = prev_rebalance[f'entry_token_amount_{leg}']
                                    delta_tokens = current_amount - prev_amount
                                    delta_usd = delta_tokens * rebalance[f'opening_price_{leg}']

                                    if abs(delta_usd) > 0.1:  # Ignore tiny differences
                                        # Format action based on action type and direction
                                        usd_amt = abs(delta_usd)
                                        if action == 'Lend':
                                            if delta_usd > 0:
                                                token_rebalance_action = f"Lend ${usd_amt:,.0f}"
                                            else:
                                                token_rebalance_action = f"Withdraw ${usd_amt:,.0f}"
                                        else:  # Borrow
                                            if delta_usd > 0:
                                                token_rebalance_action = f"Borrow ${usd_amt:,.0f}"
                                            else:
                                                token_rebalance_action = f"Repay ${usd_amt:,.0f}"
                                    else:
                                        token_rebalance_action = "No change"
                                else:
                                    # First rebalance - no previous to compare
                                    token_rebalance_action = "Initial"

                                # Calculate "Rebalance Out" for this leg
                                # Shows the USD value of token change when exiting this segment
                                rebalance_out_usd = ''

                                # Determine next position state
                                if next_rebalance is not None:
                                    # There's another rebalance after this one
                                    next_amt = next_rebalance[f'entry_token_amount_{leg}']
                                elif current_seq == len(rebalances):
                                    # This is the last rebalance, compare to LIVE position
                                    # Calculate live position token amounts from current weights
                                    live_deployment = position['deployment_usd']
                                    if leg == '1a':
                                        live_weight = position['l_a']
                                        live_price = position['entry_price_1a']
                                    elif leg == '2a':
                                        live_weight = position['b_a']
                                        live_price = position['entry_price_2a']
                                    elif leg == '2b':
                                        live_weight = position['l_b']
                                        live_price = position['entry_price_2b']
                                    else:  # '3b'
                                        live_weight = position['b_b']
                                        live_price = position['entry_price_3b']

                                    next_amt = (live_weight * live_deployment) / live_price if live_price > 0 else 0
                                else:
                                    # Not last rebalance and no next rebalance (shouldn't happen)
                                    next_amt = None

                                if next_amt is not None:
                                    curr_amt = rebalance[f'entry_token_amount_{leg}']
                                    delta_out_tokens = next_amt - curr_amt
                                    delta_out_usd_val = delta_out_tokens * rebalance[f'closing_price_{leg}']

                                    if abs(delta_out_usd_val) > 1:
                                        # Format with action verb based on action type and direction
                                        usd_amt = abs(delta_out_usd_val)
                                        if action == 'Lend':
                                            if delta_out_usd_val > 0:
                                                rebalance_out_usd = f"Lend ${usd_amt:,.0f}"
                                            else:
                                                rebalance_out_usd = f"Withdraw ${usd_amt:,.0f}"
                                        else:  # Borrow
                                            if delta_out_usd_val > 0:
                                                rebalance_out_usd = f"Borrow ${usd_amt:,.0f}"
                                            else:
                                                rebalance_out_usd = f"Repay ${usd_amt:,.0f}"

                                # Calculate base and reward earnings for this leg
                                # Create position-like Series from rebalance data
                                rebalance_as_position = pd.Series({
                                    'deployment_usd': rebalance['deployment_usd'],
                                    'l_a': rebalance['l_a'],
                                    'b_a': rebalance['b_a'],
                                    'l_b': rebalance['l_b'],
                                    'b_b': rebalance['b_b'],
                                    'token1': position['token1'],
                                    'token2': position['token2'],
                                    'token3': position['token3'],
                                    'token1_contract': position['token1_contract'],
                                    'token2_contract': position['token2_contract'],
                                    'token3_contract': position['token3_contract'],
                                    'protocol_a': position['protocol_a'],
                                    'protocol_b': position['protocol_b']
                                })

                                opening_ts = to_seconds(rebalance['opening_timestamp'])

                                # For the LATEST segment (still open), use strategy_timestamp instead of stored closing_timestamp
                                # For CLOSED segments (historical), use the stored closing_timestamp
                                is_latest_segment = (int(rebalance['sequence_number']) == len(rebalances))
                                if is_latest_segment:
                                    # Latest segment: calculate earnings up to selected timestamp
                                    closing_ts = timestamp_seconds
                                else:
                                    # Closed segment: use stored closing timestamp
                                    closing_ts = to_seconds(rebalance['closing_timestamp'])

                                try:
                                    base_amount, reward_amount = service.calculate_leg_earnings_split(
                                        rebalance_as_position, leg, action, opening_ts, closing_ts
                                    )
                                except Exception as e:
                                    # Fallback to zeros if calculation fails
                                    base_amount, reward_amount = 0.0, 0.0

                                # Note: total_base_earnings, total_reward_earnings already calculated before title
                                # Per-leg values (base_amount, reward_amount) are used for token table display only

                                # Calculate fee rate for borrow legs
                                fee_rate_display = ''
                                if action == 'Borrow':
                                    # Get borrow fee rate from position
                                    if leg == '2a':
                                        borrow_fee = position.get('entry_borrow_fee_2a', 0) or 0
                                    else:  # '3b'
                                        borrow_fee = position.get('entry_borrow_fee_3b', 0) or 0

                                    if borrow_fee > 0:
                                        fee_rate_display = f"{borrow_fee * 100:.2f}%"

                                row = {
                                    'Protocol': get_protocol_for_leg(leg),
                                    'Token': get_token_for_leg(leg),
                                    'Action': action,
                                    'Weight': f"{rebalance[weight_col]:.4f}",
                                    # DESIGN PRINCIPLE: Rates stored as decimals, convert to % for display
                                    'Entry Rate': f"{rebalance[opening_rate_col] * 100:.2f}%",
                                    'Close Rate': f"{rebalance[closing_rate_col] * 100:.2f}%",
                                    'Entry Price': f"${rebalance[f'opening_price_{leg}']:.4f}",
                                    'Close Price': f"${rebalance[f'closing_price_{leg}']:.4f}",
                                    'Exit Liq Price': format_rebalance_liq_price(rebalance.get(f'closing_liq_price_{leg}')),
                                    'Rebalance In': token_rebalance_action,
                                    'Token Amount': f"{rebalance[f'entry_token_amount_{leg}']:,.4f}",
                                    'Rebalance Out': rebalance_out_usd,
                                    'Lend/Borrow Base $$$': f"${base_amount:,.2f}",
                                    'Reward $$$': f"${reward_amount:,.2f}",
                                    'Fee Rate': fee_rate_display,
                                    'Entry $$$ Size': f"${rebalance[f'entry_size_usd_{leg}']:,.2f}",
                                    'Exit $$$ Size': f"${rebalance[f'exit_size_usd_{leg}']:,.2f}",
                                    'Exit Liq Dist': format_rebalance_liq_dist(rebalance.get(f'closing_liq_dist_{leg}'))
                                }
                                rebalance_data.append(row)

                            rebalance_df = pd.DataFrame(rebalance_data)
                            # DESIGN PRINCIPLE: Use width='stretch' instead of deprecated use_container_width=True
                            st.dataframe(rebalance_df, width='stretch', hide_index=True)

                            # Summary metrics
                            st.markdown("**Segment Summary**")

                            # Get deployment for percentage calculation
                            deployment = rebalance['deployment_usd']

                            # Calculate summary values from accumulated token table values
                            # Total Earnings = Base Earnings + Reward Earnings
                            total_earnings = total_base_earnings + total_reward_earnings
                            # Realised PnL = Total Earnings - Fees
                            realised_pnl = total_earnings - total_fees

                            # GUARD: Check for zero deployment
                            if deployment > 0:
                                col1, col2, col3, col4, col5 = st.columns(5)
                                with col1:
                                    pnl_pct = (realised_pnl / deployment) * 100
                                    st.metric("Realised PnL", f"${realised_pnl:,.2f} ({pnl_pct:.2f}%)")
                                with col2:
                                    earnings_pct = (total_earnings / deployment) * 100
                                    st.metric("Total Earnings", f"${total_earnings:,.2f} ({earnings_pct:.2f}%)")
                                with col3:
                                    base_pct = (total_base_earnings / deployment) * 100
                                    st.metric("Base Earnings", f"${total_base_earnings:,.2f} ({base_pct:.2f}%)")
                                with col4:
                                    reward_pct = (total_reward_earnings / deployment) * 100
                                    st.metric("Reward Earnings", f"${total_reward_earnings:,.2f} ({reward_pct:.2f}%)")
                                with col5:
                                    fees_pct = (total_fees / deployment) * 100
                                    st.metric("Fees", f"${total_fees:,.2f} ({fees_pct:.2f}%)")
                            else:
                                st.warning("Invalid rebalance deployment amount - cannot calculate percentages")

                            # Calculate holding days
                            # DESIGN PRINCIPLE: Convert datetime strings to Unix seconds for arithmetic
                            holding_seconds = (
                                to_seconds(rebalance['closing_timestamp']) -
                                to_seconds(rebalance['opening_timestamp'])
                            )
                            holding_days = holding_seconds / 86400

                            st.caption(f"Holding period: {holding_days:.1f} days")

                            # Display reason and notes if available
                            if pd.notna(rebalance.get('rebalance_reason')):
                                st.caption(f"Reason: {rebalance['rebalance_reason']}")
                            if pd.notna(rebalance.get('rebalance_notes')):
                                st.caption(f"Notes: {rebalance['rebalance_notes']}")

        conn.close()

    except KeyError as e:
        st.error(f"❌ KeyError loading positions: {e}")
        st.write("### Full Error Traceback:")
        import traceback
        st.code(traceback.format_exc())

    except Exception as e:
        st.error(f"❌ Error loading positions: {e}")
        st.write("### Full Error Traceback:")
        import traceback
        st.code(traceback.format_exc())


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
                f"{row['protocol_a']} ↔ {row['protocol_b']} | "
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
         lend_rewards, borrow_rewards, available_borrow, borrow_fees, borrow_weights, liquidation_thresholds, timestamp) = data_loader.load_data()

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
    #print(cached_results)
    if cached_results is not None:
        # Use cached analysis from database (returns DataFrame only)
        all_results = cached_results
        #print(all_results)
        # Extract protocol_a and protocol_b from the best strategy (first row, sorted by net_apr desc)
        # if not all_results.empty:
        #     best_strategy = all_results.iloc[0]
        #     #print(best_strategy)
        #     protocol_a = best_strategy['protocol_A']  # Strategy data uses mixed-case
        #     protocol_b = best_strategy['protocol_B']  # Strategy data uses mixed-case
        # else:
        #     protocol_a = None
        #     protocol_b = None

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
            liquidation_thresholds=liquidation_thresholds,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
            available_borrow=available_borrow,
            borrow_fees=borrow_fees,
            borrow_weights=borrow_weights,
            timestamp=timestamp_seconds,  # Pass Unix seconds (int)
            liquidation_distance=liquidation_distance
        )
        analyzer_init_time = (time.time() - analyzer_init_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] RateAnalyzer initialized in {analyzer_init_time:.1f}ms")

        analysis_run_start = time.time()
        protocol_a, protocol_b, all_results = analyzer.find_best_protocol_pair()
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
            display_results['protocol_a'].isin(protocol_filter) |
            display_results['protocol_b'].isin(protocol_filter)
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

    # === TIMESTAMP DISPLAY ===
    # Show current "live" timestamp being viewed (from internal data source)
    timestamp_display = to_datetime_str(timestamp_seconds)
    st.markdown(f"**Viewing data as of:** `{timestamp_display}`")

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
            available_borrow, borrow_fees, borrow_weights, liquidation_thresholds
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
        render_positions_table_tab(timestamp_seconds)
        tab4_time = (time.time() - tab4_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab4 (Positions) rendered in {tab4_time:.1f}ms")

    total_dashboard_time = (time.time() - dashboard_start) * 1000
    print(f"[{total_dashboard_time:7.1f}ms] [DASHBOARD] ✅ Dashboard render complete (total: {total_dashboard_time:.1f}ms)\n")