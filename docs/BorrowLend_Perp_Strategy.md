# Borrow/Lend × Perp Strategy Reference

Reference document for all perp-related strategy types. Update this document whenever perp strategy code changes.

**Strategy types covered:** `perp_lending` · `perp_borrowing` · `perp_borrowing_recursive`

---

## Quick Comparison

| Aspect | `perp_lending` | `perp_borrowing` | `perp_borrowing_recursive` |
|--------|---------------|-----------------|---------------------------|
| Legs | 2 | 3 | 3 (looped) |
| What you lend (L_A) | Spot token (SUI, BTC…) | Stablecoin (USDC) | Stablecoin (USDC) |
| Borrow from protocol? | No | Yes — volatile token | Yes — volatile token (looped) |
| Bluefin position | Short perp (B_B) | Long perp (L_B) | Long perp (L_B) |
| Earn when funding is | +ve (longs pay shorts) | −ve (shorts pay longs) | −ve (shorts pay longs) |
| Protocol A liq risk | None | Yes (token2 price rises) | Yes (token2 price rises) |
| Bluefin liq risk | Yes (token2 price rises) | Yes (token2 price drops) | Yes (token2 price drops) |
| Amplification | None | None | `1 / (1 − r(1−d))` |

These strategies have **complementary funding rate preferences** — one earns when the other pays.

---

## Tokens and Roles

### perp_lending (2 legs)

| Symbol | Role | Protocol |
|--------|------|----------|
| token1 | Spot token (SUI, BTC, ETH…) — bought and lent | Protocol A (any lending protocol) |
| token3 | Perp contract (SUI-USDC-PERP, etc.) — shorted | Protocol B = Bluefin (always) |

### perp_borrowing / perp_borrowing_recursive (3 legs)

| Symbol | Role | Protocol |
|--------|------|----------|
| token1 | Stablecoin (USDC, USDY…) — posted as collateral | Protocol A (any lending protocol) |
| token2 | Volatile token (SUI, BTC…) — borrowed, sold spot | Protocol A (any lending protocol) |
| token3 | Perp contract (SUI-USDC-PERP, etc.) — long position | Protocol B = Bluefin (always) |

---

## Position Multipliers

### perp_lending

```
L_A = 1 / (1 + d)
B_A = 0.0
L_B = 0.0
B_B = L_A        # Perp short notional = spot lending notional (market neutral)
```

Where `d` = liquidation distance. Collateral posted to Bluefin = `1 − L_A = d / (1 + d)`.

**Example (d = 0.20):**
- L_A = 1/1.2 = 0.8333 — 83.3% of capital buys and lends spot
- B_B = 0.8333 — equal notional shorted on Bluefin (market neutral)
- Bluefin leverage = L_A / (1 − L_A) = 5×
- Liquidation if spot rises 20%

### perp_borrowing (non-looped)

```
L_A = 1.0
B_A = r
L_B = r        # Long perp notional = short spot notional (market neutral)
B_B = 0.0
```

Where `r` is determined by Protocol A collateral parameters:

```
liq_max = d / (1 − d)
r_safe  = liquidation_threshold_1A / ((1 + liq_max) × borrow_weight_2A)
r       = min(r_safe, collateral_ratio_1A)
```

### perp_borrowing_recursive (looped)

```
factor = 1 / (1 − r(1−d))    # geometric series amplifier

L_A = factor
B_A = r × factor
L_B = r × factor              # market neutral
B_B = 0.0
```

Where `r` is the same as non-looped. Loop ratio `q = r(1−d)` must be < 1 (always true for r < 1, d > 0).

**Example (d = 0.20, r = 0.64):**
```
q  = 0.64 × 0.80 = 0.512
factor = 1 / (1 − 0.512) ≈ 2.05

L_A = 2.05  (vs 1.0 non-looped)
B_A = 1.31  (vs 0.64 non-looped)
L_B = 1.31  (vs 0.64 non-looped)
```

