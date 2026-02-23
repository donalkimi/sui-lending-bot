# Perp Borrowing Strategy

## Overview

**Strategy:** Lend stablecoin in Protocol A → borrow token2 → sell token2 spot → buy token2 long perp on Bluefin.

**Market neutrality:** Short spot (borrow + sell token2) offsets long perp (buy token2 perp). Net price exposure to token2 = 0.

**Earn from:**
- Stablecoin lending APR (Protocol A)
- Perp funding rate when shorts pay longs (Bluefin long perp)

**Pay for:**
- Token2 borrow rate (Protocol A)
- Perp entry + exit fees (Bluefin)
- Upfront borrow fee at Protocol A (if any)

---

## Comparison with perp_lending

| Aspect | `perp_lending` | `perp_borrowing` |
|--------|---------------|-----------------|
| What you lend (L_A) | Spot token2 | Stablecoin (USDC) |
| Do you borrow? (B_A) | No | Yes — token2 from Protocol A |
| Bluefin position (L_B / B_B) | Short perp (B_B) | Long perp (L_B) |
| Earn when | Longs pay shorts (+funding) | Shorts pay longs (−funding) |
| Protocol A liq risk | None (lending, not borrowing) | Yes — if token2 price rises |
| Bluefin liq risk | Yes — if token2 price rises | Yes — if token2 price drops |

These two strategies have **opposite sign preferences on the funding rate** and are natural complements.

---

## Tokens and Roles

| Symbol | Role | Protocol |
|--------|------|----------|
| token1 | Stablecoin (USDC, USDY, etc.) — posted as collateral | Protocol A (any lending protocol) |
| token2 | Volatile token (SUI, BTC, etc.) — borrowed and sold | Protocol A (any lending protocol) |
| token3 | Perp contract (e.g., SUI-USDC-PERP) — long position | Protocol B = Bluefin (always) |

---

## Position Multipliers (Non-Looped)

Single iteration only — all USDC from selling token2 is posted as Bluefin perp collateral:

```
L_A = 1.0     (lend all stablecoins in Protocol A)
B_A = r       (borrow r × deployment of token2 from Protocol A)
L_B = r       (long perp notional = r × deployment, market neutral)
B_B = 0       (no borrowing on Bluefin)
```

Where r is determined by Protocol A's collateral parameters:

```
liq_max = liq_dist / (1 − liq_dist)
r_safe  = liquidation_threshold_1A / ((1 + liq_max) × borrow_weight_2A)
r       = min(r_safe, collateral_ratio_1A)
```

---

## Why Looping Is Possible

When you borrow $r of token2 and sell it, you receive $r USDC in cash. You do **not** need to post all of it as Bluefin perp collateral — only enough to maintain your desired liquidation distance on the long perp.

### How much perp collateral is needed?

For a long perp with notional $N and desired liquidation distance `d`:

```
leverage           = 1 / d
collateral_needed  = N / leverage = N × d
```

**Example — d = 20% (5× leverage):**
- Collateral posted = 20% × N
- Surplus USDC (recyclable) = 80% × N

**Key insight:** From the $r USDC proceeds of selling token2:
- Post `d × r` as Bluefin perp collateral (20% if d=0.20)
- Recycle `(1−d) × r` back into Protocol A as fresh USDC collateral to start another loop

---

## Geometric Series Derivation (Looped)

Define:
- `r` = borrow ratio at Protocol A (e.g., 0.64 for USDC at 80% LTV with 20% safety buffer)
- `d` = desired liquidation distance on Bluefin long perp (e.g., 0.20)
- `q = r × (1−d)` = loop ratio (fraction of capital that recycles each iteration)

### Per-Iteration Table (step k = 0, 1, 2, …)

Capital entering Protocol A at step k: `C_k = q^k` (normalized, C_0 = 1)

| Action                           | Amount at step k          |
|----------------------------------|---------------------------|
| Lend USDC in Protocol A          | `C_k`                     |
| Borrow token2 from Protocol A    | `r · C_k`                 |
| Sell token2 spot (receive USDC)  | `r · C_k`                 |
| Post as Bluefin perp collateral  | `d · r · C_k`             |
| Recycle to next loop iteration   | `(1−d) · r · C_k = C_{k+1}` |

