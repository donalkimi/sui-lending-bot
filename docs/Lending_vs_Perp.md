# Perp Lending Strategy

Reference guide for anything related to the perp_lending strategy.

## Overview

Market-neutral strategy that earns yield from both lending markets and perpetual funding rates.

## Architecture (Refactored 2026-02-19)

### Bluefin as a Protocol

Bluefin is treated as a **first-class protocol** (like Navi, AlphaFi, Suilend) in the system. It flows through the same `fetch_protocol_data()` → `merge_protocol_data()` → `save_snapshot()` pipeline as all other protocols.

**Key difference**: Unlike other protocols that fetch from APIs, Bluefin reads from the `perp_margin_rates` database table, which is populated hourly by `main_perp_refresh.py`.

### Data Flow

```
main_perp_refresh.py (hourly, independent)              refresh_pipeline.py (hourly)
    │                                                           │
    ▼                                                    STEP 1: perp check
┌──────────────────────┐                                       │
│  perp_margin_rates   │◄──────────────────────────────────────┘
│  (database table)    │  Raw funding rates from Bluefin API
└──────────┬───────────┘  protocol='Bluefin', funding_rate_annual=0.0876
           │
           │  refresh_pipeline.py Step 2: BluefinPricingReader
           ▼
┌──────────────────────┐
│  BluefinPricingReader│  get_spot_perp_basis(timestamp)
│                      │    → fetch_perp_ticker(BTC-PERP) → bid/ask/index
│                      │    → _fetch_amm_quote(USDC→spot) → spot_ask
│                      │    → _fetch_amm_quote(spot→USDC) → spot_bid
│                      │    → compute basis_bid, basis_ask, basis_mid
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  spot_perp_basis     │  One row per (perp, spot_contract) per snapshot
│  (database table)    │  + one INDEX row per perp (oracle reference price)
└──────────────────────┘

           refresh_pipeline.py Step 3: merge_protocol_data(timestamp)
           │
           ▼
┌──────────────────────┐
│  protocol_merger.py  │  fetch_protocol_data("Bluefin", timestamp)
│                      │    → BluefinReader(timestamp).get_all_data()
│                      │    → Queries perp_margin_rates at hour(timestamp)
│                      │    → Returns DataFrames with -funding_rate_annual
└──────────┬───────────┘
           │
           │  Same flow as Navi, AlphaFi, Suilend, etc.
           ▼
┌──────────────────────┐
│  rate_tracker.py     │  save_snapshot() inserts into rates_snapshot
│                      │  protocol='Bluefin', lend_total_apr=-0.0876
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  rates_snapshot      │  Bluefin rows alongside Navi, AlphaFi, etc.
│  (database table)    │  protocol='Bluefin', token='BTC-USDC-PERP'
└──────────────────────┘
```

### Critical Files

| File | Role |
|------|------|
| `config/settings.py` | `ENABLED_PROTOCOLS`, `BLUEFIN_PERP_MARKETS`, `BLUEFIN_TO_LENDINGS`, fees, aggregator config |
| `data/bluefin/bluefin_reader.py` | `BluefinReader` class - queries perp_margin_rates, returns protocol-format DataFrames |
| `data/bluefin/bluefin_pricing_reader.py` | `BluefinPricingReader` - fetches perp orderbook + AMM spot quotes, computes basis |
| `data/protocol_merger.py` | `fetch_protocol_data("Bluefin", timestamp)` elif block |
| `data/refresh_pipeline.py` | Pre-fetch check for perp rates; STEP 2: basis fetch integrated inline |
| `main_perp_refresh.py` | Standalone job to bulk-backfill perp_margin_rates (100 historical rates) |
| `main_spot_perp_pricing.py` | Standalone script for basis-only backfill runs |

### Sign Convention (CRITICAL)

**Published funding rate from Bluefin:**
- Positive (+5%): Longs pay shorts (bullish market)
- Negative (-3%): Shorts pay longs (bearish market)

**Our system convention:**
- Positive rate = you PAY (cost)
- Negative rate = you EARN (gain)

**Mapping:**

| Funding Rate | Long Perp (= Lending) | Short Perp (= Borrowing) |
|---|---|---|
| +5% | Pay 5% → lend_rate = **-5%** | Earn 5% → borrow_rate = **-5%** |
| -3% | Earn 3% → lend_rate = **+3%** | Pay 3% → borrow_rate = **+3%** |

