import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Any, Union, Dict
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def get_db_connection():
    """Get database connection (SQLite or PostgreSQL based on settings)"""
    if settings.USE_CLOUD_DB:
        import psycopg2
        return psycopg2.connect(settings.SUPABASE_URL)
    else:
        import sqlite3
        return sqlite3.connect(settings.SQLITE_PATH)


def get_latest_timestamp(conn: Optional[Any] = None) -> Optional[str]:
    """
    Get the most recent snapshot timestamp from rates_snapshot table

    Args:
        conn: Optional database connection (will create if None)

    Returns:
        Latest timestamp string or None if no data exists
    """
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    try:
        query = "SELECT MAX(timestamp) as latest FROM rates_snapshot"
        result = pd.read_sql_query(query, conn)

        if result.empty or pd.isna(result['latest'].iloc[0]):
            return None

        # Return as string to match get_available_timestamps()
        return result['latest'].iloc[0]
    finally:
        if should_close:
            conn.close()


def get_available_timestamps(conn: Optional[Any] = None) -> List[str]:
    """
    Get list of ALL available snapshot timestamps (for unified dashboard picker)

    Args:
        conn: Database connection (will create if None)

    Returns:
        List of timestamp strings in descending order (newest first)
    """
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    try:
        query = "SELECT DISTINCT timestamp FROM rates_snapshot ORDER BY timestamp DESC"
        df = pd.read_sql_query(query, conn)
        # Return timestamps as strings to avoid precision issues
        return df['timestamp'].tolist()
    finally:
        if should_close:
            conn.close()


def load_historical_snapshot(timestamp: str, conn: Optional[Any] = None) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame,
    pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame
]:
    """
    Load historical snapshot data from rates_snapshot table and pivot to match live format

    This function queries the database at a specific timestamp and returns 8 DataFrames
    in the exact same format as refresh_pipeline() from data/refresh_pipeline.py

    Args:
        timestamp: Snapshot timestamp string (from database)
        conn: Optional database connection (will create if None)

    Returns:
        Tuple of 8 DataFrames:
            1. lend_rates: Token x Protocol lending rates (with 'Token' and 'Contract' columns)
            2. borrow_rates: Token x Protocol borrow rates
            3. collateral_ratios: Token x Protocol collateral ratios
            4. prices: Token x Protocol prices (USD)
            5. lend_rewards: Token x Protocol lending reward APRs
            6. borrow_rewards: Token x Protocol borrow reward APRs
            7. available_borrow: Token x Protocol available borrow liquidity (USD)
            8. borrow_fees: Token x Protocol borrow fees (decimal)

    Example output format (lend_rates):
        Token    Contract                                 Navi    AlphaFi  Suilend
        USDC     0x5d4b302506645c37ff133b98c4b50a5ae...  0.0234  0.0256   0.0201
        SUI      0x2::sui::SUI                          0.0188  NaN      0.0199

    Design Notes:
        - Matches RateAnalyzer's expected input format exactly
        - Handles missing protocols gracefully (NaN values)
        - Includes 'Token' and 'Contract' columns for consistency
    """
    if conn is None:
        conn = get_db_connection()
        should_close = True
    else:
        should_close = False

    try:
        # Query rates_snapshot at this timestamp
        ph = '%s' if settings.USE_CLOUD_DB else '?'
        query = f"""
        SELECT
            token,
            token_contract,
            protocol,
            lend_total_apr,
            borrow_total_apr,
            collateral_ratio,
            price_usd,
            lend_reward_apr,
            borrow_reward_apr,
            available_borrow_usd,
            borrow_fee
        FROM rates_snapshot
        WHERE timestamp = {ph}
        ORDER BY token, protocol
        """

        # Use timestamp directly (should be string from get_available_timestamps)
        timestamp_param = timestamp

        df = pd.read_sql_query(query, conn, params=(timestamp_param,))

        if df.empty:
            raise ValueError(f"No snapshot data found for timestamp: {timestamp}")

        # Helper to pivot data
        def pivot_data(df, value_col):
            pivoted = df.pivot_table(
                index=['token', 'token_contract'],
                columns='protocol',
                values=value_col,
                aggfunc='first'  # Take first value if duplicates
            ).reset_index()
            pivoted.rename(columns={'token': 'Token', 'token_contract': 'Contract'}, inplace=True)
            return pivoted

        # Create 8 DataFrames by pivoting
        lend_rates = pivot_data(df, 'lend_total_apr')
        borrow_rates = pivot_data(df, 'borrow_total_apr')
        collateral_ratios = pivot_data(df, 'collateral_ratio')
        prices = pivot_data(df, 'price_usd')
        lend_rewards = pivot_data(df, 'lend_reward_apr')
        borrow_rewards = pivot_data(df, 'borrow_reward_apr')
        available_borrow = pivot_data(df, 'available_borrow_usd')
        borrow_fees = pivot_data(df, 'borrow_fee')

        return (lend_rates, borrow_rates, collateral_ratios, prices,
                lend_rewards, borrow_rewards, available_borrow, borrow_fees)

    finally:
        if should_close:
            conn.close()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
        return float(row.get('apr_net', row.get('net_apr', 0)))


