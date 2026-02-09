# Sui Lending Bot - Comprehensive Handover Document

## Overview

The Sui Lending Bot is a dashboard application for analyzing and executing recursive lending strategies across multiple Sui DeFi protocols (AlphaFi, Navi, Suilend, Pebble). The system tracks rates, calculates optimal position sizes, manages paper trading positions, and provides historical time-travel functionality.

**Document Version**: February 9, 2026
**System Status**: Production deployment on Railway with Supabase PostgreSQL
**Deployment**: Railway (cloud platform) + Supabase PostgreSQL (database)
**Refresh Schedule**: Hourly, at the top of each hour

---

## Recent Major Changes (February 2026)

### 1. PnL Calculation Fix: Token Amounts × Price (February 9, 2026)
- **Status**: Complete
- **Issue**: System was calculating PnL using `deployment × weight`, ignoring price drift between rebalances
- **Fix**: Now uses `token_amount × current_price` for accurate position valuation
- **Impact**: Corrects PnL calculations for positions with price volatility between rebalances
- **Files Modified**:
  - `analysis/position_service.py`: Updated `calculate_leg_earnings_split()` to use token amounts
  - `analysis/position_statistics_calculator.py`: Pass correct token amounts for live and rebalanced segments
- **Design Principle**: See Design Notes #12 - Always use actual token quantities, not target weights

### 2. Database Migration: SQLite → Supabase (PostgreSQL)
- **Status**: Complete, deployed on Railway
- **Production Database**: Supabase PostgreSQL (cloud-hosted)
- **Configuration**: `USE_CLOUD_DB=True` in production
- **Legacy**: SQLite was used for initial local development only
- **Connection**: Managed via SQLAlchemy engine factory with connection pooling

### 3. SQLAlchemy Integration
- **Status**: Complete
- **Impact**: Resolved pandas UserWarnings, added connection pooling
- **Pattern**: Dual-mode - SQLAlchemy engines for pandas queries, raw connections for cursor operations
- **Performance**: 20-50% faster with connection pooling on Supabase

### 4. Performance Optimizations
- **Batch Loading**: Eliminated N+1 query problem (6,000+ → 60 queries)
- **Lookup Dictionaries**: Replaced O(n) DataFrame filtering with O(1) dictionary lookups
- **Expected Speedup**: 20-60x faster dashboard rendering
- **Implementation Date**: February 3, 2026

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       EXTERNAL DATA SOURCES                       │
│   (Navi, AlphaFi, Suilend, Pebble APIs via protocol readers)    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │  refresh_pipeline()   │  Hourly on Railway
             │  (Orchestration)      │  (top of each hour)
             └──────────┬────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌────────────┐
   │Snapshot │   │ Analysis │   │Token       │
   │Save     │   │ Cache    │   │Registry    │
   └────┬────┘   └────┬─────┘   └────────────┘
        │             │
        └──────┬──────┘
               ▼
┌────────────────────────────────────────────────────────────┐
│                 DATABASE LAYER                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  Supabase PostgreSQL (production on Railway)    │     │
│  │  - SQLAlchemy Engine Factory (connection pool)   │     │
│  │  - Raw connections for cursor operations         │     │
│  │  Legacy: SQLite (local development only)         │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  Tables:                                                   │
│  ├─ rates_snapshot: Historical rates, prices, fees        │
│  ├─ positions: Active/closed positions (event sourced)    │
│  ├─ position_rebalances: Historical segments              │
│  ├─ token_registry: Token metadata                        │
│  ├─ reward_token_prices: Reward token pricing             │
│  ├─ analysis_cache: 48hr cached analysis results          │
│  └─ chart_cache: 48hr cached Plotly charts                │
└────────────────────────┬───────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
    ┌──────────────────┐    ┌──────────────────┐
    │ DASHBOARD        │    │ TIME-TRAVEL      │
    │ (Latest)         │    │ (Historical)     │
    └─────┬────────────┘    └──────────────────┘
          │
    ┌─────┴──────────────────────────────┐
    │                                    │
    ▼                                    ▼
┌──────────────┐                  ┌──────────────┐
│ Analysis &   │                  │ Position     │
│ Business     │                  │ Management   │
│ Logic Layer  │                  │              │
│              │                  │              │
│ RateAnalyzer │                  │ PositionSrvc │
│ PositionCalc │                  │ RebalanceChk │
└──────────────┘                  └──────────────┘
```

---

## Critical Design Principles

### 1. Timestamp as "Current Time"

**Core Principle**: When the user selects a timestamp in the dashboard, that timestamp IS the "live"/"current"/present time. Everything flows from that timestamp.

- **Dashboard queries**: All data fetching uses `WHERE timestamp <= strategy_timestamp`
- **Never use datetime.now()**: NEVER default to `datetime.now()` except when collecting fresh market data from protocols
- **Time travel**: This allows the dashboard to act as a time machine - showing what was available at any historical moment

**Example**:
```python
# ✅ CORRECT: Get all data up to the selected moment
query = "SELECT * FROM rates_snapshot WHERE timestamp <= ? AND ..."
params = (strategy_timestamp, ...)

# ❌ WRONG: Using datetime.now() or arbitrary cutoff dates
cutoff = datetime.now() - timedelta(days=30)  # ❌ NO!
```

### 2. Unix Timestamps (Integers) Internally

**Architecture**:
```
Database (strings)         Python Code (ints)         UI (strings)
"2026-02-03 10:00:00"  →   1738581600             →  "2026-02-03 10:00:00"
     ↑                                                      ↑
     to_seconds()                                     to_datetime_str()
```

**Why**:
- Type safety: Integers are simple, comparable, and fast
- No pandas/datetime confusion
- SQL compatibility: Works with both PostgreSQL and SQLite
- Easy arithmetic: Time deltas are just `seconds2 - seconds1`

**Two Helper Functions**:
```python
to_seconds(anything) -> int      # Handles str, datetime, pd.Timestamp, int
to_datetime_str(int) -> str      # Always returns "YYYY-MM-DD HH:MM:SS" (19 chars)
```

### 3. Event Sourcing for Positions

**Pattern**: Immutable historical records

- `positions` table: Entry state frozen (never mutated)
- `position_rebalances` table: Historical segments (append-only)
- Current PnL = calculated from rates_snapshot + rebalance segments

**Benefits**:
- Perfect reproducibility (can replay any position's history)
- No accidental overwrites
- Audit trail built-in
- Can calculate PnL at any point in time

### 4. Token Identity: Contract Addresses, Not Symbols

**Rule**: All logic uses `token_contract`, symbols only for display

**Why**: Token symbols can be duplicated (e.g., suiUSDT vs USDT are different tokens with different contracts)

**Correct**:
```python
# ✅ Logic: use contracts
token_row = df[df['token_contract'] == token_contract]