**Implementation:**
```python
# In BluefinReader.get_all_data():
perp_rate = -funding_rate_annual  # NEGATIVE of published rate

# BOTH lend and borrow use the same negated rate
Supply_apr = perp_rate
Borrow_apr = perp_rate
```

**Why both are the same**: The perp rate represents the same economic reality from different perspectives. The sign inversion maps Bluefin's convention to our convention.

### Why Store as Negative?

The sign convention ensures consistency across all protocols:

**Universal Rule:**
- Positive rate when lending/longing = you EARN
- Negative rate when lending/longing = you PAY
- Positive rate when borrowing/shorting = you PAY
- Negative rate when borrowing/shorting = you EARN

**This enables uniform calculations:**
```python
# Spot lending
spot_earnings = l_a * lend_rate  # Positive lend_rate = positive earnings

# Perp shorting
funding_costs = b_b * borrow_rate  # Negative borrow_rate = negative cost (earnings)
gross_apr = spot_earnings - funding_costs  # Subtract cost (negative cost = add earnings)
```

**Example:** When Bluefin publishes +5% funding rate (longs pay shorts):
- We store as borrow_rate = -5% (negative = we earn when shorting)
- funding_costs = 0.8333 × (-0.05) = -0.04165
- gross_apr = spot_earnings - (-0.04165) = spot_earnings + 0.04165
- Subtracting negative cost adds 4.165% to gross APR ✓

### Configuration

```python
# config/settings.py

ENABLED_PROTOCOLS = [
    "Navi", "AlphaFi", "Suilend", "ScallopLend",
    "ScallopBorrow", "Pebble", "Bluefin"
]

BLUEFIN_PERP_MARKETS = ["BTC", "ETH", "SOL", "SUI", "WAL", "DEEP"]

BLUEFIN_MAKER_FEE = 0.0001    # 0.01% = 1 bps
BLUEFIN_TAKER_FEE = 0.00035   # 0.035% = 3.5 bps

# Maps perp proxy contracts → compatible spot lending tokens
BLUEFIN_TO_LENDINGS = {
    '0xBTC-USDC-PERP_bluefin': ['0xaafb...::btc::BTC', ...],
    '0xETH-USDC-PERP_bluefin': ['0xaf8c...::coin::COIN', ...],
    # ... see config/settings.py for full mapping
}
```

### Database Tables

**perp_margin_rates** (populated by main_perp_refresh.py / refresh_pipeline STEP 1):
- `timestamp`: Hour-aligned datetime string
- `protocol`: 'Bluefin'
- `token_contract`: e.g. '0xBTC-USDC-PERP_bluefin'
- `base_token`: e.g. 'BTC'
- `funding_rate_annual`: Published rate (positive = longs pay shorts)

**spot_perp_basis** (populated by refresh_pipeline STEP 2 via BluefinPricingReader):
- `timestamp`: Same timestamp as rates_snapshot for the same run
- `perp_proxy`: e.g. '0xBTC-USDC-PERP_bluefin'
- `perp_ticker`: e.g. 'BTC'
- `spot_contract`: On-chain token contract (or synthetic INDEX address)
- `spot_bid`: USDC received when selling spot token (AMM bid)
- `spot_ask`: USDC paid when buying spot token (AMM ask)
- `perp_bid`: Best bid price on perp orderbook (USDC)
- `perp_ask`: Best ask price on perp orderbook (USDC)
- `basis_bid`: `(perp_bid - spot_ask) / perp_bid` — exit economics
- `basis_ask`: `(perp_ask - spot_bid) / perp_ask` — entry economics
- `basis_mid`: `(basis_bid + basis_ask) / 2`
- `actual_fetch_time`: Wall-clock time of API calls (metadata only)

Special rows with `spot_contract = '0x{ticker}-USDC-INDEX_bluefin'` use `oraclePriceE9` (= Bluefin Index Price from Pyth) as a zero-spread reference: `spot_bid == spot_ask == index_price`.

**rates_snapshot** (destination - populated by refresh_pipeline.py):
- `protocol`: 'Bluefin'
- `token`: e.g. 'BTC-USDC-PERP'
- `lend_total_apr`: **-funding_rate_annual** (negated)
- `borrow_total_apr`: **-funding_rate_annual** (negated)
- `price_usd`: 10.10101 (dummy placeholder)

### Perp Rate Availability & Retry

The refresh pipeline handles missing perp rates:

