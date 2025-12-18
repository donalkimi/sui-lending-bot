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
        
        # Check if the loop converges (r_A * r_B must be < 1)
        if r_A * r_B >= 1.0:
            raise ValueError(
                f"Position does not converge! r_A * r_B = {r_A * r_B:.4f} >= 1.0\n"
                f"Reduce liquidation distance or use protocols with lower LTV ratios."
            )
        
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
        borrow_rate_token1_B: float
    ) -> float:
        """
        Calculate the net APR for the strategy
        
        Net APR = (earnings from lending) - (costs from borrowing)
        
        Args:
            positions: Dictionary with L_A, B_A, L_B, B_B
            lend_rate_token1_A: Lending APY for token1 in Protocol A (as decimal)
            borrow_rate_token2_A: Borrow APY for token2 in Protocol A (as decimal)
            lend_rate_token2_B: Lending APY for token2 in Protocol B (as decimal)
            borrow_rate_token1_B: Borrow APY for token1 in Protocol B (as decimal)
            
        Returns:
            Net APR as percentage
        """
        L_A = positions['L_A']
        B_A = positions['B_A']
        L_B = positions['L_B']
        B_B = positions['B_B']
        
        # Earnings from lending
        earn_A = L_A * lend_rate_token1_A
        earn_B = L_B * lend_rate_token2_B
        
        # Costs from borrowing
        cost_A = B_A * borrow_rate_token2_A
        cost_B = B_B * borrow_rate_token1_B
        
        # Net APR
        net_apr = (earn_A + earn_B - cost_A - cost_B) * 100  # Convert to percentage
        
        return net_apr
    
    def analyze_strategy(
        self,
        token1: str,
        token2: str,
        protocol_A: str,
        protocol_B: str,
        lend_rate_token1_A: float,
        borrow_rate_token2_A: float,
        lend_rate_token2_B: float,
        borrow_rate_token1_B: float,
        collateral_ratio_token1_A: float,
        collateral_ratio_token2_B: float
    ) -> Dict:
        """
        Complete analysis of a strategy combination
        
        Args:
            token1: Stablecoin (starting lend to remain market neutral)
            token2: High-yield token (borrowed for yield generation)
            protocol_A: First protocol
            protocol_B: Second protocol
            lend_rate_token1_A: Stablecoin lending rate in Protocol A
            borrow_rate_token2_A: High-yield token borrow rate from Protocol A
            lend_rate_token2_B: High-yield token lending rate in Protocol B
            borrow_rate_token1_B: Stablecoin borrow rate from Protocol B
            collateral_ratio_token1_A: Stablecoin collateral ratio in Protocol A
            collateral_ratio_token2_B: High-yield token collateral ratio in Protocol B
        
        Returns:
            Dictionary with all strategy details
        """
        try:
            # Calculate position sizes
            positions = self.calculate_positions(
                collateral_ratio_token1_A,
                collateral_ratio_token2_B
            )
            
            # Calculate net APR
            net_apr = self.calculate_net_apr(
                positions,
                lend_rate_token1_A,
                borrow_rate_token2_A,
                lend_rate_token2_B,
                borrow_rate_token1_B
            )
            
            return {
                'token1': token1,
                'token2': token2,
                'protocol_A': protocol_A,
                'protocol_B': protocol_B,
                'net_apr': net_apr,
                'liquidation_distance': positions['liquidation_distance'] * 100,  # Convert to percentage
                'L_A': positions['L_A'],
                'B_A': positions['B_A'],
                'L_B': positions['L_B'],
                'B_B': positions['B_B'],
                'lend_rate_1A': lend_rate_token1_A * 100,
                'borrow_rate_2A': borrow_rate_token2_A * 100,
                'lend_rate_2B': lend_rate_token2_B * 100,
                'borrow_rate_1B': borrow_rate_token1_B * 100,
                'valid': True,
                'error': None
            }
            
        except ValueError as e:
            return {
                'token1': token1,
                'token2': token2,
                'protocol_A': protocol_A,
                'protocol_B': protocol_B,
                'net_apr': None,
                'liquidation_distance': None,
                'valid': False,
                'error': str(e)
            }


# Example usage
if __name__ == "__main__":
    calc = PositionCalculator(liquidation_distance=0.30)
    
    # Example from your screenshot: USDY in NAVI, DEEP in SuiLend
    print("Example: Lend USDY in NAVI, Borrow DEEP, Lend DEEP in SuiLend, Borrow USDY")
    print("="*80)
    
    positions = calc.calculate_positions(
        collateral_ratio_A=0.75,  # NAVI allows 75% LTV
        collateral_ratio_B=0.19   # SuiLend allows 19% LTV for DEEP
    )
    
    print(f"\nPosition Sizes:")
    print(f"  L_A (USDY lent in NAVI):     {positions['L_A']:.4f}")
    print(f"  B_A (DEEP borrowed from NAVI): {positions['B_A']:.4f}")
    print(f"  L_B (DEEP lent in SuiLend):  {positions['L_B']:.4f}")
    print(f"  B_B (USDY borrowed from SuiLend): {positions['B_B']:.4f}")
    print(f"  Liquidation Distance: {positions['liquidation_distance']*100:.0f}%")
    
    net_apr = calc.calculate_net_apr(
        positions,
        lend_rate_token1_A=0.097,    # 9.7% USDY lending in NAVI
        borrow_rate_token2_A=0.1950,  # 19.5% DEEP borrowing from NAVI
        lend_rate_token2_B=0.31,      # 31% DEEP lending in SuiLend
        borrow_rate_token1_B=0.059    # 5.9% USDY borrowing from SuiLend
    )
    
    print(f"\nNet APR: {net_apr:.2f}%")
