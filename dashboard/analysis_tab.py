"""Analysis tab — strategy rate charting with 8hr/24hr rolling avg overlays."""

from datetime import datetime
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analysis.strategy_history.strategy_history import get_strategy_history
from config.stablecoins import STABLECOIN_SYMBOLS


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(v) -> str:
    """Format a decimal rate as a percentage string. Design Note #7."""
    if v is None or (hasattr(v, '__class__') and v.__class__.__name__ in ('float', 'float64') and pd.isna(v)):
        return "—"
    try:
        return f"{float(v) * 100:.3f}%"
    except (TypeError, ValueError):
        return "—"


def _resolve_start_timestamp(time_range: str, end_ts: int) -> Optional[int]:
    """Convert UI time-range string → Unix seconds start. Design Note #1: explicit timestamps."""
    days = {'7d': 7, '30d': 30, '90d': 90}.get(time_range)
    if days is None:
        return None  # 'All' — no lower bound
    return end_ts - days * 86400


def _strategy_label(row: pd.Series) -> str:
    """Build a human-readable strategy selector label."""
    stype  = row.get('strategy_type', '')
    t1     = row.get('token1', '?')
    t2     = row.get('token2', '')
    t3     = row.get('token3', '?')
    pa     = row.get('protocol_a', '')
    pb     = row.get('protocol_b', '')
    apr    = row.get('apr_net', 0)

    if stype == 'perp_lending':
        tokens = f"{t1} ↔ {t3}"
    elif t2:
        tokens = f"{t1} → {t2} → {t3}"
    else:
        tokens = f"{t1} → {t3}"

    protocols = f"{pa}/{pb}" if pb else pa
    return f"{stype} | {tokens} | {protocols} | {apr * 100:.1f}%"


def _filter_strategies(
    all_results: pd.DataFrame,
    strategy_types: list,
    force_usdc: bool,
    force_t3_eq_t1: bool,
    stablecoin_only: bool,
) -> pd.DataFrame:
    df = all_results.copy()
    if strategy_types:
        df = df[df['strategy_type'].isin(strategy_types)]
    if force_usdc:
        df = df[df['token1'] == 'USDC']
    if force_t3_eq_t1:
        df = df[df['token3'] == df['token1']]
    if stablecoin_only:
        df = df[
            df['token1'].isin(STABLECOIN_SYMBOLS) &
            df['token2'].isin(STABLECOIN_SYMBOLS) &
            df['token3'].isin(STABLECOIN_SYMBOLS)
        ]
    return df


def _build_strategy_dict(row: pd.Series) -> dict:
    """Convert a strategy DataFrame row to the dict format expected by get_strategy_history()."""
    return row.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Inline strategy summary (replaces modal popup)
# ─────────────────────────────────────────────────────────────────────────────

