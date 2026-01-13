"""
Navi Protocol Borrow Fee Configuration

Navi does not expose borrow fees through their API, so we maintain
a hardcoded fee schedule here.
"""
from typing import Optional

def get_navi_borrow_fee(token_symbol: Optional[str] = None, token_contract: Optional[str] = None) -> float:
    """
    Get the borrow fee for Navi Protocol.

    Navi charges a flat 30 basis points (0.30%) on all borrows.

    Args:
        token_symbol: Token symbol (e.g., "USDC") - currently unused
        token_contract: Token contract address - currently unused

    Returns:
        Borrow fee as decimal (e.g., 0.0030 for 30 bps)
    """
    # Flat fee for all tokens
    NAVI_BORROW_FEE_BPS = 30  # 30 basis points
    return NAVI_BORROW_FEE_BPS / 10000.0  # Convert to decimal: 0.0030