# ✅ Display: use symbols
st.write(f"Token: {token_symbol}")
```

**Incorrect**:
```python
# ❌ WRONG: Logic using symbols
token_row = df[df['token'] == 'USDT']  # Which USDT?!
```

### 5. Rates as Decimals

**Rule**: All rates, APRs, fees stored as decimals (0.0 to 1.0 scale). Convert to percentages ONLY at display layer.

**Correct**:
```python
# Storage
entry_lend_rate_1A = 0.0316  # 3.16%

# Display
display_rate = f"{entry_lend_rate_1A * 100:.2f}%"  # "3.16%"
```

### 6. Collateral Ratio and Liquidation Threshold Pairing

**Rule**: Wherever `collateral_ratio` parameters are used, `liquidation_threshold` parameters MUST also be present.

**Relationship**:
- `collateral_ratio` (Max LTV): Maximum you can borrow (e.g., 0.70 = 70%)
- `liquidation_threshold` (Liquidation LTV): Point at which liquidation occurs (e.g., 0.75 = 75%)
- **Always**: `liquidation_threshold > collateral_ratio`

---

## Database Layer

### Configuration

**File**: `config/settings.py`

```python
USE_CLOUD_DB = True                          # Production: Always True (Supabase)
SQLITE_PATH = "data/lending_rates.db"        # Legacy: Local development only
SUPABASE_URL = os.getenv('SUPABASE_URL')     # Production: Supabase PostgreSQL from .env

# Auto-rebalancing
REBALANCE_THRESHOLD = 0.02  # 2% - triggers auto-rebalance warnings

# Caching
SAVE_SNAPSHOTS = True       # Enable snapshot caching
```

### SQLAlchemy Engine Factory

**File**: `dashboard/db_utils.py` (Created February 2026)

```python
get_db_engine() -> Engine
dispose_engines()
```

**Pattern**: Singleton connection pooling
- Caches engines for both SQLite and PostgreSQL
- Reuses connections efficiently
- PostgreSQL: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`
- SQLite: `check_same_thread=False` for Streamlit compatibility

**Usage**:
```python
# For pandas queries (NEW)
engine = get_db_engine()
df = pd.read_sql_query(query, engine, params=params)

# For cursor operations (UNCHANGED)
conn = get_db_connection()  # Returns psycopg2 or sqlite3 connection
cursor = conn.cursor()
cursor.execute(query, params)
```

### SQL Placeholder Handling

**Pattern**: Dynamic based on database type

```python
ph = self._get_placeholder()  # Returns '?' for SQLite, '%s' for PostgreSQL
query = f"SELECT * FROM table WHERE id = {ph}"
```

### Database Schema

**File**: `data/schema.sql`

#### Core Tables

**1. rates_snapshot** - Historical Rate Data (Immutable)
- **Primary Key**: `(timestamp, protocol, token_contract)`
- **Columns**:
  - Rates: `lend_base_apr`, `lend_reward_apr`, `lend_total_apr`, `borrow_base_apr`, `borrow_reward_apr`, `borrow_total_apr`
  - Risk: `collateral_ratio`, `liquidation_threshold`, `borrow_weight`
  - Pricing: `price_usd`
  - Liquidity: `available_borrow_usd`, `utilization`, `total_supply_usd`, `total_borrow_usd`
  - Fees: `borrow_fee`
- **Indexes**: Time, token contract, protocol+contract combinations
- **Design**: Snapshot-based, append-only (never updated)

**2. positions** - Active/Historical Positions (Event Sourced)
- **Primary Key**: `position_id` (UUID)
- **Status**: `active`, `closed`, `liquidated`
- **Entry State**: All initial rates, prices, collateral ratios captured at entry
- **Position Multipliers**: `l_a`, `b_a`, `l_b`, `b_b` (normalized weightings)
- **Rebalancing**: `accumulated_realised_pnl`, `rebalance_count`, `last_rebalance_timestamp`
- **Design**: Immutable entry state + mutable current state

**3. position_rebalances** - Historical Segments (Append-Only)
- **Primary Key**: `rebalance_id` (UUID)
- **Foreign Key**: `position_id`
- **Sequence**: `sequence_number` (1, 2, 3, ...)
- **Time Range**: `opening_timestamp` → `closing_timestamp`
- **Realized Metrics**: `realised_pnl`, `realised_fees`, `realised_lend_earnings`, `realised_borrow_costs`
- **Design**: Each rebalance creates immutable segment with opening/closing rates and prices

**4. token_registry** - Token Metadata
- **Primary Key**: `token_contract`
- **Columns**: Symbol, optional Pyth/CoinGecko IDs, protocol flags
- **Pattern**: Upsert-friendly, "sticky" flags (once set, persist)

**5. reward_token_prices** - Reward Token Pricing
- **Pattern**: Last-write-wins (no protocol attribution)
- **Usage**: Separate tracking for governance/reward tokens

**Cache Tables** (48-hour retention):
- `analysis_cache`: Cached strategy analysis results
- `chart_cache`: Cached Plotly chart HTML

---

## Data Flow Pipeline

### Refresh Pipeline (Single Orchestration Point)

**File**: `data/refresh_pipeline.py`

```python
def refresh_pipeline(
    timestamp: Optional[datetime] = None,
    liquidation_distance: float = settings.DEFAULT_LIQUIDATION_DISTANCE,
    save_snapshots: bool = settings.SAVE_SNAPSHOTS,
    send_slack_notifications: bool = True,
) -> RefreshResult
```

**Processing Flow**:

