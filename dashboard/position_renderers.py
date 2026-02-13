"""
Position rendering system with strategy-type support.

Each strategy type can have custom rendering logic while sharing
common infrastructure.

Currently supported:
- recursive_lending (4-leg recursive lending strategy)

Future strategy types:
- fund_rate_arb (funding rate arbitrage)
- cross_protocol_lending (direct cross-protocol lending)
- yield_farming (single-sided yield farming)
"""

import streamlit as st
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Tuple
from utils.time_helpers import to_seconds, to_datetime_str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _safe_float(value, default=0.0):
    """
    Safely convert value to float, handling bytes and edge cases.

    Args:
        value: Value to convert (can be float, int, bytes, None, etc.)
        default: Default value to return if conversion fails

    Returns:
        float: Converted value or default
    """
    if pd.isna(value):
        return default
    if isinstance(value, bytes):
        try:
            return float(int.from_bytes(value, byteorder='little'))
        except Exception:
            return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class StrategyRendererBase(ABC):
    """
    Abstract base class that all strategy renderers must implement.

    This ensures consistency while allowing strategy-specific customization.
    """

    @staticmethod
    @abstractmethod
    def get_strategy_name() -> str:
        """Return human-readable strategy name."""
        pass

    @staticmethod
    @abstractmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List]
    ) -> None:
        """Render the strategy-specific detail table."""
        pass

    @staticmethod
    @abstractmethod
    def get_metrics_layout() -> List[str]:
        """
        Return list of metric keys to display in summary.

        Returns:
            List of metric keys in display order.
            Standard metrics: total_pnl, total_earnings, base_earnings,
                             reward_earnings, total_fees
            Strategy-specific metrics can be added.
        """
        pass

    @staticmethod
    @abstractmethod
    def build_token_flow_string(position: pd.Series) -> str:
        """Build the token flow display string."""
        pass

    @staticmethod
    @abstractmethod
    def validate_position_data(position: pd.Series) -> bool:
        """Validate that position has required fields for this strategy."""
        pass


# ============================================================================
# STRATEGY REGISTRY
# ============================================================================

_STRATEGY_RENDERERS: Dict[str, type] = {}


def register_strategy_renderer(strategy_type: str):
    """
    Decorator to register a strategy renderer.

    Usage:
        @register_strategy_renderer('recursive_lending')
        class RecursiveLendingRenderer(StrategyRendererBase):
            ...
    """
    def decorator(renderer_class):
        _STRATEGY_RENDERERS[strategy_type] = renderer_class
        return renderer_class
    return decorator


def get_strategy_renderer(strategy_type: str) -> type:
    """
    Get renderer for a strategy type.

    Args:
        strategy_type: Strategy type identifier

    Returns:
        Renderer class for the strategy type

    Raises:
        ValueError: If strategy_type is not registered
    """
    if strategy_type not in _STRATEGY_RENDERERS:
        registered_types = ', '.join(_STRATEGY_RENDERERS.keys())
        raise ValueError(
            f"Unknown strategy type: '{strategy_type}'. "
            f"Registered types: [{registered_types}]. "
            f"Please implement a renderer by decorating with "
            f"@register_strategy_renderer('{strategy_type}')"
        )

    return _STRATEGY_RENDERERS[strategy_type]


def get_registered_strategy_types() -> List[str]:
    """
    Get list of all registered strategy types.

    Returns:
        List of registered strategy type identifiers
    """
    return list(_STRATEGY_RENDERERS.keys())


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def build_rate_lookup(rates_snapshot_df: pd.DataFrame) -> Dict:
    """
    Build rate lookup dictionary from rates snapshot.

    Args:
        rates_snapshot_df: DataFrame with rates snapshot data

    Returns:
        dict: {(protocol, token): {lend_apr, borrow_apr, borrow_fee, price}}
    """
    rate_lookup = {}
    for _, row in rates_snapshot_df.iterrows():
        key = (row['protocol'], row['token'])
        rate_lookup[key] = {
            'lend_apr': float(row['lend_total_apr']) if pd.notna(row['lend_total_apr']) else 0.0,
            'borrow_apr': float(row['borrow_total_apr']) if pd.notna(row['borrow_total_apr']) else 0.0,
            'borrow_fee': float(row['borrow_fee']) if pd.notna(row['borrow_fee']) else 0.0,
            'price': float(row['price_usd']) if pd.notna(row['price_usd']) else 0.0
        }
    return rate_lookup


def build_oracle_prices(rates_snapshot_df: pd.DataFrame) -> Dict[str, float]:
    """
    Build oracle price lookup from rates snapshot.

    Args:
        rates_snapshot_df: DataFrame with rates snapshot data

    Returns:
        dict: {token_symbol: price_usd}
    """
    oracle_prices = {}
    for _, row in rates_snapshot_df.iterrows():
        token = row['token']
        if token not in oracle_prices:
            oracle_prices[token] = float(row['price_usd']) if pd.notna(row['price_usd']) else 0.0
    return oracle_prices


