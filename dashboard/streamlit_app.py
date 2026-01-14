"""
Streamlit dashboard for Sui Lending Bot
streamlit run dashboard/streamlit_app.py

"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Tuple, Optional, Union, Any, Dict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS, STABLECOIN_SYMBOLS
from data.refresh_pipeline import refresh_pipeline
from analysis.position_calculator import PositionCalculator


def format_usd_abbreviated(value: float) -> str:
    """Format USD amount abbreviated (e.g., $1.23M, $456K)"""
    if value is None or pd.isna(value):
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.0f}"


def get_apr_value(row: Union[pd.Series, Dict[str, Any]], use_unlevered: bool) -> float:
    """Get the appropriate Net APR value based on leverage toggle"""
    if use_unlevered:
        return float(row.get('unlevered_apr', 0))
    else:
        return float(row.get('apr_net', row.get('net_apr', 0)))  # Prefer apr_net, fallback to base


# ============================================================================
# HISTORICAL CHART FUNCTIONS
# ============================================================================

def get_db_connection() -> Optional[Any]:
    """
    Connect to SQLite or PostgreSQL based on settings
    
    Returns:
        Database connection object
    """
    if settings.USE_CLOUD_DB:
        try:
            import psycopg2
            return psycopg2.connect(settings.SUPABASE_URL)
        except ImportError:
            st.error("psycopg2 not installed. Install with: pip install psycopg2-binary")
            return None
    else:
        import sqlite3
        db_path = settings.SQLITE_PATH
        if not os.path.exists(db_path):
            st.warning(f"Database not found at: {db_path}. Run main.py to populate data.")
            return None
        return sqlite3.connect(db_path)


def get_token_contract(conn: Any, token_symbol: str) -> Optional[str]:
    """
    Look up contract address for a token symbol
    
    Args:
        conn: Database connection
        token_symbol: Token symbol (e.g., "USDC", "WAL")
        
    Returns:
        Contract address string or None if not found
    """
    if conn is None:
        return None
    
    try:
        if settings.USE_CLOUD_DB:
            query = "SELECT DISTINCT token_contract FROM rates_snapshot WHERE token = %s LIMIT 1"
            cursor = conn.cursor()
            cursor.execute(query, (token_symbol,))
        else:
            query = "SELECT DISTINCT token_contract FROM rates_snapshot WHERE token = ? LIMIT 1"
            cursor = conn.cursor()
            cursor.execute(query, (token_symbol,))
        
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        st.error(f"Error looking up token contract: {e}")
        return None


def fetch_historical_rates(conn: Any, token1_contract: str, token2_contract: str, token3_contract: str,
                          protocol_A: str, protocol_B: str, days_back: int = 30) -> pd.DataFrame:
    """
    Fetch all 4 required rates + token2 price for each timestamp
    
    Args:
        conn: Database connection
        token1_contract: Token1 contract address
        token2_contract: Token2 contract address
        token3_contract: Token3 contract address
        protocol_A: First protocol name
        protocol_B: Second protocol name
        days_back: Number of days to look back
        
    Returns:
        DataFrame with columns: timestamp, protocol, token_contract, lend_total_apr, borrow_total_apr, price_usd
    """
    if conn is None:
        return pd.DataFrame()
    
    try:
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        if settings.USE_CLOUD_DB:
            query = """
            SELECT 
                timestamp,
                protocol,
                token_contract,
                lend_total_apr,
                borrow_total_apr,
                price_usd
            FROM rates_snapshot
            WHERE 
                timestamp >= %s
                AND (
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s)
                )
            ORDER BY timestamp
            """
            params = (
                cutoff_date,
                token1_contract, protocol_A,
                token2_contract, protocol_A,
                token2_contract, protocol_B,
                token3_contract, protocol_B
            )
        else:
            query = """
            SELECT 
                timestamp,
                protocol,
                token_contract,
                lend_total_apr,
                borrow_total_apr,
                price_usd
            FROM rates_snapshot
            WHERE 
                timestamp >= ?
                AND (
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?)
                )
            ORDER BY timestamp
            """
            params = (
                cutoff_date.isoformat(),
                token1_contract, protocol_A,
                token2_contract, protocol_A,
                token2_contract, protocol_B,
                token3_contract, protocol_B
            )
        
        df = pd.read_sql_query(query, conn, params=params)
        
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    except Exception as e:
        st.error(f"Error fetching historical rates: {e}")
        return pd.DataFrame()


def calculate_net_apr_history(raw_df: pd.DataFrame, token1_contract: str, token2_contract: str,
                              token3_contract: str, protocol_A: str, protocol_B: str,
                              L_A: float, B_A: float, L_B: float, B_B: float,
                              borrow_fee_2A: float = 0.0, borrow_fee_3B: float = 0.0) -> pd.DataFrame:
    """
    Calculate net APR for each timestamp using static weightings and fees

    Args:
        raw_df: Raw rates DataFrame
        token1_contract: Token1 contract address
        token2_contract: Token2 contract address
        token3_contract: Token3 contract address
        protocol_A: First protocol name
        protocol_B: Second protocol name
        L_A, B_A, L_B, B_B: Position weightings
        borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
        borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)

    Returns:
        DataFrame with columns: timestamp, net_apr (fee-adjusted), token2_price
    """
    results = []

    for timestamp, group in raw_df.groupby('timestamp'):
        lend_1A = None
        borrow_2A = None
        lend_2B = None
        borrow_3B = None
        token2_price = None

        for _, row in group.iterrows():
            contract = row['token_contract']
            protocol = row['protocol']

            if contract == token1_contract and protocol == protocol_A:
                lend_1A = row['lend_total_apr']
            elif contract == token2_contract and protocol == protocol_A:
                borrow_2A = row['borrow_total_apr']
                token2_price = row['price_usd']
            elif contract == token2_contract and protocol == protocol_B:
                lend_2B = row['lend_total_apr']
            elif contract == token3_contract and protocol == protocol_B:
                borrow_3B = row['borrow_total_apr']

        # Skip if any required values are missing
        if lend_1A is None or borrow_2A is None or lend_2B is None or borrow_3B is None or token2_price is None:
            continue

        earn_A = L_A * lend_1A
        earn_B = L_B * lend_2B
        cost_A = B_A * borrow_2A
        cost_B = B_B * borrow_3B

        # Calculate base APR
        base_apr = (earn_A + earn_B - cost_A - cost_B) * 100

        # Subtract annualized fee cost to get Net APR
        total_fee_cost = (B_A * borrow_fee_2A + B_B * borrow_fee_3B) * 100
        net_apr = base_apr - total_fee_cost

        results.append({
            'timestamp': timestamp,
            'net_apr': net_apr,  # Now contains fee-adjusted Net APR
            'token2_price': token2_price
        })
    
    return pd.DataFrame(results)


def create_strategy_history_chart(df: pd.DataFrame, token1: str, token2: str, token3: str,
                                  protocol_A: str, protocol_B: str, liq_dist: float,
                                  L_A: float, B_A: float, L_B: float, B_B: float) -> go.Figure:
    """
    Create Plotly chart with dual axes (price + APR)
    
    Args:
        df: DataFrame with timestamp, net_apr, token2_price
        token1, token2, token3: Token symbols
        protocol_A, protocol_B: Protocol names
        liq_dist: Liquidation distance (for display)
        L_A, B_A, L_B, B_B: Position weightings (for display)
        
    Returns:
        Plotly Figure object
    """
    fig = go.Figure()
    
    # Calculate axis ranges with padding
    price_min = df['token2_price'].min()
    price_max = df['token2_price'].max()
    price_padding = (price_max - price_min) * 0.1 if price_max > price_min else price_min * 0.1
    price_range = [price_min - price_padding, price_max + price_padding]
    
    apr_min = df['net_apr'].min()
    apr_max = df['net_apr'].max()
    apr_padding = (apr_max - apr_min) * 0.1 if apr_max > apr_min else 1.0
    apr_range = [apr_min - apr_padding, apr_max + apr_padding]
    
    # Token2 price (background, left axis)
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['token2_price'],
        name=f'{token2} Price (USD)',
        yaxis='y1',
        mode='lines',
        line=dict(color='rgba(135, 206, 235, 0.8)', width=2),
        fillcolor='rgba(173, 216, 230, 0.2)',
        hovertemplate='<b>Price:</b> $%{y:.4f}<br><extra></extra>'
    ))
    
    # Net APR (primary, right axis)
    apr_color = 'green' if df['net_apr'].iloc[-1] > 0 else 'red'
    
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['net_apr'],
        name='Net APR (%)',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color=apr_color, width=3),
        marker=dict(size=6, color=apr_color),
        hovertemplate='<b>Net APR:</b> %{y:.2f}%<br><extra></extra>'
    ))
    
    # Layout
    fig.update_layout(
        title=dict(
            text=(
                f'<b>Historical Performance: {token1} → {token2} → {token3}</b><br>'
                f'<sub>{protocol_A} ↔ {protocol_B} | '
                f'Liq Dist: {liq_dist*100:.0f}% | '
                f'Weightings: L_A={L_A:.2f}, B_A={B_A:.2f}, L_B={L_B:.2f}, B_B={B_B:.2f}</sub>'
            ),
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        xaxis=dict(
            title='Date',
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True
        ),
        yaxis=dict(
            title=dict(
                text=f'{token2} Price (USD)',
                font=dict(color='rgba(135, 206, 235, 1)')
            ),
            tickfont=dict(color='rgba(135, 206, 235, 1)'),
            side='left',
            showgrid=False,
            range=price_range
        ),
        yaxis2=dict(
            title=dict(
                text='Net APR (%)',
                font=dict(color=apr_color)
            ),
            tickfont=dict(color=apr_color),
            side='right',
            overlaying='y',
            gridcolor='rgba(128, 128, 128, 0.2)',
            showgrid=True,
            range=apr_range
        ),
        hovermode='x unified',
        height=400,
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor='gray',
            borderwidth=1
        )
    )
    
    return fig


def get_strategy_history(strategy_row: Dict[str, Any], liquidation_distance: float = 0.15, days_back: int = 30) -> Tuple[Optional[pd.DataFrame], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Main orchestration function to get historical chart data for a strategy
    
    Args:
        strategy_row: Strategy details from all_results DataFrame
        liquidation_distance: Current liquidation distance setting (for display only)
        days_back: Days of history to fetch
        
    Returns:
        Tuple of (history_df, L_A, B_A, L_B, B_B) or (None, None, None, None, None) if error
    """
    # Get database connection
    conn = get_db_connection()
    if conn is None:
        return None, None, None, None, None
    
    try:
        # Extract strategy details
        token1 = strategy_row['token1']
        token2 = strategy_row['token2']
        token3 = strategy_row['token3']
        protocol_A = strategy_row['protocol_A']
        protocol_B = strategy_row['protocol_B']
        
        # Get contract addresses
        token1_contract = get_token_contract(conn, token1)
        token2_contract = get_token_contract(conn, token2)
        token3_contract = get_token_contract(conn, token3)

        if token1_contract is None or token2_contract is None or token3_contract is None:
            st.warning("Could not find token contracts in database")
            return None, None, None, None, None
        
        # USE THE WEIGHTINGS ALREADY CALCULATED IN THE ANALYSIS
        # These were computed with the correct collateral ratios and liquidation distance
        L_A = strategy_row['L_A']
        B_A = strategy_row['B_A']
        L_B = strategy_row['L_B']
        B_B = strategy_row['B_B']

        # Get current fees from the strategy row
        borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)
        borrow_fee_3B = strategy_row.get('borrow_fee_3B', 0.0)

        # Fetch historical rates
        raw_df = fetch_historical_rates(
            conn, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, days_back
        )

        if raw_df.empty:
            return None, L_A, B_A, L_B, B_B

        # Calculate net APR history using the SAME weightings as the displayed strategy
        # Apply current fees retroactively to all historical data points
        history_df = calculate_net_apr_history(
            raw_df, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, L_A, B_A, L_B, B_B,
            borrow_fee_2A, borrow_fee_3B
        )
        
        return history_df, L_A, B_A, L_B, B_B
        
    except Exception as e:
        st.error(f"Error generating history: {e}")
        return None, None, None, None, None
    finally:
        conn.close()