1. **Data Fetch** → `merge_protocol_data()` combines data from all protocols
2. **Snapshot Save** → `RateTracker.save_snapshot()` persists to `rates_snapshot`
3. **Analysis** → `RateAnalyzer.find_best_protocol_pair()` finds optimal strategies
4. **Caching** → `tracker.save_analysis_cache()` stores results (48-hour retention)
5. **Auto-Rebalancing** → `PositionService.check_positions_need_rebalancing()` checks all active positions
6. **Alerting** → `SlackNotifier` sends top strategies notification

**Returns**: `RefreshResult` dataclass with:
- Raw merged data (10 DataFrames)
- Strategy analysis results
- Rebalance checks and metrics
- Token registry updates

**Scheduling**: Runs hourly via Railway scheduler (top of each hour)

### Rate Tracking (Data Persistence)

**File**: `data/rate_tracker.py`

**RateTracker Class**:
```python
tracker = RateTracker(
    use_cloud=settings.USE_CLOUD_DB,
    db_path=settings.SQLITE_PATH,
    connection_url=settings.SUPABASE_URL
)
```

**Key Methods**:
- `save_snapshot()` - Saves all 10 DataFrames to rates_snapshot table
- `upsert_token_registry()` - Updates token metadata
- `save_analysis_cache()` / `load_analysis_cache()` - 48hr cache management
- `save_chart_cache()` / `load_chart_cache()` - Cached Plotly charts

**Type Conversion**: Automatically converts NumPy types to Python native types for PostgreSQL compatibility

**Data Quality Validation**: `_validate_snapshot_quality()`
- Alerts when rows < 20 (expected ~47)
- Alerts when protocols < 3 (expected 3)
- Sends Slack webhook notifications on issues

---

## Dashboard Architecture

### Main Entry Point

**File**: `dashboard/dashboard_renderer.py`

```python
def main():
    # 1. Sidebar: User inputs
    #    - Liquidation distance slider
    #    - Deployment USD amount
    #    - Time-travel picker (all available timestamps)
    #    - Filters (stablecoin-only, min APR, token/protocol filters)

    # 2. Data Loading
    #    - Check analysis cache first (instant if hit)
    #    - If miss, run RateAnalyzer against snapshot
    #    - Save result to cache

    # 3. Render timestamp display
    #    - Show which snapshot being viewed

    # 4. Render 4 tabs
```

### Dashboard Structure: Four Tabs

| Tab | Purpose | Data Source | Key Features |
|-----|---------|-------------|--------------|
| **📊 All Strategies** | Sortable table of top strategies | `all_results` from RateAnalyzer + filters | Deploy button, expandable details, historical charts |
| **📈 Rate Tables** | Raw protocol data (rates, prices, fees) | Direct from `rates_snapshot` | Protocol comparison, token lookup |
| **⚠️ 0 Liquidity** | Strategies with zero available liquidity | `all_results` filtered by `available_borrow` | Warning indicators |
| **💼 Positions** | Active/closed positions with PnL tracking | `positions` + `position_rebalances` tables | Rebalance, close, time-travel |

### Time-Travel Implementation

**Mechanism**: Timestamp picker in sidebar loads ANY historical snapshot

```python
available_timestamps = get_available_timestamps()  # All distinct timestamps in DB
selected = st.selectbox("Viewing timestamp:", available_timestamps)
```

**Features**:
- Complete reproducibility - any past snapshot can be re-analyzed
- Compare strategies across time periods
- Chart historical performance
- Position PnL at any historical timestamp

---

## Position Management

### Position Service Architecture

**File**: `analysis/position_service.py`

```python
service = PositionService(conn, engine=None)
```

**Design Pattern**: Event sourcing
- Positions table = immutable entry state
- Rebalances table = historical segments
- Calculated fields applied at read time

**Key Methods**:

#### Position Lifecycle
- `create_position()` - Creates new position from strategy
- `get_active_positions()` - Retrieves active positions, optionally filtered by timestamp
- `get_position_by_id()` - Gets single position with defensive type conversion
- `close_position()` - Closes position, calculates final PnL

#### PnL Calculations
- `calculate_position_value()` - Calculates current position value and PnL breakdown
- `calculate_leg_earnings_split()` - **OPTIMIZED (Feb 2026)**: Batch loads rates, calculates base/reward earnings split

#### Rebalancing
- `rebalance_position()` - Manual rebalance triggered by user
- `check_positions_need_rebalancing()` - Auto-rebalance check (runs in refresh_pipeline)
- `create_rebalance_record()` - Creates immutable segment in position_rebalances table

#### Historical
- `get_position_state_at_timestamp()` - Time-travel: gets position state at historical timestamp
- `get_rebalance_history()` - Gets all rebalance segments for a position
- `has_future_rebalances()` - Checks if position rebalanced after selected timestamp

### Auto-Rebalancing System

**Trigger Mechanism**:
- Runs automatically in `refresh_pipeline()` every hour on Railway
- Compares entry liquidation distance vs. current liquidation distance
- Threshold: `REBALANCE_THRESHOLD = 0.02` (2%)

**Formula**:
```python
needs_rebalance = abs(current_liq_dist) - abs(entry_liq_dist) < REBALANCE_THRESHOLD
```

**When Triggered**:
1. Creates new entry in `position_rebalances` table
2. Records opening/closing rates and prices for all 4 legs
3. Calculates realized PnL:
   - Realized fees paid
   - Lend earnings (accrued interest)
   - Borrow costs (accrued interest)
   - Net PnL = earnings - costs - fees
4. Accumulates PnL to `positions.accumulated_realised_pnl`
5. Updates `positions.rebalance_count` and `last_rebalance_timestamp`

**Manual Rebalance**:
- User clicks "Rebalance" button in Positions tab
- Opens modal for confirmation
- Creates same rebalance record regardless of threshold
- **Time-travel protection**: Disabled when viewing past timestamps with future rebalances

---

## Performance Optimizations (February 2026)

### Optimization #1: Batch Load Rates (100x Query Reduction)

**File**: `analysis/position_service.py` - `calculate_leg_earnings_split()`

**Problem**: N+1 query problem - queried rates for EACH timestamp individually

**Before**:
```python
# Query timestamps
timestamps_df = pd.read_sql_query(query_timestamps, ...)

# Loop and query EACH timestamp
for i in range(len(timestamps_df) - 1):
    ts_current = timestamps[i]
    rates = pd.read_sql_query(rate_query, ..., params=(ts_current, ...))  # 100+ queries
```

