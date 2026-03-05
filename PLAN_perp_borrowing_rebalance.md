# Plan: perp_borrowing / perp_borrowing_recursive — Rebalance Implementation

## Context

`perp_borrowing` lends stablecoin (token1) on Protocol A, borrows a volatile token (token2), sells it spot, and goes long the perp (token3) on Bluefin. It has **dual liquidation risk** from opposite price moves:

| Leg | Token | Liq when | Protocol |
|-----|-------|----------|----------|
| B_A borrow | token2 (volatile) | price **rises** | Protocol A |
| L_B long perp | token3 (perp proxy) | price **drops** | Bluefin |

`perp_borrowing_recursive` is identical in structure — only the multipliers are amplified by `1/(1 − r(1−d))`. Since the amplification is already baked into stored entry amounts, the same rebalance logic applies.

**Current bugs in `perp_borrowing.py:289`:**
1. **Wrong signature** — uses `current_prices, target_liquidation_distance` instead of `live_rates, live_prices` → `TypeError`
2. **Returns `{'requires_rebalance': False}` always** — missing `actions` and `reason`; manual rebalance is silently ignored

`perp_borrowing_recursive` inherits from `PerpBorrowingCalculator` — same bugs by inheritance unless overridden (it should not be overridden).

**Files to modify:**
- [analysis/strategy_calculators/perp_borrowing.py:289](analysis/strategy_calculators/perp_borrowing.py#L289)
- [analysis/strategy_calculators/perp_borrowing_recursive.py](analysis/strategy_calculators/perp_borrowing_recursive.py) — verify no override (read-only)

---

## Token Convention (Design Note 18)

| Weight | Token | Role |
|--------|-------|------|
| L_A | token1 | Stablecoin (USDC) — collateral at Protocol A |
| B_A | token2 | Volatile token (SUI, BTC…) — borrowed from Protocol A, sold spot |
| L_B | token3 | Perp proxy (SUI-USDC-PERP) — long on Bluefin |
| B_B | token4 | NULL (unused) |

`live_prices` arrives with old slot names — map to universal names at the top of the function:
```python
price_token1 = live_prices.get('price_1a')   # USDC ≈ 1.0 (real price ✓)
price_token2 = live_prices.get('price_2a')   # volatile spot price (real price ✓)
# price_token3 = live_prices.get('price_2b') — 10.10101 placeholder, do NOT use
```
Use `price_token2` (volatile spot) as proxy for the long perp price. Basis < 1%.

---

## Position Fields Used

From `position.to_dict()`:

| Field | Value |
|-------|-------|
| `entry_token1_price` | USDC entry price ≈ 1.0 |
| `entry_token2_price` | volatile entry price |
| `entry_token3_price` | perp entry price (long) at position open |
| `entry_token1_amount` | USDC collateral posted |
| `entry_token2_amount` | volatile tokens borrowed |
| `entry_token3_amount` | perp notional (= token2 amount, market neutral) |
| `entry_token1_liquidation_threshold` | Protocol A LLTV for USDC collateral |
| `entry_token2_borrow_weight` | borrow weight for volatile token |
| `entry_liquidation_distance` | configured `d` (e.g., 0.20) — same for both legs |
| `deployment_usd` | total capital deployed |
| `l_a`, `b_a`, `l_b` | position multipliers |
| `protocol_a` | lending protocol name |
| `protocol_b` | 'Bluefin' |
| `token1`, `token2`, `token3` | token symbols |

---

## Rebalance Logic

### Pattern (from `check_positions_need_rebalancing`, `position_service.py:2357`)

```
delta = abs(baseline_liq_dist) - abs(live_liq_dist)
requires_rebalance = delta >= REBALANCE_THRESHOLD   # config/settings.py, default 0.05
```

Checked independently for **both legs**. Either leg breaching threshold triggers rebalance.

### Leg 1 — token2 B_A (Protocol A borrow)

Uses `PositionCalculator.calculate_liquidation_price()` from [analysis/position_calculator.py:23](analysis/position_calculator.py#L23):

```python
# Baseline: entry token amounts × entry prices
baseline_result_token2 = calculator.calculate_liquidation_price(
    collateral_value=entry_token1_amount * entry_token1_price,
    loan_value=entry_token2_amount * entry_token2_price,
    lending_token_price=entry_token1_price,
    borrowing_token_price=entry_token2_price,
    lltv=liq_threshold,
    side='borrowing',
    borrow_weight=borrow_weight
)
baseline_liq_dist_token2 = baseline_result_token2['pct_distance']   # ≈ d at entry

# Live: same token amounts × live prices
live_result_token2 = calculator.calculate_liquidation_price(
    collateral_value=entry_token1_amount * price_token1,
    loan_value=entry_token2_amount * price_token2,
    lending_token_price=price_token1,
    borrowing_token_price=price_token2,
    lltv=liq_threshold,
    side='borrowing',
    borrow_weight=borrow_weight
)
live_liq_dist_token2 = live_result_token2['pct_distance']
```

### Leg 2 — token3 L_B (Bluefin long perp)

Long perp is liquidated when price *drops* to `liq_price_token3`:

```python
# Baseline: at entry, liq dist = d (by design)
baseline_liq_dist_token3 = d

# Live: use volatile spot price as perp proxy
liq_price_token3 = entry_token3_price * (1 - d)
live_liq_dist_token3 = (price_token2 - liq_price_token3) / price_token2
```

---

## Rebalance Action

> ⚠️ **TO BE DEFINED** — pending further instruction from user.
>
> The rebalance action steps for `perp_borrowing` (what to buy/sell/adjust on each protocol to restore `d` on both legs) have not yet been specified. This section will be completed before implementation begins.
>
> Key questions to resolve:
> - When token2 price rises (B_A liq risk): reduce borrow + reduce long perp proportionally? Or add USDC collateral?
> - When token3 price drops (L_B liq risk): add Bluefin margin? Or reduce long perp size?
> - When both legs breach simultaneously: can a single set of actions fix both?

---

## Implementation Phases

### Phase 1 — Fix Signature
Replace the current broken signature:
```python
# BEFORE (wrong)
def calculate_rebalance_amounts(self, position, current_prices, target_liquidation_distance, **kwargs):
    return {'requires_rebalance': False}
```
With the correct signature:
```python
def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict) -> Dict:
```

### Phase 2 — Implement Liq Distance Check (Trigger)

```python
def calculate_rebalance_amounts(self, position: Dict, live_rates: Dict, live_prices: Dict) -> Dict:
    from config.settings import REBALANCE_THRESHOLD
    from analysis.position_calculator import PositionCalculator

    # Map old slot names → universal token names (Design Note 18)
    price_token1 = live_prices.get('price_1a')   # USDC ≈ 1.0
    price_token2 = live_prices.get('price_2a')   # volatile (also used as perp proxy)
    # price_token3 = live_prices.get('price_2b') — 10.10101 placeholder, do NOT use

    if not price_token1 or price_token1 <= 0 or not price_token2 or price_token2 <= 0:
        return {
            'requires_rebalance': False,
            'actions': [],
            'reason': 'Cannot check: missing live token1/token2 prices'
        }

    d = float(position['entry_liquidation_distance'])
    entry_token1_amount = float(position['entry_token1_amount'])
    entry_token2_amount = float(position['entry_token2_amount'])
    entry_token1_price  = float(position['entry_token1_price'])
    entry_token2_price  = float(position['entry_token2_price'])
    entry_token3_price  = float(position['entry_token3_price'])
    liq_threshold       = float(position['entry_token1_liquidation_threshold'])
    borrow_weight       = float(position['entry_token2_borrow_weight'])

    calculator = PositionCalculator()

    # --- Baseline liq distances (entry prices = TARGET) ---
    baseline_result_token2 = calculator.calculate_liquidation_price(
        collateral_value=entry_token1_amount * entry_token1_price,
        loan_value=entry_token2_amount * entry_token2_price,
        lending_token_price=entry_token1_price,
        borrowing_token_price=entry_token2_price,
        lltv=liq_threshold,
        side='borrowing',
        borrow_weight=borrow_weight
    )
    baseline_liq_dist_token2 = baseline_result_token2['pct_distance']
    baseline_liq_dist_token3 = d   # long perp baseline = d by design

    # --- Live liq distances ---
    live_result_token2 = calculator.calculate_liquidation_price(
        collateral_value=entry_token1_amount * price_token1,
        loan_value=entry_token2_amount * price_token2,
        lending_token_price=price_token1,
        borrowing_token_price=price_token2,
        lltv=liq_threshold,
        side='borrowing',
        borrow_weight=borrow_weight
    )
    live_liq_dist_token2 = live_result_token2['pct_distance']

    liq_price_token3    = entry_token3_price * (1 - d)
    live_liq_dist_token3 = (price_token2 - liq_price_token3) / price_token2

    # --- Check threshold ---
    delta_token2 = abs(baseline_liq_dist_token2) - abs(live_liq_dist_token2)
    delta_token3 = abs(baseline_liq_dist_token3) - abs(live_liq_dist_token3)

    needs_token2 = delta_token2 >= REBALANCE_THRESHOLD
    needs_token3 = delta_token3 >= REBALANCE_THRESHOLD
    requires_rebalance = needs_token2 or needs_token3

    reason = (
        f'token2 (B_A): baseline {baseline_liq_dist_token2:.1%} → live {live_liq_dist_token2:.1%} (Δ {delta_token2:.1%}); '
        f'token3 (L_B): baseline {baseline_liq_dist_token3:.1%} → live {live_liq_dist_token3:.1%} (Δ {delta_token3:.1%}); '
        f'threshold {REBALANCE_THRESHOLD:.1%}'
    )
```

### Phase 3 — Compute Rebalance Actions

> ⚠️ **Blocked — rebalance action definition pending.** See "Rebalance Action" section above.

Placeholder to return informational actions until defined:
```python
    actions = []
    if needs_token2:
        actions.append({'description': f'token2 (B_A) liq dist shrunk by {delta_token2:.1%} — action TBD'})
    if needs_token3:
        actions.append({'description': f'token3 (L_B) liq dist shrunk by {delta_token3:.1%} — action TBD'})

    return {
        'requires_rebalance': requires_rebalance,
        'actions': actions,
        'reason': reason
    }
```

### Phase 4 — Verify `perp_borrowing_recursive` Inherits Correctly

Read `perp_borrowing_recursive.py` and confirm it does **not** override `calculate_rebalance_amounts`. If it does override (with the old broken stub), remove the override so it inherits the fixed parent implementation.

---

## Verification

1. **Unit check (Python shell)**:
   ```python
   from analysis.strategy_calculators.perp_borrowing import PerpBorrowingCalculator
   calc = PerpBorrowingCalculator()

   pos = {
       'entry_liquidation_distance': 0.20,
       'entry_token1_price': 1.0,   'entry_token1_amount': 10000,
       'entry_token2_price': 3.50,  'entry_token2_amount': 1828.6,  # r × D / P2_entry
       'entry_token3_price': 3.51,  'entry_token3_amount': 1828.6,
       'entry_token1_liquidation_threshold': 0.80,
       'entry_token2_borrow_weight': 1.0,
       'deployment_usd': 10000,
       'protocol_a': 'Navi', 'protocol_b': 'Bluefin',
       'token1': 'USDC', 'token2': 'SUI', 'token3': 'SUI-USDC-PERP',
   }
   prices_at_entry = {'price_1a': 1.0, 'price_2a': 3.50, 'price_2b': 10.10101, 'price_3b': None}
   prices_risen    = {'price_1a': 1.0, 'price_2a': 4.40, 'price_2b': 10.10101, 'price_3b': None}
   prices_dropped  = {'price_1a': 1.0, 'price_2a': 2.50, 'price_2b': 10.10101, 'price_3b': None}

   r1 = calc.calculate_rebalance_amounts(pos, {}, prices_at_entry)
   assert r1['requires_rebalance'] == False

   r2 = calc.calculate_rebalance_amounts(pos, {}, prices_risen)
   assert r2['requires_rebalance'] == True   # token2 price rose → B_A liq dist shrunk

   r3 = calc.calculate_rebalance_amounts(pos, {}, prices_dropped)
   assert r3['requires_rebalance'] == True   # token2/perp price dropped → L_B liq dist shrunk

   assert all(k in r1 for k in ('requires_rebalance', 'actions', 'reason'))
   ```

2. **Verify recursive inherits**: instantiate `PerpBorrowingRecursiveCalculator` and confirm it passes the same checks.

3. **Dashboard manual rebalance**: trigger rebalance on a live `perp_borrowing` position → no crash, `position_rebalances` table gets new record.
