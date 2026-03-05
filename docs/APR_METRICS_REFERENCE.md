# APR Metrics Reference Guide

---

## Page 1: Overview

This codebase tracks **9 distinct APR/rate metrics** across strategy analysis, position tracking, and portfolio management.

| Metric | Variable Names | One-Line Summary |
|--------|---------------|-----------------|
| **Gross APR** | `gross_apr`, `apr_gross` | Raw earnings minus borrowing costs — before any fees |
| **Net APR** | `net_apr`, `apr_net` | Gross APR minus all upfront fees (the "headline" rate) |
| **APR 5/30/90** | `apr5`, `apr30`, `apr90` | Net APR assuming you exit after N days (fees hurt shorter holds) |
| **Realized APR** | `realized_apr` | Actual annualized return from real PnL since position open |
| **Current APR** | `current_apr` | Net APR recalculated live with today's rates |
| **Basis-Adjusted APR** | `current_apr_incl_basis` | Current APR + unrealised spot/perp divergence (perp strategies only) |
| **Blended APR** | `blended_apr` | Weighted average of net_apr, apr5, apr30, apr90 |
| **Adjusted APR** | `adjusted_apr` | Blended APR × stablecoin multiplier (used for strategy ranking) |
| **Entry APR snapshots** | `entry_net_apr`, `entry_apr5`, etc. | Frozen snapshot of APR metrics at position creation |

**Naming anomaly:** `net_apr` and `apr_net` refer to the same concept but coexist due to different generations of strategy calculators. Old strategies emit `apr_net`; newer ones emit `net_apr`. The Slack notifier and position service handle both.

**No APY:** All rates are expressed as APR (not compounded APY). Perp funding rates are already provided annualized by the exchange.

---

## Section 1: Gross APR

**What it is:** Earnings from lending minus borrowing costs, with zero fee deductions. The raw spread of the strategy before execution costs.

**Variable names:** `gross_apr`, `apr_gross`

**Formulas (by strategy type):**

| Strategy | Formula |
|----------|---------|
| Stablecoin lending | `L_A × lend_total_apr_1A` |
| Recursive lending | `(L_A × lend_1A) + (L_B × lend_2B) - (B_A × borrow_2A) - (B_B × borrow_3B)` |
| NoLoop cross-protocol | `(L_A × lend_1A) + (L_B × lend_2B) - (B_A × borrow_2A)` |
| Perp lending | `L_A × lend_1A - B_B × funding_rate_3B` |
| Perp borrowing | `-B_A × borrow_2A + B_B × funding_rate_3B` |

Where:
- `L_X` = leverage / size of lend leg as fraction of deployment
- `B_X` = leverage / size of borrow leg as fraction of deployment
- `lend_total_apr_1A` = total lending APR at Protocol A (base + rewards)
- `borrow_total_apr_2A` = total borrowing APR at Protocol A
- `funding_rate_3B` = perp funding rate at Protocol B (Bluefin), annualized

**Key files:**
- Abstract definition: [analysis/strategy_calculators/base.py](analysis/strategy_calculators/base.py) (lines 126–153)
- Recursive: [analysis/strategy_calculators/recursive_lending.py](analysis/strategy_calculators/recursive_lending.py) (line 203)
- Perp lending: [analysis/strategy_calculators/perp_lending.py](analysis/strategy_calculators/perp_lending.py) (line 93)
- Perp borrowing: [analysis/strategy_calculators/perp_borrowing.py](analysis/strategy_calculators/perp_borrowing.py) (line 48)
- Stablecoin: [analysis/strategy_calculators/stablecoin_lending.py](analysis/strategy_calculators/stablecoin_lending.py) (lines 87–96)
- NoLoop: [analysis/strategy_calculators/noloop_cross_protocol.py](analysis/strategy_calculators/noloop_cross_protocol.py) (lines 151–158)
- Live recalc: [analysis/position_statistics_calculator.py](analysis/position_statistics_calculator.py) (line 275)

**Where displayed:** Not shown directly in UI; intermediate for calculating net_apr.

---

## Section 2: Net APR

**What it is:** Gross APR minus all upfront/one-time fees. This is the annualized return assuming you hold the position for exactly 1 year.

