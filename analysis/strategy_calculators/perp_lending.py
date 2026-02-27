from typing import Dict, Optional
from .base import StrategyCalculatorBase
from config import settings

class PerpLendingCalculator(StrategyCalculatorBase):
    """
    Perp lending calculator (2-leg strategy).

    Strategy:
        1. Buy and lend spot token on lending protocol (long)
        2. Short equivalent perp on Bluefin (short)
        3. Market neutral: long spot = short perp

    Position multipliers:
        L_A = 1/(1 + liquidation_distance)  # Spot lending notional
        B_A = 0.0
        L_B = 0.0
        B_B = L_A  # Perp short notional (equals spot for market neutrality)

    Note: Collateral posted = (1 - L_A), Leverage = L_A / (1 - L_A)

    Liquidation:
        - Short gets liquidated at price increase of 1/leverage
        - Spot cannot be liquidated (not borrowing)
        - Leverage = L_A / B_B
        - For 50/50: liquidation at 100% price increase
    """

    def get_strategy_type(self) -> str:
        return 'perp_lending'

    def get_required_legs(self) -> int:
        return 2

    def calculate_positions(
        self,
        liquidation_distance: float,
        collateral_ratio_a: float,
        collateral_ratio_b: float,
        **kwargs
    ) -> Dict[str, float]:
        """
        Calculate position multipliers based on liquidation distance.

        For perp lending:
        - L_A = 1/(1 + liq_dist) = spot lending notional
        - B_B = L_A = perp short notional (market neutral)
        - Collateral posted = (1 - L_A)
        - Leverage = L_A / (1 - L_A)
        """
        l_a = 1.0 / (1.0 + liquidation_distance)
        b_b = l_a  # Notional perp exposure = lending exposure (market neutral)

        return {
            'l_a': l_a,
            'b_a': 0.0,
            'l_b': 0.0,
            'b_b': b_b
        }

    def calculate_gross_apr(
        self,
        positions: Dict[str, float],
        rates: Dict[str, float]
    ) -> float:
        """
        Calculate gross APR for perp lending (before fees).

        NOTE: This calculates YIELD APR only (lending + funding).
        Price PnL is tracked separately and NOT included in APR calculation.

        Formula:
            gross_apr = L_A × lend_total_apr_1A - B_B × funding_costs_3B

        Note: funding_costs are negative when we earn (shorts earn funding)

        Args:
            positions: Dict with l_a, b_b
            rates: Dict with lend_total_apr_1A, borrow_total_apr_3B (funding rate)

        Returns:
            Gross APR as decimal (e.g., 0.0524 = 5.24%)
        """
        l_a = positions['l_a']
        b_b = positions['b_b']

        lend_apr_1a = rates.get('lend_total_apr_1A', 0.0)
        funding_rate_3b = rates.get('borrow_total_apr_3B', 0.0)  # Perp funding rate

        # Earnings (yield only, no price PnL)
        spot_earnings = l_a * lend_apr_1a
        funding_costs = b_b * funding_rate_3b  # Negative when we earn (shorts earn)
        gross_apr = spot_earnings - funding_costs  # Subtract cost (negative cost = add earnings)

        return gross_apr

    def calculate_net_apr(
        self,
        positions: Dict[str, float],
        rates: Dict[str, float],
        fees: Dict[str, float],
        basis_cost: float = 0.0
    ) -> float:
        """
        Calculate net APR for perp lending (after fees).

        NOTE: This calculates YIELD APR only (lending + funding).
        Price PnL is tracked separately and NOT included in APR calculation.

        Formula:
            net_apr = gross_apr - (B_B × perp_fees) - basis_cost

        Args:
            positions: Dict with l_a, b_b
            rates: Dict with lend_total_apr_1A, borrow_total_apr_3B (funding rate)
            fees: Dict (not used, perp fees are fixed in settings)
            basis_cost: One-time round-trip spot/perp spread cost (decimal, default 0.0)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        gross_apr = self.calculate_gross_apr(positions, rates)

        b_b = positions['b_b']
        perp_fee = b_b * 2.0 * settings.BLUEFIN_TAKER_FEE  # One-time $$$ cost: fee_rate × B_B

        return gross_apr - perp_fee - basis_cost

    def calculate_price_pnl(
        self,
        positions: Dict[str, float],
        entry_prices: Dict[str, float],
        current_prices: Dict[str, float],
        deployment_usd: float,
        **kwargs
    ) -> Dict[str, float]:
        """
        Calculate PnL from price movements (separate from yield).

        Formula: PnL = (current_price - entry_price) × tokens × direction
        - Spot (long): direction = +1
        - Perp (short): direction = -1

        Args:
            positions: {'l_a': 0.833, 'b_b': 0.167, ...}
            entry_prices: {'spot': 100.0, 'perp': 100.0}
            current_prices: {'spot': 105.0, 'perp': 105.0}
            deployment_usd: 1000.0

        Returns:
            {
                'spot_pnl': 50.0,      # Gain on long
                'perp_pnl': -50.0,     # Loss on short
                'net_pnl': 0.0,        # Net (hedged)
                'spot_tokens': 8.33,   # Number of tokens
                'perp_tokens': 8.33    # Number of tokens (same)
            }
        """
        l_a = positions['l_a']
        b_b = positions['b_b']

        spot_entry_price = entry_prices.get('spot', 0.0)
        perp_entry_price = entry_prices.get('perp', 0.0)

        spot_current_price = current_prices.get('spot', 0.0)
        perp_current_price = current_prices.get('perp', spot_current_price)  # Default perp = spot

        # Calculate token amounts
        spot_tokens = (l_a * deployment_usd) / spot_entry_price if spot_entry_price > 0 else 0
        perp_tokens = spot_tokens  # Market neutral: match sizes

        # Calculate PnL
        # Spot: long position, direction = +1
        spot_pnl = (spot_current_price - spot_entry_price) * spot_tokens * 1.0

        # Perp: short position, direction = -1
        perp_pnl = (perp_current_price - perp_entry_price) * perp_tokens * (-1.0)

        net_pnl = spot_pnl + perp_pnl

        return {
            'spot_pnl': spot_pnl,
            'perp_pnl': perp_pnl,
            'net_pnl': net_pnl,
            'spot_tokens': spot_tokens,
            'perp_tokens': perp_tokens
        }

    def analyze_strategy(
        self,
        token1: str,
        protocol_a: str,
        protocol_b: str,
        lend_total_apr_1A: float,
        borrow_total_apr_3B: float,  # Perp funding rate
        price_1A: float,
        liquidation_distance: float = 0.20,
        **kwargs
    ) -> Dict:
        """
        Analyze perp lending strategy.

        Args:
            token1: Spot token symbol (e.g., 'BTC', 'ETH')
            protocol_a: Lending protocol name (e.g., 'suilend', 'navi')
            protocol_b: Perp protocol name (always 'bluefin')
            lend_total_apr_1A: Total lending APR for spot token
            borrow_total_apr_3B: Perp funding rate (annualized)
            price_1A: Spot token price
            liquidation_distance: Safety buffer for perp short (default 0.20 = 20%)
            **kwargs: Additional params (token3, prices, contracts, etc.)

        Returns:
            Strategy dict with all required fields
        """
        # Validate inputs
        if lend_total_apr_1A is None or price_1A is None or price_1A <= 0:
            return {
                'valid': False,
                'error': 'Invalid or missing required data'
            }

        # Extract additional params from kwargs
        token3 = kwargs.get('token3', f'{token1}-PERP')
        token1_contract = kwargs.get('token1_contract')
        token3_contract = kwargs.get('token3_contract')
        price_3B = kwargs.get('price_3B', price_1A)  # Default perp price = spot price

        # Calculate positions
        positions = self.calculate_positions(
            liquidation_distance=liquidation_distance,
            collateral_ratio_a=0.0,  # Not used
            collateral_ratio_b=0.0   # Not used
        )

        # Build rates dict for APR calculation
        rates = {
            'lend_total_apr_1A': lend_total_apr_1A,
            'borrow_total_apr_3B': borrow_total_apr_3B
        }

        # Calculate APRs
        gross_apr = self.calculate_gross_apr(positions=positions, rates=rates)

        # Calculate APR breakdown components for display
        l_a = positions['l_a']
        b_b = positions['b_b']

        spot_lending_apr = l_a * lend_total_apr_1A
        funding_rate_apr = b_b * borrow_total_apr_3B

        # One-time $$$ costs (as fraction of deployment_usd)
        perp_fee   = b_b * 2.0 * settings.BLUEFIN_TAKER_FEE  # fee_rate × B_B

        # Basis spread cost: round-trip bid/ask friction on the spot+perp hedge.
        # basis_spread = basis_ask - basis_bid from spot_perp_basis table.
        # None when basis data is unavailable; cost treated as 0 in that case.
        basis_spread = kwargs.get('basis_spread')
        basis_mid    = kwargs.get('basis_mid')
        basis_cost   = b_b * basis_spread if basis_spread is not None else 0.0  # basis_spread × B_B

        net_apr = self.calculate_net_apr(positions=positions, rates=rates, fees={},
                                         basis_cost=basis_cost)

        # Time-adjusted APRs: earn N days of gross APR, subtract the one-time upfront cost, annualise.
        # Formula: APR(N days) = (gross_apr × N/365 - total_upfront_fee) × 365/N
        total_upfront_fee = perp_fee + basis_cost
        apr5  = (gross_apr * 5  / 365 - total_upfront_fee) * 365 / 5
        apr30 = (gross_apr * 30 / 365 - total_upfront_fee) * 365 / 30
        apr90 = (gross_apr * 90 / 365 - total_upfront_fee) * 365 / 90
        days_to_breakeven = (total_upfront_fee * 365.0 / gross_apr) if gross_apr > 0 else float('inf')

        # Liquidation distances
        leverage = 1.0 / liquidation_distance
        liq_price_multiplier = 1.0 + (1.0 / leverage)

        return {
            # Token and protocol info
            'token1': token1,
            'token2': 'USDC',  # Collateral for perp
            'token3': token3,
            'protocol_a': protocol_a,
            'protocol_b': protocol_b,

            # Contracts (for historical chart queries)
            'token1_contract': token1_contract,
            'token2_contract': None,  # USDC not tracked separately
            'token3_contract': token3_contract,

            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'apr_net': net_apr,
            'apr_gross': gross_apr,
            'spot_lending_apr': spot_lending_apr,
            'funding_rate_apr': funding_rate_apr,
            'perp_fees_apr': perp_fee,
            'basis_spread': basis_spread,
            'basis_mid': basis_mid,
            'basis_cost': basis_cost,
            'total_upfront_fee': total_upfront_fee,
            'basis_cost_included': basis_spread is not None,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': liquidation_distance,
            'leverage': leverage,
            'liq_price_multiplier': liq_price_multiplier,
            'has_lending_liq_risk': False,  # Spot cannot be liquidated
            'has_perp_liq_risk': True,      # Short can be liquidated
            'max_size': float('inf'),  # Not limited yet

            # Prices (required by dashboard)
            'P1_A': price_1A,
            'P2_A': 1.0,  # USDC price
            'P2_B': 1.0,  # USDC price
            'P3_B': price_3B,  # Perp price

            # Rates (required by dashboard)
            'lend_rate_1a': lend_total_apr_1A,
            'borrow_rate_2a': 0.0,  # No borrowing on spot side
            'lend_rate_2b': 0.0,  # No lending on perp side
            'borrow_rate_3b': borrow_total_apr_3B,  # Funding rate

            # Validation
            'valid': True,
            'strategy_type': self.get_strategy_type(),

            # Backwards compat alias (create_position reads 'net_apr'; all other calculators use 'apr_net')
            'net_apr': net_apr,

            # Fields not applicable to perp_lending — store as NULL in DB
            'collateral_ratio_1a': None,
            'liquidation_threshold_1a': None,
            'borrow_fee_2a': None,
            'available_borrow_2a': None,
            'borrow_weight_2a': None,
            'collateral_ratio_2b': None,
            'liquidation_threshold_2b': None,
            'borrow_fee_3b': None,
            'borrow_weight_3b': None,

            # Note: Price PnL calculated separately via calculate_price_pnl()
        }

    def calculate_rebalance_amounts(
        self,
        position: Dict,
        current_prices: Dict[str, float],
        target_liquidation_distance: float,
        **kwargs
    ) -> Dict:
        """Calculate rebalance needed to restore target liquidation distance."""
        # To be implemented when rebalancing is needed
        pass
