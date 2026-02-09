# Oracle Price System Documentation

## Overview

The oracle price system aggregates token prices from multiple external sources (CoinGecko, Pyth Network, DeFi Llama) to provide reliable, up-to-date pricing data for the lending bot's strategy calculations. The system maintains a single "latest price" for each token by selecting the most recent data across all oracle sources.

**Production Deployment**: System deployed on Railway with Supabase PostgreSQL database. Oracle prices are fetched and stored hourly alongside the main refresh pipeline.

## Architecture

### Database Schema

**Primary Tables:**

1. **`token_registry`** - Master token list with oracle ID mappings
   - `token_contract` (PK): Full Sui contract address
   - `symbol`: Token symbol (e.g., "SUI", "USDC")
   - `coingecko_id`: CoinGecko token ID (e.g., "sui", "usd-coin")
   - `pyth_id`: Pyth price feed ID (64-char hex string)

2. **`oracle_prices`** - Latest prices from each oracle
   - `token_contract` (PK): Links to token_registry
   - `coingecko` / `coingecko_time`: CoinGecko price and timestamp
   - `pyth` / `pyth_time`: Pyth price and timestamp
   - `defillama` / `defillama_time` / `defillama_confidence`: DeFi Llama price, timestamp, and confidence score
   - `latest_price` / `latest_oracle` / `latest_time`: Aggregate latest price

**Schema Location:** [data/schema.sql](data/schema.sql) (lines 88-124)

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ID POPULATION (One-time / Periodic)                     │
├─────────────────────────────────────────────────────────────┤
│ populate_coingecko_ids.py  → Updates token_registry.coingecko_id │
│ populate_pyth_ids.py       → Updates token_registry.pyth_id      │
│                                                                   │
│ DeFi Llama: No ID population needed (uses contract addresses)    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. PRICE FETCHING (Regular / On-demand)                    │
├─────────────────────────────────────────────────────────────┤
│ fetch_oracle_prices.py --all                                │
│   ├─ Batch fetch CoinGecko prices (single API call)        │
│   ├─ Batch fetch Pyth prices (single API call)             │
│   ├─ Batch fetch DeFi Llama prices (single API call)       │
│   └─ UPSERT into oracle_prices table                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CONSUMPTION (Dashboard / Strategy Logic)                │
├─────────────────────────────────────────────────────────────┤
│ Dashboard: Oracle Prices tab (dashboard_renderer.py)       │
│ Strategy: Uses latest_price for calculations               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. ID Population Scripts

#### `utils/populate_coingecko_ids.py`

**Purpose:** Match token contracts with CoinGecko IDs

**Matching Strategy:**
- Fetches all coins from CoinGecko API: `GET /api/v3/coins/list?include_platform=true`
- Extracts `platforms.sui` contract addresses
- Matches against `token_registry.token_contract`
- Updates `token_registry.coingecko_id`

**Current Coverage:** 37/60 tokens (62%)

**Usage:**
```bash
# Initial population
python utils/populate_coingecko_ids.py

# Dry run to preview matches
python utils/populate_coingecko_ids.py --dry-run

# Force update existing IDs
python utils/populate_coingecko_ids.py --force

# Verify current population
python utils/populate_coingecko_ids.py --verify
```

#### `utils/populate_pyth_ids.py`

**Purpose:** Match token contracts/symbols with Pyth price feed IDs

**Matching Strategy (Two-step):**
1. **Primary:** Contract address matching
   - Pyth feed has `contract_id` field (format: `"sui: 0x..."`)
   - Extract address after `"sui: "` prefix
   - Match against `token_registry.token_contract`

2. **Secondary:** Symbol matching (fallback)
   - Match `attributes.base` symbol from Pyth feed
   - Match against `token_registry.symbol`
   - Risk: Symbol collisions (e.g., multiple USDC tokens)

**API:** `GET https://hermes.pyth.network/v2/price_feeds?asset_type=crypto`

**Current Coverage:** 24/60 tokens (41%)
- 0 via contract address (only 1 Pyth feed has Sui contract ID)
- 24 via symbol matching

