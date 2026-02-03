"""
Position size calculator for recursive cross-protocol lending strategy
"""

import numpy as np
from typing import Dict, Tuple, Union, Optional


class PositionCalculator:
    """Calculate recursive position sizes and net APR"""
    
    def __init__(self, liquidation_distance: float = 0.30):
        """
        Initialize the position calculator

        Args:
            liquidation_distance: Minimum safety buffer as decimal (0.20 = 20% minimum)
                                This is the minimum protection guaranteed on the lending side.
                                Internally transformed to liq_max = liq_dist / (1 - liq_dist)
                                to ensure proper protection using existing formulas.
        """
        # Store original user input for display/reporting purposes
        self.liq_dist_input = liquidation_distance

        # Transform user's minimum liquidation distance to liq_max for internal use
        # This ensures the user gets AT LEAST their requested protection on lending side
        # Formula: liq_max = liq_dist / (1 - liq_dist)
        # Example: 0.20 → 0.25, which gives 20% lending protection and 25% borrowing protection
        self.liq_dist = liquidation_distance / (1 - liquidation_distance)
    
    def calculate_positions(
        self,
        liquidation_threshold_a: float,
        liquidation_threshold_b: float,
        collateral_ratio_a: float,
        collateral_ratio_b: float,
        borrow_weight_a: float = 1.0,
        borrow_weight_b: float = 1.0,
        protocol_a: Optional[str] = None,
        protocol_b: Optional[str] = None,
        token1: Optional[str] = None,
        token2: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Calculate recursive position sizes that converge to steady state

        The strategy (MARKET NEUTRAL - token1 must be a stablecoin):
        1. Lend l_a(0) = 1.0 of token1 (STABLECOIN) in Protocol A
        2. Borrow b_a(0) = l_a * r_A of token2 (HIGH-YIELD TOKEN) from Protocol A
        3. Lend l_b(0) = b_a of token2 (HIGH-YIELD TOKEN) in Protocol B
        4. Borrow b_b(0) = l_b * r_B of token1 (STABLECOIN) from Protocol B
        5. Deposit b_b as l_a(1) back into Protocol A
        6. Repeat infinitely...

        By starting with a stablecoin lend, you remain market neutral with no
        directional price exposure to the high-yield token.

        Args:
            liquidation_threshold_a: Liquidation LTV for Protocol A (e.g., 0.75 for 75%)
            liquidation_threshold_b: Liquidation LTV for Protocol B (e.g., 0.80 for 80%)
            collateral_ratio_a: Max LTV for Protocol A (e.g., 0.70 for 70%)
            collateral_ratio_b: Max LTV for Protocol B (e.g., 0.75 for 75%)
            borrow_weight_a: Borrow weight multiplier for token2 (default 1.0)
            borrow_weight_b: Borrow weight multiplier for token3 (default 1.0)

        Returns:
            Dictionary with position sizes: {l_a, b_a, l_b, b_b}
        """
        # Use liquidation threshold instead of collateral ratio with safety buffer AND borrow weights
        # Borrow weight reduces effective collateral (higher weight = less borrowing capacity)
        r_A = (liquidation_threshold_a / borrow_weight_a) / (1 + self.liq_dist)
        r_B = (liquidation_threshold_b / borrow_weight_b) / (1 + self.liq_dist)

        # Geometric series convergence
        # l_a = 1 + r_A*r_B + (r_A*r_B)^2 + ... = 1 / (1 - r_A*r_B)
        l_a = 1.0 / (1.0 - r_A * r_B)
        b_a = l_a * r_A
        l_b = b_a  # All borrowed token2 is lent in Protocol B
        b_b = l_b * r_B

        # Calculate effective LTV (on-the-fly, not stored in return dict)
        effective_ltv_A = (b_a / l_a) * borrow_weight_a
        effective_ltv_B = (b_b / l_b) * borrow_weight_b

        # AUTO-ADJUSTMENT: Bring effective LTV down to 99.5% of maxCF if exceeded
        adjusted_A = False
        adjusted_B = False

        # Build context strings for debug messages
        context_A = f" [{protocol_a} - Lend {token1}]" if protocol_a and token1 else ""
        context_B = f" [{protocol_b} - Lend {token2}]" if protocol_b and token2 else ""

        if effective_ltv_A > collateral_ratio_a:
            print(f"⚠️  Adjusting r_A{context_A}: effective_LTV_A ({effective_ltv_A:.4f}) > maxCF_A ({collateral_ratio_a:.4f})")
            print(f"   Setting effective_LTV_A = {collateral_ratio_a * 0.995:.4f} (99.5% of maxCF)")
            r_A = (collateral_ratio_a * 0.995) / borrow_weight_a
            adjusted_A = True

        if effective_ltv_B > collateral_ratio_b:
            print(f"⚠️  Adjusting r_B{context_B}: effective_LTV_B ({effective_ltv_B:.4f}) > maxCF_B ({collateral_ratio_b:.4f})")
            print(f"   Setting effective_LTV_B = {collateral_ratio_b * 0.995:.4f} (99.5% of maxCF)")
            r_B = (collateral_ratio_b * 0.995) / borrow_weight_b
            adjusted_B = True

        # Recalculate positions if any adjustment was made
        if adjusted_A or adjusted_B:
            l_a = 1.0 / (1.0 - r_A * r_B)
            b_a = l_a * r_A
            l_b = b_a
            b_b = l_b * r_B

            # Recalculate effective LTV for verification and print only for adjusted parameters
            effective_ltv_A = (b_a / l_a) * borrow_weight_a
            effective_ltv_B = (b_b / l_b) * borrow_weight_b

            if adjusted_A:
                print(f"✓ Adjusted{context_A}: effective_LTV_A = {effective_ltv_A:.4f} (vs maxCF {collateral_ratio_a:.4f})")
            if adjusted_B:
                print(f"✓ Adjusted{context_B}: effective_LTV_B = {effective_ltv_B:.4f} (vs maxCF {collateral_ratio_b:.4f})")

        return {
            'l_a': l_a,  # Total lent token1 in Protocol A
            'b_a': b_a,  # Total borrowed token2 from Protocol A
            'l_b': l_b,  # Total lent token2 in Protocol B
            'b_b': b_b,  # Total borrowed token1 from Protocol B
            'r_A': r_A,  # Effective ratio for Protocol A
            'r_B': r_B,  # Effective ratio for Protocol B
            'liquidation_threshold_a': liquidation_threshold_a,  # Store for reference
            'liquidation_threshold_b': liquidation_threshold_b,  # Store for reference
            'collateral_ratio_a': collateral_ratio_a,  # Store for reference
            'collateral_ratio_b': collateral_ratio_b,  # Store for reference
            'borrow_weight_a': borrow_weight_a,  # Borrow weight for token2
            'borrow_weight_b': borrow_weight_b,  # Borrow weight for token3
            'liquidation_distance': self.liq_dist_input  # Original user input (for display)
        }
    
    def calculate_net_apr(
        self,
        positions: Dict[str, float],
        lend_rate_token1_A: float,
        borrow_rate_token2_A: float,
        lend_rate_token2_B: float,
        borrow_rate_token1_B: float,
        borrow_fee_2A: float = 0.0,
        borrow_fee_3B: float = 0.0
    ) -> float:
        """
        Calculate the net APR for the strategy (after fees)

        Net APR = (earnings from lending) - (costs from borrowing) - (borrow fees)

        Args:
            positions: Dictionary with l_a, b_a, l_b, b_b
            lend_rate_token1_A: Lending APY for token1 in Protocol A (as decimal)
            borrow_rate_token2_A: Borrow APY for token2 in Protocol A (as decimal)
            lend_rate_token2_B: Lending APY for token2 in Protocol B (as decimal)
            borrow_rate_token1_B: Borrow APY for token1 in Protocol B (as decimal)
            borrow_fee_2A: Borrow fee for token2 from Protocol A (as decimal, annualized)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (as decimal, annualized)

        Returns:
            Net APR as decimal (after fees)
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']
        b_b = positions['b_b']

        # Earnings from lending
        earn_A = l_a * lend_rate_token1_A
        earn_B = l_b * lend_rate_token2_B

        # Costs from borrowing (rates only)
        cost_A = b_a * borrow_rate_token2_A
        cost_B = b_b * borrow_rate_token1_B

        # Gross APR (as decimal, before fees)
        gross_apr = earn_A + earn_B - cost_A - cost_B

        # Fee costs (annualized)
        fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B

        # Net APR (after fees)
        net_apr = gross_apr - fee_cost

        return net_apr

    def calculate_apr_for_days(
        self,
        net_apr: float,
        b_a: float,
        b_b: float,
        borrow_fee_2A: float,
        borrow_fee_3B: float,
        days: int
    ) -> float:
        """
        Calculate time-adjusted APR for a given holding period

        Args:
            net_apr: Base APR without fees (decimal)
            b_a: Borrow amount from Protocol A (position multiplier)
            b_b: Borrow amount from Protocol B (position multiplier)
            borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)
            days: Holding period in days

        Returns:
            Time-adjusted APR accounting for upfront fees (decimal)

        Formula:
            APRx = net_apr - (b_a × f_2A + b_b × f_3B) × 365 / days
        """
        # Total fee cost (decimal)
        total_fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B

        # Time-adjusted fee impact (annualized, as decimal)
        fee_impact = total_fee_cost * 365 / days

        return net_apr - fee_impact

    def calculate_days_to_breakeven(
        self,
        gross_apr: float,
        b_a: float,
        b_b: float,
        borrow_fee_2A: float,
        borrow_fee_3B: float
    ) -> float:
        """
        Calculate days until upfront borrow fees are recovered by gross APR

        Breakeven occurs when:
            gross_apr = (total_fees × 365) / days

        Solving for days:
            days = (total_fees × 365) / gross_apr

        Args:
            gross_apr: Gross APR before fees (decimal, e.g., 0.05 for 5%)
            b_a: Borrow multiplier from Protocol A
            b_b: Borrow multiplier from Protocol B
            borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)

        Returns:
            Days to breakeven as float. Returns special values:
            - 0.0 if fees are zero (instant breakeven)
            - float('inf') if gross_apr <= 0 (never breaks even)

        Edge Cases:
            - Zero fees: Returns 0.0 (instant breakeven)
            - Negative gross_apr: Returns float('inf') (never profitable)
            - Zero gross_apr: Returns float('inf') (never breaks even)
        """
        # Total upfront fees (decimal)
        total_fees = b_a * borrow_fee_2A + b_b * borrow_fee_3B

        # Edge case 1: No fees means instant breakeven
        if total_fees == 0:
            return 0.0

        # Edge case 2: Non-positive gross APR means never breaks even
        if gross_apr <= 0:
            return float('inf')

        # Calculate breakeven days
        days_to_breakeven = total_fees / (gross_apr/365)

        return days_to_breakeven

    def calculate_liquidation_price(
        self,
        collateral_value: float,
        loan_value: float,
        lending_token_price: float,
        borrowing_token_price: float,
        lltv: float,
        side: str,
        borrow_weight: float = 1.0
    ) -> Dict[str, Union[float, str]]:
        """
        Calculate the token price at which a position would be liquidated.

        This function solves for the price movement required to trigger liquidation
        by calculating when LTV equals LLTV. It can calculate from either the
        lending perspective (price drop) or borrowing perspective (price rise).

        Args:
            collateral_value: Total USD value of collateral position
            loan_value: Total USD value of borrowed position
            lending_token_price: Current price of lending/collateral token (USD)
            borrowing_token_price: Current price of borrowing/loan token (USD)
            lltv: Liquidation Loan-to-Value ratio as decimal (e.g., 0.75 for 75%)
            side: Calculate for 'lending' price drop or 'borrowing' price rise

        Returns:
            Dictionary with liquidation analysis:
                - liq_price: Liquidation price (0.0 if already liquidated, inf if impossible)
                - current_price: Current price of the queried token
                - pct_distance: Percentage price change to liquidation (negative = down, positive = up)
                - current_ltv: Current LTV ratio
                - lltv: Liquidation LTV threshold
                - direction: 'up', 'down', 'liquidated', or 'impossible'

        Raises:
            ValueError: If side is not 'lending' or 'borrowing'
            ValueError: If lltv is not positive
            ValueError: If token prices are not positive

        Examples:
            >>> calc = PositionCalculator()
            >>> # Calculate lending side liquidation price
            >>> result = calc.calculate_liquidation_price(
            ...     collateral_value=100.0,
            ...     loan_value=50.0,
            ...     lending_token_price=1.0,
            ...     borrowing_token_price=1.0,
            ...     lltv=0.75,
            ...     side='lending'
            ... )
            >>> print(f"Liquidation at ${result['liq_price']:.2f}")
            Liquidation at $0.67
            >>> print(f"Distance: {result['pct_distance']*100:.1f}%")
            Distance: -33.3%
        """
        # Input validation
        if side not in ['lending', 'borrowing']:
            raise ValueError(f"side must be 'lending' or 'borrowing', got '{side}'")

        if lending_token_price <= 0 or borrowing_token_price <= 0:
            raise ValueError("Token prices must be positive")

        # Calculate current LTV (including borrow weight)
        if collateral_value <= 0:
            current_ltv = float('inf')
        else:
            current_ltv = (loan_value * borrow_weight) / collateral_value

        # Determine current price based on side
        current_price = lending_token_price if side == 'lending' else borrowing_token_price

        # Special case: LLTV = 0 means asset cannot be used as collateral
        # Any position would be immediately liquidated
        if lltv <= 0:
            return {
                'liq_price': 0.0,
                'current_price': current_price,
                'pct_distance': -1.0,
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'liquidated'
            }

        # Check for edge case: zero or negative values
        if collateral_value <= 0 or loan_value <= 0:
            return {
                'liq_price': float('inf'),
                'current_price': current_price,
                'pct_distance': float('inf'),
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'impossible'
            }

        # Check if already liquidated
        if current_ltv >= lltv:
            return {
                'liq_price': 0.0,
                'current_price': current_price,
                'pct_distance': -1.0,
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'liquidated'
            }

        # Calculate liquidation price based on side
        if side == 'lending':
            # Lending token price must fall for liquidation
            # liq_price = lending_token_price * (current_ltv / lltv)
            liq_price = lending_token_price * (current_ltv / lltv)
            direction = 'down'  # Price must go down to trigger liquidation

        else:  # side == 'borrowing'
            # Borrowing token price must rise for liquidation
            # liq_price = borrowing_token_price * (lltv / current_ltv)
            liq_price = borrowing_token_price * (lltv / current_ltv)
            direction = 'up'  # Price must go up to trigger liquidation

        # Check for impossible liquidation (negative price)
        if liq_price <= 0:
            return {
                'liq_price': float('inf'),
                'current_price': current_price,
                'pct_distance': float('inf'),
                'current_ltv': current_ltv,
                'lltv': lltv,
                'direction': 'impossible'
            }

        # Calculate percentage distance
        pct_distance = (liq_price - current_price) / current_price

        return {
            'liq_price': liq_price,
            'current_price': current_price,
            'pct_distance': pct_distance,
            'current_ltv': current_ltv,
            'lltv': lltv,
            'direction': direction
        }

    def calculate_fee_adjusted_aprs(
        self,
        gross_apr: float,
        positions: Dict,
        borrow_fee_2A: float,
        borrow_fee_3B: float
    ) -> Dict[str, float]:
        """
        Calculate fee-adjusted APR metrics for multiple time horizons

        Args:
            gross_apr: Base APR before fees (decimal)
            positions: Dict with l_a, b_a, l_b, b_b
            borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)

        Returns:
            Dictionary with apr_net, apr5, apr30, apr90 (all as decimals)
        """
        b_a = positions['b_a']
        b_b = positions['b_b']

        # Total annualized fee cost (decimal)
        total_fee_cost = b_a * borrow_fee_2A + b_b * borrow_fee_3B

        # APR(net) = APR - annualized fees (equivalent to 365-day APR)
        apr_net = gross_apr - total_fee_cost

        # Time-adjusted APRs using helper function
        apr5 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 5)
        apr30 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 30)
        apr90 = self.calculate_apr_for_days(gross_apr, b_a, b_b, borrow_fee_2A, borrow_fee_3B, 90)

        # Calculate days to breakeven
        days_to_breakeven = self.calculate_days_to_breakeven(
            gross_apr,
            b_a,
            b_b,
            borrow_fee_2A,
            borrow_fee_3B
        )

        return {
            'apr_net': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven
        }

    def analyze_strategy(
        self,
        token1: str,
        token2: str,
        token3: str,
        protocol_a: str,
        protocol_b: str,
        lend_rate_token1_A: float,
        borrow_rate_token2_A: float,
        lend_rate_token2_B: float,
        borrow_rate_token3_B: float,
        collateral_ratio_token1_A: float,
        collateral_ratio_token2_B: float,
        liquidation_threshold_token1_A: float,
        liquidation_threshold_token2_B: float,
        price_token1_A: float,
        price_token2_A: float,
        price_token2_B: float,
        price_token3_B: float,
        available_borrow_2A: float = None,
        available_borrow_3B: float = None,
        borrow_fee_2A: float = None,
        borrow_fee_3B: float = None,
        borrow_weight_2A: float = 1.0,
        borrow_weight_3B: float = 1.0
    ) -> Dict:
        """a
        Complete analysis of a strategy combination
        
        Args:
            token1: Stablecoin (starting lend to remain market neutral)
            token2: High-yield token (borrowed for yield generation)
            token3: Closing stablecoin (borrowed from Protocol B, converted to token1)
            protocol_a: First protocol
            protocol_b: Second protocol
            lend_rate_token1_A: Stablecoin lending rate in Protocol A
            borrow_rate_token2_A: High-yield token borrow rate from Protocol A
            lend_rate_token2_B: High-yield token lending rate in Protocol B
            borrow_rate_token3_B: Closing stablecoin borrow rate from Protocol B
            collateral_ratio_token1_A: Stablecoin collateral ratio in Protocol A
            collateral_ratio_token2_B: High-yield token collateral ratio in Protocol B
            price_token1_A: Token1 price in Protocol A
            price_token2_A: Token2 price in Protocol A
            price_token2_B: Token2 price in Protocol B
            price_token3_B: Token3 price in Protocol B
        
        Returns:
            Dictionary with all strategy details
        """
        try:
            # Calculate position sizes
            positions = self.calculate_positions(
                liquidation_threshold_token1_A,
                liquidation_threshold_token2_B,
                collateral_ratio_token1_A,
                collateral_ratio_token2_B,
                borrow_weight_2A,
                borrow_weight_3B,
                protocol_a=protocol_a,
                protocol_b=protocol_b,
                token1=token1,
                token2=token2
            )

            # Calculate max deployable size based on liquidity constraints
            max_size = None
            if available_borrow_2A is not None and available_borrow_3B is not None:
                b_a = positions['b_a']  # Borrow multiplier for token2 on protocol A
                b_b = positions['b_b']  # Borrow multiplier for token3 on protocol B

                # Calculate max size for each constraint
                if b_a > 0:
                    max_size_constraint_2A = available_borrow_2A / b_a
                else:
                    max_size_constraint_2A = float('inf')

                if b_b > 0:
                    max_size_constraint_3B = available_borrow_3B / b_b
                else:
                    max_size_constraint_3B = float('inf')

                # Take the minimum (most restrictive constraint)
                max_size = min(max_size_constraint_2A, max_size_constraint_3B)

            # Calculate net APR (levered, after fees)
            # Note: token3 is converted 1:1 to token1, so we use token3's borrow rate
            net_apr = self.calculate_net_apr(
                positions,
                lend_rate_token1_A,
                borrow_rate_token2_A,
                lend_rate_token2_B,
                borrow_rate_token3_B,  # Changed: use token3 borrow rate
                borrow_fee_2A if borrow_fee_2A is not None else 0.0,
                borrow_fee_3B if borrow_fee_3B is not None else 0.0
            )

            # Calculate fee-adjusted APRs for different time horizons (5, 30, 90 days)
            # Note: net_apr already includes fees, so we need to back out fees and recalculate for different time periods
            # For now, calculate based on gross APR
            gross_apr = net_apr + (positions['b_a'] * (borrow_fee_2A if borrow_fee_2A is not None else 0.0) +
                                   positions['b_b'] * (borrow_fee_3B if borrow_fee_3B is not None else 0.0))

            fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(
                gross_apr,
                positions,
                borrow_fee_2A if borrow_fee_2A is not None else 0.0,
                borrow_fee_3B if borrow_fee_3B is not None else 0.0
            )

            # Calculate token amounts per $100 notional
            T1_A = (positions['l_a'] / price_token1_A) * 100
            T2_A = (positions['b_a'] / price_token2_A) * 100
            T2_B = T2_A  # Same amount of token2
            T3_B = (positions['b_b'] / price_token3_B) * 100
            return {
                'token1': token1,
                'token2': token2,
                'token3': token3,  # NEW: Track closing stablecoin
                'protocol_a': protocol_a,
                'protocol_b': protocol_b,
                'net_apr': net_apr,  # As decimal
                'apr_net': fee_adjusted_aprs['apr_net'],  # As decimal
                'apr5': fee_adjusted_aprs['apr5'],  # As decimal
                'apr30': fee_adjusted_aprs['apr30'],  # As decimal
                'apr90': fee_adjusted_aprs['apr90'],  # As decimal
                'days_to_breakeven': fee_adjusted_aprs['days_to_breakeven'],  # As float (days)
                'liquidation_distance': positions['liquidation_distance'],  # As decimal
                'l_a': positions['l_a'],
                'b_a': positions['b_a'],
                'l_b': positions['l_b'],
                'b_b': positions['b_b'],
                'lend_rate_1a': lend_rate_token1_A,  # As decimal
                'borrow_rate_2a': borrow_rate_token2_A,  # As decimal
                'lend_rate_2b': lend_rate_token2_B,  # As decimal
                'borrow_rate_3b': borrow_rate_token3_B,  # As decimal
                'collateral_ratio_1a': collateral_ratio_token1_A,
                'collateral_ratio_2b': collateral_ratio_token2_B,
                'liquidation_threshold_1a': liquidation_threshold_token1_A,
                'liquidation_threshold_2b': liquidation_threshold_token2_B,
                'P1_A': price_token1_A,
                'P2_A': price_token2_A,
                'P2_B': price_token2_B,
                'P3_B': price_token3_B,
                'T1_A': T1_A,
                'T2_A': T2_A,
                'T2_B': T2_B,
                'T3_B': T3_B,
                'available_borrow_2a': available_borrow_2A,
                'available_borrow_3b': available_borrow_3B,
                'max_size': max_size,
                'borrow_fee_2a': borrow_fee_2A if borrow_fee_2A is not None else 0.0,  # Default to 0
                'borrow_fee_3b': borrow_fee_3B if borrow_fee_3B is not None else 0.0,  # Default to 0
                'borrow_weight_2a': borrow_weight_2A,
                'borrow_weight_3b': borrow_weight_3B,
                'valid': True,
                'error': None
            }
            
        except ValueError as e:
            return {
                'token1': token1,
                'token2': token2,
                'token3': token3,  # Include token3 in error case too
                'protocol_a': protocol_a,
                'protocol_b': protocol_b,
                'net_apr': None,
                'liquidation_distance': None,
                'valid': False,
                'error': str(e)
            }