# ============================================================================
# HISTORICAL CHART FUNCTIONS
# ============================================================================

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
    except Exception:
        return None


def fetch_historical_rates(conn: Any, token1_contract: str, token2_contract: str, token3_contract: str,
                          protocol_A: str, protocol_B: str, strategy_seconds: int) -> pd.DataFrame:
    """
    Fetch ALL historical rates for the given tokens/protocols UP TO the strategy timestamp.

    The strategy_seconds is the "current" moment selected in the dashboard (Unix timestamp).
    We fetch all historical data where timestamp <= strategy_seconds.

    Args:
        conn: Database connection
        token1_contract: Token1 contract address
        token2_contract: Token2 contract address
        token3_contract: Token3 contract address
        protocol_A: First protocol name
        protocol_B: Second protocol name
        strategy_seconds: Unix timestamp in seconds (the "current" moment)

    Returns:
        DataFrame with columns: timestamp (as seconds), protocol, token_contract, lend_total_apr, borrow_total_apr, price_usd
    """
    from utils.time_helpers import to_seconds, to_datetime_str

    if conn is None:
        return pd.DataFrame()

    try:
        if strategy_seconds is None:
            raise ValueError("strategy_seconds is required")

        # Convert seconds to datetime string for SQL query
        strategy_dt_str = to_datetime_str(strategy_seconds)

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
                timestamp <= %s
                AND (
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s) OR
                    (token_contract = %s AND protocol = %s)
                )
            ORDER BY timestamp
            """
            params = (
                strategy_dt_str,
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
                timestamp <= ?
                AND (
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?) OR
                    (token_contract = ? AND protocol = ?)
                )
            ORDER BY timestamp
            """
            params = (
                strategy_dt_str,
                token1_contract, protocol_A,
                token2_contract, protocol_A,
                token2_contract, protocol_B,
                token3_contract, protocol_B
            )

        df = pd.read_sql_query(query, conn, params=params)

        # DEBUG: Print query results
        print(f"\n{'='*80}")
        print(f"DEBUG fetch_historical_rates - SQL Results:")
        print(f"Strategy timestamp: {strategy_seconds} seconds ({strategy_dt_str})")
        print(f"Rows returned: {len(df)}")
        if len(df) > 0:
            print(f"\nLatest 10 rows:")
            print(df.tail(10).to_string())
        else:
            print("❌ NO ROWS RETURNED FROM QUERY")
            print(f"\nQuery executed:")
            print(query)
            print(f"\nParams: {params}")
        print(f"{'='*80}\n")

        # IMMEDIATELY convert timestamp column from strings to seconds
        if 'timestamp' in df.columns and len(df) > 0:
            df['timestamp'] = df['timestamp'].apply(to_seconds)

        return df
    except Exception as e:
        print(f"❌ Exception in fetch_historical_rates: {e}")
        import traceback
        traceback.print_exc()
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

        # Calculate base APR (as decimal)
        base_apr = earn_A + earn_B - cost_A - cost_B

        # Subtract annualized fee cost to get Net APR (as decimal)
        total_fee_cost = B_A * borrow_fee_2A + B_B * borrow_fee_3B
        net_apr = base_apr - total_fee_cost

        results.append({
            'timestamp': timestamp,
            'net_apr': net_apr,
            'token2_price': token2_price
        })

    return pd.DataFrame(results)