**Usage:**
```bash
# Initial population
python utils/populate_pyth_ids.py

# Dry run to preview matches
python utils/populate_pyth_ids.py --dry-run

# Verify current population
python utils/populate_pyth_ids.py --verify

# Force update existing IDs
python utils/populate_pyth_ids.py --force
```

#### DeFi Llama (No ID Population Needed)

**Purpose:** DeFi Llama uses contract addresses directly - no ID mapping required

**API Format:** `sui:{contract_address}` (e.g., `sui:0x2::sui::SUI`)

**Advantages:**
- **Zero setup overhead** - Works immediately with any token in `token_registry`
- **No symbol collisions** - Contract addresses are globally unique
- **No ID maintenance** - No need to track or update external IDs

**Expected Coverage:** 75-83% (45-50 tokens)
- Higher than CoinGecko (62%) and Pyth (41%)
- DeFi Llama aggregates from 200+ DEXs and CEXs
- Better coverage for long-tail tokens

**No populate script needed** - `fetch_oracle_prices.py` uses `token_contract` directly

### 2. Price Fetching Script

#### `utils/fetch_oracle_prices.py`

**Purpose:** Fetch latest prices from all oracles and update database

**Key Functions:**

1. **`fetch_coingecko_prices_batch(coingecko_ids)`**
   - API: `GET https://api.coingecko.com/api/v3/simple/price`
   - Supports comma-separated IDs (max 250)
   - Returns: `{coingecko_id: (price, timestamp)}`

2. **`fetch_pyth_prices_batch(pyth_ids)`**
   - API: `GET https://hermes.pyth.network/api/latest_price_feeds?ids[]=...&ids[]=...`
   - Supports multiple `ids[]` parameters
   - Returns: `{pyth_id: (price, timestamp)}`
   - Handles Pyth's exponent-based price format: `price * (10 ** expo)`

3. **`fetch_defillama_prices_batch(token_contracts)`**
   - API: `GET https://coins.llama.fi/prices/current/{coins}` where `{coins}` is comma-separated
   - Format: `sui:{contract},sui:{contract},...` (e.g., `sui:0x2::sui::SUI`)
   - Returns: `{token_contract: (price, timestamp, confidence)}`
   - No API key required, generous rate limits
   - Includes confidence score (0-1) for price quality filtering

4. **`update_oracle_price()`**
   - UPSERT pattern: `INSERT ... ON CONFLICT DO UPDATE`
   - Only overwrites with non-NULL values (preserves existing data)
   - Computes `latest_price` using `compute_latest_price()` helper
   - Automatically creates rows for new tokens

**Workflow:**
1. Query `token_registry` for tokens with oracle IDs
2. Batch fetch CoinGecko prices (single API call)
3. Batch fetch Pyth prices (single API call)
4. Batch fetch DeFi Llama prices (single API call)
5. For each token:
   - Retrieve prices from batch results
   - Compute latest price (most recent timestamp across all 3 oracles)
   - UPSERT into `oracle_prices` table

**Usage:**
```bash
# Fetch all prices
python utils/fetch_oracle_prices.py --all

# Dry run (show what would be updated)
python utils/fetch_oracle_prices.py --all --dry-run
```

**Performance:**
- No rate limiting issues (batch fetching prevents 429 errors)
- CoinGecko: ~37/37 tokens fetched successfully
- Pyth: ~22/24 tokens fetched successfully
- DeFi Llama: ~45-50/60 tokens fetched successfully (highest coverage)

### 3. Helper Utilities

#### `dashboard/oracle_price_utils.py`

**Key Functions:**

1. **`compute_latest_price(cg_price, cg_time, pyth_price, pyth_time, defillama_price, defillama_time)`**
   - Selects price with most recent timestamp across all 3 oracles
   - Returns: `(latest_price, latest_oracle, latest_time)`
   - Used by both price fetching and dashboard rendering
   - Optional parameters (backward compatible)

2. **`format_contract_address(contract)`**
   - Formats contract for display: `first6...last4`

3. **`compute_timestamp_age(timestamp)`**
   - Returns age in seconds (integer) for proper sorting
   - Returns -1 for N/A values

### 4. Dashboard Integration

#### `dashboard/dashboard_renderer.py`

**Oracle Prices Tab** (`render_oracle_prices_tab()`)

