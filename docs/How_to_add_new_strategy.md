# How to Add a New Strategy Type

Reference document based on implementing `perp_lending_recursive`. Update as new strategies are added and new issues are discovered.

---

## Overview

A "strategy" in this system is a combination of legs (lend/borrow/perp positions) across protocols. Adding a new strategy type requires changes in three layers:

1. **Analysis layer** — calculator (maths), generator (data collection), history handler (historical APR)
2. **Dashboard layer** — renderer (display), various type-check branches throughout
3. **Config** — settings constants, registration

---

## Checklist: All Files to Touch

### Files to Create
| File | Purpose |
|------|---------|
| `analysis/strategy_calculators/<type>.py` | `*Calculator` class — positions, APR maths |
| `analysis/strategy_history/<type>.py` | `*HistoryHandler` class — historical leg data |

### Files to Modify
| File | What to change |
|------|---------------|
| `config/settings.py` | Add to strategy grouping constants |
| `analysis/strategy_calculators/__init__.py` | Import + `register_calculator()` + `__all__` |
| `analysis/strategy_history/__init__.py` | Import + `register_handler()` + `__all__` |
| `analysis/rate_analyzer.py` | Generator method + dispatcher |
| `dashboard/position_renderers.py` | Renderer class (register + extend) |
| `dashboard/dashboard_renderer.py` | Multiple type-check branches (see below) |
| `dashboard/analysis_tab.py` | Header render + rate table columns |
| `analysis/strategy_history/strategy_history.py` | Basis contract lookup |

---

## Step-by-Step Process

### Step 1: Add to `config/settings.py` FIRST

Add your strategy to the appropriate grouping constant. **Never hardcode strategy type strings inline anywhere else — always use these constants.**

```python
# If adding a perp lending variant:
PERP_LENDING_STRATEGIES  = ('perp_lending', 'perp_lending_recursive', 'your_new_type')
PERP_BORROWING_STRATEGIES = ('perp_borrowing', 'perp_borrowing_recursive')
PERP_STRATEGIES = PERP_LENDING_STRATEGIES + PERP_BORROWING_STRATEGIES

# If adding a completely new category, add a new group:
MY_NEW_STRATEGIES = ('new_strategy', 'new_strategy_recursive')
```

Do this first because every other file imports from settings.

---

### Step 2: Create the Calculator

`analysis/strategy_calculators/<type>.py`

**Pattern:** inherit from the closest parent calculator.

```python
class MyNewCalculator(ParentCalculator):
    def get_strategy_type(self) -> str:
        return 'my_new_strategy'

    def get_required_legs(self) -> int:
        return 3  # number of active legs

    def calculate_positions(self, liquidation_distance, ..., **kwargs) -> Dict[str, float]:
        # Return {'l_a': ..., 'b_a': ..., 'l_b': ..., 'b_b': ...}
        pass

    def analyze_strategy(self, *args, **kwargs) -> Dict[str, Any]:
        result = super().analyze_strategy(*args, **kwargs)
        if not result['valid']:
            return result
        # Adjust APR fields, add new token fields, add metadata
        result.update({...})
        return result
```

**Critical pitfall: parent `calculate_positions()` must pass `**kwargs`.**
If the parent's `analyze_strategy()` calls `self.calculate_positions(a=x, b=y)` without `**kwargs`, your override won't receive the extra params it needs (e.g. `collateral_ratio_1A`). Fix the parent call:
```python
# In parent's analyze_strategy():
positions = self.calculate_positions(
    liquidation_distance=liquidation_distance,
    collateral_ratio_a=0.0,
    collateral_ratio_b=0.0,
    **kwargs   # ADD THIS — allows subclass overrides to receive extra params
)
```

**Output dict requirements:**
- Always include `'net_apr'` key (not `'apr_net'`) — enforced by base class
- Always include `'valid': True/False`
- Always include `'strategy_type': self.get_strategy_type()`
- Unused leg fields (`token2`, `token3`, etc.) must be set to `None` not omitted
- Rates stored as decimals (0.0–1.0), never percentages

**APR adjustments when calling super():**
If your parent only calculates APR for N legs and your strategy adds leg N+1, adjust after `super()`:
```python
result['apr_gross'] -= b_a * borrow_total_apr_2A
result['net_apr']   -= b_a * borrow_total_apr_2A + b_a * borrow_fee_2A
result['total_upfront_fee'] += b_a * borrow_fee_2A
# Recalculate time-adjusted APRs from scratch:
for N in [5, 30, 90]:
    result[f'apr{N}'] = (result['apr_gross'] * N/365 - result['total_upfront_fee']) * 365/N
```