**Variable names:** `net_apr` (newer code), `apr_net` (older strategies) — same concept

**Formula:**
```
net_apr = gross_apr - total_fee_cost

total_fee_cost =
    b_a × borrow_fee_2A           # lending protocol borrow fee
  + b_b × borrow_fee_3B           # lending protocol borrow fee (second leg)
  + position_multiplier × 2.0 × BLUEFIN_TAKER_FEE   # perp entry+exit (perp strategies)
  + position_multiplier × basis_spread               # spot/perp spread friction (perp, if data available)
```

**Fee breakdown:**
- **Borrow fees:** One-time fee charged by lending protocol when opening a borrow position
- **Perp trading fees:** Bluefin taker fee = 0.035% × 2 (entry + exit)
- **Basis spread cost:** Round-trip bid/ask friction between spot and perp price

**Naming issue — `net_apr` vs `apr_net`:**

| Code | Variable | Reason |
|------|----------|--------|
| `stablecoin_lending.py` | `apr_net` | Older implementation |
| `noloop_cross_protocol.py` | `apr_net` | Older implementation |
| `recursive_lending.py` | `apr_net` (returned), `net_apr` (internal) | Mixed |
| `perp_lending.py` | `apr_net` | Newer, but kept old name |
| `perp_borrowing.py` | `apr_net` | Newer, but kept old name |
| `position_service.py` | `entry_net_apr` (stored) | Reads from `net_apr` field |
| `slack_notifier.py` lines 75–77, 351–353 | handles both | Backwards compatibility shim |

**Key files:**
- Calculation: [analysis/strategy_calculators/base.py](analysis/strategy_calculators/base.py) (line 288)
- Entry storage: [analysis/position_service.py](analysis/position_service.py) (line 215)
- Display: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) (lines 140, 417, 705)

**Where displayed:**
- Analysis tab: `Net APR` column
- All strategies table: `Net APR` column with help text: *"Annual return if held 1 year, after all fees including basis spread cost"*
- Position modals: `Net APR` field

**Database column:** `positions.entry_net_apr` (stores decimal, e.g. 0.1185 = 11.85%)

---

## Section 3: APR5 / APR30 / APR90

**What it is:** "If I exit this trade after only N days, what APR did I actually earn?" You pay all fees in full on day 1 regardless of when you exit. The shorter you hold, the smaller the gross earnings you captured — but the fee was the same. APR5/30/90 quantifies the drag of exiting early.

**Variable names:** `apr5`, `apr30`, `apr90`

**Formula (same for all N):**
```
APR(N) = (gross_apr × N/365 - total_fee_cost) × 365/N

Expanded:
  Step 1 — N-day earnings:   gross_apr × N/365
  Step 2 — Subtract fees:    - total_fee_cost   (paid in full on day 1, same cost regardless of N)
  Step 3 — Express as APR:   × 365/N
```

**Intuition:** Fees are paid upfront in full. If you exit after 5 days, you've earned only 5 days of spread but already paid the full cost of entry and exit. That fee eats a much larger share of a 5-day return than a 90-day return. These are NOT rolling historical averages — they show your actual return at current rates if you closed today after N days.

**Example (gross=11%, upfront fee=0.2% of deployment):**
| Exit after | Gross earned | Fee paid | Net earned | APR if you exited here |
|------------|-------------|---------|-----------|----------------------|
| 5 days  | 0.151% | 0.200% | −0.049% | −3.6% |
| 30 days | 0.904% | 0.200% | +0.704% | +8.6% |
| 90 days | 2.712% | 0.200% | +2.512% | +10.2% |
| 365 days| 11.00% | 0.200% | +10.80% | +10.8% |

**Key files:**
- Generic formula: [analysis/strategy_calculators/base.py](analysis/strategy_calculators/base.py) (lines 155–193)
- Recursive: [analysis/strategy_calculators/recursive_lending.py](analysis/strategy_calculators/recursive_lending.py) (lines 339–341)
- Perp lending: [analysis/strategy_calculators/perp_lending.py](analysis/strategy_calculators/perp_lending.py) (lines 268–273)
- Perp borrowing: [analysis/strategy_calculators/perp_borrowing.py](analysis/strategy_calculators/perp_borrowing.py) (lines 196–198)
- Stablecoin: [analysis/strategy_calculators/stablecoin_lending.py](analysis/strategy_calculators/stablecoin_lending.py) (lines 149–151)
- NoLoop: [analysis/strategy_calculators/noloop_cross_protocol.py](analysis/strategy_calculators/noloop_cross_protocol.py) (lines 266–268)

