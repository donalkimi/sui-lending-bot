"""Chart generation utilities for strategy history visualization."""

import plotly.graph_objects as go
import pandas as pd
from typing import Optional
from datetime import datetime


def create_history_chart(
    history_df: pd.DataFrame,
    title: str,
    include_price: bool = False,
    price_column: str = 'token2_price',
    height: int = 400
) -> go.Figure:
    """
    Create interactive Plotly chart for APR history.

    Chart features:
    - APR line on right y-axis (percentage)
    - Optional price line on left y-axis (USD)
    - Hover tooltips with formatted values
    - Time axis with automatic date formatting

    Args:
        history_df: DataFrame with 'timestamp' index and 'net_apr' column
        title: Chart title
        include_price: If True, add price as secondary y-axis
        price_column: Column name for price data (only used if include_price=True)
        height: Chart height in pixels

    Returns:
        Plotly Figure object ready for st.plotly_chart()
    """

    fig = go.Figure()

    # Convert timestamp index to datetime for plotting
    timestamps = pd.to_datetime(history_df.index, unit='s')

    # Add APR trace (right y-axis)
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=history_df['net_apr'] * 100,  # Convert decimal to percentage
        name='Net APR',
        mode='lines',
        line=dict(color='#2E7D32', width=2),  # Green
        yaxis='y2',
        hovertemplate='<b>Net APR</b>: %{y:.2f}%<br><b>Date</b>: %{x|%Y-%m-%d %H:%M}<extra></extra>'
    ))

    # Add price trace (left y-axis) if requested
    if include_price and price_column in history_df.columns:
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=history_df[price_column],
            name='Token Price',
            mode='lines',
            line=dict(color='#1976D2', width=2),  # Blue
            yaxis='y1',
            hovertemplate='<b>Price</b>: $%{y:.4f}<br><b>Date</b>: %{x|%Y-%m-%d %H:%M}<extra></extra>'
        ))

    # Layout configuration
    fig.update_layout(
        title=title,
        xaxis=dict(
            title='Date',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)'
        ),
        yaxis=dict(
            title='Token Price (USD)' if include_price else '',
            side='left',
            showgrid=False,
            visible=include_price
        ),
        yaxis2=dict(
            title='Net APR (%)',
            side='right',
            overlaying='y',
            showgrid=True,
            gridcolor='rgba(128, 128, 128, 0.2)'
        ),
        hovermode='x unified',
        height=height,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    return fig


def format_history_table(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create summary statistics table for APR history.

    Args:
        history_df: DataFrame with 'net_apr' column

    Returns:
        DataFrame with summary statistics
    """

    apr_pct = history_df['net_apr'] * 100  # Convert to percentage

    stats = {
        'Metric': [
            'Average APR',
            'Min APR',
            'Max APR',
            'APR Volatility (Std Dev)',
            'Data Points',
            'Time Range (Days)'
        ],
        'Value': [
            f"{apr_pct.mean():.2f}%",
            f"{apr_pct.min():.2f}%",
            f"{apr_pct.max():.2f}%",
            f"{apr_pct.std():.2f}%",
            f"{len(history_df):,}",
            f"{(history_df.index.max() - history_df.index.min()) / 86400:.1f}"
        ]
    }

    return pd.DataFrame(stats)


def get_chart_time_range(range_name: str, current_timestamp: int) -> tuple:
    """
    Calculate start/end timestamps for chart time range.

    Args:
        range_name: One of '7d', '30d', '90d', 'all'
        current_timestamp: Current timestamp (Unix seconds)

    Returns:
        Tuple of (start_timestamp, end_timestamp)
    """

    if range_name == '7d':
        start = current_timestamp - (7 * 24 * 60 * 60)
    elif range_name == '30d':
        start = current_timestamp - (30 * 24 * 60 * 60)
    elif range_name == '90d':
        start = current_timestamp - (90 * 24 * 60 * 60)
    else:  # 'all'
        start = None  # Fetch all available data

    return start, current_timestamp
