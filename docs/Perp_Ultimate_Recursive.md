# Perp Ultimate Recursive Strategy Reference

## Overview

The **Perp Ultimate Recursive** strategy is a capital-amplified yield strategy that chains a
short-perp lending loop (à la `perp_lending_recursive`) with a borrow-and-long-perp loop
(à la `perp_borrowing_recursive`) into a single self-reinforcing cycle.

**Starting capital:** USDC (or any stablecoin).
**Requirements:** Two distinct volatile tokens (token1 ≠ token2), each with:
- A lending/borrowing market at **Protocol A** (e.g. Suilend, Scallop, NAVI)
- A perpetual futures market at **Protocol B** (e.g. Bluefin)

**Slot assignments (per system naming convention):**

| Slot | DB column | Role |
|------|-----------|------|
| **L_A** | token1 / 1A | token1 lent to Protocol A |
| **B_A** | token2 / 2A | token2 borrowed from Protocol A |
| **L_B** | token3 / 2B | token2 long perp on Protocol B |
| **B_B** | token4 / 3B | token1 short perp on Protocol B |

---

## Parameters

| Symbol | Name | Meaning |
|--------|------|---------|
| d | `liquidation_distance` | Target liquidation distance for both perp legs (e.g. 0.20) |
| r | borrow ratio | USD value of token2 borrowed per USD of token1 lent at Protocol A |
| λ_A | `liquidation_threshold_1A` | LTV threshold at Protocol A before liquidation (e.g. 0.85) |
| α | loop multiplier | = r(1−d)/(1+d) — the fraction of capital recycled each loop |
| F | amplifier | = (1+d)/(1+d−r(1−d)) — the geometric series sum factor |

---

## Capital Split — Achieving Equal Liquidation Distances

The key design choice is how to split each loop's capital C between perp collateral and spot.

**Target:** both perp legs (B_B and L_B) should have liquidation distance = d.
This requires margin ratio = d for each leg, i.e. collateral = d × notional.

For B_B with notional S and collateral d·S:

```
S + d·S = C   →   S = C/(1+d),   collateral = d·C/(1+d)
```

---

## Capital Flow Per Loop Iteration

Starting with capital **C_k** USDC at iteration k:

```
Step 1  ──►  Buy C_k/(1+d) token1 spot
             Short C_k/(1+d) token1 perp on Protocol B   [← B_B]
             Collateral for B_B: d·C_k/(1+d) USDC
             (margin ratio = d  →  LD₃ = d)

Step 2  ──►  Lend C_k/(1+d) token1 to Protocol A         [← L_A]

Step 3  ──►  Borrow r·C_k/(1+d) token2 from Protocol A   [← B_A]
             (token1 is the collateral)

Step 4  ──►  Sell ALL r·C_k/(1+d) token2 for USDC
             │
             ├─ d·r·C_k/(1+d) USDC  →  collateral for long token2 perp  [← L_B]
             │                          notional of L_B = r·C_k/(1+d)   (= B_A, full hedge)
             │                          (margin ratio = d  →  LD₄ = d)
             │
             └─ (1−d)·r·C_k/(1+d) USDC  →  recycled back to Step 1

Step 5  ──►  Recycled capital = r(1−d)/(1+d) · C_k = α · C_k = C_{k+1}
```

The loop multiplier is **α = r(1−d)/(1+d)**.

For convergence: α < 1, i.e. r(1−d) < (1+d), always satisfied for r < 1.

---

## Derivation of Position Sizes — Geometric Series

At iteration k, capital is **C_k = α^k · C_0** where C_0 = 1 USDC.

```
Slot weight = (per-iteration fraction) × Σ_{k=0}^{∞} α^k = (per-iteration fraction) × F
```

where **F = 1/(1−α) = (1+d) / (1+d−r(1−d))**.

**L_A** — token1 lent to Protocol A:

```
L_A = Σ_{k=0}^{∞} [1/(1+d)] · α^k = F/(1+d)
```

**B_A** — token2 borrowed from Protocol A:

```
B_A = Σ_{k=0}^{∞} [r/(1+d)] · α^k = r·F/(1+d)
```

**B_B** — token1 short perp (notional = spot purchased each iteration):

```
B_B = Σ_{k=0}^{∞} [1/(1+d)] · α^k = F/(1+d) = L_A
```

**L_B** — token2 long perp (notional = full borrowed amount each iteration):