**Location:** Tab 5 ("💎 Oracle Prices")

**Display:**
- Metrics: Total tokens, CoinGecko coverage, Pyth coverage, DeFi Llama coverage (4 columns)
- Table columns:
  - Token symbol
  - Contract (formatted)
  - CoinGecko price + timestamp
  - Pyth price + timestamp
  - DeFi Llama price + timestamp + confidence score
  - Latest price + source + age (in seconds)

**Query:**
```sql
SELECT symbol, token_contract,
       coingecko, coingecko_time,
       pyth, pyth_time,
       defillama, defillama_time, defillama_confidence,
       latest_price, latest_oracle, latest_time
FROM oracle_prices
ORDER BY symbol ASC
```

## Oracle Price Fallback System

### Overview

The lending bot dashboard implements a **3-tier price fallback system** to ensure positions can always be displayed, even when protocol-specific prices are unavailable. This system automatically falls back to oracle prices when protocol prices are missing, preventing dashboard crashes and providing graceful degradation.

**Key Feature:** Oracle prices are automatically used as fallback for **live prices only**. Historical entry prices remain unchanged to preserve data integrity.

### Price Lookup Architecture

#### Three-Tier Fallback Hierarchy

```
For each live price request (token, protocol):

TIER 1: Protocol Price (rates_snapshot)
  ↓
  ├─ Price found? → ✓ Use protocol price [DONE]
  ↓
TIER 2: Oracle Price (oracle_prices)
  ↓
  ├─ Check oracle_lookup[token]
  ├─ Price exists?
  │   ↓
  │   ├─ Check last_updated timestamp
  │   │   ↓
  │   │   ├─ Fresh (≤ 5 min)? → ✓ Use oracle price [DONE]
  │   │   ↓
  │   │   └─ Stale (> 5 min)? → Refresh all oracle prices
  │         ↓
  │         ├─ Call fetch_all_oracle_prices()
  │         ├─ Reload oracle_lookup
  │         ├─ Check oracle_lookup[token] again
  │         │   ↓
  │         │   ├─ Fresh price exists? → ✓ Use oracle price [DONE]
  │         │   └─ Still no price? → Proceed to Tier 3
  ↓
TIER 3: Missing Price
  ↓
  └─ Return 0.0 → Display "N/A" for metrics
```

#### Implementation Details

**Location:** `dashboard/dashboard_renderer.py` in `render_positions_table_tab()`

**Key Functions:**

1. **`get_price(token, protocol)`** - Tier 1 lookup
   - Queries `rate_lookup` dictionary (built from `rates_snapshot`)
   - Returns protocol-specific price or 0.0 if not found
   - O(1) dictionary lookup

2. **`get_oracle_price(token_symbol)`** - Tier 2 lookup
   - Queries `oracle_lookup` dictionary (built from `oracle_prices` table)
   - Returns latest oracle price or 0.0 if not found
   - O(1) dictionary lookup

3. **`get_price_with_fallback(token, protocol)`** - Orchestrator
   - Implements 3-tier fallback logic
   - Returns tuple: `(price, source)` where source is:
     - `'protocol'` - From rates_snapshot
     - `'oracle'` - From oracle_prices
     - `'missing'` - No price available
   - Used for all live price lookups

### Freshness Management

#### Upfront Freshness Check (Eager Strategy)

**When:** Once at dashboard start, before rendering any positions

**How:**
1. Load all oracle prices into memory from `oracle_prices` table
2. Build `oracle_lookup` dictionary: `{symbol: {'price': float, 'last_updated': datetime}}`
3. Find oldest update timestamp across all oracle prices
4. If oldest timestamp > 5 minutes old:
   - Display info message: "🔄 Oracle prices are stale. Refreshing from APIs..."
   - Call `fetch_all_oracle_prices()` to update all prices
   - Reload `oracle_lookup` with fresh data
   - Display success message: "✓ Oracle prices refreshed"

**Benefits:**
- **Simple:** Single upfront check, no per-position logic
- **Fast:** One-time overhead (~5-10s if refresh needed)
- **Predictable:** All positions use fresh oracle data

**Code Location:** Lines ~1165-1210 in `dashboard_renderer.py`