1. **Before snapshot**: Check if `perp_margin_rates` has data for current hour
2. **If missing**: Fetch from Bluefin API (limit=100), save to perp_margin_rates
3. **Snapshot**: `merge_protocol_data()` includes Bluefin via BluefinReader
4. **Backfill**: `backfill_rates_snapshot_with_perp()` stub exists (TODO: implement)

---

## Spot/Perp Basis Pricing (added 2026-02-23)

### Overview

Each hourly refresh fetches live tradeable prices for every (perp, spot_token) pair in `BLUEFIN_TO_LENDINGS`. This gives real entry/exit economics beyond just the funding rate.

### Basis Definition

Basis follows the standard futures convention: `(future - spot) / future`

Positive basis = perp trades above spot (contango) = positive funding rate (longs pay).

| Name | Formula | Scenario |
|------|---------|----------|
| `basis_ask` | `(perp_ask - spot_bid) / perp_ask` | **Entry**: buy perp at ask, short spot at bid |
| `basis_bid` | `(perp_bid - spot_ask) / perp_bid` | **Exit**: sell perp at bid, cover short spot at ask |
| `basis_mid` | `(basis_bid + basis_ask) / 2` | Mid-market estimate |

### Index Reference Rows

Each perp also gets one synthetic row per refresh with `spot_contract = '0x{ticker}-USDC-INDEX_bluefin'`. This uses `oraclePriceE9` from the Bluefin ticker API, which equals the Pyth-sourced Index Price. Since `spot_bid == spot_ask == index_price`, these rows show the pure perp-vs-oracle basis with zero AMM spread.

### Data Sources

| Field | Source |
|-------|--------|
| `perp_bid`, `perp_ask` | `GET https://api.sui-prod.bluefin.io/v1/exchange/ticker?symbol=BTC-PERP` → `bestBidPriceE9 / 1e9` |
| `spot_ask` | `GET aggregator.api.sui-prod.bluefin.io/v3/quote?from=USDC&to=spot_contract` → `effectivePrice` |
| `spot_bid` | Same endpoint reversed (`from=spot_contract&to=USDC`), using `effectivePriceReserved` |
| `index_price` | Same ticker API → `oraclePriceE9 / 1e9` (Pyth-sourced) |

The two-step AMM approach (`returnAmountWithDecimal` from Step 1 feeds Step 2 as the X amount) avoids needing a separate token decimals lookup.

### Pipeline Integration

Basis fetch runs as **STEP 2** in `refresh_pipeline()`, after the perp check and before lending rate fetch. It only runs when `save_snapshots=True` and is non-fatal (failures log a warning, pipeline continues).

All three tables (`perp_margin_rates`, `spot_perp_basis`, `rates_snapshot`) share the same `current_seconds` timestamp for every run.

### Configuration

```python
# config/settings.py
BLUEFIN_AGGREGATOR_BASE_URL = "https://aggregator.api.sui-prod.bluefin.io"
BLUEFIN_AMM_USDC_AMOUNT_RAW = 100_000_000   # 100 USDC (6 decimals)
BLUEFIN_AGGREGATOR_SOURCES = ["cetus", "turbos", "aftermath", ...]  # all DEXes
```

---

## Mechanics

### Strategy Components

**Position A: Spot Lending (Long)**
- Buy spot token (BTC, ETH, SOL, etc.)
- Lend to protocol (Suilend, Navi, Scallop, etc.)
- Earn: Lending APR

**Position B: Perpetual Short**
- Short perp on Bluefin (BTC-PERP, ETH-PERP, etc.)
- Post USDC collateral
- Earn: Funding rate (when positive = shorts receive)

**Net exposure:**
- Market neutral (long spot cancels short perp)
- Basis risk ignored (assume spot price = perp price)
- Single protocol risk (only lending protocol)

### Capital Allocation

For $1 deployed:
- $L goes to buying spot and lending
- $S goes to posting as perp collateral
- $L + $S = $1 (total deployment)

**For market neutral: Short size must equal spot size**
- Perp notional = $L (match spot position)
- Leverage = Perp notional / Collateral = $L / $S

### Liquidation Distance

**Key formula:** Nx leverage => liquidation at (1 + 1/N)x price change

**For shorts:**
- Liquidation when collateral = loss from price increase
- Loss = Position x Price_change%
- $S = $L x (1/N) where N = leverage
- Price increase to liquidation = 1/N = S/L

**Examples:**