Fees already handled by parent (e.g. Bluefin taker fees scaled by `b_b`) don't need re-adding — the parent uses the amplified positions from your `calculate_positions()` override.

Register in `analysis/strategy_calculators/__init__.py`:
```python
from .my_new_strategy import MyNewCalculator
register_calculator(MyNewCalculator)
# Add to __all__
```

---

### Step 3: Extend or Create the Generator (`analysis/rate_analyzer.py`)

**Two cases:**

**A. New variant of existing strategy (same token structure, different multipliers):**
Reuse the existing generator — same dispatcher branch. The parent generator calls `calculator.analyze_strategy()` polymorphically, so the new calculator class produces its own strategy type automatically.

Example: `perp_borrowing_recursive` reuses `_generate_perp_borrowing_strategies()` because both `perp_borrowing` and `perp_borrowing_recursive` have the same 3-leg data structure.

**B. New variant that adds extra legs/data not in the existing generator:**
Extend the existing generator to conditionally collect the extra data. Use `calculator.get_required_legs()` to detect which variant is running:
```python
stablecoins = list(self.STABLECOINS) if calculator.get_required_legs() >= 3 else [None]
```

**Dispatcher** — always use settings constants, never hardcode:
```python
# WRONG:
elif strategy_type in ('perp_borrowing', 'perp_borrowing_recursive'):
# CORRECT:
elif strategy_type in settings.PERP_BORROWING_STRATEGIES:
```