def create_rate_helpers(
    rate_lookup: Dict,
    oracle_prices: Dict
) -> Tuple[Callable, Callable, Callable]:
    """
    Create helper functions for rate/price lookups.

    Args:
        rate_lookup: Rate lookup dictionary
        oracle_prices: Oracle price dictionary

    Returns:
        Tuple of (get_rate, get_borrow_fee, get_price_with_fallback) functions
    """
    def get_rate(token, protocol, rate_type):
        """Get rate from lookup dict."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        return rates.get(rate_type, 0.0)

    def get_borrow_fee(token, protocol):
        """Get borrow fee from lookup dict."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        return rates.get('borrow_fee', 0.0)

    def get_price_with_fallback(token, protocol):
        """3-tier fallback: protocol -> oracle -> None."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        price = rates.get('price')

        if price is not None and price > 0:
            return price

        # Fallback to oracle
        oracle_price = oracle_prices.get(token)
        if oracle_price is not None and oracle_price > 0:
            return oracle_price

        return None

    return get_rate, get_borrow_fee, get_price_with_fallback


# ============================================================================
# BATCH RENDERING INFRASTRUCTURE
# ============================================================================

def render_positions_batch(
    position_ids: List[str],
    timestamp_seconds: int,
    context: str = 'standalone'
) -> None:
    """
    Batch render multiple positions with optimized data loading.

    This is the primary entry point for rendering positions across all tabs.
    Handles all database connections and batch loading internally.

    Args:
        position_ids: List of position IDs to render
        timestamp_seconds: Unix timestamp defining "current time"
        context: Rendering context ('standalone', 'portfolio2', 'portfolio')

    Design Principle #5: Uses Unix seconds for all timestamps
    Design Principle #11: Dashboard as pure view - handles infrastructure internally
    """

    # Handle empty case
    if not position_ids:
        st.info("No positions to display.")
        return

    # ========================================
    # INFRASTRUCTURE SETUP (Internal)
    # ========================================
    # Design Principle: Function handles its own infrastructure
    # based on USE_CLOUD_DB global config

    from dashboard.dashboard_utils import get_db_connection
    from dashboard.db_utils import get_db_engine
    from analysis.position_service import PositionService

    conn = get_db_connection()
    engine = get_db_engine()
    service = PositionService(conn)

    # ========================================
    # BATCH DATA LOADING (Performance Optimization)
    # ========================================
    # Following ARCHITECTURE.md: Batch loading avoids N+1 queries

    # Import batch loading functions
    from dashboard.dashboard_renderer import get_all_position_statistics, get_all_rebalance_history

    # Load all position statistics (1 query for N positions)
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)

    # Load all rebalance history (1 query for N positions)
    all_rebalances = get_all_rebalance_history(position_ids, conn)

    # Load rates snapshot (1 query)
    timestamp_str = to_datetime_str(timestamp_seconds)
    ph = service._get_placeholder()
    rates_query = f"""
    SELECT protocol, token, lend_total_apr, borrow_total_apr, borrow_fee, price_usd
    FROM rates_snapshot
    WHERE timestamp = {ph}
    """
    rates_df = pd.read_sql_query(rates_query, engine, params=(timestamp_str,))

    # Build shared lookups (O(1) access for all positions)
    rate_lookup = build_rate_lookup(rates_df)
    oracle_prices = build_oracle_prices(rates_df)

    # ========================================
    # RENDER EACH POSITION
    # ========================================
    # Design Principle #13: Explicit error handling with debug info

    for position_id in position_ids:
        try:
            # Get position data
            position = service.get_position_by_id(position_id)

            if position is None:
                st.warning(f"Position {position_id} not found.")
                continue

            # Retrieve pre-loaded data
            stats = all_stats.get(position_id)
            rebalances = all_rebalances.get(position_id, [])

            # Determine strategy type (default to recursive_lending)
            strategy_type = position.get('strategy_type', 'recursive_lending')

            # Render using existing function
            render_position_expander(
                position=position,
                stats=stats,
                rebalances=rebalances,
                rate_lookup=rate_lookup,
                oracle_prices=oracle_prices,
                service=service,
                timestamp_seconds=timestamp_seconds,
                strategy_type=strategy_type,
                context=context,
                portfolio_id=position.get('portfolio_id'),
                expanded=False
            )

        except Exception as e:
            # Design Principle #13: Fail loudly with debug info, continue execution
            st.error(f"⚠️  Error rendering position {position_id}: {e}")
            print(f"⚠️  Error rendering position {position_id}: {e}")
            print(f"    Available position IDs: {position_ids}")
            # Continue rendering other positions
            continue


def render_position_single(
    position_id: str,
    timestamp_seconds: int,
    context: str = 'standalone'
) -> None:
    """
    Render a single position.

    Convenience wrapper around render_positions_batch for single position.
    Note: Less efficient than batch rendering - prefer batch when possible.

    Args:
        position_id: Position ID to render
        timestamp_seconds: Unix timestamp defining "current time"
        context: Rendering context ('standalone', 'portfolio2', 'portfolio')
    """
    render_positions_batch([position_id], timestamp_seconds, context)


def calculate_position_summary_stats(
    position_ids: List[str],
    timestamp_seconds: int
) -> Dict[str, float]:
    """
    Calculate aggregated summary statistics for a list of positions.

    Pure calculation function - does NOT render anything.

    Args:
        position_ids: List of position IDs to aggregate
        timestamp_seconds: Unix timestamp for stats lookup

    Returns:
        Dict of calculated metrics:
        {
            'total_deployed': float,
            'total_pnl': float,
            'total_earnings': float,
            'base_earnings': float,
            'reward_earnings': float,
            'total_fees': float,
            'roi': float,
            'avg_entry_apr': float,  # Time-and-capital-weighted
            'avg_realised_apr': float,  # Time-and-capital-weighted
            'avg_current_apr': float  # Time-and-capital-weighted
        }

    Raises:
        ValueError: If position_ids is empty or required position fields are missing

    Note:
        Connection management handled by USE_DB_CLOUD setting and service layer.
        APR calculations use time-and-capital-weighted averaging.
    """
    # Handle empty case - fail loudly
    if not position_ids:
        raise ValueError(
            "calculate_position_summary_stats requires at least one position_id. "
            "Received empty list."
        )

    # Setup infrastructure
    from dashboard.dashboard_utils import get_db_connection
    from dashboard.db_utils import get_db_engine
    from dashboard.dashboard_renderer import get_all_position_statistics
    from analysis.position_service import PositionService

    conn = get_db_connection()
    engine = get_db_engine()
    service = PositionService(conn)

    # Batch load data
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)

    positions_data = {}
    for position_id in position_ids:
        try:
            position = service.get_position_by_id(position_id)
            if position is None:
                # This should never happen - position_id came from active_positions
                raise ValueError(
                    f"Position {position_id} not found in database. "
                    f"This suggests data inconsistency - position_id exists in query "
                    f"but get_position_by_id returned None. "
                    f"Total positions requested: {len(position_ids)}"
                )
            positions_data[position_id] = position
        except Exception as e:
            # Fail loudly with context
            raise ValueError(
                f"Failed to load position {position_id} for summary stats. "
                f"Position index: {list(position_ids).index(position_id) + 1}/{len(position_ids)}. "
                f"Error: {e}"
            ) from e

    # Initialize accumulators
    total_deployed = 0.0
    total_pnl = 0.0
    total_earnings = 0.0
    base_earnings = 0.0
    reward_earnings = 0.0
    total_fees = 0.0
    weighted_entry_apr_sum = 0.0
    weighted_realised_apr_sum = 0.0
    weighted_current_apr_sum = 0.0
    total_weight = 0.0

    # Aggregate metrics
    for position_id in position_ids:
        position = positions_data.get(position_id)
        stats = all_stats.get(position_id)

        # Skip if missing data
        if position is None or stats is None:
            continue

        # Validate timestamp
        if to_seconds(stats.get('timestamp')) != timestamp_seconds:
            continue

        # Extract position values
        deployment_usd = _safe_float(position.get('deployment_usd'))
        entry_ts = to_seconds(position.get('entry_timestamp'))
        strategy_days = (timestamp_seconds - entry_ts) / 86400

        # Extract entry APR from position (not from stats)
        entry_net_apr = _safe_float(position.get('entry_net_apr'))

        # Extract statistics
        strategy_pnl = _safe_float(stats['total_pnl'])
        strategy_total_earnings = _safe_float(stats['total_earnings'])
        strategy_base_earnings = _safe_float(stats['base_earnings'])
        strategy_reward_earnings = _safe_float(stats['reward_earnings'])
        strategy_fees = _safe_float(stats['total_fees'])
        strategy_net_apr = _safe_float(stats['realized_apr'])
        current_net_apr = _safe_float(stats['current_apr'])

        # Accumulate sums
        total_deployed += deployment_usd
        total_pnl += strategy_pnl
        total_earnings += strategy_total_earnings
        base_earnings += strategy_base_earnings
        reward_earnings += strategy_reward_earnings
        total_fees += strategy_fees

        # Weighted APR components (all time-and-capital weighted)
        weight = strategy_days * deployment_usd
        weighted_entry_apr_sum += weight * entry_net_apr
        weighted_realised_apr_sum += weight * strategy_net_apr
        weighted_current_apr_sum += weight * current_net_apr
        total_weight += weight

    # Calculate derived metrics
    roi = (total_pnl / total_deployed * 100) if total_deployed > 0 else 0.0
    avg_entry_apr = (weighted_entry_apr_sum / total_weight) if total_weight > 0 else 0.0
    avg_realised_apr = (weighted_realised_apr_sum / total_weight) if total_weight > 0 else 0.0
    avg_current_apr = (weighted_current_apr_sum / total_weight) if total_weight > 0 else 0.0

    # Return calculated metrics
    return {
        'total_deployed': total_deployed,
        'total_pnl': total_pnl,
        'total_earnings': total_earnings,
        'base_earnings': base_earnings,
        'reward_earnings': reward_earnings,
        'total_fees': total_fees,
        'roi': roi,
        'avg_entry_apr': avg_entry_apr,
        'avg_realised_apr': avg_realised_apr,
        'avg_current_apr': avg_current_apr
    }


def render_position_summary_stats(
    stats: Dict[str, float],
    title: str = "Portfolio Summary"
) -> None:
    """
    Render pre-calculated summary statistics.

    Pure rendering function - takes pre-calculated stats and displays them.

    Args:
        stats: Pre-calculated stats dict from calculate_position_summary_stats()
        title: Display title for the stats section

    Returns:
        None (only renders UI)

    Displays metrics in a 3-row layout (4-3-3 columns):
    - Row 1: Total Deployed, Total PnL (with ROI delta), Total Earnings, Base Earnings
    - Row 2: Reward Earnings, Fees, Avg Realised APR
    - Row 3: Avg Current APR
    """
    # Render UI - 3-row layout (4-3-3 columns)
    st.markdown(f"### 📊 {title}")

    # Row 1: 4 columns
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Deployed", f"${stats['total_deployed']:,.2f}")
    with col2:
        roi_display = f"ROI: {stats['roi']:.2f}%"
        st.metric("Total PnL (Real+Unreal)", f"${stats['total_pnl']:,.2f}", delta=roi_display)
    with col3:
        st.metric("Total Earnings", f"${stats['total_earnings']:,.2f}")
    with col4:
        st.metric("Base Earnings", f"${stats['base_earnings']:,.2f}")

    # Row 2: 3 columns
    col5, col6, col7 = st.columns(3)
    with col5:
        st.metric("Reward Earnings", f"${stats['reward_earnings']:,.2f}")
    with col6:
        st.metric("Fees", f"${stats['total_fees']:,.2f}")
    with col7:
        st.metric("Avg Realised APR", f"{stats['avg_realised_apr'] * 100:.2f}%")

    # Row 3: 3 columns
    col8, _, _ = st.columns(3)
    with col8:
        st.metric("Avg Current APR", f"{stats['avg_current_apr'] * 100:.2f}%")

    st.markdown("---")  # Separator


# ============================================================================
# SEGMENT DATA BUILDERS
# ============================================================================

def build_segment_data_from_position(position: pd.Series) -> Dict:
    """
    Build segment data from position entry data (for positions with no rebalances).

    This converts the position's entry_* fields into the segment_data format
    that the leg builders expect.

    Args:
        position: Position record from database

    Returns:
        Dict with opening_token_amount_*, opening_price_*, opening_*_rate fields
    """
    segment_data = {
        # REQUIRED: Explicit flag for segment type detection
        'is_live_segment': True,

        # Token amounts from position entry (stored in positions table)
        'opening_token_amount_1a': position.get('entry_token_amount_1a'),
        'opening_token_amount_2a': position.get('entry_token_amount_2a'),
        'opening_token_amount_2b': position.get('entry_token_amount_2b'),
        'opening_token_amount_3b': position.get('entry_token_amount_3b'),

        # Prices from position entry
        'opening_price_1a': position.get('entry_price_1a'),
        'opening_price_2a': position.get('entry_price_2a'),
        'opening_price_2b': position.get('entry_price_2b'),
        'opening_price_3b': position.get('entry_price_3b'),

        # Rates from position entry
        'opening_lend_rate_1a': position.get('entry_lend_rate_1a'),
        'opening_borrow_rate_2a': position.get('entry_borrow_rate_2a'),
        'opening_lend_rate_2b': position.get('entry_lend_rate_2b'),
        'opening_borrow_rate_3b': position.get('entry_borrow_rate_3b'),
    }

    return segment_data


def build_segment_data_from_rebalance(rebalance: Dict) -> Dict:
    """
    Build segment data from rebalance record.

    This extracts the entry/opening_* fields from a rebalance record.
    Use this for rendering ANY segment (historical or live) - the last rebalance
    in the database is the current/live segment.

    Args:
        rebalance: Rebalance record (dict from position_rebalances table)

    Returns:
        Dict with opening_token_amount_*, opening_price_*, opening_*_rate,
        and closing_price_* fields (for historical segments)
    """
    segment_data = {
        # REQUIRED: Explicit flag for segment type detection
        'is_live_segment': False,

        # Token amounts from rebalance entry
        'opening_token_amount_1a': rebalance.get('entry_token_amount_1a'),
        'opening_token_amount_2a': rebalance.get('entry_token_amount_2a'),
        'opening_token_amount_2b': rebalance.get('entry_token_amount_2b'),
        'opening_token_amount_3b': rebalance.get('entry_token_amount_3b'),

        # Prices from rebalance opening
        'opening_price_1a': rebalance.get('opening_price_1a'),
        'opening_price_2a': rebalance.get('opening_price_2a'),
        'opening_price_2b': rebalance.get('opening_price_2b'),
        'opening_price_3b': rebalance.get('opening_price_3b'),

        # Prices from rebalance closing (for historical segments)
        'closing_price_1a': rebalance.get('closing_price_1a'),
        'closing_price_2a': rebalance.get('closing_price_2a'),
        'closing_price_2b': rebalance.get('closing_price_2b'),
        'closing_price_3b': rebalance.get('closing_price_3b'),

        # Rates from rebalance opening
        'opening_lend_rate_1a': rebalance.get('opening_lend_rate_1a'),
        'opening_borrow_rate_2a': rebalance.get('opening_borrow_rate_2a'),
        'opening_lend_rate_2b': rebalance.get('opening_lend_rate_2b'),
        'opening_borrow_rate_3b': rebalance.get('opening_borrow_rate_3b'),

        # Rates from rebalance closing (for historical segments)
        'closing_lend_rate_1a': rebalance.get('closing_lend_rate_1a'),
        'closing_borrow_rate_2a': rebalance.get('closing_borrow_rate_2a'),
        'closing_lend_rate_2b': rebalance.get('closing_lend_rate_2b'),
        'closing_borrow_rate_3b': rebalance.get('closing_borrow_rate_3b'),
    }

    return segment_data




# ============================================================================
# CORE RENDERING FUNCTIONS (Strategy-Agnostic)
# ============================================================================

def build_position_expander_title(
    position: pd.Series,
    stats: Optional[Dict],
    strategy_type: str,
    include_timestamp: bool = True
) -> str:
    """
    Build expander title for a position.

    Args:
        position: Position record
        stats: Pre-calculated statistics
        strategy_type: Strategy type identifier
        include_timestamp: Whether to include entry timestamp

    Returns:
        Formatted title string
    """
    # Get strategy-specific renderer
    renderer = get_strategy_renderer(strategy_type)

    # Build token flow using strategy-specific logic
    token_flow = renderer.build_token_flow_string(position)

    # Build protocol pair
    protocol_pair = f"{position['protocol_a']} ↔ {position['protocol_b']}"

    # Get metrics (standard across all strategies)
    entry_apr = position.get('entry_net_apr', 0.0) * 100
    deployment = position['deployment_usd']

    if stats:
        current_value = stats['current_value']
        current_apr = stats.get('current_apr', 0.0) * 100
        realized_apr = stats.get('realized_apr', 0.0) * 100
        total_pnl = stats['total_pnl']
        total_earnings = stats['total_earnings']
        base_earnings = stats.get('base_earnings', 0.0)
        reward_earnings = stats.get('reward_earnings', 0.0)
        total_fees = stats['total_fees']
    else:
        current_value = deployment
        current_apr = entry_apr
        realized_apr = 0.0
        total_pnl = 0.0
        total_earnings = 0.0
        base_earnings = 0.0
        reward_earnings = 0.0
        total_fees = 0.0

    # Build title
    title_parts = []

    if include_timestamp:
        entry_ts_str = to_datetime_str(to_seconds(position['entry_timestamp']))
        title_parts.append(entry_ts_str)

    title_parts.extend([
        token_flow,
        protocol_pair,
        f"Entry {entry_apr:.2f}%",
        f"Current {current_apr:.2f}%",
        f"Net APR {realized_apr:.2f}%",
        f"Value \\${current_value:,.2f}",
        f"PnL \\${total_pnl:,.2f}",
        f"Earnings \\${total_earnings:,.2f}",
        f"Base \\${base_earnings:,.2f}",
        f"Rewards \\${reward_earnings:,.2f}",
        f"Fees \\${total_fees:,.2f}"
    ])

    return "▶ " + " | ".join(title_parts)


def render_strategy_summary_metrics(
    stats: Optional[Dict],
    deployment: float,
    strategy_type: str
) -> None:
    """
    Render strategy summary metrics (layout depends on strategy type).

    Args:
        stats: Pre-calculated statistics
        deployment: Deployment USD
        strategy_type: Strategy type identifier
    """
    if not stats:
        st.info("Statistics not available. Click 'Calculate Statistics' to generate.")
        return

    # Get strategy-specific metric layout
    renderer = get_strategy_renderer(strategy_type)
    metrics_layout = renderer.get_metrics_layout()

    # Map metric keys to display info
    metric_config = {
        'total_pnl': ('Total PnL', 'total_pnl'),
        'total_earnings': ('Total Earnings', 'total_earnings'),
        'base_earnings': ('Base Earnings', 'base_earnings'),
        'reward_earnings': ('Reward Earnings', 'reward_earnings'),
        'total_fees': ('Total Fees', 'total_fees'),
        'funding_received': ('Funding Received', 'funding_received'),
        'hedging_costs': ('Hedging Costs', 'hedging_costs')
    }

    # Create columns based on layout
    cols = st.columns(len(metrics_layout))

    for idx, metric_key in enumerate(metrics_layout):
        if metric_key not in metric_config:
            continue

        label, stats_key = metric_config[metric_key]
        value = stats.get(stats_key, 0.0)
        pct = (value / deployment * 100) if deployment > 0 else 0

        with cols[idx]:
            st.metric(label, f"${value:,.2f}", f"{pct:.2f}%")


def render_segment_summary(rebalance: Dict) -> None:
    """
    Render summary metrics for a historical segment (from rebalance record).

    Args:
        rebalance: Rebalance record with realized metrics
    """
    # Extract timestamps for duration calculation
    opening_ts = rebalance.get('opening_timestamp')
    closing_ts = rebalance.get('closing_timestamp')

    # Calculate duration if timestamps available
    duration_str = "N/A"
    if opening_ts and closing_ts:
        try:
            from utils.time_helpers import to_seconds
            from datetime import datetime

            # Convert to seconds and calculate duration
            opening_sec = to_seconds(opening_ts)
            closing_sec = to_seconds(closing_ts)
            duration_days = (closing_sec - opening_sec) / 86400  # seconds to days
            duration_str = f"{duration_days:.1f} days"
        except:
            duration_str = "N/A"

    # Show realized metrics from rebalance
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        pnl = rebalance.get('realised_pnl', 0.0) or 0.0
        st.metric("Realized PnL", f"${pnl:,.2f}")

    with col2:
        earnings = rebalance.get('realised_lend_earnings', 0.0) or 0.0
        st.metric("Lend Earnings", f"${earnings:,.2f}")

    with col3:
        costs = rebalance.get('realised_borrow_costs', 0.0) or 0.0
        st.metric("Borrow Costs", f"${costs:,.2f}")

    with col4:
        fees = rebalance.get('realised_fees', 0.0) or 0.0
        st.metric("Fees Paid", f"${fees:,.2f}")

    with col5:
        st.metric("Duration", duration_str)


def render_historical_segment(
    position: pd.Series,
    rebalance: Dict,
    sequence_number: int,
    get_rate: Callable,
    get_borrow_fee: Callable,
    get_price_with_fallback: Callable,
    strategy_type: str
) -> None:
    """
    Render a historical segment (collapsed expander).

    Args:
        position: Position record (for protocol/token info)
        rebalance: Rebalance record with opening/closing state
        sequence_number: Segment number (1, 2, 3, ...)
        get_rate: Rate lookup function
        get_borrow_fee: Borrow fee lookup function
        get_price_with_fallback: Price lookup function
        strategy_type: Strategy type identifier
    """
    # Build segment title
    opening_ts = rebalance.get('opening_timestamp', 'N/A')
    closing_ts = rebalance.get('closing_timestamp', 'N/A')
    title = f"📊 Segment {sequence_number}: {opening_ts} → {closing_ts}"

    with st.expander(title, expanded=False):
        # Show segment summary metrics
        render_segment_summary(rebalance)

        st.markdown("---")

        # Show detail table using segment data from rebalance
        st.markdown("#### Segment Details")

        segment_data = build_segment_data_from_rebalance(rebalance)

        # Get renderer and call detail table
        renderer = get_strategy_renderer(strategy_type)
        renderer.render_detail_table(
            position,
            get_rate,
            get_borrow_fee,
            get_price_with_fallback,
            [rebalance],  # Pass this rebalance as the "most recent" one
            segment_type='historical'
        )


# ============================================================================
# ACTION BUTTON RENDERERS
# ============================================================================

def render_position_actions_standalone(
    position: pd.Series,
    timestamp_seconds: int,
    service
) -> None:
    """Render action buttons for standalone position (Positions tab)."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Rebalance Position", key=f"rebal_{position['position_id']}"):
            # Check for future rebalances
            if service.has_future_rebalances(position['position_id'], timestamp_seconds):
                st.error("❌ Cannot rebalance: future rebalances exist")
            else:
                try:
                    # Call rebalance method
                    rebalance_id = service.rebalance_position(
                        position['position_id'],
                        timestamp_seconds,
                        'manual_rebalance',
                        'Rebalanced via dashboard (Positions tab)'
                    )
                    st.success(f"✅ Position rebalanced (ID: {rebalance_id[:8]}...)")
                    st.rerun()
                except ValueError as e:
                    # Position validation errors (inactive, not found, etc.)
                    st.error(f"❌ Rebalance failed: {e}")
                except Exception as e:
                    # Unexpected errors
                    st.error(f"❌ Unexpected error during rebalance: {e}")
                    print(f"⚠️ Rebalance error: {e}")
                    import traceback
                    traceback.print_exc()

    with col2:
        if st.button("❌ Close Position", key=f"close_{position['position_id']}"):
            # Close logic
            service.close_position(
                position['position_id'],
                timestamp_seconds,
                'manual_close',
                'Closed via dashboard'
            )
            st.success("Position closed")
            st.rerun()