def _render_strategy_summary(strategy: dict, timestamp_seconds: int) -> None:
    """
    Render strategy summary table + per-leg detail table inline (no dialog).
    Uses the same registered strategy renderers as the All Strategies modal.
    """
    from dashboard.position_renderers import get_strategy_renderer
    from utils.time_helpers import to_datetime_str

    strategy_type = strategy.get('strategy_type', '')
    is_perp = strategy_type in ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')

    # ── Header ────────────────────────────────────────────────────────────
    if strategy_type == 'perp_lending':
        st.markdown(f"#### {strategy.get('token1')} ↔ {strategy.get('token3')} (Perp Lending)")
    elif is_perp:
        st.markdown(f"#### {strategy.get('token1')} / {strategy.get('token2')} / {strategy.get('token3')} (Perp Borrowing)")
    else:
        st.markdown(f"#### {strategy.get('token1')} / {strategy.get('token2', '')} / {strategy.get('token3')}")

    # ── Token flow string from renderer ───────────────────────────────────
    try:
        renderer_cls = get_strategy_renderer(strategy_type)
        token_flow = renderer_cls.build_token_flow_string(pd.Series(strategy))
    except Exception:
        t1 = strategy.get('token1', '')
        t2 = strategy.get('token2', '')
        t3 = strategy.get('token3', '')
        token_flow = f"{t1} ↔ {t3}" if strategy_type == 'perp_lending' else f"{t1} → {t2} → {t3}"

    def _sf(key, default=0.0):
        try:
            v = strategy.get(key, default)
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    # ── APR summary table ─────────────────────────────────────────────────
    summary_data = [{
        'Time':       to_datetime_str(timestamp_seconds),
        'Token Flow': token_flow,
        'Protocols':  f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}",
        'Net APR':    f"{_sf('apr_net') * 100:.2f}%",
        'APR 5d':     f"{_sf('apr5')    * 100:.2f}%",
        'APR 30d':    f"{_sf('apr30')   * 100:.2f}%",
        'Liq Dist':   f"{_sf('liquidation_distance') * 100:.2f}%",
    }]
    summary_df = pd.DataFrame(summary_data)

    def _color_apr(val):
        if isinstance(val, str) and '%' in val:
            try:
                n = float(val.replace('%', ''))
                return 'color: green' if n > 0 else ('color: red' if n < 0 else '')
            except (ValueError, TypeError):
                pass
        return ''

    styled = summary_df.style.map(_color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
    st.dataframe(styled, width='stretch', hide_index=True)
    st.markdown("")

    # ── Deployment amount input (required by render_strategy_modal_table) ─
    max_size = _sf('max_size', 1_000_000)
    default_dep = min(10_000.0, max_size)
    max_val_cap = min(max_size, 1e9) if max_size != float('inf') else 1e9
    col1, _ = st.columns([1, 2])
    with col1:
        deployment_usd = st.number_input(
            "Deployment Amount (USD)",
            min_value=100.0,
            max_value=max_val_cap,
            value=default_dep,
            step=100.0,
            key="analysis_deployment_usd",
        )
    st.markdown("")

    # ── Per-leg detail table via registered renderer ───────────────────────
    st.markdown("**Position Details:**")
    try:
        renderer_cls = get_strategy_renderer(strategy_type)
        renderer_cls.render_strategy_modal_table(strategy, deployment_usd)
    except (ValueError, NotImplementedError) as e:
        st.warning(f"No detail renderer registered for `{strategy_type}`: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Rate detail table
# ─────────────────────────────────────────────────────────────────────────────

def _render_rate_table(history_df: pd.DataFrame, strategy: dict) -> None:
    """
    Render per-timestamp rate breakdown table.
    Columns adapt to strategy type (perp_lending = 2 legs, perp_borrowing = 3 legs, spot = basic).
    All rates displayed as % per Design Note #7.
    """
    strategy_type = strategy.get('strategy_type', '')
    is_perp_borrowing = strategy_type in ('perp_borrowing', 'perp_borrowing_recursive')
    is_perp_lending   = strategy_type == 'perp_lending'
    is_perp           = is_perp_borrowing or is_perp_lending

    rows = []
    for ts, row in history_df.iterrows():
        ts_str = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')

        record = {
            'Timestamp':        ts_str,
            'Net APR':          _fmt(row.get('net_apr')),
            'Net APR (8hr avg)': _fmt(row.get('net_avg8hr_apr')),
            'Net APR (24hr avg)': _fmt(row.get('net_avg24hr_apr')),
        }

        if is_perp_lending:
            # 2 legs: spot lend + perp short
            record['Lend 1A'] = _fmt(row.get('lend_total_apr_1A'))
            record['Perp 3B'] = _fmt(row.get('perp_rate_3B'))
            record['Perp 3B (8hr)'] = _fmt(row.get('avg8hr_perp_rate_3B'))
            record['Perp 3B (24hr)'] = _fmt(row.get('avg24hr_perp_rate_3B'))

        elif is_perp_borrowing:
            # 3 legs: stable lend + volatile borrow + perp long
            record['Lend 1A'] = _fmt(row.get('lend_total_apr_1A'))
            record['Borrow 2A'] = _fmt(row.get('borrow_total_apr_2A'))
            record['Perp 3B'] = _fmt(row.get('perp_rate_3B'))
            record['Perp 3B (8hr)'] = _fmt(row.get('avg8hr_perp_rate_3B'))
            record['Perp 3B (24hr)'] = _fmt(row.get('avg24hr_perp_rate_3B'))

        else:
            # Spot strategies — avg columns will show "—"
            record['Lend 1A'] = _fmt(row.get('lend_total_apr_1A'))
            if row.get('borrow_total_apr_2A') is not None:
                record['Borrow 2A'] = _fmt(row.get('borrow_total_apr_2A'))

        rows.append(record)

    if not rows:
        st.info("No rate data available.")
        return

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# APR chart
# ─────────────────────────────────────────────────────────────────────────────

def _render_apr_chart(history_df: pd.DataFrame) -> None:
    """
    Line chart of net APR + 8hr and 24hr rolling avg overlays.
    Each series can be toggled via checkboxes.
    Y-axis values are in % (Design Note #7 — conversion at display layer only).
    """
    col1, col2, col3 = st.columns(3)
    show_spot  = col1.checkbox("Spot net APR",   value=True,  key="analysis_show_spot")
    show_8hr   = col2.checkbox("8hr avg APR",    value=True,  key="analysis_show_8hr")
    show_24hr  = col3.checkbox("24hr avg APR",   value=True,  key="analysis_show_24hr")

    # Convert Unix-second index to display strings (Design Note #5: conversion at display boundary)
    ts_display = [datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M')
                  for ts in history_df.index]

    fig = go.Figure()

    if show_spot:
        fig.add_trace(go.Scatter(
            x=ts_display,
            y=(history_df['net_apr'] * 100).round(4),
            name='Net APR (spot)',
            line=dict(color='#4fc3f7', width=1.5),
            hovertemplate='%{x}<br>Net APR: %{y:.3f}%<extra></extra>',
        ))

    if show_8hr and 'net_avg8hr_apr' in history_df and history_df['net_avg8hr_apr'].notna().any():
        fig.add_trace(go.Scatter(
            x=ts_display,
            y=(history_df['net_avg8hr_apr'] * 100).round(4),
            name='Net APR (8hr avg)',
            line=dict(color='#ff9800', width=2, dash='dash'),
            hovertemplate='%{x}<br>8hr avg: %{y:.3f}%<extra></extra>',
        ))

    if show_24hr and 'net_avg24hr_apr' in history_df and history_df['net_avg24hr_apr'].notna().any():
        fig.add_trace(go.Scatter(
            x=ts_display,
            y=(history_df['net_avg24hr_apr'] * 100).round(4),
            name='Net APR (24hr avg)',
            line=dict(color='#e91e63', width=2, dash='dot'),
            hovertemplate='%{x}<br>24hr avg: %{y:.3f}%<extra></extra>',
        ))

    fig.update_layout(
        yaxis_title='Net APR (%)',
        hovermode='x unified',
        height=420,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )

    st.plotly_chart(fig, width="stretch")   # Design Note #6: width= not use_container_width=


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_analysis_tab(all_results: pd.DataFrame, timestamp_seconds: int) -> None:
    """
    Render the Analysis tab.

    Args:
        all_results: Full unfiltered strategies DataFrame from rate_analyzer.
        timestamp_seconds: Current dashboard timestamp (Unix seconds). Design Note #1.
    """
    st.markdown("### Strategy Rate Analysis")

    if all_results is None or all_results.empty:
        st.info("No strategies available. Ensure the pipeline has run successfully.")
        return

    # ── Filter controls ────────────────────────────────────────────────────
    col_filters, col_selector = st.columns([1, 2])

    with col_filters:
        all_types = sorted(all_results['strategy_type'].dropna().unique().tolist())
        selected_types = st.multiselect(
            "Strategy types", all_types, default=all_types, key="analysis_types"
        )
        force_usdc     = st.checkbox("Force token1 = USDC",    key="analysis_force_usdc")
        force_t3_eq_t1 = st.checkbox("Force token3 = token1",  key="analysis_force_t3")
        stablecoin_only = st.checkbox("Stablecoin only",        key="analysis_stable_only")

    filtered = _filter_strategies(
        all_results, selected_types, force_usdc, force_t3_eq_t1, stablecoin_only
    )

    with col_selector:
        if filtered.empty:
            st.info("No strategies match the selected filters.")
            return

        strategy_labels = [_strategy_label(r) for _, r in filtered.iterrows()]
        selected_label  = st.selectbox(
            "Select strategy", strategy_labels, key="analysis_strategy_select"
        )
        time_range = st.selectbox(
            "History period", ["7d", "30d", "90d", "All"], index=1, key="analysis_time_range"
        )

    load_btn = st.button("Load Analysis", key="analysis_load_btn")

    # Don't render anything until the user clicks Load (or history already in session)
    if not load_btn and 'analysis_history_df' not in st.session_state:
        return

    # ── Resolve selected strategy ─────────────────────────────────────────
    selected_idx = strategy_labels.index(selected_label)
    strategy_row  = filtered.iloc[selected_idx]
    strategy_dict = _build_strategy_dict(strategy_row)

    # ── Inline strategy summary ───────────────────────────────────────────
    st.markdown("---")
    _render_strategy_summary(strategy_dict, timestamp_seconds)

    # ── Load history ──────────────────────────────────────────────────────
    if load_btn:
        start_ts = _resolve_start_timestamp(time_range, timestamp_seconds)
        with st.spinner("Loading historical rates…"):
            try:
                history_df = get_strategy_history(
                    strategy_dict,
                    start_timestamp=start_ts,
                    end_timestamp=timestamp_seconds,
                )
            except Exception as e:
                st.error(f"Failed to load history: {e}")
                return

        st.session_state['analysis_history_df'] = history_df
        st.session_state['analysis_strategy']   = strategy_dict

    history_df    = st.session_state.get('analysis_history_df', pd.DataFrame())
    strategy_dict = st.session_state.get('analysis_strategy', strategy_dict)

    if history_df.empty:
        st.info("No historical data found for this strategy in the selected period.")
        return

    # ── Rate detail table ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Historical Rates")
    _render_rate_table(history_df, strategy_dict)

    # ── APR chart ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### APR Chart")
    _render_apr_chart(history_df)