def create_strategy_history_chart(df: pd.DataFrame, token1: str, token2: str, token3: str,
                                  protocol_A: str, protocol_B: str, liq_dist: float,
                                  L_A: float, B_A: float, L_B: float, B_B: float) -> go.Figure:
    """
    Create Plotly chart with dual axes (price + APR)

    Args:
        df: DataFrame with timestamp (as seconds), net_apr, token2_price
        token1, token2, token3: Token symbols
        protocol_A, protocol_B: Protocol names
        liq_dist: Liquidation distance (for display)
        L_A, B_A, L_B, B_B: Position weightings (for display)

    Returns:
        Plotly Figure object
    """
    from utils.time_helpers import to_datetime_str

    # Convert timestamp (seconds) to datetime strings for chart display
    df_display = df.copy()
    df_display['timestamp_display'] = df_display['timestamp'].apply(to_datetime_str)

    # Convert APR from decimal to percentage for display
    df_display['net_apr_pct'] = df_display['net_apr'] * 100

    fig = go.Figure()

    # Calculate axis ranges with padding
    price_min = df['token2_price'].min()
    price_max = df['token2_price'].max()
    price_padding = (price_max - price_min) * 0.1 if price_max > price_min else price_min * 0.1
    price_range = [price_min - price_padding, price_max + price_padding]

    apr_min = df_display['net_apr_pct'].min()
    apr_max = df_display['net_apr_pct'].max()
    apr_padding = (apr_max - apr_min) * 0.1 if apr_max > apr_min else 1.0
    apr_range = [apr_min - apr_padding, apr_max + apr_padding]

    # Token2 price (background, left axis)
    fig.add_trace(go.Scatter(
        x=df_display['timestamp_display'],
        y=df_display['token2_price'],
        name=f'{token2} Price (USD)',
        yaxis='y1',
        mode='lines',
        line=dict(color='rgba(135, 206, 235, 0.8)', width=2),
        fillcolor='rgba(173, 216, 230, 0.2)',
        hovertemplate='<b>Price:</b> $%{y:.4f}<br><extra></extra>'
    ))

    # Net APR (primary, right axis)
    apr_color = 'green' if df_display['net_apr_pct'].iloc[-1] > 0 else 'red'

    fig.add_trace(go.Scatter(
        x=df_display['timestamp_display'],
        y=df_display['net_apr_pct'],
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


def get_strategy_history(strategy_row: Dict[str, Any], liquidation_distance: float = 0.15) -> Tuple[Optional[pd.DataFrame], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Main orchestration function to get historical chart data for a strategy

    Args:
        strategy_row: Strategy details from all_results DataFrame
        liquidation_distance: Current liquidation distance setting (for display only)

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

        # Get contract addresses from strategy_row (populated by analysis phase)
        token1_contract = strategy_row.get('token1_contract')
        token2_contract = strategy_row.get('token2_contract')
        token3_contract = strategy_row.get('token3_contract')

        # Critical check - token1 and token2 MUST have contracts
        if token1_contract is None or token2_contract is None:
            print(f"Error: Missing contracts for tokens - token1={token1} ({token1_contract}), token2={token2} ({token2_contract})")
            return None, None, None, None, None

        # token3 can be None for unlevered strategies - use empty string to skip SQL query
        if token3_contract is None:
            token3_contract = ""  # Will be filtered in SQL WHERE clause

        # USE THE WEIGHTINGS ALREADY CALCULATED IN THE ANALYSIS
        L_A = strategy_row['L_A']
        B_A = strategy_row['B_A']
        L_B = strategy_row['L_B']
        B_B = strategy_row['B_B']

        # Get current fees from the strategy row
        borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)
        borrow_fee_3B = strategy_row.get('borrow_fee_3B', 0.0)

        # Get the strategy timestamp and convert to seconds
        from utils.time_helpers import to_seconds, to_datetime_str

        strategy_timestamp_raw = strategy_row.get('timestamp')
        if strategy_timestamp_raw is None:
            raise ValueError("strategy_row must contain 'timestamp'")

        # Convert to seconds (handles any input type)
        strategy_seconds = to_seconds(strategy_timestamp_raw)

        print(f"\n{'='*80}")
        print(f"DEBUG get_strategy_history - Before SQL query:")
        print(f"Strategy timestamp: {strategy_seconds} seconds ({to_datetime_str(strategy_seconds)})")
        print(f"Token contracts: {token1_contract}, {token2_contract}, {token3_contract}")
        print(f"Protocols: {protocol_A}, {protocol_B}")
        print(f"{'='*80}\n")

        # Fetch historical rates
        raw_df = fetch_historical_rates(
            conn, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, strategy_seconds
        )

        if raw_df.empty:
            return None, L_A, B_A, L_B, B_B

        # Calculate net APR history
        history_df = calculate_net_apr_history(
            raw_df, token1_contract, token2_contract, token3_contract,
            protocol_A, protocol_B, L_A, B_A, L_B, B_B,
            borrow_fee_2A, borrow_fee_3B
        )

        return history_df, L_A, B_A, L_B, B_B

    except Exception as e:
        print(f"❌ Error in get_strategy_history: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise the exception instead of silently returning None
    finally:
        conn.close()