| Split | L | S | Leverage | Liq Distance | Liq Price |
|-------|---|---|----------|--------------|-----------|
| 83.33/16.67 | $0.83 | $0.17 | 5x | 20% | 1.20x entry |
| 50/50 | $0.50 | $0.50 | 1x | 100% | 2.0x entry |
| 67/33 | $0.67 | $0.33 | 2x | 50% | 1.5x entry |
| 75/25 | $0.75 | $0.25 | 3x | 33% | 1.33x entry |
| 80/20 | $0.80 | $0.20 | 4x | 25% | 1.25x entry |

**Formula derivation:**

Given desired liquidation distance d:
- Leverage N = 1/d
- S/L = d
- L + S = 1
- L(1 + d) = 1
- **L = 1/(1 + d)**
- **S = d/(1 + d)**

**Example: 20% liquidation distance**
- L = 1/(1 + 0.2) = 1/1.2 = 0.8333 = 83.33%
- S = 0.2/(1 + 0.2) = 0.2/1.2 = 0.1667 = 16.67%
- Leverage = 0.8333/0.1667 = 5x
- Liquidation at 20% price increase

### Mapping to Existing Framework

The system uses position multipliers (L_A, B_A, L_B, B_B) to represent all strategies.

**For perp lending:**
```python
L_A = 1/(1 + liquidation_distance)  # Spot lending
B_A = 0.0                            # No borrowing
L_B = 0.0                            # No second lending
B_B = liquidation_distance/(1 + liquidation_distance)  # Perp short
```

**Example (20% liquidation distance):**
- L_A = 1/(1 + 0.2) = 0.8333 (83.33%)
- B_A = 0.0
- L_B = 0.0
- B_B = 0.2/(1 + 0.2) = 0.1667 (16.67%)

**Example (50/50 split, 100% liq distance):**
- L_A = 1/(1 + 1.0) = 0.5
- B_A = 0.0
- L_B = 0.0
- B_B = 1.0/(1 + 1.0) = 0.5

**Rate variables:**
- r_1A = Lending APR for spot token on Protocol A
- r_2A = 0 (no borrowing)
- r_2B = 0 (no lending on perp protocol)
- r_3B = Perp funding rate (annualized, from Bluefin)

**Net APR formula:**
```python
gross_earnings = L_A * r_1A + B_B * r_3B
upfront_fees = B_B * (2 * BLUEFIN_TAKER_FEE)  # Entry + exit
holding_period_years = 1.0  # Assume 1 year for APR
net_apr = gross_earnings - (upfront_fees / holding_period_years)
```

## Liquidation Formulas

### Short Perpetual Liquidation

**Setup:**
- Collateral: $C (USDC posted)
- Position: $P (notional value shorted)
- Entry price: P0
- Current price: P
- Leverage: N = P/C

**Liquidation condition:**
Loss from price increase = Collateral

**Formula:**
```
P - P0 = C * P/P0  (loss in dollar terms)
P/P0 = C/P = 1/N
P_liq = P0 * (1 + 1/N)
```

**Liquidation distance:**
```
distance = (P_liq - P0)/P0 = 1/N = C/P
```

**For long perpetuals** (formula is symmetric):
```
P_liq = P0 * (1 - 1/N)
distance = (P0 - P_liq)/P0 = 1/N
```

### Spot Lending Liquidation

**Key difference:** This strategy has NO liquidation risk on the spot side because:
1. We're not borrowing against the spot tokens
2. Spot tokens are collateral, not borrowed assets
3. Lending protocols don't liquidate lenders

**Effective liquidation distance:** infinity on lending side

## Fee Structure

### Perpetual Fees (Bluefin)

**Maker fee:** 0.01% (1 bps) - when you provide liquidity
**Taker fee:** 0.035% (3.5 bps) - when you take liquidity

**Conservative assumption:** Pay taker fee on both entry and exit
- Entry: 0.035% x position_size
- Exit: 0.035% x position_size
- **Total upfront:** 0.07% x position_size

**Stored as:**
```python
BLUEFIN_MAKER_FEE = 0.0001   # 0.01%
BLUEFIN_TAKER_FEE = 0.00035  # 0.035%
```

**Amortized over holding period:**
```python
annual_fee_drag = (2 * BLUEFIN_TAKER_FEE) / holding_period_years
```

### Lending Protocol Fees

Most lending protocols have zero entry/exit fees. Borrow fees are captured in the borrow_total_apr.

## Token Mappings

### Bluefin Perpetual Markets

Mapping is explicitly controlled in `config/settings.py` via `BLUEFIN_TO_LENDINGS` dictionary.