| Multiplier | Non-looped | Looped | Amplification |
|------------|-----------|--------|---------------|
| L_A        | 1.00      | 2.05   | 2.05×         |
| B_A        | 0.64      | 1.31   | 2.05×         |
| L_B        | 0.64      | 1.31   | 2.05×         |
| Bluefin collateral | 0.13 | 0.26 | 2.05×       |

### Why Looping Is Possible

When you borrow $r of token2 and sell it, you receive $r USDC. You do **not** need to post all of it as Bluefin perp collateral — only enough to maintain the desired liquidation distance on the long perp.

For a long perp with notional $N and liquidation distance `d`:
```
leverage          = 1 / d
collateral_needed = N / leverage = N × d
```

**Example (d = 20%, N = r = 0.64):**
- Collateral needed = 20% × 0.64 = 0.128
- Surplus USDC (recyclable) = 80% × 0.64 = 0.512

The surplus 0.512 is recycled back into Protocol A as fresh USDC collateral, starting the next loop iteration.

### Geometric Series Derivation

Define:
- `r` = borrow ratio at Protocol A (e.g., 0.64 for USDC at 80% LTV with 20% safety buffer)
- `d` = desired liquidation distance on Bluefin long perp (e.g., 0.20)
- `q = r × (1−d)` = loop ratio (fraction of capital that recycles each iteration)

**Per-iteration table** (step k = 0, 1, 2, …; capital entering Protocol A at step k: `C_k = q^k`):

| Action | Amount at step k |
|--------|-----------------|
| Lend USDC in Protocol A | `C_k` |
| Borrow token2 from Protocol A | `r · C_k` |
| Sell token2 spot (receive USDC) | `r · C_k` |
| Post as Bluefin perp collateral | `d · r · C_k` |
| Recycle to next loop iteration | `(1−d) · r · C_k = C_{k+1}` |

**Infinite sums** (geometric series, converges when q < 1):

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│   L_A  =  Σ C_k          = Σ q^k     =  1 / (1 − q)  │
│   B_A  =  Σ r · C_k      = r · Σ q^k =  r / (1 − q)  │
│   L_B  =  B_A                         (market neutral) │
│   C_BF =  d · r / (1 − q)            (Bluefin margin) │
│   B_B  =  0                                            │
│                                                        │
│   Substituting q = r(1−d):                             │
│                                                        │
│   L_A  =  1 / (1 − r(1−d))                            │
│   B_A  =  r / (1 − r(1−d))                            │
│   L_B  =  r / (1 − r(1−d))                            │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Capital conservation check** (starting equity = 1):

```
equity = (L_A + C_BF) − B_A
       = [1/(1−q) + r·d/(1−q)] − r/(1−q)
       = [1 + r·d − r] / (1−q)
       = [1 − r(1−d)] / (1−q)
       = (1−q) / (1−q)
       = 1  ✓
```

---

## APR Formulas

### perp_lending

```python
gross_apr = L_A × lend_rate_1A − B_B × funding_rate_3B
# Note: funding_rate_3B is already negated (see sign convention)
# Subtracting negative funding_cost = adding earnings when funding is positive

net_apr   = gross_apr − B_B × 2 × BLUEFIN_TAKER_FEE
```

### perp_borrowing / perp_borrowing_recursive

```python
gross_apr = L_A × lend_rate_1A                 # stablecoin lending
          + L_B × lend_total_apr_3B            # long perp funding (positive stored = longs earn)
          − B_A × borrow_rate_2A               # volatile token borrow cost

net_apr   = gross_apr
          − L_B × 2 × BLUEFIN_TAKER_FEE        # perp entry + exit
          − B_A × borrow_fee_2A                # upfront borrow fee at Protocol A
```

Looped closed-form:
```
gross_apr = [lend_USDC + r × (lend_perp − borrow_token2)] / (1 − r(1−d))
```

---

## Sign Convention for Perp Funding Rate (CRITICAL)