**Where displayed:**
- Analysis tab: `APR 5d`, `APR 30d` columns (90d shown for perp strategies)
- All strategies table: `APR 5d`, `APR 30d` columns
- Position modals: `APR 5d`, `APR 30d`
- Dashboard compact view: `APR5`, `APR30`, `APR90`

**Database columns:** `positions.entry_apr5`, `positions.entry_apr30`, `positions.entry_apr90`

**Portfolio allocation weight:** Configurable in [config/settings.py](config/settings.py) (lines 203–206):
```python
apr_weights = {
    'net_apr': 0.30,
    'apr5':    0.30,
    'apr30':   0.30,
    'apr90':   0.10,
}
```

---

## Section 4: Realized APR

**What it is:** Backward-looking metric. Actual annualized return from real PnL earned since position open.

**Variable names:** `realized_apr`

**Formula:**
```
realized_apr = (total_pnl / deployment_usd) × (365 / days_elapsed)
```

Where `total_pnl` = accumulated lending interest, funding payments, and other realized income.

**Key files:**
- Calculation: [analysis/position_statistics_calculator.py](analysis/position_statistics_calculator.py) (lines 250–255)
- Display: [dashboard/position_renderers.py](dashboard/position_renderers.py) (lines 586, 818–819)
- Storage: `position_statistics.realized_apr`

**Database column:** `position_statistics.realized_apr`

---

## Section 5: Current APR

**What it is:** Net APR recalculated at query time using live rates. Shows what the strategy would earn today if entered fresh, reflecting rate changes since position open.

**Variable names:** `current_apr`

**Formula:**
```
current_apr = gross_apr(live_rates) - fee_cost(live_rates) - perp_trading_fee_apr
```

This mirrors net_apr but uses live `lend_total_apr` and `borrow_total_apr` values from the rate tracker, not entry-time values.

**Key files:**
- Calculation: [analysis/position_statistics_calculator.py](analysis/position_statistics_calculator.py) (lines 257–293)
- Storage: `position_statistics.current_apr`

**Database column:** `position_statistics.current_apr`

---

## Section 6: Basis-Adjusted APR (Perp strategies only)

**What it is:** Current APR plus the unrealised gain/loss from spot/perp price divergence. Shows the "true" effective return for perp strategies when spot and perp prices have drifted apart since entry.

**Variable names:** `current_apr_incl_basis`, `basis_adjusted_current_apr`

**Formula:**
```
basis_pnl = (live_perp_price - entry_perp_price) × perp_tokens
          - (live_spot_price - entry_spot_price) × spot_tokens    [for perp_lending]

basis_adjusted_apr = current_apr + (basis_pnl / deployment_usd)
```

Note: `basis_pnl` is in dollars. Converting to APR here is NOT annualized — it's a direct ratio addition, representing "how much of my capital has the basis drift given me (or cost me) right now."

**Key files:**
- `basis_pnl` calc: [analysis/position_service.py](analysis/position_service.py) (lines 1155–1188)
- `basis_adjusted_apr` calc: [analysis/position_service.py](analysis/position_service.py) (lines 1191–1220)
- Display: [dashboard/position_renderers.py](dashboard/position_renderers.py) (lines 843–844)
  - Format: `"Current 8.50% | Basis-adj 9.12%"`

**Database column:** `position_statistics.basis_pnl` (stored in dollars, not APR)

---

## Section 7: Blended APR

**What it is:** Portfolio-level metric. Weighted average of net_apr, apr5, apr30, apr90 for a strategy. Used to rank strategies for capital allocation.

**Variable names:** `blended_apr`

**Formula:**
```
blended_apr = w_net × net_apr + w5 × apr5 + w30 × apr30 + w90 × apr90

Default weights (config/settings.py lines 203-206):
  w_net = 0.30
  w5    = 0.30
  w30   = 0.30
  w90   = 0.10
```

