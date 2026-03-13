from typing import Dict, Optional
from .base import StrategyCalculatorBase, MIN_TOKEN_DELTA
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
            gross_apr = L_A × rate_token1 - B_B × funding_costs_token4

        Note: funding_costs are negative when we earn (shorts earn funding)

        Args:
            positions: Dict with l_a, b_b
            rates: Dict with rate_token1, rate_token4 (funding rate)

        Returns:
            Gross APR as decimal (e.g., 0.0524 = 5.24%)
        """
        l_a = positions['l_a']
        b_b = positions['b_b']

        lend_apr_1a = rates.get('rate_token1', 0.0)
        funding_rate_3b = rates.get('rate_token4', 0.0)  # Perp funding rate

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
    ) -> float:
        """
        Calculate net APR for perp lending (after deterministic fees).

        NOTE: This calculates YIELD APR only (lending + funding).
        Price PnL is tracked separately and NOT included in APR calculation.

        Formula:
            net_apr = gross_apr - (B_B × perp_fees)

        Args:
            positions: Dict with l_a, b_b
            rates: Dict with rate_token1, rate_token4 (funding rate)
            fees: Dict (not used, perp fees are fixed in settings)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        gross_apr = self.calculate_gross_apr(positions, rates)

        b_b = positions['b_b']
        perp_fee = b_b * 2.0 * settings.BLUEFIN_TAKER_FEE  # One-time $$$ cost: fee_rate × B_B

        return gross_apr - perp_fee

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
        rate_token1: float,
        rate_token4: float,  # Perp funding rate
        price_token1: float,
        liquidation_distance: float = 0.20,
        **kwargs
    ) -> Dict:
        """
        Analyze perp lending strategy.

        Args:
            token1: Spot token symbol (e.g., 'BTC', 'ETH')
            protocol_a: Lending protocol name (e.g., 'suilend', 'navi')
            protocol_b: Perp protocol name (always 'bluefin')
            rate_token1: Total lending APR for spot token
            rate_token4: Perp funding rate (annualized)
            price_token1: Spot token price
            liquidation_distance: Safety buffer for perp short (default 0.20 = 20%)
            **kwargs: Additional params (token3, prices, contracts, etc.)

        Returns:
            Strategy dict with all required fields
        """
        # Validate inputs
        if rate_token1 is None or price_token1 is None or price_token1 <= 0:
            return {
                'valid': False,
                'error': 'Invalid or missing required data'
            }

        # Extract additional params from kwargs (perp proxy is B_B = token4 slot)
        token4 = kwargs.get('token4', f'{token1}-PERP')
        token1_contract = kwargs.get('token1_contract')
        token4_contract = kwargs.get('token4_contract')
        price_token4 = kwargs.get('price_token4', price_token1)  # Default perp price = spot price

        # Calculate positions — **kwargs passed through so subclasses can receive
        # extra params (e.g. collateral_ratio_token1, liquidation_threshold_token1 for recursive variant)
        positions = self.calculate_positions(
            liquidation_distance=liquidation_distance,
            collateral_ratio_a=0.0,  # Not used by base class
            collateral_ratio_b=0.0,  # Not used by base class
            **kwargs
        )

        # Build rates dict for APR calculation
        rates = {
            'rate_token1': rate_token1,
            'rate_token4': rate_token4
        }

        # Calculate APRs
        gross_apr = self.calculate_gross_apr(positions=positions, rates=rates)

        # Calculate APR breakdown components for display
        l_a = positions['l_a']
        b_b = positions['b_b']

        spot_lending_apr = l_a * rate_token1
        funding_rate_apr = b_b * rate_token4

        # One-time $$$ costs (as fraction of deployment_usd)
        perp_fee   = b_b * 2.0 * settings.BLUEFIN_TAKER_FEE  # fee_rate × B_B

        # Basis spread cost: round-trip bid/ask friction on the spot+perp hedge.
        # basis_spread = basis_ask - basis_bid from spot_perp_basis table.
        # None when basis data is unavailable; cost treated as 0 in that case.
        basis_spread = kwargs.get('basis_spread')
        basis_mid    = kwargs.get('basis_mid')
        basis_bid    = kwargs.get('basis_bid')   # entry-side basis for perp_lending (short perp at bid)
        basis_ask    = kwargs.get('basis_ask')   # exit-side basis for perp_lending (cover short at ask)
        basis_cost   = b_b * basis_spread if basis_spread is not None else 0.0  # basis_spread × B_B

        net_apr = self.calculate_net_apr(positions=positions, rates=rates, fees={})
        basis_adj_net_apr = self.calculate_basis_adj_net_apr(positions=positions, rates=rates, fees={},
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

        _t1_a = l_a / price_token1 if price_token1 > 0 else 0.0

        return {
            # Token identity (universal leg convention)
            # L_A = token1 (spot, lent at protocol_A)
            # B_A = None (no borrow at protocol_A)
            # L_B = None (no lend at protocol_B — Bluefin is perp only)
            # B_B = token4 (perp proxy = short perp at Bluefin)
            'token1': token1,
            'token2': None,     # B_A unused
            'token3': None,     # L_B unused
            'token4': token4,   # B_B = short perp proxy
            'protocol_a': protocol_a,
            'protocol_b': protocol_b,

            # Contracts
            'token1_contract': token1_contract,
            'token2_contract': None,
            'token3_contract': None,
            'token4_contract': token4_contract,

            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'net_apr': net_apr,
            'basis_adj_net_apr': basis_adj_net_apr,
            'apr_gross': gross_apr,
            'spot_lending_apr': spot_lending_apr,
            'funding_rate_apr': funding_rate_apr,
            'perp_fees_apr': perp_fee,
            'basis_spread': basis_spread,
            'basis_mid': basis_mid,
            'basis_bid': basis_bid,
            'basis_ask': basis_ask,
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
            'max_size': float('inf'),

            # Prices (unused legs = None)
            'token1_price': price_token1,
            'token2_price': None,
            'token3_price': None,
            'token4_price': price_token4,   # B_B: perp price

            # Token amounts (tokens per $1 deployed)
            'token1_units': _t1_a,
            'token2_units': None,
            'token3_units': None,
            'token4_units': _t1_a,  # market neutral: perp short = spot token count

            # Rates (unused legs = None)
            'token1_rate': rate_token1,
            'token2_rate': None,
            'token3_rate': None,
            'token4_rate': rate_token4,  # B_B: perp funding rate

            # Validation
            'valid': True,
            'strategy_type': self.get_strategy_type(),

            # Fields not applicable to perp_lending — store as NULL in DB
            'token1_collateral_ratio': None,
            'token1_liquidation_threshold': None,
            'token2_borrow_fee': None,
            'token2_available_borrow': None,
            'token2_borrow_weight': None,
            'token3_collateral_ratio': None,
            'token3_liquidation_threshold': None,
            'token4_borrow_fee': None,
            'token4_borrow_weight': None,

            # Note: Price PnL calculated separately via calculate_price_pnl()
        }

    def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict,
                                    force: bool = False) -> Dict:
        """
        Calculate whether rebalancing is needed and the actions to restore target liq distance.

        Trigger: short perp liq distance has shrunk by >= REBALANCE_THRESHOLD from entry.
        Action:  reduce spot lending + cover part of short perp, sell tokens, deposit USDC
                 into Bluefin collateral to restore liq_dist = d.
        """
        from config.settings import REBALANCE_THRESHOLD

        # Map to universal token names (token4 = B_B = short perp at Bluefin)
        price_token1 = live_prices.get('price_token1')   # spot token (token1 = L_A)
        price_token4 = live_prices.get('price_token4')   # perp price (token4 = B_B)

        d = float(position['entry_liquidation_distance'])
        entry_token4_price  = position['entry_token4_price']
        entry_token1_amount = float(position['entry_token1_amount'])
        deployment_usd      = float(position['deployment_usd'])

        # Baseline: at entry, liq dist = d (by design)
        baseline_liq_dist = d

        no_data_response = {
            'exit_token1_amount': entry_token1_amount, 'exit_token2_amount': None,
            'exit_token3_amount': None, 'exit_token4_amount': entry_token1_amount,
            'action_token1': 'No change', 'action_token2': None,
            'action_token3': None, 'action_token4': 'No change',
        }

        if not entry_token4_price or float(entry_token4_price) <= 0:
            return {'requires_rebalance': False, 'actions': [],
                    'reason': 'Cannot check: entry_token4_price (perp entry price) is missing', **no_data_response}
        entry_token4_price = float(entry_token4_price)

        if not price_token1 or price_token1 <= 0:
            return {'requires_rebalance': False, 'actions': [],
                    'reason': 'Cannot check: no live token1 (spot) price available', **no_data_response}

        if not price_token4 or price_token4 <= 0:
            return {'requires_rebalance': False, 'actions': [],
                    'reason': 'Cannot check: no live token4 (perp) price available', **no_data_response}

        # Short perp liq price is fixed at entry: rises by d from entry perp price
        liq_price_token4 = entry_token4_price * (1 + d)
        live_liq_dist = (liq_price_token4 - price_token4) / price_token4

        delta = abs(baseline_liq_dist) - abs(live_liq_dist)
        requires_rebalance = delta >= REBALANCE_THRESHOLD

        reason = (
            f'Short perp liq dist: baseline {baseline_liq_dist:.1%}, '
            f'live {live_liq_dist:.1%}, delta {delta:.1%} '
            f'(threshold {REBALANCE_THRESHOLD:.1%})'
        )

        actions = []
        new_token1_amount = entry_token1_amount  # default: no change
        t1 = position.get('token1', 'token1')
        t4 = position.get('token4', 'token4')

        if requires_rebalance:
            # To restore liq_dist = d at current price:
            #   new_token1_amount = deployment_usd / (price_token1 × (1 + d))
            #   Δ_tokens = entry_token1_amount − new_token1_amount  (tokens to withdraw + cover)
            #   Δ_usdc   = Δ_tokens × price_token1                  (USDC to deposit into Bluefin)
            new_token1_amount = deployment_usd / (price_token1 * (1 + d))
            delta_tokens = entry_token1_amount - new_token1_amount
            delta_usdc   = delta_tokens * price_token1
            actions = [
                {
                    'protocol': position['protocol_a'],
                    'action': 'withdraw_lending',
                    'token': position['token1'],
                    'amount': delta_tokens,
                    'description': f'Withdraw {delta_tokens:.4f} {position["token1"]} from {position["protocol_a"]} lending'
                },
                {
                    'protocol': position['protocol_b'],
                    'action': 'close_short_perp',
                    'token': position['token4'],
                    'amount': delta_tokens,
                    'description': f'Cover {delta_tokens:.4f} notional of {position["token4"]} short perp'
                },
                {
                    'protocol': 'AMM',
                    'action': 'sell_spot',
                    'token': position['token1'],
                    'amount': delta_tokens,
                    'receive_usdc': delta_usdc,
                    'description': f'Sell {delta_tokens:.4f} {position["token1"]} → {delta_usdc:.2f} USDC'
                },
                {
                    'protocol': position['protocol_b'],
                    'action': 'deposit_collateral',
                    'token': 'USDC',
                    'amount': delta_usdc,
                    'description': f'Deposit {delta_usdc:.2f} USDC into Bluefin as perp margin'
                },
            ]

        MIN = MIN_TOKEN_DELTA
        delta1 = new_token1_amount - entry_token1_amount  # negative = reduce (price UP)

        # leg 1 (spot lend): price UP → withdraw+sell; price DOWN → transfer in+buy+lend
        if abs(delta1) < MIN:
            action1 = 'No change'
        elif delta1 < 0:
            action1 = f'Withdraw {abs(delta1):.4f} {t1} \u2192 Sell'
        else:
            action1 = f'Transfer in USDC \u2192 Buy {abs(delta1):.4f} {t1} \u2192 Lend'

        # leg 4 (short perp): moves in step with leg 1
        if abs(delta1) < MIN:
            action4 = 'No change'
        elif delta1 < 0:
            action4 = f'Buy to cover {abs(delta1):.4f} \u2192 Transfer in USDC'
        else:
            action4 = f'Add to short {abs(delta1):.4f} \u2192 Transfer out USDC'

        # Execution mode: threshold check already done upstream, always proceed
        if force:
            requires_rebalance = True

        return {
            'requires_rebalance': requires_rebalance,
            'actions': actions,
            'reason': reason,
            'exit_token1_amount': new_token1_amount,
            'exit_token2_amount': None,
            'exit_token3_amount': None,
            'exit_token4_amount': new_token1_amount,  # market neutral: perp count = spot count
            'action_token1': action1,
            'action_token2': None,
            'action_token3': None,
            'action_token4': action4,
        }
