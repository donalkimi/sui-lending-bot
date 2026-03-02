# Plan: Fix perp_borrowing earnings calculation (Net APR bug)

## Context

**Correct mental model:**
- token3 = the perp contract (e.g. WAL-USDC-PERP) — distinct from token2 (WAL spot) even if same underlying.
- Which *leg* the perp occupies is determined by the weight matrix (l_a, b_a, l_b, b_b):
  - `perp_borrowing / recursive`: l_a=1, b_a=r, **l_b=r** (perp), b_b=0 → perp = **leg 2b** (Lend)
  - `perp_lending`:              l_a=1/(1+d), b_a=0, l_b=0, **b_b=l_a** (perp) → perp = **leg 3b** (Borrow)

**Docs (`BorrowLend_Perp_strategy.md`) are correct** — token3 is the perp for both strategies. No doc fix needed for the token table.

**Root cause of Net APR -13.89% (should be ~+185%):**

`position_statistics_calculator.py` calls **both** leg '2b' (Lend) AND leg '3b' (Borrow) for all strategies.
For perp_borrowing both resolve to the WAL-USDC-PERP contract (via `_get_token_contract_for_leg` special case)
with rate 1.18. The Lend call adds +1.18 to earnings; the Borrow call subtracts −1.18. They cancel to 0.
Only USDC lend − WAL borrow = −11% remains → Net APR −13.89%.

**What already works correctly (do not change):**
- `position_service._get_token_contract_for_leg('2b', perp_borrowing)` → already returns `token3_contract` ✓
- `entry_token_amount_2b` already stores perp token count ✓
- `calculate_leg_earnings_split(pos, '2b', 'Lend', ...)` already correctly queries lend_base_apr = 1.18 ✓
- `current_apr` calculation in `position_statistics_calculator.py` lines 256-259 already correct ✓

**Secondary issue — `compute_basis_adjusted_current_apr` (position_renderers.py ~L789):**
Uses `entry_price_2b` (= WAL spot price P2_A) as the perp entry price, not the actual perp ask
price `entry_price_3b` (= P3_B). Live perp price fetched via `get_price_with_fallback(token2, protocol_b)`
returns WAL oracle/spot price. Both entry and live use spot → basis_pnl ≈ 0 → basis adjustment useless.

---

## Changes

### 1. Fix earnings — analysis/position_statistics_calculator.py

**Define `_strat` early (before line 120, near line 68 where position params are extracted):**

    _strat = position.get('strategy_type', '')

**Replace lines 131-133 (leg 3b live segment call):**

    # perp_borrowing: perp lives in leg 2b (already called above with 'Lend').
    # Leg 3b is N/A — skip it to avoid double-counting the perp funding.
    if _strat in ('perp_borrowing', 'perp_borrowing_recursive'):
        base_3B, reward_3B = 0.0, 0.0
    else:
        base_3B, reward_3B = service.calculate_leg_earnings_split(
            live_position, '3b', 'Borrow', segment_start_ts, timestamp
        )

**Replace lines 205-207 (leg 3b rebalance loop call — same logic):**

    if _strat in ('perp_borrowing', 'perp_borrowing_recursive'):
        rebal_base_3B, rebal_reward_3B = 0.0, 0.0
    else:
        rebal_base_3B, rebal_reward_3B = service.calculate_leg_earnings_split(
            rebal_as_pos, '3b', 'Borrow', opening_ts_rebal, closing_ts_rebal
        )

**Remove now-redundant `_strat` at line ~255** (already defined early above).

### 2. Fix basis calc — dashboard/position_renderers.py, compute_basis_adjusted_current_apr (~L789)

For perp_borrowing, fix entry_perp_price and live_perp_price:

    else:  # perp_borrowing / perp_borrowing_recursive
        spot_tokens      = _safe_float(position.get('entry_token_amount_2a', 0.0))
        perp_tokens      = _safe_float(position.get('entry_token_amount_2b', 0.0))
        entry_spot_price = _safe_float(position.get('entry_price_2a', 0.0))
        entry_perp_price = _safe_float(position.get('entry_price_3b', 0.0))  # fix: P3_B not P2_B
        live_spot_price  = get_price_with_fallback(position['token2'], position['protocol_a'])
        live_perp_price  = get_price_with_fallback(position['token3'], position['protocol_b'])  # fix: token3 is the perp proxy

### 3. Fix strategy calculator — analysis/strategy_calculators/perp_borrowing.py

Change `'P2_B': price_2A` to `'P2_B': price_3B` so that new positions store the correct perp
entry price in `entry_price_2b`. (Existing positions already have `entry_price_3b` = correct perp price.)

    'P2_B': price_3B,   # perp ask price (was: price_2A = spot, wrong)

### 4. Update docs — docs/BorrowLend_Perp_strategy.md

Token table is correct. Add a note clarifying leg mapping vs token naming:

> **Leg mapping note:** token3 is always the perp contract. Which *leg slot* it occupies is
> determined by the weight matrix. For `perp_borrowing`, the perp uses the `l_b` weight → stored
> in leg 2b fields (`entry_token_amount_2b`, `entry_price_2b`). For `perp_lending`, the perp uses
> the `b_b` weight → stored in leg 3b fields. The `_get_token_contract_for_leg('2b', perp_borrowing)`
> special case in `position_service.py` routes leg 2b to `token3_contract` for perp_borrowing.
> Leg 3b is N/A for perp_borrowing (b_b=0) — do not include in earnings calculations.

---

## Files modified

| File | Change |
|------|--------|
| `analysis/position_statistics_calculator.py` | Skip leg '3b' for perp_borrowing earnings (primary fix) |
| `dashboard/position_renderers.py` | Fix basis calc to use entry_price_3b and token3 for live perp price |
| `analysis/strategy_calculators/perp_borrowing.py` | Fix P2_B = price_3B (perp price, not spot) for new positions |
| `docs/BorrowLend_Perp_strategy.md` | Add leg mapping note (token table already correct) |

---

## Expected result after pipeline refresh

    Base Earnings:  ~+$143  (was -$12.21: perp cancellation removed, +1.18 now net positive)
    Net APR:        ~+180%  (was -13.89%)
    Current APR:    185.27% (unchanged — already correct)
    Basis-adj APR:  shows real basis divergence (was ≈ current_apr, useless)

## No DB migration needed for existing positions
(entry_price_3b already stores correct perp price; earnings calc uses rates_snapshot not entry_price)