**Key files:**
- Calculation: [analysis/portfolio_allocator.py](analysis/portfolio_allocator.py) (lines 104–127)
- Display: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) (lines 2879, 2905, 2924)

---

## Section 8: Adjusted APR

**What it is:** Blended APR penalized by a stablecoin multiplier. The primary ranking metric for strategy selection.

**Variable names:** `adjusted_apr`

**Formula:**
```
adjusted_apr = blended_apr × stablecoin_multiplier

stablecoin_multiplier = min(multipliers for stablecoins involved in strategy)
                      = 1.0 if no stablecoins (no penalty)
```

The stablecoin multiplier deprioritizes strategies whose legs are in stablecoins (lower upside, lower volatility exposure).

**Key files:**
- Calculation: [analysis/portfolio_allocator.py](analysis/portfolio_allocator.py) (lines 86–95, 510)
- Display: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) (lines 2823–2924)
  - Column label: `Adjusted APR ⭐`

---

## Section 9: Entry APR Snapshots

**What it is:** Frozen copies of APR metrics captured at the moment a position is opened. Used to compare entry conditions vs. current conditions.

**Variable names:** `entry_net_apr`, `entry_apr5`, `entry_apr30`, `entry_apr90`, `entry_days_to_breakeven`

**Key files:**
- Capture: [analysis/position_service.py](analysis/position_service.py) (lines 215–219)
- Storage: [data/schema.sql](data/schema.sql) (lines 375–379)
- Display: [dashboard/position_renderers.py](dashboard/position_renderers.py) (lines 577, 813)

**Database columns (table: `positions`):**
- `entry_net_apr`
- `entry_apr5`
- `entry_apr30`
- `entry_apr90`
- `entry_days_to_breakeven`
- `entry_basis` (perp only)
- `entry_basis_spread` (perp only)

---

## Section 10: Portfolio-Weighted APR Metrics

**What it is:** Aggregate metrics across all active positions, weighted by USD allocation.

**Variable names:** `entry_weighted_net_apr`, `weighted_net_apr`, `weighted_apr5`, `weighted_apr30`, `weighted_adjusted_apr`

**Formula:**
```
weighted_apr = Σ(position.apr × position.allocation_usd) / Σ(position.allocation_usd)
```

**Key files:**
- Entry-weighted: [analysis/portfolio_service.py](analysis/portfolio_service.py) (lines 153–154)
- Live-weighted: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) (lines 3182–3187)
- Display labels: `"Weighted Avg Net APR"`, `"Weighted Avg APR5"`, `"Weighted Avg APR30"`, `"Weighted APR (Adjusted)"`

**Database column:** `portfolios.entry_weighted_net_apr`

---

## Section 11: Supporting Metrics & Sub-components

### Days to Breakeven

**Variable names:** `days_to_breakeven`, `entry_days_to_breakeven`

**Formula:**
```
days_to_breakeven = (total_fee_cost × 365) / gross_apr
```

Returns `inf` if gross_apr ≤ 0. This is how long you must hold the position before upfront fees are recovered.

**Key files:**
- Calc: [analysis/strategy_calculators/base.py](analysis/strategy_calculators/base.py) (lines 195–228)
- Display: position modals

### Basis Cost (Perp strategies)

**Variable names:** `basis_cost`, `basis_spread`, `basis_bid`, `basis_ask`, `basis_mid`

**Formula:**
```
basis_spread = basis_ask - basis_bid    (round-trip cost)
basis_cost   = position_multiplier × basis_spread   (as fraction of deployment)
```

This is a **one-time upfront cost** (not ongoing) included in `total_fee_cost` for APR calculations. Displayed in UI as basis points (`basis_spread × 10000`).

**Database table:** `spot_perp_basis` with columns `basis_bid`, `basis_ask`, `basis_mid`, `basis_spread`

**Key files:**
- Calc: [analysis/strategy_calculators/perp_lending.py](analysis/strategy_calculators/perp_lending.py) (lines 256–262)
- Display: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) line 420 — `'Basis (bps)'` column

### Historical Rolling Averages (8hr / 24hr)

**Variable names:** `net_avg8hr_apr`, `net_avg24hr_apr`