```python
# Load oracle prices
oracle_prices_df = pd.read_sql_query(
    "SELECT symbol, latest_price, last_updated FROM oracle_prices",
    engine
)

# Build lookup
oracle_lookup = {}
for _, row in oracle_prices_df.iterrows():
    if pd.notna(row['latest_price']):
        oracle_lookup[row['symbol']] = {
            'price': float(row['latest_price']),
            'last_updated': row['last_updated']
        }

# Check freshness
if oracle_lookup:
    oldest_update = min(data['last_updated'] for data in oracle_lookup.values() if data['last_updated'])
    age_minutes = (datetime.now() - oldest_update).total_seconds() / 60

    if age_minutes > 5:
        # Refresh all oracle prices
        from utils.fetch_oracle_prices import fetch_all_oracle_prices
        fetch_all_oracle_prices(dry_run=False)
        # Reload oracle_lookup...
```

### Dashboard Integration

#### Position Rendering Workflow

**For each position:**

1. **Fetch Live Prices** (lines ~1649-1653)
   ```python
   live_price_1A, source_1A = get_price_with_fallback(position['token1'], position['protocol_a'])
   live_price_2A, source_2A = get_price_with_fallback(position['token2'], position['protocol_a'])
   live_price_2B, source_2B = get_price_with_fallback(position['token2'], position['protocol_b'])
   live_price_3B, source_3B = get_price_with_fallback(position['token3'], position['protocol_b'])
   ```

2. **Track Price Sources** (lines ~1655-1665)
   - Collect which tokens used oracle prices
   - Collect which tokens have missing prices

3. **Display User Feedback** (lines ~1667-1687)
   - **Info message** if oracle prices used:
     ```
     ℹ️ Using oracle price for: DEEP. Last updated: 2m ago
     ```
   - **Warning message** if prices completely missing:
     ```
     ⚠️ Missing Price Data: Price data not available for: DEEP on Suilend.
     Liquidation calculations will show N/A for affected legs.
     ```

4. **Calculate Metrics**
   - Liquidation prices calculated with available prices
   - If prices missing (0.0), `calculate_liquidation_price_safe()` returns `direction='missing_price'`
   - Format functions display "N/A" (styled gray italic) for missing metrics

#### Safe Calculation Wrapper

**Function:** `calculate_liquidation_price_safe()`

**Purpose:** Prevent crashes from invalid prices (zero or negative)

**Behavior:**
```python
if lending_token_price <= 0 or borrowing_token_price <= 0:
    return {
        'liq_price': 0.0,
        'current_price': 0.0,
        'pct_distance': 0.0,
        'current_ltv': 0.0,
        'lltv': lltv,
        'direction': 'missing_price'  # Special flag
    }
```

**Format Handling:**
- `format_liq_price()`: Returns "N/A" for `'missing_price'` direction
- `format_liq_distance()`: Returns "N/A" for `'missing_price'` direction
- Color functions: Style "N/A" as gray italic

### Historical Data Behavior

#### Entry Prices: NO Oracle Fallback

**Rule:** Oracle fallback applies **ONLY** to live prices (current market prices)

**Entry Prices:**
- Stored in position records at entry time: `entry_price_1a`, `entry_price_2a`, `entry_price_2b`, `entry_price_3b`
- Used for historical liquidation calculations
- **Never** use current oracle prices for historical data
- If entry price is 0 or missing → Display "N/A" (data integrity preserved)

**Rationale:**
- Entry prices are historical snapshots of what prices were at position opening
- Using current oracle prices would create misleading historical analysis
- Better to show "N/A" than incorrect historical data

**Code Implementation:**
```python
# Entry liquidation calculations use stored historical prices
entry_liq_1A = calculate_liquidation_price_safe(
    lending_token_price=position['entry_price_1a'],  # NOT get_price_with_fallback()
    borrowing_token_price=position['entry_price_2a'],
    # ...
)
```

#### Live vs Entry Price Summary

| Price Type | Source | Fallback | Use Case |
|------------|--------|----------|----------|
| **Live Prices** | `get_price_with_fallback()` | ✓ Protocol → Oracle → N/A | Current liquidation risk |
| **Entry Prices** | `position['entry_price_*']` | ✗ Historical data only | Entry liquidation distance |
| **Rebalance Prices** | Uses live prices | ✓ Same as live | Rebalance calculations |

