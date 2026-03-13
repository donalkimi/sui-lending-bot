"""
Base class for strategy-specific calculations.

All strategy calculators must inherit from StrategyCalculatorBase and implement
the abstract methods for position calculation, APR calculation, and rebalancing.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Minimum token delta below which a rebalance action is considered "No change"
MIN_TOKEN_DELTA = 0.0001


def _liq_delta(d: float, collateral_amount, collateral_price,
               loan_amount, loan_price, lltv: float, bw: float = 1.0) -> float:
    """
    Compute how much the liq distance has drifted from baseline for an LLTV-based leg.

    Returns abs(baseline_liq_dist) - abs(live_liq_dist).
    Positive value = liq distance has shrunk (closer to liquidation).
    Returns 0.0 if any required value is missing.
    """
    if not (collateral_amount and collateral_price and loan_amount and loan_price and lltv):
        return 0.0
    ltv = (loan_amount * loan_price * bw) / (collateral_amount * collateral_price)
    if ltv <= 0:
        return 0.0
    live_liq_dist = (lltv / ltv) - 1
    return abs(d) - abs(live_liq_dist)


def _perp_liq_delta(d: float, entry_price, live_price, direction: str) -> float:
    """
    Compute liq distance drift for an exchange-side perp leg.

    direction: 'short' (liq when price rises) or 'long' (liq when price drops).
    Returns 0.0 if any required value is missing.
    """
    if not (entry_price and live_price):
        return 0.0
    liq_price = entry_price * (1 + d) if direction == 'short' else entry_price * (1 - d)
    return abs(d) - abs((liq_price - live_price) / live_price)


def _build_reason(token_deltas: dict, threshold: float) -> str:
    """
    Build a human-readable reason string showing all token liq dist deltas.
    Tokens that exceeded the threshold are flagged with [TRIGGERED].

    token_deltas: {token_name: delta_value}  e.g. {'token2': 0.052, 'token1': 0.001}
    """
    parts = []
    for token, delta in token_deltas.items():
        if delta >= threshold:
            parts.append(f"{token} [TRIGGERED {delta:.1%}]")
        else:
            parts.append(f"{token} {delta:.1%}")
    return " | ".join(parts) + f"  (threshold {threshold:.1%})"


def _format_lend_action(delta: float, token: str, min_delta: float = MIN_TOKEN_DELTA) -> str:
    """Format a lend-leg rebalance action string from a token delta."""
    if abs(delta) < min_delta:
        return 'No change'
    n = abs(delta)
    return f'Add {n:.4f} {token}' if delta > 0 else f'Withdraw {n:.4f} {token}'


def _format_borrow_action(delta: float, token: str, min_delta: float = MIN_TOKEN_DELTA) -> str:
    """Format a borrow-leg rebalance action string from a token delta."""
    if abs(delta) < min_delta:
        return 'No change'
    n = abs(delta)
    return f'Borrow {n:.4f} {token}' if delta > 0 else f'Repay {n:.4f} {token}'


class StrategyCalculatorBase(ABC):
    """Base class for strategy-specific calculations"""

    @abstractmethod
    def get_strategy_type(self) -> str:
        """
        Returns strategy type identifier.

        Examples: 'stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending'
        """
        pass

    @abstractmethod
    def get_required_legs(self) -> int:
        """
        Returns number of legs (1, 3, or 4).

        - 1 leg: Stablecoin lending (single lend)
        - 3 legs: No-loop cross-protocol (lend, borrow, lend)
        - 4 legs: Recursive lending (lend, borrow, lend, borrow with loop)
        """
        pass

    @abstractmethod
    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers/weights for this strategy.

        Returns:
            Dict with keys: l_a, b_a, l_b, b_b (all float, use 0.0 for unused legs)

        Example:
            {
                'l_a': 1.0,   # Lend multiplier at protocol A
                'b_a': 0.67,  # Borrow multiplier at protocol A
                'l_b': 0.67,  # Lend multiplier at protocol B
                'b_b': 0.0    # Borrow multiplier at protocol B (0 if not used)
            }
        """
        pass

    @abstractmethod
    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for this strategy (deterministic protocol fees only).

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_*, borrow_total_apr_* (base + reward combined)
            fees: Dict with borrow_fee_* (nullable, may need fallback)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        pass

    def calculate_basis_adj_net_apr(
        self,
        positions: Dict[str, float],
        rates: Dict[str, float],
        fees: Dict[str, float],
        basis_cost: float = 0.0
    ) -> float:
        """
        Net APR minus basis cost (market-dependent spot/perp spread).

        For non-perp strategies, callers pass basis_cost=0.0 (default) → returns net_apr unchanged.
        For perp strategies, callers pass the actual basis cost → returns net_apr - basis_cost.

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_*, borrow_total_apr_*
            fees: Dict with borrow_fee_*
            basis_cost: Basis cost as fraction of deployment (decimal, default 0.0)

        Returns:
            Basis-adjusted net APR as decimal
        """
        return self.calculate_net_apr(positions, rates, fees) - basis_cost

    @abstractmethod
    def analyze_strategy(self, **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis returning all metrics.

        Must return dict with at minimum:
            - l_a, b_a, l_b, b_b: Position multipliers (float)
            - net_apr: Decimal net APR (float)
            - liquidation_distance: Safety buffer from liquidation (float, could be inf)
            - max_size: Max deployable size in USD (float, could be inf)
            - valid: Whether strategy is valid (bool)
            - strategy_type: Strategy identifier (str)

        Optional but recommended:
            - apr5, apr30, apr90: Time-adjusted APRs
            - days_to_breakeven: Days to recover upfront fees
            - error: Error message if not valid
        """
        pass

    @abstractmethod
    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict,
                                   force: bool = False) -> Dict:
        """
        Calculate token amounts needed to restore target weights.

        FAIL LOUD: Never return None. Always return a dict.

        Args:
            position: Position dict with entry state (deployment_usd, l_a, b_a, l_b, b_b, etc.)
            live_rates: Current market rates
            live_prices: Current token prices

        Returns:
            Dict with structure:
            {
                "requires_rebalance": bool,  # True if rebalancing needed (outside tolerance)
                "actions": List[Dict],       # Empty list if no rebalancing needed
                "reason": str                # Human-readable explanation
            }

        Raises:
            ValueError: If position data is invalid or missing
            KeyError: If required rates/prices are missing
        """
        pass

    # ========== Fee-Adjusted APR Calculation Methods ==========

    @abstractmethod
    def calculate_gross_apr(self,
                           positions: Dict[str, float],
                           rates: Dict[str, float]) -> float:
        """
        Calculate gross APR (earnings - borrowing costs, before fees).

        This is the annualized yield from lending minus borrowing costs,
        excluding upfront fees. Fees are subtracted separately in calculate_net_apr().

        Formula:
            gross_apr = sum(lending_earnings) - sum(borrowing_costs)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b multipliers
            rates: Dict with rate_token1, rate_token3 (if applicable),
                   rate_token2, rate_token4 (if applicable)

        Returns:
            Gross APR as decimal (e.g., 0.0524 = 5.24%)

        Note:
            This method must be implemented by each calculator since the
            lending/borrowing structure differs:
            - Stablecoin: Only l_a lending, no borrowing
            - NoLoop: l_a + l_b lending, b_a borrowing
            - Recursive: l_a + l_b lending, b_a + b_b borrowing
        """
        raise NotImplementedError("Subclasses must implement calculate_gross_apr()")

    def calculate_apr_for_days(self,
                               gross_apr: float,
                               b_a: float,
                               b_b: float,
                               borrow_fee_token2: float,
                               borrow_fee_token4: float,
                               days: int) -> float:
        """
        Calculate time-adjusted APR for a specific time horizon.

        When upfront fees exist, short-term APRs are lower because fees
        are amortized over fewer days.

        Formula:
            APR(N days) = (gross_apr × N/365 - total_fee_cost) × 365/N

            Derivation: earn N days of gross APR, subtract the one-time upfront cost, annualise.
            Where total_fee_cost = b_a × fee_token2 + b_b × fee_token4

        Args:
            gross_apr: Gross APR (before fees) as decimal
            b_a: Borrow multiplier for leg 2A
            b_b: Borrow multiplier for leg 3B (0.0 for stablecoin/noloop)
            borrow_fee_token2: Upfront fee for borrowing token2 (0.0 if None)
            borrow_fee_token4: Upfront fee for borrowing token4 (0.0 if None)
            days: Time horizon (5, 30, 90, etc.)

        Returns:
            Time-adjusted APR as decimal

        Example:
            gross_apr = 0.11 (11%), fees = 0.002 (0.2%), days = 5
            → earn 5d: 0.11 × 5/365 = 0.00151
            → subtract fee: 0.00151 - 0.002 = -0.00049
            → annualise: -0.00049 × 365/5 = -0.036 (-3.6%)
            (Negative because fees exceed 5-day earnings)
        """
        total_fee_cost = b_a * borrow_fee_token2 + b_b * borrow_fee_token4
        return (gross_apr * days / 365 - total_fee_cost) * 365 / days

    def calculate_days_to_breakeven(self,
                                    gross_apr: float,
                                    b_a: float,
                                    b_b: float,
                                    borrow_fee_token2: float,
                                    borrow_fee_token4: float) -> float:
        """
        Calculate days until upfront fees are recovered.

        Formula:
            days_to_breakeven = (total_fee_cost × 365) / gross_apr

        Args:
            gross_apr: Gross APR (before fees) as decimal
            b_a: Borrow multiplier for leg 2A
            b_b: Borrow multiplier for leg 3B (0.0 for stablecoin/noloop)
            borrow_fee_token2: Upfront fee for borrowing token2 (0.0 if None)
            borrow_fee_token4: Upfront fee for borrowing token4 (0.0 if None)

        Returns:
            Days to breakeven (0.0 if no fees or gross_apr <= 0)

        Example:
            gross_apr = 0.11 (11%), total_fees = 0.002 (0.2%)
            → days = (0.002 × 365) / 0.11 = 6.6 days
        """
        if gross_apr <= 0:
            return 0.0

        total_fee_cost = b_a * borrow_fee_token2 + b_b * borrow_fee_token4
        if total_fee_cost == 0:
            return 0.0

        return (total_fee_cost * 365.0) / gross_apr

    def calculate_fee_adjusted_aprs(self,
                                    positions: Dict[str, float],
                                    rates: Dict[str, float],
                                    fees: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate all fee-adjusted APR metrics.

        Returns net APR (365-day), time-adjusted APRs (5/30/90 day),
        and days to breakeven.

        Args:
            positions: Dict with l_a, b_a, l_b, b_b multipliers
            rates: Dict with lending/borrowing APRs
            fees: Dict with borrow_fee_token2, borrow_fee_token4 (nullable)

        Returns:
            Dict with:
                - apr_gross: Earnings - borrowing costs (before fees)
                - net_apr: Net APR (365-day, after fees)
                - apr5: 5-day time-adjusted APR
                - apr30: 30-day time-adjusted APR
                - apr90: 90-day time-adjusted APR
                - days_to_breakeven: Days to recover upfront fees

        Note:
            Calls calculate_gross_apr() which must be implemented by subclass.
        """
        # Calculate gross APR (subclass-specific implementation)
        gross_apr = self.calculate_gross_apr(positions, rates)

        # Extract position multipliers and fees
        b_a = positions['b_a']
        b_b = positions['b_b']
        borrow_fee_token2 = fees.get('borrow_fee_token2')
        if borrow_fee_token2 is None:
            logger.warning("Missing borrow_fee_token2 in fees dict - assuming 0.0")
            borrow_fee_token2 = 0.0
        borrow_fee_token4 = fees.get('borrow_fee_token4')
        if borrow_fee_token4 is None:
            logger.warning("Missing borrow_fee_token4 in fees dict - assuming 0.0")
            borrow_fee_token4 = 0.0

        # Calculate annualized fee cost (for 365-day net APR)
        total_fee_cost = b_a * borrow_fee_token2 + b_b * borrow_fee_token4
        apr_net = gross_apr - total_fee_cost

        # Calculate time-adjusted APRs
        apr5 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_token2, borrow_fee_token4, 5)
        apr30 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_token2, borrow_fee_token4, 30)
        apr90 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_token2, borrow_fee_token4, 90)

        # Calculate breakeven
        days_to_breakeven = self.calculate_days_to_breakeven(
            gross_apr, b_a, b_b, borrow_fee_token2, borrow_fee_token4
        )

        return {
            'apr_gross': gross_apr,
            'net_apr': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven
        }