**Example structure:**
```python
BLUEFIN_TO_LENDINGS = {
    '0xBTC-USDC-PERP_bluefin': [
        '0xaafb...::btc::BTC',      # BTC
        '0x876a...::xbtc::XBTC',    # xBTC
        '0x41f9...::wbtc::WBTC',    # wBTC
    ],
    '0xETH-USDC-PERP_bluefin': [
        '0xaf8c...::coin::COIN',    # ETH
        '0xd0e8...::eth::ETH',      # wETH
    ],
    # ... other perp markets
}
```

**Generation:**
1. Query `token_registry` table
2. Filter to tokens with `pyth_id` OR `coingecko_id` (not neither)
3. Group by base asset (BTC, ETH, SOL, etc.)
4. Map to corresponding perp markets

**Strategy generation:** For each perp market, generate strategies for all mapped spot tokens on all lending protocols.

## Current Simplifications

**To be addressed later:**

1. **Maker/taker optimization:** Assume worst case (taker fees)
2. **Funding rate volatility:** Use current rate, no forecasting
3. **Rebalancing costs:** Ignore drift between spot and perp sizes
4. **Oracle risk:** Assume accurate price feeds
5. **Dummy pricing:** Perp tokens use placeholder price 10.10101 in `rates_snapshot` (TODO: replace with real mark price)
6. **Backfill:** `backfill_rates_snapshot_with_perp()` is a stub (TODO: implement)

**Addressed:**
- ~~Basis risk: assume spot = perp~~ → `spot_perp_basis` table now tracks real AMM spread and tradeable entry/exit costs

## Risk Analysis

### Risks Present

1. **Lending protocol risk:** Smart contract risk on lending side
2. **Funding rate reversal:** If funding goes negative, strategy loses
3. **Bluefin protocol risk:** Smart contract/liquidation engine risk
4. **Basis risk:** Spot and perp prices can diverge
5. **Liquidation risk:** If leverage too high, short gets liquidated

### Risks Absent (vs Recursive Lending)

1. **NO multi-protocol cascading:** Only 1 lending protocol
2. **NO double liquidation:** Spot side cannot be liquidated
3. **NO loop complexity:** Only 2 legs (lend + short)
4. **NO borrow rate spikes:** Not borrowing from lending protocols

### Risk Mitigation

- Start with conservative liquidation distance (100% = 50/50 split)
- Monitor funding rates hourly (already happening)
- Alert if funding goes negative (to be implemented)
- Rebalance when spot/perp ratio drifts >5%

## Verification Queries

```sql
-- Check Bluefin rows in rates_snapshot
SELECT timestamp, protocol, token, lend_total_apr, borrow_total_apr
FROM rates_snapshot
WHERE protocol = 'Bluefin'
ORDER BY timestamp DESC
LIMIT 10;

-- Compare with raw rates in perp_margin_rates
SELECT timestamp, token_contract, funding_rate_annual
FROM perp_margin_rates
WHERE protocol = 'Bluefin'
ORDER BY timestamp DESC
LIMIT 10;

-- Verify sign convention:
-- If funding_rate_annual = +0.0876 (8.76%)
-- Then lend_total_apr should = -0.0876 (-8.76%)
-- And borrow_total_apr should = -0.0876 (-8.76%)

-- Check basis rows for latest snapshot
SELECT perp_ticker, spot_contract,
       spot_bid, spot_ask,
       perp_bid, perp_ask,
       basis_bid * 100 AS basis_bid_pct,
       basis_ask * 100 AS basis_ask_pct,
       basis_mid * 100 AS basis_mid_pct
FROM spot_perp_basis
ORDER BY timestamp DESC, perp_ticker, spot_contract
LIMIT 30;

-- Check index reference rows only (oracle basis, zero AMM spread)
SELECT perp_ticker, spot_bid AS index_price,
       basis_bid * 100 AS basis_bid_pct,
       basis_ask * 100 AS basis_ask_pct
FROM spot_perp_basis
WHERE spot_contract LIKE '0x%-USDC-INDEX_bluefin'
ORDER BY timestamp DESC;

-- Verify timestamp alignment: basis and rates_snapshot share the same timestamp
SELECT r.timestamp, r.protocol, r.token,
       b.perp_ticker, b.basis_mid * 100 AS basis_mid_pct
FROM rates_snapshot r
JOIN spot_perp_basis b
  ON r.timestamp = b.timestamp
  AND r.token_contract = b.perp_proxy
WHERE r.protocol = 'Bluefin'
ORDER BY r.timestamp DESC
LIMIT 12;
```
