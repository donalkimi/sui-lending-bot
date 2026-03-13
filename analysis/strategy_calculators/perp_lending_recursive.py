"""Strategy calculator for perp_lending_recursive (3 legs: spot lend + stablecoin borrow + perp short).

Starting capital: stablecoin (e.g. USDC).

Each loop iteration:
  0. Buy (1-d) spot via AMM + open (1-d) short perp on Bluefin (market neutral from first trade)
  1. Lend spot at Protocol A (L_A leg)
  2. Borrow stablecoin at Protocol A against spot collateral (B_A leg)
  3. Recycle (1-d)*r stablecoin → repeat from step 0

Geometric series amplifier: factor = 1 / (1 - r*(1-d))

Positions per $1 deployed:
    L_A = (1-d) / (1 - r*(1-d))   — spot lending notional (amplified)
    B_A = r * L_A                  — stablecoin borrow notional
    L_B = 0
    B_B = L_A                      — short perp notional (market neutral)

Two liquidation risks (opposite directions):
    Protocol A: spot price drops  → USDC borrow exceeds collateral value
    Bluefin:    spot price rises  → short perp margin call
"""

from typing import Dict, Any

from .perp_lending import PerpLendingCalculator


class PerpLendingRecursiveCalculator(PerpLendingCalculator):
    """
    Perp lending calculator — recursive (looped) variant.

    Inherits all APR, fee, and basis logic from PerpLendingCalculator.
    Overrides:
      - get_strategy_type()      → 'perp_lending_recursive'
      - get_required_legs()      → 3
      - calculate_positions()    → geometric series amplification
      - analyze_strategy()       → super() + subtract B_A borrow cost + populate token2 fields
    """

    def get_strategy_type(self) -> str:
        return 'perp_lending_recursive'

    def get_required_legs(self) -> int:
        return 3  # L_A (spot lend), B_A (stablecoin borrow), B_B (perp short); L_B = 0

    def calculate_positions(
        self,
        liquidation_distance: float,
        collateral_ratio_a: float = 0.0,   # unused (signature compat with parent)
        collateral_ratio_b: float = 0.0,   # unused
        collateral_ratio_token1: float = 0.0,
        liquidation_threshold_token1: float = 0.0,
        borrow_weight_token2: float = 1.0,
        **kwargs
    ) -> Dict[str, float]:
        """
        Recursive positions via geometric series.

        r      = safe borrow ratio (stablecoin vs spot collateral at Protocol A)
        q      = r * (1 - d)  — loop ratio; converges for r < 1, d > 0
        factor = 1 / (1 - q)  — amplifier
        """
        d       = liquidation_distance
        liq_max = d / (1.0 - d)
        r_safe  = liquidation_threshold_token1 / ((1.0 + liq_max) * borrow_weight_token2) if borrow_weight_token2 > 0 else 0.0
        r       = min(r_safe, collateral_ratio_token1)

        q      = r * (1.0 - d)
        factor = 1.0 / (1.0 - q) if q < 1.0 else 1.0

        l_a = (1.0 - d) * factor
        b_a = r * l_a
        b_b = l_a   # market neutral: short perp notional = spot lending notional

        return {'l_a': l_a, 'b_a': b_a, 'l_b': 0.0, 'b_b': b_b}

    def analyze_strategy(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Full analysis for perp_lending_recursive.

        Calls parent (perp_lending) to build the base result — which correctly uses
        the amplified L_A and B_B from our calculate_positions() override, so the
        spot lending APR, perp funding APR, and Bluefin taker fees are all already
        scaled correctly.

        Then adjusts APRs to subtract the B_A stablecoin borrow cost, which the
        parent has no concept of, and populates token2 fields.
        """
        # Extract B_A leg params from kwargs
        rate_token2          = kwargs.get('rate_token2')
        borrow_fee_token2    = kwargs.get('borrow_fee_token2') or 0.0
        available_borrow_token2  = kwargs.get('available_borrow_token2')
        borrow_weight_token2     = kwargs.get('borrow_weight_token2', 1.0)
        collateral_ratio_token1     = kwargs.get('collateral_ratio_token1')
        liquidation_threshold_token1 = kwargs.get('liquidation_threshold_token1')
        token2               = kwargs.get('token2')
        token2_contract      = kwargs.get('token2_contract')
        price_token2         = kwargs.get('price_token2')

        if rate_token2 is None:
            return {'valid': False, 'error': 'perp_lending_recursive: missing rate_token2'}
        if collateral_ratio_token1 is None or liquidation_threshold_token1 is None:
            return {'valid': False, 'error': 'perp_lending_recursive: missing collateral_ratio_token1 or liquidation_threshold_token1'}

        # Run parent analysis — spot lend + perp short APRs computed with amplified positions
        result = super().analyze_strategy(*args, **kwargs)

        if not result['valid']:
            return result

        b_a = result['b_a']
        l_a = result['l_a']

        # --- Subtract B_A stablecoin borrow cost (parent does not know about this leg) ---
        borrow_cost_apr  = b_a * rate_token2
        upfront_borrow_fee = b_a * borrow_fee_token2

        new_gross   = result['apr_gross'] - borrow_cost_apr
        new_upfront = result['total_upfront_fee'] + upfront_borrow_fee
        new_net     = result['net_apr'] - borrow_cost_apr - upfront_borrow_fee
        new_basis_adj_net = result['basis_adj_net_apr'] - borrow_cost_apr - upfront_borrow_fee

        # Recalculate time-adjusted APRs with updated gross and upfront costs
        apr5  = (new_gross *  5 / 365 - new_upfront) * 365 /  5
        apr30 = (new_gross * 30 / 365 - new_upfront) * 365 / 30
        apr90 = (new_gross * 90 / 365 - new_upfront) * 365 / 90
        days_to_breakeven = (new_upfront * 365.0 / new_gross) if new_gross > 0 else float('inf')

        # max_size: limited by available stablecoin borrow liquidity at Protocol A
        if available_borrow_token2 is not None and b_a > 0:
            max_size = available_borrow_token2 / b_a
        else:
            max_size = float('inf')

        # Loop parameters
        liquidation_distance = kwargs.get('liquidation_distance', 0.20)
        r = b_a / l_a if l_a > 0 else 0.0
        q = r * (1.0 - liquidation_distance)
        loop_amplifier = 1.0 / (1.0 - q) if q < 1.0 else float('inf')

        # token2 units: stablecoin tokens per $1 deployed ≈ b_a / price_token2
        token2_units = b_a / price_token2 if price_token2 and price_token2 > 0 else None

        result.update({
            # Adjusted APRs
            'net_apr':           new_net,
            'basis_adj_net_apr': new_basis_adj_net,
            'apr_gross':         new_gross,
            'total_upfront_fee': new_upfront,
            'apr5':              apr5,
            'apr30':             apr30,
            'apr90':             apr90,
            'days_to_breakeven': days_to_breakeven,
            'max_size':          max_size,

            # Token2 identity (B_A = stablecoin borrow)
            'token2':          token2,
            'token2_contract': token2_contract,
            'token2_price':    price_token2,
            'token2_units':    token2_units,
            'token2_rate':     rate_token2,

            # Collateral / borrow params for liquidation calc and display
            'token1_collateral_ratio':       collateral_ratio_token1,
            'token1_liquidation_threshold':  liquidation_threshold_token1,
            'token2_borrow_fee':             borrow_fee_token2,
            'token2_available_borrow':       available_borrow_token2,
            'token2_borrow_weight':          borrow_weight_token2,

            # Both legs have liquidation risk (opposite price directions)
            'has_lending_liq_risk': True,

            # Loop metadata
            'loop_ratio':      q,
            'loop_amplifier':  loop_amplifier,

            # Strategy type
            'strategy_type':   'perp_lending_recursive',
        })

        return result

    def calculate_rebalance_amounts(self, position: dict, live_rates: dict, live_prices: dict,
                                    force: bool = False) -> dict:
        """
        Extends parent rebalance logic (perp liq trigger) with B_A stablecoin borrow repayment.

        When L_A is reduced to restore the short perp's liquidation distance:
          - B_A must be proportionally reduced to keep Protocol A LTV safe
          - Part of the USDC freed by selling spot goes to repay B_A, not all to Bluefin margin
          - Parent's 'deposit_collateral' action amount is reduced by the B_A repayment

        Also checks token1 (volatile collateral) and token2 (stablecoin borrow) liq dist drift.
        """
        from config.settings import REBALANCE_THRESHOLD
        from analysis.strategy_calculators.base import _liq_delta, _build_reason

        # Parent computes: trigger check (token4 short perp), exit_token1/token4 amounts
        result = super().calculate_rebalance_amounts(position, live_rates, live_prices, force=force)

        if not force:
            # Add Protocol A liq checks: token1 (volatile collateral drops) + token2 (stablecoin borrow depeg)
            d = float(position.get('entry_liquidation_distance') or 0)
            lltv_a = float(position.get('entry_token1_liquidation_threshold') or 0)
            bw_a = float(position.get('entry_token2_borrow_weight') or 1.0)
            e1 = float(position.get('entry_token1_amount') or 0)
            e2 = float(position.get('entry_token2_amount') or 0)
            p1 = live_prices.get('price_token1')
            p2 = live_prices.get('price_token2')

            d_prot_a = _liq_delta(d, e1, p1, e2, p2, lltv_a, bw_a)
            if d_prot_a != 0.0 and d_prot_a >= REBALANCE_THRESHOLD:
                result['requires_rebalance'] = True
                # Append Protocol A info to existing reason
                prot_a_str = _build_reason({'token1/token2': d_prot_a}, REBALANCE_THRESHOLD)
                result['reason'] = f"{result.get('reason', '')} | {prot_a_str}"

        # Borrow ratio r = B_A / L_A (from position multipliers, constant for the strategy)
        b_a = float(position['b_a'])
        l_a = float(position['l_a'])
        r   = b_a / l_a if l_a > 0 else 0.0

        # New B_A proportional to new L_A at current spot price
        new_token1_amount   = result['exit_token1_amount']   # set by parent — always present
        price_token1        = live_prices['price_token1']    # KeyError = data problem, fail loudly
        new_b_a_tokens      = r * new_token1_amount * price_token1   # USDC ≈ USD

        entry_token2_amount = float(position['entry_token2_amount'])
        b_a_repayment       = max(0.0, entry_token2_amount - new_b_a_tokens)

        result['exit_token2_amount'] = new_b_a_tokens

        if result.get('requires_rebalance') and b_a_repayment > 0:
            # Reduce the parent's deposit_collateral — part of USDC goes to repay B_A
            for action in result['actions']:
                if action.get('action') == 'deposit_collateral':
                    action['amount'] = max(0.0, action['amount'] - b_a_repayment)
                    action['description'] = (
                        f"Deposit {action['amount']:.2f} USDC into Bluefin as perp margin"
                    )
                    break

            # Add borrow repayment action
            token2 = position.get('token2', 'USDC')
            result['actions'].append({
                'protocol': position['protocol_a'],
                'action': 'repay_borrow',
                'token': token2,
                'amount': b_a_repayment,
                'description': f'Repay {b_a_repayment:.2f} {token2} borrow at {position["protocol_a"]}',
            })
            result['action_token2'] = f'Repay {b_a_repayment:.2f} {token2}'
        else:
            result['action_token2'] = 'No change'

        return result
