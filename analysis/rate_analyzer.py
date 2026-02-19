"""
Rate analyzer to find the best protocol pair and token combination
"""

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import sys
import os

logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from config.stablecoins import STABLECOIN_SYMBOLS
from analysis.position_calculator import PositionCalculator
from analysis.strategy_calculators import get_calculator, get_all_strategy_types
from analysis.strategy_calculators.base import StrategyCalculatorBase


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
        liquidation_distance: Optional[float] = None,
        strategy_types: Optional[List[str]] = None,  # NEW: Multi-strategy support
        rate_tracker=None  # NEW: Optional RateTracker for perp lending strategies
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
            strategy_types: REQUIRED list of strategy types to generate  # NEW
                           Use get_all_strategy_types() to get all available types
                           Example: ['recursive_lending'] or ['stablecoin_lending', 'recursive_lending']

        Raises:
            ValueError: If strategy_types is None, empty, or contains invalid types
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

        # Initialize calculator (legacy - for backward compatibility)
        self.calculator = PositionCalculator(self.liquidation_distance)

        # NEW: Multi-strategy support - load calculators for each strategy type
        # FAIL LOUD: Require explicit strategy_types parameter
        if strategy_types is None:
            raise ValueError(
                "strategy_types parameter is required. "
                "Explicitly specify which strategy types to generate. "
                f"Available types: {get_all_strategy_types()}. "
                "Example: strategy_types=['recursive_lending'] or "
                "strategy_types=get_all_strategy_types() for all types."
            )

        if not isinstance(strategy_types, list) or len(strategy_types) == 0:
            raise ValueError(
                f"strategy_types must be a non-empty list of strings. "
                f"Available types: {get_all_strategy_types()}"
            )

        # Validate all strategy types are registered
        available_types = get_all_strategy_types()
        invalid_types = [st for st in strategy_types if st not in available_types]
        if invalid_types:
            raise ValueError(
                f"Invalid strategy types: {invalid_types}. "
                f"Available types: {available_types}"
            )

        self.strategy_types = strategy_types
        self.calculators = {
            st: get_calculator(st) for st in self.strategy_types
        }

        # NEW: Store RateTracker for perp lending strategies (optional)
        self.rate_tracker = rate_tracker

        # Track exclusions
        self.excluded_by_rate_spread = 0  # Count strategies excluded by rate spread filter

        # Store timestamp (when this data was captured) - must be int (seconds)
        if timestamp is None:
            raise ValueError("timestamp is required and must be explicitly provided")
        if not isinstance(timestamp, int):
            raise TypeError(f"timestamp must be int (Unix seconds), got {type(timestamp).__name__}")
        self.timestamp = timestamp

        print(f"[ANALYZER] Initialized: {len(self.protocols)} protocols, {len(self.ALL_TOKENS)} tokens (Stablecoins: {len(self.STABLECOINS)}, High-Yield: {len(self.OTHER_TOKENS)})")
        print(f"[ANALYZER] Strategy types enabled: {', '.join(self.strategy_types)}")
    
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

    def _get_protocol_pairs(self) -> List[Tuple[str, str]]:
        """
        Get all valid protocol pairs.

        Returns:
            List of (protocol_a, protocol_b) tuples
        """
        pairs = []
        for i, protocol_a in enumerate(self.protocols):
            for protocol_b in self.protocols[i+1:]:  # Only unique pairs
                pairs.append((protocol_a, protocol_b))
        return pairs

    def _generate_stablecoin_strategies(
        self,
        calculator: StrategyCalculatorBase
    ) -> pd.DataFrame:
        """
        Generate stablecoin lending strategies.

        Iteration pattern:
        - token1 (stablecoins only) × protocol_a
        - Single token, single protocol
        """
        results = []

        # MUST always use stablecoins only (ignore tokens parameter)
        stablecoins = self.STABLECOINS

        for token1 in stablecoins:
            for protocol_a in self.protocols:
                # Early check: Does token1 exist in protocol_a for lending?
                lend_total_apr_1A = self.get_rate(self.lend_rates, token1, protocol_a)
                if np.isnan(lend_total_apr_1A) or lend_total_apr_1A <= 1e-9:
                    continue  # token1 not lendable in protocol_a

                # Get remaining rates and validate
                lend_reward_apr_1A = self.get_rate(self.lend_rewards, token1, protocol_a)
                if np.isnan(lend_reward_apr_1A):
                    logger.warning(f"[Stablecoin] NaN reward APR for {token1} on {protocol_a} - skipping")
                    continue
                lend_base_apr_1A = lend_total_apr_1A - lend_reward_apr_1A
                price_1A = self.get_rate(self.prices, token1, protocol_a)
                token1_contract = self.get_contract(token1, protocol_a)

                if np.isnan(price_1A) or price_1A <= 1e-9:
                    continue

                # Call calculator
                result = calculator.analyze_strategy(
                    token1=token1,
                    token1_contract=token1_contract,
                    protocol_a=protocol_a,
                    lend_total_apr_1A=lend_total_apr_1A,
                    lend_base_apr_1A=lend_base_apr_1A,
                    lend_reward_apr_1A=lend_reward_apr_1A,
                    price_1A=price_1A,
                    liquidation_distance=self.liquidation_distance,
                    timestamp=self.timestamp
                )

                if result.get('valid', False):
                    results.append(result)

        df = pd.DataFrame(results)
        if not df.empty:
            df['strategy_type'] = calculator.get_strategy_type()
            # Add timestamp column - when this data was captured
            # Explicitly cast to int to prevent pandas from converting to float64
            df['timestamp'] = self.timestamp
            df['timestamp'] = df['timestamp'].astype(int)

        return df

    def _generate_noloop_strategies(
        self,
        calculator: StrategyCalculatorBase
    ) -> pd.DataFrame:
        """
        Generate no-loop cross-protocol strategies.

        Iteration pattern:
        - token1 (stablecoins) × token2 (all) × protocol_a × protocol_b
        - Two tokens, two protocols, no token3
        """
        results = []

        # Token1 MUST always be stablecoins (ignore tokens parameter for this)
        stablecoins = self.STABLECOINS
        all_tokens = self.ALL_TOKENS  # Use ALL tokens (including stablecoins)

        # PRE-FILTER token2 candidates to exclude non-profitable tokens
        valid_token2s = []
        excluded_token2s = []

        for token2 in all_tokens:
            # Find highest lending rate across all protocols
            lend_rates = [self.get_rate(self.lend_rates, token2, p) for p in self.protocols]
            lend_rates = [r for r in lend_rates if not np.isnan(r)]

            # Find lowest borrow rate across all protocols
            borrow_rates = [self.get_rate(self.borrow_rates, token2, p) for p in self.protocols]
            borrow_rates = [r for r in borrow_rates if not np.isnan(r)]

            if not lend_rates or not borrow_rates:
                continue

            r_2_max = max(lend_rates)
            b_2_min = min(borrow_rates)

            # If max lend rate < min borrow rate, no profitable combination exists
            if r_2_max >= b_2_min:
                valid_token2s.append(token2)
            else:
                excluded_token2s.append((token2, r_2_max, b_2_min))

        print(f"[ANALYZER] NoLoop: Pre-filtered {len(all_tokens)} tokens -> {len(valid_token2s)} valid token2 candidates")
        if excluded_token2s:
            print(f"[ANALYZER] NoLoop: Excluded {len(excluded_token2s)} tokens with r_max < b_min")

        for token1 in stablecoins:
            for token2 in valid_token2s:
                if token1 == token2:
                    continue

                # Nested protocol loops with early filtering for efficiency
                for protocol_a in self.protocols:
                    # Early check: Does token1 exist in protocol_a for lending?
                    lend_total_apr_1A = self.get_rate(self.lend_rates, token1, protocol_a)
                    if np.isnan(lend_total_apr_1A) or lend_total_apr_1A <= 1e-9:
                        continue  # token1 not lendable in protocol_a

                    # Early check: Does token2 exist in protocol_a for borrowing?
                    borrow_total_apr_2A = self.get_rate(self.borrow_rates, token2, protocol_a)
                    if np.isnan(borrow_total_apr_2A) or borrow_total_apr_2A <= 1e-9:
                        continue  # token2 not borrowable in protocol_a

                    for protocol_b in self.protocols:
                        # Skip if same protocol (cross-protocol strategy requires different protocols)
                        if protocol_b == protocol_a:
                            continue

                        # Early check: Does token2 exist in protocol_b for lending?
                        lend_total_apr_2B = self.get_rate(self.lend_rates, token2, protocol_b)
                        if np.isnan(lend_total_apr_2B) or lend_total_apr_2B <= 1e-9:
                            continue  # token2 not lendable in protocol_b

                        # All tokens exist in required protocols - now get remaining data
                        collateral_ratio_1A = self.get_rate(self.collateral_ratios, token1, protocol_a)
                        liquidation_threshold_1A = self.get_liquidation_threshold(token1, protocol_a)

                        price_1A = self.get_rate(self.prices, token1, protocol_a)
                        price_2A = self.get_rate(self.prices, token2, protocol_a)
                        price_2B = self.get_rate(self.prices, token2, protocol_b)

                        borrow_fee_2A = self.get_rate(self.borrow_fees, token2, protocol_a)
                        available_borrow_2A = self.get_rate(self.available_borrow, token2, protocol_a)
                        borrow_weight_2A = self.get_borrow_weight(token2, protocol_a)

                        token1_contract = self.get_contract(token1, protocol_a)
                        token2_contract = self.get_contract(token2, protocol_a)

                        # FAIL LOUD: Validate all required data is present
                        # At this point, we already checked APRs exist, so NaN here indicates data quality issues
                        required_checks = [
                            (collateral_ratio_1A, f"collateral_ratio for {token1} on {protocol_a}"),
                            (liquidation_threshold_1A, f"liquidation_threshold for {token1} on {protocol_a}"),
                            (price_1A, f"price for {token1} on {protocol_a}"),
                            (price_2A, f"price for {token2} on {protocol_a}"),
                            (price_2B, f"price for {token2} on {protocol_b}"),
                        ]

                        # Check for NaN or invalid values
                        skip_strategy = False
                        for value, name in required_checks:
                            if np.isnan(value):
                                logger.warning(f"[NoLoop] NaN value for {name} - skipping strategy")
                                skip_strategy = True
                                break
                            if value <= 1e-9:
                                skip_strategy = True
                                break

                        if skip_strategy:
                            continue

                        # Call calculator
                        result = calculator.analyze_strategy(
                            token1=token1,
                            token1_contract=token1_contract,
                            token2=token2,
                            token2_contract=token2_contract,
                            protocol_a=protocol_a,
                            protocol_b=protocol_b,
                            lend_total_apr_1A=lend_total_apr_1A,
                            borrow_total_apr_2A=borrow_total_apr_2A,
                            lend_total_apr_2B=lend_total_apr_2B,
                            collateral_ratio_1A=collateral_ratio_1A,
                            liquidation_threshold_1A=liquidation_threshold_1A,
                            price_1A=price_1A,
                            price_2A=price_2A,
                            price_2B=price_2B,
                            available_borrow_2A=available_borrow_2A,
                            borrow_fee_2A=borrow_fee_2A,
                            borrow_weight_2A=borrow_weight_2A,
                            liquidation_distance=self.liquidation_distance,
                            timestamp=self.timestamp
                        )

                        if result.get('valid', False):
                            results.append(result)

                            # Progress indicator every 50 strategies
                            if len(results) % 500 == 0:
                                print(f"[ANALYZER] NoLoop: Generated {len(results)} strategies so far...")

        print(f"[ANALYZER] NoLoop: Generated {len(results)} total strategies")
        df = pd.DataFrame(results)
        if not df.empty:
            df['strategy_type'] = calculator.get_strategy_type()
            # Add timestamp column - when this data was captured
            # Explicitly cast to int to prevent pandas from converting to float64
            df['timestamp'] = self.timestamp
            df['timestamp'] = df['timestamp'].astype(int)
        return df

    def _generate_recursive_strategies(
        self,
        calculator: StrategyCalculatorBase,
        tokens: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Generate recursive lending strategies.

        Iteration pattern:
        - token1 × token2 × token3 (stablecoins) × protocol_a × protocol_b
        - Three tokens, two protocols, full loop

        Note: For now, this returns empty DataFrame. The existing analyze_all_combinations()
        logic will be refactored to use this method in a future update.
        """
        # TODO: Refactor existing analyze_all_combinations() logic to use calculator
        # For now, return empty DataFrame to maintain backward compatibility
        print("[ANALYZER] Recursive strategy generation using existing analyze_all_combinations() logic")
        return pd.DataFrame()

    def _generate_perp_lending_strategies(
        self,
        calculator: StrategyCalculatorBase
    ) -> pd.DataFrame:
        """
        Generate perp lending strategies (spot + perp short).

        Iteration pattern:
        - token1 (spot tokens from Bluefin mappings) × protocol_a (lending protocols)
        - token3 (perp tokens from Bluefin)
        - protocol_b (always 'Bluefin')
        """
        results = []

        # Get all Bluefin perp tokens from rates
        bluefin_tokens = [token for token in self.ALL_TOKENS if '-PERP' in token]

        print(f"[ANALYZER] Perp: Found {len(bluefin_tokens)} perp tokens: {bluefin_tokens}")

        if not bluefin_tokens:
            print("[ANALYZER] Perp: No Bluefin perp markets found in rates_snapshot")
            return pd.DataFrame()

        # Get BLUEFIN_TO_LENDINGS mapping from settings
        from config.settings import BLUEFIN_TO_LENDINGS

        for perp_token in bluefin_tokens:
            # Get perp funding rate from Bluefin
            borrow_total_apr_3B = self.get_rate(self.borrow_rates, perp_token, 'Bluefin')
            if np.isnan(borrow_total_apr_3B):
                print(f"[ANALYZER] Perp: No borrow rate for {perp_token} on Bluefin - skipping")
                continue

            print(f"[ANALYZER] Perp: Processing {perp_token}, funding_rate={borrow_total_apr_3B:.4f}")

            price_3B = self.get_rate(self.prices, perp_token, 'Bluefin')
            perp_contract = self.get_contract(perp_token, 'Bluefin')

            # Get compatible spot tokens for this perp market
            # Build the perp contract key for lookup
            perp_contract_key = perp_contract if perp_contract else f'0x{perp_token}_bluefin'

            compatible_spot_contracts = BLUEFIN_TO_LENDINGS.get(perp_contract_key, [])

            print(f"[ANALYZER] Perp: {perp_token} -> key={perp_contract_key}, found {len(compatible_spot_contracts)} spot contracts")

            if not compatible_spot_contracts:
                # Try alternative key formats
                print(f"[ANALYZER] Perp: No compatible spot contracts for {perp_token} - skipping")
                continue

            # For each compatible spot token
            for spot_contract in compatible_spot_contracts:
                # Find spot token symbol from contract
                spot_token = None
                for token in self.ALL_TOKENS:
                    if self.get_contract(token, self.protocols[0]) == spot_contract:
                        spot_token = token
                        break

                if not spot_token:
                    continue

                # For each lending protocol
                for protocol_a in self.protocols:
                    if protocol_a == 'Bluefin':
                        continue  # Skip Bluefin as lending protocol

                    # Get spot token lending rate
                    lend_total_apr_1A = self.get_rate(self.lend_rates, spot_token, protocol_a)
                    if np.isnan(lend_total_apr_1A) or lend_total_apr_1A <= 1e-9:
                        continue

                    price_1A = self.get_rate(self.prices, spot_token, protocol_a)
                    if np.isnan(price_1A) or price_1A <= 1e-9:
                        continue

                    token1_contract = self.get_contract(spot_token, protocol_a)

                    # Call calculator
                    result = calculator.analyze_strategy(
                        token1=spot_token,
                        token1_contract=token1_contract,
                        protocol_a=protocol_a,
                        protocol_b='Bluefin',
                        lend_total_apr_1A=lend_total_apr_1A,
                        borrow_total_apr_3B=borrow_total_apr_3B,
                        price_1A=price_1A,
                        price_3B=price_3B,
                        token3=perp_token,
                        token3_contract=perp_contract,
                        liquidation_distance=self.liquidation_distance,
                        timestamp=self.timestamp
                    )

                    if result.get('valid', False):
                        results.append(result)

        print(f"[ANALYZER] Perp: Generated {len(results)} total strategies")
        df = pd.DataFrame(results)
        if not df.empty:
            df['strategy_type'] = calculator.get_strategy_type()
            df['timestamp'] = self.timestamp
            df['timestamp'] = df['timestamp'].astype(int)
        return df

    def analyze_all_combinations(self, tokens: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Analyze all possible protocol pairs and token combinations for ALL strategy types.

        IMPORTANT: Token1 must be a stablecoin to avoid price exposure.
        The strategy starts by lending a stablecoin to remain market neutral.

        Args:
            tokens: List of tokens to analyze (default: all tokens from merged data)

        Returns:
            DataFrame with strategies from all types, sorted by net_apr descending
        """
        if tokens is None:
            tokens = self.ALL_TOKENS

        # NEW: Multi-strategy support
        # If multiple strategy types enabled, generate strategies for each type
        if len(self.strategy_types) > 1 or 'recursive_lending' not in self.strategy_types:
            all_strategies = []

            for strategy_type, calculator in self.calculators.items():

                # Generate strategies for this type
                if strategy_type == 'stablecoin_lending':
                    strategies = self._generate_stablecoin_strategies(calculator)
                elif strategy_type == 'noloop_cross_protocol_lending':
                    strategies = self._generate_noloop_strategies(calculator)
                elif strategy_type == 'perp_lending':
                    strategies = self._generate_perp_lending_strategies(calculator)
                elif strategy_type == 'recursive_lending':
                    # For recursive, fall through to existing logic below
                    print("[ANALYZER] Using existing logic for recursive_lending strategies")
                    continue
                else:
                    print(f"[ANALYZER] Unknown strategy type: {strategy_type}, skipping")
                    continue

                if not strategies.empty:
                    print(f"[ANALYZER] Generated {len(strategies)} {strategy_type} strategies")
                    all_strategies.append(strategies)

            # If recursive_lending is in the list, generate using existing logic
            if 'recursive_lending' in self.strategy_types:
                print(f"[ANALYZER] Generating recursive_lending strategies using legacy logic...")
                # Continue with existing logic below (fall through)
            else:
                # Combine all non-recursive strategy types
                if not all_strategies:
                    print("[ANALYZER] No valid strategies found")
                    return pd.DataFrame()

                combined = pd.concat(all_strategies, ignore_index=True)
                combined = combined.sort_values(by='apr_net', ascending=False)
                print(f"[ANALYZER] Total strategies generated: {len(combined)}")
                return combined

        # Existing logic for recursive_lending strategies
        print(f"[ANALYZER] Analyzing combinations (recursive lending)...")

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

        # Pre-filter token1 (stablecoin) candidates based on minimum lending threshold
        # Find minimum borrow rate across all stablecoins and protocols
        all_stablecoin_borrow_rates = []
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

        # Pre-filter token3 (stablecoin) candidates based on maximum borrow threshold
        # Find MAXIMUM lend rate across all stablecoins and protocols
        all_stablecoin_lend_rates = []
        for stablecoin in self.STABLECOINS:
            for protocol in self.protocols:
                rate = self.get_rate(self.lend_rates, stablecoin, protocol)
                if not np.isnan(rate):
                    all_stablecoin_lend_rates.append(rate)

        if not all_stablecoin_lend_rates:
            print(f"[ERROR] No stablecoin lend rates found")
            return pd.DataFrame()

        # Maximum viable borrow rate = max lend rate - threshold
        # Logic: Even with the best token1 lending rate, token3 borrow must be low enough to maintain 1% spread
        max_stablecoin_lend = max(all_stablecoin_lend_rates)
        max_borrow_threshold = max_stablecoin_lend - spread_threshold

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
                    for protocol_a in self.protocols:
                        for protocol_b in self.protocols:
                            # Skip if same protocol
                            if protocol_a == protocol_b:
                                continue
                            analyzed += 1
                            
                            # Get all the rates
                            lend_rate_1A = self.get_rate(self.lend_rates, token1, protocol_a)
                            if np.isnan(lend_rate_1A): 
                                continue
                            borrow_rate_2A = self.get_rate(self.borrow_rates, token2, protocol_a)
                            if np.isnan(borrow_rate_2A): 
                                continue
                            lend_rate_2B = self.get_rate(self.lend_rates, token2, protocol_b)
                            if np.isnan(lend_rate_2B): 
                                continue
                            borrow_rate_3B = self.get_rate(self.borrow_rates, token3, protocol_b)
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

                                # #print(f"   [FILTERED] {protocol_a} <-> {protocol_b} | {token1}->{token2}->{token3} | {', '.join(failed_conditions)}")
                                continue  # Skip this combination
                            
                            # Get collateral ratios
                            collateral_1A = self.get_rate(self.collateral_ratios, token1, protocol_a)
                            collateral_2B = self.get_rate(self.collateral_ratios, token2, protocol_b)
                            # Get liquidation thresholds
                            liquidation_threshold_1A = self.get_liquidation_threshold(token1, protocol_a)
                            liquidation_threshold_2B = self.get_liquidation_threshold(token2, protocol_b)
                            # NEW: Get prices
                            price_1A = self.get_price(token1, protocol_a)
                            price_2A = self.get_price(token2, protocol_a)
                            price_2B = self.get_price(token2, protocol_b)
                            price_3B = self.get_price(token3, protocol_b)

                            # NEW: Get available borrow
                            available_borrow_2A = self.get_available_borrow(token2, protocol_a)
                            available_borrow_3B = self.get_available_borrow(token3, protocol_b)

                            # NEW: Get borrow fees
                            borrow_fee_2A = self.get_borrow_fee(token2, protocol_a)
                            borrow_fee_3B = self.get_borrow_fee(token3, protocol_b)

                            # NEW: Get borrow weights (defaults to 1.0)
                            borrow_weight_2A = self.get_borrow_weight(token2, protocol_a)
                            borrow_weight_3B = self.get_borrow_weight(token3, protocol_b)

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
                                price_token3_B=price_3B,
                                available_borrow_2A=available_borrow_2A,
                                available_borrow_3B=available_borrow_3B,
                                borrow_fee_2A=borrow_fee_2A,  # NEW
                                borrow_fee_3B=borrow_fee_3B,  # NEW
                                borrow_weight_2A=borrow_weight_2A,  # NEW
                                borrow_weight_3B=borrow_weight_3B   # NEW
                            )

                            # Add contract addresses to result (for historical chart queries)
                            result['token1_contract'] = self.get_contract(token1, protocol_a)
                            result['token2_contract'] = self.get_contract(token2, protocol_a)  # Use Protocol A
                            result['token3_contract'] = self.get_contract(token3, protocol_b)

                            if result['valid']:
                                valid += 1
                                results.append(result)
        
        print(f"[ANALYZER] Found {valid} valid strategies from {analyzed} combinations")
        
        # Convert to DataFrame and sort by net APR
        if results:
            df_results = pd.DataFrame(results)

            # Add timestamp column - when this data was captured
            # Explicitly cast to int to prevent pandas from converting to float64
            df_results['timestamp'] = self.timestamp
            df_results['timestamp'] = df_results['timestamp'].astype(int)

            # Add flag for stablecoin-only strategies (both tokens are stablecoins)
            df_results['is_stablecoin_only'] = df_results.apply(
                lambda row: row['token1'] in self.STABLECOINS and row['token2'] in self.STABLECOINS,
                axis=1
            )
            
            # Add strategy_type column for multi-strategy support
            df_results['strategy_type'] = 'recursive_lending'
            
            # Sort by apr_net (descending), then by stablecoin-only (True first) as tiebreaker
            df_results = df_results.sort_values(
                by=['apr_net', 'is_stablecoin_only'],
                ascending=[False, False]
            )
            #print(df_results)

            # If we have other strategy types, combine with them
            if len(self.strategy_types) > 1:
                # We generated recursive strategies, now generate others
                other_strategies = []
                for strategy_type, calculator in self.calculators.items():
                    if strategy_type == 'recursive_lending':
                        continue  # Already generated above

                    print(f"[ANALYZER] Generating {strategy_type} strategies...")

                    if strategy_type == 'stablecoin_lending':
                        strategies = self._generate_stablecoin_strategies(calculator)
                    elif strategy_type == 'noloop_cross_protocol_lending':
                        strategies = self._generate_noloop_strategies(calculator)
                    elif strategy_type == 'perp_lending':
                        strategies = self._generate_perp_lending_strategies(calculator)
                    else:
                        continue

                    if not strategies.empty:
                        print(f"[ANALYZER] Generated {len(strategies)} {strategy_type} strategies")
                        other_strategies.append(strategies)

                # Combine all strategies
                if other_strategies:
                    other_strategies.append(df_results)
                    print(f"[ANALYZER] Combining {len(other_strategies)} strategy DataFrames...")
                    combined = pd.concat(other_strategies, ignore_index=True)
                    combined = combined.sort_values(by='apr_net', ascending=False)
                    return combined

            print(f"[ANALYZER] Returning {len(df_results)} recursive strategies only (no other types generated)")
            return df_results
        else:
            return pd.DataFrame()
    
    def find_best_protocol_pair(self, tokens: Optional[List[str]] = None) -> Tuple[Optional[str], Optional[str], pd.DataFrame]:
        """
        Find the best protocol pair based on maximum spread across any token
        
        Args:
            tokens: List of tokens to consider (default: all tokens)
            
        Returns:
            Tuple of (protocol_a, protocol_b, detailed_results_df)
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
        
        conversion_str = f" -> {best['token1']}" if has_conversion else ""
        print(f"[BEST STRATEGY] {best['protocol_a']}/{best['protocol_b']}: {best['token1']}/{best['token2']}/{best['token3']}{conversion_str} @ {best['apr_net'] * 100:.2f}% APR")
        
        return best['protocol_a'], best['protocol_b'], all_results


# Example usage
if __name__ == "__main__":
    print("This module requires merged data from protocol_merger")
    print("Run main.py to see the full analysis with real data")