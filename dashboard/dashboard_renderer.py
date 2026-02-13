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
from analysis.position_statistics_calculator import calculate_position_statistics
from dashboard.position_renderers import (
    build_rate_lookup,
    build_oracle_prices,
    render_position_expander,
    render_positions_batch,
    calculate_position_summary_stats,
    render_position_summary_stats,
    get_registered_strategy_types
)


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
# SETTINGS INITIALIZATION
# ============================================================================

def initialize_allocator_settings():
    """
    Initialize allocator settings on dashboard startup.

    Priority:
    1. If already in session_state → use existing (already initialized)
    2. Try loading 'last_used' from database
    3. Fall back to config defaults

    Sets:
    - st.session_state.allocation_constraints
    - st.session_state.sidebar_filters
    """
    # Skip if already initialized
    if 'allocation_constraints' in st.session_state:
        return

    try:
        from analysis.allocator_settings_service import AllocatorSettingsService

        conn = get_db_connection()
        service = AllocatorSettingsService(conn)

        # Try loading last used settings
        last_used = service.load_last_used()
        conn.close()

        if last_used:
            st.session_state.allocation_constraints = last_used['allocator_constraints']
            st.session_state.sidebar_filters = last_used.get('sidebar_filters', {})
            print("✅ Loaded last used settings from database")
            return
    except Exception as e:
        print(f"⚠️  Warning: Failed to load last used settings: {e}")
        # Fall through to defaults

    # Fall back to config defaults
    from config.settings import DEFAULT_ALLOCATION_CONSTRAINTS, DEFAULT_DEPLOYMENT_USD

    st.session_state.allocation_constraints = DEFAULT_ALLOCATION_CONSTRAINTS.copy()
    st.session_state.sidebar_filters = {
        'liquidation_distance': 0.20,
        'deployment_usd': DEFAULT_DEPLOYMENT_USD,
        'force_usdc_start': False,
        'force_token3_equals_token1': False,
        'stablecoin_only': False,
        'min_net_apr': 0.0,
        'token_filter': [],
        'protocol_filter': []
    }
    print("ℹ️  Using default settings (no last_used found)")


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
        if isinstance(val, str):
            if val == "N/A":
                return 'color: gray; font-style: italic'
            elif '%' in val:
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
    if st.button("🚀 Deploy Position", type="primary", width='stretch'):
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


def get_position_statistics(position_id: str, timestamp: int, engine) -> Optional[dict]:
    """
    Get position statistics for a specific timestamp.
    Returns the latest statistics at or before the given timestamp.

    Args:
        position_id: Position ID to retrieve statistics for
        timestamp: Unix timestamp in seconds
        engine: Database engine

    Returns:
        dict with statistics, or None if not found
    """
    from utils.time_helpers import to_datetime_str
    from sqlalchemy import text

    timestamp_str = to_datetime_str(timestamp)

    # Use SQLAlchemy text() with named parameters for cross-database compatibility
    query = text("""
    SELECT * FROM position_statistics
    WHERE position_id = :position_id
    AND timestamp <= :timestamp
    ORDER BY timestamp DESC
    LIMIT 1
    """)

    result = pd.read_sql_query(query, engine, params={'position_id': position_id, 'timestamp': timestamp_str})

    if result.empty:
        return None

    return result.iloc[0].to_dict()


def get_all_position_statistics(position_ids: list, timestamp: int, engine) -> dict:
    """
    Batch load position statistics for multiple positions.

    This function loads statistics for all positions in a single query,
    avoiding N+1 query problems.

    Args:
        position_ids: List of position IDs to retrieve statistics for
        timestamp: Unix timestamp in seconds
        engine: Database engine

    Returns:
        dict mapping position_id -> stats dict
    """
    from utils.time_helpers import to_datetime_str
    from sqlalchemy import text

    if not position_ids:
        return {}

    timestamp_str = to_datetime_str(timestamp)

    # Build query with window function to get latest stats for each position
    placeholders = ','.join([f':pid{i}' for i in range(len(position_ids))])

    query = text(f"""
    WITH ranked_stats AS (
        SELECT
            *,
            ROW_NUMBER() OVER (PARTITION BY position_id ORDER BY timestamp DESC) as rn
        FROM position_statistics
        WHERE position_id IN ({placeholders})
        AND timestamp <= :timestamp
    )
    SELECT * FROM ranked_stats WHERE rn = 1
    """)

    params = {'timestamp': timestamp_str}
    params.update({f'pid{i}': pid for i, pid in enumerate(position_ids)})

    result_df = pd.read_sql_query(query, engine, params=params)

    # Convert to dict keyed by position_id
    stats_dict = {}
    for _, row in result_df.iterrows():
        stats_dict[row['position_id']] = row.to_dict()

    return stats_dict


def get_all_rebalance_history(position_ids: list, conn) -> dict:
    """
    Batch load rebalance history for multiple positions.

    This function loads rebalance history for all positions in a single query,
    avoiding N+1 query problems.

    Args:
        position_ids: List of position IDs to retrieve rebalance history for
        conn: Database connection

    Returns:
        dict mapping position_id -> DataFrame of rebalances
    """
    if not position_ids:
        return {}

    # Determine placeholder based on connection type
    try:
        import psycopg2
        if isinstance(conn, psycopg2.extensions.connection):
            ph = '%s'
        else:
            ph = '?'
    except ImportError:
        ph = '?'  # Default to SQLite if psycopg2 not available

    placeholders = ','.join([ph for _ in position_ids])

    query = f"""
    SELECT * FROM position_rebalances
    WHERE position_id IN ({placeholders})
    ORDER BY position_id, sequence_number ASC
    """

    cursor = conn.cursor()
    cursor.execute(query, position_ids)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()

    # Group by position_id
    rebalance_dict = {}
    for row in rows:
        row_dict = dict(zip(columns, row))
        position_id = row_dict['position_id']

        if position_id not in rebalance_dict:
            rebalance_dict[position_id] = []
        rebalance_dict[position_id].append(row_dict)

    # Convert to DataFrames
    for position_id in rebalance_dict:
        rebalance_dict[position_id] = pd.DataFrame(rebalance_dict[position_id])

    # Return empty DataFrames for positions with no rebalances
    for position_id in position_ids:
        if position_id not in rebalance_dict:
            rebalance_dict[position_id] = pd.DataFrame()

    return rebalance_dict


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

        # Load oracle prices for fallback when protocol prices are missing
        oracle_prices_df = pd.read_sql_query(
            "SELECT symbol, latest_price, last_updated FROM oracle_prices",
            engine
        )

        # Build oracle lookup dictionary
        oracle_lookup = {}  # {symbol: {'price': float, 'last_updated': datetime}}
        for _, row in oracle_prices_df.iterrows():
            if pd.notna(row['latest_price']):  # Only include valid prices
                oracle_lookup[row['symbol']] = {
                    'price': float(row['latest_price']),
                    'last_updated': row['last_updated']
                }

        # Check if oracle data is stale (max age > 60 minutes) and refresh if needed
        if oracle_lookup:
            # Find oldest update timestamp
            oldest_update = min(
                data['last_updated']
                for data in oracle_lookup.values()
                if data.get('last_updated') is not None
            )
            age_minutes = (datetime.now() - oldest_update).total_seconds() / 60

            if age_minutes > 60:
                st.info("🔄 Oracle prices are stale. Refreshing from APIs...")
                try:
                    # Import and call oracle price fetcher
                    from utils.fetch_oracle_prices import fetch_all_oracle_prices
                    fetch_all_oracle_prices(dry_run=False)

                    # Reload oracle prices after refresh
                    oracle_prices_df = pd.read_sql_query(
                        "SELECT symbol, latest_price, last_updated FROM oracle_prices",
                        engine
                    )
                    oracle_lookup = {}
                    for _, row in oracle_prices_df.iterrows():
                        if pd.notna(row['latest_price']):
                            oracle_lookup[row['symbol']] = {
                                'price': float(row['latest_price']),
                                'last_updated': row['last_updated']
                            }
                    st.success("✓ Oracle prices refreshed")
                except Exception as e:
                    st.warning(f"⚠️ Failed to refresh oracle prices: {e}. Using stale data.")

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

        # Helper function to get oracle price
        def get_oracle_price(token_symbol):
            """Get oracle price for token symbol, return 0 if not found"""
            oracle_data = oracle_lookup.get(token_symbol, {})
            return oracle_data.get('price', 0.0)

        # Helper function to get price with oracle fallback
        def get_price_with_fallback(token, protocol):
            """
            Get price with 3-tier fallback: protocol → oracle → missing.

            Returns:
                Tuple of (price, source) where source is 'protocol', 'oracle', or 'missing'
            """
            # Tier 1: Try protocol price
            protocol_price = get_price(token, protocol)
            if protocol_price > 0:
                return (protocol_price, 'protocol')

            # Tier 2: Try oracle price
            oracle_price = get_oracle_price(token)
            if oracle_price > 0:
                return (oracle_price, 'oracle')

            # Tier 3: No price available
            return (0.0, 'missing')

        # Helper function to safely calculate liquidation price with missing price handling
        def calculate_liquidation_price_safe(
            collateral_value: float,
            loan_value: float,
            lending_token_price: float,
            borrowing_token_price: float,
            lltv: float,
            side: str,
            borrow_weight: float = 1.0
        ):
            """
            Safely calculate liquidation price, handling missing price data.

            Returns a result dict with 'missing_price' direction if prices are invalid.
            """
            # Check for missing/invalid prices
            if lending_token_price <= 0 or borrowing_token_price <= 0:
                return {
                    'liq_price': 0.0,
                    'current_price': 0.0,
                    'pct_distance': 0.0,
                    'current_ltv': 0.0,
                    'lltv': lltv,
                    'direction': 'missing_price'
                }

            # Prices are valid, proceed with normal calculation
            return calc.calculate_liquidation_price(
                collateral_value=collateral_value,
                loan_value=loan_value,
                lending_token_price=lending_token_price,
                borrowing_token_price=borrowing_token_price,
                lltv=lltv,
                side=side,
                borrow_weight=borrow_weight
            )

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

        # ========================================================================
        # PHASE 1: LOAD PRE-CALCULATED POSITION STATISTICS FROM DATABASE
        # ========================================================================

        # OPTIMIZATION: Batch load statistics for all positions in ONE query
        position_ids = active_positions['position_id'].tolist()
        all_stats = get_all_position_statistics(position_ids, latest_timestamp, engine)

        # OPTIMIZATION: Batch load rebalance history for all positions in ONE query
        all_rebalances = get_all_rebalance_history(position_ids, conn)

        # Check if any positions are missing statistics
        positions_missing_stats = []
        for _, position in active_positions.iterrows():
            stats = all_stats.get(position['position_id'])
            if stats is None or to_seconds(stats.get('timestamp')) != latest_timestamp:
                positions_missing_stats.append(position)

        # Show "Calculate All Statistics" button if any positions are missing stats
        if positions_missing_stats:
            st.warning(f"⚠️ {len(positions_missing_stats)} position(s) missing statistics at {latest_timestamp_str}")

            col_btn, col_info = st.columns([1, 3])
            with col_btn:
                if st.button("📊 Calculate All Statistics", type="primary", width="stretch"):
                    success_count = 0
                    error_count = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, position in enumerate(positions_missing_stats):
                        try:
                            position_short_id = position['position_id'][:8]
                            status_text.text(f"Calculating {idx+1}/{len(positions_missing_stats)}: {position_short_id}...")

                            # Calculate statistics
                            def get_rate_wrapper(token_contract, protocol, side):
                                return get_rate(token_contract, protocol, side)

                            def get_borrow_fee_wrapper(token_contract, protocol):
                                return get_borrow_fee(token_contract, protocol)

                            stats_dict = calculate_position_statistics(
                                position_id=position['position_id'],
                                timestamp=latest_timestamp,
                                service=service,
                                get_rate_func=get_rate_wrapper,
                                get_borrow_fee_func=get_borrow_fee_wrapper
                            )

                            # Save to database
                            tracker = RateTracker(
                                use_cloud=settings.USE_CLOUD_DB,
                                connection_url=settings.SUPABASE_URL
                            )
                            tracker.save_position_statistics(stats_dict)

                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            st.error(f"Failed for {position_short_id}: {e}")

                        progress_bar.progress((idx + 1) / len(positions_missing_stats))

                    status_text.empty()
                    progress_bar.empty()

                    if success_count > 0:
                        st.success(f"✅ Calculated statistics for {success_count} position(s)")
                    if error_count > 0:
                        st.warning(f"⚠️ Failed for {error_count} position(s)")

                    # Reload page to show updated data
                    st.rerun()

            with col_info:
                st.info("💡 This will calculate and save statistics for all positions at once (~1-2 seconds per position)")

            st.markdown("---")

        # ========================================================================
        # PHASE 3: RENDER ALL POSITIONS SUMMARY
        # ========================================================================

        # Calculate stats (pure calculation, no rendering)
        summary_stats = calculate_position_summary_stats(
            position_ids=position_ids,
            timestamp_seconds=latest_timestamp
        )

        # Render stats (pure rendering, no calculation)
        render_position_summary_stats(
            stats=summary_stats,
            title="All Positions Summary"
        )


        # ========================================================================
        # PHASE 4: Render positions using BATCH RENDERER
        # ========================================================================
        # Design Principle #11: Pure view layer - delegates to batch renderer

        from dashboard.position_renderers import render_positions_batch

        # Delegate all rendering to batch wrapper (handles infrastructure internally)
        render_positions_batch(
            position_ids=position_ids,
            timestamp_seconds=latest_timestamp,
            context='standalone'
        )

        conn.close()

    except ValueError as e:
        st.error(f"❌ Value Error: {e}")
        st.write("### Error Details:")
        import traceback
        st.code(traceback.format_exc())
        try:
            conn.close()
        except:
            pass
    except KeyError as e:
        st.error(f"❌ KeyError loading positions: {e}")
        st.write("### Full Error Traceback:")
        import traceback
        st.code(traceback.format_exc())

        conn.close()

    except Exception as e:
        st.error(f"❌ Error loading positions: {e}")
        st.write("### Full Error Traceback:")
        import traceback
        st.code(traceback.format_exc())


