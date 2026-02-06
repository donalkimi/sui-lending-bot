"""
Utility functions for oracle price dashboard tab.
"""
from typing import Optional, Tuple
from datetime import datetime
import pandas as pd


def compute_latest_price(
    coingecko_price: Optional[float],
    coingecko_time: Optional[datetime],
    pyth_price: Optional[float],
    pyth_time: Optional[datetime]
) -> Tuple[Optional[float], Optional[str], Optional[datetime]]:
    """
    Determine the latest price across all oracles based on timestamps.

    Args:
        coingecko_price: CoinGecko price or None
        coingecko_time: CoinGecko timestamp or None
        pyth_price: Pyth price or None
        pyth_time: Pyth timestamp or None

    Returns:
        Tuple of (latest_price, latest_oracle, latest_time) or (None, None, None) if no valid data
    """
    candidates = []

    if coingecko_price is not None and coingecko_time is not None:
        candidates.append({
            'price': coingecko_price,
            'oracle': 'coingecko',
            'time': coingecko_time
        })

    if pyth_price is not None and pyth_time is not None:
        candidates.append({
            'price': pyth_price,
            'oracle': 'pyth',
            'time': pyth_time
        })

    if not candidates:
        return None, None, None

    # Sort by timestamp (descending) and pick latest
    latest = max(candidates, key=lambda x: x['time'])

    return latest['price'], latest['oracle'], latest['time']


def format_contract_address(contract: str) -> str:
    """
    Format contract address for display (first 6 + last 4 chars).

    Args:
        contract: Full contract address

    Returns:
        Formatted address string
    """
    if not contract or len(contract) < 12:
        return contract
    return f"{contract[:6]}...{contract[-4:]}"


def compute_timestamp_age(timestamp) -> str:
    """
    Compute human-readable age from timestamp.

    Args:
        timestamp: Datetime or timestamp string

    Returns:
        Age string (e.g., "5m", "2h", "3d")
    """
    if pd.isna(timestamp):
        return "N/A"

    try:
        dt = pd.to_datetime(timestamp)
        now = datetime.now()

        # Handle timezone-aware timestamps
        if dt.tzinfo is not None:
            from datetime import timezone
            now = datetime.now(timezone.utc)

        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h"
        else:
            return f"{int(seconds / 86400)}d"
    except Exception:
        return "N/A"
