"""
Base class for strategy-specific calculations.

All strategy calculators must inherit from StrategyCalculatorBase and implement
the abstract methods for position calculation, APR calculation, and rebalancing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


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
                         fees: Dict[str, float],
                         basis_cost: float = 0.0) -> float:
        """
        Calculate net APR for this strategy.

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_*, borrow_total_apr_* (base + reward combined)
            fees: Dict with borrow_fee_* (nullable, may need fallback)
            basis_cost: One-time round-trip spot/perp spread cost (decimal, default 0.0)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        pass

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
                                   live_prices: Dict) -> Dict:
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
            rates: Dict with lend_total_apr_1A, lend_total_apr_2B (if applicable),
                   borrow_total_apr_2A, borrow_total_apr_3B (if applicable)

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
                               borrow_fee_2A: float,
                               borrow_fee_3B: float,
                               days: int) -> float:
        """
        Calculate time-adjusted APR for a specific time horizon.

        When upfront fees exist, short-term APRs are lower because fees
        are amortized over fewer days.

        Formula:
            APR(N days) = (gross_apr × N/365 - total_fee_cost) × 365/N

            Derivation: earn N days of gross APR, subtract the one-time upfront cost, annualise.
            Where total_fee_cost = b_a × fee_2A + b_b × fee_3B

        Args:
            gross_apr: Gross APR (before fees) as decimal
            b_a: Borrow multiplier for leg 2A
            b_b: Borrow multiplier for leg 3B (0.0 for stablecoin/noloop)
            borrow_fee_2A: Upfront fee for borrowing token2 (0.0 if None)
            borrow_fee_3B: Upfront fee for borrowing token3 (0.0 if None)
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
        total_fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B
        return (gross_apr * days / 365 - total_fee_cost) * 365 / days

    def calculate_days_to_breakeven(self,
                                    gross_apr: float,
                                    b_a: float,
                                    b_b: float,
                                    borrow_fee_2A: float,
                                    borrow_fee_3B: float) -> float:
        """
        Calculate days until upfront fees are recovered.

        Formula:
            days_to_breakeven = (total_fee_cost × 365) / gross_apr

        Args:
            gross_apr: Gross APR (before fees) as decimal
            b_a: Borrow multiplier for leg 2A
            b_b: Borrow multiplier for leg 3B (0.0 for stablecoin/noloop)
            borrow_fee_2A: Upfront fee for borrowing token2 (0.0 if None)
            borrow_fee_3B: Upfront fee for borrowing token3 (0.0 if None)

        Returns:
            Days to breakeven (0.0 if no fees or gross_apr <= 0)

        Example:
            gross_apr = 0.11 (11%), total_fees = 0.002 (0.2%)
            → days = (0.002 × 365) / 0.11 = 6.6 days
        """
        if gross_apr <= 0:
            return 0.0

        total_fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B
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
            fees: Dict with borrow_fee_2A, borrow_fee_3B (nullable)

        Returns:
            Dict with:
                - apr_gross: Earnings - borrowing costs (before fees)
                - apr_net: Net APR (365-day, after fees)
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
        borrow_fee_2A = fees.get('borrow_fee_2A') or 0.0
        borrow_fee_3B = fees.get('borrow_fee_3B') or 0.0

        # Calculate annualized fee cost (for 365-day net APR)
        total_fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B
        apr_net = gross_apr - total_fee_cost

        # Calculate time-adjusted APRs
        apr5 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 5)
        apr30 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 30)
        apr90 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 90)

        # Calculate breakeven
        days_to_breakeven = self.calculate_days_to_breakeven(
            gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B
        )

        return {
            'apr_gross': gross_apr,
            'apr_net': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven
        }
