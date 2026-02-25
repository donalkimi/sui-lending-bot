"""Main orchestration for strategy history retrieval."""

import pandas as pd
from typing import Dict, Optional
import logging

from analysis.strategy_history import get_handler
from analysis.strategy_history.data_fetcher import fetch_rates_from_database, fetch_basis_history
from analysis.strategy_calculators import get_calculator

logger = logging.getLogger(__name__)


def get_strategy_history(
    strategy: Dict,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> pd.DataFrame:
    """
    Get historical APR timeseries for a strategy configuration.

    Args:
        strategy: Dict with:
            - strategy_type: Required ('stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending')
            - token1_contract: Required
            - token2_contract: Required for noloop/recursive
            - token3_contract: Required for recursive
            - protocol_a: Required
            - protocol_b: Required for noloop/recursive
            - liquidation_distance: Optional (default from settings)
        start_timestamp: Unix seconds (default: earliest available)
        end_timestamp: Unix seconds (default: latest available)

    Returns:
        DataFrame with columns:
        - timestamp (Unix seconds) - index
        - net_apr (decimal)
        - gross_apr (decimal, if available from calculator)
        - strategy_type (str)

    Raises:
        ValueError: If strategy dict is invalid

    Example:
        >>> strategy_dict = {
        ...     'strategy_type': 'recursive_lending',
        ...     'token1_contract': '0xabc...',
        ...     'token2_contract': '0xdef...',
        ...     'token3_contract': '0x123...',
        ...     'protocol_a': 'navi',
        ...     'protocol_b': 'suilend'
        ... }
        >>> df = get_strategy_history(strategy_dict)
        >>> # Returns DataFrame with historical APR data
    """

    # Step 1: Get strategy type and validate
    strategy_type = strategy.get('strategy_type')
    if not strategy_type:
        raise ValueError("strategy dict must contain 'strategy_type'")

    # Step 2: Get handler from registry
    handler = get_handler(strategy_type)
    logger.debug(f"Using handler: {handler.__class__.__name__}")

    # Step 3: Validate strategy dict
    is_valid, error_msg = handler.validate_strategy_dict(strategy)
    if not is_valid:
        raise ValueError(f"Invalid strategy dict: {error_msg}")

    # Step 4: Get required token/protocol pairs
    token_pairs = handler.get_required_tokens(strategy)
    logger.info(f"Fetching history for {len(token_pairs)} legs")

    # Step 5: Fetch raw rates data
    raw_df = fetch_rates_from_database(token_pairs, start_timestamp, end_timestamp)

    if raw_df.empty:
        logger.warning("No rate data found for specified parameters")
        return pd.DataFrame(columns=['timestamp', 'net_apr', 'strategy_type']).set_index('timestamp')

    # Step 6: Calculate APR timeseries
    apr_df = calculate_apr_timeseries(handler, raw_df, strategy)

    # Step 7: Add strategy_type column
    apr_df['strategy_type'] = strategy_type

    # Step 8: For perp strategies, left-join basis_mid from spot_perp_basis.
    # spot_contract is token1_contract for perp_lending, token2_contract for perp_borrowing*.
    perp_types = {'perp_lending', 'perp_borrowing', 'perp_borrowing_recursive'}
    if strategy_type in perp_types:
        perp_proxy    = strategy.get('token3_contract')
        spot_contract = (strategy.get('token1_contract')
                         if strategy_type == 'perp_lending'
                         else strategy.get('token2_contract'))

        if perp_proxy and spot_contract:
            basis_df = fetch_basis_history(
                perp_proxy=perp_proxy,
                spot_contract=spot_contract,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
            if not basis_df.empty:
                apr_df = apr_df.join(basis_df[['basis_mid']], how='left')
            else:
                apr_df['basis_mid'] = None
        else:
            apr_df['basis_mid'] = None
    else:
        apr_df['basis_mid'] = None

    logger.info(f"Calculated APR for {len(apr_df)} timestamps")

    return apr_df


def calculate_apr_timeseries(
    handler,
    raw_df: pd.DataFrame,
    strategy: Dict
) -> pd.DataFrame:
    """
    Calculate APR for each timestamp using existing strategy calculators.

    Args:
        handler: HistoryHandlerBase instance
        raw_df: Raw rates data from fetch_rates_from_database()
        strategy: Strategy configuration dict

    Returns:
        DataFrame with columns:
        - timestamp (Unix seconds) - index
        - net_apr (decimal)
        - gross_apr (decimal, if available)

    Process:
        For each timestamp:
        1. Group rows by timestamp
        2. handler.build_market_data_dict() - transform to calculator input
        3. calculator.analyze_strategy() - compute APR
        4. Extract net_apr from result
    """

    strategy_type = strategy['strategy_type']
    calculator = get_calculator(strategy_type)

    results = []

    # Group by timestamp
    for timestamp, group in raw_df.groupby('timestamp'):

        # Transform raw rows into market_data dict
        market_data = handler.build_market_data_dict(group, strategy)

        if market_data is None:
            # Skip incomplete timestamps
            logger.debug(f"Skipping timestamp {timestamp}: incomplete data")
            continue

        try:
            # Calculate APR using existing calculator
            # Unpack market_data dict into individual keyword arguments
            result = calculator.analyze_strategy(**market_data)

            # Extract APR values
            net_apr = result.get('net_apr', result.get('apr_net'))

            if net_apr is None:
                logger.warning(f"No APR returned for timestamp {timestamp}")
                continue

            # Compute avg8hr / avg24hr net APR by substituting perp leg avg rate and re-running.
            # Works for perp_borrowing (lend_avg8hr_apr_3B) and perp_lending (borrow_avg8hr_apr_3B).
            # For non-perp strategies these keys are absent so avg APRs remain None.
            net_avg8hr_apr = None
            net_avg24hr_apr = None

            avg8hr_key = ('lend_avg8hr_apr_3B'   if 'lend_avg8hr_apr_3B'   in market_data else
                          'borrow_avg8hr_apr_3B'  if 'borrow_avg8hr_apr_3B' in market_data else None)
            avg24hr_key = ('lend_avg24hr_apr_3B'  if 'lend_avg24hr_apr_3B'  in market_data else
                           'borrow_avg24hr_apr_3B' if 'borrow_avg24hr_apr_3B' in market_data else None)
            spot_key = ('lend_total_apr_3B'  if 'lend_total_apr_3B'  in market_data else
                        'borrow_total_apr_3B' if 'borrow_total_apr_3B' in market_data else None)

            if avg8hr_key and spot_key and market_data.get(avg8hr_key) is not None:
                try:
                    r8 = calculator.analyze_strategy(**{**market_data, spot_key: market_data[avg8hr_key]})
                    net_avg8hr_apr = r8.get('net_apr', r8.get('apr_net'))
                except Exception:
                    pass

            if avg24hr_key and spot_key and market_data.get(avg24hr_key) is not None:
                try:
                    r24 = calculator.analyze_strategy(**{**market_data, spot_key: market_data[avg24hr_key]})
                    net_avg24hr_apr = r24.get('net_apr', r24.get('apr_net'))
                except Exception:
                    pass

            # Extract token2 price for position charts (if token2 exists)
            token2_price = None
            if 'token2_contract' in strategy and strategy['token2_contract']:
                token2_rows = group[group['token_contract'] == strategy['token2_contract']]
                if not token2_rows.empty:
                    token2_price = token2_rows.iloc[0]['price_usd']

            results.append({
                'timestamp':            timestamp,
                'net_apr':              net_apr,
                'net_avg8hr_apr':       net_avg8hr_apr,
                'net_avg24hr_apr':      net_avg24hr_apr,
                'gross_apr':            result.get('gross_apr', result.get('apr_gross')),
                'apr5':                 result.get('apr5'),
                'apr30':                result.get('apr30'),
                'apr90':                result.get('apr90'),
                'token2_price':         token2_price,
                # Per-leg raw rates for analysis tab display
                'lend_total_apr_1A':    market_data.get('raw_lend_total_apr_1A'),
                'borrow_total_apr_2A':  market_data.get('raw_borrow_total_apr_2A'),
                'perp_rate_3B':         market_data.get('raw_perp_rate_3B'),
                'avg8hr_perp_rate_3B':  market_data.get('raw_avg8hr_perp_rate_3B'),
                'avg24hr_perp_rate_3B': market_data.get('raw_avg24hr_perp_rate_3B'),
            })

        except Exception as e:
            logger.warning(f"Failed to calculate APR for timestamp {timestamp}: {e}")
            continue

    # Build DataFrame
    if not results:
        logger.warning("No APR values calculated")
        return pd.DataFrame(columns=[
            'timestamp', 'net_apr', 'net_avg8hr_apr', 'net_avg24hr_apr',
            'gross_apr', 'apr5', 'apr30', 'apr90', 'token2_price',
            'lend_total_apr_1A', 'borrow_total_apr_2A',
            'perp_rate_3B', 'avg8hr_perp_rate_3B', 'avg24hr_perp_rate_3B',
            'basis_mid',
        ]).set_index('timestamp')

    df = pd.DataFrame(results)
    df = df.set_index('timestamp')

    return df
