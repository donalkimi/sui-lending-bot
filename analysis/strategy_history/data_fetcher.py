"""Database fetching utilities for strategy history."""

import pandas as pd
from typing import List, Tuple, Optional
import logging

from dashboard.db_utils import get_db_engine
from config import settings

logger = logging.getLogger(__name__)


def fetch_rates_from_database(
    token_protocol_pairs: List[Tuple[str, str]],
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> pd.DataFrame:
    """
    Fetch rate snapshots for specified token/protocol pairs.

    Args:
        token_protocol_pairs: List of (token_contract, protocol) tuples
        start_timestamp: Start time (Unix seconds), default: earliest available
        end_timestamp: End time (Unix seconds), default: latest available

    Returns:
        DataFrame with columns:
        - timestamp (Unix seconds)
        - token_contract
        - protocol
        - lend_total_apr, lend_base_apr, lend_reward_apr
        - borrow_total_apr, borrow_base_apr, borrow_reward_apr
        - price_usd
        - collateral_ratio, liquidation_threshold, borrow_fee
        - avg8hr_lend_total_apr, avg8hr_borrow_total_apr (NULL for non-Bluefin rows)
        - avg24hr_lend_total_apr, avg24hr_borrow_total_apr (NULL for non-Bluefin rows)

    Example:
        >>> pairs = [('0xabc...', 'navi'), ('0xdef...', 'suilend')]
        >>> df = fetch_rates_from_database(pairs, start_ts, end_ts)
        >>> # Returns all rate snapshots for those pairs in that time range

    Note:
        - Uses parameterized queries to prevent SQL injection
        - Converts Unix timestamps to datetime strings for SQLite/PostgreSQL compatibility
        - Always fetches both collateral_ratio AND liquidation_threshold (Principle 10)
    """
    engine = get_db_engine()

    # Convert Unix timestamps to datetime strings for SQL (Principle 5: Timestamp boundaries)
    from utils.time_helpers import to_datetime_str

    # Use correct placeholder for database type (PostgreSQL uses %s, SQLite uses ?)
    placeholder = '%s' if settings.USE_CLOUD_DB else '?'

    # Build WHERE clause for token/protocol pairs (parameterized for safety)
    pair_conditions = []
    for token_contract, protocol in token_protocol_pairs:
        pair_conditions.append(
            f"(token_contract = {placeholder} AND protocol = {placeholder})"
        )

    pairs_clause = " OR ".join(pair_conditions)

    # Flatten token_protocol_pairs into parameter list
    params = []
    for token_contract, protocol in token_protocol_pairs:
        params.extend([token_contract, protocol])

    # Build time range clause with parameters
    time_clause = ""
    if start_timestamp is not None:
        time_clause += f" AND timestamp >= {placeholder}"
        params.append(to_datetime_str(start_timestamp))
    if end_timestamp is not None:
        time_clause += f" AND timestamp <= {placeholder}"
        params.append(to_datetime_str(end_timestamp))

    # Query rates_snapshot table (Principle 10: Always fetch both collateral_ratio and liquidation_threshold)
    # Include base and reward APR components for breakdown analysis
    # avg8hr/avg24hr columns are populated for Bluefin perp rows only (NULL elsewhere)
    query = f"""
        SELECT
            timestamp,
            token_contract,
            protocol,
            lend_total_apr,
            lend_base_apr,
            lend_reward_apr,
            borrow_total_apr,
            borrow_base_apr,
            borrow_reward_apr,
            price_usd,
            collateral_ratio,
            liquidation_threshold,
            borrow_fee,
            avg8hr_lend_total_apr,
            avg8hr_borrow_total_apr,
            avg24hr_lend_total_apr,
            avg24hr_borrow_total_apr
        FROM rates_snapshot
        WHERE use_for_pnl = TRUE
          AND ({pairs_clause})
          {time_clause}
        ORDER BY timestamp ASC
    """

    logger.debug(f"Fetching rates for {len(token_protocol_pairs)} token/protocol pairs")
    logger.debug(f"Time range: {start_timestamp} to {end_timestamp}")

    try:
        # Use parameterized query for safety
        # SQLAlchemy requires tuple or dict, not list
        df = pd.read_sql(query, engine, params=tuple(params))

        # Convert timestamp strings back to Unix seconds for internal processing (Principle 5)
        from utils.time_helpers import to_seconds
        if not df.empty and 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].apply(to_seconds)

        logger.info(f"Fetched {len(df)} rate snapshots")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch rates: {e}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        raise


def fetch_basis_history(
    perp_proxy: str,
    spot_contract: str,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
) -> pd.DataFrame:
    """
    Fetch basis_mid history from spot_perp_basis for a specific perp/spot pair.

    Args:
        perp_proxy:       Perp proxy contract key (e.g. '0xBTC-USDC-PERP_bluefin')
        spot_contract:    On-chain spot token contract address
        start_timestamp:  Start time (Unix seconds), inclusive
        end_timestamp:    End time (Unix seconds), inclusive

    Returns:
        DataFrame with columns:
        - timestamp (Unix seconds, index)
        - basis_mid (decimal, e.g. -0.0003 = -0.03%)
        Empty DataFrame if no data is available.
    """
    engine = get_db_engine()
    from utils.time_helpers import to_datetime_str, to_seconds

    placeholder = '%s' if settings.USE_CLOUD_DB else '?'

    params: list = [perp_proxy, spot_contract]
    time_clause = ""
    if start_timestamp is not None:
        time_clause += f" AND timestamp >= {placeholder}"
        params.append(to_datetime_str(start_timestamp))
    if end_timestamp is not None:
        time_clause += f" AND timestamp <= {placeholder}"
        params.append(to_datetime_str(end_timestamp))

    query = f"""
        SELECT timestamp, basis_mid
        FROM spot_perp_basis
        WHERE perp_proxy = {placeholder}
          AND spot_contract = {placeholder}
          {time_clause}
        ORDER BY timestamp ASC
    """

    try:
        df = pd.read_sql(query, engine, params=tuple(params))
        if df.empty:
            return pd.DataFrame(columns=['timestamp', 'basis_mid']).set_index('timestamp')
        df['timestamp'] = df['timestamp'].apply(to_seconds)
        df = df.set_index('timestamp')
        return df
    except Exception as e:
        logger.warning(f"Failed to fetch basis history: {e}")
        return pd.DataFrame(columns=['timestamp', 'basis_mid']).set_index('timestamp')
