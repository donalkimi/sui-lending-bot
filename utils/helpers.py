"""
Shared utility functions for Sui Lending Bot
"""

from datetime import datetime, timezone


def generate_snapshot_timestamp():
    """
    Generate snapshot timestamp rounded DOWN to nearest minute (UTC).
    
    Avoids timezone/DST issues by always using UTC.
    Rounds down so 10:15:37 becomes 10:15:00.
    
    Returns:
        datetime object (timezone-aware UTC)
        
    Example:
        >>> ts = generate_snapshot_timestamp()
        >>> # Current time: 2025-01-08 10:15:37.123456 UTC
        >>> # Returns:      2025-01-08 10:15:00+00:00
    """
    now = datetime.now(timezone.utc)
    # Round DOWN to nearest minute
    now = now.replace(second=0, microsecond=0)
    
    return now