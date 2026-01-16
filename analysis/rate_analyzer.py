"""
Rate analyzer to find the best protocol pair and token combination
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from config.stablecoins import STABLECOIN_SYMBOLS
from analysis.position_calculator import PositionCalculator


class RateAnalyzer:
    """Analyze all protocol and token combinations to find the best strategy"""
    
    def __init__(
        self,
        lend_rates: pd.DataFrame,
        borrow_rates: pd.DataFrame,
        collateral_ratios: pd.DataFrame,
        prices: pd.DataFrame,                    # NEW
        lend_rewards: pd.DataFrame,              # NEW
        borrow_rewards: pd.DataFrame,            # NEW
        available_borrow: pd.DataFrame,          # NEW
        borrow_fees: pd.DataFrame,               # NEW
        timestamp: int,  # Unix timestamp in seconds
        liquidation_distance: Optional[float] = None
    ):
        """
        Initialize the rate analyzer

        Args:
            lend_rates: DataFrame with lending rates (tokens x protocols)
            borrow_rates: DataFrame with borrow rates (tokens x protocols)
            collateral_ratios: DataFrame with collateral ratios (tokens x protocols)
            prices: DataFrame with prices (tokens x protocols)                    # NEW
            lend_rewards: DataFrame with lend reward APRs (tokens x protocols)    # NEW
            borrow_rewards: DataFrame with borrow reward APRs (tokens x protocols) # NEW
            available_borrow: DataFrame with available borrow USD (tokens x protocols) # NEW
            borrow_fees: DataFrame with borrow fees (tokens x protocols)          # NEW
            timestamp: Unix timestamp in seconds (integer) - the "current" moment
            liquidation_distance: Safety buffer (default from settings)
        """
        self.lend_rates = lend_rates
        self.borrow_rates = borrow_rates
        self.collateral_ratios = collateral_ratios
        self.prices = prices                      # NEW
        self.lend_rewards = lend_rewards          # NEW
        self.borrow_rewards = borrow_rewards      # NEW
        self.available_borrow = available_borrow  # NEW
        self.borrow_fees = borrow_fees            # NEW
        self.liquidation_distance = liquidation_distance or settings.DEFAULT_LIQUIDATION_DISTANCE
        
        # Get list of protocols from column headers (excluding 'Token' and 'Contract' columns)
        non_protocol_cols = {'Token', 'Contract'}
        self.protocols = [col for col in lend_rates.columns if col not in non_protocol_cols]
        
        # Get all tokens from merged DataFrame
        all_tokens_in_df = lend_rates['Token'].dropna().unique().tolist()
        
        # Stablecoins from config
        self.STABLECOINS = STABLECOIN_SYMBOLS
        
        # OTHER_TOKENS = all tokens EXCEPT stablecoins
        self.OTHER_TOKENS = [token for token in all_tokens_in_df 
                             if token not in self.STABLECOINS]
        
        # ALL_TOKENS = all tokens in the merged data
        self.ALL_TOKENS = all_tokens_in_df
        
        # Initialize calculator
        self.calculator = PositionCalculator(self.liquidation_distance)

        # Store timestamp (when this data was captured) - must be int (seconds)
        if timestamp is None:
            raise ValueError("timestamp is required and must be explicitly provided")
        if not isinstance(timestamp, int):
            raise TypeError(f"timestamp must be int (Unix seconds), got {type(timestamp).__name__}")
        self.timestamp = timestamp
        
        print(f"\n🔧 Initialized Rate Analyzer:")
        print(f"   Protocols: {len(self.protocols)} ({', '.join(self.protocols)})")
        print(f"   Tokens: {len(self.ALL_TOKENS)} (Stablecoins: {len(self.STABLECOINS)}, High-Yield: {len(self.OTHER_TOKENS)})")
        print(f"   Stablecoins: {', '.join(sorted(self.STABLECOINS))}")
        print(f"   High-Yield Tokens: {', '.join(sorted(self.OTHER_TOKENS))}")
        print(f"   Liquidation Distance: {self.liquidation_distance*100:.0f}%")
    
    def get_rate(self, df: pd.DataFrame, token: str, protocol: str) -> float:
        """
        Safely get a rate from a dataframe
        
        Args:
            df: DataFrame with rates
            token: Token name
            protocol: Protocol name
            
        Returns:
            Rate as decimal, or np.nan if not found
        """
        # Set the first column as index if it isn't already
        if df.index.name != 'Token':
            df_indexed = df.set_index('Token')
        else:
            df_indexed = df
        
        try:
            # Get the rate
            if token in df_indexed.index and protocol in df_indexed.columns:
                rate = df_indexed.loc[token, protocol]
                return float(rate) if pd.notna(rate) else np.nan
            else:
                return np.nan
        except:
            return np.nan

    def get_price(self, token: str, protocol: str) -> float:
        """
        Safely get a price from the prices dataframe

        Args:
            token: Token name
            protocol: Protocol name

        Returns:
            Price as float, or np.nan if not found
        """
        # Set the first column as index if it isn't already
        if self.prices.index.name != 'Token':
            df_indexed = self.prices.set_index('Token')
        else:
            df_indexed = self.prices

        try:
            # Get the price
            if token in df_indexed.index and protocol in df_indexed.columns:
                price = df_indexed.loc[token, protocol]
                return float(price) if pd.notna(price) else np.nan
            else:
                return np.nan
        except:
            return np.nan

    def get_available_borrow(self, token: str, protocol: str) -> float:
        """
        Safely get available borrow USD from the available_borrow dataframe

        Args:
            token: Token name
            protocol: Protocol name

        Returns:
            Available borrow in USD, or np.nan if not found
        """
        # Set the first column as index if it isn't already
        if self.available_borrow.index.name != 'Token':
            df_indexed = self.available_borrow.set_index('Token')
        else:
            df_indexed = self.available_borrow

        try:
            # Get the available borrow
            if token in df_indexed.index and protocol in df_indexed.columns:
                value = df_indexed.loc[token, protocol]
                return float(value) if pd.notna(value) else np.nan
            else:
                return np.nan
        except:
            return np.nan

    def get_borrow_fee(self, token: str, protocol: str) -> float:
        """
        Safely get borrow fee from the borrow_fees dataframe

        Args:
            token: Token name
            protocol: Protocol name

        Returns:
            Borrow fee as decimal, or np.nan if not found
        """
        # Set the first column as index if it isn't already
        if self.borrow_fees.index.name != 'Token':
            df_indexed = self.borrow_fees.set_index('Token')
        else:
            df_indexed = self.borrow_fees

        try:
            # Get the borrow fee
            if token in df_indexed.index and protocol in df_indexed.columns:
                fee = df_indexed.loc[token, protocol]
                return float(fee) if pd.notna(fee) else np.nan
            else:
                return np.nan
        except:
            return np.nan

    def get_contract(self, token: str, protocol: str) -> Optional[str]:
        """
        Get contract address for a token on a specific protocol

        Args:
            token: Token symbol (e.g., 'USDC')
            protocol: Protocol name (e.g., 'navi')

        Returns:
            Contract address or None if not found
        """
        # Check lend_rates first (has 'Token' and 'Contract' columns)
        mask = (self.lend_rates['Token'] == token)
        if mask.any():
            row = self.lend_rates[mask].iloc[0]
            return row.get('Contract')

        # Fallback to borrow_rates
        mask = (self.borrow_rates['Token'] == token)
        if mask.any():
            row = self.borrow_rates[mask].iloc[0]
            return row.get('Contract')

        return None

    def analyze_all_combinations(self, tokens: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Analyze all possible protocol pairs and token combinations
        
        IMPORTANT: Token1 must be a stablecoin to avoid price exposure.
        The strategy starts by lending a stablecoin to remain market neutral.
        
        Args:
            tokens: List of tokens to analyze (default: all tokens from merged data)
            
        Returns:
            DataFrame with all results sorted by net APR
        """
        if tokens is None:
            tokens = self.ALL_TOKENS
        
        print(f"\n🔍 Analyzing all combinations...")
        print(f"   Tokens to analyze: {len(tokens)}")
        print(f"   Protocol pairs: {len(self.protocols) * (len(self.protocols) - 1)} (bidirectional)")
        print(f"   ⚠️  Enforcing: Token1 must be a stablecoin (market neutral requirement)")
        
        results = []
        analyzed = 0
        valid = 0
        
        # For each token pair
        # CRITICAL: token1 must be a stablecoin to avoid price exposure
        for token1 in tokens:
            # Enforce that token1 is a stablecoin
            if token1 not in self.STABLECOINS:
                continue
            
            for token2 in tokens:
                # Skip if same token
                if token1 == token2:
                    continue
                
                # For each closing stablecoin (CHANGE1: Stablecoin fungibility)
                for token3 in self.STABLECOINS:
                    # Skip if token3 same as token2
                    if token3 == token2:
                        continue
                    
                    # For each protocol pair (bidirectional)
                    for protocol_A in self.protocols:
                        for protocol_B in self.protocols:
                            # Skip if same protocol
                            if protocol_A == protocol_B:
                                continue
                            
                            analyzed += 1
                            
                            # Get all the rates
                            lend_rate_1A = self.get_rate(self.lend_rates, token1, protocol_A)
                            borrow_rate_2A = self.get_rate(self.borrow_rates, token2, protocol_A)
                            lend_rate_2B = self.get_rate(self.lend_rates, token2, protocol_B)
                            borrow_rate_3B = self.get_rate(self.borrow_rates, token3, protocol_B)
                            
                            # Get collateral ratios
                            collateral_1A = self.get_rate(self.collateral_ratios, token1, protocol_A)
                            collateral_2B = self.get_rate(self.collateral_ratios, token2, protocol_B)
                            # NEW: Get prices
                            price_1A = self.get_price(token1, protocol_A)
                            price_2A = self.get_price(token2, protocol_A)
                            price_2B = self.get_price(token2, protocol_B)
                            price_3B = self.get_price(token3, protocol_B)

                            # NEW: Get available borrow
                            available_borrow_2A = self.get_available_borrow(token2, protocol_A)
                            available_borrow_3B = self.get_available_borrow(token3, protocol_B)

                            # NEW: Get borrow fees
                            borrow_fee_2A = self.get_borrow_fee(token2, protocol_A)
                            borrow_fee_3B = self.get_borrow_fee(token3, protocol_B)

                            # Skip if any rates OR prices are missing
                            if any(np.isnan([lend_rate_1A, borrow_rate_2A, lend_rate_2B,
                                            borrow_rate_3B, collateral_1A, collateral_2B,
                                            price_1A, price_2A, price_2B, price_3B])):  # Add prices to check
                                continue
                            
                            # Analyze this strategy
                            result = self.calculator.analyze_strategy(
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
                                price_token3_B=price_3B,
                                available_borrow_2A=available_borrow_2A,
                                available_borrow_3B=available_borrow_3B,
                                borrow_fee_2A=borrow_fee_2A,  # NEW
                                borrow_fee_3B=borrow_fee_3B   # NEW
                            )

                            # Add contract addresses to result (for historical chart queries)
                            result['token1_contract'] = self.get_contract(token1, protocol_A)
                            result['token2_contract'] = self.get_contract(token2, protocol_A)  # Use Protocol A
                            result['token3_contract'] = self.get_contract(token3, protocol_B)

                            if result['valid']:
                                valid += 1
                                results.append(result)
        
        print(f"   ✓ Analyzed {analyzed} combinations")
        print(f"   ✓ {valid} valid strategies found")
        
        # Convert to DataFrame and sort by net APR
        if results:
            df_results = pd.DataFrame(results)

            # Add timestamp column - when this data was captured
            df_results['timestamp'] = self.timestamp

            # Add flag for stablecoin-only strategies (both tokens are stablecoins)
            df_results['is_stablecoin_only'] = df_results.apply(
                lambda row: row['token1'] in self.STABLECOINS and row['token2'] in self.STABLECOINS,
                axis=1
            )
            
            # Sort by net APR (descending), then by stablecoin-only (True first) as tiebreaker
            df_results = df_results.sort_values(
                by=['net_apr', 'is_stablecoin_only'],
                ascending=[False, False]
            )
            
            return df_results
        else:
            return pd.DataFrame()
    
    def find_best_protocol_pair(self, tokens: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str], pd.DataFrame]:
        """
        Find the best protocol pair based on maximum spread across any token
        
        Args:
            tokens: List of tokens to consider (default: all tokens)
            
        Returns:
            Tuple of (protocol_A, protocol_B, detailed_results_df)
        """
        # Analyze all combinations
        all_results = self.analyze_all_combinations(tokens)
        
        if all_results.empty:
            print("✗ No valid strategies found!")
            return None, None, pd.DataFrame()
        
        # Get the best strategy
        best = all_results.iloc[0]
        
        # Determine strategy type
        is_stablecoin_only = best['token1'] in self.STABLECOINS and best['token2'] in self.STABLECOINS
        has_conversion = best['token1'] != best['token3']
        
        if is_stablecoin_only:
            strategy_type = "Stablecoin-only"
        else:
            strategy_type = "Stablecoin + High-yield"
        
        if has_conversion:
            strategy_type += " (with conversion)"
        
        print(f"\n🏆 BEST STRATEGY FOUND ({strategy_type}):")
        print(f"   Protocol A: {best['protocol_A']}")
        print(f"   Protocol B: {best['protocol_B']}")
        print(f"   Token 1 (Start): {best['token1']}")
        print(f"   Token 2 (Middle): {best['token2']}")
        print(f"   Token 3 (Close): {best['token3']}", end="")
        if has_conversion:
            print(f" → Convert to {best['token1']}")
        else:
            print()  # Just newline
        print(f"   Net APR: {best['net_apr']:.2f}%")
        print(f"   Liquidation Distance: {best['liquidation_distance']:.0f}%")
        
        return best['protocol_A'], best['protocol_B'], all_results


# Example usage
if __name__ == "__main__":
    print("This module requires merged data from protocol_merger")
    print("Run main.py to see the full analysis with real data")