"""
Portfolio Allocator - Greedy algorithm for optimal portfolio selection

This module implements constraint-based portfolio allocation:
1. Filter strategies by minimum confidence threshold
2. Calculate blended APR using user-defined weights
3. Apply stablecoin preference penalties
4. Greedily select strategies respecting token/protocol exposure limits
"""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from config.settings import DEFAULT_ALLOCATION_CONSTRAINTS


class PortfolioAllocator:
    """
    Allocates capital across strategies using greedy algorithm with constraints.

    The allocator:
    - Filters strategies by confidence threshold
    - Calculates blended APR (weighted average of net_apr, apr5, apr30, apr90)
    - Applies stablecoin preference penalties to adjust APR
    - Ranks strategies by adjusted APR (descending)
    - Greedily allocates capital respecting exposure limits
    """

    def __init__(self, strategies_df: pd.DataFrame, db_connection=None):
        """
        Initialize allocator with strategy data.

        Args:
            strategies_df: DataFrame with strategy data including:
                - net_apr, apr5, apr30, apr90 (as decimals 0-1)
                - token1, token2, token3 (symbols)
                - token1_contract, token2_contract, token3_contract
                - protocol_a, protocol_b
                - confidence (calculated separately, 0-1)
            db_connection: Optional database connection for historical queries
        """
        self.strategies = strategies_df.copy()
        self.conn = db_connection

    def calculate_adjusted_apr(
        self,
        strategy_row: pd.Series,
        blended_apr: float,
        stablecoin_prefs: Dict[str, float]
    ) -> Dict[str, any]:
        """
        Apply stablecoin preference penalty to blended APR.

        Logic:
        - Check all tokens in strategy (token1, token2, token3)
        - If token is in stablecoin_prefs, get its multiplier
        - Apply the LOWEST multiplier found (most conservative)
        - If no stablecoins found, multiplier = 1.0 (no penalty)

        Args:
            strategy_row: Strategy data
            blended_apr: Weighted APR from apr5/apr30/apr90/net_apr
            stablecoin_prefs: Dict mapping token symbol -> multiplier (0-1)

        Returns:
            Dict with:
            - blended_apr: Original blended APR
            - stablecoin_multiplier: Applied multiplier (lowest from strategy)
            - adjusted_apr: blended_apr * stablecoin_multiplier
            - stablecoins_in_strategy: List of stablecoins found in strategy
        """
        # Get all tokens in strategy
        tokens_in_strategy = [
            strategy_row['token1'],
            strategy_row['token2'],
            strategy_row['token3']
        ]

        # Find stablecoins and their multipliers
        stablecoins_found = []
        multipliers = []

        for token in tokens_in_strategy:
            if token in stablecoin_prefs:
                stablecoins_found.append(token)
                multipliers.append(stablecoin_prefs[token])

        # Apply the LOWEST multiplier (most conservative penalty)
        # If no stablecoins found, multiplier = 1.0 (no penalty)
        stablecoin_multiplier = min(multipliers) if multipliers else 1.0

        adjusted_apr = blended_apr * stablecoin_multiplier

        return {
            'blended_apr': blended_apr,
            'stablecoin_multiplier': stablecoin_multiplier,
            'adjusted_apr': adjusted_apr,
            'stablecoins_in_strategy': stablecoins_found
        }

    def calculate_blended_apr(
        self,
        strategy_row: pd.Series,
        apr_weights: Dict[str, float]
    ) -> float:
        """
        Calculate blended APR using user-defined weights.

        Formula: blended_apr = w1*net_apr + w2*apr5 + w3*apr30 + w4*apr90

        Args:
            strategy_row: Strategy data
            apr_weights: Dict with keys: net_apr, apr5, apr30, apr90 (as decimals)

        Returns:
            Blended APR as decimal (e.g., 0.10 = 10%)
        """
        blended_apr = (
            strategy_row['net_apr'] * apr_weights.get('net_apr', 0.0) +
            strategy_row.get('apr5', 0.0) * apr_weights.get('apr5', 0.0) +
            strategy_row.get('apr30', 0.0) * apr_weights.get('apr30', 0.0) +
            strategy_row.get('apr90', 0.0) * apr_weights.get('apr90', 0.0)
        )
        return blended_apr

    def _calculate_max_allocation(
        self,
        strategy_row: pd.Series,
        remaining_capital: float,
        token_exposures: Dict[str, float],
        protocol_exposures: Dict[str, float],
        constraints: Dict,
        portfolio_size: float
    ) -> float:
        """
        Calculate maximum allocation for strategy without violating constraints.

        Args:
            strategy_row: Strategy data
            remaining_capital: Unallocated capital
            token_exposures: Current token exposures {token_contract: usd_amount}
            protocol_exposures: Current protocol exposures {protocol: usd_amount}
            constraints: Constraint settings
            portfolio_size: Total portfolio size

        Returns:
            Maximum USD amount that can be allocated to this strategy
        """
        max_amount = remaining_capital

        # Check token exposure constraints (all 3 tokens)
        # Use token-specific override if available, otherwise use default limit
        default_token_limit = portfolio_size * constraints['token_exposure_limit']
        token_overrides = constraints.get('token_exposure_overrides', {})

        # Get borrow weights (token1 always 1.0, token2/3 from strategy)
        weights = {
            1: 1.0,  # Token1 always has weight 1.0
            2: strategy_row.get('borrow_weight_2a', 1.0),
            3: strategy_row.get('borrow_weight_3b', 1.0)
        }

        for token_num in [1, 2, 3]:
            token_contract = strategy_row[f'token{token_num}_contract']
            token_symbol = strategy_row[f'token{token_num}']
            weight = weights[token_num]

            # Check if token has specific override
            if token_symbol in token_overrides:
                token_limit = portfolio_size * token_overrides[token_symbol]
            else:
                token_limit = default_token_limit

            current_exposure = token_exposures.get(token_contract, 0.0)
            remaining_room = token_limit - current_exposure

            # Divide by weight to get max allocation amount
            # e.g., if weight=1.3 and room=$13k, max allocation=$10k
            max_allocation_for_this_token = remaining_room / weight if weight > 0 else remaining_room
            max_amount = min(max_amount, max_allocation_for_this_token)

        # Check protocol exposure constraints (both protocols)
        protocol_limit = portfolio_size * constraints['protocol_exposure_limit']

        for protocol in [strategy_row['protocol_a'], strategy_row['protocol_b']]:
            current_exposure = protocol_exposures.get(protocol, 0.0)
            remaining_room = protocol_limit - current_exposure
            max_amount = min(max_amount, remaining_room)

        return max(0.0, max_amount)  # Ensure non-negative

    def _update_exposures(
        self,
        strategy_row: pd.Series,
        allocation_amount: float,
        token_exposures: Dict[str, float],
        protocol_exposures: Dict[str, float]
    ):
        """
        Update exposure tracking after allocating to a strategy.

        Token exposure = allocation_amount * borrow_weight for that token.
        For example, $10k allocation with token2 weight 1.3 = $13k token2 exposure.

        Args:
            strategy_row: Strategy data
            allocation_amount: USD amount allocated
            token_exposures: Token exposure dict to update
            protocol_exposures: Protocol exposure dict to update
        """
        # Get borrow weights (token1 always 1.0, token2/3 from strategy)
        weights = {
            1: 1.0,  # Token1 always has weight 1.0
            2: strategy_row.get('borrow_weight_2a', 1.0),
            3: strategy_row.get('borrow_weight_3b', 1.0)
        }

        # Update token exposures (multiply by weight)
        for token_num in [1, 2, 3]:
            token_contract = strategy_row[f'token{token_num}_contract']
            weight = weights[token_num]
            exposure = allocation_amount * weight
            token_exposures[token_contract] = (
                token_exposures.get(token_contract, 0.0) + exposure
            )

        # Update protocol exposures
        for protocol in [strategy_row['protocol_a'], strategy_row['protocol_b']]:
            protocol_exposures[protocol] = (
                protocol_exposures.get(protocol, 0.0) + allocation_amount
            )

    def select_portfolio(
        self,
        portfolio_size: float,
        constraints: Dict = None
    ) -> pd.DataFrame:
        """
        Select optimal portfolio using greedy algorithm with constraints.

        Algorithm:
        1. Filter strategies by min_confidence
        2. Calculate blended_apr (weighted by user APR weights)
        3. Calculate adjusted_apr (apply stablecoin penalty)
        4. Sort by adjusted_apr (descending)
        5. Greedily allocate respecting constraints

        Args:
            portfolio_size: Total USD to allocate
            constraints: Constraint settings (uses defaults if None)

        Returns:
            DataFrame with selected strategies and allocation amounts.
            Includes columns:
            - All original strategy columns
            - blended_apr: Weighted APR before penalty
            - stablecoin_multiplier: Applied multiplier
            - adjusted_apr: Final APR used for ranking
            - stablecoins_in_strategy: List of stablecoins in strategy
            - allocation_usd: USD amount allocated to this strategy
        """
        if constraints is None:
            constraints = DEFAULT_ALLOCATION_CONSTRAINTS.copy()

        # Filter by confidence
        if 'confidence' not in self.strategies.columns:
            # If confidence not calculated, assume all pass
            strategies = self.strategies.copy()
        else:
            min_confidence = constraints.get('min_apy_confidence', 0.0)
            strategies = self.strategies[
                self.strategies['confidence'] >= min_confidence
            ].copy()

        if strategies.empty:
            return pd.DataFrame()

        # Calculate blended APR
        apr_weights = constraints['apr_weights']
        strategies['blended_apr'] = strategies.apply(
            lambda row: self.calculate_blended_apr(row, apr_weights),
            axis=1
        )

        # Calculate adjusted APR with stablecoin preferences
        stablecoin_prefs = constraints['stablecoin_preferences']

        adjusted_results = strategies.apply(
            lambda row: self.calculate_adjusted_apr(
                row,
                row['blended_apr'],
                stablecoin_prefs
            ),
            axis=1
        )

        # Unpack results into separate columns
        strategies['stablecoin_multiplier'] = adjusted_results.apply(
            lambda x: x['stablecoin_multiplier']
        )
        strategies['adjusted_apr'] = adjusted_results.apply(
            lambda x: x['adjusted_apr']
        )
        strategies['stablecoins_in_strategy'] = adjusted_results.apply(
            lambda x: x['stablecoins_in_strategy']
        )

        # Sort by ADJUSTED APR (not blended APR)
        strategies = strategies.sort_values('adjusted_apr', ascending=False)

        # Greedy allocation
        selected = []
        allocated_capital = 0.0
        token_exposures = {}
        protocol_exposures = {}
        max_strategies = constraints.get('max_strategies', 10)

        for idx, strategy in strategies.iterrows():
            if len(selected) >= max_strategies:
                break

            # Calculate max allocation for this strategy
            max_amount = self._calculate_max_allocation(
                strategy,
                portfolio_size - allocated_capital,
                token_exposures,
                protocol_exposures,
                constraints,
                portfolio_size
            )

            # If we can allocate at least something, add strategy
            if max_amount > 0:
                strategy_dict = strategy.to_dict()
                strategy_dict['allocation_usd'] = max_amount
                selected.append(strategy_dict)

                allocated_capital += max_amount
                self._update_exposures(
                    strategy,
                    max_amount,
                    token_exposures,
                    protocol_exposures
                )

        return pd.DataFrame(selected) if selected else pd.DataFrame()

    def calculate_portfolio_exposures(
        self,
        portfolio_df: pd.DataFrame,
        portfolio_size: float
    ) -> Tuple[Dict, Dict]:
        """
        Calculate token and protocol exposures from portfolio.

        Args:
            portfolio_df: Portfolio with allocation_usd column
            portfolio_size: Total portfolio size in USD (not just allocated amount)

        Returns:
            Tuple of (token_exposures, protocol_exposures)
            - token_exposures: {token_contract: {symbol, usd, pct}}
            - protocol_exposures: {protocol: {usd, pct}}
        """
        if portfolio_df.empty:
            return {}, {}

        token_exposures = {}
        protocol_exposures = {}

        for _, row in portfolio_df.iterrows():
            allocation = row['allocation_usd']

            # Aggregate token exposures - ONLY COUNT LENDING, NOT BORROWING
            # In a recursive strategy:
            # - Token1: Lent on protocol A (count this)
            # - Token2: Borrowed on A, Lent on B (only count lend amount)
            # - Token3: Borrowed on B (don't count, no lending exposure)

            # Token1 - always lent
            token1_contract = row['token1_contract']
            token1_symbol = row['token1']
            if token1_contract not in token_exposures:
                token_exposures[token1_contract] = {
                    'symbol': token1_symbol,
                    'usd': 0.0,
                    'pct': 0.0
                }
            token_exposures[token1_contract]['usd'] += allocation

            # Token2 - lent on protocol B
            token2_contract = row['token2_contract']
            token2_symbol = row['token2']
            if token2_contract not in token_exposures:
                token_exposures[token2_contract] = {
                    'symbol': token2_symbol,
                    'usd': 0.0,
                    'pct': 0.0
                }
            token_exposures[token2_contract]['usd'] += allocation

            # Token3 - only borrowed, not lent (no exposure counted)

            # Aggregate protocol exposures
            for protocol in [row['protocol_a'], row['protocol_b']]:
                if protocol not in protocol_exposures:
                    protocol_exposures[protocol] = {'usd': 0.0, 'pct': 0.0}
                protocol_exposures[protocol]['usd'] += allocation

        # Calculate percentages against total portfolio size (not just allocated amount)
        for contract in token_exposures:
            token_exposures[contract]['pct'] = (
                token_exposures[contract]['usd'] / portfolio_size if portfolio_size > 0 else 0.0
            )

        for protocol in protocol_exposures:
            protocol_exposures[protocol]['pct'] = (
                protocol_exposures[protocol]['usd'] / portfolio_size if portfolio_size > 0 else 0.0
            )

        return token_exposures, protocol_exposures