# ============================================================================
# END HISTORICAL CHART FUNCTIONS
# ============================================================================


# Page configuration
st.set_page_config(
    page_title="Sui Lending Bot",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_and_save_protocol_data(refresh_nonce: int):
    """Fetch protocol data, save to database, and prepare for analysis."""
    try:
        from data.protocol_merger import merge_protocol_data
        from data.rate_tracker import RateTracker
        from datetime import datetime

        # Fetch fresh data from APIs
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees = merge_protocol_data(
            stablecoin_contracts=STABLECOIN_CONTRACTS
        )

        # Save to database immediately
        tracker = RateTracker(
            use_cloud=settings.USE_CLOUD_DB,
            db_path=settings.SQLITE_PATH,
            connection_url=settings.SUPABASE_URL,
        )

        timestamp = datetime.now()
        tracker.save_snapshot(
            timestamp=timestamp,
            lend_rates=lend_rates,
            borrow_rates=borrow_rates,
            collateral_ratios=collateral_ratios,
            prices=prices,
            lend_rewards=lend_rewards,
            borrow_rewards=borrow_rewards,
        )

        # Update token registry
        tokens_df = lend_rates[['Token', 'Contract']].copy()
        tokens_df.rename(columns={'Token': 'symbol', 'Contract': 'token_contract'}, inplace=True)
        tracker.upsert_token_registry(tokens_df=tokens_df, timestamp=timestamp)

        print(f"✅ Dashboard: Saved snapshot to database at {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        return (lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp), None
    except Exception as e:
        return None, str(e)


def run_analysis(lend_rates: pd.DataFrame, borrow_rates: pd.DataFrame, collateral_ratios: pd.DataFrame,
                 prices: pd.DataFrame, lend_rewards: pd.DataFrame, borrow_rewards: pd.DataFrame,
                 available_borrow: pd.DataFrame, borrow_fees: pd.DataFrame,
                 liquidation_distance: float) -> Tuple[Optional[str], Optional[str], pd.DataFrame, Optional[str]]:
    """Run strategy analysis (fast operation)."""
    try:
        from analysis.rate_analyzer import RateAnalyzer

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
        return protocol_A, protocol_B, all_results, None
    except Exception as e:
        return None, None, pd.DataFrame(), str(e)


def display_apr_table(strategy_row: Union[pd.Series, Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """
    Display compact APR comparison table with both levered and unlevered strategies
    Returns warnings/info to be displayed later

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)

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
    # For unlevered, we need to recalculate fee-adjusted APRs with B_B = 0
    # For now, use the levered values as placeholder (will be more accurate in future)
    apr_net_unlevered = unlevered_base  # Simplified for now
    apr90_unlevered = unlevered_base
    apr30_unlevered = unlevered_base
    apr5_unlevered = unlevered_base

    # Build row names with emojis at the start
    row_name_levered = f"🔄 {token1}→{token2}→{token3} Loop 🔄"
    row_name_unlevered = f"▶️  {token1}→{token2} No-Loop ⏹️"

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

    # Display compact table without header
    st.dataframe(styled_apr_df, hide_index=True)

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

    # USD values (multiply by 100 for $100 notional)
    L_A = strategy_row['L_A']
    B_A = strategy_row['B_A']
    L_B = strategy_row['L_B']
    B_B = strategy_row['B_B']

    # Rates (already as percentages in the dict)
    lend_rate_1A = strategy_row['lend_rate_1A']
    borrow_rate_2A = strategy_row['borrow_rate_2A']
    lend_rate_2B = strategy_row['lend_rate_2B']
    borrow_rate_3B = strategy_row['borrow_rate_3B']

    # Prices
    P1_A = strategy_row['P1_A']
    P2_A = strategy_row['P2_A']
    P2_B = strategy_row['P2_B']
    P3_B = strategy_row['P3_B']

    # Token amounts
    T1_A = strategy_row['T1_A']
    T2_A = strategy_row['T2_A']
    T3_B = strategy_row['T3_B']

    # Borrow fees and available liquidity (already extracted above but kept for compatibility)
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


def main():
    """Main dashboard"""

    # Header
    st.title("🚀 Sui Lending Bot")
    st.markdown("**Cross-Protocol Yield Optimizer**")

    # Sidebar - set wider width
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            min-width: 300px;
            max-width: 350px;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # Placeholder for database snapshot timestamp (will be populated after data load)
        db_timestamp_placeholder = st.empty()
        st.markdown("---")

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

        # Validate input
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
            # Clear all chart cache
            keys_to_delete = [key for key in st.session_state.keys() if key.startswith('chart_tab')]
            for key in keys_to_delete:
                del st.session_state[key]

            # Update last known liquidation distance
            st.session_state.last_liq_distance = liquidation_distance

            print(f"🗑️ Cleared {len(keys_to_delete)} cached charts due to liquidation distance change")

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

        # Validate input
        try:
            deployment_usd = float(deployment_text)
            if deployment_usd < 0:
                st.error("Deployment USD must be non-negative")
                st.stop()
        except ValueError:
            st.error("Deployment USD must be a number")
            st.stop()

        st.markdown("---")
        
        # Toggle to force token1 = USDC
        force_usdc_start = st.toggle(
            "Force token1 = USDC",
            value=True,
            help="When enabled, only shows strategies starting with USDC"
        )
        
        # Toggle to force token3 = token1
        force_token3_equals_token1 = st.toggle(
            "Force token3 = token1 (no conversion)",
            value=True,
            help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
        )
        
        # Toggle to show only stablecoin strategies
        stablecoin_only = st.toggle(
            "Stablecoin Only",
            value=False,
            help="When enabled, only shows strategies where all three tokens are stablecoins"
        )

        # Toggle for leverage/looping
        use_unlevered = st.toggle(
            "No leverage/looping",
            value=False,
            help="When enabled, shows unlevered APR (single lend→borrow→lend cycle without recursive loop)"
        )

        st.markdown("---")

        # Filters section (will be populated after data is loaded)
        st.subheader("🔍 Filters")

        # Placeholder for filters - will be filled after data loading
        filter_placeholder = st.container()

        st.markdown("---")

        st.subheader("📊 Data Source")
        st.info(f"Live data from {len(['Navi', 'AlphaFi', 'Suilend'])} protocols")

        if "refresh_nonce" not in st.session_state:
            st.session_state.refresh_nonce = 0

        if st.button("🔄 Refresh Data", width='stretch'):
            # Bust only the cached data load by changing the cache key (refresh_nonce)
            st.session_state.refresh_nonce += 1
            st.rerun()
        
        st.caption("💡 Changing liquidation distance re-runs analysis instantly without re-fetching protocol data")

        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Load data (cached - only refreshes on button click)
    with st.spinner("Loading data from protocols..."):
        data_result, data_error = fetch_and_save_protocol_data(st.session_state.refresh_nonce)

    if data_error:
        st.error(f"❌ Error loading data: {data_error}")
        st.info("💡 Check that all protocol APIs are accessible")
        st.stop()

    if data_result is None:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, db_timestamp = data_result

    # Update the database timestamp placeholder in the sidebar
    with db_timestamp_placeholder.container():
        st.caption(f"📸 **Database Snapshot**")
        st.caption(f"{db_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # Run analysis (fast - re-runs when liquidation_distance changes)
    protocol_A, protocol_B, all_results, analysis_error = run_analysis(
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees,
        liquidation_distance
    )
    
    if analysis_error:
        st.error(f"❌ Error during analysis: {analysis_error}")
        st.stop()
    
    # Send Slack notification only when data is actually refreshed
    # Check if this is a fresh fetch (not from cache)
    if "last_notified_nonce" not in st.session_state:
        st.session_state.last_notified_nonce = -1

    if st.session_state.refresh_nonce != st.session_state.last_notified_nonce:
        from alerts.slack_notifier import SlackNotifier
        notifier = SlackNotifier()

        if all_results is None or all_results.empty:
            notifier.alert_error("No valid strategies found in dashboard refresh.")
        else:
            notifier.alert_top_strategies(
                all_results=all_results,
                liquidation_distance=liquidation_distance,
                deployment_usd=100.0,
                timestamp=datetime.now()
            )

        st.session_state.last_notified_nonce = st.session_state.refresh_nonce
    
    # Apply filters ONCE before displaying in tabs
    filtered_results = all_results.copy()
    
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

    # Filter by deployment size (remove strategies with insufficient liquidity)
    if deployment_usd > 0:
        filtered_results = filtered_results[
            (filtered_results['max_size'].notna()) &
            (filtered_results['max_size'] >= deployment_usd)
        ]

    # Create zero_liquidity_results for Tab 4
    zero_liquidity_results = all_results.copy()

    # Apply the same toggle filters
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

    # Keep only strategies with NaN, 0, or below deployment threshold
    zero_liquidity_results = zero_liquidity_results[
        (zero_liquidity_results['max_size'].isna()) |
        (zero_liquidity_results['max_size'] == 0) |
        (zero_liquidity_results['max_size'] < deployment_usd)
    ]

    # Sort filtered results by Net APR (apr_net for levered, unlevered_apr for unlevered)
    # Note: apr_net is fee-adjusted Net APR, not base net_apr
    apr_col = 'unlevered_apr' if use_unlevered else 'apr_net'
    filtered_results = filtered_results.sort_values(by=apr_col, ascending=False)
    zero_liquidity_results = zero_liquidity_results.sort_values(by=apr_col, ascending=False)

    # Now populate the sidebar filters with the loaded data
    with filter_placeholder:
        min_apr = st.number_input("Min Net APR (%)", value=0.0, step=0.5)

        token_filter = st.multiselect(
            "Filter by Token",
            options=sorted(set(filtered_results['token1']).union(set(filtered_results['token2'])).union(set(filtered_results['token3']))) if not filtered_results.empty else [],
            default=[]
        )

        protocol_filter = st.multiselect(
            "Filter by Protocol",
            options=['Navi','AlphaFi','Suilend'],
            default=[]
        )

    # Apply additional filters based on user input
    display_results = filtered_results[filtered_results[apr_col] >= min_apr]

    if token_filter:
        display_results = display_results[
            display_results['token1'].isin(token_filter) |
            display_results['token2'].isin(token_filter)
        ]

    if protocol_filter:
        display_results = display_results[
            display_results['protocol_A'].isin(protocol_filter) |
            display_results['protocol_B'].isin(protocol_filter)
        ]

    # Add strategy count to sidebar
    with filter_placeholder:
        st.metric("Strategies Found", f"{len(display_results)} / {len(all_results)}")

    # Tabs
    # tab1, tab2, tab3, tab4 = st.tabs([
    #     "🏆 Best Opportunities",
    #     "📊 All Strategies",
    #     "📈 Rate Tables",
    #     "⚠️ 0 Liquidity"
    # ])
    tab1, tab2, tab3 = st.tabs([
        "📊 All Strategies",
        "📈 Rate Tables",
        "⚠️ 0 Liquidity"
    ])

    # # ---------------- Tab 1: Best Opportunities (COMMENTED OUT) ----------------
    # # with tab1:
    # #     st.header("🏆 Best Opportunities")
    # #
    # #     if protocol_A and not filtered_results.empty:
    # #
    # #         for idx, row in filtered_results.head(10).iterrows():
    # #             # Chart data key
    # #             chart_key = f"chart_tab1_{idx}"
    # #
    # #             # Expander should be open if chart data exists for this strategy
    # #             is_expanded = chart_key in st.session_state
    # #
    # #             # Build expander title with max size and APR
    # #             max_size = row.get('max_size')
    # #             if max_size is not None and not pd.isna(max_size):
    # #                 max_size_text = f" | Max Size ${max_size:,.2f}"
    # #             else:
    # #                 max_size_text = ""
    # #
    # #             # Build token flow based on leverage toggle
    # #             if use_unlevered:
    # #                 token_flow = f"{row['token1']} → {row['token2']}"
    # #             else:
    # #                 token_flow = f"{row['token1']} → {row['token2']} → {row['token3']}"
    # #
    # #             title = f"▶ {token_flow} | {row['protocol_A']} ↔ {row['protocol_B']}{max_size_text} | {get_apr_value(row, use_unlevered):.2f}% APR"
    # #
    # #             with st.expander(title, expanded=is_expanded):
    # #                 # Display APR comparison table at the top
    # #                 display_apr_table(row)
    # #
    # #                 # Button to load historical chart
    # #                 if st.button("📈 Load Historical Chart", key=f"btn_tab1_{idx}"):
    # #                     with st.spinner("Loading historical data..."):
    # #                         history_df, L_A, B_A, L_B, B_B = get_strategy_history(
    # #                             strategy_row=row.to_dict(),
    # #                             liquidation_distance=liquidation_distance,
    # #                             days_back=30
    # #                         )
    # #
    # #                         # Store in session state
    # #                         st.session_state[chart_key] = {
    # #                             'history_df': history_df,
    # #                             'L_A': L_A,
    # #                             'B_A': B_A,
    # #                             'L_B': L_B,
    # #                             'B_B': B_B
    # #                         }
    # #
    # #                     # Force rerun to show chart
    # #                     st.rerun()
    # #
    # #                 # Display chart if loaded
    # #                 if chart_key in st.session_state:
    # #                     chart_data = st.session_state[chart_key]
    # #                     history_df = chart_data['history_df']
    # #
    # #                     if history_df is not None and not history_df.empty:
    # #                         st.subheader("📈 Historical Performance")
    # #
    # #                         # Create and display chart
    # #                         fig = create_strategy_history_chart(
    # #                             df=history_df,
    # #                             token1=row['token1'],
    # #                             token2=row['token2'],
    # #                             token3=row['token3'],
    # #                             protocol_A=row['protocol_A'],
    # #                             protocol_B=row['protocol_B'],
    # #                             liq_dist=liquidation_distance,
    # #                             L_A=chart_data['L_A'],
    # #                             B_A=chart_data['B_A'],
    # #                             L_B=chart_data['L_B'],
    # #                             B_B=chart_data['B_B']
    # #                         )
    # #                         st.plotly_chart(fig, width='stretch')
    # #
    # #                         # Summary metrics
    # #                         col1, col2, col3, col4 = st.columns(4)
    # #                         col1.metric("Current APR", f"{get_apr_value(row, use_unlevered):.2f}%")
    # #                         col2.metric("Avg APR", f"{history_df['net_apr'].mean():.2f}%")
    # #                         col3.metric("Max APR", f"{history_df['net_apr'].max():.2f}%")
    # #                         col4.metric("Min APR", f"{history_df['net_apr'].min():.2f}%")
    # #
    # #                         st.markdown("---")
    # #                     else:
    # #                         st.info("📊 No historical data available yet. Run main.py to build up history.")
    # #
    # #                 # Always show strategy details table
    # #                 display_strategy_details(row, use_unlevered)
    # #     else:
    # #         st.warning("⚠️ No strategies found with current filters")

    # ---------------- Tab 1: All Strategies (formerly Tab 2) ----------------
    with tab1:

        if not display_results.empty:
            # Display with expanders
            for idx, row in display_results.iterrows():
                # Chart data key
                chart_key = f"chart_tab2_{idx}"

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

                # Get Net APR and APR5 values (use apr_net and apr5 columns)
                if use_unlevered:
                    # For unlevered, calculate fee-adjusted values from unlevered_apr
                    # For now, use unlevered_apr as both (simplified - can enhance later)
                    net_apr_value = row.get('unlevered_apr', 0)
                    apr5_value = row.get('unlevered_apr', 0)  # Simplified
                else:
                    # For levered, use apr_net and apr5 columns
                    net_apr_value = row.get('apr_net', row['net_apr'])  # Fallback to base if missing
                    apr5_value = row.get('apr5', row['net_apr'])  # Fallback to base if missing

                # Format APR values with color indicators (emoji-based since expander titles are plain text)
                # Use ✅ for positive, ⚠️ for negative Net APR
                # Use 🟢 for positive, 🔴 for negative APR5
                net_apr_indicator = "🟢" if net_apr_value >= 0 else "🔴"
                apr5_indicator = "🟢" if apr5_value >= 0 else "🔴"

                title = f"▶ {token_flow} | {row['protocol_A']} ↔ {row['protocol_B']}{max_size_text} | {net_apr_indicator} Net APR {net_apr_value:.2f}% | {apr5_indicator} 5day APR {apr5_value:.2f}%"

                with st.expander(title, expanded=is_expanded):
                    # 1. Display APR comparison table at the top
                    fee_caption, warning_message = display_apr_table(row)

                    # 2. Display strategy details table right after
                    max_size_msg, liquidity_msg = display_strategy_details(row, use_unlevered)

                    # 3. Button to load historical chart
                    if st.button("📈 Load Historical Chart", key=f"btn_tab2_{idx}"):
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

    # ---------------- Tab 2: Rate Tables (formerly Tab 3) ----------------
    with tab2:
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
        # Format available_borrow values as abbreviated USD
        available_borrow_display = available_borrow.copy()
        if 'Contract' in available_borrow_display.columns:
            available_borrow_display = available_borrow_display.drop(columns=['Contract'])

        # Format numeric columns (protocol columns)
        for col in available_borrow_display.columns:
            if col != 'Token':
                available_borrow_display[col] = available_borrow_display[col].apply(format_usd_abbreviated)

        st.dataframe(available_borrow_display, width='stretch', hide_index=True)

        st.subheader("💳 Borrow Fees")
        # Format fees as percentages
        borrow_fees_display = borrow_fees.copy()
        if 'Contract' in borrow_fees_display.columns:
            borrow_fees_display = borrow_fees_display.drop(columns=['Contract'])

        # Format numeric columns as percentages
        for col in borrow_fees_display.columns:
            if col != 'Token':
                borrow_fees_display[col] = borrow_fees_display[col].apply(
                    lambda x: f"{x*100:.2f}%" if pd.notna(x) and x > 0 else ("0.00%" if x == 0 else "N/A")
                )

        st.dataframe(borrow_fees_display, width='stretch', hide_index=True)

    # ---------------- Tab 3: Zero Liquidity (formerly Tab 4) ----------------
    with tab3:
        st.header("⚠️ Zero Liquidity Strategies")

        if not zero_liquidity_results.empty:
            st.info(f"⚠️ These strategies have insufficient liquidity (max size < ${deployment_usd:,.0f}) or missing liquidity data")

            st.metric("Strategies Found", f"{len(zero_liquidity_results)}")

            # Display with expanders (no historical charts)
            for idx, row in zero_liquidity_results.iterrows():
                # Build expander title with max size
                max_size = row.get('max_size')
                if max_size is not None and not pd.isna(max_size):
                    max_size_text = f" | Max Size ${max_size:,.2f}"
                else:
                    max_size_text = " | No Liquidity Data"

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

                with st.expander(
                    f"▶ {token_flow} | "
                    f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                    f"{net_apr_indicator} Net APR {net_apr_value:.2f}% | {apr5_indicator} 5day APR {apr5_value:.2f}%{max_size_text}",
                    expanded=False
                ):
                    # 1. Display APR comparison table at the top
                    fee_caption, warning_message = display_apr_table(row)

                    # 2. Display strategy details table right after
                    max_size_msg, liquidity_msg = display_strategy_details(row, use_unlevered)

                    # 3. Display warnings/info at the end
                    st.caption(fee_caption)
                    if warning_message:
                        st.warning(warning_message)

                    # 4. Display liquidity info at the very end
                    if max_size_msg:
                        st.success(max_size_msg)
                    if liquidity_msg:
                        st.info(liquidity_msg)
        else:
            st.success("✅ All strategies have sufficient liquidity for the current deployment size!")


if __name__ == "__main__":
    main()