```
L_B = Σ_{k=0}^{∞} [r/(1+d)] · α^k = r·F/(1+d) = B_A
```

### Closed-form results:

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│              1                                           │
│  L_A = ─────────────────── = B_B                        │
│        1 + d − r(1−d)                                   │
│                                                          │
│              r                                           │
│  B_A = ─────────────────── = L_B                        │
│        1 + d − r(1−d)                                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Key identities:

- **B_B = L_A** — short perp notional equals spot lent → perfectly delta-neutral on token1
- **L_B = B_A** — long perp notional equals borrow → perfectly delta-neutral on token2
- **B_A / L_A = r** — borrow ratio preserved through the amplification
- **Both perp legs have margin ratio = d → LD₃ = LD₄ = d**

---

## Collateral Deployment

Per $1 initial USDC, USDC locked as perp collateral:

| Purpose | Amount |
|---------|--------|
| Collateral for B_B (token1 short) | d · L_A = d/(1+d−r(1−d)) |
| Collateral for L_B (token2 long)  | d · B_A = d·r/(1+d−r(1−d)) |
| **Total Protocol B collateral**   | **d(1+r) / (1+d−r(1−d))** |

### Balance sheet verification (net value = $1):

```
Net = B_B_collateral + token1_spot − token2_debt + L_B_collateral

    =  F/(1+d) · [d + 1 − r + d·r]

    =  F/(1+d) · [1+d − r(1−d)]

    =  F/(1+d) · (1+d)/F  =  1  ✓
```

---

## Leverage

Gross leverage (total positive asset value / net value, at entry):

```
Gross assets = B_B_collateral + L_A + L_B_collateral
             = F/(1+d) · [d + 1 + d·r]
             = F · (1 + d(1+r)) / (1+d)

Leverage = F · (1 + d(1+r)) / (1+d)
         = (1 + d(1+r)) / (1+d−r(1−d))
```

**Numerical example** (d = 0.20, r = 0.70):

```
α = 0.70 × 0.80 / 1.20  = 0.4667
F = 1.20 / (1.20 − 0.56) = 1.20 / 0.64 = 1.875

L_A = B_B = 1 / 0.64    = 1.5625
B_A = L_B = 0.70 / 0.64 = 1.0938

B_B collateral = 0.20 / 0.64 = 0.3125
L_B collateral = 0.14 / 0.64 = 0.2188

Gross leverage = 1.34 / 0.64 = 2.09×
```

---

## Net APR Formula

### Gross income (annualised, per $1 initial capital):

```
gross_apr =   L_A × lend_apr(token1)
            − B_B × funding_rate(token1_perp)    ← short earns when funding_rate < 0
            − B_A × borrow_apr(token2)
            + L_B × funding_rate(token2_perp)    ← long earns when funding_rate < 0
```

