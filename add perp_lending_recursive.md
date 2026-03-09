# Plan: Add `perp_lending_recursive` Strategy

## Context

Extending `perp_lending` (spot lend + short perp, market-neutral) with a recursive borrow loop. Instead of deploying all capital as spot token + perp margin, the new strategy:
1. Lends the spot token (e.g. BTC) at Protocol A
2. Borrows stablecoin (USDC) against that lent collateral at Protocol A
3. Uses the borrowed stablecoin to buy more spot token → re-lend → repeat
4. Maintains a market-neutral short perp on Bluefin sized to equal total L_A

This amplifies the APR from spot lending while adding a stablecoin borrow cost. It has **two liquidation risks** (opposite directions): Protocol A liq if spot price drops (USDC borrow against spot), and Bluefin liq if spot price rises (short perp). A single `liquidation_distance` parameter governs both (established pattern in `perp_borrowing_recursive`).

---

## Token Slot Convention
- `token1` = spot volatile (e.g. BTC) — **L_A leg**
- `token2` = stablecoin borrowed at Protocol A (e.g. USDC) — **B_A leg**
- `token3` = None (L_B unused)
- `token4` = perp proxy (e.g. BTC-PERP) — **B_B leg**

## Position Multipliers (per $1 deployed)

```
liq_max = liquidation_distance / (1 - liquidation_distance)
r_safe  = liquidation_threshold_1A / ((1 + liq_max) * borrow_weight_2A)
r       = min(r_safe, collateral_ratio_1A)

# Each loop iteration splits: (1-d) → spot, d → perp margin  (same as perp_borrowing_recursive)
q      = r * (1.0 - liquidation_distance)   # geometric series ratio (mirrors perp_borrowing_recursive)
factor = 1.0 / (1.0 - q)

L_A = (1.0 - liquidation_distance) * factor   # = (1-d) / (1 - r*(1-d))
B_A = r * L_A                                  # total stablecoin borrowed at Protocol A
L_B = 0.0
B_B = L_A                                      # market neutral: short perp = spot notional
```

Key property: perp leverage = L_A / total_perp_margin = (1-d)/d — **constant regardless of r**.
Perp liq distance = d/(1-d) (fixed; does not shrink as recursive factor grows).
Protocol A liq distance = governed by r ≤ r_safe.

## APR Formulas

```
gross_apr = L_A * lend_apr_1A - B_A * borrow_apr_2A - B_B * funding_rate_3B
net_apr   = gross_apr - B_B * 2 * BLUEFIN_TAKER_FEE - B_A * borrow_fee_2A - basis_cost
```

---

## Files to Create

### 1. `analysis/strategy_calculators/perp_lending_recursive.py`
New `PerpLendingRecursiveCalculator(PerpLendingCalculator)`:
- `get_strategy_type()` → `'perp_lending_recursive'`
- `get_required_legs()` → 3 (L_A, B_A, B_B; L_B = 0)
- `calculate_positions(liquidation_distance, liquidation_threshold_1A, collateral_ratio_1A, borrow_weight_2A, **kwargs)` → `q = r*(1-d)`, `factor = 1/(1-q)`, `L_A = (1-d)*factor`, `B_A = r*L_A`, `B_B = L_A`
- `calculate_gross_apr(positions, rates)` → extends parent: subtract `B_A * borrow_total_apr_2A`
- `calculate_net_apr(positions, rates, fees, basis_cost)` → extends parent: also subtract `B_A * borrow_fee_2A`
- `analyze_strategy(token1, token2, token4, protocol_a, protocol_b, lend_total_apr_1A, borrow_total_apr_2A, borrow_total_apr_3B, collateral_ratio_1A, liquidation_threshold_1A, price_1A, price_2A, price_3B, ...)` → full strategy dict (same structure as `perp_lending` + `token2` fields + `loop_ratio`, `loop_amplifier`)
- `calculate_rebalance_amounts()` → track token1 (spot lend), token2 (stablecoin borrow), token4 (perp short)
  - Rebalance trigger: same as `perp_lending` (perp liq distance shrinks)
  - Additional: `exit_token2_amount` (stablecoin borrow, scales with token1)

### 2. `analysis/strategy_history/perp_lending_recursive.py`
New `PerpLendingRecursiveHistoryHandler`:
- Extends or mirrors `PerpLendingHistoryHandler` with 3 legs:
  - `(token1_contract, protocol_a)` — spot lend
  - `(token2_contract, protocol_a)` — stablecoin borrow
  - `(token4_contract, protocol_b)` — perp short
- `build_market_data_dict()` → parses 3 rows, returns dict including `borrow_total_apr_2A`, `collateral_ratio_1A`, `liquidation_threshold_1A`, `borrow_weight_2A`

---

## Files to Modify

### 3. `analysis/strategy_calculators/__init__.py`
- Import `PerpLendingRecursiveCalculator` from `.perp_lending_recursive`
- Add `register_calculator(PerpLendingRecursiveCalculator)` after `PerpBorrowingRecursiveCalculator`
- Add to `__all__`