def calculate_acceptable_ranges(
    expected_price: float,
    expected_rate: float,
    price_tolerance: float = 0.0025,  # 0.25% default
    rate_tolerance: float = 0.03       # 3% default
) -> Dict[str, float]:
    """
    Calculate acceptable ranges for prices and rates

    Args:
        expected_price: Expected token price (USD)
        expected_rate: Expected interest rate (decimal, e.g., 0.08 = 8%)
        price_tolerance: Price tolerance as decimal (0.0025 = 0.25%)
        rate_tolerance: Rate tolerance as decimal (0.03 = 3%)

    Returns:
        Dict with 'price_low', 'price_high', 'rate_low', 'rate_high'
    """
    return {
        'price_low': expected_price * (1 - price_tolerance),
        'price_high': expected_price * (1 + price_tolerance),
        'rate_low': expected_rate * (1 - rate_tolerance),
        'rate_high': expected_rate * (1 + rate_tolerance)
    }


def render_pending_deployments_tab():
    """
    Render Pending Deployments tab showing positions awaiting execution

    Displays all positions with execution_time = -1 regardless of selected timestamp.
    Shows detailed execution instructions for each leg of the position.
    """
    st.header("🚀 Pending Deployments")
    st.markdown("Positions awaiting on-chain execution. Follow the instructions below to execute each leg.")

    try:
        # Connect to database
        conn = get_db_connection()
        service = PositionService(conn)

        # Query pending positions (execution_time = -1)
        from dashboard.db_utils import get_db_engine
        engine = get_db_engine()
        query = """
        SELECT *
        FROM positions
        WHERE execution_time = -1
        ORDER BY created_at DESC
        """
        pending_positions = pd.read_sql_query(query, engine)

        # Handle empty state
        if pending_positions.empty:
            st.info("📭 No pending deployments. Deploy a strategy from the 'All Strategies' tab to see positions here.")
            conn.close()
            return

        # Display count
        st.metric("Pending Positions", len(pending_positions))
        st.markdown("---")

        # Render each position
        for _, position in pending_positions.iterrows():
            render_pending_position_instructions(position, service)

        conn.close()

    except Exception as e:
        st.error(f"❌ Error loading pending deployments: {e}")
        import traceback
        st.code(traceback.format_exc())


def render_pending_position_instructions(position: pd.Series, service: PositionService):
    """
    Render execution instructions for a single pending position

    Args:
        position: Position row from database
        service: PositionService instance for database operations
    """
    # Extract core info
    position_id = position['position_id']
    position_short_id = position_id[:8]
    token1, token2, token3 = position['token1'], position['token2'], position['token3']
    protocol_a, protocol_b = position['protocol_a'], position['protocol_b']
    deployment_usd = float(position['deployment_usd'])

    # Extract multipliers
    l_a, b_a = float(position['l_a']), float(position['b_a'])
    l_b, b_b = float(position['l_b']), float(position['b_b'])

    # Extract prices and rates
    price_1a, price_2a = float(position['entry_price_1a']), float(position['entry_price_2a'])
    price_2b, price_3b = float(position['entry_price_2b']), float(position['entry_price_3b'])

    rate_1a = float(position['entry_lend_rate_1a'])
    rate_2a = float(position['entry_borrow_rate_2a'])
    rate_2b = float(position['entry_lend_rate_2b'])
    rate_3b = float(position['entry_borrow_rate_3b'])

    fee_2a = float(position.get('entry_borrow_fee_2a', 0))
    fee_3b = float(position.get('entry_borrow_fee_3b', 0))

    # Calculate USD amounts per leg
    lend_1a_usd = l_a * deployment_usd
    borrow_2a_usd = b_a * deployment_usd
    lend_2b_usd = l_b * deployment_usd
    borrow_3b_usd = b_b * deployment_usd

    # Calculate token amounts
    amt_1a = lend_1a_usd / price_1a
    amt_2a = borrow_2a_usd / price_2a
    amt_2b = lend_2b_usd / price_2b
    amt_3b = borrow_3b_usd / price_3b

    # Calculate acceptable ranges (using defaults for now)
    ranges_1a = calculate_acceptable_ranges(price_1a, rate_1a)
    ranges_2a = calculate_acceptable_ranges(price_2a, rate_2a)
    ranges_2b = calculate_acceptable_ranges(price_2b, rate_2b)
    ranges_3b = calculate_acceptable_ranges(price_3b, rate_3b)

    # Build title
    token_flow = f"{token1} → {token2} → {token3}"
    protocol_pair = f"{protocol_a} ↔ {protocol_b}"
    created_at = position['created_at']
    title = f"Position {position_short_id} | {token_flow} | {protocol_pair} | ${deployment_usd:,.0f} | Created: {created_at}"

    # Expandable section
    with st.expander(title, expanded=True):
        # Position summary
        st.markdown(f"**Position ID:** `{position_id}`")
        st.markdown(f"**Strategy:** {token_flow} via {protocol_pair}")
        st.markdown(f"**Deployment Amount:** ${deployment_usd:,.2f}")
        st.markdown(f"**Entry Net APR:** {position['entry_net_apr'] * 100:.2f}%")

        st.markdown("---")
        st.markdown("### 📋 Execution Instructions")
        st.markdown("Execute the following 4 legs in order:")
        st.markdown("")

        # Leg 1: Lend token1 to Protocol A
        st.markdown(f"**Leg 1: Lend {token1} to {protocol_a}**")
        st.markdown(f"- **Action:** Lend **{amt_1a:,.6f} {token1}** to {protocol_a}")
        st.markdown(f"- **Expected USD Value:** ${lend_1a_usd:,.2f}")
        st.markdown(f"- **Expected Price:** ${price_1a:.6f} USD per {token1}")
        st.markdown(f"- **Acceptable Price:** ≥ ${ranges_1a['price_low']:.6f} USD")
        st.markdown(f"- **Expected Rate:** {rate_1a * 100:.2f}%")
        st.markdown(f"- **Acceptable Rate:** ≥ {ranges_1a['rate_low'] * 100:.2f}%")
        st.markdown("")

        # Leg 2: Borrow token2 from Protocol A
        st.markdown(f"**Leg 2: Borrow {token2} from {protocol_a}**")
        st.markdown(f"- **Action:** Borrow **{amt_2a:,.6f} {token2}** from {protocol_a}")
        st.markdown(f"- **Expected USD Value:** ${borrow_2a_usd:,.2f}")
        st.markdown(f"- **Expected Price:** ${price_2a:.6f} USD per {token2}")
        st.markdown(f"- **Acceptable Price:** ≤ ${ranges_2a['price_high']:.6f} USD")
        st.markdown(f"- **Expected Rate:** {rate_2a * 100:.2f}%")
        st.markdown(f"- **Acceptable Rate:** ≤ {ranges_2a['rate_high'] * 100:.2f}%")
        st.markdown(f"- **Borrow Fee:** {fee_2a * 100:.3f}% (${borrow_2a_usd * fee_2a:,.2f})")
        st.markdown("")

        # Leg 3: Lend token2 to Protocol B
        st.markdown(f"**Leg 3: Lend {token2} to {protocol_b}**")
        st.markdown(f"- **Action:** Lend **{amt_2b:,.6f} {token2}** to {protocol_b}")
        st.markdown(f"- **Expected USD Value:** ${lend_2b_usd:,.2f}")
        st.markdown(f"- **Expected Price:** ${price_2b:.6f} USD per {token2}")
        st.markdown(f"- **Acceptable Price:** ≥ ${ranges_2b['price_low']:.6f} USD")
        st.markdown(f"- **Expected Rate:** {rate_2b * 100:.2f}%")
        st.markdown(f"- **Acceptable Rate:** ≥ {ranges_2b['rate_low'] * 100:.2f}%")
        st.markdown("")

        # Leg 4: Borrow token3 from Protocol B
        st.markdown(f"**Leg 4: Borrow {token3} from {protocol_b}**")
        st.markdown(f"- **Action:** Borrow **{amt_3b:,.6f} {token3}** from {protocol_b}")
        st.markdown(f"- **Expected USD Value:** ${borrow_3b_usd:,.2f}")
        st.markdown(f"- **Expected Price:** ${price_3b:.6f} USD per {token3}")
        st.markdown(f"- **Acceptable Price:** ≤ ${ranges_3b['price_high']:.6f} USD")
        st.markdown(f"- **Expected Rate:** {rate_3b * 100:.2f}%")
        st.markdown(f"- **Acceptable Rate:** ≤ {ranges_3b['rate_high'] * 100:.2f}%")
        st.markdown(f"- **Borrow Fee:** {fee_3b * 100:.3f}% (${borrow_3b_usd * fee_3b:,.2f})")

        st.markdown("---")
        st.markdown("### 🔧 Actions")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✅ Mark as Executed", key=f"execute_{position_id}", type="primary"):
                service.mark_position_executed(position_id)
                st.success(f"✅ Position {position_short_id} marked as executed!")
                st.rerun()

        with col2:
            if st.button("🗑️ Delete Position", key=f"delete_{position_id}", type="secondary"):
                service.delete_position(position_id)
                st.success(f"🗑️ Position {position_short_id} deleted!")
                st.rerun()

        with col3:
            # Copy instructions to clipboard
            instructions_text = f"""Position ID: {position_id}
Strategy: {token_flow} via {protocol_pair}
Deployment: ${deployment_usd:,.2f}

Leg 1: Lend {amt_1a:,.6f} {token1} to {protocol_a}
  Expected price: ${price_1a:.6f}, rate: {rate_1a*100:.2f}%
  Acceptable price: ≥${ranges_1a['price_low']:.6f}, rate: ≥{ranges_1a['rate_low']*100:.2f}%

Leg 2: Borrow {amt_2a:,.6f} {token2} from {protocol_a}
  Expected price: ${price_2a:.6f}, rate: {rate_2a*100:.2f}%
  Acceptable price: ≤${ranges_2a['price_high']:.6f}, rate: ≤{ranges_2a['rate_high']*100:.2f}%
  Fee: {fee_2a*100:.3f}%

Leg 3: Lend {amt_2b:,.6f} {token2} to {protocol_b}
  Expected price: ${price_2b:.6f}, rate: {rate_2b*100:.2f}%
  Acceptable price: ≥${ranges_2b['price_low']:.6f}, rate: ≥{ranges_2b['rate_low']*100:.2f}%

Leg 4: Borrow {amt_3b:,.6f} {token3} from {protocol_b}
  Expected price: ${price_3b:.6f}, rate: {rate_3b*100:.2f}%
  Acceptable price: ≤${ranges_3b['price_high']:.6f}, rate: ≤{ranges_3b['rate_high']*100:.2f}%
  Fee: {fee_3b*100:.3f}%"""

            st.download_button(
                label="📋 Copy Instructions",
                data=instructions_text,
                file_name=f"position_{position_short_id}_instructions.txt",
                mime="text/plain",
                key=f"copy_{position_id}"
            )