# Example usage
# Example usage
if __name__ == "__main__":
    import pandas as pd
    #from data.navi.navi_reader import NaviReader
    #from data.suilend.suilend_reader import SuilendReader, SuilendReaderConfig
    
    # Hardcoded example tokens/protocols
    token1 = 'USDY'
    token2 = 'DEEP'
    token3 = 'AUSD'
    protocol_a = 'Navi'
    protocol_b = 'Suilend'
    
    lend_rate_1A = 0.05027
    borrow_rate_2A = 0.1486
    collateral_1A = 0.7
    liquidation_threshold_1A = 0.75  # Must be > collateral_1A (liquidation occurs at higher LTV)
    price_1A = 1.116726
    price_2A = 0.04458
    
    # Get rates from Protocol B (Suilend)
    lend_rate_2B = 0.25906
    borrow_rate_3B = 0.5
    collateral_2B = 0.3
    liquidation_threshold_2B = 0.35  # Must be > collateral_2B (liquidation occurs at higher LTV)
    price_2B = 0.04454
    price_3B = 1.11681
    
    print(f"Example: Lend {token1} in {protocol_a}, Borrow {token2}, Lend {token2} in {protocol_b}, Borrow {token3}")
    print("="*80)
    print("\nFetching data from protocols...")
    
    # Check if all data is available
    if None in [lend_rate_1A, borrow_rate_2A, lend_rate_2B, borrow_rate_3B,
                collateral_1A, collateral_2B, liquidation_threshold_1A, liquidation_threshold_2B,
                price_1A, price_2A, price_2B, price_3B]:
        print("❌ Error: Missing data for this token/protocol combination")
        print(f"   {token1} in {protocol_a}: lend={lend_rate_1A}, collateral={collateral_1A}, lltv={liquidation_threshold_1A}, price={price_1A}")
        print(f"   {token2} in {protocol_a}: borrow={borrow_rate_2A}, price={price_2A}")
        print(f"   {token2} in {protocol_b}: lend={lend_rate_2B}, collateral={collateral_2B}, lltv={liquidation_threshold_2B}, price={price_2B}")
        print(f"   {token3} in {protocol_b}: borrow={borrow_rate_3B}, price={price_3B}")
        import sys
        sys.exit(1)
    
    # Run analysis
    calc = PositionCalculator(liquidation_distance=0.30)
    
    result = calc.analyze_strategy(
        token1=token1,
        token2=token2,
        token3=token3,
        protocol_a=protocol_a,
        protocol_b=protocol_b,
        lend_rate_token1_A=lend_rate_1A,
        borrow_rate_token2_A=borrow_rate_2A,
        lend_rate_token2_B=lend_rate_2B,
        borrow_rate_token3_B=borrow_rate_3B,
        collateral_ratio_token1_A=collateral_1A,
        collateral_ratio_token2_B=collateral_2B,
        liquidation_threshold_token1_A=liquidation_threshold_1A,
        liquidation_threshold_token2_B=liquidation_threshold_2B,
        price_token1_A=price_1A,
        price_token2_A=price_2A,
        price_token2_B=price_2B,
        price_token3_B=price_3B
    )
    
    if not result['valid']:
        print(f"❌ Strategy not valid: {result['error']}")
        import sys
        sys.exit(1)
    
    print(f"\n✓ Strategy is valid!")
    print(f"\nPosition Sizes:")
    print(f"  l_a ({token1} lent in {protocol_a}):     ${result['l_a']:.4f} = {result['T1_A']:.2f} {token1} @ ${result['P1_A']:.4f}")
    print(f"  b_a ({token2} borrowed from {protocol_a}): ${result['b_a']:.4f} = {result['T2_A']:.2f} {token2} @ ${result['P2_A']:.4f}")
    print(f"  l_b ({token2} lent in {protocol_b}):  ${result['l_b']:.4f} = {result['T2_B']:.2f} {token2} @ ${result['P2_B']:.4f}")
    print(f"  b_b ({token3} borrowed from {protocol_b}): ${result['b_b']:.4f} = {result['T3_B']:.2f} {token3} @ ${result['P3_B']:.4f}")
    print(f"  Liquidation Distance: {result['liquidation_distance'] * 100:.0f}%")

    print(f"\nNet APR: {result['net_apr'] * 100:.2f}%")