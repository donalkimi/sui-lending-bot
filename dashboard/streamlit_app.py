"""
Streamlit dashboard for Sui Lending Bot
streamlit run dashboard/streamlit_app.py

"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
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


# ============================================================================
# HISTORICAL CHART FUNCTIONS
# ============================================================================

def get_db_connection():
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


def get_token_contract(conn, token_symbol: str):
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


def fetch_historical_rates(conn, token1_contract: str, token2_contract: str, token3_contract: str,
                          protocol_A: str, protocol_B: str, days_back: int = 30):
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
                              L_A: float, B_A: float, L_B: float, B_B: float):
    """
    Calculate net APR for each timestamp using static weightings
    
    Args:
        raw_df: Raw rates DataFrame
        token1_contract: Token1 contract address
        token2_contract: Token2 contract address
        token3_contract: Token3 contract address
        protocol_A: First protocol name
        protocol_B: Second protocol name
        L_A, B_A, L_B, B_B: Position weightings
        
    Returns:
        DataFrame with columns: timestamp, net_apr, token2_price
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
        
        if None in [lend_1A, borrow_2A, lend_2B, borrow_3B, token2_price]:
            continue
        
        earn_A = L_A * lend_1A
        earn_B = L_B * lend_2B
        cost_A = B_A * borrow_2A
        cost_B = B_B * borrow_3B
        
        net_apr = (earn_A + earn_B - cost_A - cost_B) * 100
        
        results.append({
            'timestamp': timestamp,
            'net_apr': net_apr,
            'token2_price': token2_price
        })
    
    return pd.DataFrame(results)


def create_strategy_history_chart(df: pd.DataFrame, token1: str, token2: str, token3: str,
                                  protocol_A: str, protocol_B: str, liq_dist: float,
                                  L_A: float, B_A: float, L_B: float, B_B: float):
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


def get_strategy_history(strategy_row: dict, liquidation_distance: float, days_back: int = 30):
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
        
        if None in [token1_contract, token2_contract, token3_contract]:
            st.warning("Could not find token contracts in database")
            return None, None, None, None, None
        
        # USE THE WEIGHTINGS ALREADY CALCULATED IN THE ANALYSIS
        # These were computed with the correct collateral ratios and liquidation distance
        L_A = strategy_row['L_A']
        B_A = strategy_row['B_A']
        L_B = strategy_row['L_B']
        B_B = strategy_row['B_B']
        
        # Fetch historical rates
        raw_df = fetch_historical_rates(
            conn, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, days_back
        )
        
        if raw_df.empty:
            return None, L_A, B_A, L_B, B_B
        
        # Calculate net APR history using the SAME weightings as the displayed strategy
        history_df = calculate_net_apr_history(
            raw_df, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, L_A, B_A, L_B, B_B
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

        return (lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees), None
    except Exception as e:
        return None, str(e)


def run_analysis(lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, liquidation_distance: float):
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
            liquidation_distance=liquidation_distance,
        )
        
        protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()
        return protocol_A, protocol_B, all_results, None
    except Exception as e:
        return None, None, pd.DataFrame(), str(e)