**Published rate** (Bluefin API): `+5%` = longs pay shorts, `−3%` = shorts pay longs.

**Stored rate** in system: `stored_rate = −published_rate`

```
Published +5%  →  stored −5%  →  perp_lending EARNS (short perp earns when longs pay)
Published −3%  →  stored +3%  →  perp_borrowing EARNS (long perp earns when shorts pay)
```

**Implementation** (`bluefin_reader.py`):
```python
perp_rate = -funding_rate_annual   # Negate published rate
# Both lend and borrow rows use the same perp_rate
Supply_apr = perp_rate
Borrow_apr = perp_rate
```

**In rate_analyzer generators:**
- `perp_lending` reads `self.borrow_rates` for `borrow_total_apr_3B`
- `perp_borrowing*` reads `self.lend_rates` for `lend_total_apr_3B`

Both columns store the same value — the negated published rate. Using different df names makes the sign intent explicit.

---

## Directional Pricing from spot_perp_basis

Real tradeable prices are used instead of mid. The direction depends on what each strategy does:

| Strategy | Spot price column | Perp price column | Logic |
|----------|-------------------|-------------------|-------|
| `perp_lending` | `spot_ask` | `perp_bid` | Buying spot token; selling/shorting perp |
| `perp_borrowing*` | `spot_bid` | `perp_ask` | Selling borrowed spot token; buying long perp |

### Lookup helpers (rate_analyzer.py)

```python
# Perp price — same for all spot contracts of a given perp market
# Called ONCE per perp_token at the outer loop level
get_perp_price(perp_proxy, col)          # col: 'perp_bid' or 'perp_ask'

# Spot price — specific to a (perp, spot_contract) pair
# Called per spot_contract inside the inner loop
get_perp_basis_price(perp_proxy, spot_contract, col)  # col: 'spot_bid' or 'spot_ask'
```

**Fallback behaviour:**
- `get_perp_price` returns `nan` if no basis data → strategy is **skipped entirely**
- `get_perp_basis_price` returns `nan` if no match → falls back to lending protocol price from `self.prices`

### spot_perp_basis table schema

One row per `(timestamp, perp_proxy, spot_contract)`:

| Column | Description |
|--------|-------------|
| `perp_proxy` | Perp market key, e.g. `'0xSUI-USDC-PERP_bluefin'` |
| `spot_contract` | On-chain spot token contract address |
| `spot_bid` | USDC received when selling spot token (AMM bid) |
| `spot_ask` | USDC paid when buying spot token (AMM ask) |
| `perp_bid` | Best bid on Bluefin perp orderbook |
| `perp_ask` | Best ask on Bluefin perp orderbook |
| `basis_bid` | `(perp_bid − spot_ask) / perp_bid` — exit economics |
| `basis_ask` | `(perp_ask − spot_bid) / perp_ask` — entry economics |
| `basis_mid` | `(basis_bid + basis_ask) / 2` |

Special INDEX rows: `spot_contract = '0x{ticker}-USDC-INDEX_bluefin'` use `oraclePriceE9` (Pyth). `spot_bid == spot_ask == index_price`, showing pure perp-vs-oracle basis with zero AMM spread.

---

## Data Flow

### perp_margin_rates (funding rates)

```
main_perp_refresh.py (hourly)
    │
    ▼
perp_margin_rates table
    │
    │  refresh_pipeline.py STEP 1: pre-fetch check
    │  if not present for current hour → fetch from Bluefin API
    ▼
protocol_merger.py
    → BluefinReader.get_all_data_for_timestamp(timestamp)
    → Queries perp_margin_rates at hour(timestamp)
    → Returns DataFrames: lend_df, borrow_df (price_usd = 10.10101 placeholder)
    │
    ▼
rates_snapshot table
    protocol='Bluefin', token='SUI-USDC-PERP'
    lend_total_apr  = −funding_rate_annual   (negated)
    borrow_total_apr = −funding_rate_annual  (negated)
    price_usd = 10.10101                    (placeholder — not used by perp generators)
```