**After**:
```python
# Single bulk query for ALL rates in the segment
bulk_query = """
SELECT timestamp, lend_base_apr, lend_reward_apr
FROM rates_snapshot
WHERE timestamp >= ? AND timestamp <= ?
  AND protocol = ? AND token_contract = ?
ORDER BY timestamp ASC
"""
all_rates = pd.read_sql_query(bulk_query, engine, params=(start, end, protocol, token_contract))

# Create lookup dictionary for O(1) access
rates_lookup = {to_seconds(row['timestamp']): row for _, row in all_rates.iterrows()}

# Loop uses dictionary lookup - NO queries
for timestamp in timestamps:
    rate_data = rates_lookup[timestamp]  # O(1) lookup
```

**Impact**:
- **Before**: 6,000+ queries per dashboard render
- **After**: ~60 queries per dashboard render
- **Reduction**: **100x fewer queries**

### Optimization #2: Rate Lookup Dictionaries (15x Operation Reduction)

**File**: `dashboard/dashboard_renderer.py`

**Problem**: Helper functions did O(n) DataFrame filtering on every call

**Before**:
```python
def get_rate(token, protocol, rate_type):
    # O(n) DataFrame filtering - SLOW
    row = rates_df[(rates_df['token'] == token) & (rates_df['protocol'] == protocol)]
    return float(row[f'{rate_type}_total_apr'].iloc[0])

# Called 6 times per position
for position in positions:
    lend_1A = get_rate(token1, protocol_a, 'lend')  # O(n) scan
    borrow_2A = get_rate(token2, protocol_a, 'borrow')  # O(n) scan
    # ... 4 more lookups
```

**After**:
```python
# Build lookup dictionary ONCE before loop
rate_lookup = {}
for _, row in rates_df.iterrows():
    key = (row['token'], row['protocol'])
    rate_lookup[key] = {
        'lend': float(row['lend_total_apr']) if pd.notna(row['lend_total_apr']) else 0.0,
        'borrow': float(row['borrow_total_apr']) if pd.notna(row['borrow_total_apr']) else 0.0,
        'borrow_fee': float(row['borrow_fee']) if pd.notna(row['borrow_fee']) else 0.0,
        'price': float(row['price_usd']) if pd.notna(row['price_usd']) else 0.0
    }

# Updated helper function - O(1) lookup
def get_rate(token, protocol, rate_type):
    key = (token, protocol)
    data = rate_lookup.get(key, {})
    return data.get(rate_type, 0.0)

# Same usage, but now O(1)
for position in positions:
    lend_1A = get_rate(token1, protocol_a, 'lend')  # O(1) dict lookup
```

**Impact**:
- **Before**: 900+ O(n) DataFrame filter operations
- **After**: 30 operations to build dict + 30 O(1) lookups = 60 operations
- **Reduction**: **15x fewer operations**

### Combined Performance Improvement

**Expected Results**:
- **Before**: 5-15 seconds initial render
- **After**: 0.5-1.5 seconds
- **Total Speedup**: **20-60x faster**

---

## Position Calculator & APR Calculations

### Position Size Calculation

**File**: `analysis/position_calculator.py`

```python
calculator = PositionCalculator(liquidation_distance=0.20)  # 20% minimum buffer
positions = calculator.calculate_positions(
    liquidation_threshold_a=0.75,      # 75% liq threshold
    liquidation_threshold_b=0.80,      # 80% liq threshold
    collateral_ratio_a=0.70,           # 70% max LTV
    collateral_ratio_b=0.75,           # 75% max LTV
    borrow_weight_a=1.0,               # Risk adjustment
    borrow_weight_b=1.0
)
```

**Returns**: `{l_a, b_a, l_b, b_b, r_A, r_B, liquidation_distance}`

**Geometric Series Convergence**:
```python
l_a = 1 / (1 - r_A × r_B)       # Total lent token1
b_a = l_a × r_A                 # Total borrowed token2
l_b = b_a                       # All borrowed token2 re-lent
b_b = l_b × r_B                 # Total borrowed token1 from Protocol B
```

**Safety Mechanisms**:
- Auto-adjusts if effective LTV exceeds collateral ratio
- Sets effective LTV to 99.5% of max collateral factor as cap
- Handles borrow weights (reduce borrowing capacity if weight > 1.0)

### APR Calculations

**Four APR Metrics**:

1. **Net APR** (base - fees):
   ```python
   net_apr = (l_a × lend_rate_1a + l_b × lend_rate_2b)
           - (b_a × borrow_rate_2a + b_b × borrow_rate_3b)
           - (b_a × fee_2a + b_b × fee_3b)
   ```

2. **5-Day APR** - Time-adjusted for upfront fees:
   ```python
   apr5 = net_apr - (b_a × fee_2a + b_b × fee_3b) × 365 / 5
   ```

3. **30-Day APR**:
   ```python
   apr30 = net_apr - (b_a × fee_2a + b_b × fee_3b) × 365 / 30
   ```

4. **90-Day APR**:
   ```python
   apr90 = net_apr - (b_a × fee_2a + b_b × fee_3b) × 365 / 90
   ```

### Days to Breakeven

```python
days_to_breakeven = (total_fees × 365) / gross_apr
```

- Returns `0.0` if no fees (instant breakeven)
- Returns `inf` if gross_apr ≤ 0 (never breaks even)
- Warns on very short-term holds (< 5 days unprofitable)

---

## Recent Enhancements (January-February 2026)

### Enhanced Segment Summary Display (January 2026)

The Positions Tab shows detailed PnL breakdown for each rebalance segment and live position:

**5-Metric Summary Format**:
- **Realised PnL**: Total profit/loss for the segment
- **Total Earnings**: Net earnings (Lend Earnings - Borrow Costs)
- **Base Earnings**: Earnings from base APRs
- **Reward Earnings**: Earnings from reward APRs
- **Fees**: Upfront borrow fees (full for first segment, delta for rebalances)

Each metric displays both USD amount and percentage of deployment: `$X,XXX.XX (Y.YY%)`

