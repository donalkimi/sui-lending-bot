# Plan: perp_lending — Rebalance Implementation

## Context

`perp_lending` lends a spot token (e.g., SUI) on Protocol A and shorts the equivalent notional on Bluefin (market neutral). The short perp carries liquidation risk when price rises — the liq distance shrinks from the configured `d` over time.

`calculate_rebalance_amounts()` currently has two bugs:
1. **Wrong signature** — uses `current_prices, target_liquidation_distance` instead of `live_rates, live_prices` → `TypeError` before the body runs
2. **Returns `None`** (via `pass`) → `rebalance_position()` raises `ValueError` at line 1288

Result: any rebalance attempt on a `perp_lending` position crashes.

**File to modify:** [analysis/strategy_calculators/perp_lending.py:371](analysis/strategy_calculators/perp_lending.py#L371)

---

## Token Convention (Design Note 18)

| Weight | Token | Role |
|--------|-------|------|
| L_A | token1 | Spot token (e.g., SUI) — bought and lent at Protocol A |
| B_B | token4 | Perp proxy (e.g., SUI-USDC-PERP) — shorted on Bluefin |
| B_A | token2 | NULL (unused) |
| L_B | token3 | NULL (unused) |

`live_prices` arrives with old slot names — map to universal names at the top of the function:
```python
price_token1 = live_prices.get('price_1a')   # spot token (real price ✓)
# price_token4 = live_prices.get('price_3b') — 10.10101 placeholder, do NOT use
```
Use `price_token1` (spot) as proxy for the perp price. Basis < 1%, acceptable for a 5% threshold.

---

## Position Fields Used

From `position.to_dict()`:

| Field | Value |
|-------|-------|
| `entry_token1_price` | spot entry price |
| `entry_token4_price` | perp entry price at position open |
| `entry_token1_amount` | spot tokens currently lent |
| `entry_liquidation_distance` | configured `d` (e.g., 0.20) |
| `deployment_usd` | total capital deployed |
| `l_a` | = 1/(1+d) |
| `protocol_a` | lending protocol name |
| `protocol_b` | 'Bluefin' |
| `token1` | spot token symbol |
| `token4` | perp proxy symbol |

---

## Rebalance Logic

### Pattern (from `check_positions_need_rebalancing`, `position_service.py:2357`)

```
delta = abs(baseline_liq_dist) - abs(live_liq_dist)
requires_rebalance = delta >= REBALANCE_THRESHOLD   # config/settings.py, default 0.05
```

- **baseline_liq_dist** = liq distance at entry = `d` (by design, always)
- **live_liq_dist** = current liq distance using spot price as perp proxy

### Liq distance formula (short perp)

Short perp is liquidated when price *rises* to `liq_price_token4`:

```
liq_price_token4 = entry_token4_price × (1 + d)
live_liq_dist    = (liq_price_token4 - price_token1) / price_token1
```

---

## Rebalance Action

When price has risen, reduce the spot + perp position and move capital to Bluefin collateral to restore `d`.

### Derivation

```
new_token1_amount = deployment_usd / (price_token1 × (1 + d))
Δ_tokens          = entry_token1_amount − new_token1_amount
Δ_usdc            = Δ_tokens × price_token1
```

Proof: after these steps, new Bluefin margin = `d × deployment_usd / (1+d)`, new leverage = `1/d`, new liq_dist = `d` ✓

### Steps

1. Withdraw `Δ_tokens` token1 from Protocol A lending
2. Cover `Δ_tokens` notional of token4 short perp on Bluefin (simultaneously)
3. Sell `Δ_tokens` token1 → USDC via AMM
4. Deposit `Δ_usdc` USDC into Bluefin as perp margin

---

## Implementation Phases

### Phase 1 — Fix Signature
Replace the current broken signature:
```python
# BEFORE (wrong — crashes with TypeError when called from position_service)
def calculate_rebalance_amounts(self, position, current_prices, target_liquidation_distance, **kwargs):
    pass
```
With the correct signature matching the base class and position_service call:
```python
def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict) -> Dict:
```

### Phase 2 — Implement Liq Distance Check (Trigger)

```python
def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict) -> Dict:
    from config.settings import REBALANCE_THRESHOLD

    # Map old slot names → universal token names (Design Note 18)
    price_token1 = live_prices.get('price_1a')   # spot token (proxy for perp price)
    # price_token4 = live_prices.get('price_3b') — 10.10101 placeholder, do NOT use

    d = float(position['entry_liquidation_distance'])
    entry_token4_price  = float(position['entry_token4_price'])
    entry_token1_amount = float(position['entry_token1_amount'])
    deployment_usd      = float(position['deployment_usd'])

    # Baseline: at entry, liq dist = d (by design)
    baseline_liq_dist = d

    if not entry_token4_price or entry_token4_price <= 0:
        return {
            'requires_rebalance': False,
            'actions': [],
            'reason': 'Cannot check: entry_token4_price (perp entry price) is missing'
        }

    if not price_token1 or price_token1 <= 0:
        return {
            'requires_rebalance': False,
            'actions': [],
            'reason': 'Cannot check: no live token1 (spot) price available'
        }

    liq_price_token4 = entry_token4_price * (1 + d)
    live_liq_dist = (liq_price_token4 - price_token1) / price_token1

    delta = abs(baseline_liq_dist) - abs(live_liq_dist)
    requires_rebalance = delta >= REBALANCE_THRESHOLD

    reason = (
        f'Short perp liq dist: baseline {baseline_liq_dist:.1%}, '
        f'live {live_liq_dist:.1%}, delta {delta:.1%} '
        f'(threshold {REBALANCE_THRESHOLD:.1%})'
    )
```

### Phase 3 — Compute Rebalance Actions

Add to the function after the check:
```python
    actions = []
    if requires_rebalance:
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

    return {
        'requires_rebalance': requires_rebalance,
        'actions': actions,
        'reason': reason
    }
```

---

## Verification

1. **Unit check (Python shell)**:
   ```python
   from analysis.strategy_calculators.perp_lending import PerpLendingCalculator
   calc = PerpLendingCalculator()

   # Mock position at entry (d=0.20, entry spot=3.50, entry perp=3.51)
   pos = {
       'entry_liquidation_distance': 0.20,
       'entry_token4_price': 3.51,
       'entry_token1_amount': 2381.0,   # 10000 / (3.51 × 1.20)
       'deployment_usd': 10000,
       'protocol_a': 'Navi', 'protocol_b': 'Bluefin',
       'token1': 'SUI', 'token4': 'SUI-USDC-PERP',
   }
   prices_at_entry = {'price_1a': 3.50, 'price_2a': None, 'price_2b': None, 'price_3b': 10.10101}
   prices_risen    = {'price_1a': 4.40, 'price_2a': None, 'price_2b': None, 'price_3b': 10.10101}

   r1 = calc.calculate_rebalance_amounts(pos, {}, prices_at_entry)
   assert r1['requires_rebalance'] == False        # delta ≈ 0

   r2 = calc.calculate_rebalance_amounts(pos, {}, prices_risen)
   assert r2['requires_rebalance'] == True         # price rose 25.7%, liq dist shrunk > 5%
   assert len(r2['actions']) == 4
   assert all(k in r2 for k in ('requires_rebalance', 'actions', 'reason'))
   ```

2. **Dashboard manual rebalance**: trigger rebalance on a live `perp_lending` position → no crash, `position_rebalances` table gets new record.