### spot_perp_basis (directional prices)

```
refresh_pipeline.py STEP 2: BluefinPricingReader
    │
    ├─ fetch_perp_ticker(BTC-PERP)   → perp_bid, perp_ask, index_price
    └─ _fetch_amm_quote(USDC→spot)   → spot_ask
       _fetch_amm_quote(spot→USDC)   → spot_bid
    │
    ▼
spot_perp_basis table
    One row per (perp_proxy, spot_contract) per snapshot
    │
    │  rate_tracker.load_spot_perp_basis(timestamp_seconds)
    │  (most recent snapshot at or before requested timestamp)
    ▼
RateAnalyzer.__init__(perp_basis=perp_basis_df)
    │
    ├─ _generate_perp_lending_strategies()
    │    price_3B = get_perp_price(key, 'perp_bid')                  ← once per perp
    │    price_1A = get_perp_basis_price(key, spot, 'spot_ask')      ← per spot contract
    │
    └─ _generate_perp_borrowing_strategies()
         price_3B = get_perp_price(key, 'perp_ask')                  ← once per perp
         price_2A = get_perp_basis_price(key, spot, 'spot_bid')      ← per spot contract
```

---

## Strategy Generator Iteration

### perp_lending

```
for perp_token in bluefin_tokens:
    borrow_total_apr_3B = borrow_rates[perp_token]['Bluefin']   # negated funding rate
    price_3B = get_perp_price(perp_key, 'perp_bid')             # once per perp — SKIP if nan

    for spot_contract in BLUEFIN_TO_LENDINGS[perp_key]:
        spot_token = resolve symbol from spot_contract
        for protocol_a (excluding Bluefin):
            lend_total_apr_1A = lend_rates[spot_token][protocol_a]
            price_1A = get_perp_basis_price(perp_key, spot_contract, 'spot_ask')
                       fallback: prices[spot_token][protocol_a]
            → PerpLendingCalculator.analyze_strategy(...)
```

### perp_borrowing / perp_borrowing_recursive

```
for perp_token in bluefin_tokens:
    lend_total_apr_3B = lend_rates[perp_token]['Bluefin']        # negated funding rate
    price_3B = get_perp_price(perp_key, 'perp_ask')              # once per perp — SKIP if nan

    for spot_contract in BLUEFIN_TO_LENDINGS[perp_key]:          # token2
        token2 = resolve symbol from spot_contract
        for token1 in STABLECOINS:
            for protocol_a (excluding Bluefin):
                lend_total_apr_1A   = stablecoin lending rate
                borrow_total_apr_2A = token2 borrow rate
                collateral_ratio_1A, liquidation_threshold_1A
                price_2A = get_perp_basis_price(perp_key, spot_contract, 'spot_bid')
                           fallback: prices[token2][protocol_a]
                → calculator.analyze_strategy(...)   # same method, different calculator class
```

Both variants share `_generate_perp_borrowing_strategies(calculator)` — the calculator class determines positions (non-looped vs looped).

---

## Strategy Calculator Classes

| Class | File | Strategy type | Positions |
|-------|------|--------------|-----------|
| `PerpLendingCalculator` | `perp_lending.py` | `perp_lending` | L_A=1/(1+d), B_B=L_A |
| `PerpBorrowingCalculator` | `perp_borrowing.py` | `perp_borrowing` | L_A=1, B_A=r, L_B=r |
| `PerpBorrowingRecursiveCalculator` | `perp_borrowing_recursive.py` | `perp_borrowing_recursive` | Inherits PerpBorrowingCalculator, overrides `calculate_positions()` |

All registered in `analysis/strategy_calculators/__init__.py` at module load time.

`PerpBorrowingRecursiveCalculator` inherits all APR and `analyze_strategy()` methods from `PerpBorrowingCalculator`. It only overrides:
- `get_strategy_type()` → `'perp_borrowing_recursive'`
- `calculate_positions()` → applies geometric series amplifier
- `analyze_strategy()` → calls `super()`, adds `loop_ratio` and `loop_amplifier` to result