### Infinite Sums (Geometric Series, Converges When q < 1)

```
L_A  = Σ C_k         = Σ q^k       =      1 / (1 − q)
B_A  = Σ r · C_k     = r · Σ q^k   =      r / (1 − q)
L_B  = B_A                           (market neutral: perp notional = spot short)
C_BF = d · r / (1 − q)              (total USDC posted to Bluefin as margin)
B_B  = 0                             (no borrowing on Bluefin)
```

Substituting `q = r(1−d)`:

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│   L_A  =      1 / (1 − r(1−d))                        │
│   B_A  =      r / (1 − r(1−d))                        │
│   L_B  =      r / (1 − r(1−d))                        │
│   B_B  =      0                                        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

The series converges for any `r ∈ (0, 1)` and `d ∈ (0, 1)`.

### Capital Conservation Check

Starting equity = 1 (initial deployment). After all loops:

```
equity = (L_A + C_BF) − B_A
       = [1/(1−q) + r·d/(1−q)] − r/(1−q)
       = [1 + r·d − r] / (1−q)
       = [1 − r(1−d)] / (1−q)
       = (1−q) / (1−q)
       = 1  ✓
```

---

## Concrete Example

**Inputs:** d = 0.20, r = 0.64 (USDC at 80% LTV with 20% safety buffer)

```
q  = 0.64 × 0.80 = 0.512
1/(1−q) = 1/0.488 ≈ 2.05
```

| Multiplier | Non-looped | Looped | Amplification |
|------------|-----------|--------|---------------|
| L_A        | 1.00      | 2.05   | 2.05×         |
| B_A        | 0.64      | 1.31   | 2.05×         |
| L_B        | 0.64      | 1.31   | 2.05×         |
| Bluefin collateral | 0.13 | 0.26 | 2.05×       |

The loop amplifies all positions uniformly by `1/(1−q) = 2.05×`.

---

## APR Formulas

### Gross APR (before fees)

```
gross_apr = L_A × lend_rate_USDC_A
          − B_A × borrow_rate_token2_A
          + L_B × lend_total_apr_perp_B
```

Where `lend_total_apr_perp_B` is the stored Bluefin funding rate for the long perp
(positive = we earn, negative = we pay — see sign convention below).

### Net APR (after fees)

```
net_apr = gross_apr
        − L_B × 2 × BLUEFIN_TAKER_FEE    (perp entry + exit, amortized over 1 year)
        − B_A × borrow_fee_2A            (upfront borrow fee at Protocol A)
```

### Closed-Form (substituting looped multipliers)

```
gross_apr = [lend_USDC + r × (lend_perp − borrow_token2)] / (1 − r(1−d))
```

The loop amplifies the base APR by `1/(1−r(1−d))` — the same amplifier pattern as `recursive_lending`.

---

## Sign Convention for Perp Funding Rate

Our system stores perp rates as: `stored_rate = −published_funding_rate`

```
Bluefin publishes −3%  →  stored as +3%  →  long perp earns 3%  ✓
Bluefin publishes +5%  →  stored as −5%  →  long perp pays 5%   ✓
```

For the long perp, use `lend_total_apr_3B` (positive stored rate = earnings for longs).

This is the **opposite** of `perp_lending` (short perp), which earns when the stored rate is negative (published rate is positive, longs pay shorts).

---

## Risk Profile

| Risk | Trigger | Affected Leg |
|------|---------|--------------|
| Protocol A liquidation | Token2 price **rises** (debt USD value exceeds collateral) | B_A |
| Bluefin long perp liquidation | Token2 price **drops** (margin call on long position) | L_B |

Both liquidation distances are controlled by the same parameter `d`. They trigger on **opposite** price directions, meaning the strategy is immune to a single directional move wiping out both legs simultaneously. However, leverage is present on both sides.

---