These are rolling time-weighted averages of the **net APR** over 8-hour and 24-hour windows, calculated by the rate tracker. Used in the analysis tab charts.

**Key files:**
- [dashboard/analysis_tab.py](dashboard/analysis_tab.py) (lines 203–205, 270–273)
- Chart Y-axis: `'Net APR (%)'`

### Component Rate Breakdown

**Variable names:** `lend_total_apr_1A`, `borrow_total_apr_2A`, `lend_reward_apr`, `borrow_base_apr`, etc.

The raw per-protocol rates that feed into gross_apr:
- `lend_base_apr`: Base lending rate (without rewards)
- `lend_reward_apr`: Reward token component of lending APR
- `lend_total_apr`: base + reward (used in gross_apr)
- `borrow_base_apr`: Base borrow rate
- `borrow_reward_apr`: Any borrow-side rewards
- `borrow_total_apr`: Effective borrow cost after rewards

Stored in `rates_snapshot` database table with 8hr and 24hr rolling averages.

---

## Section 12: Thresholds & Configuration

| Setting | Variable | Default | Purpose |
|---------|----------|---------|---------|
| Minimum APR filter | `MIN_NET_APR_THRESHOLD` | -1% | Hide strategies below this threshold |
| Alert threshold | `ALERT_NET_APR_THRESHOLD` | 5.0% | Slack alert when APR drops below this |
| Bluefin taker fee | `BLUEFIN_TAKER_FEE` | 0.00035 | Perp entry/exit fee (0.035%) |
| APR blending weights | `apr_weights` dict | see above | Weights for blended_apr calculation |

Config file: [config/settings.py](config/settings.py) (lines 58, 61, 109, 202–209)

---

## Section 13: Naming Conventions & Data Types

**Storage format:** All APR values stored as **decimals** (0.1185 = 11.85%)

**Display format:** Multiplied by 100 and formatted as `f"{apr * 100:.2f}%"`
- Exception: Historical analysis tab uses 3 decimal places `:.3f%`

**Basis points:** Basis spread displayed as `basis_spread × 10000` in bps

**Complete variable name inventory:**

| Variable | Location | Type |
|----------|----------|------|
| `gross_apr` / `apr_gross` | Strategy calculators, position_statistics | decimal |
| `net_apr` / `apr_net` | Strategy calculators (dual naming) | decimal |
| `apr5` / `apr30` / `apr90` | Strategy calculators, positions table | decimal |
| `realized_apr` | position_statistics table | decimal |
| `current_apr` | position_statistics table | decimal |
| `current_apr_incl_basis` | position_renderers (runtime) | decimal |
| `blended_apr` | portfolio_allocator | decimal |
| `adjusted_apr` | portfolio_allocator | decimal |
| `entry_net_apr` | positions table | decimal |
| `entry_apr5` / `entry_apr30` / `entry_apr90` | positions table | decimal |
| `entry_weighted_net_apr` | portfolios table | decimal |
| `weighted_net_apr` / `weighted_apr5` / `weighted_apr30` | dashboard (runtime) | decimal |
| `weighted_adjusted_apr` | dashboard (runtime) | decimal |
| `net_avg8hr_apr` / `net_avg24hr_apr` | strategy_history, analysis_tab | decimal |
| `basis_pnl` | position_statistics table | USD dollars |
| `basis_cost` / `basis_spread` / `basis_bid` / `basis_ask` / `basis_mid` | strategy calculators, spot_perp_basis table | decimal |
| `days_to_breakeven` / `entry_days_to_breakeven` | positions table, strategy calculators | float (days) |
| `lend_total_apr_1A` / `borrow_total_apr_2A` etc. | rate data, strategy inputs | decimal |

---

## Appendix: "Effective APR" — Does It Exist?

There is **no variable literally named `effective_apr`** in the codebase. The concept maps to two things:

1. **`current_apr`** — what you'd call the "effective current APR" (live rates, fees deducted)
2. **`current_apr_incl_basis`** / `basis_adjusted_current_apr` — the closest thing to a true "effective APR" for perp strategies, incorporating unrealised basis drift

The display string `"Current X% | Basis-adj Y%"` in position modals is the only place this concept is surfaced to the user.