---

## History Handlers

| Handler | File | Handles |
|---------|------|---------|
| `PerpBorrowingHistoryHandler` | `analysis/strategy_history/perp_borrowing.py` | `perp_borrowing` AND `perp_borrowing_recursive` (same 3-leg structure) |
| `PerpLendingHistoryHandler` | *(not yet created)* | `perp_lending` — **TODO** |

Registration in `analysis/strategy_history/__init__.py`:
```python
register_handler(PerpBorrowingHistoryHandler)                     # 'perp_borrowing'
_HANDLERS['perp_borrowing_recursive'] = _HANDLERS['perp_borrowing']  # reuse same handler
```

Plan for `PerpLendingHistoryHandler`: `/Users/donalmoore/.claude/plans/perp-lending-history-handler.md`

---

## Dashboard Integration

### Sidebar toggles

```python
show_perp_lending  = st.toggle("Show Perp Lending", ...)
show_perp_borrowing = st.toggle("Show Perp Borrowing", ...)
# show_perp_borrowing enables BOTH perp_borrowing AND perp_borrowing_recursive
```

### enabled_strategy_types filter

```python
if show_perp_lending:
    enabled_strategy_types.append('perp_lending')
if show_perp_borrowing:
    enabled_strategy_types.append('perp_borrowing')
    enabled_strategy_types.append('perp_borrowing_recursive')
```

### strategy_type_map (display labels)

```python
'perp_lending':              'Perp Lending',
'perp_borrowing':            'Perp Borrowing',
'perp_borrowing_recursive':  'Perp Borrowing (Recursive)',
```

---

## Liquidation Analysis

### perp_lending: short perp

Short liquidated when price rises by `1/leverage`:

```
leverage     = L_A / (1 − L_A) = 1/d
liq_distance = d   (the configured liquidation distance)
liq_price    = entry_price × (1 + d)
```

Spot side has no liquidation risk (not borrowing against it).

### perp_borrowing*: dual liquidation risk

Both legs have liq risk but triggered by **opposite** price moves:

| Leg | Liquidated when | Why |
|-----|----------------|-----|
| Protocol A borrow (B_A) | token2 price **rises** | Debt USD value exceeds collateral |
| Bluefin long perp (L_B) | token2 price **drops** | Margin call on long position |

A single large directional move cannot wipe out both legs simultaneously. However, leverage is present on both sides.

---

## Critical Files

| File | Role |
|------|------|
| `config/settings.py` | `BLUEFIN_TO_LENDINGS`, `BLUEFIN_TAKER_FEE`, `ENABLED_PROTOCOLS` |
| `data/bluefin/bluefin_reader.py` | `get_all_data_for_timestamp()` — queries `perp_margin_rates`, returns funding rates. `price_usd=10.10101` placeholder (unused by perp generators) |
| `data/bluefin/bluefin_pricing_reader.py` | `get_spot_perp_basis()` — fetches AMM spot prices + perp orderbook, computes basis rows |
| `data/rate_tracker.py` | `save_spot_perp_basis()`, `load_spot_perp_basis(timestamp_seconds)` |
| `data/refresh_pipeline.py` | STEP 1: perp rate check; STEP 2: basis fetch + `load_spot_perp_basis`; passes `perp_basis` to `RateAnalyzer` |
| `analysis/rate_analyzer.py` | `get_perp_price()`, `get_perp_basis_price()`, `_generate_perp_lending_strategies()`, `_generate_perp_borrowing_strategies()` |
| `analysis/strategy_calculators/perp_lending.py` | `PerpLendingCalculator` |
| `analysis/strategy_calculators/perp_borrowing.py` | `PerpBorrowingCalculator` |
| `analysis/strategy_calculators/perp_borrowing_recursive.py` | `PerpBorrowingRecursiveCalculator` |
| `analysis/strategy_history/perp_borrowing.py` | `PerpBorrowingHistoryHandler` (shared for both borrowing variants) |
| `dashboard/dashboard_renderer.py` | `show_perp_borrowing` toggle, `strategy_type_map`, `enabled_strategy_types` filter |