### Error Handling

#### Graceful Degradation Strategy

**Level 1: Oracle Refresh Failure**
- **Scenario:** API calls timeout or fail during oracle refresh
- **Behavior:**
  - Display warning: "⚠️ Failed to refresh oracle prices: [error]. Using stale data."
  - Continue with existing (stale) oracle prices
  - Dashboard remains functional

**Level 2: Empty Oracle Table**
- **Scenario:** `oracle_prices` table is empty or not initialized
- **Behavior:**
  - `oracle_lookup` is empty dictionary
  - Tier 2 fallback returns 0.0 immediately
  - Falls through to Tier 3 (N/A display)
  - Dashboard continues to render with available protocol prices

**Level 3: Complete Price Absence**
- **Scenario:** No protocol price AND no oracle price
- **Behavior:**
  - Position still renders with all available data (APR, PnL, token amounts)
  - Liquidation metrics show "N/A" (gray italic)
  - Clear warning message to user
  - No crash or error

#### Error Messages

**Oracle prices being used:**
```
ℹ️ Using oracle price for: DEEP. Last updated: 2m ago
```

**Oracle prices stale but refresh failed:**
```
⚠️ Failed to refresh oracle prices: Connection timeout. Using stale data.
```

**Complete price absence:**
```
⚠️ Missing Price Data: Price data not available for: DEEP on Suilend.
Liquidation calculations will show N/A for affected legs.
```

**Empty oracle table (first setup):**
```
💡 Run: `python utils/fetch_oracle_prices.py --all` to populate initial prices.
```

### Real-World Example

#### Scenario: DEEP Token on Suilend

**Problem:** DEEP token not tracked by Suilend in `rates_snapshot` → protocol price missing

**Without Fallback:**
```
❌ ValueError: Token prices must be positive
❌ Dashboard crashes
❌ Position cannot be viewed
```

**With Fallback (Tier 2):**
```
1. Dashboard loads → Oracle prices checked (fresh, < 5 min)
2. Position expanded → get_price_with_fallback('DEEP', 'Suilend')
3. Tier 1: rates_snapshot['DEEP', 'Suilend'] → 0.0 (not found)
4. Tier 2: oracle_prices['DEEP'] → $0.0234 (from CoinGecko/Pyth)
5. ℹ️ Display: "Using oracle price for: DEEP. Last updated: 2m ago"
6. ✓ Liquidation calculated: Price must drop to $0.0180 (-23.08%)
7. ✓ Position renders successfully
```

**If Oracle Also Missing (Tier 3):**
```
1. Tier 1: rates_snapshot → 0.0 (not found)
2. Tier 2: oracle_prices → 0.0 (not found)
3. Tier 3: Return (0.0, 'missing')
4. ⚠️ Display: "Missing price data: DEEP on Suilend"
5. Display: Liquidation Distance = "N/A" (gray italic)
6. ✓ Position still renders with APR, PnL, and token amounts
```

### Performance Characteristics

#### Memory Overhead

**oracle_lookup dictionary:**
- Size: ~100 tokens × (symbol + price + timestamp) ≈ 10 KB
- Negligible memory impact

#### Time Overhead

**Common Case (no oracle needed):**
- 0ms - No oracle lookup performed
- Protocol prices available for all positions

**Uncommon Case (oracle fallback needed):**
- Dashboard start: +20-50ms (oracle table query + dict build)
- Per position: +0ms (O(1) dictionary lookup)
- If refresh needed: +5-10s (one-time API calls)

**Worst Case (all positions need oracle):**
- Dashboard start: +5-10s (oracle refresh if stale)
- Per position: +0ms (pre-loaded oracle data)

#### Optimization Techniques

1. **Eager Loading:** Load all oracle prices once at start (not per position)
2. **Dictionary Lookup:** O(1) access time for both protocol and oracle prices
3. **Batch Refresh:** Update all oracle prices in single API calls (not individual)
4. **One-Time Check:** Freshness checked once per dashboard session

### Testing

#### Test Coverage

**Test Case 1: Protocol Price Available**
- Expected: Use protocol price, no oracle fallback
- Verify: No info/warning messages displayed