def render_oracle_prices_tab(timestamp_seconds: int):
    """
    Render Oracle Prices tab showing latest prices from multiple oracles.

    Args:
        timestamp_seconds: Current timestamp (for consistency with other tabs)
    """
    import streamlit as st
    import pandas as pd
    from dashboard.db_utils import get_db_engine
    from dashboard.oracle_price_utils import (
        format_contract_address,
        compute_timestamp_age
    )

    st.header("💎 Oracle Prices")

    engine = get_db_engine()

    query = """
    SELECT
        symbol,
        token_contract,
        coingecko,
        coingecko_time,
        pyth,
        pyth_time,
        defillama,
        defillama_time,
        defillama_confidence,
        latest_price,
        latest_oracle,
        latest_time
    FROM oracle_prices
    ORDER BY symbol ASC
    """

    try:
        df = pd.read_sql_query(query, engine)

        if df.empty:
            st.warning("⚠️ No oracle price data available.")
            st.info("💡 Run: `python data/migrations/init_oracle_prices.py` to populate initial prices.")
            return

        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tokens", len(df))
        with col2:
            cg_count = df['coingecko'].notna().sum()
            st.metric("CoinGecko", f"{cg_count}/{len(df)}")
        with col3:
            pyth_count = df['pyth'].notna().sum()
            st.metric("Pyth", f"{pyth_count}/{len(df)}")
        with col4:
            dl_count = df['defillama'].notna().sum()
            st.metric("DeFi Llama", f"{dl_count}/{len(df)}")

        st.markdown("---")

        # Transform data for display
        display_df = pd.DataFrame()
        display_df['Token'] = df['symbol']
        display_df['Contract'] = df['token_contract'].apply(format_contract_address)
        display_df['CoinGecko'] = df['coingecko']
        display_df['CG Time'] = pd.to_datetime(df['coingecko_time'])
        display_df['Pyth'] = df['pyth']
        display_df['Pyth Time'] = pd.to_datetime(df['pyth_time'])
        display_df['DeFi Llama'] = df['defillama']
        display_df['DL Time'] = pd.to_datetime(df['defillama_time'])
        display_df['Confidence'] = df['defillama_confidence']
        display_df['Latest Price'] = df['latest_price']
        display_df['Source'] = df['latest_oracle']
        display_df['Age'] = df['latest_time'].apply(compute_timestamp_age)

        # Display table
        st.dataframe(
            display_df,
            column_config={
                "Token": st.column_config.TextColumn("Token", width="small"),
                "Contract": st.column_config.TextColumn("Contract", width="medium"),
                "CoinGecko": st.column_config.NumberColumn(
                    "CoinGecko", format="$%.6f"
                ),
                "CG Time": st.column_config.DatetimeColumn(
                    "CG Time", format="MMM DD, HH:mm"
                ),
                "Pyth": st.column_config.NumberColumn(
                    "Pyth", format="$%.6f"
                ),
                "Pyth Time": st.column_config.DatetimeColumn(
                    "Pyth Time", format="MMM DD, HH:mm"
                ),
                "DeFi Llama": st.column_config.NumberColumn(
                    "DeFi Llama", format="$%.6f"
                ),
                "DL Time": st.column_config.DatetimeColumn(
                    "DL Time", format="MMM DD, HH:mm"
                ),
                "Confidence": st.column_config.NumberColumn(
                    "Conf", format="%.2f"
                ),
                "Latest Price": st.column_config.NumberColumn(
                    "Latest", format="$%.6f"
                ),
                "Source": st.column_config.TextColumn("Source", width="small"),
                "Age": st.column_config.NumberColumn("Age (sec)", width="small"),
            },
            hide_index=True,
            width='stretch'
        )

        st.caption("💡 Latest Price shows the most recent price across all oracles.")

    except Exception as e:
        st.error(f"❌ Error loading oracle prices: {e}")
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


def render_allocator_settings_manager():
    """
    Render the allocator settings preset manager.

    Allows users to:
    - Load saved presets
    - Save current settings as named preset
    - Delete presets
    - See current preset and last modified time

    Returns:
        None (updates session state)
    """
    st.markdown("#### 💾 Settings Presets")

    try:
        from analysis.allocator_settings_service import AllocatorSettingsService

        conn = get_db_connection()
        service = AllocatorSettingsService(conn)

        # Get all presets
        presets_df = service.get_all_presets()

        # Build preset options: Last Used + named presets
        preset_options = ['Last Used Settings']
        preset_ids = ['last_used']

        if not presets_df.empty:
            for _, row in presets_df.iterrows():
                preset_options.append(row['settings_name'])
                preset_ids.append(row['settings_id'])

        # 4-column layout
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

        with col1:
            selected_preset_idx = st.selectbox(
                "Select Preset",
                range(len(preset_options)),
                format_func=lambda i: preset_options[i],
                key="preset_selector"
            )

        selected_id = preset_ids[selected_preset_idx]

        with col2:
            if st.button("📥 Load", width='stretch'):
                loaded = service.load_settings(selected_id)
                if loaded:
                    st.session_state.allocation_constraints = loaded['allocator_constraints']
                    st.session_state.sidebar_filters = loaded.get('sidebar_filters', {})

                    # Extract and restore portfolio_size
                    if 'portfolio_size' in loaded['allocator_constraints']:
                        st.session_state.portfolio_size = loaded['allocator_constraints']['portfolio_size']

                    st.session_state.current_preset_id = selected_id
                    st.session_state.current_preset_name = preset_options[selected_preset_idx]
                    st.success(f"✅ Loaded: {preset_options[selected_preset_idx]}")
                    st.rerun()
                else:
                    st.error("❌ Failed to load preset")

        with col3:
            if st.button("💾 Save As...", width='stretch'):
                st.session_state.show_save_preset_dialog = True
                st.rerun()

        with col4:
            delete_disabled = (selected_id == 'last_used')
            if st.button("🗑️ Delete", width='stretch', disabled=delete_disabled):
                if not delete_disabled:
                    success = service.delete_preset(selected_id)
                    if success:
                        st.success(f"✅ Deleted: {preset_options[selected_preset_idx]}")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete preset")

        # Save preset dialog
        if st.session_state.get('show_save_preset_dialog', False):
            with st.form("save_preset_form"):
                st.markdown("##### Save Current Settings As Preset")

                preset_name = st.text_input("Preset Name", placeholder="e.g., Conservative Strategy")
                preset_description = st.text_area("Description (optional)",
                    placeholder="e.g., Low risk, high stablecoin allocation")

                col_save, col_cancel = st.columns(2)

                with col_save:
                    save_clicked = st.form_submit_button("💾 Save", width='stretch')

                with col_cancel:
                    cancel_clicked = st.form_submit_button("❌ Cancel", width='stretch')

                if save_clicked:
                    if not preset_name or preset_name.strip() == "":
                        st.error("❌ Preset name cannot be empty")
                    else:
                        # Capture current settings from session state
                        allocator_constraints = st.session_state.get('allocation_constraints', {}).copy()
                        sidebar_filters = st.session_state.get('sidebar_filters', {})

                        # Capture portfolio_size from session state
                        portfolio_size = st.session_state.get('portfolio_size', settings.DEFAULT_DEPLOYMENT_USD)
                        allocator_constraints['portfolio_size'] = portfolio_size

                        preset_id = service.create_named_preset(
                            preset_name=preset_name.strip(),
                            allocator_constraints=allocator_constraints,
                            sidebar_filters=sidebar_filters,
                            description=preset_description.strip() if preset_description else None
                        )

                        st.session_state.show_save_preset_dialog = False
                        st.session_state.current_preset_id = preset_id
                        st.session_state.current_preset_name = preset_name.strip()
                        st.success(f"✅ Saved preset: {preset_name}")
                        st.rerun()

                if cancel_clicked:
                    st.session_state.show_save_preset_dialog = False
                    st.rerun()

        # Current preset indicator
        current_preset = st.session_state.get('current_preset_name', 'Last Used Settings')
        st.caption(f"📌 Current: **{current_preset}**")

        conn.close()

    except Exception as e:
        st.error(f"⚠️ Error loading settings manager: {e}")
        print(f"Settings manager error: {e}")