**Protocol pre-filtering** — before iterating protocols, filter to those that actually support the token. Use contract address (Design Note #9), check the in-memory DataFrame directly:
```python
spot_row = self.lend_rates[self.lend_rates['Contract'] == spot_contract]
if spot_row.empty:
    print(f"⚠️  [ANALYZER] {spot_contract!r} not found in lend_rates — "
          f"possible coding error. Known: {list(self.lend_rates['Contract'].unique())}")
    continue
valid_protocols = [
    p for p in self.protocols
    if p != 'Bluefin' and p in spot_row.columns and pd.notna(spot_row[p].values[0])
]
```

**Rate existence checks** — only skip if the rate is NaN (token absent at protocol). **Never filter on `rate <= 1e-9`** — near-zero rates are valid market data. Viability is the calculator's job, not the generator's.
```python
# WRONG — silently eliminates valid strategies:
if np.isnan(rate) or rate <= 1e-9:
    continue
# CORRECT — existence check only:
if np.isnan(rate):
    continue
```

---

### Step 4: Create the History Handler

`analysis/strategy_history/<type>.py`

```python
class MyNewHistoryHandler(HistoryHandlerBase):
    def get_strategy_type(self) -> str:
        return 'my_new_strategy'

    def get_required_legs(self) -> int:
        return 3

    def get_required_tokens(self, strategy: Dict) -> List[Tuple[str, str]]:
        return [
            (strategy['token1_contract'], strategy['protocol_a']),
            (strategy['token2_contract'], strategy['protocol_a']),
            (strategy['token4_contract'], strategy['protocol_b']),
        ]

    def build_market_data_dict(self, row_group, strategy) -> Optional[Dict]:
        # Match rows to legs, validate, return dict for calculator
        pass

    def validate_strategy_dict(self, strategy) -> Tuple[bool, str]:
        pass
```

**Key:** use `token4_contract` + `token1_contract` for perp lending variants (B_B slot = token4), and `token3_contract` + `token2_contract` for perp borrowing variants (L_B slot = token3).

Register in `analysis/strategy_history/__init__.py`:
```python
from .my_new_strategy import MyNewHistoryHandler
register_handler(MyNewHistoryHandler)
# Add to __all__
```

**After adding the handler, check `dashboard/position_renderers.py` → `render_position_history_chart()` (~line 1229).**
This function builds a `strategy_dict` from the position row to pass to `get_strategy_history()`. It must include ALL token slots your handler's `validate_strategy_dict()` requires. If any token slot is missing, the history chart raises `ValueError: Missing required fields: tokenX, tokenX_contract`. Add any missing slots:
```python
strategy_dict = {
    ...
    'token4': position.get('token4'),           # ← required if handler uses token4
    'token4_contract': position.get('token4_contract'),
}
```

Also update `analysis/strategy_history/strategy_history.py` — the basis contract lookup:
```python
perp_contract = (strategy['token4_contract']
                 if strategy_type in settings.PERP_LENDING_STRATEGIES
                 else strategy['token3_contract'])
spot_contract = (strategy['token1_contract']
                 if strategy_type in settings.PERP_LENDING_STRATEGIES
                 else strategy['token2_contract'])
```

---

### Step 5: Add/Extend the Renderer (`dashboard/position_renderers.py`)

**Option A: Reuse existing renderer** — add a second decorator:
```python
@register_strategy_renderer('perp_lending')
@register_strategy_renderer('perp_lending_recursive')   # ← add this
class PerpLendingRenderer(StrategyRendererBase):
    ...
```

Multiple decorators are fully supported — each registers the class with a different key.

**Option B: New renderer class** — implement all abstract methods:
- `get_strategy_name()` — display name string
- `build_token_flow_string(position)` — e.g. `"BTC ↔ USDC ↔ BTC-PERP"`
- `validate_position_data(position)` — check required fields
- `get_metrics_layout()` — list of metric keys
- `render_apr_summary_table(strategy, timestamp_seconds)` — strategy selection modal APR overview
- `render_detail_table(position, get_rate, get_borrow_fee, get_price, ...)` — main position detail
- `render_strategy_modal_table(strategy, deployment_usd)` — All Strategies tab popup preview

**Key design notes for renderers:**

- Use direct key access (`strategy['b_a']`), never `.get('b_a', 0)` — Design Note #16
- Wrap in try/except KeyError with debug output, then skip and continue:
  ```python
  try:
      b_a = strategy['b_a']
  except KeyError as e:
      print(f"⚠️  KeyError: {e}. Available: {list(strategy.keys())}")
      # skip this row/field
  ```
- Conditional rows must use `b_a > 0` AND check the token exists
- `safe_value()` is defined inline in `render_detail_table()` — define it BEFORE any code that uses it (not partway through the function)
- Column names in live vs historical rows differ — keep them consistent per branch
- Use `width="stretch"` not `use_container_width=True` (Design Note #6)

---

### Step 6: Update `dashboard/dashboard_renderer.py`

Multiple places need updating. Search for every occurrence of `'perp_lending'` or the nearest existing variant to find them all:

1. **`strategy_type_map`** — add display label:
   ```python
   'my_new_strategy': 'My New Strategy',
   ```

2. **Token pair display** in the All Strategies table:
   ```python
   if strategy_type in settings.PERP_LENDING_STRATEGIES:
       token_pair = f"{row['token1']} ↔ {row['token4']}"  # or adapt for extra legs
   ```

3. **`entry_basis`** — use settings constants:
   ```python
   'entry_basis': (
       strategy.get('basis_bid') if strategy_type in settings.PERP_LENDING_STRATEGIES
       else strategy.get('basis_ask') if strategy_type in settings.PERP_BORROWING_STRATEGIES
       else None
   ),
   ```

4. **Header rendering** in modal:
   ```python
   if strategy_type == 'perp_lending':
       ...
   elif strategy_type == 'perp_lending_recursive':   # ← add
       ...
   ```

5. **`_get_basis` callback** in `show_strategy_modal()`:
   ```python
   if _strategy_type in settings.PERP_LENDING_STRATEGIES:   # ← NOT == 'perp_lending'
       return {'basis_bid': ..., 'spot_bid': ..., 'perp_ask': ...}
   ```
   **This is a common pitfall** — if you only check `== 'perp_lending'`, the new variant gets no basis data and `render_detail_table()` raises "No basis data for perp_lending position".

6. **`enabled_strategy_types` filter** — use `extend()` with settings constants:
   ```python
   if show_perp_lending:
       enabled_strategy_types.extend(settings.PERP_LENDING_STRATEGIES)  # ← NOT append('perp_lending')
   ```
   If you use `append('perp_lending')` instead, new variants are invisible in the dashboard even if generated.

---

### Step 7: Update `dashboard/analysis_tab.py`

1. **Header render** — add `elif` for each new type:
   ```python
   elif strategy_type == 'perp_lending_recursive':
       st.markdown(f"#### {strategy.get('token1')} ↔ {strategy.get('token2')} ↔ {strategy.get('token4')}")
   ```

2. **Token flow fallback** (exception handler):
   ```python
   if strategy_type in settings.PERP_LENDING_STRATEGIES:
       token_flow = f"{t1} ↔ {t2} ↔ {t4}" if t2 else f"{t1} ↔ {t4}"
   ```

3. **Rate table columns** — add extra columns for new legs:
   ```python
   if is_perp_lending:
       record['Lend 1A'] = _fmt(row.get('lend_total_apr_1A'))
       if strategy_type == 'perp_lending_recursive':
           record['Borrow 2A'] = _fmt(row.get('borrow_total_apr_2A'))
       record['Perp 3B'] = ...
   ```

---

---

## Rebalancing: position_service.py Audit

`position_service.py` has multiple hardcoded strategy-type branches that ALL need updating when you add a new perp variant. Missing even one causes silent wrong data or crashes during rebalancing.

**After adding any new perp strategy variant, run this search and update every result:**
```
grep -n "perp_lending\|perp_borrowing" analysis/position_service.py
```

### Known strategy-type branches in position_service.py

| Line (approx) | Function | What it does | Pattern to fix |
|---|---|---|---|
| ~247 | `create_position` token amount calc | `perp_lending` uses market-neutral count match for B_B amount; others use formula | `== 'perp_lending'` → `in settings.PERP_LENDING_STRATEGIES` |
| ~935–940 | `calculate_initial_fees` | `perp_lending` uses `b_b * 2 * TAKER_FEE`; `perp_borrowing*` uses `L_B * 2 * TAKER_FEE` | `== 'perp_lending'` → `in settings.PERP_LENDING_STRATEGIES`; `in (...)` → `in settings.PERP_BORROWING_STRATEGIES` |
| ~1174 | `_get_basis_for_pnl` | Fetches basis data for PnL calculation using token1 (lending) or token2 (borrowing) | `== 'perp_lending'` → `in settings.PERP_LENDING_STRATEGIES` |
| ~1799–1839 | `_query_basis_at_timestamp` | Fetches basis data for rebalance using token1 (lending) or token2 (borrowing) | `== 'perp_lending'` → `in settings.PERP_LENDING_STRATEGIES`; `in (...)` → `in settings.PERP_BORROWING_STRATEGIES` |

### Why the rebalance crash happens (the cascade pattern)

When a perp strategy variant is missing from `_query_basis_at_timestamp`:
1. `strategy_type` falls into the `else: return None` branch
2. `live_basis_dict` is `None`
3. `live_basis_dict['spot_price_token1_bid']` raises `TypeError: 'NoneType' object is not subscriptable`
4. `except Exception` catches it and logs "Unexpected error in rebalance validation"
5. `rebalance_result` was never assigned (exception thrown before that line)
6. Code proceeds to `rebalance_result['exit_token1_amount']` → `UnboundLocalError`

The fix to prevent the crash regardless: initialize `rebalance_result = None` before the try block, guard the snapshot call with `exit_amounts = rebalance_result or {}`.

### calculate_rebalance_amounts() override

If your new strategy has extra legs not present in the parent strategy (e.g. a stablecoin borrow leg), the parent's `calculate_rebalance_amounts()` won't know about it. It will return `exit_token2_amount = None` and no action for that leg.

Override in the subclass calculator to:
1. Call `super().calculate_rebalance_amounts()` to get the parent's result
2. Compute the new leg's exit amount (proportional to the reduced primary leg)
3. Add the repayment/action for that leg
4. Modify the parent's existing actions if the new leg affects their amounts (e.g. stablecoin borrow repayment reduces USDC available for Bluefin margin deposit)

Use direct key access for all required fields — no `.get()` defaults, no `or 0.0` fallbacks (Design Notes #15, #16). Exceptions propagate to the outer try/except in `rebalance_position()` which logs and proceeds gracefully.

---

## After Implementation

### 1. Clear the analysis cache

The dashboard serves cached strategies. After adding a new strategy type, the cache must be regenerated. Either:
- Wait for the next hourly `refresh_pipeline` run
- Or manually delete the stale cache rows: `DELETE FROM analysis_cache WHERE timestamp_seconds = <current>`

### 2. Check the dashboard loads without errors

A syntax error in any dashboard file (even a stray `]`) will prevent the entire module from loading. The symptom is "No detail table renderer registered for strategy type: X" — which looks like a registration error but is actually an import failure. Check Python syntax carefully after any structural edits to renderer files (especially when refactoring list literals to `.append()` calls).

---

## Common Bugs and Pitfalls

| Bug | Symptom | Fix |
|-----|---------|-----|
| Hardcoded `== 'perp_lending'` instead of `in PERP_LENDING_STRATEGIES` | New variant not rendered / missing from filter | Use settings constants everywhere |
| `enabled_strategy_types.append('perp_lending')` instead of `.extend(PERP_LENDING_STRATEGIES)` | New strategy type invisible in All Strategies tab despite being generated | `.extend()` with settings constant |
| `_get_basis` not handling new variant | "No basis data for perp_lending position" error in modal | Update `_get_basis` to use `strategy_type in settings.PERP_LENDING_STRATEGIES` |
| `<= 1e-9` rate guard in generator | Valid strategies silently skipped (e.g. ScallopBorrow with 0% supply rate) | Remove `<= 1e-9`; use only `np.isnan()` for existence check |
| Parent `calculate_positions()` not passing `**kwargs` | Subclass override receives only parent's positional params, missing `collateral_ratio_1A` etc. | Add `**kwargs` to the parent's `calculate_positions()` call |
| `safe_value()` defined after it is used | `NameError: name 'safe_value' is not defined` at runtime | Move `safe_value` definition to before the first usage |
| Stray `]` or `)` left over from refactoring list → append | `SyntaxError: unmatched ']'` — entire module fails to import | Review diffs carefully when converting list literals to `.append()` calls |
| `.get('field', 0)` with default on required field | Silent wrong values (Design Note #16) | Direct key access + try/except KeyError with debug print |
| `value or 0.0` fallback on dict/position fields | Silent wrong values when field is None or missing (Design Note #15) | Direct key access — `position['field']` not `position.get('field') or 0.0` |
| `_query_basis_at_timestamp` hardcoded `== 'perp_lending'` | New perp lending variant gets `None` basis dict → `TypeError: 'NoneType' object is not subscriptable` → `UnboundLocalError` on `rebalance_result` | Use `in settings.PERP_LENDING_STRATEGIES` / `in settings.PERP_BORROWING_STRATEGIES` (4 places in `position_service.py`) |
| `rebalance_result` unbound if try block throws before assignment | `UnboundLocalError: cannot access local variable 'rebalance_result'` | Initialize `rebalance_result = None` before the try block; guard snapshot call with `exit_amounts = rebalance_result or {}` |
| `render_detail_table` passes `borrow_token=None` for new variant that has a B_A borrow leg | No liquidation price/distance shown for the spot lend row (token1) in Positions tab | Detect `b_a > 0 and token2` in `PerpLendingRenderer.render_detail_table()`, populate borrow params (`borrow_token`, `borrow_price_live/entry`, `liquidation_threshold`, `borrow_weight`) in the `_build_lend_leg_row()` call; pass computed liq values to the B_A row too (same Protocol A liquidation event) |
| Analysis cache not invalidated | New strategy type doesn't appear even after all code is correct | Clear cache or wait for next hourly refresh |
| History handler using wrong token slot | Basis lookup fails for new strategy | `perp_lending*` uses `token4_contract`/`token1_contract`; `perp_borrowing*` uses `token3_contract`/`token2_contract` |
| `strategy_dict` built without `token4` | `ValueError: Missing required fields: token4, token4_contract` in APR history chart | `render_position_history_chart()` in `position_renderers.py` line ~1229 — add `'token4': position.get('token4'), 'token4_contract': position.get('token4_contract')` |

---

## Design Notes That Apply to All Strategies

| Note | Rule |
|------|------|
| #6 | `width="stretch"` not `use_container_width=True` in all `st.dataframe()` calls |
| #7 | Rates as decimals internally; convert `* 100` only at display |
| #9 | Use contract addresses for all logic; symbols for display only |
| #16 | No `.get(key, default)` on required fields — direct key access, fail loudly |
| #17 | Perp funding rates stored negative in DB (shorts earn when negative) |
| #18 | Token slot convention: L_A=1A, B_A=2A, L_B=2B, B_B=3B |

---

## Token Slot Convention Quick Reference

| Weight | DB/code slot | Token | Protocol |
|--------|-------------|-------|----------|
| `L_A` | `token1` / `1A` cols | spot or stablecoin lent | `protocol_a` |
| `B_A` | `token2` / `2A` cols | borrowed token | `protocol_a` |
| `L_B` | `token3` / `2B` cols | lent at protocol B | `protocol_b` |
| `B_B` | `token4` / `3B` cols | perp short or borrow at B | `protocol_b` |

`NULL` means the leg is unused (weight = 0). Always guard before looking up rates/prices for unused legs.