**Example**:
```
Segment Summary
Realised PnL: $125.50 (1.26%)
Total Earnings: $180.25 (1.80%)
Base Earnings: $140.10 (1.40%)
Reward Earnings: $40.15 (0.40%)
Fees: $54.75 (0.55%)
```

### Base/Reward APR Breakdown

Token tables show per-leg earnings split between base and reward APRs:

**New Columns**:
- **Lend/Borrow Base $$$**: USD earnings from base rates
- **Reward $$$**: USD earnings from reward rates

**Implementation**:
- Helper method: `calculate_leg_earnings_split()` in position_service.py
- Queries rates_snapshot for `lend_base_apr`, `lend_reward_apr`, `borrow_base_apr`, `borrow_reward_apr`
- Calculates earnings period-by-period using forward-looking rate principle
- **Critical**: Queries use `token_contract` not `token` symbol

**Algorithm**:
```python
# For each timestamp period [t_i, t_{i+1})
period_years = (t_next - t_current) / (365.25 * 86400)

# Query rates at t_current (NOW BATCH LOADED - Feb 2026 optimization)
base_apr, reward_apr = get_rates_at_timestamp(t_current, token_contract, protocol)

# Calculate earnings for period
if action == 'Lend':
    base_earnings += deployment * weight * base_apr * period_years
    reward_earnings += deployment * weight * reward_apr * period_years
else:  # Borrow
    base_costs += deployment * weight * base_apr * period_years
    reward_savings += deployment * weight * reward_apr * period_years
```

### Delta Fees Calculation

**First segment**: Show full upfront borrow fees
**After rebalance**: Show only fees on INCREMENTAL borrowing

**Logic**:
```python
if prev_rebalance exists:
    delta_borrow = current_borrow_amount - prev_borrow_amount
    if delta_borrow > 0:
        delta_fees = borrow_fee_rate * delta_borrow * price
        display = f"${delta_fees:.2f} (Δ)"
    else:
        display = "$0.00"
else:
    full_fees = borrow_fee_rate * borrow_amount * price
    display = f"${full_fees:.2f}"
```

### Strategy Summary (Real + Unreal)

New summary section combining ALL segments (live + all rebalances):

**Location**: Above live position display, below APR summary table

**Metrics**: Same 5-metric format as Segment Summaries
- Sums each metric across all segments
- Live segment + sum of all rebalance segments
- Shows total strategy performance to date

### Auto-Rebalancing System (February 2026)

Automatically detects and rebalances positions when liquidation risk changes significantly.

**Trigger**: When liquidation distance changes by more than configured threshold (default 2%)

**Location**: Integrated into `data/refresh_pipeline.py` - runs hourly on Railway

**Algorithm**:
1. After fetching fresh market data, check all active positions
2. For each position, compare live liquidation distances to baseline:
   - **Never rebalanced**: Baseline = entry liquidation distances
   - **Previously rebalanced**: Baseline = `closing_liq_dist_2A/2B` from most recent segment
3. Check token2 legs independently:
   - **Leg 2A**: Compare baseline vs live liquidation distance
   - **Leg 2B**: Compare baseline vs live liquidation distance
4. Trigger rebalance if: `abs(baseline_liq_dist) - abs(live_liq_dist) >= threshold`
5. Execute `service.rebalance_position()` automatically
6. Log all auto-rebalance attempts

**Configuration**:
```python
# config/settings.py
REBALANCE_THRESHOLD = 0.02  # 2% default
```

**Safety Features**:
- Only rebalances positions with `status='active'`
- Non-blocking: errors don't crash the refresh pipeline
- Detailed logging for audit trail
- Rebalance reason: `"auto_rebalance_threshold_exceeded"`

---

## Critical Files & Components

### 1. Dashboard Rendering

**File**: `dashboard/dashboard_renderer.py`

#### Key Functions:

##### `render_positions_table_tab(timestamp_seconds: int)`
**Location**: Lines 960-2200+
**Purpose**: Main entry point for Positions Tab

**Flow**:
1. Connect to database
2. Get active positions filtered by timestamp
3. Query rates/prices at selected timestamp
4. Build rate lookup dictionary (Feb 2026 optimization)
5. For each position:
   - Display summary row (expandable)
   - When expanded:
     - Display Strategy Summary (Real + Unreal)
     - Display Live Position Summary
     - Display 4-leg token table with base/reward columns
     - Display rebalance history with segment summaries
6. Calculate position value using `calculate_position_value()`
7. Calculate per-leg base/reward split using `calculate_leg_earnings_split()`

**Key Features**:
- Timestamp filtering: Only shows positions deployed before/at selected timestamp
- Context-aware messaging: Different messages for historical vs current views
- Expandable rows: Summary → Detailed breakdown
- Time-travel paradox prevention: Disables rebalance button when viewing past with future rebalances

##### Helper Functions (Lines 1012-1033) - OPTIMIZED Feb 2026

```python
# Build lookup dictionary ONCE before position loop
rate_lookup = {...}  # (token, protocol) → {lend, borrow, fee, price}

def get_rate(token, protocol, rate_type):
    """O(1) dictionary lookup"""
    key = (token, protocol)
    data = rate_lookup.get(key, {})
    return data.get(rate_type, 0.0)

def get_borrow_fee(token, protocol):
    """O(1) dictionary lookup"""
    key = (token, protocol)
    data = rate_lookup.get(key, {})
    return data.get('borrow_fee', 0.0)

def get_price(token, protocol):
    """O(1) dictionary lookup"""
    key = (token, protocol)
    data = rate_lookup.get(key, {})
    return data.get('price', 0.0)
```

### 2. Position Service (Business Logic)

**File**: `analysis/position_service.py`

#### Key Methods:

##### `get_active_positions(live_timestamp: Optional[int] = None) -> pd.DataFrame`
**Location**: Lines 271-387
**Purpose**: Retrieve active positions, optionally filtered by timestamp

**Features**:
- Backward compatible: `None` returns all active positions
- Filters positions: `positions[positions['entry_timestamp'] <= live_timestamp]`
- Converts all numeric fields (handles bytes/corrupted data)
- Returns empty DataFrame if no matches (not an error)

##### `calculate_position_value(position, start_ts, end_ts) -> Dict`
**Location**: Lines 585-709
**Purpose**: Calculate current position value and PnL breakdown

