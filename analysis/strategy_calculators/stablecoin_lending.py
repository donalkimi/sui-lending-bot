"""
Stablecoin lending calculator (1-leg strategy).

Simplest strategy: just lend a stablecoin in one protocol.
No borrowing, no leverage, no liquidation risk.
"""

import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)


class StablecoinLendingCalculator(StrategyCalculatorBase):
    """
    Stablecoin lending calculator (1-leg strategy).

    Mechanics:
        - Lend stablecoin in one protocol
        - No borrowing, no cross-protocol activity
        - Just earn base lending APR + rewards

    Position multipliers:
        - L_A = 1.0 (lend $1 for every $1 deployed)
        - B_A = 0.0 (no borrowing)
        - L_B = 0.0 (no second lending)
        - B_B = 0.0 (no second borrowing)

    Risk profile:
        - No liquidation risk
        - No rebalancing needed
        - No price exposure (stablecoin only)
        - Protocol risk only
    """

    def get_strategy_type(self) -> str:
        return 'stablecoin_lending'

    def get_required_legs(self) -> int:
        return 1

    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers (trivial for stablecoin lending).

        Returns:
            Dict with l_a=1.0, all others=0.0
        """
        return {
            'l_a': 1.0,
            'b_a': 0.0,
            'l_b': 0.0,
            'b_b': 0.0  # Consistent with other strategies (use 0.0 not None)
        }

    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for stablecoin lending.

        APR = lend_total_apr_1A (base + reward already combined in database)

        Args:
            positions: Not used (only one leg, no multiplier effects)
            rates: Dict with 'lend_total_apr_1A'
            fees: Not used (no borrowing)

        Returns:
            Net APR as decimal (e.g., 0.04 = 4%)

        Raises:
            ValueError: If lend_total_apr_1A is missing
        """
        lend_total_apr = rates.get('lend_total_apr_1A')

        # Validate data quality - fail fast if missing
        if lend_total_apr is None:
            raise ValueError(
                "Missing lend_total_apr_1A for stablecoin lending strategy. "
                "This is a critical data quality issue."
            )

        return lend_total_apr

    def calculate_gross_apr(self,
                           positions: Dict[str, float],
                           rates: Dict[str, float]) -> float:
        """
        Calculate gross APR for stablecoin lending strategy.

        Formula:
            gross_apr = L_A × lend_total_apr_1A

        Note: No borrowing, so gross_apr = net_apr for stablecoin strategies.
        """
        l_a = positions['l_a']
        lend_total_1A = rates['lend_total_apr_1A']

        return l_a * lend_total_1A

    def analyze_strategy(self,
                        token1: str,
                        protocol_a: str,
                        lend_total_apr_1A: float,
                        price_1A: float,
                        **kwargs) -> Dict[str, Any]:
        """
        Analyze stablecoin lending strategy.

        Args:
            token1: Stablecoin symbol (e.g., 'USDC')
            protocol_a: Protocol name (e.g., 'navi')
            lend_total_apr_1A: Total lending APR (base + reward)
            price_1A: Token price (should be ~$1 for stablecoins)
            **kwargs: Ignored (other strategies need more params)

        Returns:
            Strategy dict with all required fields
        """
        # Validate inputs
        if lend_total_apr_1A is None:
            return {
                'valid': False,
                'error': 'Missing lend_total_apr_1A'
            }

        if price_1A is None or price_1A <= 0:
            return {
                'valid': False,
                'error': 'Invalid or missing price_1A'
            }

        # Calculate positions (trivial)
        positions = self.calculate_positions()

        # Calculate ALL fee-adjusted APRs using base class methods
        rates = {'lend_total_apr_1A': lend_total_apr_1A}
        fees = {
            'borrow_fee_2A': 0.0,
            'borrow_fee_3B': 0.0
        }
        fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(positions, rates, fees)

        # Extract all APR values from single source of truth
        apr_gross = fee_adjusted_aprs['apr_gross']
        apr_net = fee_adjusted_aprs['apr_net']
        apr5 = fee_adjusted_aprs['apr5']
        apr30 = fee_adjusted_aprs['apr30']
        apr90 = fee_adjusted_aprs['apr90']
        days_to_breakeven = fee_adjusted_aprs['days_to_breakeven']  # Will be 0.0 (no fees)

        # Extract contract from kwargs (passed by analyzer)
        token1_contract = kwargs.get('token1_contract')

        return {
            # Token and protocol info
            'token1': token1,
            'token2': token1,  # Stablecoin lending has no second token
            'token3': token1,  # Single leg strategy
            'protocol_a': protocol_a,
            'protocol_b': protocol_a,  # Single protocol strategy

            # Contracts (for historical chart queries)
            'token1_contract': token1_contract,
            'token2_contract': token1_contract,
            'token3_contract': token1_contract,

            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics (all equal for stablecoin since no fees)
            'apr_net': apr_net,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': float('inf'),  # No liquidation risk
            'max_size': float('inf'),  # Not limited by liquidity constraints

            # Prices (required by dashboard) - all same for single-token strategy
            'P1_A': price_1A,
            'P2_A': price_1A,
            'P2_B': price_1A,
            'P3_B': price_1A,

            # Token amounts (tokens per $1 deployed)
            'T1_A': 1.0 / price_1A if price_1A > 0 else 0.0,
            'T2_A': 0.0,
            'T2_B': 0.0,
            'T3_B': 0.0,

            # Rates (required by dashboard)
            'lend_rate_1a': lend_total_apr_1A,
            'borrow_rate_2a': 0.0,  # No borrowing
            'lend_rate_2b': 0.0,  # No second lending leg
            'borrow_rate_3b': 0.0,  # No borrowing

            # Collateral and liquidation (required by dashboard)
            'collateral_ratio_1a': 0.0,  # Not used as collateral
            'collateral_ratio_2b': 0.0,  # No second leg
            'liquidation_threshold_1a': 0.0,  # No liquidation risk
            'liquidation_threshold_2b': 0.0,  # No second leg

            # Fees and liquidity (required by dashboard)
            'borrow_fee_2a': 0.0,  # No borrowing
            'borrow_fee_3b': 0.0,  # No borrowing
            'available_borrow_2a': 0.0,  # No borrowing
            'available_borrow_3b': 0.0,  # No borrowing
            'borrow_weight_2a': 1.0,  # No borrowing
            'borrow_weight_3b': 1.0,  # No borrowing

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),

            # Note: We don't track lending supply caps in database
            # Only borrow liquidity limits (available_borrow_usd)
            # Future: Will add supply_cap tracking
        }

    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Stablecoin lending never needs rebalancing (no leverage, no liquidation risk).

        Single-leg strategy with no borrowing means the position cannot drift from
        target weights - there are no weights to maintain.

        Args:
            position: Position dict (not used for stablecoin lending)
            live_rates: Current rates (not used)
            live_prices: Current prices (not used)

        Returns:
            Dict with requires_rebalance=False (always)
        """
        return {
            "requires_rebalance": False,
            "actions": [],
            "reason": "Single-leg strategy does not require rebalancing"
        }
