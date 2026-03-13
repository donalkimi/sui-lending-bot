# Plan: Single source of truth for all APR calculations

## Context

APR calculations are duplicated across two code paths:
- **Strategy calculators** (`analysis/strategy_calculators/*.py`) — for undeployed strategies in the allocation tab
- **Position statistics** (`analysis/position_statistics_calculator.py:287-306`) — inline duplicate for live positions
- **Basis-adjusted APR** (`analysis/position_service.py:1282-1316`) — standalone function, not shared

Goal: consolidate so that `calculate_net_apr()` and a new `calculate_basis_adj_net_apr()` on each strategy calculator are the **only** place APR formulas exist. Both the allocation tab and live positions call the same functions.

---

## Step 1: Remove `basis_cost` from `calculate_net_apr()` in perp calculators

`basis_cost` is market-dependent, not a deterministic protocol fee. It belongs in a separate function.

### `analysis/strategy_calculators/perp_lending.py`

**Line 102:** Remove `basis_cost` parameter
**Line 127:** Change `return gross_apr - perp_fee - basis_cost` → `return gross_apr - perp_fee`

### `analysis/strategy_calculators/perp_borrowing.py`

**Line 60-61:** Remove `basis_cost` parameter
**Line 71:** Change `return gross - perp_fees - borrow_fee - basis_cost` → `return gross - perp_fees - borrow_fee`

### `analysis/strategy_calculators/base.py`

**Line 123-126:** Remove `basis_cost` from abstract method signature:
```python
# Before
def calculate_net_apr(self, positions, rates, fees, basis_cost: float = 0.0) -> float:
# After
def calculate_net_apr(self, positions, rates, fees) -> float:
```

### Non-perp calculators (stablecoin_lending, noloop, recursive_lending)

Already don't use `basis_cost` — just remove the parameter from signatures if present.

---

## Step 2: Add `calculate_basis_adj_net_apr()` to base class + each calculator

### `analysis/strategy_calculators/base.py`

Add a **concrete** method (not abstract) with a default implementation:

```python
def calculate_basis_adj_net_apr(self, positions, rates, fees, basis_cost: float = 0.0) -> float:
    """Net APR minus basis cost. For non-perp strategies, returns net_apr unchanged."""
    return self.calculate_net_apr(positions, rates, fees) - basis_cost
```

This works for all strategies:
- Non-perp: callers pass `basis_cost=0.0` (default) → returns `net_apr`
- Perp: callers pass the actual basis cost → returns `net_apr - basis_cost`

No override needed in any subclass — the base implementation is correct for all.

---

## Step 3: Update `analyze_strategy()` in perp calculators

### `perp_lending.py` (~line 266-267)

```python
# Before
net_apr = self.calculate_net_apr(positions=positions, rates=rates, fees={}, basis_cost=basis_cost)

# After
net_apr = self.calculate_net_apr(positions=positions, rates=rates, fees={})
basis_adj_net_apr = self.calculate_basis_adj_net_apr(positions=positions, rates=rates, fees={}, basis_cost=basis_cost)
```

Add `'basis_adj_net_apr': basis_adj_net_apr` to result dict (~line 308).

### `perp_borrowing.py` (~line 190)

Same pattern. Add to result dict (~line 222).

### Non-perp calculators

In each `analyze_strategy()`, add:
```python
'basis_adj_net_apr': net_apr   # No basis cost for non-perp
```

### Time-adjusted APRs (apr5/apr30/apr90)

**No change.** These use `total_upfront_fee = perp_fee + basis_cost` which is computed independently in `analyze_strategy()`. The `basis_cost` variable is still calculated there — it's just no longer passed to `calculate_net_apr()`.

---

## Step 4: Refactor `position_statistics_calculator.py` to call calculators

### Replace lines 270-306 with:

