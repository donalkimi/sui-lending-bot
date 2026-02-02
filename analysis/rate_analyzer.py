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
        liquidation_thresholds: pd.DataFrame,
        prices: pd.DataFrame,                    # NEW
        lend_rewards: pd.DataFrame,              # NEW
        borrow_rewards: pd.DataFrame,            # NEW
        available_borrow: pd.DataFrame,          # NEW
        borrow_fees: pd.DataFrame,               # NEW
        borrow_weights: pd.DataFrame,            # NEW
        timestamp: int,  # Unix timestamp in seconds
        liquidation_distance: Optional[float] = None
    ):
        """
        Initialize the rate analyzer

        Args:
            lend_rates: DataFrame with lending rates (tokens x protocols)
            borrow_rates: DataFrame with borrow rates (tokens x protocols)
            collateral_ratios: DataFrame with collateral ratios (tokens x protocols)
            liquidation_thresholds: DataFrame with liquidation thresholds (tokens x protocols)
            prices: DataFrame with prices (tokens x protocols)                    # NEW
            lend_rewards: DataFrame with lend reward APRs (tokens x protocols)    # NEW
            borrow_rewards: DataFrame with borrow reward APRs (tokens x protocols) # NEW
            available_borrow: DataFrame with available borrow USD (tokens x protocols) # NEW
            borrow_fees: DataFrame with borrow fees (tokens x protocols)          # NEW
            borrow_weights: DataFrame with borrow weights (tokens x protocols)    # NEW
            timestamp: Unix timestamp in seconds (integer) - the "current" moment
            liquidation_distance: Safety buffer (default from settings)
        """
        self.lend_rates = lend_rates
        self.borrow_rates = borrow_rates
        self.collateral_ratios = collateral_ratios
        self.liquidation_thresholds = liquidation_thresholds
        self.prices = prices                      # NEW
        self.lend_rewards = lend_rewards          # NEW
        self.borrow_rewards = borrow_rewards      # NEW
        self.available_borrow = available_borrow  # NEW
        self.borrow_fees = borrow_fees            # NEW
        self.borrow_weights = borrow_weights      # NEW
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

        # Track exclusions
        self.excluded_by_rate_spread = 0  # Count strategies excluded by rate spread filter

        # Store timestamp (when this data was captured) - must be int (seconds)
        if timestamp is None:
            raise ValueError("timestamp is required and must be explicitly provided")
        if not isinstance(timestamp, int):
            raise TypeError(f"timestamp must be int (Unix seconds), got {type(timestamp).__name__}")
        self.timestamp = timestamp
        
        print(f"\n[ANALYZER] Initialized Rate Analyzer:")
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

    def get_liquidation_threshold(self, token: str, protocol: str) -> float:
        """
        Safely get liquidation threshold from the liquidation_thresholds dataframe

        Args:
            token: Token name
            protocol: Protocol name

        Returns:
            Liquidation threshold as decimal, or np.nan if not found
        """
        # Set the first column as index if it isn't already
        if self.liquidation_thresholds.index.name != 'Token':
            df_indexed = self.liquidation_thresholds.set_index('Token')
        else:
            df_indexed = self.liquidation_thresholds

        try:
            if token in df_indexed.index and protocol in df_indexed.columns:
                threshold = df_indexed.loc[token, protocol]
                return float(threshold) if pd.notna(threshold) else np.nan
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

    def get_borrow_weight(self, token: str, protocol: str) -> float:
        """
        Safely get borrow weight from the borrow_weights dataframe

        Args:
            token: Token name
            protocol: Protocol name

        Returns:
            Borrow weight as float (default 1.0 if not found)
        """
        # Set the first column as index if it isn't already
        if self.borrow_weights.index.name != 'Token':
            df_indexed = self.borrow_weights.set_index('Token')
        else:
            df_indexed = self.borrow_weights

        try:
            # Get the borrow weight
            if token in df_indexed.index and protocol in df_indexed.columns:
                weight = df_indexed.loc[token, protocol]
                return float(weight) if pd.notna(weight) else 1.0
            else:
                return 1.0
        except:
            return 1.0

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
        
        print(f"\n[ANALYZER] Analyzing all combinations...")
        print(f"   Tokens to analyze: {len(tokens)}")
        print(f"   Protocol pairs: {len(self.protocols) * (len(self.protocols) - 1)} (bidirectional)")
        print(f"   [!] Enforcing: Token1 must be a stablecoin (market neutral requirement)")

        # Pre-filter token2 candidates based on best-case spread
        spread_threshold = settings.RATE_SPREAD_THRESHOLD
        valid_token2s = []
        excluded_token2s = []

        for token in tokens:
            # Get all borrow rates for this token across protocols
            borrow_rates = [self.get_rate(self.borrow_rates, token, p) for p in self.protocols]
            borrow_rates = [r for r in borrow_rates if not np.isnan(r)]

            # Get all lend rates for this token across protocols
            lend_rates = [self.get_rate(self.lend_rates, token, p) for p in self.protocols]
            lend_rates = [r for r in lend_rates if not np.isnan(r)]

            if not borrow_rates or not lend_rates:
                continue

            # Best case: lend at max rate, borrow at min rate
            best_spread = max(lend_rates) - min(borrow_rates)

            if best_spread >= spread_threshold:
                valid_token2s.append(token)
            else:
                excluded_token2s.append((token, best_spread))

        print(f"   [OK] Token2 candidates: {len(valid_token2s)} valid, {len(excluded_token2s)} excluded")

        # Pre-filter token1 (stablecoin) candidates based on minimum lending threshold
        # Find minimum borrow rate across all stablecoins and protocols
        all_stablecoin_borrow_rates = []
        print(self.protocols)
        for stablecoin in self.STABLECOINS:
            for protocol in self.protocols:
                rate = self.get_rate(self.borrow_rates, stablecoin, protocol)
                if not np.isnan(rate):
                    all_stablecoin_borrow_rates.append(rate)

        if not all_stablecoin_borrow_rates:
            print(f"   [ERROR] No stablecoin borrow rates found")
            return pd.DataFrame()

        # Minimum viable lending rate = min borrow rate + threshold
        min_stablecoin_borrow = min(all_stablecoin_borrow_rates)
        min_lending_threshold = min_stablecoin_borrow + spread_threshold


        valid_token1s = []
        excluded_token1s = []

        for stablecoin in self.STABLECOINS:
            # Get all lend rates for this stablecoin across protocols
            lend_rates = [self.get_rate(self.lend_rates, stablecoin, p) for p in self.protocols]
            lend_rates = [r for r in lend_rates if not np.isnan(r)]

            if not lend_rates:
                continue

            # Check if max lending rate meets minimum threshold
            max_lend_rate = max(lend_rates)

            if max_lend_rate >= min_lending_threshold:
                valid_token1s.append(stablecoin)
            else:
                excluded_token1s.append((stablecoin, max_lend_rate))

        print(f"   [OK] Token1 candidates: {len(valid_token1s)} valid, {len(excluded_token1s)} excluded")

        # Pre-filter token3 (stablecoin) candidates based on maximum borrow threshold
        # Find MAXIMUM lend rate across all stablecoins and protocols
        all_stablecoin_lend_rates = []
        for stablecoin in self.STABLECOINS:
            for protocol in self.protocols:
                rate = self.get_rate(self.lend_rates, stablecoin, protocol)
                if not np.isnan(rate):
                    all_stablecoin_lend_rates.append(rate)

        if not all_stablecoin_lend_rates:
            print(f"   [ERROR] No stablecoin lend rates found")
            return pd.DataFrame()

        # Maximum viable borrow rate = max lend rate - threshold
        # Logic: Even with the best token1 lending rate, token3 borrow must be low enough to maintain 1% spread
        max_stablecoin_lend = max(all_stablecoin_lend_rates)
        max_borrow_threshold = max_stablecoin_lend - spread_threshold

        print(f"   [OK] Max stablecoin lend rate: {max_stablecoin_lend*100:.2f}%")
        print(f"   [OK] Max borrow threshold for token3: {max_borrow_threshold*100:.2f}%")

        valid_token3s = []
        excluded_token3s = []

        for stablecoin in self.STABLECOINS:
            # Get all borrow rates for this stablecoin across protocols
            borrow_rates = [self.get_rate(self.borrow_rates, stablecoin, p) for p in self.protocols]
            borrow_rates = [r for r in borrow_rates if not np.isnan(r)]

            if not borrow_rates:
                continue

            # Check if min borrow rate is below maximum threshold
            min_borrow_rate = min(borrow_rates)

            if min_borrow_rate <= max_borrow_threshold:
                valid_token3s.append(stablecoin)
            else:
                excluded_token3s.append((stablecoin, min_borrow_rate))


        results = []
        analyzed = 0
        valid = 0

        # For each token pair
        # CRITICAL: token1 must be a stablecoin to avoid price exposure
        for token1 in valid_token1s:
            # Enforce that token1 is a stablecoin
            if token1 not in self.STABLECOINS:
                continue
            
            for token2 in valid_token2s:
                # Skip if same token
                if token1 == token2:
                    continue
                
                # For each closing stablecoin (CHANGE1: Stablecoin fungibility)
                for token3 in valid_token3s:
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
                            if np.isnan(lend_rate_1A): 
                                continue
                            borrow_rate_2A = self.get_rate(self.borrow_rates, token2, protocol_A)
                            if np.isnan(borrow_rate_2A): 
                                continue
                            lend_rate_2B = self.get_rate(self.lend_rates, token2, protocol_B)
                            if np.isnan(lend_rate_2B): 
                                continue
                            borrow_rate_3B = self.get_rate(self.borrow_rates, token3, protocol_B)
                            if np.isnan(borrow_rate_3B): 
                                continue
                            
                            # Apply rate spread filter
                            spread_threshold = settings.RATE_SPREAD_THRESHOLD

                            # Condition 1: token2 spread (lend to B should be higher than borrow from A)
                            # We want: lend_rate_2B - borrow_rate_2A >= +1%
                            token2_spread = lend_rate_2B - borrow_rate_2A

                            # Condition 2: token1/token3 spread (lend to A should be higher than borrow from B)
                            # We want: lend_rate_1A - borrow_rate_3B >= +1%
                            token1_spread = lend_rate_1A - borrow_rate_3B

                            # If BOTH spread are below threshold, exclude this strategy. It might be the case the the weighted average of a negative spread in the middle is more than offset by spread on the boundaries (or vice-versa)
                            if token2_spread < spread_threshold and token1_spread < spread_threshold:
                                self.excluded_by_rate_spread += 1
                                
                                # # Log to console for debugging
                                # failed_conditions = []
                                # if token2_spread < spread_threshold:
                                #     failed_conditions.append(
                                #         f"token2_spread: {token2_spread*100:.2f}% "
                                #         f"(lend {token2} @ {lend_rate_2B*100:.2f}% - borrow @ {borrow_rate_2A*100:.2f}%)"
                                #     )
                                # if token1_spread < spread_threshold:
                                #     failed_conditions.append(
                                #         f"token1_spread: {token1_spread*100:.2f}% "
                                #         f"(lend {token1} @ {lend_rate_1A*100:.2f}% - borrow {token3} @ {borrow_rate_3B*100:.2f}%)"
                                #     )

                                # #print(f"   [FILTERED] {protocol_A} <-> {protocol_B} | {token1}->{token2}->{token3} | {', '.join(failed_conditions)}")
                                continue  # Skip this combination
                            
                            # Get collateral ratios
                            collateral_1A = self.get_rate(self.collateral_ratios, token1, protocol_A)
                            collateral_2B = self.get_rate(self.collateral_ratios, token2, protocol_B)
                            # Get liquidation thresholds
                            liquidation_threshold_1A = self.get_liquidation_threshold(token1, protocol_A)
                            liquidation_threshold_2B = self.get_liquidation_threshold(token2, protocol_B)
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

                            # NEW: Get borrow weights (defaults to 1.0)
                            borrow_weight_2A = self.get_borrow_weight(token2, protocol_A)
                            borrow_weight_3B = self.get_borrow_weight(token3, protocol_B)

                            # Skip if any rates OR prices are missing
                            if any(np.isnan([lend_rate_1A, borrow_rate_2A, lend_rate_2B,
                                            borrow_rate_3B, collateral_1A, collateral_2B,
                                            liquidation_threshold_1A, liquidation_threshold_2B,
                                            price_1A, price_2A, price_2B, price_3B])):  # Add prices to check
                                continue

                            # Skip if collateral ratios are zero or near-zero (causes division by zero)
                            # A collateral ratio of 0 means the token cannot be used as collateral
                            if collateral_1A <= 1e-9 or collateral_2B <= 1e-9:
                                continue

                            # Skip if liquidation thresholds are zero or near-zero
                            # Zero liquidation threshold is invalid (position would be instantly liquidated)
                            if liquidation_threshold_1A <= 1e-9 or liquidation_threshold_2B <= 1e-9:
                                continue

                            # Skip if any prices are zero or near-zero (causes division by zero in calculations)
                            if any(p <= 1e-9 for p in [price_1A, price_2A, price_2B, price_3B]):
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
                                liquidation_threshold_token1_A=liquidation_threshold_1A,
                                liquidation_threshold_token2_B=liquidation_threshold_2B,
                                price_token1_A=price_1A,
                                price_token2_A=price_2A,
                                price_token2_B=price_2B,
                                price_token3_B=price_3B,
                                available_borrow_2A=available_borrow_2A,
                                available_borrow_3B=available_borrow_3B,
                                borrow_fee_2A=borrow_fee_2A,  # NEW
                                borrow_fee_3B=borrow_fee_3B,  # NEW
                                borrow_weight_2A=borrow_weight_2A,  # NEW
                                borrow_weight_3B=borrow_weight_3B   # NEW
                            )

                            # Add contract addresses to result (for historical chart queries)
                            result['token1_contract'] = self.get_contract(token1, protocol_A)
                            result['token2_contract'] = self.get_contract(token2, protocol_A)  # Use Protocol A
                            result['token3_contract'] = self.get_contract(token3, protocol_B)

                            if result['valid']:
                                valid += 1
                                results.append(result)
        
        print(f"   [OK] Analyzed {analyzed} combinations")
        print(f"   [OK] {self.excluded_by_rate_spread} excluded by rate spread filter (<{settings.RATE_SPREAD_THRESHOLD*100:.0f}% spread)")
        print(f"   [OK] {valid} valid strategies found")
        
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
        
        print(f"\n[BEST STRATEGY] BEST STRATEGY FOUND ({strategy_type}):")
        print(f"   Protocol A: {best['protocol_A']}")
        print(f"   Protocol B: {best['protocol_B']}")
        print(f"   Token 1 (Start): {best['token1']}")
        print(f"   Token 2 (Middle): {best['token2']}")
        print(f"   Token 3 (Close): {best['token3']}", end="")
        if has_conversion:
            print(f" -> Convert to {best['token1']}")
        else:
            print()  # Just newline
        print(f"   Net APR: {best['net_apr'] * 100:.2f}%")
        print(f"   Liquidation Distance: {best['liquidation_distance'] * 100:.0f}%")
        
        return best['protocol_A'], best['protocol_B'], all_results


# Example usage
if __name__ == "__main__":
    print("This module requires merged data from protocol_merger")
    print("Run main.py to see the full analysis with real data")