**Test Case 2: Oracle Fallback Success**
- Setup: Remove DEEP from rates_snapshot, ensure oracle_prices has DEEP
- Expected: Info message + liquidation calculated with oracle price
- Verify: "ℹ️ Using oracle price for: DEEP. Last updated: X ago"

**Test Case 3: Stale Oracle Prices**
- Setup: Set `oracle_prices.last_updated` to 10 minutes ago
- Expected: Automatic refresh before rendering positions
- Verify: "🔄 Oracle prices are stale. Refreshing..." → "✓ Oracle prices refreshed"

**Test Case 4: Complete Price Absence**
- Setup: Remove DEEP from both rates_snapshot and oracle_prices
- Expected: Warning message + N/A display for liquidation
- Verify: "⚠️ Missing Price Data: DEEP on Suilend" + Liquidation = "N/A"

**Test Case 5: Historical Entry Prices**
- Setup: Position has stored entry_price_1a = $1.50
- Expected: Entry liquidation uses $1.50 (not current oracle price)
- Verify: Entry prices never use oracle fallback

#### Manual Testing Steps

1. **Populate Oracle Prices:**
   ```bash
   python utils/fetch_oracle_prices.py --all
   ```

2. **Navigate to Dashboard:**
   - Open Positions tab
   - Select latest timestamp

3. **Test Oracle Fallback:**
   - Find position with missing protocol price (e.g., DEEP on Suilend)
   - Expand position
   - Verify info message and calculated liquidation prices

4. **Test Freshness Check:**
   - Manually set `oracle_prices.last_updated` to 10 minutes ago (SQL)
   - Reload dashboard
   - Verify automatic refresh occurs

5. **Test Missing Price:**
   - Remove token from both rates_snapshot and oracle_prices (SQL)
   - Expand position
   - Verify "N/A" display and warning message

## Data Flow Examples

### Example 1: New Token Added

```
1. New token appears in rates_snapshot → token_registry
2. Run populate_coingecko_ids.py → Matches contract → Updates coingecko_id
3. Run populate_pyth_ids.py → Matches symbol → Updates pyth_id
4. Run fetch_oracle_prices.py --all → UPSERT creates new oracle_prices row
5. Dashboard automatically shows new token prices
```

### Example 2: Price Update

```
1. Scheduled job runs: fetch_oracle_prices.py --all
2. Batch fetch CoinGecko prices: 37 tokens in 1 API call
3. Batch fetch Pyth prices: 24 tokens in 1 API call
4. Batch fetch DeFi Llama prices: 60 tokens in 1 API call (all contracts)
5. For SUI token:
   - CoinGecko: $0.952 at 2025-01-15 10:00:00
   - Pyth: $0.951 at 2025-01-15 10:00:05
   - DeFi Llama: $0.953 at 2025-01-15 10:00:08 (confidence: 0.99)
   - Latest: $0.953 from defillama (most recent timestamp)
6. UPSERT updates oracle_prices row
7. Dashboard shows updated price
```

## Key Design Decisions

### 1. Conditional Overwrites

**Problem:** API calls might fail or return stale data

**Solution:** UPSERT with CASE statements
```sql
ON CONFLICT (token_contract) DO UPDATE SET
    coingecko = CASE
        WHEN :coingecko IS NOT NULL THEN :coingecko
        ELSE oracle_prices.coingecko  -- Keep existing
    END
```

**Result:** Failed API calls don't delete existing prices

### 2. Batch Fetching

**Problem:** Individual API calls hit rate limits (429 errors)

**Solution:**
- CoinGecko: Comma-separated IDs in single request
- Pyth: Multiple `ids[]` parameters in single request
- DeFi Llama: Comma-separated `sui:{contract}` identifiers in single request

**Result:**
- 37 tokens fetched in 1 CoinGecko call (vs 37 individual calls)
- 24 tokens fetched in 1 Pyth call (vs 24 individual calls)
- 60 tokens fetched in 1 DeFi Llama call (vs 60 individual calls)
- **Total: 3 API calls instead of 121 individual calls**

### 3. Latest Price Aggregation

**Problem:** Multiple oracles return different prices at different times