---

## Configuration

```python
# config/settings.py

ENABLED_PROTOCOLS = [
    "Navi", "AlphaFi", "Suilend", "ScallopLend",
    "ScallopBorrow", "Pebble", "Bluefin"
]

BLUEFIN_PERP_MARKETS = ["BTC", "ETH", "SOL", "SUI", "WAL", "DEEP"]

BLUEFIN_MAKER_FEE = 0.0001    # 0.01%  (1 bps)
BLUEFIN_TAKER_FEE = 0.00035   # 0.035% (3.5 bps)

# Maps perp proxy key → compatible spot lending token contracts
BLUEFIN_TO_LENDINGS = {
    '0xSUI-USDC-PERP_bluefin': [
        '0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI',
        '0x2::sui::SUI',
        '0x549e...::cert::CERT',
        ...
    ],
    '0xBTC-USDC-PERP_bluefin': ['0xaafb...::btc::BTC', ...],
    # ... see config/settings.py for full mapping
}

BLUEFIN_AGGREGATOR_BASE_URL = "https://aggregator.api.sui-prod.bluefin.io"
BLUEFIN_AMM_USDC_AMOUNT_RAW = 100_000_000   # 100 USDC (6 decimals)
```

---

## Known Simplifications / TODOs

| Item | Status |
|------|--------|
| `perp_lending` history handler | **TODO** — plan at `/Users/donalmoore/.claude/plans/perp-lending-history-handler.md` |
| `price_usd` in `rates_snapshot` for perp tokens | `10.10101` placeholder — real prices come from `spot_perp_basis` via `get_perp_price()` |
| Backfill of `rates_snapshot` with perp data | Stub exists; not yet implemented |
| Maker/taker fee optimisation | Uses worst-case taker fee for both entry and exit |
| Funding rate forecasting | Uses current snapshot rate, no averaging or forecast |
| Rebalance cost modelling | Not included in APR calculations |

---

## Verification Queries

```sql
-- Check perp funding rates in rates_snapshot
-- If funding_rate_annual = +0.0876 then lend_total_apr should = -0.0876
SELECT timestamp, protocol, token, lend_total_apr, borrow_total_apr
FROM rates_snapshot
WHERE protocol = 'Bluefin'
ORDER BY timestamp DESC LIMIT 10;

-- Raw rates from perp_margin_rates
SELECT timestamp, token_contract, funding_rate_annual
FROM perp_margin_rates
WHERE protocol = 'Bluefin'
ORDER BY timestamp DESC LIMIT 10;

-- Inspect directional prices in spot_perp_basis
SELECT perp_ticker, spot_contract,
       spot_bid, spot_ask, perp_bid, perp_ask,
       basis_bid * 100 AS basis_bid_pct,
       basis_ask * 100 AS basis_ask_pct
FROM spot_perp_basis
ORDER BY timestamp DESC, perp_ticker LIMIT 30;

-- Index reference rows (oracle basis, zero AMM spread)
SELECT perp_ticker, spot_bid AS index_price,
       basis_bid * 100, basis_ask * 100
FROM spot_perp_basis
WHERE spot_contract LIKE '0x%-USDC-INDEX_bluefin'
ORDER BY timestamp DESC;

-- Verify timestamp alignment between tables
SELECT r.timestamp, r.protocol, r.token,
       b.perp_ticker, b.spot_bid, b.spot_ask, b.perp_bid, b.perp_ask
FROM rates_snapshot r
JOIN spot_perp_basis b
  ON r.timestamp = b.timestamp
 AND r.token_contract = b.perp_proxy
WHERE r.protocol = 'Bluefin'
ORDER BY r.timestamp DESC LIMIT 12;
```