Funding sign convention (DESIGN_NOTES #17): rates stored negative in DB when shorts earn.

### Upfront fees (paid once, amortised over holding period):

```
upfront_fees =   2 × B_B × BLUEFIN_TAKER_FEE     ← entry + exit of token1 short perp
               + 2 × L_B × BLUEFIN_TAKER_FEE     ← entry + exit of token2 long perp
               + B_A × borrow_fee(token2)          ← borrow opening fee
               + basis_cost(token1_perp)           ← token1 spot/perp spread round-trip
               + basis_cost(token2_perp)           ← token2 spot/perp spread round-trip
```

### Net APR (amortised over N days):

```
net_apr(N) = gross_apr − upfront_fees × (365/N)
```

---

## Liquidation Risk Analysis

Four independent liquidation risks. With the symmetric margin structure all four reduce to
two distinct values driven by d alone.

---

### Risk 1 — Token1 DROPS  (Protocol A: collateral depreciates)

At Protocol A: collateral = L_A × P₁, debt = B_A × P₂.
Entry LTV = r (by construction).

With r = λ_A(1−d) (the safe borrow ratio, see below):

```
LD₁ = (λ_A − r) / λ_A  =  d
```

---

### Risk 2 — Token2 RISES  (Protocol A: debt appreciates)

```
LD₂ = (λ_A − r) / r  =  d / (1−d)
```

---

### Risk 3 — Token1 RISES  (Protocol B: B_B short perp)

Per iteration: collateral = d·C/(1+d), notional = C/(1+d).
Margin ratio = d. Collateral exhausted when notional loss = d × notional:

```
(1) × ΔP = d   →   ΔP = d

LD₃ = d
```

---

### Risk 4 — Token2 DROPS  (Protocol B: L_B long perp)

Per iteration: collateral = d·r·C/(1+d), notional = r·C/(1+d).
Margin ratio = d. Collateral exhausted when notional loss = d × notional:

```
(1) × ΔP = d   →   ΔP = d

LD₄ = d
```

---

## Summary of Liquidation Distances

| # | Direction | Protocol | Formula | Value (d=0.20) |
|---|-----------|----------|---------|----------------|
| LD₁ | Token1 **drops** | Protocol A (lending) | d | **20%** |
| LD₂ | Token2 **rises** | Protocol A (lending) | d/(1−d) | **25%** |
| LD₃ | Token1 **rises** | Protocol B (B_B short) | d | **20%** |
| LD₄ | Token2 **drops** | Protocol B (L_B long) | d | **20%** |

**Three of the four distances equal d exactly.** LD₂ = d/(1−d) is always larger — Protocol A
is more tolerant of token2 rising because the debt denominator is smaller than the collateral.

---

## Convergence and Parameter Bounds

**Convergence:** α = r(1−d)/(1+d) < 1. Since r < 1, this is always satisfied.

**Safe borrow ratio** (ensuring LD₁ = d):

```
r = λ_A × (1 − d)
```

**Code pattern:**

```python
r_safe  = liquidation_threshold_1A * (1 - d) / borrow_weight_2A   # ensures LD₁ = d
r       = min(r_safe, collateral_ratio_1A)
alpha   = r * (1 - d) / (1 + d)                                    # loop multiplier
factor  = (1 + d) / (1 + d - r * (1 - d))                         # amplifier F

L_A = factor / (1 + d)
B_A = r * factor / (1 + d)
B_B = L_A
L_B = B_A                                                          # delta-neutral on token2
```

---

## Comparison with Parent Strategies

```
perp_lending_recursive
  loop:  α = r(1−d)             ← recycles stablecoin; split is (d, 1-d)
  L_A = B_B = (1−d)/(1−r(1−d))
  B_A = r·L_A                   ← stablecoin borrow (not volatile)
  L_B = 0

perp_borrowing_recursive
  loop:  α = r(1−d)             ← split is (d, 1-d) on borrowed proceeds
  L_A = 1/(1−r(1−d))            ← stablecoin lent
  B_A = r·L_A
  L_B = B_A                     ← full delta-neutral
  B_B = 0

perp_ultimate_recursive (this strategy)
  loop:  α = r(1−d)/(1+d)       ← SMALLER — split is (d/(1+d), 1/(1+d)) on capital
  L_A = B_B = 1/(1+d−r(1−d))
  B_A = L_B = r/(1+d−r(1−d))   ← both delta-neutral, LD₃ = LD₄ = d
```

The ultimate strategy's α = r(1−d)/(1+d) is smaller than the parents' r(1−d). In exchange
it harvests four yield sources simultaneously and has a uniform liquidation distance d on
all three per-token risks.

---

## Delta Neutrality

**Token1:** Perfectly delta-neutral. B_B = L_A — short perp notional equals spot lent.

**Token2:** Perfectly delta-neutral. L_B = B_A — long perp notional equals borrow.

**Both perps share the same margin ratio d:**

| Leg | Notional | Collateral | Margin ratio | LD |
|-----|----------|-----------|-------------|-----|
| B_B | L_A      | d · L_A   | d | d |
| L_B | B_A      | d · B_A   | d | d |

---

## Risk Notes

1. **Correlation.** Token1 and token2 are modelled as independent. Both tend to fall
   together in risk-off events, so LD₁ and LD₄ could be triggered simultaneously.

2. **Shared Bluefin margin.** B_B and L_B share the Protocol B margin account. Correlated
   moves may partially offset P&L, **reducing** total liquidation risk vs the independent model.

3. **Funding rate risk.** If both markets are strongly bullish, B_B pays funding (short loses)
   and L_B pays funding (long pays), compressing yield from both perp legs simultaneously.

4. **Strategy name:** Proposed `perp_ultimate_recursive`. Per `config/settings.py` conventions,
   add to both `PERP_LENDING_STRATEGIES` and `PERP_BORROWING_STRATEGIES`, or create a new
   `PERP_ULTIMATE_STRATEGIES` tuple.
