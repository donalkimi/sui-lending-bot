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
from dashboard.dashboard_utils import format_days_to_breakeven
from analysis.position_service import PositionService


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


def get_token_precision(price: float, target_usd: float = 10.0) -> int:
    """Calculate decimal places to show ~$10 worth of precision."""
    import math
    if price <= 0:
        return 5
    decimal_places = math.ceil(-math.log10(price / target_usd))
    return max(5, min(8, decimal_places))


def get_price_precision(token_amount: float, target_usd: float = 1.0) -> int:
    """
    Calculate decimal places for a price such that a 1-tick move changes
    position value by less than target_usd.

    Formula: n = ceil(log10(token_amount / target_usd))
    Examples (target_usd=1):
      0.1 BTC  → ceil(log10(0.1))   = 0  decimal places
      10 SUI   → ceil(log10(10))    = 1  decimal place
      340k WAL → ceil(log10(340000))= 6  decimal places
    """
    import math
    if token_amount <= 0:
        return 2
    decimal_places = math.ceil(math.log10(token_amount / target_usd))
    return max(0, min(8, decimal_places))


def _modal_sf(strategy: dict, key: str, default: float = 0.0) -> float:
    """Safe float from strategy dict — returns default when missing or NaN."""
    return _safe_float(strategy.get(key, default), default)


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

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """
        Render strategy-specific detail table in the strategy selection modal.

        Args:
            strategy: Strategy dict from analysis cache (all_results row)
            deployment_usd: Hypothetical deployment amount in USD
        """
        raise NotImplementedError(
            "render_strategy_modal_table not implemented for this renderer. "
            "Add a render_strategy_modal_table() method to the renderer class."
        )

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table in the strategy selection modal.

        Displayed above the position details table. Replaces the inline APR
        summary block in show_strategy_modal(). Strategy-specific so each
        strategy type can show relevant fee breakdown columns.

        Args:
            strategy: Strategy dict from analysis cache (all_results row)
            timestamp_seconds: Dashboard-selected timestamp (Unix seconds)
        """
        raise NotImplementedError(
            "render_apr_summary_table not implemented for this renderer. "
            "Add a render_apr_summary_table() method to the renderer class."
        )


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
        """2-tier fallback: protocol -> oracle -> None."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        price = rates.get('price')

        if price is not None and price > 0:
            return price

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

    # Load spot/perp basis data (for perp strategies)
    basis_lookup: Dict = {}
    try:
        basis_query = f"""
        SELECT spot_contract, basis_bid, basis_ask,
               perp_bid, perp_ask, spot_bid, spot_ask
        FROM spot_perp_basis
        WHERE timestamp = {ph}
        """
        basis_df = pd.read_sql_query(basis_query, engine, params=(timestamp_str,))
        basis_lookup = {
            row['spot_contract']: {
                'basis_bid': row['basis_bid'],
                'basis_ask': row['basis_ask'],
                'perp_bid':  row['perp_bid'],
                'perp_ask':  row['perp_ask'],
                'spot_bid':  row['spot_bid'],
                'spot_ask':  row['spot_ask'],
            }
            for _, row in basis_df.iterrows()
        }
    except Exception as _e:
        print(f"[BASIS] Warning: could not load spot_perp_basis: {_e}")

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
                expanded=False,
                basis_lookup=basis_lookup
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
        'opening_token1_amount': position.get('entry_token1_amount'),
        'opening_token2_amount': position.get('entry_token2_amount'),
        'opening_token3_amount': position.get('entry_token3_amount'),
        'opening_token4_amount': position.get('entry_token4_amount'),

        # Prices from position entry
        'opening_token1_price': position.get('entry_token1_price'),
        'opening_token2_price': position.get('entry_token2_price'),
        'opening_token3_price': position.get('entry_token3_price'),
        'opening_token4_price': position.get('entry_token4_price'),

        # Rates from position entry
        'opening_token1_rate': position.get('entry_token1_rate'),
        'opening_token2_rate': position.get('entry_token2_rate'),
        'opening_token3_rate': position.get('entry_token3_rate'),
        'opening_token4_rate': position.get('entry_token4_rate'),
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
    # A segment is still live if it has no closing_timestamp (initial deployment or open segment).
    ct = rebalance.get('closing_timestamp')
    _is_live = ct is None or (isinstance(ct, float) and ct != ct)  # None or NaN

    segment_data = {
        # REQUIRED: Explicit flag for segment type detection
        'is_live_segment': _is_live,

        # Token amounts from rebalance entry
        'opening_token1_amount': rebalance.get('entry_token1_amount'),
        'opening_token2_amount': rebalance.get('entry_token2_amount'),
        'opening_token3_amount': rebalance.get('entry_token3_amount'),
        'opening_token4_amount': rebalance.get('entry_token4_amount'),

        # Prices from rebalance opening
        'opening_token1_price': rebalance.get('opening_token1_price'),
        'opening_token2_price': rebalance.get('opening_token2_price'),
        'opening_token3_price': rebalance.get('opening_token3_price'),
        'opening_token4_price': rebalance.get('opening_token4_price'),

        # Prices from rebalance closing (for historical segments)
        'closing_token1_price': rebalance.get('closing_token1_price'),
        'closing_token2_price': rebalance.get('closing_token2_price'),
        'closing_token3_price': rebalance.get('closing_token3_price'),
        'closing_token4_price': rebalance.get('closing_token4_price'),

        # Rates from rebalance opening
        'opening_token1_rate': rebalance.get('opening_token1_rate'),
        'opening_token2_rate': rebalance.get('opening_token2_rate'),
        'opening_token3_rate': rebalance.get('opening_token3_rate'),
        'opening_token4_rate': rebalance.get('opening_token4_rate'),

        # Rates from rebalance closing (for historical segments)
        'closing_token1_rate': rebalance.get('closing_token1_rate'),
        'closing_token2_rate': rebalance.get('closing_token2_rate'),
        'closing_token3_rate': rebalance.get('closing_token3_rate'),
        'closing_token4_rate': rebalance.get('closing_token4_rate'),
    }

    return segment_data




# ============================================================================
# CORE RENDERING FUNCTIONS (Strategy-Agnostic)
# ============================================================================