## Two Strategy Variants

### Variant 1: `perp_borrowing` (non-looped)

```
L_A = 1.0
B_A = r
L_B = r
B_B = 0
```

- Simpler; single iteration; all USDC from selling token2 goes to Bluefin collateral
- No amplification; lowest exposure; lowest APR

### Variant 2: `perp_borrowing_recursive` (looped, infinite geometric series)

```
L_A = 1 / (1 − r(1−d))
B_A = r / (1 − r(1−d))
L_B = r / (1 − r(1−d))
B_B = 0
```

- Recycles surplus USDC back into Protocol A each iteration
- Amplified exposure and APR by factor `1/(1−r(1−d))`
- Same risk structure per unit of deployment; converges cleanly

---

## Implementation Scope

### Files to Create

| File | Contents |
|------|----------|
| `analysis/strategy_calculators/perp_borrowing.py` | `PerpBorrowingCalculator` — non-looped |
| `analysis/strategy_calculators/perp_borrowing_recursive.py` | `PerpBorrowingRecursiveCalculator` — looped |
| `analysis/strategy_history/perp_borrowing.py` | `PerpBorrowingHistoryHandler` — shared 3-leg handler |

### Files to Modify

| File | Change |
|------|--------|
| `analysis/strategy_calculators/__init__.py` | Import + register both new calculators |
| `analysis/strategy_history/__init__.py` | Import + register new history handler |
| `analysis/rate_analyzer.py` | Add `_generate_perp_borrowing_strategies()` + dispatch |

### Files NOT Changed

| File | Reason |
|------|--------|
| `data/protocol_merger.py` | No new protocol — all data already collected |
| `data/schema.sql` | No new tables needed |
| `data/rate_tracker.py` | No new DB operations |
| `config/settings.py` | Uses existing `BLUEFIN_TO_LENDINGS` and `BLUEFIN_TAKER_FEE` |

---

## Strategy Generation Iteration (rate_analyzer)

```python
for perp_token in bluefin_tokens:                        # e.g., SUI-USDC-PERP (token3)
    lend_total_apr_3B = lend rate for perp_token on Bluefin
    price_3B          = price for perp_token on Bluefin
    perp_contract     = contract for perp_token

    for spot_contract in BLUEFIN_TO_LENDINGS[perp_contract]:  # e.g., SUI contracts (token2)
        token2 = find symbol from spot_contract

        for token1 in self.STABLECOINS:                  # USDC, USDY, etc.

            for protocol_a in self.protocols (excluding Bluefin):
                # Early exits
                if token1 not lendable in protocol_a: continue
                if token2 not borrowable in protocol_a: continue

                # Collect data
                lend_total_apr_1A       = stablecoin lending rate
                collateral_ratio_1A     = stablecoin collateral factor
                liquidation_threshold_1A = stablecoin LTV threshold
                borrow_total_apr_2A     = token2 borrow rate
                borrow_fee_2A           = token2 upfront fee
                available_borrow_2A     = token2 borrow liquidity
                borrow_weight_2A        = token2 borrow weight

                # Call calculator
                result = calculator.analyze_strategy(
                    token1, token2, token3=perp_token,
                    protocol_a, protocol_b='Bluefin',
                    lend_total_apr_1A, borrow_total_apr_2A, lend_total_apr_3B,
                    collateral_ratio_1A, liquidation_threshold_1A,
                    price_1A, price_2A, price_3B,
                    borrow_fee_2A, available_borrow_2A, borrow_weight_2A,
                    liquidation_distance
                )
```

---

## Key Template Files (for implementation reference)

| File | What to reuse |
|------|--------------|
| `analysis/strategy_calculators/perp_lending.py` | Overall structure, sign convention, perp fees |
| `analysis/strategy_calculators/noloop_cross_protocol.py` | `calculate_positions()` borrow ratio formula |
| `analysis/strategy_history/noloop_cross_protocol.py` | 3-leg history handler structure |
| `analysis/rate_analyzer.py` line 578 | `_generate_perp_lending_strategies()` iteration pattern |
