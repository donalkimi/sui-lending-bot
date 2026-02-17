"""
Time conversion utilities for the Sui Lending Bot.

Core principle: Work in Unix timestamps (seconds as integers) internally.
Convert only at boundaries (database, UI).

Single datetime string format everywhere: "2026-01-16 12:00:00"
"""

from datetime import datetime
from typing import Union


def to_seconds(ts: Union[str, datetime, int, float]) -> int:
    """
    Convert any timestamp format to Unix seconds.
    FAILS LOUDLY if input is not recognized.

    Args:
        ts: datetime string, datetime object, Unix timestamp (int), or numeric timestamp (float)

    Returns:
        Unix timestamp in seconds (integer)

    Raises:
        TypeError: If input type is not supported
        ValueError: If string format is invalid or timestamp is None
    """
    if ts is None:
        raise ValueError("Cannot convert None to seconds - timestamp is required")

    # Already an integer (Unix timestamp)
    if isinstance(ts, int):
        # Sanity check: should be reasonable Unix timestamp (after year 2000, before year 2100)
        if ts < 946684800 or ts > 4102444800:
            raise ValueError(f"Integer {ts} doesn't look like a valid Unix timestamp (seconds since epoch)")
        return ts

    # Float (pandas/numpy often converts int timestamps to float64)
    # Convert to int, preserving the original seconds value
    if isinstance(ts, float):
        # Check for NaN (pandas missing value indicator)
        if ts != ts:  # NaN != NaN is True
            raise ValueError("Cannot convert NaN to seconds - timestamp is missing")
        ts_int = int(ts)
        # Sanity check: should be reasonable Unix timestamp
        if ts_int < 946684800 or ts_int > 4102444800:
            raise ValueError(f"Float {ts} doesn't look like a valid Unix timestamp (seconds since epoch)")
        return ts_int

    # String format: "2026-01-16 12:00:00" or "2026-01-16T12:00:00"
    elif isinstance(ts, str):
        if not ts.strip():
            raise ValueError("Cannot convert empty string to seconds")
        try:
            # Handle both space and 'T' separator
            dt = datetime.fromisoformat(ts.replace(' ', 'T'))
            return int(dt.timestamp())
        except ValueError as e:
            raise ValueError(f"Cannot parse timestamp string '{ts}': {e}")

    # Python datetime.datetime object
    elif isinstance(ts, datetime):
        return int(ts.timestamp())

    # pandas.Timestamp object
    elif hasattr(ts, 'to_pydatetime'):
        try:
            return int(ts.to_pydatetime().timestamp())
        except Exception as e:
            raise TypeError(f"Failed to convert pandas.Timestamp to seconds: {e}")

    # Unknown type - FAIL LOUDLY
    else:
        raise TypeError(
            f"Cannot convert {type(ts).__name__} to seconds. "
            f"Supported types: int, str, datetime.datetime, pandas.Timestamp. "
            f"Got: {type(ts)}"
        )


def to_datetime_str(seconds: int) -> str:
    """
    Convert Unix seconds to datetime string.
    Used everywhere: database, UI, display, everything.
    FAILS LOUDLY if input is not valid.

    Single format for the entire system: "2026-01-16 12:00:00"

    Args:
        seconds: Unix timestamp in seconds (integer)

    Returns:
        Datetime string like "2026-01-16 12:00:00"

    Raises:
        TypeError: If seconds is not an integer
        ValueError: If seconds is None or not a valid Unix timestamp
    """
    if seconds is None:
        raise ValueError("Cannot convert None to datetime string - seconds is required")

    if not isinstance(seconds, int):
        raise TypeError(
            f"seconds must be int, got {type(seconds).__name__}. "
            f"Use to_seconds() first to convert to int."
        )

    # Sanity check: should be reasonable Unix timestamp (after year 2000, before year 2100)
    if seconds < 946684800 or seconds > 4102444800:
        raise ValueError(
            f"Integer {seconds} doesn't look like a valid Unix timestamp. "
            f"Expected range: 946684800 (2000-01-01) to 4102444800 (2100-01-01)"
        )

    try:
        return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, OverflowError, ValueError) as e:
        raise ValueError(f"Failed to convert {seconds} to datetime string: {e}")