def display_strategy_details(strategy_row):
    """
    Display expanded strategy details when row is clicked
    
    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
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

    # Available borrow liquidity
    available_borrow_2A = strategy_row.get('available_borrow_2A')

    # Show available borrow metric if available
    if available_borrow_2A is not None and not pd.isna(available_borrow_2A):
        st.info(f"💵 **Available Borrow Liquidity ({token2} on {protocol_A}):** ${available_borrow_2A:,.2f}")

    # Build the table data
    table_data = [
        # Row 1: Protocol A, token1, Lend
        {
            'Protocol': protocol_A,
            'Token': token1,
            'Action': 'Lend',
            'Rate': f"{lend_rate_1A:.2f}%",
            'USD Value': f"${L_A * 100:.2f}",
            'Token Amount': f"{(L_A * 100) / P1_A:.2f}",
            'Price': f"${P1_A:.4f}"
        },
        # Row 2: Protocol A, token2, Borrow
        {
            'Protocol': protocol_A,
            'Token': token2,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_2A:.2f}%",
            'USD Value': f"${B_A * 100:.2f}",
            'Token Amount': f"{(B_A * 100) / P2_A:.2f}",
            'Price': f"${P2_A:.4f}"
        },
        # Row 3: Protocol B, token2, Lend
        {
            'Protocol': protocol_B,
            'Token': token2,
            'Action': 'Lend',
            'Rate': f"{lend_rate_2B:.2f}%",
            'USD Value': f"${((B_A * 100) / P2_A) * P2_B:.2f}",
            'Token Amount': f"{(B_A * 100) / P2_A:.2f}",
            'Price': f"${P2_B:.4f}"
        },
        # Row 4: Protocol B, token3, Borrow
        {
            'Protocol': protocol_B,
            'Token': token3,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_3B:.2f}%",
            'USD Value': f"${B_B * 100:.2f}",
            'Token Amount': f"{(B_B * 100) / P3_B:.2f}",
            'Price': f"${P3_B:.4f}"
        }
    ]
    
    # Create DataFrame and display
    details_df = pd.DataFrame(table_data)
    st.dataframe(details_df, use_container_width=True, hide_index=True)


def main():
    """Main dashboard"""

    # Header
    st.title("🚀 Sui Lending Bot")
    st.markdown("**Cross-Protocol Yield Optimizer**")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Liquidation Distance - inline with label
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("**Liquidation Dist (%)**")
        with col2:
            liq_dist_text = st.text_input(
                label="Liq Dist",
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

        st.markdown("---")

        st.subheader("📊 Data Source")
        st.info(f"Live data from {len(['Navi', 'AlphaFi', 'Suilend'])} protocols")

        if "refresh_nonce" not in st.session_state:
            st.session_state.refresh_nonce = 0

        if st.button("🔄 Refresh Data", use_container_width=True):
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

    lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees = data_result

    if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # Run analysis (fast - re-runs when liquidation_distance changes)
    protocol_A, protocol_B, all_results, analysis_error = run_analysis(
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow,
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
            best = all_results.iloc[0].to_dict()
            notifier.alert_high_apr(best)
        
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
    

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "🏆 Best Opportunities",
        "📊 All Strategies",
        "📈 Rate Tables"
    ])

    # ---------------- Tab 1 ----------------
    with tab1:
        st.header("🏆 Best Opportunities")

        if protocol_A and not filtered_results.empty:
            best = filtered_results.iloc[0]

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Net APR", f"{best['net_apr']:.2f}%")
            col2.metric("Liquidation Distance", f"{best['liquidation_distance']:.0f}%")
            col3.metric("Protocol A", protocol_A)
            col4.metric("Protocol B", protocol_B)

            # Show available borrow if available
            available_borrow_2A = best.get('available_borrow_2A')
            if available_borrow_2A is not None and not pd.isna(available_borrow_2A):
                col5.metric(f"{best['token2']} Liquidity", f"${available_borrow_2A:,.2f}")

            st.subheader("Strategy Details")
            st.write(f"**Token 1 (Start):** {best['token1']}")
            st.write(f"**Token 2 (Middle):** {best['token2']}")
            st.write(f"**Token 3 (Close):** {best['token3']}")
            
            if best['token1'] != best['token3']:
                st.info(f"💱 This strategy includes stablecoin conversion: {best['token3']} → {best['token1']}")

            st.subheader("Top 10 Strategies")
            
            for idx, row in filtered_results.head(10).iterrows():
                # Chart data key
                chart_key = f"chart_tab1_{idx}"

                # Expander should be open if chart data exists for this strategy
                is_expanded = chart_key in st.session_state

                # Build expander title with available borrow
                available_borrow_2A = row.get('available_borrow_2A')
                avail_borrow_text = f" | {row['protocol_A']}/{row['token2']} Available ${available_borrow_2A:,.2f}"

                with st.expander(
                    f"▶ {row['token1']} → {row['token2']} → {row['token3']} | "
                    f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                    f"{row['net_apr']:.2f}% APR{avail_borrow_text}",
                    expanded=is_expanded
                ):
                    # Button to load historical chart
                    if st.button("📈 Load Historical Chart", key=f"btn_tab1_{idx}"):
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
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Current APR", f"{row['net_apr']:.2f}%")
                            col2.metric("Avg APR", f"{history_df['net_apr'].mean():.2f}%")
                            col3.metric("Max APR", f"{history_df['net_apr'].max():.2f}%")
                            col4.metric("Min APR", f"{history_df['net_apr'].min():.2f}%")
                            
                            st.markdown("---")
                        else:
                            st.info("📊 No historical data available yet. Run main.py to build up history.")
                    
                    # Always show strategy details table
                    display_strategy_details(row)
        else:
            st.warning("⚠️ No strategies found with current filters")

    # ---------------- Tab 2 ----------------
    with tab2:
        st.header("📊 All Valid Strategies")

        if not filtered_results.empty:
            col1, col2, col3 = st.columns(3)

            with col1:
                min_apr = st.number_input("Min APR (%)", value=0.0, step=0.5)

            with col2:
                token_filter = st.multiselect(
                    "Filter by Token",
                    options=sorted(set(filtered_results['token1']).union(set(filtered_results['token2'])).union(set(filtered_results['token3']))) if not filtered_results.empty else [],
                    default=[]
                )

            with col3:
                protocol_filter = st.multiselect(
                    "Filter by Protocol",
                    options=['Navi','AlphaFi','Suilend'],
                    default=[]
                )

            display_results = filtered_results[filtered_results['net_apr'] >= min_apr]

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

            st.metric("Strategies Found", f"{len(display_results)} / {len(all_results)}")

            # Display with expanders
            for idx, row in display_results.iterrows():
                # Chart data key
                chart_key = f"chart_tab2_{idx}"

                # Expander should be open if chart data exists for this strategy
                is_expanded = chart_key in st.session_state

                # Build expander title with available borrow
                available_borrow_2A = row.get('available_borrow_2A')
                avail_borrow_text = f" | {row['protocol_A']}/{row['token2']} Available ${available_borrow_2A:,.2f}"

                with st.expander(
                    f"▶ {row['token1']} → {row['token2']} → {row['token3']} | "
                    f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                    f"{row['net_apr']:.2f}% APR{avail_borrow_text}",
                    expanded=is_expanded
                ):
                    # Button to load historical chart
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
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Summary metrics
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Current APR", f"{row['net_apr']:.2f}%")
                            col2.metric("Avg APR", f"{history_df['net_apr'].mean():.2f}%")
                            col3.metric("Max APR", f"{history_df['net_apr'].max():.2f}%")
                            col4.metric("Min APR", f"{history_df['net_apr'].min():.2f}%")
                            
                            st.markdown("---")
                        else:
                            st.info("📊 No historical data available yet. Run main.py to build up history.")
                    
                    # Always show strategy details table
                    display_strategy_details(row)
        else:
            st.warning("⚠️ No strategies found with current filters")

    # ---------------- Tab 3 ----------------
    with tab3:
        st.header("📈 Current Rates")

        col1, col2 = st.columns(2)
        
        col1.subheader("💵 Lending Rates")
        lend_display = lend_rates.drop(columns=['Contract']) if 'Contract' in lend_rates.columns else lend_rates
        col1.dataframe(lend_display, use_container_width=True, hide_index=True)

        col2.subheader("💸 Borrow Rates")
        borrow_display = borrow_rates.drop(columns=['Contract']) if 'Contract' in borrow_rates.columns else borrow_rates
        col2.dataframe(borrow_display, use_container_width=True, hide_index=True)

        st.subheader("🔒 Collateral Ratios")
        collateral_display = collateral_ratios.drop(columns=['Contract']) if 'Contract' in collateral_ratios.columns else collateral_ratios
        st.dataframe(collateral_display, use_container_width=True, hide_index=True)
        
        st.subheader("💰 Prices")
        prices_display = prices.drop(columns=['Contract']) if 'Contract' in prices.columns else prices
        st.dataframe(prices_display, use_container_width=True, hide_index=True)

        st.subheader("💵 Available Borrow Liquidity")
        # Format available_borrow values as abbreviated USD
        available_borrow_display = available_borrow.copy()
        if 'Contract' in available_borrow_display.columns:
            available_borrow_display = available_borrow_display.drop(columns=['Contract'])

        # Format numeric columns (protocol columns)
        for col in available_borrow_display.columns:
            if col != 'Token':
                available_borrow_display[col] = available_borrow_display[col].apply(format_usd_abbreviated)

        st.dataframe(available_borrow_display, use_container_width=True, hide_index=True)

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

        st.dataframe(borrow_fees_display, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()