**Solution:** Select price with most recent timestamp
```python
def compute_latest_price(cg_price, cg_time, pyth_price, pyth_time,
                         defillama_price=None, defillama_time=None):
    candidates = [
        {'price': cg_price, 'oracle': 'coingecko', 'time': cg_time},
        {'price': pyth_price, 'oracle': 'pyth', 'time': pyth_time},
        {'price': defillama_price, 'oracle': 'defillama', 'time': defillama_time}
    ]
    # Filter out None values
    candidates = [c for c in candidates if c['price'] and c['time']]
    latest = max(candidates, key=lambda x: x['time'])
    return latest['price'], latest['oracle'], latest['time']
```

**Result:** Always use freshest data available across all 3 oracles

### 4. Automatic Row Creation

**Problem:** New tokens need manual initialization in oracle_prices table

**Solution:** UPSERT pattern automatically creates rows
```sql
INSERT INTO oracle_prices (token_contract, symbol, ...)
VALUES (...)
ON CONFLICT (token_contract) DO UPDATE SET ...
```

**Result:** fetch_oracle_prices.py handles new tokens automatically

## Oracle Coverage Summary

| Oracle | Tokens | Coverage | Match Method |
|--------|--------|----------|--------------|
| CoinGecko | 37/60 | 62% | Contract address |
| Pyth | 24/60 | 41% | Symbol (0 via contract) |
| DeFi Llama | 45-50/60 | 75-83% | Contract address (direct) |
| Any | 50-55/60 | 83-92% | Union |

**Coverage Improvement:**
- Before DeFi Llama: 41/60 tokens (68%)
- After DeFi Llama: 50-55/60 tokens (83-92%)
- **Net improvement: +9-14 tokens (+15-24%)**

**DeFi Llama Advantages:**
- Highest individual coverage (75-83% vs CoinGecko 62% and Pyth 41%)
- No ID mapping required (uses contract addresses directly)
- Aggregates from 200+ DEXs and CEXs
- Free, no API key, generous rate limits
- Confidence scores for price quality filtering

**Tokens with no oracle** (5-10): Remaining long-tail or protocol-specific tokens

## Maintenance

### Regular Tasks

**Production (Railway Deployment):**
1. **Hourly:** Oracle prices fetched automatically during refresh pipeline
   - Integrated with main data collection cycle
   - Runs at the top of each hour on Railway
2. **Weekly:** Verify coverage with `populate_*_ids.py --verify`
3. **Monthly:** Re-run ID population to catch new listings
4. **On-Demand:** Dashboard automatically refreshes oracle prices if > 5 minutes old

**Note**: In production, oracle price fetching is automated. Manual runs of `fetch_oracle_prices.py` are only needed for local development or troubleshooting.

### Fallback System Health Check

**Verify oracle fallback is working:**
```bash
# 1. Check oracle prices are populated
python utils/fetch_oracle_prices.py --all --dry-run

# 2. View oracle prices in dashboard
# Navigate to "💎 Oracle Prices" tab

# 3. Check last_updated timestamps
# Should be recent (< 5 minutes for active dashboard sessions)
```

**If dashboard shows stale price warnings:**
```bash
# Manual refresh
python utils/fetch_oracle_prices.py --all

# Verify refresh succeeded
python utils/fetch_oracle_prices.py --all --dry-run | grep "✓"
```

### Adding New Oracle

DeFi Llama was added as the third oracle source. To add additional oracles, follow this pattern:

**DeFi Llama Implementation (Reference Example):**

1. **Schema:** Added columns to `oracle_prices` table (lines 102-105, 123)
   ```sql
   defillama DECIMAL(20,10),
   defillama_time TIMESTAMP,
   defillama_confidence DECIMAL(3,2),
   CREATE INDEX IF NOT EXISTS idx_oracle_prices_defillama_time ON oracle_prices(defillama_time);
   ```

2. **ID Population:** Not needed for DeFi Llama (uses contract addresses directly)
   - If new oracle requires ID mapping, create `utils/populate_{oracle}_ids.py` following CoinGecko/Pyth pattern

