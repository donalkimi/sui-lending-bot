# Variable Cleanup: Rename `_1A/_2A/_2B/_3B` → `_token1/_token2/_token3/_token4`

## Context

After the universal refactoring to token1/2/3/4 slot naming, the `RecursiveLendingCalculator` (and its call site in `rate_analyzer.py`) still uses old positional-leg suffixes (`_1A`, `_2A`, `_2B`, `_3B`). These need renaming throughout for consistency with the universal convention.

Also: `base.py` still uses the old key names in the fees dict interface, and other calculators pass old-named keys — once renamed here, all must be updated together.

---

## Files and Changes

### 1. `analysis/strategy_calculators/recursive_lending.py`

**`analyze_strategy()` parameter names:**

| Old | New |
|-----|-----|
| `lend_total_apr_1A` | `lend_total_apr_token1` |
| `borrow_total_apr_2A` | `borrow_total_apr_token2` |
| `lend_total_apr_2B` | `lend_total_apr_token3` |
| `borrow_total_apr_3B` | `borrow_total_apr_token4` |
| `collateral_ratio_1A` | `collateral_ratio_token1` |
| `collateral_ratio_2B` | `collateral_ratio_token3` |
| `liquidation_threshold_1A` | `liquidation_threshold_token1` |
| `liquidation_threshold_2B` | `liquidation_threshold_token3` |
| `price_1A` | `price_token1` |
| `price_2A` | `price_token2` |
| `price_2B` | `price_token3` |
| `price_3B` | `price_token4` |
| `available_borrow_2A` | `available_borrow_token2` |
| `available_borrow_3B` | `available_borrow_token4` |
| `borrow_fee_2A` | `borrow_fee_token2` |
| `borrow_fee_3B` | `borrow_fee_token4` |
| `borrow_weight_2A` | `borrow_weight_token2` |
| `borrow_weight_3B` | `borrow_weight_token4` |

**Internal rates dict keys** (built in `analyze_strategy`, consumed by `calculate_net_apr` / `calculate_gross_apr`):

| Old key | New key |
|---------|---------|
| `'lend_total_apr_1A'` | `'lend_total_apr_token1'` |
| `'lend_total_apr_2B'` | `'lend_total_apr_token3'` |
| `'borrow_total_apr_2A'` | `'borrow_total_apr_token2'` |
| `'borrow_total_apr_3B'` | `'borrow_total_apr_token4'` |

**`calculate_net_apr()` and `calculate_gross_apr()`:** Update all `rates.get()`/`rates[]` key lookups to match new keys above.

**Internal fees dict keys** (already fixed to pass raw values; key names follow base class interface — update after base class is renamed):

| Old key | New key |
|---------|---------|
| `'borrow_fee_2A'` | `'borrow_fee_token2'` |
| `'borrow_fee_3B'` | `'borrow_fee_token4'` |

---

### 2. `analysis/strategy_calculators/base.py` — `calculate_fee_adjusted_aprs()`

Fee dict key lookups (lines ~262–265):
- `fees.get('borrow_fee_2A')` → `fees.get('borrow_fee_token2')`
- `fees.get('borrow_fee_3B')` → `fees.get('borrow_fee_token4')`
- Update local var names `borrow_fee_2A` → `borrow_fee_token2`, `borrow_fee_3B` → `borrow_fee_token4`
- Propagate to `calculate_apr_for_days()` and `calculate_days_to_breakeven()` call args

---

### 3. `analysis/rate_analyzer.py` (recursive strategy call site, lines ~876–920)

Local variable renames:
- `borrow_fee_4B` → `borrow_fee_token4`
- `borrow_weight_4B` → `borrow_weight_token4`
- `available_borrow_4B` → `available_borrow_token4`

Keyword argument renames in `calculator.analyze_strategy()` call:
- All `_1A=`, `_2A=`, `_2B=`, `_3B=` suffixes → `_token1=`, `_token2=`, `_token3=`, `_token4=` (18 args total)

---

### 4. `analysis/strategy_calculators/noloop_cross_protocol.py`

Fees dict keys passed to `calculate_fee_adjusted_aprs()`:
- `'borrow_fee_2A'` → `'borrow_fee_token2'`
- `'borrow_fee_3B'` → `'borrow_fee_token4'`

---

### 5. `analysis/strategy_calculators/stablecoin_lending.py`

Fees dict keys passed to `calculate_fee_adjusted_aprs()`:
- `'borrow_fee_2A'` → `'borrow_fee_token2'`
- `'borrow_fee_3B'` → `'borrow_fee_token4'`

---

## Order of Changes

Do files 4 and 5 last (after base class updated) to avoid a broken intermediate state. Safest order: `base.py` → `recursive_lending.py` → `noloop_cross_protocol.py` → `stablecoin_lending.py` → `rate_analyzer.py`.
