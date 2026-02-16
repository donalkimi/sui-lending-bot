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
    ) -> Tuple[float, Dict]:
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
            Tuple of (max_amount, constraint_info)
            - max_amount: Maximum USD amount that can be allocated to this strategy
            - constraint_info: Dict with details about which constraint limited allocation
        """
        max_amount = remaining_capital
        constraint_info = {
            'limiting_constraint': 'remaining_capital',
            'limiting_value': remaining_capital,
            'token_constraints': [],
            'protocol_constraints': []
        }

        # Check strategy max size constraint (liquidity limit)
        try:
            strategy_max = strategy_row['max_size']
            if pd.notna(strategy_max) and strategy_max < max_amount:
                max_amount = strategy_max
                constraint_info['limiting_constraint'] = 'strategy_max_size'
                constraint_info['limiting_value'] = strategy_max
        except KeyError as e:
            raise KeyError(
                f"Column 'max_size' not found in strategy_row. "
                f"Available columns: {list(strategy_row.index)}"
            ) from e

        # Check token exposure constraints (all 3 tokens)
        # Use token-specific override if available, otherwise use default limit

        # Get constraint keys - fail loudly if missing
        if 'token2_exposure_limit' not in constraints and 'token_exposure_limit' not in constraints:
            raise KeyError("Missing required constraint: 'token2_exposure_limit' or 'token_exposure_limit'")
        if 'stablecoin_exposure_limit' not in constraints:
            raise KeyError("Missing required constraint: 'stablecoin_exposure_limit'")

        token2_limit_pct = constraints.get('token2_exposure_limit', constraints['token_exposure_limit'])
        stablecoin_limit_pct = constraints['stablecoin_exposure_limit']

        # Convert -1 (unlimited) to infinity
        if stablecoin_limit_pct < 0:
            stablecoin_limit = float('inf')
        else:
            stablecoin_limit = portfolio_size * stablecoin_limit_pct

        default_token2_limit = portfolio_size * token2_limit_pct
        token_overrides = constraints.get('token_exposure_overrides', {})

        # Get position weights for exposure calculation
        # See allocator_reference.md for formulas
        from config.stablecoins import STABLECOIN_SYMBOLS

        l_a = strategy_row.get('l_a', 1.0)
        b_a = strategy_row.get('borrow_weight_2A', 1.0)
        b_b = strategy_row.get('borrow_weight_3B', 1.0)

        # Calculate exposure weights for each token
        # Stablecoins use net lending formula: +L_A for token1, -B_B for token3
        # Non-stablecoins (token2) use de-leveraged formula: B_A / L_A
        for token_num in [1, 2, 3]:
            token_contract = strategy_row[f'token{token_num}_contract']
            token_symbol = strategy_row[f'token{token_num}']

            # Determine exposure weight based on token position and type
            is_stablecoin = token_symbol in STABLECOIN_SYMBOLS

            if token_num == 1:
                # Token1: Lent to Protocol A
                weight = l_a if is_stablecoin else 1.0
            elif token_num == 2:
                # Token2: De-leveraged exposure B_A / L_A (applies to all tokens)
                weight = b_a / l_a if l_a > 0 else 1.0
            else:  # token_num == 3
                # Token3: Borrowed from Protocol B
                # Stablecoins: negative weight (borrowed position)
                # Non-stablecoins: standard borrow weight
                weight = -b_b if is_stablecoin else b_b

            # Determine token limit based on type and position
            if token_symbol in token_overrides:
                # Specific override for this token
                token_limit = portfolio_size * token_overrides[token_symbol]
            elif is_stablecoin:
                # Stablecoin: use stablecoin limit (can be infinite)
                token_limit = stablecoin_limit
            else:
                # Non-stablecoin: use token2 limit
                token_limit = default_token2_limit

            current_exposure = token_exposures.get(token_contract, 0.0)
            remaining_room = token_limit - current_exposure

            # For negative weights (stablecoin borrows), exposure increases as we allocate
            # For positive weights, standard calculation applies
            if weight < 0:
                # Negative weight: borrowed position
                # We want |current_exposure + allocation × weight| ≤ token_limit
                # This means: allocation × |weight| ≤ token_limit - |current_exposure|
                max_allocation_for_this_token = (token_limit - abs(current_exposure)) / abs(weight) if weight != 0 else remaining_room
            elif weight > 0:
                # Positive weight: lent position (standard case)
                max_allocation_for_this_token = remaining_room / weight if weight > 0 else remaining_room
            else:
                # Weight is zero: no constraint from this token
                max_allocation_for_this_token = float('inf')

            # Track token constraint info
            token_constraint = {
                'token': token_symbol,
                'position': token_num,
                'weight': weight,
                'current_exposure': current_exposure,
                'limit': token_limit,
                'remaining_room': remaining_room,
                'max_from_token': max_allocation_for_this_token,
                'is_stablecoin': is_stablecoin
            }
            constraint_info['token_constraints'].append(token_constraint)

            if max_allocation_for_this_token < max_amount:
                max_amount = max_allocation_for_this_token
                constraint_info['limiting_constraint'] = f'token_{token_num}_{token_symbol}'
                constraint_info['limiting_value'] = max_allocation_for_this_token

        # Check protocol exposure constraints
        # Protocol A: full allocation (weight = 1.0)
        # Protocol B: de-leveraged (weight = L_B / L_A)
        # See allocator_reference.md for formula
        protocol_limit = portfolio_size * constraints['protocol_exposure_limit']

        # Protocol A constraint
        protocol_a = strategy_row['protocol_a']
        current_exposure_a = protocol_exposures.get(protocol_a, 0.0)
        remaining_room_a = protocol_limit - current_exposure_a

        protocol_a_constraint = {
            'protocol': protocol_a,
            'position': 'A',
            'weight': 1.0,
            'current_exposure': current_exposure_a,
            'limit': protocol_limit,
            'remaining_room': remaining_room_a,
            'max_from_protocol': remaining_room_a
        }
        constraint_info['protocol_constraints'].append(protocol_a_constraint)

        if remaining_room_a < max_amount:
            max_amount = remaining_room_a
            constraint_info['limiting_constraint'] = f'protocol_A_{protocol_a}'
            constraint_info['limiting_value'] = remaining_room_a

        # Protocol B constraint (de-leveraged by L_B / L_A)
        protocol_b = strategy_row['protocol_b']
        l_b = strategy_row.get('l_b', 1.0)
        protocol_b_weight = l_b / l_a if l_a > 0 else 1.0

        current_exposure_b = protocol_exposures.get(protocol_b, 0.0)
        remaining_room_b = protocol_limit - current_exposure_b
        max_allocation_for_protocol_b = remaining_room_b / protocol_b_weight if protocol_b_weight > 0 else remaining_room_b

        protocol_b_constraint = {
            'protocol': protocol_b,
            'position': 'B',
            'weight': protocol_b_weight,
            'current_exposure': current_exposure_b,
            'limit': protocol_limit,
            'remaining_room': remaining_room_b,
            'max_from_protocol': max_allocation_for_protocol_b
        }
        constraint_info['protocol_constraints'].append(protocol_b_constraint)

        if max_allocation_for_protocol_b < max_amount:
            max_amount = max_allocation_for_protocol_b
            constraint_info['limiting_constraint'] = f'protocol_B_{protocol_b}'
            constraint_info['limiting_value'] = max_allocation_for_protocol_b

        # Check max single allocation % constraint
        max_single_pct = constraints.get('max_single_allocation_pct', 1.0)  # Default: unlimited (100%)
        max_single_amount = portfolio_size * max_single_pct

        constraint_info['max_single_constraint'] = {
            'limit_pct': max_single_pct,
            'limit_amount': max_single_amount,
            'max_from_single': max_single_amount
        }

        if max_single_amount < max_amount:
            max_amount = max_single_amount
            constraint_info['limiting_constraint'] = 'max_single_allocation'
            constraint_info['limiting_value'] = max_single_amount

        return max(0.0, max_amount), constraint_info  # Ensure non-negative

    def _update_exposures(
        self,
        strategy_row: pd.Series,
        allocation_amount: float,
        token_exposures: Dict[str, float],
        protocol_exposures: Dict[str, float]
    ):
        """
        Update exposure tracking after allocating to a strategy.

        Exposure calculation depends on token type and position:
        - Stablecoins: Net lending formula (+L_A for token1, -B_B for token3)
        - Non-stablecoins (token2): De-leveraged formula (B_A / L_A)

        See allocator_reference.md for detailed formulas.

        Args:
            strategy_row: Strategy data
            allocation_amount: USD amount allocated
            token_exposures: Token exposure dict to update
            protocol_exposures: Protocol exposure dict to update
        """
        # Get position weights
        from config.stablecoins import STABLECOIN_SYMBOLS

        l_a = strategy_row.get('l_a', 1.0)
        b_a = strategy_row.get('borrow_weight_2A', 1.0)
        b_b = strategy_row.get('borrow_weight_3B', 1.0)

        # Update token exposures using appropriate weight for each position
        for token_num in [1, 2, 3]:
            token_contract = strategy_row[f'token{token_num}_contract']
            token_symbol = strategy_row[f'token{token_num}']

            # Determine exposure weight based on token position and type
            is_stablecoin = token_symbol in STABLECOIN_SYMBOLS

            if token_num == 1:
                # Token1: Lent to Protocol A
                weight = l_a if is_stablecoin else 1.0
            elif token_num == 2:
                # Token2: De-leveraged exposure B_A / L_A
                weight = b_a / l_a if l_a > 0 else 1.0
            else:  # token_num == 3
                # Token3: Borrowed from Protocol B
                # Stablecoins: negative weight (net borrowing)
                weight = -b_b if is_stablecoin else b_b

            exposure = allocation_amount * weight
            token_exposures[token_contract] = (
                token_exposures.get(token_contract, 0.0) + exposure
            )

        # Update protocol exposures
        # Protocol A: full allocation (weight = 1.0)
        # Protocol B: de-leveraged (weight = L_B / L_A)
        protocol_a = strategy_row['protocol_a']
        protocol_b = strategy_row['protocol_b']
        l_b = strategy_row.get('l_b', 1.0)

        # Protocol A gets full allocation
        protocol_exposures[protocol_a] = (
            protocol_exposures.get(protocol_a, 0.0) + allocation_amount
        )

        # Protocol B gets de-leveraged allocation
        protocol_b_weight = l_b / l_a if l_a > 0 else 1.0
        protocol_exposures[protocol_b] = (
            protocol_exposures.get(protocol_b, 0.0) + (allocation_amount * protocol_b_weight)
        )

    def select_portfolio(
        self,
        portfolio_size: float,
        constraints: Dict = None,
        enable_iterative_updates: bool = True,
        allowed_strategy_types: Optional[List[str]] = None  # NEW: Multi-strategy support
    ) -> Tuple[pd.DataFrame, List[Dict]]:
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
            enable_iterative_updates: Whether to use iterative liquidity updates
            allowed_strategy_types: Optional list of strategy types to include (default: all types)

        Returns:
            Tuple of (portfolio_df, debug_info)
            - portfolio_df: DataFrame with selected strategies and allocation amounts
              Includes columns:
              - All original strategy columns
              - blended_apr: Weighted APR before penalty
              - stablecoin_multiplier: Applied multiplier
              - adjusted_apr: Final APR used for ranking
              - stablecoins_in_strategy: List of stablecoins in strategy
              - allocation_usd: USD amount allocated to this strategy
            - debug_info: List of dicts with allocation debugging details
        """
        if constraints is None:
            constraints = DEFAULT_ALLOCATION_CONSTRAINTS.copy()

        # NEW: Filter by strategy type if specified
        if allowed_strategy_types is not None:
            if 'strategy_type' in self.strategies.columns:
                self.strategies = self.strategies[
                    self.strategies['strategy_type'].isin(allowed_strategy_types)
                ]
                print(f"[ALLOCATOR] Filtered to strategy types: {allowed_strategy_types}")

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
            return pd.DataFrame(), []

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

        # NEW: Setup iterative liquidity updates
        if enable_iterative_updates:
            available_borrow = self._prepare_available_borrow_matrix(strategies)
        else:
            available_borrow = None

        # Greedy allocation
        selected = []
        debug_info = []
        allocated_capital = 0.0
        token_exposures = {}
        protocol_exposures = {}
        max_strategies = constraints.get('max_strategies', 10)

        for idx, strategy in strategies.iterrows():
            if len(selected) >= max_strategies:
                break

            # Recalculate max_size for CURRENT strategy using current available_borrow matrix
            if enable_iterative_updates and available_borrow is not None:
                strategy = strategy.copy()

                # Recalculate max_size based on current available_borrow
                updated_max_size = self._calculate_max_size_from_available_borrow(
                    strategy,
                    available_borrow
                )
                strategy['max_size'] = updated_max_size

            # Capture state before allocation
            remaining_capital = portfolio_size - allocated_capital

            # Calculate max allocation for this strategy
            max_amount, constraint_info = self._calculate_max_allocation(
                strategy,
                remaining_capital,
                token_exposures,
                protocol_exposures,
                constraints,
                portfolio_size
            )

            # Build debug record
            debug_record = {
                'strategy_num': len(debug_info) + 1,
                'token1': strategy['token1'],
                'token2': strategy['token2'],
                'token3': strategy['token3'],
                'protocol_a': strategy['protocol_a'],
                'protocol_b': strategy['protocol_b'],
                'adjusted_apr': strategy['adjusted_apr'],
                'remaining_capital': remaining_capital,
                'max_amount': max_amount,
                'allocated': max_amount > 0,
                'constraint_info': constraint_info,
                'token_exposures_before': token_exposures.copy(),
                'protocol_exposures_before': protocol_exposures.copy(),
                'max_size_before': strategy.get('max_size', None)
            }

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

                # Update available_borrow matrix after allocation
                if enable_iterative_updates and available_borrow is not None:
                    # Update liquidity matrix
                    self._update_available_borrow(
                        strategy,
                        max_amount,
                        available_borrow
                    )

                # Capture state after allocation
                debug_record['token_exposures_after'] = token_exposures.copy()
                debug_record['protocol_exposures_after'] = protocol_exposures.copy()
                debug_record['max_size_after'] = strategy.get('max_size', None) if enable_iterative_updates else None
                debug_record['available_borrow_snapshot'] = available_borrow.copy() if enable_iterative_updates and available_borrow is not None else None
            else:
                # Not allocated, exposures unchanged
                debug_record['token_exposures_after'] = token_exposures.copy()
                debug_record['protocol_exposures_after'] = protocol_exposures.copy()
                debug_record['max_size_after'] = None
                debug_record['available_borrow_snapshot'] = None

            debug_info.append(debug_record)

        return (pd.DataFrame(selected) if selected else pd.DataFrame()), debug_info

    def calculate_portfolio_exposures(
        self,
        portfolio_df: pd.DataFrame,
        portfolio_size: float
    ) -> Tuple[Dict, Dict]:
        """
        Calculate token and protocol exposures from portfolio.

        Uses updated exposure formulas (see allocator_reference.md):
        - Stablecoins: Net lending formula (+L_A for token1, -B_B for token3)
        - Non-stablecoins (token2): De-leveraged formula (B_A / L_A)

        Args:
            portfolio_df: Portfolio with allocation_usd column
            portfolio_size: Total portfolio size in USD (not just allocated amount)

        Returns:
            Tuple of (token_exposures, protocol_exposures)
            - token_exposures: {token_contract: {symbol, usd, pct, is_stablecoin}}
            - protocol_exposures: {protocol: {usd, pct}}
        """
        if portfolio_df.empty:
            return {}, {}

        from config.stablecoins import STABLECOIN_SYMBOLS

        token_exposures = {}
        protocol_exposures = {}

        for _, row in portfolio_df.iterrows():
            allocation = row['allocation_usd']

            # Get position weights
            l_a = row.get('l_a', 1.0)
            b_a = row.get('borrow_weight_2A', 1.0)
            l_b = row.get('l_b', 1.0)
            b_b = row.get('borrow_weight_3B', 1.0)

            # Process each token using appropriate exposure formula
            for token_num in [1, 2, 3]:
                token_contract = row[f'token{token_num}_contract']
                token_symbol = row[f'token{token_num}']

                # Initialize token entry if needed
                if token_contract not in token_exposures:
                    token_exposures[token_contract] = {
                        'symbol': token_symbol,
                        'usd': 0.0,
                        'pct': 0.0,
                        'is_stablecoin': token_symbol in STABLECOIN_SYMBOLS
                    }

                # Calculate exposure contribution based on token position and type
                is_stablecoin = token_symbol in STABLECOIN_SYMBOLS

                if token_num == 1:
                    # Token1: Lent to Protocol A
                    weight = l_a if is_stablecoin else l_a  # Both use l_a for now
                elif token_num == 2:
                    # Token2: De-leveraged exposure B_A / L_A
                    weight = (b_a / l_a) if l_a > 0 else 1.0
                else:  # token_num == 3
                    # Token3: Borrowed from Protocol B
                    # Stablecoins: negative weight (net borrowing)
                    weight = -b_b if is_stablecoin else 0.0  # Non-stablecoins don't count token3

                exposure_contribution = allocation * weight
                token_exposures[token_contract]['usd'] += exposure_contribution

            # Aggregate protocol exposures
            # Protocol A: full allocation (normalized)
            # Protocol B: de-leveraged (L_B / L_A)
            # See allocator_reference.md for formula
            protocol_a = row['protocol_a']
            protocol_b = row['protocol_b']

            # Protocol A: full allocation (weight = 1.0)
            if protocol_a not in protocol_exposures:
                protocol_exposures[protocol_a] = {'usd': 0.0, 'pct': 0.0}
            protocol_exposures[protocol_a]['usd'] += allocation

            # Protocol B: de-leveraged allocation (weight = L_B / L_A)
            protocol_b_weight = l_b / l_a if l_a > 0 else 1.0
            if protocol_b not in protocol_exposures:
                protocol_exposures[protocol_b] = {'usd': 0.0, 'pct': 0.0}
            protocol_exposures[protocol_b]['usd'] += allocation * protocol_b_weight

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

    @staticmethod
    def _prepare_available_borrow_matrix(strategies: pd.DataFrame) -> pd.DataFrame:
        """
        Create Token×Protocol matrix from strategies DataFrame.

        Extracts available_borrow data from strategies and pivots to matrix format
        for efficient updates during allocation.

        Args:
            strategies: Strategy data with available_borrow_2a/3b fields

        Returns:
            DataFrame with Token symbols as index, Protocol names as columns,
            available_borrow USD values as data
        """
        # Collect all unique tokens and protocols
        tokens_set = set()
        protocols_set = set()

        for _, row in strategies.iterrows():
            # Token2 and its protocol
            if pd.notna(row.get('token2')) and pd.notna(row.get('protocol_a')):
                tokens_set.add(row['token2'])
                protocols_set.add(row['protocol_a'])

            # Token3 and its protocol (skip if None for unlevered strategies)
            if pd.notna(row.get('token3')) and pd.notna(row.get('protocol_b')):
                tokens_set.add(row['token3'])
                protocols_set.add(row['protocol_b'])

        # Create empty DataFrame with Token index and Protocol columns
        tokens_list = sorted(list(tokens_set))
        protocols_list = sorted(list(protocols_set))
        matrix = pd.DataFrame(index=tokens_list, columns=protocols_list, dtype=float)
        matrix[:] = 0.0  # Initialize with zeros

        # Populate matrix with available_borrow values
        # Use max() aggregation when multiple strategies report different values
        # for same token/protocol (take most optimistic)
        for _, row in strategies.iterrows():
            # Process token2 on protocol_a
            token2 = row.get('token2')
            protocol_a = row.get('protocol_a')
            available_2a = row.get('available_borrow_2a', 0.0)

            if pd.notna(token2) and pd.notna(protocol_a) and pd.notna(available_2a):
                current_value = matrix.loc[token2, protocol_a]
                matrix.loc[token2, protocol_a] = max(current_value, float(available_2a))

            # Process token3 on protocol_b (skip if None)
            token3 = row.get('token3')
            protocol_b = row.get('protocol_b')
            available_3b = row.get('available_borrow_3b', 0.0)

            if pd.notna(token3) and pd.notna(protocol_b) and pd.notna(available_3b):
                current_value = matrix.loc[token3, protocol_b]
                matrix.loc[token3, protocol_b] = max(current_value, float(available_3b))

        return matrix

    def _update_available_borrow(
        self,
        strategy_row: pd.Series,
        allocation_amount: float,
        available_borrow: pd.DataFrame
    ) -> None:
        """
        Update available_borrow matrix after allocating to a strategy (in-place).

        When we allocate capital to a strategy, we borrow tokens from protocols,
        reducing available liquidity for future allocations.

        Args:
            strategy_row: Strategy with token2/3, protocol_a/b, borrow_weight_2A/3B
            allocation_amount: USD amount allocated to this strategy
            available_borrow: Token×Protocol matrix (modified in-place)
        """
        # Extract token2 and protocol_a (leg 2A)
        token2 = strategy_row.get('token2')
        protocol_a = strategy_row.get('protocol_a')
        b_a = strategy_row.get('borrow_weight_2A', strategy_row.get('b_a', 0.0))

        # Calculate borrow amount for token2 on protocol_a
        borrow_2A = allocation_amount * b_a

        # Update matrix for token2 (if exists)
        if pd.notna(token2) and pd.notna(protocol_a) and b_a > 0:
            try:
                current_value = available_borrow.loc[token2, protocol_a]
                new_value = current_value - borrow_2A

                # Clamp to 0 to prevent negative liquidity
                available_borrow.loc[token2, protocol_a] = max(0.0, new_value)

                # Warn if over-borrowed
                if new_value < 0:
                    print(f"⚠️  Warning: {token2} on {protocol_a} over-borrowed by ${abs(new_value):.2f}")
            except KeyError:
                print(f"⚠️  Warning: {token2} on {protocol_a} not found in available_borrow matrix. Skipping update.")

        # Extract token3 and protocol_b (leg 3B)
        token3 = strategy_row.get('token3')
        protocol_b = strategy_row.get('protocol_b')
        b_b = strategy_row.get('borrow_weight_3B', strategy_row.get('b_b', 0.0))

        # Calculate borrow amount for token3 on protocol_b
        borrow_3B = allocation_amount * b_b

        # Update matrix for token3 (if exists - skip for unlevered strategies)
        if pd.notna(token3) and pd.notna(protocol_b) and b_b > 0:
            try:
                current_value = available_borrow.loc[token3, protocol_b]
                new_value = current_value - borrow_3B

                # Clamp to 0 to prevent negative liquidity
                available_borrow.loc[token3, protocol_b] = max(0.0, new_value)

                # Warn if over-borrowed
                if new_value < 0:
                    print(f"⚠️  Warning: {token3} on {protocol_b} over-borrowed by ${abs(new_value):.2f}")
            except KeyError:
                print(f"⚠️  Warning: {token3} on {protocol_b} not found in available_borrow matrix. Skipping update.")

    def _calculate_max_size_from_available_borrow(
        self,
        strategy: pd.Series,
        available_borrow: pd.DataFrame
    ) -> float:
        """
        Calculate max_size for a strategy using current available_borrow matrix.

        Called once per strategy at the start of its allocation attempt.
        Uses the SAME logic as position_calculator.py, but applied to
        current liquidity state instead of original liquidity.

        Formula:
            max_size = min(
                available_borrow[token2][protocol_a] / b_a,
                available_borrow[token3][protocol_b] / b_b
            )

        Args:
            strategy: Strategy row
            available_borrow: Current liquidity matrix (tokens × protocols)

        Returns:
            Updated max_size constraint (USD)

        Complexity: O(1) - constant time lookup and calculation
        """
        try:
            # Extract strategy parameters
            token2 = strategy['token2']
            token3 = strategy.get('token3', None)
            protocol_a = strategy['protocol_a']
            protocol_b = strategy.get('protocol_b', None)

            # Extract borrow weights - MUST exist in strategy DataFrame
            # Follow explicit error handling pattern (design_notes.md Section 13)
            try:
                b_a = strategy['b_a']
            except KeyError:
                print(f"⚠️  ERROR: Column 'b_a' not found in strategy")
                print(f"   Available columns: {list(strategy.index)}")
                print(f"   Strategy: {strategy.get('token2', 'unknown')}/{strategy.get('protocol_a', 'unknown')}")
                return 0.0

            try:
                b_b = strategy['b_b']
            except KeyError:
                print(f"⚠️  ERROR: Column 'b_b' not found in strategy")
                print(f"   Available columns: {list(strategy.index)}")
                print(f"   Strategy: {strategy.get('token2', 'unknown')}/{strategy.get('protocol_a', 'unknown')}")
                return 0.0

            # Calculate constraint from token2 on protocol_a
            if token2 in available_borrow.index and protocol_a in available_borrow.columns:
                available_2a = available_borrow.loc[token2, protocol_a]
            else:
                available_2a = 0.0

            if b_a > 0:
                constraint_2a = available_2a / b_a
            else:
                constraint_2a = float('inf')

            # Calculate constraint from token3 on protocol_b (if levered)
            if token3 and protocol_b:
                if token3 in available_borrow.index and protocol_b in available_borrow.columns:
                    available_3b = available_borrow.loc[token3, protocol_b]
                else:
                    available_3b = 0.0

                if b_b > 0:
                    constraint_3b = available_3b / b_b
                else:
                    constraint_3b = float('inf')
            else:
                constraint_3b = float('inf')

            # Max size is minimum of constraints
            max_size = min(constraint_2a, constraint_3b)

            return max(0.0, max_size)

        except Exception as e:
            print(f"⚠️  Warning: Failed to recalculate max_size for strategy: {e}")
            # Return 0 to be conservative (don't allocate if can't calculate)
            return 0.0

    def _recalculate_max_sizes(
        self,
        strategies: pd.DataFrame,
        available_borrow: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Recalculate max_size for all strategies using current available_borrow.

        Uses the same formula as position_calculator.py:
        max_size = min(available_borrow_2A / b_a, available_borrow_3B / b_b)

        Args:
            strategies: DataFrame with strategy data (modified in-place)
            available_borrow: Current Token×Protocol liquidity matrix

        Returns:
            Updated strategies DataFrame (also modified in-place)
        """
        # Calculate new max_sizes for all strategies
        new_max_sizes = []

        for idx, row in strategies.iterrows():
            # Extract token2 and protocol_a
            token2 = row.get('token2')
            protocol_a = row.get('protocol_a')
            b_a = row.get('borrow_weight_2A', row.get('b_a', 0.0))

            # Extract token3 and protocol_b
            token3 = row.get('token3')
            protocol_b = row.get('protocol_b')
            b_b = row.get('borrow_weight_3B', row.get('b_b', 0.0))

            # Get current available_borrow for token2 on protocol_a
            try:
                available_2A = available_borrow.loc[token2, protocol_a] if pd.notna(token2) and pd.notna(protocol_a) else 0.0
            except KeyError:
                available_2A = 0.0

            # Get current available_borrow for token3 on protocol_b
            try:
                available_3B = available_borrow.loc[token3, protocol_b] if pd.notna(token3) and pd.notna(protocol_b) else 0.0
            except KeyError:
                available_3B = 0.0

            # Calculate max_size constraints
            # Handle division by zero: if b_a or b_b = 0, constraint is infinite
            if b_a > 0:
                constraint_2A = available_2A / b_a
            else:
                constraint_2A = float('inf')

            if b_b > 0:
                constraint_3B = available_3B / b_b
            else:
                constraint_3B = float('inf')

            # Take minimum (most restrictive constraint)
            max_size = min(constraint_2A, constraint_3B)
            new_max_sizes.append(max_size)

        # Update max_size column
        strategies['max_size'] = new_max_sizes

        return strategies
