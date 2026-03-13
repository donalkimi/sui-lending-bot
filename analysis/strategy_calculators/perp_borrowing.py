from typing import Dict, Any
from .base import StrategyCalculatorBase, MIN_TOKEN_DELTA
from config import settings


class PerpBorrowingCalculator(StrategyCalculatorBase):
    """
    Perp borrowing calculator (3-leg strategy, non-looped).

    Legs:
        1A: Lend token1 (stablecoin) at Protocol A
        2A: Borrow token2 (volatile) at Protocol A, sell spot
        3B: Long token3 perp on Bluefin (market-neutral offset to short spot)

    Positions:
        L_A = 1.0,  B_A = r,  L_B = r,  B_B = 0.0

    Where:
        liq_max = liquidation_distance / (1 - liquidation_distance)
        r_safe  = liquidation_threshold_token1 / ((1 + liq_max) * borrow_weight_token2)
        r       = min(r_safe, collateral_ratio_token1)

    Liquidation risks:
        - Protocol A: token2 price rises (debt value exceeds collateral)
        - Bluefin long perp: token2 price drops (margin call on long)
    """

    def get_strategy_type(self) -> str:
        return 'perp_borrowing'

    def get_required_legs(self) -> int:
        return 3

    def calculate_positions(
        self,
        liquidation_distance: float,
        liquidation_threshold_token1: float,
        collateral_ratio_token1: float,
        borrow_weight_token2: float = 1.0,
        **kwargs
    ) -> Dict[str, float]:
        liq_max = liquidation_distance / (1.0 - liquidation_distance)
        r_safe  = liquidation_threshold_token1 / ((1.0 + liq_max) * borrow_weight_token2)
        r       = min(r_safe, collateral_ratio_token1)

        return {'l_a': 1.0, 'b_a': r, 'l_b': r, 'b_b': 0.0}

    def calculate_gross_apr(self, positions: Dict, rates: Dict) -> float:
        """
        gross = L_A × lend_1A + L_B × lend_3B − B_A × borrow_2A

        rate_token3 is the stored Bluefin rate for the long perp.
        Positive = longs earn. Negative = longs pay.
        """
        earnings = (positions['l_a'] * rates['rate_token1']
                  + positions['l_b'] * rates['rate_token3'])
        costs    =  positions['b_a'] * rates['rate_token2']
        return earnings - costs

    def calculate_net_apr(self, positions: Dict, rates: Dict, fees: Dict) -> float:
        """
        net = gross
            − L_B × 2 × BLUEFIN_TAKER_FEE   (long perp entry + exit)
            − B_A × borrow_fee_token2             (upfront borrow fee at Protocol A)
        """
        gross      = self.calculate_gross_apr(positions, rates)
        perp_fees  = positions['l_b'] * 2.0 * settings.BLUEFIN_TAKER_FEE
        borrow_fee = (fees.get('borrow_fee_token2') or 0.0) * positions['b_a']
        return gross - perp_fees - borrow_fee

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

        Token count is anchored to the spot side (borrowed + sold short).
        Perp long matches that token count exactly.

        If there is a basis (spot_price ≠ perp_price), the USD values
        will differ slightly — this is expected and acceptable.

        Args:
            positions: {'b_a': ..., 'l_b': ..., ...}
            entry_prices: {'spot': price_token2_at_entry, 'perp': price_token4_at_entry}
            current_prices: {'spot': current_price_token2, 'perp': current_price_token4}
            deployment_usd: total deployment in USD

        Returns:
            {
                'spot_pnl': ...,    # P&L on short spot leg (negative if price rises)
                'perp_pnl': ...,    # P&L on long perp leg (positive if price rises)
                'net_pnl': ...,     # Net (near-zero if hedged; residual from basis is ok)
                'spot_tokens': ...,
                'perp_tokens': ...
            }
        """
        b_a = positions['b_a']

        spot_entry_price   = entry_prices.get('spot', 0.0)
        perp_entry_price   = entry_prices.get('perp', 0.0)
        spot_current_price = current_prices.get('spot', 0.0)
        perp_current_price = current_prices.get('perp', spot_current_price)

        # Anchor: number of tokens borrowed and sold short
        spot_tokens = (b_a * deployment_usd) / spot_entry_price if spot_entry_price > 0 else 0
        perp_tokens = spot_tokens  # Match token count, not USD notional

        # Spot: short position (borrowed and sold), direction = -1
        spot_pnl = (spot_current_price - spot_entry_price) * spot_tokens * (-1.0)

        # Perp: long position, direction = +1
        perp_pnl = (perp_current_price - perp_entry_price) * perp_tokens * 1.0

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
        token2: str,
        token3: str,
        protocol_a: str,
        protocol_b: str,
        rate_token1: float,
        rate_token2: float,
        rate_token3: float,
        collateral_ratio_token1: float,
        liquidation_threshold_token1: float,
        price_token1: float,
        price_token2: float,
        price_token4: float,
        liquidation_distance: float = 0.20,
        **kwargs
    ) -> Dict[str, Any]:
        # Validate required inputs
        missing = [n for n, v in [
            ('rate_token1', rate_token1),
            ('rate_token2', rate_token2),
            ('rate_token3', rate_token3),
            ('collateral_ratio_token1', collateral_ratio_token1),
            ('liquidation_threshold_token1', liquidation_threshold_token1),
        ] if v is None]
        if missing:
            return {'valid': False, 'error': f"Missing: {', '.join(missing)}"}

        borrow_weight_token2 = kwargs.get('borrow_weight_token2', 1.0)
        borrow_fee_token2    = kwargs.get('borrow_fee_token2') or 0.0
        available_borrow = kwargs.get('available_borrow_token2')

        positions = self.calculate_positions(
            liquidation_distance=liquidation_distance,
            liquidation_threshold_token1=liquidation_threshold_token1,
            collateral_ratio_token1=collateral_ratio_token1,
            borrow_weight_token2=borrow_weight_token2,
        )
        rates = {
            'rate_token1':   rate_token1,
            'rate_token2': rate_token2,
            'rate_token3':   rate_token3,
        }
        fees = {'borrow_fee_token2': borrow_fee_token2}

        l_a, b_a, l_b = positions['l_a'], positions['b_a'], positions['l_b']
        gross_apr = self.calculate_gross_apr(positions, rates)

        # Basis spread cost: round-trip bid/ask friction on the spot+perp hedge.
        # basis_spread = basis_ask - basis_bid from spot_perp_basis table.
        # None when basis data is unavailable; cost treated as 0 in that case.
        basis_spread = kwargs.get('basis_spread')
        basis_mid    = kwargs.get('basis_mid')
        basis_ask    = kwargs.get('basis_ask')   # entry-side basis for perp_borrowing (long perp at ask)
        basis_bid    = kwargs.get('basis_bid')   # exit-side basis (close long at perp_bid, buy spot)
        basis_cost = l_b * basis_spread if basis_spread is not None else 0.0

        net_apr = self.calculate_net_apr(positions, rates, fees)
        basis_adj_net_apr = self.calculate_basis_adj_net_apr(positions, rates, fees, basis_cost=basis_cost)

        # Time-adjusted APRs: earn N days of gross APR, subtract the one-time upfront cost, annualise.
        # Formula: APR(N days) = (gross_apr × N/365 - total_upfront_fee) × 365/N
        perp_fee = l_b * 2.0 * settings.BLUEFIN_TAKER_FEE
        total_upfront_fee = b_a * borrow_fee_token2 + perp_fee + basis_cost
        apr5  = (gross_apr * 5  / 365 - total_upfront_fee) * 365 / 5
        apr30 = (gross_apr * 30 / 365 - total_upfront_fee) * 365 / 30
        apr90 = (gross_apr * 90 / 365 - total_upfront_fee) * 365 / 90
        days_to_breakeven = (total_upfront_fee * 365.0 / gross_apr) if gross_apr > 0 else float('inf')

        max_size = (available_borrow / b_a) if (available_borrow is not None and b_a > 0) else float('inf')

        _t2_a = b_a / price_token2 if price_token2 > 0 else 0.0

        return {
            # Identity (universal leg convention)
            # L_A = token1 (stablecoin lent at protocol_A)
            # B_A = token2 (volatile borrowed from protocol_A, sold spot)
            # L_B = token3 (perp proxy = long perp, market-neutral offset)
            # B_B = None  (no borrow from protocol_B)
            'token1': token1, 'token2': token2, 'token3': token3,
            'token4': None,   # B_B unused
            'protocol_a': protocol_a, 'protocol_b': protocol_b,
            'token1_contract': kwargs.get('token1_contract'),
            'token2_contract': kwargs.get('token2_contract'),
            'token3_contract': kwargs.get('token3_contract'),
            'token4_contract': None,

            # Positions
            'l_a': l_a, 'b_a': b_a, 'l_b': l_b, 'b_b': 0.0,

            # APR
            'apr_gross': gross_apr,
            'net_apr':   net_apr,
            'basis_adj_net_apr': basis_adj_net_apr,
            'stablecoin_lending_apr': l_a * rate_token1,
            'token2_borrow_apr':      b_a * rate_token2,
            'funding_rate_apr':       l_b * rate_token3,
            'perp_fees_apr':          l_b * 2.0 * settings.BLUEFIN_TAKER_FEE,
            'basis_spread':           basis_spread,
            'basis_mid':              basis_mid,
            'basis_ask':              basis_ask,
            'basis_bid':              basis_bid,
            'basis_cost':             basis_cost,
            'total_upfront_fee':      total_upfront_fee,
            'basis_cost_included':    basis_spread is not None,
            'apr5':  apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk
            'liquidation_distance': liquidation_distance,
            'has_lending_liq_risk': True,   # Protocol A liq if token2 price rises
            'has_perp_liq_risk':    True,   # Bluefin long liq if token2 price drops
            'max_size':             max_size,

            # Prices
            'token1_price': price_token1,
            'token2_price': price_token2,
            'token3_price': price_token4,   # L_B: perp price (bug fix: was price_token2)
            'token4_price': None,       # B_B unused

            # Token amounts (tokens per $1 deployed)
            'token1_units': l_a / price_token1 if price_token1 > 0 else 0.0,
            'token2_units': _t2_a,
            'token3_units': _t2_a,  # L_B: perp contracts = borrowed token count (bug fix: was 0.0)
            'token4_units': None,   # B_B unused (bug fix: was _t2_a)

            # Rates
            'token1_rate': rate_token1,
            'token2_rate': rate_token2,
            'token3_rate': rate_token3,   # L_B: perp funding rate (bug fix: was 0.0)
            'token4_rate': None,                # B_B unused

            # Collateral / liquidation
            'token1_collateral_ratio':      collateral_ratio_token1,
            'token1_liquidation_threshold': liquidation_threshold_token1,

            # Fees / liquidity
            'token2_borrow_fee':       borrow_fee_token2,
            'token2_available_borrow': available_borrow,
            'token2_borrow_weight':    borrow_weight_token2,
            'token4_available_borrow':  None,  # B_B unused

            # Metadata
            'valid':         True,
            'strategy_type': self.get_strategy_type(),

            # Fields not applicable to perp_borrowing — store as NULL in DB
            'token3_collateral_ratio': None,
            'token3_liquidation_threshold': None,
            'token4_borrow_fee': None,
            'token4_borrow_weight': None,
        }

    def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict,
                                    force: bool = False) -> Dict:
        l_a = float(position['l_a'])
        b_a = float(position['b_a'])
        D   = float(position['deployment_usd'])

        p1 = live_prices['price_token1']   # oracle USDC price
        p2 = live_prices['price_token2']   # oracle DEEP spot price
        p3 = live_prices['price_token3']   # oracle DEEP perp price

        if not p1 or not p2 or not p3:
            return {
                'requires_rebalance': True,
                'actions': [],
                'reason': 'Missing live prices — cannot compute rebalance amounts',
                'exit_token1_amount': None, 'exit_token2_amount': None,
                'exit_token3_amount': None, 'exit_token4_amount': None,
                'action_token1': None, 'action_token2': None,
                'action_token3': None, 'action_token4': None,
            }

        # Ideal amounts at current prices (weights × deployment / price)
        rebalanced_token1_amount = D * l_a / p1
        rebalanced_token2_amount = D * b_a / p2
        rebalanced_token3_amount = rebalanced_token2_amount  # matched to token2 by design

        # Deltas vs current segment opening amounts
        delta1 = rebalanced_token1_amount - float(position['entry_token1_amount'])
        delta2 = rebalanced_token2_amount - float(position['entry_token2_amount'])
        delta3 = rebalanced_token3_amount - float(position['entry_token3_amount'])
        # delta2 == delta3 by construction

        # token1 (USDC): flag only if depeg > 25bps of deployment
        DEPEG_THRESHOLD = 0.0025 * D
        if delta1 > DEPEG_THRESHOLD:
            action1 = f'{position["token1"]} fallen >25bps — lend more'
        elif delta1 < -DEPEG_THRESHOLD:
            action1 = f'{position["token1"]} risen >25bps — reduce lending'
        else:
            action1 = None

        token1 = position['token1']
        token2 = position['token2']
        token3 = position['token3']

        # token2: borrow+short/send token1, or receive token1/buy to cover+repay
        if delta2 > 0:
            action2 = f'Borrow {abs(delta2):.4f} {token2} + short / send {token1} to perp margin'
        elif delta2 < 0:
            action2 = f'Receive {token1} from perp / buy to cover {abs(delta2):.4f} {token2} + repay'
        else:
            action2 = None

        # token3: receive token1/add to long, or send token1/close longs
        if delta3 > 0:
            action3 = f'Receive {token1} / add {abs(delta3):.4f} {token3} to long'
        elif delta3 < 0:
            action3 = f'Send {token1} / close {abs(delta3):.4f} {token3} long'
        else:
            action3 = None

        actions = [a for a in [action1, action2, action3] if a is not None]

        MIN = MIN_TOKEN_DELTA

        # Per-leg action strings using agreed multi-step format
        action2 = ('No change' if abs(delta2) < MIN
                   else f'Borrow {abs(delta2):.4f} {token2} \u2192 Sell' if delta2 > 0
                   else f'Buy {abs(delta2):.4f} {token2} \u2192 Repay borrow')
        action3 = ('No change' if abs(delta3) < MIN
                   else f'Transfer in USDC \u2192 Open long {abs(delta3):.4f} {token3}' if delta3 > 0
                   else f'Close long {abs(delta3):.4f} {token3} \u2192 Transfer out USDC')

        from config.settings import REBALANCE_THRESHOLD
        from analysis.strategy_calculators.base import _liq_delta, _perp_liq_delta, _build_reason

        if force:
            requires_rebalance = True
            reason = 'manual'
        else:
            # Use per-token stored baseline liq dists (set at deployment)
            d_token2 = float(position.get('entry_liquidation_distance_token2') or 0)
            d_token3 = abs(float(position.get('entry_liquidation_distance_token3') or 0))  # stored negative for long perp
            lltv_a = float(position.get('entry_token1_liquidation_threshold') or 0)
            bw_a = float(position.get('entry_token2_borrow_weight') or 1.0)
            e1 = float(position.get('entry_token1_amount') or 0)
            e2 = float(position.get('entry_token2_amount') or 0)
            entry_token3_price = float(position.get('entry_token3_price') or 0)

            # token1/token2: Protocol A (stablecoin collateral vs volatile borrow)
            d_prot_a = _liq_delta(d_token2, e1, p1, e2, p2, lltv_a, bw_a)
            # token3: long perp (liq when price drops)
            d_perp = _perp_liq_delta(d_token3, entry_token3_price, p3, 'long')

            token_deltas = {}
            if d_prot_a != 0.0:
                token_deltas['token1/token2'] = d_prot_a
            if d_perp != 0.0:
                token_deltas['token3'] = d_perp

            requires_rebalance = any(v >= REBALANCE_THRESHOLD for v in token_deltas.values())
            reason = _build_reason(token_deltas, REBALANCE_THRESHOLD) if token_deltas else 'insufficient price data'

        return {
            'requires_rebalance': requires_rebalance,
            'actions': actions,
            'reason': reason,
            'exit_token1_amount': rebalanced_token1_amount,
            'exit_token2_amount': rebalanced_token2_amount,
            'exit_token3_amount': rebalanced_token3_amount,
            'exit_token4_amount': None,
            'action_token1': 'No change',
            'action_token2': action2,
            'action_token3': action3,
            'action_token4': None,
        }