```python
# 7. Calculate current APR via strategy calculator (single source of truth)
from analysis.strategy_calculators import get_calculator

calc = get_calculator(position['strategy_type'])

positions_dict = {'l_a': l_a, 'b_a': b_a, 'l_b': l_b, 'b_b': b_b}
rates_dict = {
    'lend_total_apr_1A': get_rate_func(position['token1_contract'], position['protocol_a'], 'lend'),
    'borrow_total_apr_2A': get_rate_func(position['token2_contract'], position['protocol_a'], 'borrow')
                           if position.get('token2_contract') else 0.0,
    'lend_total_apr_2B': get_rate_func(position['token3_contract'], position['protocol_b'], 'lend')
                         if position.get('token3_contract') else 0.0,
    'borrow_total_apr_3B': get_rate_func(position['token4_contract'], position['protocol_b'], 'borrow')
                           if position.get('token4_contract') else 0.0,
}
fees_dict = {
    'borrow_fee_2A': get_borrow_fee_func(position['token2_contract'], position['protocol_a'])
                     if position.get('token2_contract') else 0.0,
    'borrow_fee_3B': get_borrow_fee_func(position['token4_contract'], position['protocol_b'])
                     if position.get('token4_contract') else 0.0,
}

current_apr = calc.calculate_net_apr(positions_dict, rates_dict, fees_dict)

# Basis-adjusted APR: for perp strategies, subtract basis cost (basis_pnl / deployment_usd)
basis_cost_apr = (basis_pnl / deployment_usd) if deployment_usd > 0 else 0.0
basis_adj_current_apr = calc.calculate_basis_adj_net_apr(
    positions_dict, rates_dict, fees_dict, basis_cost=basis_cost_apr
)
```

Note: `basis_pnl` is already computed at line 171-172. For live positions, `basis_cost` = `basis_pnl / deployment_usd` (the realised basis drift as a fraction of capital — same convention as the strategy calculators use for `basis_spread × weight`).

### Add to return dict (line 309):

```python
'basis_adj_current_apr': basis_adj_current_apr,
```

---

## Step 5: Remove `compute_basis_adjusted_current_apr()` from position_service.py

### `analysis/position_service.py`

Delete lines 1282-1316 (`compute_basis_adjusted_current_apr` static method).

### `dashboard/position_renderers.py`

**Line 2360:** Replace:
```python
# Before
current_apr_incl_basis = PositionService.compute_basis_adjusted_current_apr(position, stats)
# After
current_apr_incl_basis = stats.get('basis_adj_current_apr')
```

**Line 2527:** Same replacement.

Both call sites now read the pre-computed value from stats (already in DB from Step 4).

---

## Step 6: Add `basis_adj_net_apr` column to allocation tab

### `dashboard/dashboard_renderer.py`

**base_columns (~line 2903):** Add `'basis_adj_net_apr'` after `'net_apr'`
**column_names (~line 2950):** Add `'Basis-Adj APR'` in matching position
**Percentage conversion (~line 2933):** Add `display_df['basis_adj_net_apr'] = display_df['basis_adj_net_apr'] * 100`
**column_config (~line 2976):** Add `'Basis-Adj APR': st.column_config.NumberColumn(format="%.2f%%")`

---

## Files modified

| File | What changes |
|---|---|
| `analysis/strategy_calculators/base.py` | Remove `basis_cost` from abstract `calculate_net_apr()`, add concrete `calculate_basis_adj_net_apr()` |
| `analysis/strategy_calculators/perp_lending.py` | Remove `basis_cost` from `calculate_net_apr()`, add `basis_adj_net_apr` to result dict |
| `analysis/strategy_calculators/perp_borrowing.py` | Same as perp_lending |
| `analysis/strategy_calculators/stablecoin_lending.py` | Add `basis_adj_net_apr` to result dict (= net_apr) |
| `analysis/strategy_calculators/noloop_cross_protocol.py` | Add `basis_adj_net_apr` to result dict (= net_apr) |
| `analysis/strategy_calculators/recursive_lending.py` | Add `basis_adj_net_apr` to result dict (= net_apr) |
| `analysis/position_statistics_calculator.py` | Replace inline APR calc (lines 270-306) with calculator calls |
| `analysis/position_service.py` | Delete `compute_basis_adjusted_current_apr()` (lines 1282-1316) |
| `dashboard/position_renderers.py` | Lines 2360, 2527: read from stats instead of calling deleted function |
| `dashboard/dashboard_renderer.py` | Add `basis_adj_net_apr` column to allocation tab table |

---

## Verification

1. **Allocation tab:** New "Basis-Adj APR" column visible. For perp strategies: lower than Net APR. For non-perp: equals Net APR.
2. **Positions tab:** Current APR and basis-adjusted APR display unchanged (same values, different source).
3. **Net APR values for perp strategies go UP** (basis_cost no longer subtracted). This is intentional — basis cost is now shown separately.
4. **apr5/apr30/apr90 unchanged** — still account for basis in time-adjustment via `total_upfront_fee`.
5. **Regression check:** Compare a few strategy rows before/after. `old_net_apr ≈ new_basis_adj_net_apr`. `new_net_apr = old_net_apr + basis_cost`.