def build_position_expander_title(
    position: pd.Series,
    stats: Optional[Dict],
    strategy_type: str,
    include_timestamp: bool = True,
    current_apr_incl_basis: Optional[float] = None,
    basis_pnl: Optional[float] = None
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

    _perp_strategies = ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')
    if strategy_type in _perp_strategies and current_apr_incl_basis is not None:
        current_apr_str = f"Current {current_apr:.2f}% | Basis-adj {current_apr_incl_basis * 100:.2f}%"
    else:
        current_apr_str = f"Current {current_apr:.2f}%"

    _perp_strategies = ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')
    title_parts.extend([
        token_flow,
        protocol_pair,
        f"Entry {entry_apr:.2f}%",
        current_apr_str,
        f"Net APR {realized_apr:.2f}%",
        f"Value \\${current_value:,.2f}",
        f"PnL \\${total_pnl:,.2f}",
        f"Earnings \\${total_earnings:,.2f}",
        f"Base \\${base_earnings:,.2f}",
        f"Rewards \\${reward_earnings:,.2f}",
    ])
    if strategy_type in _perp_strategies and basis_pnl is not None:
        title_parts.append(f"Basis PnL \\${basis_pnl:+,.2f}")
    title_parts.append(f"Fees \\${total_fees:,.2f}")

    return "▶ " + " | ".join(title_parts)


def render_strategy_summary_metrics(
    stats: Optional[Dict],
    deployment: float,
    strategy_type: str,
    basis_pnl: Optional[float] = None
) -> None:
    """
    Render strategy summary metrics (layout depends on strategy type).

    Args:
        stats: Pre-calculated statistics
        deployment: Deployment USD
        strategy_type: Strategy type identifier
        basis_pnl: Live basis PnL (perp strategies only)
    """
    if not stats:
        st.info("Statistics not available. Click 'Calculate Statistics' to generate.")
        return

    # Get strategy-specific metric layout
    renderer = get_strategy_renderer(strategy_type)
    metrics_layout = list(renderer.get_metrics_layout())

    # Inject basis_pnl between reward_earnings and total_fees for perp strategies
    _perp_strategies = ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')
    if strategy_type in _perp_strategies and basis_pnl is not None:
        if 'reward_earnings' in metrics_layout and 'total_fees' in metrics_layout:
            insert_at = metrics_layout.index('total_fees')
            metrics_layout.insert(insert_at, 'basis_pnl')

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
        with cols[idx]:
            if metric_key == 'basis_pnl':
                pct = (basis_pnl / deployment * 100) if deployment > 0 else 0  # type: ignore[operator]
                st.metric("Basis PnL", f"${basis_pnl:+,.2f}", f"{pct:+.2f}%")
                continue
            if metric_key not in metric_config:
                continue
            label, stats_key = metric_config[metric_key]
            value = stats.get(stats_key, 0.0)
            pct = (value / deployment * 100) if deployment > 0 else 0
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


def render_position_history_chart(
    position: pd.Series,
    timestamp_seconds: int,
    context: str = 'position'
) -> None:
    """
    Render APR history chart for a position.

    Matches All Strategies tab implementation - shows APR history only.

    Args:
        position: Position data series
        timestamp_seconds: Current timestamp
        context: Context string to make keys unique ('position' or 'portfolio')
    """
    st.markdown("### 📈 Historical Performance")

    col1, col2, col3 = st.columns([1, 2, 2])

    position_id = position['position_id']
    chart_key = f"chart_{context}_{position_id}"

    with col1:
        if st.button("📊 Show Chart", key=chart_key):
            st.session_state[f'show_{chart_key}'] = True
            st.rerun()

    with col2:
        time_range = st.selectbox(
            "Time Range",
            options=['7d', '30d', '90d', 'all'],
            index=3,  # Default to 'all' (All Time)
            format_func=lambda x: {
                '7d': 'Last 7 Days',
                '30d': 'Last 30 Days',
                '90d': 'Last 90 Days',
                'all': 'All Time'
            }[x],
            key=f"range_{chart_key}"
        )

    with col3:
        st.caption("View APR history for this strategy over time")

    # Generate and display chart if button clicked
    if st.session_state.get(f'show_{chart_key}', False):
        try:
            # Build strategy dict from position data
            strategy_dict = {
                'strategy_type': position['strategy_type'],
                'token1': position.get('token1'),
                'token2': position.get('token2'),
                'token3': position.get('token3'),
                'token1_contract': position['token1_contract'],
                'token2_contract': position.get('token2_contract'),
                'token3_contract': position.get('token3_contract'),
                'protocol_a': position['protocol_a'],
                'protocol_b': position.get('protocol_b'),
                'liquidation_distance': position.get('liquidation_distance', 0.20)
            }

            # Calculate time range
            from analysis.strategy_history.chart_utils import get_chart_time_range
            start_ts, end_ts = get_chart_time_range(time_range, timestamp_seconds)

            # Fetch history
            from analysis.strategy_history.strategy_history import get_strategy_history
            history_df = get_strategy_history(strategy_dict, start_ts, end_ts)

            if history_df.empty:
                st.warning("⚠️ No historical data available for this strategy.")
            else:
                # Generate chart
                from analysis.strategy_history.chart_utils import create_history_chart, format_history_table

                # Build chart title from position details
                token_flow = f"{position.get('token1')}/{position.get('token2')}"
                if position.get('token3'):
                    token_flow += f"/{position.get('token3')}"
                protocol_pair = f"{position['protocol_a']}/{position.get('protocol_b', '')}"
                chart_title = f"{token_flow} - {protocol_pair}"

                chart = create_history_chart(
                    history_df,
                    title=chart_title,
                    include_price=False,  # APR only, like All Strategies tab
                    height=400
                )

                st.plotly_chart(chart, width="stretch")

                # Summary statistics table
                with st.expander("📊 Summary Statistics", expanded=False):
                    stats_df = format_history_table(history_df)
                    st.dataframe(stats_df, hide_index=True, width="stretch")

        except Exception as e:
            st.error(f"❌ Failed to load chart: {e}")
            import logging
            logging.exception("Chart generation error")

    st.markdown("")  # Spacing


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
            'entry_token1_rate', 'entry_token2_rate',
            'entry_token3_rate', 'entry_token4_rate',
            'entry_token1_price', 'entry_token2_price',
            'entry_token3_price', 'entry_token4_price'
        ]

        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        """Standard 5-metric layout for recursive lending."""
        return ['total_pnl', 'total_earnings', 'base_earnings',
                'reward_earnings', 'total_fees']

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table for recursive_lending in the strategy selection modal.

        Columns: Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
                 Fees (%), Days to BE, Max Liquidity.
        No basis columns — non-perp strategies have no spot/perp spread.
        Note: token2_borrow_fee / token4_borrow_fee are not stored in the recursive_lending
        result dict, so Fees (%) shows 0.00% (same as the existing inline fallback).
        """
        apr_net  = _modal_sf(strategy, 'apr_net')
        apr5     = _modal_sf(strategy, 'apr5')
        apr30    = _modal_sf(strategy, 'apr30')
        liq_dist = strategy.get('liquidation_distance', 0.0)
        b_a      = _modal_sf(strategy, 'b_a')
        b_b      = _modal_sf(strategy, 'b_b')
        fees_pct = (b_a * _modal_sf(strategy, 'token2_borrow_fee')
                  + b_b * _modal_sf(strategy, 'token4_borrow_fee'))
        days_to_be = strategy.get('days_to_breakeven')
        max_size   = float(strategy.get('max_size', float('inf')))

        token_flow    = RecursiveLendingRenderer.build_token_flow_string(pd.Series(strategy))
        protocol_pair = f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}"

        liq_dist_str = (
            "N/A"
            if not isinstance(liq_dist, (int, float)) or liq_dist == float('inf')
            else f"{liq_dist * 100:.2f}%"
        )
        max_liq_str = "N/A" if max_size == float('inf') else f"${max_size:,.2f}"

        summary_data = [{
            'Token Flow':    token_flow,
            'Protocols':     protocol_pair,
            'Net APR':       f"{apr_net * 100:.2f}%",
            'APR 5d':        f"{apr5 * 100:.2f}%",
            'APR 30d':       f"{apr30 * 100:.2f}%",
            'Liq Dist':      liq_dist_str,
            'Fees (%)':      f"{fees_pct * 100:.3f}%",
            'Days to BE':    format_days_to_breakeven(days_to_be),
            'Max Liquidity': max_liq_str,
        }]
        summary_df = pd.DataFrame(summary_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.replace('%', ''))
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        styled = summary_df.style.map(_color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
        st.dataframe(styled, width='stretch', hide_index=True)

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
            token2_price_live = float(segment_data.get('closing_token2_price')) if segment_data.get('closing_token2_price') is not None else None
            token1_price_live = float(segment_data.get('closing_token1_price')) if segment_data.get('closing_token1_price') is not None else None
        else:
            token2_price_live = get_price_with_fallback(position['token2'], position['protocol_a'])
            token1_price_live = get_price_with_fallback(position['token1'], position['protocol_a'])

        # ========== LEG 1: Protocol A - Lend token1 ==========
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token1',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_token1_rate'],
            entry_price=position['entry_token1_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token2'],  # Leg 2A borrows token2
            borrow_price_live=token2_price_live,
            borrow_price_entry=position['entry_token2_price'],
            borrow_weight_value=position['b_a'],
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
        ))

        # ========== LEG 2: Protocol A - Borrow token2 ==========
        detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
            position=position,
            leg_id='token2',
            token=position['token2'],
            protocol=position['protocol_a'],
            weight=position['b_a'],
            entry_rate=position['entry_token2_rate'],
            entry_price=position['entry_token2_price'],
            collateral_ratio=position.get('entry_token1_collateral_ratio', 0.0),
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            get_rate=get_rate,
            get_borrow_fee=get_borrow_fee,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            collateral_token=position['token1'],
            collateral_price_live=token1_price_live,
            collateral_price_entry=position['entry_token1_price'],
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
        ))

        # ========== LEG 3: Protocol B - Lend token2 ==========
        # Check if there's a 4th leg (borrow token4 = closing stablecoin) to calculate liquidation
        token4 = position.get('token4')
        b_b = position.get('b_b')
        has_leg4 = token4 is not None and pd.notna(token4) and str(token4).strip() != '' and b_b is not None and pd.notna(b_b) and float(b_b) > 0

        # For historical segments, use closing prices from segment_data
        # For live segments, use current market prices
        if segment_type == 'historical' and segment_data:
            token4_price_live = float(segment_data.get('closing_token4_price')) if (has_leg4 and segment_data.get('closing_token4_price') is not None) else None
            token2_price_live_protocolb = float(segment_data.get('closing_token3_price')) if segment_data.get('closing_token3_price') is not None else None
        else:
            token4_price_live = get_price_with_fallback(position['token4'], position['protocol_b']) if has_leg4 else None
            token2_price_live_protocolb = get_price_with_fallback(position['token2'], position['protocol_b'])

        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token3',
            token=position['token2'],
            protocol=position['protocol_b'],
            weight=position['l_b'],
            entry_rate=position['entry_token3_rate'],
            entry_price=position['entry_token3_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token4'] if has_leg4 else None,  # Leg 3B borrows token4 (B_B = closing stablecoin)
            borrow_price_live=token4_price_live,
            borrow_price_entry=position['entry_token4_price'] if has_leg4 else None,
            borrow_weight_value=position['b_b'] if has_leg4 else None,
            liquidation_threshold=position.get('entry_token3_liquidation_threshold', 0.0) if has_leg4 else None,
            borrow_weight=position.get('entry_token4_borrow_weight', 1.0) if has_leg4 else 1.0
        ))

        # ========== LEG 4: Protocol B - Borrow token4 (B_B = closing stablecoin, if levered) ==========
        # Use has_leg4 check from Leg 3
        if has_leg4:
            detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
                position=position,
                leg_id='token4',
                token=position['token4'],
                protocol=position['protocol_b'],
                weight=position['b_b'],
                entry_rate=position['entry_token4_rate'],
                entry_price=position['entry_token4_price'],
                collateral_ratio=position.get('entry_token3_collateral_ratio', 0.0),
                liquidation_threshold=position.get('entry_token3_liquidation_threshold', 0.0),
                get_rate=get_rate,
                get_borrow_fee=get_borrow_fee,
                get_price_with_fallback=get_price_with_fallback,
                deployment=deployment,
                segment_data=segment_data,
                segment_type=segment_type,
                collateral_token=position['token2'],
                collateral_price_live=token2_price_live_protocolb,
                collateral_price_entry=position['entry_token3_price'],
                borrow_weight=position.get('entry_token4_borrow_weight', 1.0)
            ))

        # Display table
        detail_df = pd.DataFrame(detail_data)
        st.dataframe(detail_df, width="stretch")

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """Render 4-row detail table for recursive lending (modal view)."""
        from analysis.position_calculator import PositionCalculator

        l_a = _modal_sf(strategy, 'l_a')
        b_a = _modal_sf(strategy, 'b_a')
        l_b = _modal_sf(strategy, 'l_b')
        b_b = _modal_sf(strategy, 'b_b')
        P1_A = _modal_sf(strategy, 'token1_price', 1.0)
        P2_A = _modal_sf(strategy, 'token2_price', 1.0)
        P2_B = _modal_sf(strategy, 'token3_price', 1.0)
        P3_B = _modal_sf(strategy, 'token4_price', 1.0)
        token2_borrow_fee = _modal_sf(strategy, 'token2_borrow_fee')
        token4_borrow_fee = _modal_sf(strategy, 'token4_borrow_fee')
        token2_borrow_weight = _modal_sf(strategy, 'token2_borrow_weight', 1.0)
        token4_borrow_weight = _modal_sf(strategy, 'token4_borrow_weight', 1.0)
        lltv_1A = _modal_sf(strategy, 'token1_liquidation_threshold')
        lltv_2B = _modal_sf(strategy, 'token3_liquidation_threshold')
        token1_collateral_ratio = _modal_sf(strategy, 'token1_collateral_ratio')
        token3_collateral_ratio = _modal_sf(strategy, 'token3_collateral_ratio')
        token2_available_borrow = _modal_sf(strategy, 'token2_available_borrow')
        available_borrow_3b = _modal_sf(strategy, 'available_borrow_3b')

        T1_A = _modal_sf(strategy, 'token1_units')
        T2_A = _modal_sf(strategy, 'token2_units')
        T2_B = _modal_sf(strategy, 'token3_units')
        T3_B = _modal_sf(strategy, 'token4_units')
        entry_token_amount_1A = T1_A * deployment_usd
        entry_token_amount_2 = T2_A * deployment_usd
        entry_token_amount_2B = T2_B * deployment_usd
        entry_token_amount_3B = T3_B * deployment_usd
        position_size_1A = l_a * deployment_usd
        position_size_2A = b_a * deployment_usd
        position_size_2B = l_b * deployment_usd
        position_size_3B = b_b * deployment_usd
        fee_usd_2A = b_a * token2_borrow_fee * deployment_usd
        fee_usd_3B = b_b * token4_borrow_fee * deployment_usd
        precision_1A = get_token_precision(P1_A)
        precision_2A = get_token_precision(P2_A)
        precision_2B = get_token_precision(P2_B)
        precision_3B = get_token_precision(P3_B)
        pp_1A = get_price_precision(entry_token_amount_1A) if entry_token_amount_1A > 0 else 4
        pp_2A = get_price_precision(entry_token_amount_2) if entry_token_amount_2 > 0 else 4
        pp_2B = get_price_precision(entry_token_amount_2B) if entry_token_amount_2B > 0 else 4
        pp_3B = get_price_precision(entry_token_amount_3B) if entry_token_amount_3B > 0 else 4
        effective_ltv_1A = (b_a / l_a) * token2_borrow_weight if l_a > 0 else 0.0
        effective_ltv_2B = (b_b / l_b) * token4_borrow_weight if l_b > 0 else 0.0

        calc = PositionCalculator()
        liq1 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'lending', token2_borrow_weight)
        liq2 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'borrowing', token2_borrow_weight)
        liq3 = calc.calculate_liquidation_price(position_size_2B, position_size_3B, P2_B, P3_B, lltv_2B, 'lending', token4_borrow_weight)
        liq4 = calc.calculate_liquidation_price(position_size_2B, position_size_3B, P2_B, P3_B, lltv_2B, 'borrowing', token4_borrow_weight)

        def _lp(r, pp):
            p = r['liq_price']
            return f"${p:.{pp}f}" if p != float('inf') and p > 0 else "N/A"

        def _ld(r):
            p = r['liq_price']
            return f"{r['pct_distance'] * 100:.2f}%" if p != float('inf') and p > 0 else "N/A"

        detail_data = [
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token1', ''), 'Action': 'Lend',
                'maxCF': f"{token1_collateral_ratio:.2%}", 'LLTV': f"{lltv_1A:.2%}" if lltv_1A > 0 else "",
                'Effective LTV': f"{effective_ltv_1A:.2%}", 'Borrow Weight': "-", 'Weight': f"{l_a:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token1_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}", 'Size ($$$)': f"${position_size_1A:,.2f}",
                'Price': f"${P1_A:.{pp_1A}f}", 'Fees (%)': "", 'Fees ($$$)': "",
                'Liquidation Price': _lp(liq1, pp_1A), 'Liq Distance': _ld(liq1), 'Max Borrow': "",
            },
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token2', ''), 'Action': 'Borrow',
                'maxCF': "-", 'LLTV': "-", 'Effective LTV': "-",
                'Borrow Weight': f"{token2_borrow_weight:.2f}x", 'Weight': f"{b_a:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token2_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_2:,.{precision_2A}f}", 'Size ($$$)': f"${position_size_2A:,.2f}",
                'Price': f"${P2_A:.{pp_2A}f}",
                'Fees (%)': f"{token2_borrow_fee * 100:.2f}%" if token2_borrow_fee > 0 else "",
                'Fees ($$$)': f"${fee_usd_2A:.2f}" if fee_usd_2A > 0 else "",
                'Liquidation Price': _lp(liq2, pp_2A), 'Liq Distance': _ld(liq2),
                'Max Borrow': f"${token2_available_borrow:,.2f}" if token2_available_borrow > 0 else "",
            },
            {
                'Protocol': strategy.get('protocol_b', ''), 'Token': strategy.get('token2', ''), 'Action': 'Lend',
                'maxCF': f"{token3_collateral_ratio:.2%}", 'LLTV': f"{lltv_2B:.2%}" if lltv_2B > 0 else "",
                'Effective LTV': f"{effective_ltv_2B:.2%}", 'Borrow Weight': "-", 'Weight': f"{l_b:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token3_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_2B:,.{precision_2B}f}", 'Size ($$$)': f"${position_size_2B:,.2f}",
                'Price': f"${P2_B:.{pp_2B}f}", 'Fees (%)': "", 'Fees ($$$)': "",
                'Liquidation Price': _lp(liq3, pp_2B), 'Liq Distance': _ld(liq3), 'Max Borrow': "",
            },
            {
                'Protocol': strategy.get('protocol_b', ''), 'Token': strategy.get('token3', ''), 'Action': 'Borrow',
                'maxCF': "-", 'LLTV': "-", 'Effective LTV': "-",
                'Borrow Weight': f"{token4_borrow_weight:.2f}x", 'Weight': f"{b_b:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token4_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_3B:,.{precision_3B}f}", 'Size ($$$)': f"${position_size_3B:,.2f}",
                'Price': f"${P3_B:.{pp_3B}f}",
                'Fees (%)': f"{token4_borrow_fee * 100:.2f}%" if token4_borrow_fee > 0 else "",
                'Fees ($$$)': f"${fee_usd_3B:.2f}" if fee_usd_3B > 0 else "",
                'Liquidation Price': _lp(liq4, pp_3B), 'Liq Distance': _ld(liq4),
                'Max Borrow': f"${available_borrow_3b:,.2f}" if available_borrow_3b > 0 else "",
            },
        ]

        detail_df = pd.DataFrame(detail_data)

        def _color_rate(val):
            if isinstance(val, str) and '%' in val and val != "":
                try:
                    if float(val.replace('%', '')) > 0:
                        return 'color: green'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_liq(val):
            if isinstance(val, str):
                if val == "N/A":
                    return 'color: gray; font-style: italic'
                elif '%' in val:
                    try:
                        n = abs(float(val.replace('%', '')))
                        if n < 10:
                            return 'color: red'
                        elif n < 30:
                            return 'color: orange'
                        else:
                            return 'color: green'
                    except (ValueError, TypeError):
                        pass
            return ''

        styled_df = detail_df.style.map(_color_rate, subset=['Rate']).map(_color_liq, subset=['Liq Distance'])
        st.dataframe(styled_df, width='stretch', hide_index=True)

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
        borrow_weight: float = 1.0,
        live_price_override: float = None
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
            if leg_id == 'token1':
                segment_entry_rate = segment_data.get('opening_token1_rate')
                segment_entry_price = segment_data.get('opening_token1_price')
                token_amount = segment_data.get('opening_token1_amount')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_token1_rate')) if segment_data.get('closing_token1_rate') is not None else None
                live_price = float(segment_data.get('closing_token1_price')) if segment_data.get('closing_token1_price') is not None else None
            elif leg_id == 'token3':
                segment_entry_rate = segment_data.get('opening_token3_rate')
                segment_entry_price = segment_data.get('opening_token3_price')
                token_amount = segment_data.get('opening_token3_amount')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_token3_rate')) if segment_data.get('closing_token3_rate') is not None else None
                live_price = float(segment_data.get('closing_token3_price')) if segment_data.get('closing_token3_price') is not None else None
        else:
            # LIVE SEGMENT PATH: Use positions table + current rates
            # segment_data already contains position entry values (from build_live_segment_data)
            live_rate = get_rate(token, protocol, 'lend_apr')
            live_price = live_price_override if live_price_override is not None else get_price_with_fallback(token, protocol)

            # Map leg_id to field names
            if leg_id == 'token1':
                segment_entry_rate = segment_data.get('opening_token1_rate')
                segment_entry_price = segment_data.get('opening_token1_price')
                token_amount = segment_data.get('opening_token1_amount')
            elif leg_id == 'token3':
                segment_entry_rate = segment_data.get('opening_token3_rate')
                segment_entry_price = segment_data.get('opening_token3_price')
                token_amount = segment_data.get('opening_token3_amount')

        # Pandas-safe checks (avoid truth value ambiguity)
        def safe_value(val):
            """Check if value is valid (not None, not NaN). Allows zero values."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                float(val)  # Check if convertible to float
                return True  # Valid value (including zero)
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
                    if leg_id == 'token1':
                        # token1 lends, token2 borrows
                        loan_token_amount = segment_data.get('opening_token2_amount')
                    elif leg_id == 'token3':
                        # token3 lends, token4 borrows
                        loan_token_amount = segment_data.get('opening_token4_amount')

                # Collateral is this lend leg's tokens at live price
                collateral_value = float(token_amount) * float(live_price) if token_amount else 0.0
                # Loan is the borrow leg's tokens at live price
                loan_value = float(loan_token_amount) * float(borrow_price_live) if loan_token_amount and borrow_price_live else 0.0

                # Calculate entry liquidation distance using ENTRY prices
                if safe_value(segment_entry_price) and safe_value(borrow_price_entry) and token_amount and loan_token_amount:
                    entry_collateral_value = float(token_amount) * float(segment_entry_price)
                    entry_loan_value = float(loan_token_amount) * float(borrow_price_entry)
                    if entry_loan_value > 0:
                        try:
                            entry_liq_result = calc.calculate_liquidation_price(
                                collateral_value=entry_collateral_value,
                                loan_value=entry_loan_value,
                                lending_token_price=float(segment_entry_price),
                                borrowing_token_price=float(borrow_price_entry),
                                lltv=liquidation_threshold,
                                side='lending',
                                borrow_weight=borrow_weight
                            )
                            entry_liq_dist_str = f"{entry_liq_result['pct_distance'] * 100:+.1f}%"
                        except Exception as e:
                            print(f"⚠️  [LIQUIDATION-LEND-ENTRY] Failed for {leg_id}/{token}/{protocol}: {e}")

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

                        # Format liquidation price (live)
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
        pp = get_price_precision(float(token_amount)) if safe_value(token_amount) else 4

        if is_live_segment:
            # LIVE SEGMENT: Entry → Live
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Lend',
                'Weight': f"{weight:.2f}",
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Live Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Entry Price ($)': f"{segment_entry_price:.{pp}f}" if safe_value(segment_entry_price) else "N/A",
                'Live Price ($)': f"{live_price:.{pp}f}" if safe_value(live_price) else "N/A",
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
                'Weight': f"{weight:.2f}",
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Segment Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Exit Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Segment Entry Price ($)': f"{segment_entry_price:.{pp}f}" if safe_value(segment_entry_price) else "N/A",
                'Exit Price ($)': f"{live_price:.{pp}f}" if safe_value(live_price) else "N/A",
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
        borrow_weight: float = 1.0,
        live_price_override: float = None
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
            if leg_id == 'token2':
                segment_entry_rate = segment_data.get('opening_token2_rate')
                segment_entry_price = segment_data.get('opening_token2_price')
                token_amount = segment_data.get('opening_token2_amount')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_token2_rate')) if segment_data.get('closing_token2_rate') is not None else None
                live_price = float(segment_data.get('closing_token2_price')) if segment_data.get('closing_token2_price') is not None else None
            elif leg_id == 'token4':
                segment_entry_rate = segment_data.get('opening_token4_rate')
                segment_entry_price = segment_data.get('opening_token4_price')
                token_amount = segment_data.get('opening_token4_amount')
                # Use closing values for "exit" price/rate
                live_rate = float(segment_data.get('closing_token4_rate')) if segment_data.get('closing_token4_rate') is not None else None
                live_price = float(segment_data.get('closing_token4_price')) if segment_data.get('closing_token4_price') is not None else None
            # Get borrow fee (always from current market - not stored in rebalance history)
            borrow_fee = get_borrow_fee(token, protocol)
        else:
            # LIVE SEGMENT PATH: Use positions table + current rates
            # segment_data already contains position entry values (from build_live_segment_data)
            live_rate = get_rate(token, protocol, 'borrow_apr')
            live_price = live_price_override if live_price_override is not None else get_price_with_fallback(token, protocol)
            borrow_fee = get_borrow_fee(token, protocol)

            # Map leg_id to field names
            if leg_id == 'token2':
                segment_entry_rate = segment_data.get('opening_token2_rate')
                segment_entry_price = segment_data.get('opening_token2_price')
                token_amount = segment_data.get('opening_token2_amount')
            elif leg_id == 'token4':
                segment_entry_rate = segment_data.get('opening_token4_rate')
                segment_entry_price = segment_data.get('opening_token4_price')
                token_amount = segment_data.get('opening_token4_amount')

        # Pandas-safe checks (avoid truth value ambiguity)
        def safe_value(val):
            """Check if value is valid (not None, not NaN). Allows zero values."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                float(val)  # Check if convertible to float
                return True  # Valid value (including zero)
            except (TypeError, ValueError):
                return False

        # Calculate liquidation price and distance
        # Get collateral leg token amount based on which borrow leg this is
        collateral_token_amount = None
        collateral_leg_weight = 0.0

        if segment_data:
            if leg_id == 'token2':
                # token2 borrows, token1 is collateral
                collateral_token_amount = segment_data.get('opening_token1_amount')
                collateral_leg_weight = position.get('l_a', 0.0)
            elif leg_id == 'token4':
                # token4 borrows, token3 is collateral
                collateral_token_amount = segment_data.get('opening_token3_amount')
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
        pp = get_price_precision(float(token_amount)) if safe_value(token_amount) else 4

        if is_live_segment:
            # LIVE SEGMENT: Entry → Live (position deployment → current state)
            return {
                'Protocol': protocol,
                'Token': token,
                'Action': 'Borrow',
                'Weight': f"{weight:.2f}",
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Live Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Entry Price ($)': f"{segment_entry_price:.{pp}f}" if safe_value(segment_entry_price) else "N/A",
                'Live Price ($)': f"{live_price:.{pp}f}" if safe_value(live_price) else "N/A",
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
                'Weight': f"{weight:.2f}",
                'Position Entry Rate (%)': f"{entry_rate * 100:.2f}" if safe_value(entry_rate) else "N/A",
                'Segment Entry Rate (%)': f"{segment_entry_rate * 100:.2f}" if safe_value(segment_entry_rate) else "N/A",
                'Exit Rate (%)': f"{live_rate * 100:.2f}" if safe_value(live_rate) else "N/A",
                'Segment Entry Price ($)': f"{segment_entry_price:.{pp}f}" if safe_value(segment_entry_price) else "N/A",
                'Exit Price ($)': f"{live_price:.{pp}f}" if safe_value(live_price) else "N/A",
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

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        st.info("🚧 Funding Rate Arbitrage detail table — coming soon!")


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
    expanded: bool = False,
    basis_lookup: Optional[Dict] = None
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

    # Create rate helpers (needed for basis-adjusted APR)
    get_rate, get_borrow_fee, get_price_with_fallback = create_rate_helpers(
        rate_lookup, oracle_prices
    )

    _perp_strategies = ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')

    def get_basis(perp_proxy):
        if basis_lookup is None:
            return None
        return basis_lookup.get(perp_proxy)

    # Compute basis-adjusted current APR and basis PnL (perp strategies only)
    current_apr_incl_basis = PositionService.compute_basis_adjusted_current_apr(
        position, stats, get_basis
    )
    basis_pnl = stats.get('basis_pnl') if stats else None
    if basis_pnl is None and strategy_type in _perp_strategies:
        basis_pnl = PositionService.calculate_basis_pnl(position, get_basis)

    # Build title
    title = build_position_expander_title(
        position, stats, strategy_type, include_timestamp=True,
        current_apr_incl_basis=current_apr_incl_basis,
        basis_pnl=basis_pnl
    )

    with st.expander(title, expanded=expanded):
        # Strategy name badge and position ID
        st.caption(f"📊 Strategy: {renderer.get_strategy_name()}")
        st.caption(f"🔑 Position ID: {position['position_id']}")

        # Strategy summary metrics (uses strategy-specific layout)
        st.markdown("#### Total Position Summary (All Segments)")
        render_strategy_summary_metrics(stats, position['deployment_usd'], strategy_type, basis_pnl=basis_pnl)

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

        _kwargs = {'get_basis': get_basis} if strategy_type in _perp_strategies else {}
        renderer.render_detail_table(
            position,
            get_rate,
            get_borrow_fee,
            get_price_with_fallback,
            rebalances_list,
            **_kwargs
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

        # Historical performance chart
        render_position_history_chart(position, timestamp_seconds, context=context)

        st.markdown("---")

        # Action buttons (context-aware)
        if context == 'standalone':
            render_position_actions_standalone(position, timestamp_seconds, service)
        elif context == 'portfolio2':
            render_position_actions_portfolio(
                position, timestamp_seconds, service, portfolio_id)
# Append these renderer classes to the end of dashboard/position_renderers.py

# ============================================================================
# STABLECOIN LENDING RENDERER (1-LEG)
# ============================================================================

@register_strategy_renderer('stablecoin_lending')
class StablecoinLendingRenderer(StrategyRendererBase):
    """Renderer for 1-leg stablecoin lending strategies."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Stablecoin Lending"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        """Build token flow: just token1 (single token)"""
        return position['token1']

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        """Validate stablecoin lending position has required fields."""
        required_fields = [
            'token1', 'protocol_a',
            'l_a',
            'entry_token1_rate',
            'entry_token1_price'
        ]
        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        """Standard 5-metric layout for visual consistency across all strategies."""
        return ['total_pnl', 'total_earnings', 'base_earnings',
                'reward_earnings', 'total_fees']

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table for stablecoin_lending in the strategy selection modal.

        Columns: Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
                 Fees (%), Days to BE, Max Liquidity.
        Liq Dist shows "N/A" (stablecoin lending has no liquidation risk).
        Fees (%) is always 0.00% (no borrowing, no upfront costs).
        """
        apr_net  = _modal_sf(strategy, 'apr_net')
        apr5     = _modal_sf(strategy, 'apr5')
        apr30    = _modal_sf(strategy, 'apr30')
        liq_dist = strategy.get('liquidation_distance', float('inf'))
        b_a      = _modal_sf(strategy, 'b_a')
        b_b      = _modal_sf(strategy, 'b_b')
        fees_pct = (b_a * _modal_sf(strategy, 'token2_borrow_fee')
                  + b_b * _modal_sf(strategy, 'token4_borrow_fee'))
        days_to_be = strategy.get('days_to_breakeven')
        max_size   = float(strategy.get('max_size', float('inf')))

        token_flow    = StablecoinLendingRenderer.build_token_flow_string(pd.Series(strategy))
        protocol_pair = f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}"

        liq_dist_str = (
            "N/A"
            if not isinstance(liq_dist, (int, float)) or liq_dist == float('inf')
            else f"{liq_dist * 100:.2f}%"
        )
        max_liq_str = "N/A" if max_size == float('inf') else f"${max_size:,.2f}"

        summary_data = [{
            'Token Flow':    token_flow,
            'Protocols':     protocol_pair,
            'Net APR':       f"{apr_net * 100:.2f}%",
            'APR 5d':        f"{apr5 * 100:.2f}%",
            'APR 30d':       f"{apr30 * 100:.2f}%",
            'Liq Dist':      liq_dist_str,
            'Fees (%)':      f"{fees_pct * 100:.3f}%",
            'Days to BE':    format_days_to_breakeven(days_to_be),
            'Max Liquidity': max_liq_str,
        }]
        summary_df = pd.DataFrame(summary_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.replace('%', ''))
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        styled = summary_df.style.map(_color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
        st.dataframe(styled, width='stretch', hide_index=True)

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None,
        segment_type: str = 'live'
    ) -> None:
        """Render 1-leg detail table for stablecoin lending."""

        deployment = position['deployment_usd']

        # Build segment_data from last rebalance (if any)
        if not rebalances or len(rebalances) == 0:
            segment_data = build_segment_data_from_position(position)
        else:
            segment_data = build_segment_data_from_rebalance(rebalances[-1])

        detail_data = []

        # Single leg: Lend token1 in Protocol A
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token1',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_token1_rate'],
            entry_price=position['entry_token1_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=None,  # No borrowing
            borrow_price_live=None,
            borrow_price_entry=None,
            borrow_weight_value=0,
            liquidation_threshold=0.0,  # No liquidation risk
            borrow_weight=1.0
        ))

        # Render table
        df = pd.DataFrame(detail_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """Render 1-row detail table for stablecoin lending (modal view)."""
        l_a = _modal_sf(strategy, 'l_a')
        P1_A = _modal_sf(strategy, 'token1_price', 1.0)
        precision_1A = get_token_precision(P1_A)
        T1_A = _modal_sf(strategy, 'token1_units')
        token_amount = T1_A * deployment_usd
        pp_1A = get_price_precision(token_amount) if token_amount > 0 else 4
        detail_data = [{
            'Protocol': strategy.get('protocol_a', ''),
            'Token': strategy.get('token1', ''),
            'Action': 'Lend',
            'Weight': f"{l_a:.4f}",
            'Rate': f"{_modal_sf(strategy, 'token1_rate') * 100:.2f}%",
            'Token Amount': f"{token_amount:,.{precision_1A}f}",
            'Size ($$$)': f"${l_a * deployment_usd:,.2f}",
            'Price': f"${P1_A:.{pp_1A}f}",
            'Fees (%)': "", 'Fees ($$$)': "",
            'Liquidation Price': "N/A", 'Liq Distance': "N/A",
        }]
        st.dataframe(pd.DataFrame(detail_data), width='stretch', hide_index=True)


# ============================================================================
# NO-LOOP CROSS-PROTOCOL RENDERER (3-LEG)
# ============================================================================

@register_strategy_renderer('noloop_cross_protocol_lending')
class NoLoopCrossProtocolRenderer(StrategyRendererBase):
    """Renderer for 3-leg cross-protocol lending strategies (no loop back)."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Cross-Protocol Lending (No Loop)"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        """Build token flow: token1 → token2 (no loop back)"""
        token_flow = position['token1']

        token2 = position.get('token2')
        has_token2 = token2 is not None and pd.notna(token2) and str(token2).strip() != ''

        if has_token2:
            token_flow += f" → {position['token2']}"

        return token_flow

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        """Validate no-loop cross-protocol position has required fields."""
        required_fields = [
            'token1', 'token2', 'protocol_a', 'protocol_b',
            'l_a', 'b_a', 'l_b',
            'entry_token1_rate', 'entry_token2_rate', 'entry_token3_rate',
            'entry_token1_price', 'entry_token2_price', 'entry_token3_price'
        ]
        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        """Standard 5-metric layout for visual consistency across all strategies."""
        return ['total_pnl', 'total_earnings', 'base_earnings',
                'reward_earnings', 'total_fees']

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table for noloop_cross_protocol_lending in the strategy modal.

        Columns: Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
                 Fees (%), Days to BE, Max Liquidity.
        Fees (%) = B_A × token2_borrow_fee (only Protocol A borrow leg; token4_borrow_fee = 0).
        """
        apr_net  = _modal_sf(strategy, 'apr_net')
        apr5     = _modal_sf(strategy, 'apr5')
        apr30    = _modal_sf(strategy, 'apr30')
        liq_dist = strategy.get('liquidation_distance', 0.0)
        b_a      = _modal_sf(strategy, 'b_a')
        b_b      = _modal_sf(strategy, 'b_b')
        fees_pct = (b_a * _modal_sf(strategy, 'token2_borrow_fee')
                  + b_b * _modal_sf(strategy, 'token4_borrow_fee'))
        days_to_be = strategy.get('days_to_breakeven')
        max_size   = float(strategy.get('max_size', float('inf')))

        token_flow    = NoLoopCrossProtocolRenderer.build_token_flow_string(pd.Series(strategy))
        protocol_pair = f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}"

        liq_dist_str = (
            "N/A"
            if not isinstance(liq_dist, (int, float)) or liq_dist == float('inf')
            else f"{liq_dist * 100:.2f}%"
        )
        max_liq_str = "N/A" if max_size == float('inf') else f"${max_size:,.2f}"

        summary_data = [{
            'Token Flow':    token_flow,
            'Protocols':     protocol_pair,
            'Net APR':       f"{apr_net * 100:.2f}%",
            'APR 5d':        f"{apr5 * 100:.2f}%",
            'APR 30d':       f"{apr30 * 100:.2f}%",
            'Liq Dist':      liq_dist_str,
            'Fees (%)':      f"{fees_pct * 100:.3f}%",
            'Days to BE':    format_days_to_breakeven(days_to_be),
            'Max Liquidity': max_liq_str,
        }]
        summary_df = pd.DataFrame(summary_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.replace('%', ''))
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        styled = summary_df.style.map(_color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
        st.dataframe(styled, width='stretch', hide_index=True)

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None,
        segment_type: str = 'live'
    ) -> None:
        """Render 3-leg detail table for no-loop cross-protocol lending."""

        deployment = position['deployment_usd']

        # Build segment_data from last rebalance
        if not rebalances or len(rebalances) == 0:
            segment_data = build_segment_data_from_position(position)
        else:
            segment_data = build_segment_data_from_rebalance(rebalances[-1])

        detail_data = []

        # Get token2 live price
        if segment_type == 'historical' and segment_data:
            token2_price_live = float(segment_data.get('closing_token2_price')) if segment_data.get('closing_token2_price') is not None else None
        else:
            token2_price_live = get_price_with_fallback(position['token2'], position['protocol_a'])

        # ========== LEG 1: Protocol A - Lend token1 ==========
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token1',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_token1_rate'],
            entry_price=position['entry_token1_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token2'],  # Leg 2A borrows token2
            borrow_price_live=token2_price_live,
            borrow_price_entry=position['entry_token2_price'],
            borrow_weight_value=position['b_a'],
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
        ))

        # ========== LEG 2: Protocol A - Borrow token2 ==========
        detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
            position=position,
            leg_id='token2',
            token=position['token2'],
            protocol=position['protocol_a'],
            weight=position['b_a'],
            entry_rate=position['entry_token2_rate'],
            entry_price=position['entry_token2_price'],
            collateral_ratio=position.get('entry_token1_collateral_ratio', 0.0),
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            get_rate=get_rate,
            get_borrow_fee=get_borrow_fee,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
        ))

        # ========== LEG 3: Protocol B - Lend token2 ==========
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token3',
            token=position['token2'],
            protocol=position['protocol_b'],
            weight=position['l_b'],
            entry_rate=position['entry_token3_rate'],
            entry_price=position['entry_token3_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=None,  # No 4th leg (no loop back)
            borrow_price_live=None,
            borrow_price_entry=None,
            borrow_weight_value=0,
            liquidation_threshold=0.0,
            borrow_weight=1.0
        ))

        # Render table
        df = pd.DataFrame(detail_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """Render 3-row detail table for no-loop cross-protocol lending (modal view)."""
        from analysis.position_calculator import PositionCalculator

        l_a = _modal_sf(strategy, 'l_a')
        b_a = _modal_sf(strategy, 'b_a')
        l_b = _modal_sf(strategy, 'l_b')
        P1_A = _modal_sf(strategy, 'token1_price', 1.0)
        P2_A = _modal_sf(strategy, 'token2_price', 1.0)
        P2_B = _modal_sf(strategy, 'token3_price', 1.0)
        token2_borrow_fee = _modal_sf(strategy, 'token2_borrow_fee')
        token2_borrow_weight = _modal_sf(strategy, 'token2_borrow_weight', 1.0)
        lltv_1A = _modal_sf(strategy, 'token1_liquidation_threshold')
        token1_collateral_ratio = _modal_sf(strategy, 'token1_collateral_ratio')
        token3_collateral_ratio = _modal_sf(strategy, 'token3_collateral_ratio')
        token2_available_borrow = _modal_sf(strategy, 'token2_available_borrow')

        precision_1A = get_token_precision(P1_A)
        precision_2A = get_token_precision(P2_A)
        precision_2B = get_token_precision(P2_B)
        position_size_1A = l_a * deployment_usd
        position_size_2A = b_a * deployment_usd
        position_size_2B = l_b * deployment_usd
        T1_A = _modal_sf(strategy, 'token1_units')
        T2_A = _modal_sf(strategy, 'token2_units')
        entry_token_amount_1A = T1_A * deployment_usd
        entry_token_amount_2 = T2_A * deployment_usd
        fee_usd_2A = b_a * token2_borrow_fee * deployment_usd
        pp_1A = get_price_precision(entry_token_amount_1A) if entry_token_amount_1A > 0 else 4
        pp_2A = get_price_precision(entry_token_amount_2) if entry_token_amount_2 > 0 else 4
        effective_ltv_1A = (b_a / l_a) * token2_borrow_weight if l_a > 0 else 0.0

        calc = PositionCalculator()
        liq1 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'lending', token2_borrow_weight)
        liq2 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'borrowing', token2_borrow_weight)

        def _lp(r, pp):
            p = r['liq_price']
            return f"${p:.{pp}f}" if p != float('inf') and p > 0 else "N/A"

        def _ld(r):
            p = r['liq_price']
            return f"{r['pct_distance'] * 100:.2f}%" if p != float('inf') and p > 0 else "N/A"

        detail_data = [
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token1', ''), 'Action': 'Lend',
                'maxCF': f"{token1_collateral_ratio:.2%}", 'LLTV': f"{lltv_1A:.2%}" if lltv_1A > 0 else "",
                'Effective LTV': f"{effective_ltv_1A:.2%}", 'Borrow Weight': "-", 'Weight': f"{l_a:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token1_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_1A:,.{precision_1A}f}", 'Size ($$$)': f"${position_size_1A:,.2f}",
                'Price': f"${P1_A:.{pp_1A}f}", 'Fees (%)': "", 'Fees ($$$)': "",
                'Liquidation Price': _lp(liq1, pp_1A), 'Liq Distance': _ld(liq1), 'Max Borrow': "",
            },
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token2', ''), 'Action': 'Borrow',
                'maxCF': "-", 'LLTV': "-", 'Effective LTV': "-",
                'Borrow Weight': f"{token2_borrow_weight:.2f}x", 'Weight': f"{b_a:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token2_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_2:,.{precision_2A}f}", 'Size ($$$)': f"${position_size_2A:,.2f}",
                'Price': f"${P2_A:.{pp_2A}f}",
                'Fees (%)': f"{token2_borrow_fee * 100:.2f}%" if token2_borrow_fee > 0 else "",
                'Fees ($$$)': f"${fee_usd_2A:.2f}" if fee_usd_2A > 0 else "",
                'Liquidation Price': _lp(liq2, pp_2A), 'Liq Distance': _ld(liq2),
                'Max Borrow': f"${token2_available_borrow:,.2f}" if token2_available_borrow > 0 else "",
            },
            {
                'Protocol': strategy.get('protocol_b', ''), 'Token': strategy.get('token2', ''), 'Action': 'Lend',
                'maxCF': f"{token3_collateral_ratio:.2%}", 'LLTV': "", 'Effective LTV': "",
                'Borrow Weight': "-", 'Weight': f"{l_b:.4f}",
                'Rate': f"{_modal_sf(strategy, 'token3_rate') * 100:.2f}%",
                'Token Amount': f"{entry_token_amount_2:,.{precision_2B}f}", 'Size ($$$)': f"${position_size_2B:,.2f}",
                'Price': f"${P2_B:.{pp_2A}f}", 'Fees (%)': "", 'Fees ($$$)': "",
                'Liquidation Price': "N/A", 'Liq Distance': "N/A", 'Max Borrow': "",
            },
        ]

        detail_df = pd.DataFrame(detail_data)

        def _color_rate(val):
            if isinstance(val, str) and '%' in val and val != "":
                try:
                    if float(val.replace('%', '')) > 0:
                        return 'color: green'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_liq(val):
            if isinstance(val, str):
                if val == "N/A":
                    return 'color: gray; font-style: italic'
                elif '%' in val:
                    try:
                        n = abs(float(val.replace('%', '')))
                        if n < 10:
                            return 'color: red'
                        elif n < 30:
                            return 'color: orange'
                        else:
                            return 'color: green'
                    except (ValueError, TypeError):
                        pass
            return ''

        styled_df = detail_df.style.map(_color_rate, subset=['Rate']).map(_color_liq, subset=['Liq Distance'])
        st.dataframe(styled_df, width='stretch', hide_index=True)


# ============================================================================
# PERP LENDING RENDERER (2-LEG: SPOT LEND + SHORT PERP)
# ============================================================================

@register_strategy_renderer('perp_lending')
class PerpLendingRenderer(StrategyRendererBase):
    """Renderer for 2-leg perp lending strategies (spot lend + short perp)."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Perp Lending"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        token1 = position.get('token1', '')
        token4 = position.get('token4', '')  # B_B = short perp
        return f"{token1} (Spot) ↔ {token4} (Short Perp)"

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        required_fields = ['token1', 'token4', 'protocol_a', 'protocol_b', 'l_a', 'b_b']
        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        return ['total_pnl', 'total_earnings', 'base_earnings', 'reward_earnings', 'total_fees']

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table for perp_lending in the strategy selection modal.

        Columns: Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
                 Basis Cost (%), Fees (%), Total Fees (%), Days to BE, Max Liquidity
        """
        apr_net  = _modal_sf(strategy, 'apr_net')
        apr5     = _modal_sf(strategy, 'apr5')
        apr30    = _modal_sf(strategy, 'apr30')
        liq_dist = _modal_sf(strategy, 'liquidation_distance')
        perp_fees_apr      = _modal_sf(strategy, 'perp_fees_apr')
        basis_cost         = _modal_sf(strategy, 'basis_cost')
        basis_cost_included = strategy.get('basis_cost_included', False)
        total_upfront_fee  = _modal_sf(strategy, 'total_upfront_fee')
        days_to_be  = strategy.get('days_to_breakeven')
        max_size    = float(strategy.get('max_size', float('inf')))

        token_flow   = PerpLendingRenderer.build_token_flow_string(pd.Series(strategy))
        protocol_pair = f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}"

        basis_cost_str = (
            f"{basis_cost * 100:.3f}%"
            if basis_cost_included
            else "N/A"
        )
        max_liq_str = (
            "N/A"
            if max_size == float('inf')
            else f"${max_size:,.2f}"
        )

        summary_data = [{
            'Token Flow':      token_flow,
            'Protocols':       protocol_pair,
            'Net APR':         f"{apr_net * 100:.2f}%",
            'APR 5d':          f"{apr5 * 100:.2f}%",
            'APR 30d':         f"{apr30 * 100:.2f}%",
            'Liq Dist':        f"{liq_dist * 100:.2f}%",
            'Basis Cost (%)':  basis_cost_str,
            'Fees (%)':        f"{perp_fees_apr * 100:.3f}%",
            'Total Fees (%)':  f"{total_upfront_fee * 100:.3f}%",
            'Days to BE':      format_days_to_breakeven(days_to_be),
            'Max Liquidity':   max_liq_str,
        }]
        summary_df = pd.DataFrame(summary_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.replace('%', ''))
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_basis(val):
            if val == "N/A":
                return 'color: gray; font-style: italic'
            return ''

        styled = (
            summary_df.style
            .map(_color_apr,   subset=['Net APR', 'APR 5d', 'APR 30d'])
            .map(_color_basis, subset=['Basis Cost (%)'])
        )
        st.dataframe(styled, width='stretch', hide_index=True)

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None,
        segment_type: str = 'live',
        get_basis: Optional[Callable] = None
    ) -> None:
        """Render 2-leg detail table: Spot Lend (token1) + Short Perp (token4)."""
        deployment = position['deployment_usd']

        # Build segment_data (same pattern as RecursiveLendingRenderer)
        if not rebalances or len(rebalances) == 0:
            segment_data = build_segment_data_from_position(position)
        else:
            segment_data = build_segment_data_from_rebalance(rebalances[-1])

        is_live_segment = segment_data['is_live_segment']

        detail_data = []

        # Get basis data early — needed for live prices on both legs
        basis_data = None
        if get_basis is not None and is_live_segment:
            basis_data = get_basis(position['token1_contract'])

        # ========== LEG 1: Protocol A - Spot Lend token1 ==========
        # No borrow on this lend leg for perp lending → no liquidation distance
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token1',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_token1_rate'],
            entry_price=position['entry_token1_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=None,
            borrow_price_live=None,
            borrow_price_entry=None,
            borrow_weight_value=None,
            liquidation_threshold=None,
            borrow_weight=1.0,
            live_price_override=basis_data.get('spot_bid') if basis_data else None
        ))

        # ========== LEG 2: Protocol B - Short Perp token4 (B_B) ==========
        entry_rate_token4 = position['entry_token4_rate']
        entry_token4_price = position['entry_token4_price']

        def safe_value(val):
            """Check if value is valid (not None, not NaN). Allows zero values."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                float(val)
                return True
            except (TypeError, ValueError):
                return False

        if is_live_segment:
            live_rate_token4 = get_rate(position['token4'], position['protocol_b'], 'borrow_apr')
            live_price_token4 = basis_data.get('perp_ask') if basis_data else get_price_with_fallback(position['token4'], position['protocol_b'])
            segment_entry_rate_token4 = segment_data.get('opening_token4_rate')
            segment_entry_token4_price = segment_data.get('opening_token4_price')
        else:
            segment_entry_rate_token4 = segment_data.get('opening_token4_rate')
            segment_entry_token4_price = segment_data.get('opening_token4_price')
            live_rate_token4 = float(segment_data.get('closing_token4_rate')) if segment_data.get('closing_token4_rate') is not None else None
            live_price_token4 = float(segment_data.get('closing_token4_price')) if segment_data.get('closing_token4_price') is not None else None

        token_amount_token4 = segment_data.get('opening_token4_amount')  # B_B slot = short perp amount
        perp_fee = get_borrow_fee(position['token4'], position['protocol_b'])

        # Short perp liq: price must RISE by liq_dist to liquidate.
        # Liq price is fixed at entry: entry_price * (1 + liq_dist).
        # Entry liq dist: always = +liq_dist (by definition).
        # Live liq dist: (fixed_liq_price - live_price) / live_price.
        liq_dist = position.get('entry_liquidation_distance', 0.20)
        entry_liq_dist_str = "N/A"
        live_liq_dist_str = "N/A"
        liq_price_str = "N/A"

        pp4 = get_price_precision(float(token_amount_token4)) if safe_value(token_amount_token4) else 4

        if safe_value(segment_entry_token4_price) and float(segment_entry_token4_price) > 0:
            perp_liq_price = float(segment_entry_token4_price) * (1.0 + liq_dist)
            liq_price_str = f"${perp_liq_price:,.{pp4}f}"
            entry_liq_dist_str = f"{liq_dist * 100:+.1f}%"
            if safe_value(live_price_token4) and float(live_price_token4) > 0:
                live_liq_dist_pct = (perp_liq_price - float(live_price_token4)) / float(live_price_token4)
                live_liq_dist_str = f"{live_liq_dist_pct * 100:+.1f}%"

        entry_basis = position.get('entry_basis')
        entry_basis_str = f"{entry_basis * 100:.3f}%" if safe_value(entry_basis) else "N/A"

        live_basis_str = "N/A"
        if basis_data is not None:
            lb = basis_data.get('basis_ask')
            live_basis_str = f"{lb * 100:.3f}%" if lb is not None else "N/A"

        if is_live_segment:
            perp_row = {
                'Protocol': position['protocol_b'],
                'Token': position['token4'],  # B_B = short perp
                'Action': 'Short Perp',
                'Weight': f"{float(position['b_b']):.2f}",
                'Position Entry Rate (%)': f"{entry_rate_token4 * 100:.2f}" if safe_value(entry_rate_token4) else "N/A",
                'Entry Rate (%)': f"{float(segment_entry_rate_token4) * 100:.2f}" if safe_value(segment_entry_rate_token4) else "N/A",
                'Live Rate (%)': f"{float(live_rate_token4) * 100:.2f}" if safe_value(live_rate_token4) else "N/A",
                'Entry Basis': entry_basis_str,
                'Live Basis': live_basis_str,
                'Entry Price ($)': f"{float(segment_entry_token4_price):.{pp4}f}" if safe_value(segment_entry_token4_price) else "N/A",
                'Live Price ($)': f"{float(live_price_token4):.{pp4}f}" if safe_value(live_price_token4) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{float(token_amount_token4):,.5f}" if safe_value(token_amount_token4) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{perp_fee * 100:.4f}" if safe_value(perp_fee) else "N/A",
                'Entry Liquidation Distance': entry_liq_dist_str,
                'Live Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD",
            }
        else:
            # Exit basis (short perp): closing prices are execution prices (perp ask, spot bid).
            # basis = (perp - spot) / perp — directional, equivalent to basis_ask at exit.
            _c1 = segment_data.get('closing_token1_price')
            _c4 = live_price_token4
            exit_spot_price = float(_c1) if _c1 is not None else None
            exit_perp_price = float(_c4) if _c4 is not None else None
            if exit_spot_price is not None and exit_perp_price is not None and exit_perp_price > 0:
                exit_basis = (exit_perp_price - exit_spot_price) / exit_perp_price
                exit_basis_str = f"{exit_basis * 100:.3f}%"
            else:
                exit_basis_str = "N/A"

            perp_row = {
                'Protocol': position['protocol_b'],
                'Token': position['token4'],  # B_B = short perp
                'Action': 'Short Perp',
                'Weight': f"{float(position['b_b']):.2f}",
                'Position Entry Rate (%)': f"{entry_rate_token4 * 100:.2f}" if safe_value(entry_rate_token4) else "N/A",
                'Segment Entry Rate (%)': f"{float(segment_entry_rate_token4) * 100:.2f}" if safe_value(segment_entry_rate_token4) else "N/A",
                'Exit Rate (%)': f"{float(live_rate_token4) * 100:.2f}" if safe_value(live_rate_token4) else "N/A",
                'Entry Basis': entry_basis_str,
                'Exit Basis': exit_basis_str,
                'Segment Entry Price ($)': f"{float(segment_entry_token4_price):.{pp4}f}" if safe_value(segment_entry_token4_price) else "N/A",
                'Exit Price ($)': f"{float(live_price_token4):.{pp4}f}" if safe_value(live_price_token4) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{float(token_amount_token4):,.5f}" if safe_value(token_amount_token4) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{perp_fee * 100:.4f}" if safe_value(perp_fee) else "N/A",
                'Segment Entry Liquidation Distance': entry_liq_dist_str,
                'Exit Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD",
            }

        detail_data.append(perp_row)

        detail_df = pd.DataFrame(detail_data)
        st.dataframe(detail_df, width="stretch")

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """Render 2-row detail table: Spot Lend + Short Perp."""
        l_a = _modal_sf(strategy, 'l_a')
        b_b = _modal_sf(strategy, 'b_b')
        P1_A = _modal_sf(strategy, 'token1_price', 1.0)
        P3_B = _modal_sf(strategy, 'token4_price', 1.0)
        token1_rate = _modal_sf(strategy, 'token1_rate')
        token4_rate = _modal_sf(strategy, 'token4_rate')
        spot_lending_apr = _modal_sf(strategy, 'spot_lending_apr')
        funding_rate_apr = _modal_sf(strategy, 'funding_rate_apr')
        perp_fees_apr = _modal_sf(strategy, 'perp_fees_apr')
        if 'liq_price_multiplier' not in strategy:
            raise KeyError("perp_lending strategy missing required field 'liq_price_multiplier'")
        liq_price_multiplier = _modal_sf(strategy, 'liq_price_multiplier')

        precision_1A = get_token_precision(P1_A)
        precision_3B = get_token_precision(P3_B)
        T1_A = _modal_sf(strategy, 'token1_units')
        T3_B = _modal_sf(strategy, 'token4_units')
        token_amount_1A = T1_A * deployment_usd
        token_amount_3B = T3_B * deployment_usd
        size_1A = l_a * deployment_usd
        size_3B = token_amount_3B * P3_B  # actual USD exposure of perp

        pp_1A = get_price_precision(token_amount_1A) if token_amount_1A > 0 else 4
        pp_3B = get_price_precision(token_amount_3B) if token_amount_3B > 0 else 4

        perp_liq_price = P3_B * liq_price_multiplier
        perp_liq_dist_pct = (perp_liq_price - P3_B) / P3_B * 100 if P3_B > 0 else 0
        perp_fee_usd = perp_fees_apr * deployment_usd

        basis_bid = _modal_sf(strategy, 'basis_bid')
        basis_bid_str = f"{basis_bid * 100:.3f}%" if basis_bid is not None else "N/A"

        detail_data = [
            {
                'Protocol': strategy.get('protocol_a', ''),
                'Token': strategy.get('token1', ''),
                'Action': 'Spot Lend',
                'Weight': f"{l_a:.4f}",
                'Rate': f"{token1_rate * 100:.2f}%",
                'APR Contrib': f"{spot_lending_apr * 100:.2f}%",
                'Entry Basis': "—",
                'Token Amount': f"{token_amount_1A:,.{precision_1A}f}",
                'Size ($)': f"${size_1A:,.2f}",
                'Price': f"${P1_A:.{pp_1A}f}",
                'Fees (%)': "", 'Fees ($)': "",
                'Liq Risk': "None", 'Liq Price': "N/A", 'Liq Distance': "N/A",
            },
            {
                'Protocol': strategy.get('protocol_b', ''),
                'Token': strategy.get('token4', ''),  # B_B = short perp
                'Action': 'Short Perp',
                'Weight': f"{b_b:.4f}",
                'Rate': f"{token4_rate * 100:.2f}% (funding)",
                'APR Contrib': f"{-funding_rate_apr * 100:.2f}%",  # Negate: shorts earn when rate is negative
                'Entry Basis': basis_bid_str,
                'Token Amount': f"{token_amount_3B:,.{precision_3B}f}",
                'Size ($)': f"${size_3B:,.2f}",
                'Price': f"${P3_B:.{pp_3B}f}",
                'Fees (%)': f"{perp_fees_apr * 100:.2f}%",
                'Fees ($)': f"${perp_fee_usd:,.2f}",
                'Liq Risk': "Price UP",
                'Liq Price': f"${perp_liq_price:,.{pp_3B}f}",
                'Liq Distance': f"+{perp_liq_dist_pct:.2f}%",
            },
        ]

        detail_df = pd.DataFrame(detail_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.split('%')[0])
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_liq(val):
            if isinstance(val, str):
                if val == "N/A":
                    return 'color: gray; font-style: italic'
                elif '%' in val:
                    try:
                        n = abs(float(val.replace('+', '').replace('%', '')))
                        if n < 10:
                            return 'color: red'
                        elif n < 30:
                            return 'color: orange'
                        else:
                            return 'color: green'
                    except (ValueError, TypeError):
                        pass
            return ''

        styled_df = detail_df.style.map(_color_apr, subset=['APR Contrib']).map(_color_liq, subset=['Liq Distance'])
        st.dataframe(styled_df, width='stretch', hide_index=True)


