"""
Position size calculator for recursive cross-protocol lending strategy
"""

import numpy as np
from typing import Dict, Tuple


class PositionCalculator:
    """Calculate recursive position sizes and net APR"""
    
    def __init__(self, liquidation_distance: float = 0.30):
        """
        Initialize the position calculator
        
        Args:
            liquidation_distance: Safety buffer as decimal (0.30 = 30%)
        """
        self.liq_dist = liquidation_distance
    
    def calculate_positions(
        self, 
        collateral_ratio_A: float,
        collateral_ratio_B: float
    ) -> Dict[str, float]:
        """
        Calculate recursive position sizes that converge to steady state
        
        The strategy (MARKET NEUTRAL - token1 must be a stablecoin):
        1. Lend L_A(0) = 1.0 of token1 (STABLECOIN) in Protocol A
        2. Borrow B_A(0) = L_A * r_A of token2 (HIGH-YIELD TOKEN) from Protocol A
        3. Lend L_B(0) = B_A of token2 (HIGH-YIELD TOKEN) in Protocol B
        4. Borrow B_B(0) = L_B * r_B of token1 (STABLECOIN) from Protocol B
        5. Deposit B_B as L_A(1) back into Protocol A
        6. Repeat infinitely...
        
        By starting with a stablecoin lend, you remain market neutral with no
        directional price exposure to the high-yield token.
        
        Args:
            collateral_ratio_A: Max LTV for Protocol A (e.g., 0.75 for 75%)
            collateral_ratio_B: Max LTV for Protocol B (e.g., 0.80 for 80%)
            
        Returns:
            Dictionary with position sizes: {L_A, B_A, L_B, B_B}
        """
        # Adjusted collateral ratios with safety buffer
        r_A = collateral_ratio_A / (1 + self.liq_dist)
        r_B = collateral_ratio_B / (1 + self.liq_dist)

        # Geometric series convergence
        # L_A = 1 + r_A*r_B + (r_A*r_B)^2 + ... = 1 / (1 - r_A*r_B)
        L_A = 1.0 / (1.0 - r_A * r_B)
        B_A = L_A * r_A
        L_B = B_A  # All borrowed token2 is lent in Protocol B
        B_B = L_B * r_B
        
        return {
            'L_A': L_A,  # Total lent token1 in Protocol A
            'B_A': B_A,  # Total borrowed token2 from Protocol A
            'L_B': L_B,  # Total lent token2 in Protocol B
            'B_B': B_B,  # Total borrowed token1 from Protocol B
            'r_A': r_A,  # Effective ratio for Protocol A
            'r_B': r_B,  # Effective ratio for Protocol B
            'liquidation_distance': self.liq_dist  # Safety buffer from liquidation
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
            positions: Dictionary with L_A, B_A, L_B, B_B
            lend_rate_token1_A: Lending APY for token1 in Protocol A (as decimal)
            borrow_rate_token2_A: Borrow APY for token2 in Protocol A (as decimal)
            lend_rate_token2_B: Lending APY for token2 in Protocol B (as decimal)
            borrow_rate_token1_B: Borrow APY for token1 in Protocol B (as decimal)
            borrow_fee_2A: Borrow fee for token2 from Protocol A (as decimal, annualized)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (as decimal, annualized)

        Returns:
            Net APR as decimal (after fees)
        """
        L_A = positions['L_A']
        B_A = positions['B_A']
        L_B = positions['L_B']
        B_B = positions['B_B']

        # Earnings from lending
        earn_A = L_A * lend_rate_token1_A
        earn_B = L_B * lend_rate_token2_B

        # Costs from borrowing (rates only)
        cost_A = B_A * borrow_rate_token2_A
        cost_B = B_B * borrow_rate_token1_B

        # Gross APR (as decimal, before fees)
        gross_apr = earn_A + earn_B - cost_A - cost_B

        # Fee costs (annualized)
        fee_cost = B_A * borrow_fee_2A + B_B * borrow_fee_3B

        # Net APR (after fees)
        net_apr = gross_apr - fee_cost

        return net_apr

    def calculate_apr_for_days(
        self,
        net_apr: float,
        B_A: float,
        B_B: float,
        borrow_fee_2A: float,
        borrow_fee_3B: float,
        days: int
    ) -> float:
        """
        Calculate time-adjusted APR for a given holding period

        Args:
            net_apr: Base APR without fees (decimal)
            B_A: Borrow amount from Protocol A (position multiplier)
            B_B: Borrow amount from Protocol B (position multiplier)
            borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)
            days: Holding period in days

        Returns:
            Time-adjusted APR accounting for upfront fees (decimal)

        Formula:
            APRx = net_apr - (B_A × f_2A + B_B × f_3B) × 365 / days
        """
        # Total fee cost (decimal)
        total_fee_cost = B_A * borrow_fee_2A + B_B * borrow_fee_3B

        # Time-adjusted fee impact (annualized, as decimal)
        fee_impact = total_fee_cost * 365 / days

        return net_apr - fee_impact

    def calculate_days_to_breakeven(
        self,
        gross_apr: float,
        B_A: float,
        B_B: float,
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
            B_A: Borrow multiplier from Protocol A
            B_B: Borrow multiplier from Protocol B
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
        total_fees = B_A * borrow_fee_2A + B_B * borrow_fee_3B

        # Edge case 1: No fees means instant breakeven
        if total_fees == 0:
            return 0.0

        # Edge case 2: Non-positive gross APR means never breaks even
        if gross_apr <= 0:
            return float('inf')

        # Calculate breakeven days
        days_to_breakeven = total_fees / (gross_apr/365)

        return days_to_breakeven

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
            positions: Dict with L_A, B_A, L_B, B_B
            borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
            borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)

        Returns:
            Dictionary with apr_net, apr5, apr30, apr90 (all as decimals)
        """
        B_A = positions['B_A']
        B_B = positions['B_B']

        # Total annualized fee cost (decimal)
        total_fee_cost = B_A * borrow_fee_2A + B_B * borrow_fee_3B

        # APR(net) = APR - annualized fees (equivalent to 365-day APR)
        apr_net = gross_apr - total_fee_cost

        # Time-adjusted APRs using helper function
        apr5 = self.calculate_apr_for_days(gross_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 5)
        apr30 = self.calculate_apr_for_days(gross_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 30)
        apr90 = self.calculate_apr_for_days(gross_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 90)

        # Calculate days to breakeven
        days_to_breakeven = self.calculate_days_to_breakeven(
            gross_apr,
            B_A,
            B_B,
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
        protocol_A: str,
        protocol_B: str,
        lend_rate_token1_A: float,
        borrow_rate_token2_A: float,
        lend_rate_token2_B: float,
        borrow_rate_token3_B: float,
        collateral_ratio_token1_A: float,
        collateral_ratio_token2_B: float,
        price_token1_A: float,
        price_token2_A: float,
        price_token2_B: float,
        price_token3_B: float,
        available_borrow_2A: float = None,
        available_borrow_3B: float = None,
        borrow_fee_2A: float = None,  # NEW
        borrow_fee_3B: float = None   # NEW
    ) -> Dict:
        """
        Complete analysis of a strategy combination
        
        Args:
            token1: Stablecoin (starting lend to remain market neutral)
            token2: High-yield token (borrowed for yield generation)
            token3: Closing stablecoin (borrowed from Protocol B, converted to token1)
            protocol_A: First protocol
            protocol_B: Second protocol
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
                collateral_ratio_token1_A,
                collateral_ratio_token2_B
            )

            # Calculate max deployable size based on liquidity constraints
            max_size = None
            if available_borrow_2A is not None and available_borrow_3B is not None:
                B_A = positions['B_A']  # Borrow multiplier for token2 on protocol A
                B_B = positions['B_B']  # Borrow multiplier for token3 on protocol B

                # Calculate max size for each constraint
                if B_A > 0:
                    max_size_constraint_2A = available_borrow_2A / B_A
                else:
                    max_size_constraint_2A = float('inf')

                if B_B > 0:
                    max_size_constraint_3B = available_borrow_3B / B_B
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
            gross_apr = net_apr + (positions['B_A'] * (borrow_fee_2A if borrow_fee_2A is not None else 0.0) +
                                   positions['B_B'] * (borrow_fee_3B if borrow_fee_3B is not None else 0.0))

            fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(
                gross_apr,
                positions,
                borrow_fee_2A if borrow_fee_2A is not None else 0.0,
                borrow_fee_3B if borrow_fee_3B is not None else 0.0
            )

            # Calculate token amounts per $100 notional
            T1_A = (positions['L_A'] / price_token1_A) * 100
            T2_A = (positions['B_A'] / price_token2_A) * 100
            T2_B = T2_A  # Same amount of token2
            T3_B = (positions['B_B'] / price_token3_B) * 100
            return {
                'token1': token1,
                'token2': token2,
                'token3': token3,  # NEW: Track closing stablecoin
                'protocol_A': protocol_A,
                'protocol_B': protocol_B,
                'net_apr': net_apr,  # As decimal
                'apr_net': fee_adjusted_aprs['apr_net'],  # As decimal
                'apr5': fee_adjusted_aprs['apr5'],  # As decimal
                'apr30': fee_adjusted_aprs['apr30'],  # As decimal
                'apr90': fee_adjusted_aprs['apr90'],  # As decimal
                'days_to_breakeven': fee_adjusted_aprs['days_to_breakeven'],  # As float (days)
                'liquidation_distance': positions['liquidation_distance'],  # As decimal
                'L_A': positions['L_A'],
                'B_A': positions['B_A'],
                'L_B': positions['L_B'],
                'B_B': positions['B_B'],
                'lend_rate_1A': lend_rate_token1_A,  # As decimal
                'borrow_rate_2A': borrow_rate_token2_A,  # As decimal
                'lend_rate_2B': lend_rate_token2_B,  # As decimal
                'borrow_rate_3B': borrow_rate_token3_B,  # As decimal
                'collateral_ratio_1A': collateral_ratio_token1_A,
                'collateral_ratio_2B': collateral_ratio_token2_B,
                'P1_A': price_token1_A,
                'P2_A': price_token2_A,
                'P2_B': price_token2_B,
                'P3_B': price_token3_B,
                'T1_A': T1_A,
                'T2_A': T2_A,
                'T2_B': T2_B,
                'T3_B': T3_B,
                'available_borrow_2A': available_borrow_2A,
                'available_borrow_3B': available_borrow_3B,
                'max_size': max_size,
                'borrow_fee_2A': borrow_fee_2A if borrow_fee_2A is not None else 0.0,  # Default to 0
                'borrow_fee_3B': borrow_fee_3B if borrow_fee_3B is not None else 0.0,  # Default to 0
                'valid': True,
                'error': None
            }
            
        except ValueError as e:
            return {
                'token1': token1,
                'token2': token2,
                'token3': token3,  # Include token3 in error case too
                'protocol_A': protocol_A,
                'protocol_B': protocol_B,
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
    protocol_A = 'Navi'
    protocol_B = 'Suilend'
    
    lend_rate_1A = 0.05027
    borrow_rate_2A = 0.1486
    collateral_1A = 0.7
    price_1A = 1.116726
    price_2A = 0.04458
    
    # Get rates from Protocol B (Suilend)
    lend_rate_2B = 0.25906
    borrow_rate_3B = 0.5
    collateral_2B = 0.3
    price_2B = 0.04454
    price_3B = 1.11681
    
    print(f"Example: Lend {token1} in {protocol_A}, Borrow {token2}, Lend {token2} in {protocol_B}, Borrow {token3}")
    print("="*80)
    print("\nFetching data from protocols...")
    
    # Check if all data is available
    if None in [lend_rate_1A, borrow_rate_2A, lend_rate_2B, borrow_rate_3B, 
                collateral_1A, collateral_2B, price_1A, price_2A, price_2B, price_3B]:
        print("❌ Error: Missing data for this token/protocol combination")
        print(f"   {token1} in {protocol_A}: lend={lend_rate_1A}, collateral={collateral_1A}, price={price_1A}")
        print(f"   {token2} in {protocol_A}: borrow={borrow_rate_2A}, price={price_2A}")
        print(f"   {token2} in {protocol_B}: lend={lend_rate_2B}, collateral={collateral_2B}, price={price_2B}")
        print(f"   {token3} in {protocol_B}: borrow={borrow_rate_3B}, price={price_3B}")
        import sys
        sys.exit(1)
    
    # Run analysis
    calc = PositionCalculator(liquidation_distance=0.30)
    
    result = calc.analyze_strategy(
        token1=token1,
        token2=token2,
        token3=token3,
        protocol_A=protocol_A,
        protocol_B=protocol_B,
        lend_rate_token1_A=lend_rate_1A,
        borrow_rate_token2_A=borrow_rate_2A,
        lend_rate_token2_B=lend_rate_2B,
        borrow_rate_token3_B=borrow_rate_3B,
        collateral_ratio_token1_A=collateral_1A,
        collateral_ratio_token2_B=collateral_2B,
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
    print(f"  L_A ({token1} lent in {protocol_A}):     ${result['L_A']:.4f} = {result['T1_A']:.2f} {token1} @ ${result['P1_A']:.4f}")
    print(f"  B_A ({token2} borrowed from {protocol_A}): ${result['B_A']:.4f} = {result['T2_A']:.2f} {token2} @ ${result['P2_A']:.4f}")
    print(f"  L_B ({token2} lent in {protocol_B}):  ${result['L_B']:.4f} = {result['T2_B']:.2f} {token2} @ ${result['P2_B']:.4f}")
    print(f"  B_B ({token3} borrowed from {protocol_B}): ${result['B_B']:.4f} = {result['T3_B']:.2f} {token3} @ ${result['P3_B']:.4f}")
    print(f"  Liquidation Distance: {result['liquidation_distance'] * 100:.0f}%")

    print(f"\nNet APR: {result['net_apr'] * 100:.2f}%")