**Algorithm**:
1. Validate: `end_ts >= start_ts`
2. Extract position parameters (deployment, L_A, B_A, L_B, B_B)
3. Query ALL timestamps between start and end
4. For each period `[t_i, t_{i+1})`:
   - Get rates for all 4 legs at `t_i`
   - Calculate earnings/costs for this period
   - Accumulate totals
5. Return:
   ```python
   {
       'current_value': deployment + net_earnings,
       'lend_earnings': LE(T),
       'borrow_costs': BC(T),
       'fees': upfront borrow fees,
       'net_earnings': LE(T) - BC(T) - FEES,
       'holding_days': (end_ts - start_ts) / 86400,
       'periods_count': number of time periods
   }
   ```

##### `calculate_leg_earnings_split(position, leg, action, start_ts, end_ts) -> Tuple[float, float]`
**Location**: Lines 966-1077
**Purpose**: Calculate base and reward earnings for a single leg
**Status**: **OPTIMIZED Feb 2026** - Batch loading, 100x query reduction

**Parameters**:
- `position` (pd.Series): Position record
- `leg` (str): Leg identifier ('1A', '2A', '2B', '3B')
- `action` (str): 'Lend' or 'Borrow'
- `start_timestamp` (int): Start of period (Unix seconds)
- `end_timestamp` (int): End of period (Unix seconds)

**Returns**: `(base_amount, reward_amount)` as tuple of floats in USD

**Algorithm** (OPTIMIZED):
1. **Single bulk query** - Load ALL rates for entire segment at once:
   ```sql
   SELECT timestamp, lend_base_apr, lend_reward_apr
   FROM rates_snapshot
   WHERE timestamp >= ? AND timestamp <= ?
     AND protocol = ? AND token_contract = ?
   ```
2. Create rates lookup dictionary: `timestamp → {base_apr, reward_apr}`
3. Loop through periods - **NO queries in loop**:
   - O(1) dictionary lookup for rate data
   - Calculate earnings: `deployment × weight × apr × period_years`
4. Accumulate base and reward earnings separately

**Performance**:
- **Before**: 100+ queries per leg
- **After**: 1 query per leg
- **Speedup**: 100x fewer queries

##### Helper Methods (Lines 1360-1412)

```python
def _get_token_for_leg(position, leg) -> str:
    """Get token symbol for leg (for display)"""

def _get_token_contract_for_leg(position, leg) -> str:
    """Get token contract address for leg (for queries)"""
    # CRITICAL: Use this for database queries, not symbol

def _get_protocol_for_leg(position, leg) -> str:
    """Get protocol for leg"""

def _get_weight_for_leg(position, leg) -> float:
    """Get position weight/multiplier for leg"""
```

##### `get_position_state_at_timestamp(position_id, selected_timestamp) -> Optional[Dict]`
**Location**: Lines 1127-1210
**Purpose**: Time-travel - get position state at historical timestamp

**Algorithm**:
1. Get current position from positions table
2. If `rebalance_count == 0`: Return current state
3. Query position_rebalances for segment where:
   - `opening_timestamp <= selected_timestamp < closing_timestamp`
4. If segment found: Return segment state (pre-rebalance multipliers)
5. If no segment: Return current state

##### `check_positions_need_rebalancing(live_timestamp, threshold) -> List[Dict]`
**Location**: Lines 1661-1900
**Purpose**: Auto-rebalance check - returns positions needing rebalancing

**Features**:
- Compares per-leg liquidation distances against baseline
- Returns list of positions with delta details
- Used by `refresh_pipeline()` for auto-rebalancing

### 3. Position Calculator (Strategy Math)

**File**: `analysis/position_calculator.py`

##### `calculate_positions(...) -> Dict`
**Location**: Lines 31-135
**Purpose**: Calculate recursive position sizes (L_A, B_A, L_B, B_B)

**Algorithm**:
```python
# Use LLTV (liquidation threshold) with safety buffer
r_A = (LLTV_A / borrow_weight_A) / (1 + liq_dist)
r_B = (LLTV_B / borrow_weight_B) / (1 + liq_dist)

# Geometric series convergence
L_A = 1 / (1 - r_A * r_B)
B_A = L_A * r_A
L_B = B_A
B_B = L_B * r_B

# Auto-adjustment if effective LTV exceeds maxCF
if effective_LTV_A > collateral_ratio_A:
    r_A = (collateral_ratio_A * 0.995) / borrow_weight_A
    # Recalculate positions
```

**Returns**: `{L_A, B_A, L_B, B_B, r_A, r_B, LLTV_A, LLTV_B, ...}`

##### `calculate_liquidation_price(...) -> Dict`
**Location**: Lines 287-398
**Purpose**: Calculate liquidation price and distance

**Returns**:
```python
{
    'liq_price': liquidation price,
    'current_price': current price,
    'pct_distance': percentage distance to liquidation,
    'direction': 'up'/'down'/'liquidated'/'impossible'
}
```

### 4. Rate Analyzer (Strategy Discovery)

**File**: `analysis/rate_analyzer.py`

##### `analyze_all_combinations(...) -> pd.DataFrame`
**Location**: Lines 273-598
**Purpose**: Find all valid recursive lending strategies

**Process**:
1. Iterate all protocol pairs
2. Iterate all token combinations
3. For each combination:
   - Get rates, prices, collateral ratios, liquidation thresholds
   - Skip if any missing data or zero values
   - Call `PositionCalculator.analyze_strategy(...)`
   - Store result if valid
4. Return DataFrame sorted by net APR

**Key Validation**:
```python
# Skip if collateral ratios are zero
if collateral_1A <= 1e-9 or collateral_2B <= 1e-9:
    continue

# Skip if liquidation thresholds are zero
if LLTV_1A <= 1e-9 or LLTV_2B <= 1e-9:
    continue

# Skip if any prices are zero
if any(p <= 1e-9 for p in [price_1A, price_2A, price_2B, price_3B]):
    continue
```

---

## Common Workflows

### Deploy a New Position

**User Flow**:
1. Navigate to "All Strategies" tab
2. Select a strategy from sorted list
3. Click "Deploy Strategy" button
4. Confirm in modal
5. See confirmation in Positions tab