# ============================================================================
# PERP BORROWING RENDERER (3-LEG: STABLECOIN LEND + SPOT BORROW + LONG PERP)
# ============================================================================

@register_strategy_renderer('perp_borrowing')
@register_strategy_renderer('perp_borrowing_recursive')
class PerpBorrowingRenderer(StrategyRendererBase):
    """Renderer for 3-leg perp borrowing strategies (stablecoin lend + spot borrow + long perp)."""

    @staticmethod
    def get_strategy_name() -> str:
        return "Perp Borrowing"

    @staticmethod
    def build_token_flow_string(position: pd.Series) -> str:
        token1 = position.get('token1', '')
        token2 = position.get('token2', '')
        token3 = position.get('token3', '')
        return f"{token1} (Lend) → Borrow {token2} → {token3} (Long Perp)"

    @staticmethod
    def validate_position_data(position: pd.Series) -> bool:
        required_fields = ['token1', 'token2', 'token3', 'protocol_a', 'protocol_b', 'l_a', 'b_a', 'l_b']
        return all(field in position.index for field in required_fields)

    @staticmethod
    def get_metrics_layout() -> List[str]:
        return ['total_pnl', 'total_earnings', 'base_earnings', 'reward_earnings', 'total_fees']

    @staticmethod
    def render_apr_summary_table(strategy: dict, timestamp_seconds: int) -> None:
        """
        Render APR overview table for perp_borrowing (and recursive variant) in the strategy selection modal.

        Columns: Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
                 Basis Cost (%), Fees (%), Total Fees (%), Days to BE, Max Liquidity

        Fees (%) = perp_fees (L_B × 2 × taker_fee) + borrow_fee (B_A × token2_borrow_fee)
        Total Fees (%) = Fees + Basis Cost  (stored as total_upfront_fee)
        """
        apr_net  = _modal_sf(strategy, 'apr_net')
        apr5     = _modal_sf(strategy, 'apr5')
        apr30    = _modal_sf(strategy, 'apr30')
        liq_dist = _modal_sf(strategy, 'liquidation_distance')
        perp_fees_apr       = _modal_sf(strategy, 'perp_fees_apr')
        b_a                 = _modal_sf(strategy, 'b_a')
        token2_borrow_fee       = _modal_sf(strategy, 'token2_borrow_fee')
        basis_cost          = _modal_sf(strategy, 'basis_cost')
        basis_cost_included = strategy.get('basis_cost_included', False)
        total_upfront_fee   = _modal_sf(strategy, 'total_upfront_fee')
        days_to_be  = strategy.get('days_to_breakeven')
        max_size    = float(strategy.get('max_size', float('inf')))

        token_flow    = PerpBorrowingRenderer.build_token_flow_string(pd.Series(strategy))
        protocol_pair = f"{strategy.get('protocol_a', '')} ↔ {strategy.get('protocol_b', '')}"

        # Fees = perp trading fees (entry + exit) + Protocol A upfront borrow fee
        trading_fees_pct = perp_fees_apr + b_a * token2_borrow_fee

        basis_cost_str = (
            f"{basis_cost * 100:.3f}%"
            if basis_cost_included
            else "N/A"
        )
        max_liq_str = (
            "N/A"
            if max_size == float('inf')
            else f"${max_size:,.2f}"
        )

        summary_data = [{
            'Token Flow':      token_flow,
            'Protocols':       protocol_pair,
            'Net APR':         f"{apr_net * 100:.2f}%",
            'APR 5d':          f"{apr5 * 100:.2f}%",
            'APR 30d':         f"{apr30 * 100:.2f}%",
            'Liq Dist':        f"{liq_dist * 100:.2f}%",
            'Basis Cost (%)':  basis_cost_str,
            'Fees (%)':        f"{trading_fees_pct * 100:.3f}%",
            'Total Fees (%)':  f"{total_upfront_fee * 100:.3f}%",
            'Days to BE':      format_days_to_breakeven(days_to_be),
            'Max Liquidity':   max_liq_str,
        }]
        summary_df = pd.DataFrame(summary_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.replace('%', ''))
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_basis(val):
            if val == "N/A":
                return 'color: gray; font-style: italic'
            return ''

        styled = (
            summary_df.style
            .map(_color_apr,   subset=['Net APR', 'APR 5d', 'APR 30d'])
            .map(_color_basis, subset=['Basis Cost (%)'])
        )
        st.dataframe(styled, width='stretch', hide_index=True)

    @staticmethod
    def render_detail_table(
        position: pd.Series,
        get_rate: Callable,
        get_borrow_fee: Callable,
        get_price_with_fallback: Callable,
        rebalances: Optional[List] = None,
        segment_type: str = 'live',
        get_basis: Optional[Callable] = None
    ) -> None:
        """Render 3-leg detail table: Stablecoin Lend (token1) + Spot Borrow (token2) + Long Perp (token3)."""
        deployment = position['deployment_usd']

        # Build segment_data (same pattern as RecursiveLendingRenderer)
        if not rebalances or len(rebalances) == 0:
            segment_data = build_segment_data_from_position(position)
        else:
            segment_data = build_segment_data_from_rebalance(rebalances[-1])

        is_live_segment = segment_data['is_live_segment']

        # Get basis data early — needed for live prices on spot and perp legs
        basis_data = None
        if get_basis is not None and is_live_segment:
            basis_data = get_basis(position['token2_contract'])

        # Get live prices for leg 1A/2A (needed for borrow leg liq calculation)
        if segment_type == 'historical' and segment_data:
            token2_price_live = float(segment_data.get('closing_token2_price')) if segment_data.get('closing_token2_price') is not None else None
            token1_price_live = float(segment_data.get('closing_token1_price')) if segment_data.get('closing_token1_price') is not None else None
        else:
            token2_price_live = basis_data.get('spot_ask') if basis_data else get_price_with_fallback(position['token2'], position['protocol_a'])
            token1_price_live = get_price_with_fallback(position['token1'], position['protocol_a'])

        detail_data = []

        # ========== LEG 1: Protocol A - Lend Stablecoin (token1) ==========
        detail_data.append(RecursiveLendingRenderer._build_lend_leg_row(
            position=position,
            leg_id='token1',
            token=position['token1'],
            protocol=position['protocol_a'],
            weight=position['l_a'],
            entry_rate=position['entry_token1_rate'],
            entry_price=position['entry_token1_price'],
            get_rate=get_rate,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            borrow_token=position['token2'],
            borrow_price_live=token2_price_live,
            borrow_price_entry=position['entry_token2_price'],
            borrow_weight_value=position['b_a'],
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0)
        ))

        # ========== LEG 2: Protocol A - Borrow Spot (token2) ==========
        detail_data.append(RecursiveLendingRenderer._build_borrow_leg_row(
            position=position,
            leg_id='token2',
            token=position['token2'],
            protocol=position['protocol_a'],
            weight=position['b_a'],
            entry_rate=position['entry_token2_rate'],
            entry_price=position['entry_token2_price'],
            collateral_ratio=position.get('entry_token1_collateral_ratio', 0.0),
            liquidation_threshold=position.get('entry_token1_liquidation_threshold', 0.0),
            get_rate=get_rate,
            get_borrow_fee=get_borrow_fee,
            get_price_with_fallback=get_price_with_fallback,
            deployment=deployment,
            segment_data=segment_data,
            segment_type=segment_type,
            collateral_token=position['token1'],
            collateral_price_live=token1_price_live,
            collateral_price_entry=position['entry_token1_price'],
            borrow_weight=position.get('entry_token2_borrow_weight', 1.0),
            live_price_override=basis_data.get('spot_ask') if basis_data else None
        ))

        # ========== LEG 3: Protocol B - Long Perp (token3) ==========
        def safe_value(val):
            """Check if value is valid (not None, not NaN). Allows zero values."""
            if val is None:
                return False
            if isinstance(val, (pd.Series, pd.DataFrame)):
                if len(val) == 0:
                    return False
                val = val.iloc[0] if isinstance(val, pd.Series) else val.iloc[0, 0]
            if not pd.notna(val):
                return False
            try:
                float(val)
                return True
            except (TypeError, ValueError):
                return False

        # perp_borrowing: perp is L_B = token3 slot (entry_token3_rate, entry_token3_price)
        entry_rate_token3 = position['entry_token3_rate']  # Funding rate (positive = longs pay shorts)
        entry_token3_price = position['entry_token3_price']

        if is_live_segment:
            live_rate_token3 = get_rate(position['token3'], position['protocol_b'], 'lend_apr')
            live_price_token3 = basis_data.get('perp_bid') if basis_data else get_price_with_fallback(position['token3'], position['protocol_b'])
            segment_entry_rate_token3 = segment_data.get('opening_token3_rate')
            segment_entry_token3_price = segment_data.get('opening_token3_price')
        else:
            segment_entry_rate_token3 = segment_data.get('opening_token3_rate')
            segment_entry_token3_price = segment_data.get('opening_token3_price')
            live_rate_token3 = float(segment_data.get('closing_token3_rate')) if segment_data.get('closing_token3_rate') is not None else None
            live_price_token3 = float(segment_data.get('closing_token3_price')) if segment_data.get('closing_token3_price') is not None else None

        token_amount_token3 = segment_data.get('opening_token3_amount')  # L_B slot = perp long amount
        perp_fee = get_borrow_fee(position['token3'], position['protocol_b'])

        # Long perp liq: price must DROP by liq_dist to liquidate.
        # Liq price is fixed at entry: entry_price * (1 - liq_dist).
        # Entry liq dist: always = -liq_dist (by definition).
        # Live liq dist: (fixed_liq_price - live_price) / live_price.
        liq_dist = position.get('entry_liquidation_distance', 0.20)
        entry_liq_dist_str = "N/A"
        live_liq_dist_str = "N/A"
        liq_price_str = "N/A"

        pp3 = get_price_precision(float(token_amount_token3)) if safe_value(token_amount_token3) else 4

        if safe_value(segment_entry_token3_price) and float(segment_entry_token3_price) > 0:
            perp_liq_price = float(segment_entry_token3_price) * (1.0 - liq_dist)
            liq_price_str = f"${perp_liq_price:,.{pp3}f}"
            entry_liq_dist_str = f"{-liq_dist * 100:+.1f}%"
            if safe_value(live_price_token3) and float(live_price_token3) > 0:
                live_liq_dist_pct = (perp_liq_price - float(live_price_token3)) / float(live_price_token3)
                live_liq_dist_str = f"{live_liq_dist_pct * 100:+.1f}%"

        entry_basis = position.get('entry_basis')
        entry_basis_str = f"{entry_basis * 100:.3f}%" if safe_value(entry_basis) else "N/A"

        live_basis_str = "N/A"
        if basis_data is not None:
            lb = basis_data.get('basis_bid')
            live_basis_str = f"{lb * 100:.3f}%" if lb is not None else "N/A"

        if is_live_segment:
            perp_row = {
                'Protocol': position['protocol_b'],
                'Token': position['token3'],
                'Action': 'Long Perp',
                'Weight': f"{float(position['b_a']):.2f}",
                'Position Entry Rate (%)': f"{entry_rate_token3 * 100:.2f}" if safe_value(entry_rate_token3) else "N/A",
                'Entry Rate (%)': f"{float(segment_entry_rate_token3) * 100:.2f}" if safe_value(segment_entry_rate_token3) else "N/A",
                'Live Rate (%)': f"{float(live_rate_token3) * 100:.2f}" if safe_value(live_rate_token3) else "N/A",
                'Entry Basis': entry_basis_str,
                'Live Basis': live_basis_str,
                'Entry Price ($)': f"{float(segment_entry_token3_price):.{pp3}f}" if safe_value(segment_entry_token3_price) else "N/A",
                'Live Price ($)': f"{float(live_price_token3):.{pp3}f}" if safe_value(live_price_token3) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{float(token_amount_token3):,.5f}" if safe_value(token_amount_token3) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{perp_fee * 100:.4f}" if safe_value(perp_fee) else "N/A",
                'Entry Liquidation Distance': entry_liq_dist_str,
                'Live Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD",
            }
        else:
            # Exit basis (long perp): closing prices are execution prices (perp bid, spot ask).
            # basis = (perp - spot) / perp — directional, equivalent to basis_bid at exit.
            _c2 = segment_data.get('closing_token2_price')
            _c3 = live_price_token3
            exit_spot_price = float(_c2) if _c2 is not None else None
            exit_perp_price = float(_c3) if _c3 is not None else None
            if exit_spot_price is not None and exit_perp_price is not None and exit_perp_price > 0:
                exit_basis = (exit_perp_price - exit_spot_price) / exit_perp_price
                exit_basis_str = f"{exit_basis * 100:.3f}%"
            else:
                exit_basis_str = "N/A"

            perp_row = {
                'Protocol': position['protocol_b'],
                'Token': position['token3'],
                'Action': 'Long Perp',
                'Weight': f"{float(position['b_a']):.2f}",
                'Position Entry Rate (%)': f"{entry_rate_token3 * 100:.2f}" if safe_value(entry_rate_token3) else "N/A",
                'Segment Entry Rate (%)': f"{float(segment_entry_rate_token3) * 100:.2f}" if safe_value(segment_entry_rate_token3) else "N/A",
                'Exit Rate (%)': f"{float(live_rate_token3) * 100:.2f}" if safe_value(live_rate_token3) else "N/A",
                'Entry Basis': entry_basis_str,
                'Exit Basis': exit_basis_str,
                'Segment Entry Price ($)': f"{float(segment_entry_token3_price):.{pp3}f}" if safe_value(segment_entry_token3_price) else "N/A",
                'Exit Price ($)': f"{float(live_price_token3):.{pp3}f}" if safe_value(live_price_token3) else "N/A",
                'Liquidation Price ($)': liq_price_str,
                'Token Amount': f"{float(token_amount_token3):,.5f}" if safe_value(token_amount_token3) else "N/A",
                'Token Rebalance Required': "TBD",
                'Fee Rate (%)': f"{perp_fee * 100:.4f}" if safe_value(perp_fee) else "N/A",
                'Segment Entry Liquidation Distance': entry_liq_dist_str,
                'Exit Liquidation Distance': live_liq_dist_str,
                'Segment Earnings': "TBD",
                'Segment Fees': "TBD",
            }

        detail_data.append(perp_row)

        detail_df = pd.DataFrame(detail_data)
        st.dataframe(detail_df, width="stretch")

    @staticmethod
    def render_strategy_modal_table(strategy: dict, deployment_usd: float) -> None:
        """Render 3-row detail table: Stablecoin Lend + Spot Borrow + Long Perp."""
        from analysis.position_calculator import PositionCalculator

        # Required fields — direct access per design note #16 (fail loudly if missing)
        l_a   = float(strategy['l_a'])
        b_a   = float(strategy['b_a'])
        l_b   = float(strategy['l_b'])
        P1_A  = float(strategy['token1_price'])
        P2_A  = float(strategy['token2_price'])
        P3_B  = float(strategy['token3_price'])   # L_B = long perp
        token1_rate         = float(strategy['token1_rate'])
        token2_rate       = float(strategy['token2_rate'])
        token3_rate       = float(strategy['token3_rate'])  # L_B = perp funding rate
        stablecoin_lending_apr = float(strategy['stablecoin_lending_apr'])
        token2_borrow_apr    = float(strategy['token2_borrow_apr'])
        funding_rate_apr     = float(strategy['funding_rate_apr'])
        perp_fees_apr        = float(strategy['perp_fees_apr'])
        token2_borrow_fee        = float(strategy['token2_borrow_fee'])
        token2_borrow_weight     = float(strategy['token2_borrow_weight'])
        lltv_1A              = float(strategy['token1_liquidation_threshold'])
        token1_collateral_ratio  = float(strategy['token1_collateral_ratio'])
        liquidation_distance = float(strategy['liquidation_distance'])
        T1_A = float(strategy['token1_units'])
        T2_A = float(strategy['token2_units'])
        T3_B = float(strategy['token3_units'])  # L_B = perp long contract count
        # Optional fields — None is valid (liquidity cap may be unknown)
        token2_available_borrow  = _modal_sf(strategy, 'token2_available_borrow')

        precision_1A = get_token_precision(P1_A)
        precision_2A = get_token_precision(P2_A)
        precision_3B = get_token_precision(P3_B)
        token_amount_1A = T1_A * deployment_usd
        token_amount_2A = T2_A * deployment_usd
        token_amount_3B = T3_B * deployment_usd
        pp_1A = get_price_precision(token_amount_1A) if token_amount_1A > 0 else 4
        pp_2A = get_price_precision(token_amount_2A) if token_amount_2A > 0 else 4
        pp_3B = get_price_precision(token_amount_3B) if token_amount_3B > 0 else 4
        position_size_1A = l_a * deployment_usd
        position_size_2A = b_a * deployment_usd
        position_size_3B = token_amount_3B * P3_B  # actual USD exposure of perp
        borrow_fee_usd = b_a * token2_borrow_fee * deployment_usd
        perp_fee_usd = perp_fees_apr * deployment_usd
        effective_ltv_1A = (b_a / l_a) * token2_borrow_weight if l_a > 0 else 0.0

        calc = PositionCalculator()
        liq1 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'lending', token2_borrow_weight)
        liq2 = calc.calculate_liquidation_price(position_size_1A, position_size_2A, P1_A, P2_A, lltv_1A, 'borrowing', token2_borrow_weight)

        def _lp(r, pp):
            p = r['liq_price']
            return f"${p:.{pp}f}" if p != float('inf') and p > 0 else "N/A"

        def _ld(r):
            p = r['liq_price']
            return f"{r['pct_distance'] * 100:.2f}%" if p != float('inf') and p > 0 else "N/A"

        perp_liq_price = P3_B * (1.0 - liquidation_distance)
        perp_liq_dist_pct = -liquidation_distance * 100  # Negative: price needs to drop

        basis_ask = _modal_sf(strategy, 'basis_ask')
        basis_ask_str = f"{basis_ask * 100:.3f}%" if basis_ask is not None else "N/A"

        detail_data = [
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token1', ''),
                'Action': 'Lend (Stablecoin)',
                'maxCF': f"{token1_collateral_ratio:.2%}", 'LLTV': f"{lltv_1A:.2%}" if lltv_1A > 0 else "",
                'Eff LTV': f"{effective_ltv_1A:.2%}", 'Weight': f"{l_a:.4f}",
                'Rate': f"{token1_rate * 100:.2f}%",
                'APR Contrib': f"{stablecoin_lending_apr * 100:.2f}%",
                'Entry Basis': "—",
                'Token Amount': f"{token_amount_1A:,.{precision_1A}f}", 'Size ($)': f"${position_size_1A:,.2f}",
                'Price': f"${P1_A:.{pp_1A}f}", 'Fees (%)': "", 'Fees ($)': "",
                'Liq Risk': "Price DOWN", 'Liq Price': _lp(liq1, pp_1A), 'Liq Distance': _ld(liq1),
                'Max Borrow': f"${token2_available_borrow:,.2f}" if token2_available_borrow > 0 else "",
            },
            {
                'Protocol': strategy.get('protocol_a', ''), 'Token': strategy.get('token2', ''),
                'Action': 'Borrow (Spot)',
                'maxCF': "-", 'LLTV': "-", 'Eff LTV': "-", 'Weight': f"{b_a:.4f}",
                'Rate': f"{token2_rate * 100:.2f}%",
                'APR Contrib': f"{-token2_borrow_apr * 100:.2f}%",
                'Entry Basis': "—",
                'Token Amount': f"{token_amount_2A:,.{precision_2A}f}", 'Size ($)': f"${position_size_2A:,.2f}",
                'Price': f"${P2_A:.{pp_2A}f}",
                'Fees (%)': f"{token2_borrow_fee * 100:.2f}%" if token2_borrow_fee > 0 else "",
                'Fees ($)': f"${borrow_fee_usd:,.2f}" if borrow_fee_usd > 0 else "",
                'Liq Risk': "Price UP", 'Liq Price': _lp(liq2, pp_2A), 'Liq Distance': _ld(liq2),
                'Max Borrow': "",
            },
            {
                'Protocol': strategy.get('protocol_b', ''), 'Token': strategy.get('token3', ''),
                'Action': 'Long Perp',
                'maxCF': "-", 'LLTV': "-", 'Eff LTV': "-", 'Weight': f"{l_b:.4f}",
                'Rate': f"{token3_rate * 100:.2f}% (funding)",
                'APR Contrib': f"{funding_rate_apr * 100:.2f}%",
                'Entry Basis': basis_ask_str,
                'Token Amount': f"{token_amount_3B:,.{precision_3B}f}", 'Size ($)': f"${position_size_3B:,.2f}",
                'Price': f"${P3_B:.{pp_3B}f}",
                'Fees (%)': f"{perp_fees_apr * 100:.2f}%",
                'Fees ($)': f"${perp_fee_usd:,.2f}",
                'Liq Risk': "Price DOWN",
                'Liq Price': f"${perp_liq_price:,.{pp_3B}f}",
                'Liq Distance': f"{perp_liq_dist_pct:.2f}%",
                'Max Borrow': "",
            },
        ]

        detail_df = pd.DataFrame(detail_data)

        def _color_apr(val):
            if isinstance(val, str) and '%' in val:
                try:
                    v = float(val.split('%')[0])
                    if v > 0:
                        return 'color: green'
                    elif v < 0:
                        return 'color: red'
                except (ValueError, TypeError):
                    pass
            return ''

        def _color_liq(val):
            if isinstance(val, str):
                if val == "N/A":
                    return 'color: gray; font-style: italic'
                elif '%' in val:
                    try:
                        n = abs(float(val.replace('+', '').replace('-', '').replace('%', '')))
                        if n < 10:
                            return 'color: red'
                        elif n < 30:
                            return 'color: orange'
                        else:
                            return 'color: green'
                    except (ValueError, TypeError):
                        pass
            return ''

        styled_df = detail_df.style.map(_color_apr, subset=['APR Contrib']).map(_color_liq, subset=['Liq Distance'])
        st.dataframe(styled_df, width='stretch', hide_index=True)