def render_sidebar_filters(display_results: pd.DataFrame):
    """
    Render sidebar filters with session state persistence.

    Args:
        display_results: Current filtered results (for token/protocol options)

    Returns:
        tuple: (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1, stablecoin_only, min_apr, token_filter, protocol_filter)
    """
    st.header("⚙️ Settings")

    # Initialize sidebar_filters in session_state if not exists
    if 'sidebar_filters' not in st.session_state:
        st.session_state.sidebar_filters = {
            'liquidation_distance': settings.DEFAULT_LIQUIDATION_DISTANCE,
            'deployment_usd': settings.DEFAULT_DEPLOYMENT_USD,
            'force_usdc_start': False,
            'force_token3_equals_token1': False,
            'stablecoin_only': False,
            'min_net_apr': 0.0,
            'token_filter': [],
            'protocol_filter': []
        }

    filters = st.session_state.sidebar_filters

    # Liquidation Distance
    col1, col2 = st.columns([30, 7])
    with col1:
        st.markdown("**Liquidation Distance (%)**")
    with col2:
        # Use saved value from session_state
        default_liq = filters.get('liquidation_distance', settings.DEFAULT_LIQUIDATION_DISTANCE)
        liq_dist_text = st.text_input(
            label="Liquidation Distance (%)",
            value=str(int(default_liq * 100)),
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
        # Use saved value from session_state
        default_deployment = filters.get('deployment_usd', settings.DEFAULT_DEPLOYMENT_USD)
        deployment_text = st.text_input(
            label="Deployment USD",
            value=str(int(default_deployment)),
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

    # Toggles - Use saved values from session_state
    force_usdc_start = st.toggle(
        "Force token1 = USDC",
        value=filters.get('force_usdc_start', False),
        help="When enabled, only shows strategies starting with USDC"
    )

    force_token3_equals_token1 = st.toggle(
        "Force token3 = token1 (no conversion)",
        value=filters.get('force_token3_equals_token1', False),
        help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
    )

    stablecoin_only = st.toggle(
        "Stablecoin Only",
        value=filters.get('stablecoin_only', False),
        help="When enabled, only shows strategies where all three tokens are stablecoins"
    )

    st.markdown("---")

    # Filters section
    st.subheader("🔍 Filters")

    min_apr = st.number_input(
        "Min Net APR (%)",
        value=filters.get('min_net_apr', 0.0),
        step=0.5
    )

    token_filter = st.multiselect(
        "Filter by Token",
        options=sorted(set(display_results['token1']).union(set(display_results['token2'])).union(set(display_results['token3']))) if not display_results.empty else [],
        default=filters.get('token_filter', [])
    )

    protocol_filter = st.multiselect(
        "Filter by Protocol",
        options=['Navi', 'AlphaFi', 'Suilend', 'ScallopLend', 'ScallopBorrow'],
        default=filters.get('protocol_filter', [])
    )

    # Update session_state before returning
    st.session_state.sidebar_filters.update({
        'liquidation_distance': liquidation_distance,
        'deployment_usd': deployment_usd,
        'force_usdc_start': force_usdc_start,
        'force_token3_equals_token1': force_token3_equals_token1,
        'stablecoin_only': stablecoin_only,
        'min_net_apr': min_apr,
        'token_filter': token_filter,
        'protocol_filter': protocol_filter
    })

    return (liquidation_distance, deployment_usd, force_usdc_start, force_token3_equals_token1,
            stablecoin_only, min_apr, token_filter, protocol_filter)

def render_allocation_tab(all_strategies_df: pd.DataFrame):
    """
    Render portfolio allocation tab with constraint-based selection.

    Allows users to:
    - Set portfolio size
    - Configure allocation constraints
    - Set stablecoin preferences
    - Generate optimal portfolio
    - View portfolio preview with adjusted APR

    Args:
        all_strategies_df: DataFrame with all available strategies
    """
    st.markdown("### 🎯 Portfolio Allocation")
    st.markdown(
        "Build a diversified portfolio using constraint-based selection. "
        "The allocator ranks strategies by adjusted APR (blended APR with stablecoin penalties) "
        "and greedily allocates capital while respecting exposure limits."
    )

    # Settings Preset Manager
    render_allocator_settings_manager()

    st.markdown("---")

    # Initialize constraints in session state
    if 'allocation_constraints' not in st.session_state:
        from config.settings import DEFAULT_ALLOCATION_CONSTRAINTS
        st.session_state.allocation_constraints = DEFAULT_ALLOCATION_CONSTRAINTS.copy()

    constraints = st.session_state.allocation_constraints

    st.markdown("---")

    # Portfolio Size Input
    col_size1, col_size2 = st.columns(2)
    with col_size1:
        # Try to get portfolio_size from multiple sources (fallback chain)
        default_portfolio_size = (
            st.session_state.get('portfolio_size') or
            st.session_state.get('allocation_constraints', {}).get('portfolio_size') or
            settings.DEFAULT_DEPLOYMENT_USD
        )

        portfolio_size = st.number_input(
            "Portfolio Size (USD)",
            min_value=100.0,
            max_value=1000000.0,
            value=default_portfolio_size,
            step=500.0,
            format="%.2f",
            key="portfolio_size_input"
        )
        st.session_state.portfolio_size = portfolio_size

    with col_size2:
        # Max single allocation % constraint
        default_max_single_pct = constraints.get('max_single_allocation_pct', 0.40)

        max_single_allocation_pct = st.number_input(
            "Max Single Strategy (%)",
            min_value=1.0,
            max_value=100.0,
            value=default_max_single_pct * 100,
            step=5.0,
            format="%.0f",
            help="Maximum percentage of portfolio that can be allocated to a single strategy",
            key="max_single_allocation_pct_input"
        )
        constraints['max_single_allocation_pct'] = max_single_allocation_pct / 100

    # Info note below both inputs
    st.info(f"💰 Allocating **${portfolio_size:,.0f}** across selected strategies (max **{max_single_allocation_pct:.0f}%** per strategy)")

    st.markdown("---")
    st.subheader("⚙️ Allocation Constraints")

    # ============================================================
    # EXPOSURE LIMITS SECTION (2x2 grid)
    # ============================================================
    st.markdown("#### Exposure Limits")

    # First row: Default limits for token2 (non-stablecoin) and stablecoin
    col_token2, col_stablecoin = st.columns(2)

    with col_token2:
        st.markdown("**Max Token2 Exposure**")
        st.caption("Applies to non-stablecoin tokens (WAL, DEEP, SUI, etc.)")

        constraints['token2_exposure_limit'] = st.number_input(
            "Max Token2 Exposure (%)",
            min_value=0,
            max_value=100,
            value=int(constraints.get('token2_exposure_limit', constraints.get('token_exposure_limit', 0.30)) * 100),
            step=5,
            help="Maximum allocation for non-stablecoin tokens",
            key="token2_exposure_input"
        ) / 100.0

    with col_stablecoin:
        st.markdown("**Max Stablecoin Exposure**")
        st.caption("Applies to stablecoins (USDC, USDT, etc.)")

        stablecoin_limit_input = st.number_input(
            "Max Stablecoin Exposure (%) or -1 for ∞",
            min_value=-1,
            max_value=200,
            value=int(constraints.get('stablecoin_exposure_limit', -1)) if constraints.get('stablecoin_exposure_limit', -1) >= 0 else -1,
            step=5,
            help="Maximum allocation for stablecoins. -1 = unlimited",
            key="stablecoin_exposure_input"
        )

        # Store as -1 for infinite, or as decimal for bounded
        if stablecoin_limit_input < 0:
            constraints['stablecoin_exposure_limit'] = -1
            st.info("∞ Unlimited stablecoin exposure")
        else:
            constraints['stablecoin_exposure_limit'] = stablecoin_limit_input / 100.0
            st.info(f"Max {stablecoin_limit_input}% stablecoin exposure")

    # Second row: Per-token overrides for token2 (non-stablecoin) and stablecoin
    col_token2_overrides, col_stablecoin_overrides = st.columns(2)

    with col_token2_overrides:
        # Per-Token2 Exposure Overrides (NON-STABLECOINS ONLY)
        with st.expander("🎚️ Per-Token2 Exposure Overrides"):
            st.caption("Set custom limits for specific non-stablecoin tokens")

            token2_overrides = constraints.get('token2_exposure_overrides', constraints.get('token_exposure_overrides', {}))

            # Get unique NON-STABLECOIN tokens from strategies
            if not all_strategies_df.empty:
                all_tokens = set()
                for col in ['token1', 'token2', 'token3']:
                    if col in all_strategies_df.columns:
                        all_tokens.update(all_strategies_df[col].unique())
                # Filter out stablecoins
                from config.stablecoins import STABLECOIN_SYMBOLS
                non_stablecoin_tokens = sorted([t for t in all_tokens if t not in STABLECOIN_SYMBOLS])
            else:
                non_stablecoin_tokens = ['SUI', 'DEEP', 'CETUS', 'WAL']

            if non_stablecoin_tokens:
                # Add override controls
                col_token, col_limit, col_action = st.columns([2, 1, 1])
                with col_token:
                    selected_token = st.selectbox(
                        "Select Non-Stablecoin Token",
                        options=non_stablecoin_tokens,
                        key="token2_override_select"
                    )
                with col_limit:
                    override_limit = st.number_input(
                        "Max Exposure (%)",
                        min_value=0,
                        max_value=100,
                        value=int(token2_overrides.get(selected_token, 30)),
                        step=5,
                        key="token2_override_limit"
                    )
                with col_action:
                    st.write("")  # Spacer
                    st.write("")  # Spacer
                    if st.button("Add/Update", key="add_token2_override"):
                        token2_overrides[selected_token] = override_limit / 100.0
                        constraints['token2_exposure_overrides'] = token2_overrides
                        st.success(f"✓ {selected_token}: {override_limit}%")
                        st.rerun()

                # Show current overrides
                if token2_overrides:
                    st.markdown("**Current Overrides:**")
                    for token, limit in sorted(token2_overrides.items()):
                        col_name, col_val, col_remove = st.columns([2, 1, 1])
                        with col_name:
                            st.text(token)
                        with col_val:
                            st.text(f"{limit*100:.0f}%")
                        with col_remove:
                            if st.button("❌", key=f"remove_token2_override_{token}"):
                                del token2_overrides[token]
                                constraints['token2_exposure_overrides'] = token2_overrides
                                st.rerun()
                else:
                    st.info("No overrides. All non-stablecoins use default limit.")
            else:
                st.info("No non-stablecoin tokens available")

    with col_stablecoin_overrides:
        # Per-Stablecoin Exposure Overrides (STABLECOINS ONLY)
        with st.expander("🎚️ Per-Stablecoin Exposure Overrides"):
            st.caption("Set custom limits for specific stablecoins")

            stablecoin_overrides = constraints.get('stablecoin_exposure_overrides', {})

            # Get unique STABLECOIN tokens from strategies
            if not all_strategies_df.empty:
                all_tokens = set()
                for col in ['token1', 'token2', 'token3']:
                    if col in all_strategies_df.columns:
                        all_tokens.update(all_strategies_df[col].unique())
                # Filter to stablecoins only
                from config.stablecoins import STABLECOIN_SYMBOLS
                stablecoin_tokens = sorted([t for t in all_tokens if t in STABLECOIN_SYMBOLS])
            else:
                stablecoin_tokens = list(STABLECOIN_SYMBOLS)

            if stablecoin_tokens:
                # Add override controls
                col_token, col_limit, col_action = st.columns([2, 1, 1])
                with col_token:
                    selected_stablecoin = st.selectbox(
                        "Select Stablecoin",
                        options=stablecoin_tokens,
                        key="stablecoin_override_select"
                    )
                with col_limit:
                    override_limit = st.number_input(
                        "Max Exposure (%) or -1 for ∞",
                        min_value=-1,
                        max_value=200,
                        value=int(stablecoin_overrides.get(selected_stablecoin, -1)) if stablecoin_overrides.get(selected_stablecoin, -1) >= 0 else -1,
                        step=5,
                        key="stablecoin_override_limit"
                    )
                with col_action:
                    st.write("")  # Spacer
                    st.write("")  # Spacer
                    if st.button("Add/Update", key="add_stablecoin_override"):
                        if override_limit < 0:
                            stablecoin_overrides[selected_stablecoin] = -1
                            st.success(f"✓ {selected_stablecoin}: ∞ (unlimited)")
                        else:
                            stablecoin_overrides[selected_stablecoin] = override_limit / 100.0
                            st.success(f"✓ {selected_stablecoin}: {override_limit}%")
                        constraints['stablecoin_exposure_overrides'] = stablecoin_overrides
                        st.rerun()

                # Show current overrides
                if stablecoin_overrides:
                    st.markdown("**Current Overrides:**")
                    for token, limit in sorted(stablecoin_overrides.items()):
                        col_name, col_val, col_remove = st.columns([2, 1, 1])
                        with col_name:
                            st.text(token)
                        with col_val:
                            if limit < 0:
                                st.text("∞")
                            else:
                                st.text(f"{limit*100:.0f}%")
                        with col_remove:
                            if st.button("❌", key=f"remove_stablecoin_override_{token}"):
                                del stablecoin_overrides[token]
                                constraints['stablecoin_exposure_overrides'] = stablecoin_overrides
                                st.rerun()
                else:
                    st.info("No overrides. All stablecoins use default limit.")
            else:
                st.info("No stablecoin tokens available")

    st.markdown("---")

    # ============================================================
    # PROTOCOL & STRATEGY LIMITS (horizontal)
    # ============================================================
    col_protocol, col_max_strategies = st.columns(2)

    with col_protocol:
        constraints['protocol_exposure_limit'] = st.number_input(
            "Max Protocol Exposure (%)",
            min_value=0,
            max_value=100,
            value=int(constraints.get('protocol_exposure_limit', 0.40) * 100),
            step=5,
            help="Maximum portfolio allocation to any single protocol",
            key="protocol_exposure_input"
        ) / 100.0

    with col_max_strategies:
        constraints['max_strategies'] = st.number_input(
            "Max Number of Strategies",
            min_value=1,
            max_value=100,
            value=constraints.get('max_strategies', 5),
            step=1,
            help="Maximum strategies in portfolio",
            key="max_strategies_input"
        )

    st.markdown("---")

    # Stablecoin Preferences
    constraints = render_stablecoin_preferences(constraints)

    st.markdown("---")

    # ============================================================
    # APR WEIGHTINGS (horizontal layout - 4 columns)
    # ============================================================
    st.markdown("#### APR Weightings")
    st.caption("Enter any values - they'll be auto-normalized to 100%. Example: 1,2,2,5 → 10%,20%,20%,50%")

    col_net, col_5d, col_30d, col_90d = st.columns(4)

    apr_weights = constraints.get('apr_weights', {})

    with col_net:
        w_net = st.number_input(
            "Net APR Weight",
            min_value=0.0,
            value=float(apr_weights.get('net_apr', 0.30)*100),
            step=1.0,
            key="w_net"
        )

    with col_5d:
        w_5d = st.number_input(
            "5-Day APR Weight",
            min_value=0.0,
            value=float(apr_weights.get('apr5', 0.30)*100),
            step=1.0,
            key="w_5d"
        )

    with col_30d:
        w_30d = st.number_input(
            "30-Day APR Weight",
            min_value=0.0,
            value=float(apr_weights.get('apr30', 0.30)*100),
            step=1.0,
            key="w_30d"
        )

    with col_90d:
        w_90d = st.number_input(
            "90-Day APR Weight",
            min_value=0.0,
            value=float(apr_weights.get('apr90', 0.10)*100),
            step=1.0,
            key="w_90d"
        )

    # Calculate sum and normalize
    weight_sum = w_net + w_5d + w_30d + w_90d

    if weight_sum > 0:
        # Normalize to percentages
        normalized_net = (w_net / weight_sum) * 100
        normalized_5d = (w_5d / weight_sum) * 100
        normalized_30d = (w_30d / weight_sum) * 100
        normalized_90d = (w_90d / weight_sum) * 100

        # Show normalized percentages
        st.success(
            f"✓ Normalized: Net={normalized_net:.1f}%, 5d={normalized_5d:.1f}%, "
            f"30d={normalized_30d:.1f}%, 90d={normalized_90d:.1f}%"
        )

        # Store as decimals (0-1 range) - following Design Note #5
        apr_weights['net_apr'] = normalized_net / 100.0
        apr_weights['apr5'] = normalized_5d / 100.0
        apr_weights['apr30'] = normalized_30d / 100.0
        apr_weights['apr90'] = normalized_90d / 100.0
    else:
        st.warning("⚠️ All weights are 0. Using equal weights (25% each).")
        # Default to equal weights
        apr_weights['net_apr'] = 0.25
        apr_weights['apr5'] = 0.25
        apr_weights['apr30'] = 0.25
        apr_weights['apr90'] = 0.25

    constraints['apr_weights'] = apr_weights

    # Save constraints to session state
    st.session_state.allocation_constraints = constraints

    st.markdown("---")

    # Display all strategies ranked by adjusted APR
    st.markdown("### 📋 All Strategies (Ranked by Adjusted APR)")
    st.caption(
        "Strategies are filtered by confidence threshold and ranked by adjusted APR "
        "(blended APR × stablecoin multiplier). This is the ranking order used for portfolio allocation."
    )

    if not all_strategies_df.empty:
        try:
            from analysis.portfolio_allocator import PortfolioAllocator

            # Initialize allocator
            allocator = PortfolioAllocator(all_strategies_df)

            # Apply same filtering and ranking as select_portfolio
            strategies = all_strategies_df.copy()

            # Filter by confidence
            if 'confidence' in strategies.columns:
                min_confidence = constraints.get('min_apy_confidence', 0.0)
                strategies = strategies[strategies['confidence'] >= min_confidence].copy()

            if strategies.empty:
                st.warning("⚠️ No strategies meet the confidence threshold. Lower the threshold or adjust filters.")
            else:
                # Calculate blended APR
                apr_weights = constraints['apr_weights']
                strategies['blended_apr'] = strategies.apply(
                    lambda row: allocator.calculate_blended_apr(row, apr_weights),
                    axis=1
                )

                # Calculate adjusted APR with stablecoin preferences
                stablecoin_prefs = constraints['stablecoin_preferences']
                adjusted_results = strategies.apply(
                    lambda row: allocator.calculate_adjusted_apr(
                        row,
                        row['blended_apr'],
                        stablecoin_prefs
                    ),
                    axis=1
                )

                # Unpack results
                strategies['stablecoin_multiplier'] = adjusted_results.apply(lambda x: x['stablecoin_multiplier'])
                strategies['adjusted_apr'] = adjusted_results.apply(lambda x: x['adjusted_apr'])
                strategies['stablecoins_in_strategy'] = adjusted_results.apply(lambda x: x['stablecoins_in_strategy'])

                # Sort by adjusted APR (descending)
                strategies = strategies.sort_values('adjusted_apr', ascending=False)

                # Display table - select columns (check if max_size_usd exists)
                base_columns = [
                    'token1', 'token2', 'token3',
                    'protocol_a', 'protocol_b',
                    'net_apr', 'apr5', 'apr30', 'blended_apr', 'stablecoin_multiplier', 'adjusted_apr'
                ]

                # Add max_size if it exists (explicit error handling)
                try:
                    if 'max_size' in strategies.columns:
                        base_columns.append('max_size')
                except Exception as e:
                    print(f"⚠️  Error checking for 'max_size' column: {e}")
                    print(f"    Available columns: {list(strategies.columns)}")

                display_df = strategies[base_columns].copy()

                # Format for display
                display_df['net_apr'] = display_df['net_apr'].apply(lambda x: f"{x*100:.2f}%")
                display_df['apr5'] = display_df['apr5'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A")
                display_df['apr30'] = display_df['apr30'].apply(lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A")
                display_df['blended_apr'] = display_df['blended_apr'].apply(lambda x: f"{x*100:.2f}%")
                display_df['stablecoin_multiplier'] = display_df['stablecoin_multiplier'].apply(lambda x: f"{x:.2f}x")
                display_df['adjusted_apr'] = display_df['adjusted_apr'].apply(lambda x: f"{x*100:.2f}%")

                # Format max_size column if present
                try:
                    if 'max_size' in display_df.columns:
                        display_df['max_size'] = display_df['max_size'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
                except KeyError as e:
                    print(f"⚠️  KeyError formatting 'max_size': {e}")
                    print(f"    Available columns in display_df: {list(display_df.columns)}")

                # Rename columns
                column_names = [
                    'Token1', 'Token2', 'Token3',
                    'Protocol A', 'Protocol B',
                    'Net APR', 'APR5', 'APR30', 'Blended APR', 'Stable Mult', 'Adjusted APR'
                ]

                # Add max_size to rename list if present
                try:
                    if 'max_size' in display_df.columns:
                        column_names.append('Max Size')
                except Exception as e:
                    print(f"⚠️  Error checking for 'max_size' in display_df for rename: {e}")
                    print(f"    Available columns: {list(display_df.columns)}")

                display_df.columns = column_names

                # Show count
                st.info(f"📊 Showing **{len(display_df)}** strategies meeting confidence threshold")

                # Display table with fixed height
                st.dataframe(display_df, height=400, width='stretch')

        except Exception as e:
            st.error(f"❌ Error calculating strategy rankings: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    else:
        st.warning("⚠️ No strategies available. Adjust filters in sidebar.")

    st.markdown("---")

    # Portfolio Name Input
    st.markdown("##### 📝 Portfolio Name")
    portfolio_name = st.text_input(
        "Enter portfolio name (leave empty for auto-generated name)",
        value="",
        key="portfolio_name_input",
        placeholder="e.g., Conservative USDC Portfolio"
    )

    # Generate Portfolio Button
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    with col_btn1:
        generate_clicked = st.button("🎲 Generate Portfolio", type="primary", width='stretch')
    with col_btn2:
        if st.button("🔄 Reset Constraints", width='stretch'):
            from config.settings import DEFAULT_ALLOCATION_CONSTRAINTS
            st.session_state.allocation_constraints = DEFAULT_ALLOCATION_CONSTRAINTS.copy()
            st.rerun()

    # Generate and display portfolio
    if generate_clicked:
        if all_strategies_df.empty:
            st.warning("⚠️ No strategies available. Adjust filters in sidebar.")
            return

        # Generate unique portfolio name if empty
        from datetime import datetime
        if not portfolio_name or portfolio_name.strip() == "":
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_portfolio_name = f"Portfolio_{timestamp_str}"
        else:
            final_portfolio_name = portfolio_name.strip()

        # Check for duplicate names (simple check in session state)
        existing_names = st.session_state.get('portfolio_names', set())
        if final_portfolio_name in existing_names:
            st.error(f"❌ Portfolio name '{final_portfolio_name}' already exists. Please choose a different name.")
            return

        # ============================================================
        # AUTO-SAVE: Save current settings to "last_used"
        # ============================================================
        try:
            from analysis.allocator_settings_service import AllocatorSettingsService

            conn = get_db_connection()
            service = AllocatorSettingsService(conn)

            # Capture current allocator constraints
            allocator_constraints = constraints.copy()
            # Add portfolio_size to constraints
            allocator_constraints['portfolio_size'] = portfolio_size

            # Capture current sidebar filters from session state
            sidebar_filters = st.session_state.get('sidebar_filters', {})

            # Save to last_used
            service.save_settings(
                settings_id='last_used',
                settings_name='Last Used Settings',
                allocator_constraints=allocator_constraints,
                sidebar_filters=sidebar_filters
            )

            conn.close()
            print("✅ Auto-saved settings to last_used")
        except Exception as e:
            # Don't block portfolio generation on save failure
            print(f"⚠️  Warning: Failed to auto-save settings: {e}")

        # ============================================================
        # Continue with portfolio generation
        # ============================================================
        st.markdown("---")
        with st.spinner("🔄 Generating optimal portfolio..."):
            try:
                from analysis.portfolio_allocator import PortfolioAllocator

                # Initialize allocator
                allocator = PortfolioAllocator(all_strategies_df)

                # Select portfolio
                portfolio_df, debug_info = allocator.select_portfolio(
                    portfolio_size=portfolio_size,
                    constraints=constraints
                )

                # Save to session state
                st.session_state.generated_portfolio = portfolio_df
                st.session_state.portfolio_debug_info = debug_info
                st.session_state.portfolio_strategies_source = all_strategies_df  # For reconstructing initial matrix
                st.session_state.portfolio_name = final_portfolio_name
                st.session_state.portfolio_generated = True

                # Track portfolio names
                if 'portfolio_names' not in st.session_state:
                    st.session_state.portfolio_names = set()
                st.session_state.portfolio_names.add(final_portfolio_name)

            except Exception as e:
                st.error(f"❌ Error generating portfolio: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                return

    # Display portfolio if generated
    if st.session_state.get('portfolio_generated', False) and 'generated_portfolio' in st.session_state:
        portfolio_df = st.session_state.generated_portfolio
        render_portfolio_preview(portfolio_df, portfolio_size, constraints)


def render_stablecoin_preferences(constraints: Dict) -> Dict:
    """
    Render stablecoin preference multiplier inputs for portfolio allocation.

    Allows users to set preference multipliers for different stablecoins.
    Strategies containing lower-multiplier stablecoins will rank lower in allocation.

    Args:
        constraints: Constraint dictionary containing 'stablecoin_preferences'

    Returns:
        Updated constraints dict with modified stablecoin preferences
    """
    st.markdown("##### 🪙 Stablecoin Preferences")
    st.markdown(
        "Set preference multipliers for stablecoins. "
        "Strategies containing lower-multiplier stablecoins will rank lower. "
        "**Example:** 0.9 multiplier = 10% APR penalty (10% becomes 9%)."
    )

    # Get current preferences from constraints or use defaults
    from config.settings import DEFAULT_STABLECOIN_PREFERENCES
    stablecoin_prefs = constraints.get(
        'stablecoin_preferences',
        DEFAULT_STABLECOIN_PREFERENCES.copy()
    )

    # Create editable inputs for each stablecoin in 3 columns
    stablecoin_list = sorted(stablecoin_prefs.keys())
    num_cols = 3
    cols = st.columns(num_cols)

    updated_prefs = {}
    for i, stablecoin in enumerate(stablecoin_list):
        col = cols[i % num_cols]
        with col:
            updated_prefs[stablecoin] = st.number_input(
                f"{stablecoin}",
                min_value=0.0,
                max_value=1.0,
                value=float(stablecoin_prefs[stablecoin]),
                step=0.05,
                format="%.2f",
                help=f"Multiplier for strategies containing {stablecoin}. "
                     f"Current: {stablecoin_prefs[stablecoin]:.2f}x",
                key=f"stablecoin_pref_{stablecoin}"
            )

    # Add custom stablecoin expander
    with st.expander("➕ Add Custom Stablecoin"):
        custom_col1, custom_col2, custom_col3 = st.columns([2, 1, 1])
        with custom_col1:
            custom_token = st.text_input(
                "Token Symbol",
                key="custom_stablecoin_token",
                help="Enter stablecoin symbol (e.g., SUSD, USDY)"
            )
        with custom_col2:
            custom_multiplier = st.number_input(
                "Multiplier",
                min_value=0.0,
                max_value=1.0,
                value=0.90,
                step=0.05,
                format="%.2f",
                key="custom_stablecoin_multiplier"
            )
        with custom_col3:
            if st.button("Add", key="add_custom_stablecoin"):
                if custom_token:
                    updated_prefs[custom_token.upper()] = custom_multiplier
                    st.success(f"Added {custom_token.upper()} with {custom_multiplier:.2f}x multiplier")
                    st.rerun()

    # Update constraints
    constraints['stablecoin_preferences'] = updated_prefs

    # Show summary
    avg_multiplier = sum(updated_prefs.values()) / len(updated_prefs) if updated_prefs else 1.0
    st.caption(
        f"📊 {len(updated_prefs)} stablecoins configured | "
        f"Average multiplier: {avg_multiplier:.2f}x"
    )

    return constraints


def render_portfolio_preview(portfolio_df: pd.DataFrame, portfolio_size: float, constraints: Dict):
    """
    Display generated portfolio with strategy details and adjusted APR comparison.

    Shows:
    - Portfolio summary (total allocated, weighted APR, utilization)
    - Strategy table with blended vs adjusted APR
    - Exposure breakdowns
    - Stablecoin penalty impact

    Args:
        portfolio_df: DataFrame with selected strategies and allocations
        portfolio_size: Total portfolio size in USD
        constraints: Constraint settings used for allocation
    """
    if portfolio_df.empty:
        st.warning("⚠️ No strategies selected. Try adjusting constraints or confidence thresholds.")
        return

    # Calculate portfolio metrics
    total_allocated = portfolio_df['allocation_usd'].sum()
    utilization_pct = (total_allocated / portfolio_size) * 100 if portfolio_size > 0 else 0
    weighted_blended_apr = (
        (portfolio_df['blended_apr'] * portfolio_df['allocation_usd']).sum() / total_allocated
        if total_allocated > 0 else 0
    )
    weighted_adjusted_apr = (
        (portfolio_df['adjusted_apr'] * portfolio_df['allocation_usd']).sum() / total_allocated
        if total_allocated > 0 else 0
    )

    # Calculate weighted averages for net_apr, apr5, apr30
    weighted_net_apr = (
        (portfolio_df['net_apr'] * portfolio_df['allocation_usd']).sum() / total_allocated
        if total_allocated > 0 else 0
    )
    weighted_apr5 = (
        (portfolio_df['apr5'] * portfolio_df['allocation_usd']).sum() / total_allocated
        if total_allocated > 0 else 0
    )
    weighted_apr30 = (
        (portfolio_df['apr30'] * portfolio_df['allocation_usd']).sum() / total_allocated
        if total_allocated > 0 else 0
    )

    num_strategies = len(portfolio_df)

    # Portfolio Summary
    portfolio_name = st.session_state.get('portfolio_name', 'Portfolio')
    st.success(f"✅ Portfolio Generated: **{portfolio_name}** ({num_strategies} strategies)")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Allocated", f"${total_allocated:,.0f}")
    with col2:
        st.metric("Weighted Avg Net APR", f"{weighted_net_apr*100:.2f}%")
    with col3:
        st.metric("Weighted Avg APR5", f"{weighted_apr5*100:.2f}%")
    with col4:
        st.metric("Weighted Avg APR30", f"{weighted_apr30*100:.2f}%")
    with col5:
        st.metric("Weighted APR (Adjusted)", f"{weighted_adjusted_apr*100:.2f}%")

    st.markdown("---")

    # Strategy Details Table
    st.markdown("### 📋 Selected Strategies")
    st.caption(
        "Strategies ranked by **Adjusted APR** (Blended APR × Stablecoin Penalty). "
        "Blended APR is a weighted average of historical APRs, used for ranking only."
    )

    # Prepare display DataFrame - select columns (check if max_size_usd exists)
    base_columns = [
        'token1', 'token2', 'token3',
        'protocol_a', 'protocol_b',
        'net_apr', 'blended_apr', 'adjusted_apr',
        'stablecoin_multiplier', 'stablecoins_in_strategy',
        'allocation_usd'
    ]

    # Add max_size if it exists (explicit error handling)
    # Add max_size if it exists (explicit error handling)
    try:
        if 'max_size' in portfolio_df.columns:
            base_columns.append('max_size')
    except Exception as e:
        print(f"⚠️  Error checking for 'max_size' column in portfolio_df: {e}")
        print(f"    Available columns: {list(portfolio_df.columns)}")

    display_df = portfolio_df[base_columns].copy()

    # Format columns
    display_df['net_apr'] = display_df['net_apr'].apply(lambda x: f"{x*100:.2f}%")
    display_df['blended_apr'] = display_df['blended_apr'].apply(lambda x: f"{x*100:.2f}%")
    display_df['adjusted_apr'] = display_df['adjusted_apr'].apply(lambda x: f"{x*100:.2f}%")
    display_df['stablecoin_multiplier'] = display_df['stablecoin_multiplier'].apply(
        lambda x: f"{x:.2f}x" if x < 1.0 else "✓" if x == 1.0 else f"{x:.2f}x"
    )
    display_df['stablecoins_in_strategy'] = display_df['stablecoins_in_strategy'].apply(
        lambda x: ', '.join(x) if isinstance(x, list) and x else '-'
    )
    display_df['allocation_usd'] = display_df['allocation_usd'].apply(lambda x: f"${x:,.0f}")

    # Format max_size column if present
    try:
        if 'max_size' in display_df.columns:
            display_df['max_size'] = display_df['max_size'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A")
    except KeyError as e:
        print(f"⚠️  KeyError formatting 'max_size' in portfolio display: {e}")
        print(f"    Available columns: {list(display_df.columns)}")

    # Rename columns for display
    rename_dict = {
        'token1': 'Token 1',
        'token2': 'Token 2',
        'token3': 'Token 3',
        'protocol_a': 'Protocol A',
        'protocol_b': 'Protocol B',
        'net_apr': 'Current APR',
        'blended_apr': 'Blended APR',
        'adjusted_apr': 'Adjusted APR ⭐',
        'stablecoin_multiplier': 'Penalty',
        'stablecoins_in_strategy': 'Stablecoins',
        'allocation_usd': 'Allocation'
    }

    # Add max_size to rename dict if present
    try:
        if 'max_size' in display_df.columns:
            rename_dict['max_size'] = 'Max Size'
    except Exception as e:
        print(f"⚠️  Error adding 'max_size' to rename dict: {e}")
        print(f"    Available columns: {list(display_df.columns)}")

    display_df = display_df.rename(columns=rename_dict)

    # Display table with highlighting
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True
    )

    # Allocation Debug Info
    if 'portfolio_debug_info' in st.session_state and st.session_state.portfolio_debug_info:
        st.markdown("---")
        st.markdown("### 🔍 Allocation Analysis")
        st.caption("Shows how each strategy was evaluated and which constraint limited allocation")

        debug_info = st.session_state.portfolio_debug_info

        # Build debug display data
        debug_display_rows = []
        for record in debug_info:
            # Build strategy name
            strategy_name = f"{record['token1']}/{record['token2']}/{record['token3']}"
            protocols = f"{record['protocol_a']} ↔ {record['protocol_b']}"

            # Get limiting constraint info
            constraint_info = record['constraint_info']
            limiting_constraint = constraint_info['limiting_constraint']
            limiting_value = constraint_info['limiting_value']

            # Format constraint name
            if limiting_constraint == 'remaining_capital':
                constraint_display = "Remaining Capital"
            elif limiting_constraint.startswith('token_'):
                parts = limiting_constraint.split('_', 2)
                if len(parts) >= 3:
                    constraint_display = f"Token {parts[1]} ({parts[2]}) Limit"
                else:
                    constraint_display = f"Token Limit"
            elif limiting_constraint.startswith('protocol_'):
                parts = limiting_constraint.split('_', 2)
                if len(parts) >= 3:
                    constraint_display = f"Protocol {parts[1]} ({parts[2]})"
                else:
                    constraint_display = "Protocol Limit"
            elif limiting_constraint == 'strategy_max_size':
                constraint_display = "Strategy Max Size"
            else:
                constraint_display = limiting_constraint

            # Status
            status = "✅ Allocated" if record['allocated'] else "⚠️ Skipped"

            debug_display_rows.append({
                '#': record['strategy_num'],
                'Strategy': strategy_name,
                'Protocols': protocols,
                'Adj APR': f"{record['adjusted_apr']*100:.2f}%",
                'Remaining $': f"${record['remaining_capital']:,.0f}",
                'Max Allowed': f"${record['max_amount']:,.0f}",
                'Limiting Constraint': constraint_display,
                'Status': status
            })

        debug_df = pd.DataFrame(debug_display_rows)
        st.dataframe(debug_df, width='stretch', hide_index=True)

        # Detailed constraint breakdown (expandable)
        with st.expander("📊 Detailed Constraint Analysis"):
            # Show initial matrix state before any allocations
            st.markdown("### 📋 Initial Liquidity State")
            st.caption("_Available borrow liquidity before any portfolio allocations_")

            try:
                # Reconstruct initial matrix from strategies
                from analysis.portfolio_allocator import PortfolioAllocator

                # Get strategies from portfolio or use all_strategies_df
                if 'portfolio_strategies_source' in st.session_state:
                    strategies_for_matrix = st.session_state.portfolio_strategies_source
                else:
                    # Fallback: reconstruct from portfolio
                    strategies_for_matrix = portfolio_df

                initial_matrix = PortfolioAllocator._prepare_available_borrow_matrix(strategies_for_matrix)

                if not initial_matrix.empty:
                    # Transpose for display (protocols as rows, tokens as columns)
                    matrix_display = initial_matrix.T
                    styled_matrix = matrix_display.style.format("${:,.0f}")
                    st.dataframe(styled_matrix, width='stretch')
                else:
                    st.caption("_No initial matrix data available_")
            except Exception as e:
                st.caption(f"_Could not display initial matrix: {e}_")

            st.markdown("---")
            st.markdown("### 🎯 Strategy-by-Strategy Allocation")

            for record in debug_info:
                strategy_name = f"{record['token1']}/{record['token2']}/{record['token3']}"
                st.markdown(f"**Strategy #{record['strategy_num']}: {strategy_name}**")

                # Display available borrow matrix (if available)
                if 'available_borrow_snapshot' in record and record['available_borrow_snapshot'] is not None:
                    st.markdown("**Available Borrow Matrix (after this allocation):**")
                    st.caption("_Shows remaining liquidity per Token×Protocol after allocating to this strategy_")
                    try:
                        matrix_data = record['available_borrow_snapshot']

                        # Handle both DataFrame and dict formats
                        if isinstance(matrix_data, pd.DataFrame):
                            # Already a DataFrame: index=tokens, columns=protocols
                            matrix_df = matrix_data
                        elif isinstance(matrix_data, dict):
                            # Convert dict to DataFrame
                            # Could be {token: {protocol: amount}} or {protocol: {token: amount}}
                            matrix_df = pd.DataFrame(matrix_data)
                        else:
                            st.caption("_Unsupported matrix format_")
                            matrix_df = None

                        if matrix_df is not None and not matrix_df.empty:
                            # Transpose so protocols are rows, tokens are columns (easier to read)
                            matrix_df_display = matrix_df.T
                            # Format values as currency
                            styled_matrix = matrix_df_display.style.format("${:,.0f}")
                            st.dataframe(styled_matrix, width='stretch')
                        else:
                            st.caption("_No borrow matrix data available_")
                    except Exception as e:
                        st.caption(f"_Error displaying matrix: {e}_")

                constraint_info = record['constraint_info']

                # Token constraints
                st.markdown("**Token Constraints:**")
                token_constraint_data = []
                for tc in constraint_info['token_constraints']:
                    token_constraint_data.append({
                        'Token': f"{tc['token']} (pos {tc['position']})",
                        'Type': 'Stablecoin' if tc['is_stablecoin'] else 'Non-stable',
                        'Weight': f"{tc['weight']:.3f}",
                        'Current': f"${tc['current_exposure']:,.0f}",
                        'Limit': f"${tc['limit']:,.0f}",
                        'Room': f"${tc['remaining_room']:,.0f}",
                        'Max from Token': f"${tc['max_from_token']:,.0f}" if tc['max_from_token'] != float('inf') else "∞"
                    })
                st.dataframe(pd.DataFrame(token_constraint_data), hide_index=True)

                # Protocol constraints
                st.markdown("**Protocol Constraints:**")
                protocol_constraint_data = []
                for pc in constraint_info['protocol_constraints']:
                    protocol_constraint_data.append({
                        'Protocol': f"{pc['protocol']} ({pc['position']})",
                        'Weight': f"{pc['weight']:.3f}",
                        'Current': f"${pc['current_exposure']:,.0f}",
                        'Limit': f"${pc['limit']:,.0f}",
                        'Room': f"${pc['remaining_room']:,.0f}",
                        'Max from Protocol': f"${pc['max_from_protocol']:,.0f}"
                    })
                st.dataframe(pd.DataFrame(protocol_constraint_data), hide_index=True)

                # Max Single Allocation Constraint
                if 'max_single_constraint' in constraint_info:
                    st.markdown("**Max Single Allocation Constraint:**")
                    max_single_data = []
                    msc = constraint_info['max_single_constraint']
                    is_limiting = constraint_info['limiting_constraint'] == 'max_single_allocation'
                    max_single_data.append({
                        'Limit (%)': f"{msc['limit_pct']*100:.0f}%",
                        'Limit (USD)': f"${msc['limit_amount']:,.0f}",
                        'Max from Constraint': f"${msc['max_from_single']:,.0f}",
                        'Limited By': 'Yes' if is_limiting else 'No'
                    })
                    st.dataframe(pd.DataFrame(max_single_data), hide_index=True)

                # Size Constraints
                st.markdown("**Size Constraints:**")
                size_constraint_data = []

                # Remaining capital constraint
                size_constraint_data.append({
                    'Constraint Type': 'Remaining Capital',
                    'Value': f"${record['remaining_capital']:,.0f}",
                    'Limited By': 'Yes' if constraint_info['limiting_constraint'] == 'remaining_capital' else 'No'
                })

                # Strategy max size constraint (if exists)
                max_size_before = record.get('max_size_before', None)
                if max_size_before is not None and pd.notna(max_size_before):
                    is_limiting = constraint_info['limiting_constraint'] == 'strategy_max_size'
                    size_constraint_data.append({
                        'Constraint Type': 'Strategy Max Size (before)',
                        'Value': f"${max_size_before:,.0f}",
                        'Limited By': 'Yes' if is_limiting else 'No'
                    })

                # Max size after (if iterative updates enabled)
                max_size_after = record.get('max_size_after', None)
                if max_size_after is not None and pd.notna(max_size_after):
                    size_constraint_data.append({
                        'Constraint Type': 'Strategy Max Size (after)',
                        'Value': f"${max_size_after:,.0f}",
                        'Limited By': 'N/A'
                    })

                # Final allocation
                size_constraint_data.append({
                    'Constraint Type': '→ Final Allocation',
                    'Value': f"${record['max_amount']:,.0f}",
                    'Limited By': constraint_info['limiting_constraint'].replace('_', ' ').title()
                })

                st.dataframe(pd.DataFrame(size_constraint_data), hide_index=True)

                st.markdown("---")

    # Exposure Breakdown
    st.markdown("---")
    st.markdown("### 📊 Portfolio Exposure Analysis")

    from analysis.portfolio_allocator import PortfolioAllocator
    allocator = PortfolioAllocator(portfolio_df)
    token_exposures, protocol_exposures = allocator.calculate_portfolio_exposures(portfolio_df, portfolio_size)

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        st.markdown("#### Token Exposure")
        if token_exposures:
            token_exp_data = []
            for _, data in sorted(
                token_exposures.items(),
                key=lambda x: x[1]['usd'],
                reverse=True
            ):
                token_exp_data.append({
                    'Token': data['symbol'],
                    'Exposure': f"${data['usd']:,.0f}",
                    'Percentage': f"{data['pct']*100:.1f}%"
                })
            token_exp_df = pd.DataFrame(token_exp_data)
            st.dataframe(token_exp_df, width='stretch', hide_index=True)

            # Check if any exposure exceeds limit (showing per-token limits)
            from config.stablecoins import STABLECOIN_SYMBOLS

            token2_limit_pct = constraints.get('token2_exposure_limit', constraints.get('token_exposure_limit', 0.7)) * 100
            stablecoin_limit_pct = constraints.get('stablecoin_exposure_limit', -1)
            token_overrides = constraints.get('token_exposure_overrides', {})

            violations = []
            for contract, data in token_exposures.items():
                symbol = data['symbol']
                exposure_pct = data['pct'] * 100
                is_stablecoin = symbol in STABLECOIN_SYMBOLS

                # Get limit for this token
                if symbol in token_overrides:
                    limit_pct = token_overrides[symbol] * 100
                    limit_str = f"{limit_pct:.0f}% (custom)"
                elif is_stablecoin:
                    # Stablecoin: check stablecoin limit
                    if stablecoin_limit_pct < 0:
                        # Unlimited - no violation possible
                        continue
                    limit_pct = stablecoin_limit_pct * 100
                    limit_str = f"{limit_pct:.0f}% (stablecoin)"
                else:
                    # Non-stablecoin: use token2 limit
                    limit_pct = token2_limit_pct
                    limit_str = f"{limit_pct:.0f}% (token2)"

                if exposure_pct > limit_pct + 0.1:  # Small tolerance for rounding
                    violations.append(f"{symbol}: {exposure_pct:.1f}% > {limit_str}")

            if violations:
                st.warning("⚠️ Token exposure violations:\n" + "\n".join([f"• {v}" for v in violations]))
        else:
            st.info("No token exposures")

    with col_exp2:
        st.markdown("#### Protocol Exposure")
        if protocol_exposures:
            protocol_exp_data = []
            for protocol, data in sorted(
                protocol_exposures.items(),
                key=lambda x: x[1]['usd'],
                reverse=True
            ):
                protocol_exp_data.append({
                    'Protocol': protocol,
                    'Exposure': f"${data['usd']:,.0f}",
                    'Percentage': f"{data['pct']*100:.1f}%"
                })
            protocol_exp_df = pd.DataFrame(protocol_exp_data)
            st.dataframe(protocol_exp_df, width='stretch', hide_index=True)

            # Check if any exposure exceeds limit
            protocol_limit_pct = constraints.get('protocol_exposure_limit', 0.4) * 100
            max_protocol_exp = max([data['pct']*100 for data in protocol_exposures.values()])
            if max_protocol_exp > protocol_limit_pct:
                st.warning(f"⚠️ Max protocol exposure: {max_protocol_exp:.1f}% (limit: {protocol_limit_pct:.1f}%)")
        else:
            st.info("No protocol exposures")

    # Stablecoin Impact Summary
    st.markdown("---")
    st.markdown("### 🪙 Stablecoin Penalty Impact")

    penalized_strategies = portfolio_df[portfolio_df['stablecoin_multiplier'] < 1.0]
    if not penalized_strategies.empty:
        num_penalized = len(penalized_strategies)
        avg_penalty = 1.0 - penalized_strategies['stablecoin_multiplier'].mean()
        total_penalty_impact = (weighted_adjusted_apr - weighted_blended_apr) * 100

        st.info(
            f"📉 {num_penalized} of {num_strategies} strategies have stablecoin penalties. "
            f"Average penalty: {avg_penalty*100:.1f}%. "
            f"Portfolio APR impact: {total_penalty_impact:.2f}%."
        )

        # Show which stablecoins caused penalties
        all_stablecoins = set()
        for stablecoins_list in penalized_strategies['stablecoins_in_strategy']:
            if isinstance(stablecoins_list, list):
                all_stablecoins.update(stablecoins_list)

        if all_stablecoins:
            stablecoin_prefs = constraints.get('stablecoin_preferences', {})
            penalty_details = []
            for stable in sorted(all_stablecoins):
                if stable in stablecoin_prefs and stablecoin_prefs[stable] < 1.0:
                    penalty_pct = (1.0 - stablecoin_prefs[stable]) * 100
                    penalty_details.append(f"{stable} ({penalty_pct:.0f}% penalty)")

            if penalty_details:
                st.caption(f"Stablecoins with penalties: {', '.join(penalty_details)}")
    else:
        st.success("✓ No stablecoin penalties applied. All strategies use preferred stablecoins.")

    # Export and Save options
    st.markdown("---")
    col_export1, col_export2, _ = st.columns([1, 1, 2])
    with col_export1:
        csv = portfolio_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"portfolio_allocation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    with col_export2:
        if st.button("💾 Save Portfolio", type="primary", width='stretch'):
            # Save portfolio to database
            from analysis.portfolio_service import PortfolioService

            try:
                conn = get_db_connection()
                service = PortfolioService(conn)

                # Get portfolio name and timestamp from session state
                portfolio_name = st.session_state.get('portfolio_name', 'Unnamed Portfolio')

                # Get timestamp - MUST be present (Design Note #2: fail loudly, no datetime.now() defaults)
                if 'selected_timestamp' not in st.session_state:
                    st.error("❌ Error: No timestamp selected. This should not happen.")
                    return

                # Convert to Unix seconds (Design Note #5: use to_seconds() helper at boundaries)
                from utils.time_helpers import to_seconds
                timestamp_seconds = to_seconds(st.session_state['selected_timestamp'])

                # Save portfolio
                portfolio_id = service.save_portfolio(
                    portfolio_name=portfolio_name,
                    portfolio_df=portfolio_df,
                    portfolio_size=portfolio_size,
                    constraints=constraints,
                    entry_timestamp=timestamp_seconds,
                    is_paper_trade=True,
                    notes=None
                )

                st.success(f"✅ Portfolio '{portfolio_name}' saved successfully!")
                st.info("📁 View saved portfolios in the **Portfolios** tab")

                # Mark as saved in session state
                st.session_state.portfolio_saved = True
                st.session_state.saved_portfolio_id = portfolio_id

            except Exception as e:
                st.error(f"❌ Error saving portfolio: {str(e)}")
                import traceback
                st.code(traceback.format_exc())


# ============================================================================
# PORTFOLIO2 TAB (Portfolio View - Positions Grouped by Portfolio)
# ============================================================================

def get_portfolio_by_id(portfolio_id: str, conn) -> Optional[dict]:
    """
    Retrieve portfolio metadata from portfolios table.

    Design Principle #5: Converts timestamps to Unix seconds internally.

    Args:
        portfolio_id: Portfolio ID to retrieve
        conn: Database connection

    Returns:
        dict: Portfolio metadata, or None if not found
    """
    # Determine placeholder based on connection type
    try:
        import psycopg2
        if isinstance(conn, psycopg2.extensions.connection):
            ph = '%s'
        else:
            ph = '?'
    except ImportError:
        ph = '?'  # Default to SQLite if psycopg2 not available

    query = f"""
    SELECT *
    FROM portfolios
    WHERE portfolio_id = {ph}
    """

    cursor = conn.cursor()
    cursor.execute(query, (portfolio_id,))
    row = cursor.fetchone()

    if row is None:
        return None

    # Convert row to dict
    columns = [desc[0] for desc in cursor.description]
    portfolio = dict(zip(columns, row))

    # Convert timestamps to Unix seconds (Design Principle #5)
    for ts_field in ['entry_timestamp', 'created_timestamp', 'close_timestamp', 'last_rebalance_timestamp']:
        if portfolio.get(ts_field):
            portfolio[ts_field] = to_seconds(portfolio[ts_field])

    return portfolio


def render_portfolio_metadata(portfolio: dict):
    """Display portfolio-level metadata in compact format."""

    cols = st.columns(4)

    with cols[0]:
        entry_ts = portfolio.get('entry_timestamp')
        if entry_ts:
            entry_date = to_datetime_str(entry_ts)[:10]
            st.metric("Entry Date", entry_date)

    with cols[1]:
        target_size = portfolio.get('target_portfolio_size', 0)
        st.metric("Target Size", f"${target_size:,.0f}")

    with cols[2]:
        utilization = portfolio.get('utilization_pct', 0)
        st.metric("Utilization", f"{utilization:.1f}%")

    with cols[3]:
        entry_apr = portfolio.get('entry_weighted_net_apr', 0)
        st.metric("Entry APR", f"{entry_apr * 100:.2f}%")


def render_portfolio_expander(
    portfolio: dict,
    portfolio_positions: pd.DataFrame,
    timestamp_seconds: int
):
    """
    Render a single portfolio as an expandable row.

    Collapsed: Portfolio-level aggregate metrics
    Expanded: All positions within portfolio (using batch renderer)

    Design Principle #11: Simple aggregations only (view layer)

    Args:
        portfolio: Portfolio metadata dict
        portfolio_positions: DataFrame of positions in this portfolio
        timestamp_seconds: Unix timestamp defining "current time"
    """

    # ========================================
    # CALCULATE PORTFOLIO AGGREGATES FOR TITLE
    # ========================================

    portfolio_name = portfolio.get('portfolio_name', 'Unknown Portfolio')
    num_positions = len(portfolio_positions)
    position_ids = portfolio_positions['position_id'].tolist()

    # Calculate stats ONCE using shared calculation function
    summary_stats = calculate_position_summary_stats(
        position_ids=position_ids,
        timestamp_seconds=timestamp_seconds
    )

    # ========================================
    # BUILD ENHANCED PORTFOLIO TITLE
    # ========================================

    # Extract values from calculated stats
    total_deployed = summary_stats['total_deployed']
    total_pnl = summary_stats['total_pnl']
    avg_entry_apr = summary_stats['avg_entry_apr']
    avg_realised_apr = summary_stats['avg_realised_apr']
    current_value = total_deployed + total_pnl

    title = (
        f"**{portfolio_name}** | "
        f"Positions: {num_positions} | "
        f"Total Deployed: \\${total_deployed:,.2f} | "
        f"Entry APR: {avg_entry_apr * 100:.2f}% | "
        f"Realised APR: {avg_realised_apr * 100:.2f}% | "
        f"Total PnL: \\${total_pnl:,.2f} | "
        f"Current Value: \\${current_value:,.2f}"
    )

    # ========================================
    # RENDER EXPANDER
    # ========================================

    with st.expander(title, expanded=False):
        st.markdown(f"### Positions in {portfolio_name}")

        # ========================================
        # RENDER PORTFOLIO SUMMARY STATISTICS
        # ========================================

        # Render the already-calculated stats (NO recalculation!)
        render_position_summary_stats(
            stats=summary_stats,
            title=f"{portfolio_name} Summary"
        )

        # ========================================
        # BATCH RENDER ALL POSITIONS IN PORTFOLIO
        # ========================================
        # Key design: Delegate to batch renderer

        # Determine context based on portfolio type
        context = 'portfolio2'

        # Use batch renderer (handles everything)
        from dashboard.position_renderers import render_positions_batch
        render_positions_batch(
            position_ids=position_ids,
            timestamp_seconds=timestamp_seconds,
            context=context
        )


def render_portfolio2_tab(timestamp_seconds: int):
    """
    Render Portfolio2 tab - positions grouped by portfolio.

    Design Principles:
    - #1: timestamp_seconds defines "current time"
    - #5: Uses Unix seconds internally
    - #11: Pure view layer - delegates to batch renderer

    Args:
        timestamp_seconds: Unix timestamp defining "current time"
    """

    st.markdown("## 📂 Portfolio View")
    st.markdown("Positions grouped by portfolio for portfolio-level analysis")

    # ========================================
    # LOAD POSITIONS AND GROUP BY PORTFOLIO
    # ========================================

    from dashboard.dashboard_utils import get_db_connection
    from analysis.position_service import PositionService

    conn = get_db_connection()
    service = PositionService(conn)

    # Load all active positions
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        conn.close()
        return

    # Group positions by portfolio_id
    portfolio_ids = active_positions['portfolio_id'].unique()

    # Load portfolio metadata for non-NULL portfolio_ids
    portfolios_dict = {}
    for pid in portfolio_ids:
        if pd.notna(pid):
            portfolio = get_portfolio_by_id(pid, conn)
            if portfolio is not None:
                portfolios_dict[pid] = portfolio

    # Create virtual "Single Positions" portfolio for NULL portfolio_ids
    standalone_positions = active_positions[active_positions['portfolio_id'].isna()]
    if not standalone_positions.empty:
        portfolios_dict['__standalone__'] = {
            'portfolio_id': '__standalone__',
            'portfolio_name': 'Single Positions',
            'status': 'active',
            'is_virtual': True
        }

    # ========================================
    # RENDER EACH PORTFOLIO
    # ========================================

    # Sort portfolios: real portfolios first (by entry_timestamp desc), then standalone
    portfolio_items = sorted(
        portfolios_dict.items(),
        key=lambda x: (
            x[0] == '__standalone__',  # Standalone last
            -to_seconds(x[1].get('entry_timestamp', 0)) if x[0] != '__standalone__' else 0
        )
    )

    for portfolio_id, portfolio in portfolio_items:
        # Get positions for this portfolio
        if portfolio_id == '__standalone__':
            portfolio_positions = standalone_positions
        else:
            portfolio_positions = active_positions[
                active_positions['portfolio_id'] == portfolio_id
            ]

        # Render portfolio expander
        render_portfolio_expander(
            portfolio=portfolio,
            portfolio_positions=portfolio_positions,
            timestamp_seconds=timestamp_seconds
        )

    conn.close()






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

    # Initialize allocator settings on first load
    initialize_allocator_settings()

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
    tracker = RateTracker(
        use_cloud=settings.USE_CLOUD_DB,
        connection_url=settings.SUPABASE_URL
    )

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
            st.info("🚀 View execution instructions in the **Pending Deployments** tab, and track performance in the **Positions** tab")
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

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 All Strategies",
        "🎯 Allocation",
        "📈 Rate Tables",
        "⚠️ 0 Liquidity",
        "💼 Positions",
        "📂 Portfolio View",
        "💎 Oracle Prices",
        "🚀 Pending Deployments"
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
        render_allocation_tab(display_results)  # Use filtered results, not all_results
        tab2_time = (time.time() - tab2_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab2 (Allocation) rendered in {tab2_time:.1f}ms")

    with tab3:
        tab3_start = time.time()
        render_rate_tables_tab(
            lend_rates, borrow_rates, collateral_ratios, prices,
            available_borrow, borrow_fees, borrow_weights, liquidation_thresholds
        )
        tab3_time = (time.time() - tab3_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab3 (Rate Tables) rendered in {tab3_time:.1f}ms")

    with tab4:
        tab4_start = time.time()
        render_zero_liquidity_tab(
            zero_liquidity_results, deployment_usd, mode, timestamp_seconds
        )
        tab4_time = (time.time() - tab4_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab4 (Zero Liquidity) rendered in {tab4_time:.1f}ms")

    with tab5:
        tab5_start = time.time()
        render_positions_table_tab(timestamp_seconds)
        tab5_time = (time.time() - tab5_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab5 (Positions) rendered in {tab5_time:.1f}ms")

    with tab6:
        tab6_start = time.time()
        render_portfolio2_tab(timestamp_seconds)
        tab6_time = (time.time() - tab6_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab6 (Portfolio View) rendered in {tab6_time:.1f}ms")

    with tab7:
        tab7_start = time.time()
        render_oracle_prices_tab(timestamp_seconds)
        tab7_time = (time.time() - tab7_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab7 (Oracle Prices) rendered in {tab7_time:.1f}ms")

    with tab8:
        tab8_start = time.time()
        render_pending_deployments_tab()
        tab8_time = (time.time() - tab8_start) * 1000
        print(f"[{(time.time() - dashboard_start) * 1000:7.1f}ms] [DASHBOARD] Tab8 (Pending Deployments) rendered in {tab8_time:.1f}ms")

    total_dashboard_time = (time.time() - dashboard_start) * 1000
    print(f"[{total_dashboard_time:7.1f}ms] [DASHBOARD] ✅ Dashboard render complete (total: {total_dashboard_time:.1f}ms)\n")