**Code Flow**:
```python
# dashboard_renderer.py (All Strategies Tab)
if st.button("Deploy Strategy"):
    positions = {
        'L_A': strategy['L_A'],
        'B_A': strategy['B_A'],
        'L_B': strategy['L_B'],
        'B_B': strategy['B_B']
    }

    service.create_position(
        strategy_row=pd.Series(strategy),
        positions=positions,
        token1=strategy['token1'],
        token2=strategy['token2'],
        token3=strategy['token3'],
        # ... more params
    )
```

### Rebalance a Position

**User Flow**:
1. Navigate to "Positions" tab
2. Expand a position row
3. Click "Rebalance Position" button
4. See updated rates, PnL calculation, confirmation

**Code Flow**:
```python
# dashboard_renderer.py (Positions Tab)
if st.button("🔄 Rebalance Position"):
    # Check for time-travel paradox
    if service.has_future_rebalances(position_id, timestamp_seconds):
        st.error("Cannot rebalance: future rebalances exist")
        return

    # Build snapshot with opening/closing state
    snapshot = {
        'opening_timestamp': position['entry_timestamp'],
        'closing_timestamp': timestamp_seconds,
        'opening_lend_rate_1A': position['entry_lend_rate_1A'],
        'closing_lend_rate_1A': current_rate_1A,
        # ... all rates and prices
        'realised_pnl': calculated_pnl,
        # ... breakdown
    }

    service.create_rebalance_record(
        position_id=position_id,
        snapshot=snapshot,
        rebalance_reason="User initiated",
        rebalance_notes=notes
    )
```

### Time-Travel to Historical Timestamp

**User Flow**:
1. Use timestamp selector at top of dashboard
2. Select past timestamp (e.g., yesterday)
3. Positions tab shows only positions deployed before/at that time
4. Position values calculated from entry → selected timestamp
5. If position rebalanced after selected time, shows pre-rebalance state

**Code Flow**:
```python
# dashboard_renderer.py (main)
timestamp_seconds = timestamp_selector.get_selected_timestamp()

# Positions Tab
active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

for position in active_positions:
    # Calculate value from entry → timestamp_seconds
    pv_result = service.calculate_position_value(position, entry_ts, timestamp_seconds)

    # Get historical state (if rebalanced after timestamp_seconds)
    historical_state = service.get_position_state_at_timestamp(
        position['position_id'],
        timestamp_seconds
    )
```

---

## Critical Design Considerations

### 1. Timestamp Consistency

**Problem**: Database stored timestamps with microseconds, causing exact match queries to fail

**Solution**: All timestamps MUST be exactly 19 characters: `'YYYY-MM-DD HH:MM:SS'`

**Prevention**:
- Use `to_datetime_str()` helper when writing to database
- Scripts available: `Scripts/truncate_timestamps.py`

### 2. Numeric Type Safety

**Problem**: SQLite sometimes returns numeric values as bytes

**Solution**: Defensive conversion in `get_position_by_id()` and `get_active_positions()`

**Helpers**:
```python
def safe_to_int(value, default=0):
    """Convert bytes/NaN/string to int"""
    if pd.isna(value):
        return default
    if isinstance(value, bytes):
        return int.from_bytes(value, byteorder='little')
    return int(value)

def safe_to_float(value, default=0.0):
    """Convert bytes/NaN/string to float"""
    if pd.isna(value):
        return default
    if isinstance(value, bytes):
        return float(int.from_bytes(value, byteorder='little'))
    return float(value)
```

### 3. PostgreSQL Type Conversion

**Problem**: PostgreSQL doesn't understand NumPy types

**Solution**: `_to_native_type()` method in PositionService

```python
@staticmethod
def _to_native_type(value):
    """Convert numpy types to native Python types for database insertion"""
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (np.integer, np.floating)):
        return value.item()  # Convert numpy scalar to Python scalar
    elif isinstance(value, np.ndarray):
        return value.tolist()

    return value
```

**Critical**: Must convert before INSERT/UPDATE or get `'schema "np" does not exist'` errors

---

## Troubleshooting Guide

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| pandas UserWarnings | Using raw psycopg2 connections | **RESOLVED Feb 2026** - Now using SQLAlchemy engines |
| Slow dashboard rendering | N+1 query problem | **RESOLVED Feb 2026** - Batch loading + lookup dictionaries |
| "No snapshot for timestamp" | User selected timestamp with no data | Ensure refresh_pipeline ran at that time |
| PostgreSQL connection timeout | Pool exhausted or network issue | Check `max_overflow=10` setting; monitor connections |
| NaN values in analysis results | Missing protocol data | Check data quality alerts in Slack |
| Auto-rebalance not triggering | Threshold too tight | Increase `REBALANCE_THRESHOLD` in settings.py |
| Bytes conversion errors | SQLite returning bytes | Defensive conversion in PositionService (already implemented) |

### Performance Monitoring

**Before Feb 2026 Optimizations**:
- Initial render: 5-15 seconds
- Query count: 6,000+ per render

**After Feb 2026 Optimizations**:
- Initial render: 0.5-1.5 seconds
- Query count: ~60 per render

**To Monitor**:
```python
# Add query counter
import time

start = time.time()
render_positions_table_tab(timestamp_seconds)
elapsed = time.time() - start
print(f"Render time: {elapsed:.2f}s")
```

---

## Utility Functions & Helpers

### Time Helpers

**File**: `utils/time_helpers.py`

```python
def to_seconds(value) -> int:
    """Convert any timestamp format to Unix seconds (int)"""
    # Handles: str, datetime, pandas.Timestamp, int

def to_datetime_str(seconds: int) -> str:
    """Convert Unix seconds to DB string format: 'YYYY-MM-DD HH:MM:SS'"""
    # Always returns exactly 19 characters
```

**Usage**:
```python
# DB read
timestamp_str = "2026-02-03 10:00:00"
timestamp_int = to_seconds(timestamp_str)  # 1738581600

# DB write
timestamp_int = 1738581600
timestamp_str = to_datetime_str(timestamp_int)  # "2026-02-03 10:00:00"
```

### Dashboard Utils

**File**: `dashboard/dashboard_utils.py`