def render_position_actions_portfolio(
    position: pd.Series,
    timestamp_seconds: int,
    service,
    portfolio_id: str
) -> None:
    """Render action buttons for position within portfolio (Portfolios tab)."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Rebalance Position", key=f"rebal_port_{position['position_id']}"):
            # Check for future rebalances
            if service.has_future_rebalances(position['position_id'], timestamp_seconds):
                st.error("❌ Cannot rebalance: future rebalances exist")
            else:
                try:
                    # Call rebalance method
                    rebalance_id = service.rebalance_position(
                        position['position_id'],
                        timestamp_seconds,
                        'manual_rebalance',
                        f'Rebalanced via dashboard (Portfolio {portfolio_id})'
                    )
                    st.success(f"✅ Position rebalanced (ID: {rebalance_id[:8]}...)")
                    st.rerun()
                except ValueError as e:
                    # Position validation errors (inactive, not found, etc.)
                    st.error(f"❌ Rebalance failed: {e}")
                except Exception as e:
                    # Unexpected errors
                    st.error(f"❌ Unexpected error during rebalance: {e}")
                    print(f"⚠️ Rebalance error: {e}")
                    import traceback
                    traceback.print_exc()

    with col2:
        if st.button("❌ Close Position", key=f"close_port_{position['position_id']}"):
            service.close_position(
                position['position_id'],
                timestamp_seconds,
                'manual_close',
                f'Closed from portfolio {portfolio_id}'
            )
            st.success("Position closed")
            st.rerun()


# ============================================================================
# RECURSIVE LENDING RENDERER (Current Implementation)
# ============================================================================

@register_strategy_renderer('recursive_lending')
class RecursiveLendingRenderer(StrategyRendererBase):
    """Renderer for 4-leg recursive lending strategies."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Recursive Lending"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        """Build token flow: token1 → token2 → token3 (or → token1 if loop)"""
        token_flow = position['token1']

        # Get token2 and token3 (avoid pandas truth value ambiguity)
        token2 = position.get('token2')
        token3 = position.get('token3')

        has_token2 = token2 is not None and pd.notna(token2) and str(token2).strip() != ''
        has_token3 = token3 is not None and pd.notna(token3) and str(token3).strip() != ''

        if has_token2:
            token_flow += f" → {position['token2']}"

        if has_token3:
            token_flow += f" → {position['token3']}"
        elif has_token2:
            # Loop back to token1 if no token3
            token_flow += f" → {position['token1']}"

        return token_flow

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        """Validate recursive lending position has required fields."""
        required_fields = [
            'token1', 'token2', 'protocol_a', 'protocol_b',
            'l_a', 'b_a', 'l_b', 'b_b',
            'entry_lend_rate_1a', 'entry_borrow_rate_2a',
            'entry_lend_rate_2b', 'entry_borrow_rate_3b',
            'entry_price_1a', 'entry_price_2a',
            'entry_price_2b', 'entry_price_3b'
        ]

        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        """Standard 5-metric layout for recursive lending."""
        return ['total_pnl', 'total_earnings', 'base_earnings',
                'reward_earnings', 'total_fees']

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None,
        segment_type: str = 'live'
    ) -> None:
        """Render 4-leg detail table for recursive lending."""

        deployment = position['deployment_usd']

        # Build segment_data from last rebalance
        # If position has rebalances, use the last one's entry values
        # The LAST rebalance in the list is always the current/live segment
        if not rebalances or len(rebalances) == 0:
            # No rebalances yet - use position's entry data directly
            segment_data = build_segment_data_from_position(position)
        else:
            # ALWAYS use last rebalance's ENTRY values (start of current segment)
            # Last rebalance = current/live segment (has closing_timestamp=NULL)
            segment_data = build_segment_data_from_rebalance(rebalances[-1])

        detail_data = []

        # For historical segments, use closing prices from segment_data
        # For live segments, use current market prices
        if segment_type == 'historical' and segment_data:
            token2_price_live = float(segment_data.get('closing_price_2a')) if segment_data.get('closing_price_2a') is not None else None
            token1_price_live = float(segment_data.get('closing_price_1a')) if segment_data.get('closing_price_1a') is not None else None
        else:
            token2_price_live = get_price_with_fallback(position['token2'], position['protocol_a'])
            token1_price_live = get_price_with_fallback(position['token1'], position['protocol_a'])

        # ========== LEG 1: Protocol A - Lend token1 ==========
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='leg_1a',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_lend_rate_1a'],
            entry_price=position['entry_price_1a'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token2'],  # Leg 2A borrows token2
            borrow_price_live=token2_price_live,
            borrow_price_entry=position['entry_price_2a'],
            borrow_weight_value=position['b_a'],
            liquidation_threshold=position.get('entry_liquidation_threshold_1a', 0.0),
            borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
        ))

        # ========== LEG 2: Protocol A - Borrow token2 ==========
        detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
            position=position,
            leg_id='leg_2a',
            token=position['token2'],
            protocol=position['protocol_a'],
            weight=position['b_a'],
            entry_rate=position['entry_borrow_rate_2a'],
            entry_price=position['entry_price_2a'],
            collateral_ratio=position.get('entry_collateral_ratio_1a', 0.0),
            liquidation_threshold=position.get('entry_liquidation_threshold_1a', 0.0),
            get_rate=get_rate,
            get_borrow_fee=get_borrow_fee,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            collateral_token=position['token1'],
            collateral_price_live=token1_price_live,
            collateral_price_entry=position['entry_price_1a'],
            borrow_weight=position.get('entry_borrow_weight_2a', 1.0)
        ))

        # ========== LEG 3: Protocol B - Lend token2 ==========
        # Check if there's a 4th leg (borrow token3) to calculate liquidation
        token3 = position.get('token3')
        b_b = position.get('b_b')
        has_leg4 = token3 is not None and pd.notna(token3) and str(token3).strip() != '' and b_b is not None and pd.notna(b_b) and float(b_b) > 0

        # For historical segments, use closing prices from segment_data
        # For live segments, use current market prices
        if segment_type == 'historical' and segment_data:
            token3_price_live = float(segment_data.get('closing_price_3b')) if (has_leg4 and segment_data.get('closing_price_3b') is not None) else None
            token2_price_live_protocolb = float(segment_data.get('closing_price_2b')) if segment_data.get('closing_price_2b') is not None else None
        else:
            token3_price_live = get_price_with_fallback(position['token3'], position['protocol_b']) if has_leg4 else None
            token2_price_live_protocolb = get_price_with_fallback(position['token2'], position['protocol_b'])

        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='leg_2b',
            token=position['token2'],
            protocol=position['protocol_b'],
            weight=position['l_b'],
            entry_rate=position['entry_lend_rate_2b'],
            entry_price=position['entry_price_2b'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token3'] if has_leg4 else None,  # Leg 3B borrows token3 (if exists)
            borrow_price_live=token3_price_live,
            borrow_price_entry=position['entry_price_3b'] if has_leg4 else None,
            borrow_weight_value=position['b_b'] if has_leg4 else None,
            liquidation_threshold=position.get('entry_liquidation_threshold_2b', 0.0) if has_leg4 else None,
            borrow_weight=position.get('entry_borrow_weight_3b', 1.0) if has_leg4 else 1.0
        ))

        # ========== LEG 4: Protocol B - Borrow token3 (if levered) ==========
        # Use has_leg4 check from Leg 3
        if has_leg4:
            detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
                position=position,
                leg_id='leg_3b',
                token=position['token3'],
                protocol=position['protocol_b'],
                weight=position['b_b'],
                entry_rate=position['entry_borrow_rate_3b'],
                entry_price=position['entry_price_3b'],
                collateral_ratio=position.get('entry_collateral_ratio_2b', 0.0),
                liquidation_threshold=position.get('entry_liquidation_threshold_2b', 0.0),
                get_rate=get_rate,
                get_borrow_fee=get_borrow_fee,
                get_price_with_fallback=get_price_with_fallback,
                deployment=deployment,
                segment_data=segment_data,
                segment_type=segment_type,
                collateral_token=position['token2'],
                collateral_price_live=token2_price_live_protocolb,
                collateral_price_entry=position['entry_price_2b'],
                borrow_weight=position.get('entry_borrow_weight_3b', 1.0)
            ))

        # Display table
        detail_df = pd.DataFrame(detail_data)
        st.dataframe(detail_df, width="stretch")

    @staticmethod
    def _build_lend_leg_row(
        position: pd.Series,
        leg_id: str,
        token: str,
        protocol: str,
        weight: float,
        entry_rate: float,
        entry_price: float,
        get_rate: Callable,
        get_price_with_fallback: Callable,
        deployment: float,
        segment_data: Optional[Dict] = None,
        segment_type: str = 'live',
        borrow_token: str = None,
        borrow_price_live: float = None,
        borrow_price_entry: float = None,
        borrow_weight_value: float = None,
        liquidation_threshold: float = None,
        borrow_weight: float = 1.0
    ) -> Dict:
        """Build table row for a lending leg (16-column structure)."""

        # ========================================
        # STEP 1: Detect segment type - FAIL LOUD if flag missing
        # ========================================
        if segment_data is None:
            raise ValueError("segment_data is None - must provide segment_data with is_live_segment flag")

        if 'is_live_segment' not in segment_data:
            raise ValueError(
                f"segment_data missing required 'is_live_segment' flag. "
                f"Keys present: {list(segment_data.keys())}"
            )

        is_live_segment = segment_data['is_live_segment']  # No default - fail if missing

        # Initialize variables (avoid "possibly unbound" errors)
        segment_entry_rate = None
        segment_entry_price = None
        token_amount = None

        # ========================================
        # STEP 2: Extract data based on segment type
        # ========================================
        if not is_live_segment:
            # REBALANCE SEGMENT PATH: Use position_rebalances table
            # segment_data contains rebalance opening values (from build_rebalance_segment_data)
            if leg_id == 'leg_1a':
                segment_entry_rate = segment_data.get('opening_lend_rate_1a')
                segment_entry_price = segment_data.get('opening_price_1a')
                token_amount = segment_data.get('opening_token_amount_1a')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_lend_rate_1a')) if segment_data.get('closing_lend_rate_1a') is not None else None
                live_price = float(segment_data.get('closing_price_1a')) if segment_data.get('closing_price_1a') is not None else None
            elif leg_id == 'leg_2b':
                segment_entry_rate = segment_data.get('opening_lend_rate_2b')
                segment_entry_price = segment_data.get('opening_price_2b')
                token_amount = segment_data.get('opening_token_amount_2b')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_lend_rate_2b')) if segment_data.get('closing_lend_rate_2b') is not None else None
                live_price = float(segment_data.get('closing_price_2b')) if segment_data.get('closing_price_2b') is not None else None
        else:
            # LIVE SEGMENT PATH: Use positions table + current rates
            # segment_data already contains position entry values (from build_live_segment_data)
            live_rate = get_rate(token, protocol, 'lend_apr')
            live_price = get_price_with_fallback(token, protocol)

            # Map leg_id to field names
            if leg_id == 'leg_1a':
                segment_entry_rate = segment_data.get('opening_lend_rate_1a')
                segment_entry_price = segment_data.get('opening_price_1a')
                token_amount = segment_data.get('opening_token_amount_1a')
            elif leg_id == 'leg_2b':
                segment_entry_rate = segment_data.get('opening_lend_rate_2b')
                segment_entry_price = segment_data.get('opening_price_2b')
                token_amount = segment_data.get('opening_token_amount_2b')

        # Pandas-safe checks (avoid truth value ambiguity)
        def safe_value(val):
            """Check if value is valid (not None, not NaN)."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                return float(val) != 0
            except (TypeError, ValueError):
                return False

        # Calculate liquidation price and distance for lend legs (they are collateral)
        # Initialize liquidation values
        entry_liq_dist_str = "-"
        live_liq_dist_str = "-"
        liq_price_str = "-"

        # Only calculate if this lend leg has a corresponding borrow leg
        if borrow_token and borrow_price_live and borrow_price_entry and liquidation_threshold and liquidation_threshold > 0:
            try:
                from analysis.position_calculator import PositionCalculator
                calc = PositionCalculator()

                # Get loan leg token amount based on which lend leg this is
                loan_token_amount = None
                if segment_data:
                    if leg_id == 'leg_1a':
                        # Leg 1A lends, Leg 2A borrows
                        loan_token_amount = segment_data.get('opening_token_amount_2a')
                    elif leg_id == 'leg_2b':
                        # Leg 2B lends, Leg 3B borrows
                        loan_token_amount = segment_data.get('opening_token_amount_3b')

                # Collateral is this lend leg's tokens at live price
                collateral_value = float(token_amount) * float(live_price) if token_amount else 0.0
                # Loan is the borrow leg's tokens at live price
                loan_value = float(loan_token_amount) * float(borrow_price_live) if loan_token_amount and borrow_price_live else 0.0

                # Calculate liquidation price using LIVE prices (current threshold)
                if safe_value(live_price) and safe_value(borrow_price_live) and loan_value > 0:
                    try:
                        live_liq_result = calc.calculate_liquidation_price(
                            collateral_value=collateral_value,
                            loan_value=loan_value,
                            lending_token_price=live_price,  # This lend token (live/exit price)
                            borrowing_token_price=borrow_price_live,  # Borrow token (live/exit price)
                            lltv=liquidation_threshold,
                            side='lending',  # Calculate from lending/collateral side
                            borrow_weight=borrow_weight
                        )
                        live_liq_price = live_liq_result['liq_price']
                        live_liq_dist_pct = live_liq_result['pct_distance']

                        # Format live liquidation distance (from function)
                        live_liq_dist_str = f"{live_liq_dist_pct * 100:+.1f}%"

                        # Calculate entry distance: use segment entry price
                        if safe_value(segment_entry_price) and live_liq_price > 0 and live_liq_price != float('inf'):
                            entry_liq_dist_pct = (live_liq_price - float(segment_entry_price)) / float(segment_entry_price)
                            entry_liq_dist_str = f"{entry_liq_dist_pct * 100:+.1f}%"

                        # Format liquidation price
                        if live_liq_price == float('inf'):
                            liq_price_str = "∞"
                        elif live_liq_price == 0.0:
                            liq_price_str = "$0.00"
                        else:
                            liq_price_str = f"${live_liq_price:,.4f}"
                    except Exception as e:
                        print(f"⚠️  [LIQUIDATION-LEND] Failed for {leg_id}/{token}/{protocol}: {e}")
                        print(f"    token_amount: {token_amount}")
                        print(f"    loan_token_amount: {loan_token_amount}")
                        print(f"    live_price: {live_price}")
                        print(f"    borrow_price_live: {borrow_price_live}")
                        print(f"    collateral_value: {collateral_value if 'collateral_value' in locals() else 'not calculated'}")
                        print(f"    loan_value: {loan_value if 'loan_value' in locals() else 'not calculated'}")
                        liq_price_str = "N/A"
                        live_liq_dist_str = "N/A"
            except Exception as e:
                # If import or calculation fails, keep default "-"
                print(f"⚠️  [LIQUIDATION-LEND] Import or setup failed for {leg_id}/{token}/{protocol}: {e}")
                import traceback
                traceback.print_exc()

        # ========================================
        # STEP 3: Build row with conditional column headers
        # ========================================
        if is_live_segment:
            # LIVE SEGMENT: Entry → Live
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Lend',
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Live Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Entry Price ($)': f"{segment_entry_price:.4f}" if safe_value(segment_entry_price) else "N/A",
                'Live Price ($)': f"{live_price:.4f}" if safe_value(live_price) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{token_amount:,.5f}" if safe_value(token_amount) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': "-",  # Lend legs don't have fees
                'Entry Liquidation Distance': entry_liq_dist_str,
                'Live Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD"
            }
        else:
            # REBALANCE SEGMENT: Segment Entry → Exit
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Lend',
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Segment Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Exit Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Segment Entry Price ($)': f"{segment_entry_price:.4f}" if safe_value(segment_entry_price) else "N/A",
                'Exit Price ($)': f"{live_price:.4f}" if safe_value(live_price) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{token_amount:,.5f}" if safe_value(token_amount) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': "-",  # Lend legs don't have fees
                'Segment Entry Liquidation Distance': entry_liq_dist_str,
                'Exit Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD"
            }

    @staticmethod
    def _build_borrow_leg_row(
        position: pd.Series,
        leg_id: str,
        token: str,
        protocol: str,
        weight: float,
        entry_rate: float,
        entry_price: float,
        collateral_ratio: float,
        liquidation_threshold: float,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        deployment: float,
        segment_data: Optional[Dict] = None,
        segment_type: str = 'live',
        collateral_token: str = None,
        collateral_price_live: float = None,
        collateral_price_entry: float = None,
        borrow_weight: float = 1.0
    ) -> Dict:
        """Build table row for a borrowing leg (16-column structure) with liquidation calculations."""

        # ========================================
        # STEP 1: Detect segment type - FAIL LOUD if flag missing
        # ========================================
        if segment_data is None:
            raise ValueError("segment_data is None - must provide segment_data with is_live_segment flag")

        if 'is_live_segment' not in segment_data:
            raise ValueError(
                f"segment_data missing required 'is_live_segment' flag. "
                f"Keys present: {list(segment_data.keys())}"
            )

        is_live_segment = segment_data['is_live_segment']  # No default - fail if missing

        # Initialize variables (avoid "possibly unbound" errors)
        segment_entry_rate = None
        segment_entry_price = None
        token_amount = None
        live_rate = None
        live_price = None
        borrow_fee = None

        # ========================================
        # STEP 2: Extract data based on segment type
        # ========================================
        if not is_live_segment:
            # REBALANCE SEGMENT PATH: Use position_rebalances table
            # segment_data contains rebalance opening values (from build_rebalance_segment_data)
            if leg_id == 'leg_2a':
                segment_entry_rate = segment_data.get('opening_borrow_rate_2a')
                segment_entry_price = segment_data.get('opening_price_2a')
                token_amount = segment_data.get('opening_token_amount_2a')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_borrow_rate_2a')) if segment_data.get('closing_borrow_rate_2a') is not None else None
                live_price = float(segment_data.get('closing_price_2a')) if segment_data.get('closing_price_2a') is not None else None
            elif leg_id == 'leg_3b':
                segment_entry_rate = segment_data.get('opening_borrow_rate_3b')
                segment_entry_price = segment_data.get('opening_price_3b')
                token_amount = segment_data.get('opening_token_amount_3b')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_borrow_rate_3b')) if segment_data.get('closing_borrow_rate_3b') is not None else None
                live_price = float(segment_data.get('closing_price_3b')) if segment_data.get('closing_price_3b') is not None else None
            # Get borrow fee (always from current market - not stored in rebalance history)
            borrow_fee = get_borrow_fee(token, protocol)
        else:
            # LIVE SEGMENT PATH: Use positions table + current rates
            # segment_data already contains position entry values (from build_live_segment_data)
            live_rate = get_rate(token, protocol, 'borrow_apr')
            live_price = get_price_with_fallback(token, protocol)
            borrow_fee = get_borrow_fee(token, protocol)

            # Map leg_id to field names
            if leg_id == 'leg_2a':
                segment_entry_rate = segment_data.get('opening_borrow_rate_2a')
                segment_entry_price = segment_data.get('opening_price_2a')
                token_amount = segment_data.get('opening_token_amount_2a')
            elif leg_id == 'leg_3b':
                segment_entry_rate = segment_data.get('opening_borrow_rate_3b')
                segment_entry_price = segment_data.get('opening_price_3b')
                token_amount = segment_data.get('opening_token_amount_3b')

        # Pandas-safe checks (avoid truth value ambiguity)
        def safe_value(val):
            """Check if value is valid (not None, not NaN)."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                return float(val) != 0
            except (TypeError, ValueError):
                return False

        # Calculate liquidation price and distance
        # Get collateral leg token amount based on which borrow leg this is
        collateral_token_amount = None
        collateral_leg_weight = 0.0

        if segment_data:
            if leg_id == 'leg_2a':
                # Leg 2A borrows, Leg 1A is collateral
                collateral_token_amount = segment_data.get('opening_token_amount_1a')
                collateral_leg_weight = position.get('l_a', 0.0)
            elif leg_id == 'leg_3b':
                # Leg 3B borrows, Leg 2B is collateral
                collateral_token_amount = segment_data.get('opening_token_amount_2b')
                collateral_leg_weight = position.get('l_b', 0.0)

        # Collateral is the lend leg's tokens at live price
        collateral_value = float(collateral_token_amount) * float(collateral_price_live) if collateral_token_amount and collateral_price_live else 0.0
        # Loan is this borrow leg's tokens at live price
        loan_value = float(token_amount) * float(live_price) if token_amount else 0.0

        # Initialize liquidation values
        entry_liq_dist_str = "N/A"
        live_liq_dist_str = "N/A"
        liq_price_str = "N/A"

        # Only calculate if we have necessary data
        if collateral_price_live and collateral_price_entry and liquidation_threshold > 0:
            try:
                from analysis.position_calculator import PositionCalculator
                calc = PositionCalculator()

                # Calculate liquidation price using LIVE prices (current threshold)
                if safe_value(live_price) and safe_value(collateral_price_live):
                    try:
                        live_liq_result = calc.calculate_liquidation_price(
                            collateral_value=collateral_value,
                            loan_value=loan_value,
                            lending_token_price=collateral_price_live,
                            borrowing_token_price=live_price,
                            lltv=liquidation_threshold,
                            side='borrowing',
                            borrow_weight=borrow_weight
                        )
                        live_liq_price = live_liq_result['liq_price']
                        live_liq_dist_pct = live_liq_result['pct_distance']

                        # Format live liquidation distance (from function)
                        live_liq_dist_str = f"{live_liq_dist_pct * 100:+.1f}%"

                        # Calculate entry distance: use segment entry price
                        if safe_value(segment_entry_price) and live_liq_price > 0 and live_liq_price != float('inf'):
                            entry_liq_dist_pct = (live_liq_price - float(segment_entry_price)) / float(segment_entry_price)
                            entry_liq_dist_str = f"{entry_liq_dist_pct * 100:+.1f}%"

                        # Format liquidation price
                        if live_liq_price == float('inf'):
                            liq_price_str = "∞"
                        elif live_liq_price == 0.0:
                            liq_price_str = "$0.00"
                        else:
                            liq_price_str = f"${live_liq_price:,.4f}"
                    except Exception as e:
                        print(f"⚠️  [LIQUIDATION-BORROW] Failed for {leg_id}/{token}/{protocol}: {e}")
                        print(f"    token_amount: {token_amount}")
                        print(f"    collateral_token_amount: {collateral_token_amount}")
                        print(f"    live_price: {live_price}")
                        print(f"    collateral_price_live: {collateral_price_live}")
                        print(f"    collateral_value: {collateral_value if 'collateral_value' in locals() else 'not calculated'}")
                        print(f"    loan_value: {loan_value if 'loan_value' in locals() else 'not calculated'}")
                        liq_price_str = "N/A"
                        live_liq_dist_str = "N/A"
            except Exception as e:
                # If import or calculation fails, keep default "N/A"
                print(f"⚠️  [LIQUIDATION-BORROW] Import or setup failed for {leg_id}/{token}/{protocol}: {e}")
                import traceback
                traceback.print_exc()

        # ========================================
        # STEP 3: Build return dict with conditional column headers
        # ========================================
        if is_live_segment:
            # LIVE SEGMENT: Entry → Live (position deployment → current state)
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Borrow',
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Live Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Entry Price ($)': f"{segment_entry_price:.4f}" if safe_value(segment_entry_price) else "N/A",
                'Live Price ($)': f"{live_price:.4f}" if safe_value(live_price) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{token_amount:,.5f}" if safe_value(token_amount) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{borrow_fee * 100:.4f}" if safe_value(borrow_fee) else "N/A",
                'Entry Liquidation Distance': entry_liq_dist_str,
                'Live Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD"
            }
        else:
            # REBALANCE SEGMENT: Segment Entry → Exit (segment opening → segment closing)
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Borrow',
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Segment Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Exit Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Segment Entry Price ($)': f"{segment_entry_price:.4f}" if safe_value(segment_entry_price) else "N/A",
                'Exit Price ($)': f"{live_price:.4f}" if safe_value(live_price) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{token_amount:,.5f}" if safe_value(token_amount) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{borrow_fee * 100:.4f}" if safe_value(borrow_fee) else "N/A",
                'Segment Entry Liquidation Distance': entry_liq_dist_str,
                'Exit Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD"
            }