### 4. `config/settings.py` (line 58)
```python
# Before:
PERP_STRATEGIES = ('perp_lending', 'perp_borrowing', 'perp_borrowing_recursive')
# After:
PERP_STRATEGIES = ('perp_lending', 'perp_lending_recursive', 'perp_borrowing', 'perp_borrowing_recursive')
```

### 5. `analysis/rate_analyzer.py`
- Add `_generate_perp_lending_recursive_strategies(calculator)` method:
  - Same iteration as `_generate_perp_lending_strategies()` over `(perp_token, spot_token, protocol_a)`
  - PLUS inner loop over `self.STABLECOINS` as token2 (stablecoin to borrow)
  - Collect for each combination: `collateral_ratio_1A`, `liquidation_threshold_1A`, `borrow_rate_2A`, `borrow_fee_2A`, `borrow_weight_2A`, `price_2A` (for stablecoin at Protocol A)
  - Call `calculator.analyze_strategy()` with all new params
- In `analyze_all_combinations()`: add `elif strategy_type == 'perp_lending_recursive':` dispatch to new generator

### 6. `dashboard/position_renderers.py`
- Add `@register_strategy_renderer('perp_lending_recursive')` decorator alongside existing `@register_strategy_renderer('perp_lending')` on `PerpLendingRenderer`
- In `PerpLendingRenderer.render_strategy_modal_table()`: add conditional B_A row (stablecoin borrow) when `strategy.get('b_a', 0) > 0`
- In `PerpLendingRenderer.render_detail_table()`: add conditional B_A row rendering when `position.get('b_a', 0) > 0`
- Update `build_token_flow_string()` to show `{token1} (Spot) ↔ {token2} (Borrow) ↔ {token4} (Short Perp)` when token2 is present

### 7. `dashboard/dashboard_renderer.py`
- `strategy_type_map` (line 382): add `'perp_lending_recursive': 'Perp Lending (Recursive)'`
- `is_perp` check (line 672): add `'perp_lending_recursive'`
- Token pair display (lines 397-400): add `elif strategy_type == 'perp_lending_recursive': token_pair = f"{row['token1']} ↔ {row['token2']} ↔ {row['token4']}"`
- `entry_basis` (line 641): add `'perp_lending_recursive'` to the `perp_lending` branch (both use `basis_bid`)
- Header rendering (line 677-682): handle `perp_lending_recursive` header
- All other `strategy_type == 'perp_lending'` checks → `strategy_type in ('perp_lending', 'perp_lending_recursive')`

### 8. `dashboard/analysis_tab.py`
- `is_perp` check (line 105): add `'perp_lending_recursive'`
- `is_perp_lending` check (line 195): change to `strategy_type in ('perp_lending', 'perp_lending_recursive')`
- Header render (line 108-113): add `elif strategy_type == 'perp_lending_recursive': ...`
- Rate table columns (line 209): `perp_lending_recursive` uses same columns as `perp_lending` PLUS `borrow_rate_2A` for the stablecoin borrow leg

### 9. `analysis/strategy_history/__init__.py`
- Import `PerpLendingRecursiveHistoryHandler` from `.perp_lending_recursive`
- Register: `register_handler(PerpLendingRecursiveHistoryHandler)` after `PerpLendingHistoryHandler`
- Add to `__all__`

### 10. `analysis/strategy_history/strategy_history.py` (lines 94-99)
The `PERP_STRATEGIES` branch already handles basis lookup. `perp_lending_recursive` uses the same contracts as `perp_lending`:
- `perp_contract = strategy['token4_contract']`
- `spot_contract = strategy['token1_contract']`

Change the existing `if strategy_type == 'perp_lending':` pattern to:
```python
perp_contract = (strategy['token4_contract']
                 if strategy_type in ('perp_lending', 'perp_lending_recursive')
                 else strategy['token3_contract'])
spot_contract = (strategy['token1_contract']
                 if strategy_type in ('perp_lending', 'perp_lending_recursive')
                 else strategy['token2_contract'])
```

---

## Key Design Constraints (DESIGN_NOTES.md)

- `net_apr` key (not `apr_net`) in all calculator output — already enforced by base class
- `width="stretch"` not `use_container_width=True` in all new `st.dataframe()` calls
- No `.get()` with defaults on required fields — use direct key access
- Fail loudly: raise `ValueError` for missing required data, no silent fallbacks
- Rates as decimals (0.0–1.0) internally, convert to % only at display
- Perp funding sign convention: negative = shorts earn

---

## Verification

1. **Analysis tab**: Select timestamp → enable `perp_lending_recursive` strategy type → confirm strategies appear in table with token pair `BTC ↔ USDC ↔ BTC-PERP`
2. **Strategy modal**: Click strategy row → modal shows 3-leg detail (spot lend, stablecoin borrow, short perp) with correct APR breakdown
3. **Deploy**: Deploy a `perp_lending_recursive` position → confirm `create_position()` inserts correctly with token2 (stablecoin), token4 (perp)
4. **Positions tab**: Active position renders with all 3 legs visible, liq distances shown
5. **Strategy history**: History chart loads for a deployed position (basis data fetched using token4_contract + token1_contract)
6. **APR sanity check**: `perp_lending_recursive` net_apr > `perp_lending` net_apr when stablecoin borrow rate < spot lending APR amplification gain