```python
def get_db_connection():
    """Get raw database connection (SQLite or PostgreSQL)"""
    if settings.USE_CLOUD_DB:
        return psycopg2.connect(settings.SUPABASE_URL)
    else:
        return sqlite3.connect(settings.SQLITE_PATH)

class UnifiedDataLoader:
    """Load and merge protocol data with historical snapshot support"""

    def load_snapshot(self, timestamp: int) -> Tuple[...]:
        """Load rates, prices, liquidity at specific timestamp"""
        # Returns: (rates_df, prices_df, liquidity_df, ...)
```

---

## Scripts & Maintenance

### Data Collection
- `data/refresh_pipeline.py` - Fetch fresh rates/prices from protocols (hourly on Railway)
- `data/protocol_merger.py` - Merge data from multiple protocols

### Position Management
- `Scripts/purge_positions.py` - Delete all positions (use with `--force`)
- `Scripts/delete_invalid_position.py` - Delete specific position by ID

### Database Maintenance
- `Scripts/truncate_timestamps.py` - Fix timestamp precision (remove microseconds)
- `Scripts/backfill_*.py` - Backfill missing data from latest values
- `Scripts/cleanup_old_cache.py` - Clean old cached data (analysis/chart cache)

### Migration
- `Scripts/migrate_sqlite_to_supabase.py` - Migrate data from SQLite to PostgreSQL
- `Scripts/migrate_all_tables.py` - Migrate all tables
- `Scripts/migrate_missing_rebalance_columns.py` - Data migration for schema changes

---

## Future Enhancements

### Short-Term
1. **Real Capital Integration (Phase 2)**
   - Connect to Sui wallet
   - Execute positions on-chain
   - Track actual transactions
   - Use placeholders already in schema: `wallet_address`, `transaction_hash_open/close`, `on_chain_position_id`

2. **Multi-User Support**
   - User authentication
   - Per-user position tracking
   - Portfolio aggregation

### Long-Term
1. **Advanced Rebalancing**
   - ✅ Auto-rebalance based on liquidation risk (Implemented Feb 2026)
   - 🔲 Slack notifications for auto-rebalance events
   - 🔲 Auto-rebalance based on APR drop triggers
   - 🔲 Rebalance optimizer (minimize fees)

2. **Risk Management**
   - Real-time liquidation alerts
   - Position health scoring
   - Max drawdown limits

3. **Analytics**
   - Strategy performance comparison
   - Historical backtesting
   - Protocol comparison metrics

4. **Performance**
   - ✅ Batch loading (Implemented Feb 2026)
   - ✅ Lookup dictionaries (Implemented Feb 2026)
   - 🔲 Streamlit @st.cache_data decorators
   - 🔲 Pre-computed daily OHLC data for charts

---

## Production Deployment Checklist

### 1. Configuration

**Production Settings** (Railway):
```python
# config/settings.py
USE_CLOUD_DB = True  # Always True in production
SUPABASE_URL = "postgresql://user:pass@host:port/db"  # From Railway environment variables
```

**Environment Variables** (`.env` file):
```
SUPABASE_URL=postgresql://...
SUI_RPC_URL=...
SLACK_WEBHOOK_URL=...
```

### 2. Database Initialization

1. Run `data/schema.sql` against PostgreSQL
2. Creates all 5 tables + indexes + views
3. Verify tables created: `\dt` in psql

### 3. First Snapshot

- Manual: Run `refresh_pipeline()` to create first snapshot
- Or: Let scheduler run (hourly on Railway)

### 4. Testing

**Test Scenarios**:
1. Verify Railway deployment is accessible
2. Confirm Supabase connection is active (`USE_CLOUD_DB = True`)
3. Verify all tabs load
4. Test position creation
5. Test rebalancing
6. Test time-travel
7. Verify performance improvements (< 2 seconds initial render)
8. Check hourly refresh is running on schedule

### 5. Monitoring

- Monitor Slack notifications for data quality issues
- Set up database backup schedule (Supabase automatic)
- Track cache hit rates
- Monitor query performance
- Watch for connection pool exhaustion

---

## Key Takeaways

1. **Timestamp is Sacred**: Selected timestamp represents "now" for ALL operations. Never use `datetime.now()` except when collecting fresh data.

2. **Event Sourcing**: `positions` table = current state (mutable). `position_rebalances` table = historical segments (immutable).

3. **Contract Addresses**: Use contracts for ALL logic. Symbols ONLY for display.

4. **Defensive Programming**: Always convert numeric fields when reading from database. Always validate timestamps are exactly 19 characters.

5. **Forward-Looking Calculation**: Position value calculated by summing earnings/costs over all time periods from entry to live timestamp. Each timestamp's rates apply to the NEXT period.

6. **Base/Reward APR Split**: Dashboard shows separate earnings from base rates vs reward rates. Queries MUST use `token_contract` to match rates.

7. **Delta Fees for Rebalances**: After rebalancing, fees shown are only for INCREMENTAL borrowing, not total position fees.

8. **Segment-Based PnL**: Each rebalance creates immutable segment with calculated PnL. Live position shows unrealized PnL. Strategy Summary combines all segments.

9. **Performance Optimization**: **NEW Feb 2026** - Batch loading (100x query reduction) + lookup dictionaries (15x operation reduction) = 20-60x faster.

10. **Dual Database Support**: System supports both SQLite (dev) and PostgreSQL (prod) through config toggle. SQLAlchemy engines provide unified interface.

---

## Contact & Support

**Critical Files Reference**:
- Dashboard: `dashboard/dashboard_renderer.py`
- Position Service: `analysis/position_service.py`
- Position Calculator: `analysis/position_calculator.py`
- Rate Analyzer: `analysis/rate_analyzer.py`
- Database Schema: `data/schema.sql`
- Engine Factory: `dashboard/db_utils.py`
- Time Helpers: `utils/time_helpers.py`

**Documentation**:
- This document: `docs/Handover forDashboard work.md`
- Design principles: `docs/DESIGN_NOTES.md`
- Architecture: `docs/ARCHITECTURE.md`

**Recent Changes**:
- SQLAlchemy migration: February 3, 2026
- Performance optimizations: February 3, 2026
- Database: Migrated from SQLite to Supabase (PostgreSQL)

---

**Document Last Updated**: February 3, 2026
**System Version**: Production with Supabase + SQLAlchemy + Performance Optimizations
**Status**: ✅ Production-Ready