# ============================================================================
# FUTURE STRATEGY RENDERERS (Placeholders)
# ============================================================================

@register_strategy_renderer('fund_rate_arb')
class FundRateArbRenderer(StrategyRendererBase):
    """Renderer for funding rate arbitrage strategies (FUTURE)."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Funding Rate Arbitrage"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        """Show spot vs perpetual pair."""
        return f"{position.get('token1', 'Unknown')} (Spot ↔ Perp)"

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        # TODO: Define required fields when implementing
        return True

    @staticmethod
    def get_metrics_layout() -> List[str]:
        """Include funding rate specific metrics."""
        return ['total_pnl', 'total_earnings', 'funding_received',
                'hedging_costs', 'total_fees']

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None
    ) -> None:
        """Render 2-leg table: Spot position + Perp position."""

        st.info("🚧 Funding Rate Arbitrage renderer - Coming soon!")
        st.caption("This strategy type is not yet implemented.")

        # Show basic position info
        st.json({
            'position_id': position.get('position_id'),
            'strategy_type': position.get('strategy_type'),
            'token1': position.get('token1')
        })


# ============================================================================
# MAIN POSITION EXPANDER
# ============================================================================

def render_position_expander(
    position: pd.Series,
    stats: Optional[Dict],
    rebalances: Optional[List],
    rate_lookup: Dict,
    oracle_prices: Dict,
    service,
    timestamp_seconds: int,
    strategy_type: Optional[str] = None,
    context: str = 'standalone',
    portfolio_id: Optional[str] = None,
    expanded: bool = False
) -> None:
    """
    Render complete position expander (works for any strategy type).

    Args:
        position: Position record
        stats: Pre-calculated statistics
        rebalances: Rebalance history
        rate_lookup: Rate lookup dictionary
        oracle_prices: Oracle price lookup
        service: PositionService instance
        timestamp_seconds: Current viewing timestamp
        strategy_type: Strategy type identifier (if None, reads from position)
        context: 'standalone' or 'portfolio'
        portfolio_id: Portfolio ID (if context='portfolio')
        expanded: Whether to expand by default

    Raises:
        ValueError: If strategy_type not provided and not in position data
        ValueError: If strategy_type not registered
    """
    # Get strategy type - fail if not provided
    if strategy_type is None:
        strategy_type = position.get('strategy_type')

        if not strategy_type or pd.isna(strategy_type):
            raise ValueError(
                f"Position {position.get('position_id', 'unknown')} is missing "
                f"'strategy_type' field. All positions must have a strategy_type. "
                f"Please update the position record in the database."
            )

    # Get strategy-specific renderer (will raise ValueError if not found)
    try:
        renderer = get_strategy_renderer(strategy_type)
    except ValueError as e:
        # Re-raise with position context
        raise ValueError(
            f"Position {position.get('position_id', 'unknown')}: {str(e)}"
        ) from e

    # Validate position data
    if not renderer.validate_position_data(position):
        raise ValueError(
            f"Position {position.get('position_id', 'unknown')} has invalid data "
            f"for strategy type '{strategy_type}'. Check that all required fields "
            f"are present for this strategy type."
        )

    # Build title
    title = build_position_expander_title(
        position, stats, strategy_type, include_timestamp=True
    )

    # Create rate helpers
    get_rate, get_borrow_fee, get_price_with_fallback = create_rate_helpers(
        rate_lookup, oracle_prices
    )

    with st.expander(title, expanded=expanded):
        # Strategy name badge and position ID
        st.caption(f"📊 Strategy: {renderer.get_strategy_name()}")
        st.caption(f"🔑 Position ID: {position['position_id']}")

        # Strategy summary metrics (uses strategy-specific layout)
        st.markdown("#### Total Position Summary (All Segments)")
        render_strategy_summary_metrics(stats, position['deployment_usd'], strategy_type)

        st.markdown("---")

        # Convert rebalances to list if needed
        if isinstance(rebalances, pd.DataFrame):
            rebalances_list = rebalances.to_dict('records') if not rebalances.empty else []
        elif isinstance(rebalances, list):
            rebalances_list = rebalances
        else:
            rebalances_list = []

        # Fetch rebalances if empty
        if not rebalances_list or len(rebalances_list) == 0:
            try:
                position_id = position['position_id']
                rebalances_df = service.get_rebalance_history(position_id)
                if not rebalances_df.empty:
                    rebalances_list = rebalances_df.to_dict('records')
                    print(f"ℹ️  [REBALANCES] Fetched {len(rebalances_list)} rebalance(s) for position {position_id[:8]}...")
                else:
                    # No rebalances yet - this is normal for new positions
                    pass
            except Exception as e:
                print(f"⚠️  [REBALANCES] Failed to fetch rebalances for position {position.get('position_id', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()

        # === LIVE SEGMENT ===
        st.markdown("#### Live Segment (Current)")

        renderer.render_detail_table(
            position,
            get_rate,
            get_borrow_fee,
            get_price_with_fallback,
            rebalances_list
        )

        # === HISTORICAL SEGMENTS ===
        # Show all CLOSED segments (all rebalances EXCEPT the last one, which is the current/live segment)
        if rebalances_list and len(rebalances_list) > 0:
            st.markdown("---")
            st.markdown("#### Historical Segments")

            # Show in reverse order (most recent first) - all rebalances represent closed segments
            for idx in reversed(range(len(rebalances_list))):
                rebalance = rebalances_list[idx]
                sequence_num = rebalance.get('sequence_number', idx + 1)

                render_historical_segment(
                    position=position,
                    rebalance=rebalance,
                    sequence_number=sequence_num,
                    get_rate=get_rate,
                    get_borrow_fee=get_borrow_fee,
                    get_price_with_fallback=get_price_with_fallback,
                    strategy_type=strategy_type
                )

        st.markdown("---")

        # Action buttons (context-aware)
        if context == 'standalone':
            render_position_actions_standalone(position, timestamp_seconds, service)
        elif context == 'portfolio2':
            render_position_actions_portfolio(
                position, timestamp_seconds, service, portfolio_id)