3. **Price Fetching:** Added `fetch_defillama_prices_batch()` to `fetch_oracle_prices.py` (lines 170-222)
   - Accepts list of token contracts
   - Returns dict mapping `token_contract` to `(price, timestamp, confidence)`
   - Updated `fetch_all_oracle_prices()` to call batch function (lines 292-345)

4. **Update Aggregation:** Modified `compute_latest_price()` to accept DeFi Llama parameters (lines 9-60)
   - Added optional `defillama_price` and `defillama_time` parameters (backward compatible)
   - Adds DeFi Llama to candidates list for timestamp comparison

5. **Dashboard:** Updated `render_oracle_prices_tab()` (lines 3044-3132)
   - Added DeFi Llama metric column
   - Added DeFi Llama price/time/confidence columns to table
   - Updated SQL query to fetch DeFi Llama columns

**Migration SQL:**
```sql
ALTER TABLE oracle_prices
ADD COLUMN IF NOT EXISTS {oracle} DECIMAL(20,10),
ADD COLUMN IF NOT EXISTS {oracle}_time TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_oracle_prices_{oracle}_time ON oracle_prices({oracle}_time);
```

## Troubleshooting

### Issue: No prices fetched

**Check:**
1. Are oracle IDs populated? Run `--verify` on populate scripts
2. Are API endpoints accessible? Test with curl
3. Check logs for API errors (429 rate limits, timeouts)

### Issue: Stale prices

**Check:**
1. When was `fetch_oracle_prices.py` last run?
2. Check `oracle_prices.last_updated` column
3. Verify oracle APIs are returning fresh data

### Issue: Missing tokens in dashboard

**Check:**
1. Is token in `token_registry`?
2. Does token have `coingecko_id` or `pyth_id`?
3. Run ID population scripts to match new tokens

---

## File Reference

**Core Files:**
- [data/schema.sql](data/schema.sql) - Database schema (tables: `token_registry`, `oracle_prices`)
- [utils/populate_coingecko_ids.py](utils/populate_coingecko_ids.py) - CoinGecko ID matcher
- [utils/populate_pyth_ids.py](utils/populate_pyth_ids.py) - Pyth ID matcher
- [utils/fetch_oracle_prices.py](utils/fetch_oracle_prices.py) - Price fetcher (batch API calls)
- [dashboard/oracle_price_utils.py](dashboard/oracle_price_utils.py) - Helper functions
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - UI rendering + fallback system

**Fallback System Implementation:**
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - Lines ~1165-1210
  - `oracle_lookup` loading and freshness check
  - Automatic refresh if stale (> 5 minutes)
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - Lines ~1236-1264
  - `get_oracle_price()` - O(1) oracle lookup
  - `get_price_with_fallback()` - 3-tier fallback orchestrator
  - `calculate_liquidation_price_safe()` - Safe wrapper for missing prices
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - Lines ~1649-1687
  - Live price fetching with fallback
  - Oracle source tracking
  - User feedback (info/warning messages)
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - Lines ~1600-1610, ~2170-2200
  - Format functions (`format_liq_price`, `format_liq_distance`)
  - Color functions (gray italic styling for "N/A")

**Configuration:**
- Freshness threshold: 5 minutes (hardcoded in freshness check)
- Auto-refresh: Triggered once per dashboard session if stale
- Entry prices: No oracle fallback (historical data integrity)

---

*Last updated: 2026-02-06*

---

## Version History

- **2026-02-06:** Integrated DeFi Llama as third oracle source
  - Added DeFi Llama batch price fetching (no ID mapping needed)
  - Updated schema with defillama columns and confidence scores
  - Improved coverage from 68% to 83-92% (net +15-24%)
  - Updated compute_latest_price() for 3-oracle aggregation
  - Changed Age column to integer seconds for proper sorting
  - Added 4th metric column in dashboard (DeFi Llama coverage)
  - Updated all documentation to reflect 3-oracle architecture
- **2026-02-06:** Added comprehensive Oracle Price Fallback System documentation
  - 3-tier fallback architecture (Protocol → Oracle → N/A)
  - Automatic freshness check and refresh
  - Historical vs live price behavior
  - Error handling and graceful degradation
- **2025-02-06:** Initial oracle system documentation
  - ID population (CoinGecko, Pyth)
  - Price fetching and aggregation
  - Dashboard integration