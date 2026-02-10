# Positions Tab - Complete Reference & Handover Document

**Document Version:** February 9, 2026
**Purpose:** Complete technical reference for the Positions Tab functionality in the Sui Lending Bot dashboard
**Audience:** Engineers, handover recipients, README authors
**Deployment:** Railway (cloud platform) + Supabase PostgreSQL (database) - See [ARCHITECTURE.md](ARCHITECTURE.md) for complete deployment and caching architecture

**Recent Updates:**
- February 9, 2026: Updated PnL calculation formulas to use token_amount × price (not deployment × weight). See Design Notes #12
- February 9, 2026: Added iterative liquidity updates to portfolio allocator. See Design Notes #14
- February 9, 2026: Added new exposure calculation formulas (Token2 de-leveraged, Stablecoin net lending, Protocol normalized). See allocator_reference.md
- Production deployment on Railway with hourly refresh schedule

---

## Table of Contents

1. [Overview](#1-overview)
2. [Features & User Interface](#2-features--user-interface)
3. [Tab Relationships & Data Flow](#3-tab-relationships--data-flow)
4. [Position Lifecycle](#4-position-lifecycle)
5. [Database Schema & Relationships](#5-database-schema--relationships)
6. [Key Functions & Implementation](#6-key-functions--implementation)
7. [Statistics Architecture](#7-statistics-architecture)
8. [Design Principles](#8-design-principles)
9. [File Locations](#9-file-locations)
10. [Formulas & Calculations](#10-formulas--calculations)

---

## 1. Overview

### What is the Positions Tab?

The Positions Tab is the portfolio management interface where users view, monitor, and manage their recursive lending positions. It displays comprehensive metrics including PnL, APR calculations, earnings breakdowns, and provides actions to rebalance or close positions.

### Core Capabilities

- **Portfolio View:** Aggregate metrics across all positions
- **Position Details:** 4-leg breakdown with live rates, prices, and liquidation distances
- **Historical Time-Travel:** View positions and statistics at any historical timestamp
- **Position Management:** Deploy, rebalance, and close positions
- **Statistics:** Pre-calculated and on-demand calculation support
- **Rebalance History:** Complete audit trail of all position adjustments

---

## 2. Features & User Interface

### 2.1 Portfolio Summary (Top of Tab)

Displays 7 aggregate metrics across all active positions:

```
┌─────────────────────────────────────────────────────┐
│  💰 Total Deployed     📊 Total PnL (Real+Unreal)  │
│  $XXX,XXX.XX          $XX,XXX.XX (X.XX%)            │
├─────────────────────────────────────────────────────┤
│  💵 Total Earnings     ⚙️  Base Earnings            │
│  $XX,XXX.XX (X.XX%)   $XX,XXX.XX (X.XX%)            │
├─────────────────────────────────────────────────────┤
│  🎁 Reward Earnings    💸 Fees                      │
│  $X,XXX.XX (X.XX%)    $XXX.XX (X.XX%)               │
├─────────────────────────────────────────────────────┤
│  📈 Avg Realised APR   🔄 Avg Current APR           │
│  X.XX%                 X.XX%                        │
└─────────────────────────────────────────────────────┘
```

**Calculation:** Time-and-capital-weighted averages
- Realized APR: `Σ(days × deployment × realized_apr) / Σ(days × deployment)`
- Current APR: `Σ(days × deployment × current_apr) / Σ(days × deployment)`

**Location:** `dashboard_renderer.py` lines 1500-1527

### 2.2 Position Summary Row (Collapsed)

Each position displays as an expandable row with key metrics:

```
▶ Jan 19, 2026 | SUI → USDC → SUI | Navi ↔ AlphaFi | Entry 8.52% |
  Current 7.83% | Net APR 7.15% | Value $10,245.23 | PnL $245.23 |
  Earnings $312.45 | Base $280.12 | Rewards $32.33 | Fees $67.22
```

**Components:**
- **Entry Date:** Position creation timestamp
- **Token Flow:** token1 → token2 → token1 (the loop)
- **Protocols:** Protocol A ↔ Protocol B
- **Entry APR:** APR at position creation
- **Current APR:** APR based on live rates
- **Net APR:** Current APR minus time-adjusted fees
- **Value:** Current position value (deployment + PnL)
- **PnL:** Total profit/loss (realized + unrealized)
- **Earnings:** Total lend earnings minus borrow costs
- **Base/Rewards:** Earnings breakdown
- **Fees:** Total borrow fees paid

**Location:** `dashboard_renderer.py` line 1641

### 2.3 Position Detail View (Expanded)

Click the ▶ to expand and see:

#### A. Strategy Summary (Real + Unreal)

Combines all segments (live + rebalances) into totals:
- Total PnL
- Total Earnings
- Base Earnings
- Reward Earnings
- Total Fees

**Location:** Lines 2213-2236

#### B. 4-Leg Detail Table

Shows all 4 legs of the recursive lending strategy:

| Protocol | Token | Action | Weight | Entry Rate | Live Rate | Entry Price | Live Price | Liq Price | Token Amt | Token Rebal | Base/Reward $ | Fee Rate | Entry Liq Dist | Live Liq Dist | Rebal Liq Dist |
|----------|-------|--------|--------|------------|-----------|-------------|------------|-----------|-----------|-------------|---------------|----------|----------------|---------------|----------------|
| Navi | SUI | Lend | 1.45 | 3.2% | 3.0% | $3.20 | $3.35 | - | 453.1 | - | $45/$5 | - | - | - | - |
| Navi | USDC | Borrow | 0.82 | 5.1% | 5.3% | $1.00 | $1.00 | $0.95 | 820 | +12 | $42/$0 | 0.05% | 25% | 23% | 26% |
| AlphaFi | USDC | Lend | 0.82 | 4.8% | 4.6% | $1.00 | $1.00 | - | 820 | - | $39/$3 | - | - | - | - |
| AlphaFi | SUI | Borrow | 0.48 | 2.9% | 3.1% | $3.20 | $3.35 | $3.75 | 143.1 | -2.5 | $14/$1 | 0.03% | 28% | 26% | 29% |

**Key Columns Explained:**
- **Weight:** Position multiplier (l_a, b_a, l_b, b_b)
- **Entry Rate:** APR at position creation
- **Live Rate:** Current APR from rates_snapshot
- **Entry Price:** Token price at entry
- **Live Price:** Current token price
- **Liq Price:** Liquidation price (for borrow legs only)
- **Token Amt:** Current token quantity for this leg
- **Token Rebal:** Amount to add/remove to restore balance
- **Base/Reward $:** USD earnings split between base and reward APRs
- **Fee Rate:** Upfront borrow fee (for borrow legs)
- **Entry/Live/Rebal Liq Dist:** Liquidation distance percentages

**Location:** Lines 1645-2317

#### C. Live Position Summary

5-metric breakdown of unrealized PnL:
- Live PnL
- Total Earnings
- Base Earnings
- Reward Earnings
- Fees

**Location:** Lines 2320-2356

#### D. Action Buttons

- **🔄 Rebalance Position:** Adjust token2 amounts to restore target ratios
- **❌ Close Position:** Close position and realize all PnL

**Location:** Lines 2360-2499

#### E. Rebalance History

Shows all past rebalances with:
- Sequence number
- Timestamp range
- Realized PnL
- Realized APR
- Token amount changes
- Detailed metrics per segment

**Location:** Lines 2501-2700

### 2.4 Time-Travel / Historical Viewing

**Feature:** View positions as they existed at any past timestamp

**How it works:**
1. User selects timestamp from sidebar dropdown
2. Dashboard filters positions: `entry_timestamp <= selected_timestamp`
3. Only shows positions that existed at that time
4. Uses rates/prices from that timestamp
5. Calculates PnL from entry to selected timestamp

**Protection:** Cannot rebalance at past timestamp if future rebalances exist
- Prevents breaking historical timeline
- Shows warning if attempted

**Location:** Position filtering at lines 1118-1122, future rebalance check at lines 2367-2388

### 2.5 Statistics Calculation Options

**Pre-calculated (Primary Path):**
- Statistics stored in `position_statistics` table
- Loaded in single batch query
- Instant display
- Updated during data collection pipeline

**On-the-Fly Calculation (Fallback):**
- Appears when statistics missing for timestamp
- Shows "📊 Calculate Statistics" button
- Takes 1-2 seconds per position
- Saves to database for future use

**Display Logic:**
```python
stats = get_position_statistics(position_id, timestamp)

if stats is None or stats['timestamp'] != viewing_timestamp:
    # Show "Calculate Statistics" button
else:
    # Display pre-calculated stats
```

**Location:** Lines 1388-1450

---

## 3. Tab Relationships & Data Flow

### 3.1 Dashboard Tab Structure

```
┌─────────────────────────────────────────────────────────┐
│  Sui Lending Bot Dashboard                              │
├─────────────────────────────────────────────────────────┤
│  Tab 1: 📊 All Strategies                               │
│  Tab 2: 📈 Rate Tables                                  │
│  Tab 3: ⚠️  0 Liquidity                                 │
│  Tab 4: 💼 Positions  ← THIS DOCUMENT                   │
│  Tab 5: 🔮 Oracle                                       │
│  Tab 6: 🚀 Deployment                                   │
│  Tab 7: 📊 Allocator                                    │
└─────────────────────────────────────────────────────────┘
```

**Note:** Tabs 5-7 added February 2026. See [ARCHITECTURE.md](ARCHITECTURE.md) for Oracle and Deployment tabs. See [allocator_reference.md](allocator_reference.md) for Allocator tab details.

### 3.2 Data Flow: All Strategies → Positions

#### Phase 1: Strategy Selection

**Tab:** All Strategies
**File:** `dashboard_renderer.py` lines 69-154
**Action:** User browses sorted list of recursive lending strategies
**Display:** APR projections, token flows, protocol pairs

```
┌───────────────────────────────────────────────────────┐
│ SUI → USDC → SUI | Navi ↔ AlphaFi                     │
│ Net APR: 8.52% | 5-Day: 7.83% | Liq Dist: 25%        │
│ [🚀 $10,000]  ← Deploy button                         │
└───────────────────────────────────────────────────────┘
```

**On Click:**
```python
st.session_state.pending_deployment = {
    'strategy_row': strategy,
    'deployment_usd': amount,
    'liquidation_distance': liq_dist,
    'timestamp': current_timestamp
}
```

#### Phase 2: Confirmation Modal

**File:** `dashboard_renderer.py` (main function, modal handling)
**Display:** Confirms strategy details, deployment amount, expected APR
**Action:** User clicks "Confirm Deploy"

#### Phase 3: Position Creation

**File:** `analysis/position_service.py` lines 115-350
**Function:** `create_position()`

**Inputs:**
- `strategy_row`: All entry data (rates, prices, APRs, liquidation thresholds)
- `positions`: Calculated multipliers `{l_a, b_a, l_b, b_b}`
- `deployment_usd`: USD amount to deploy
- Token contracts, protocol names

**Process:**
1. Generate unique `position_id` (UUID)
2. Extract entry rates, prices, collateral ratios from strategy_row
3. Store entry liquidation thresholds
4. Calculate entry APR values
5. Insert into `positions` table with status='active'

**Database Insert:**
```sql
INSERT INTO positions (
    position_id, status, entry_timestamp, deployment_usd,
    l_a, b_a, l_b, b_b,
    entry_lend_rate_1a, entry_borrow_rate_2a, entry_lend_rate_2b, entry_borrow_rate_3b,
    entry_price_1a, entry_price_2a, entry_price_2b, entry_price_3b,
    entry_collateral_ratio_1a, entry_collateral_ratio_2b,
    entry_liquidation_threshold_1a, entry_liquidation_threshold_2b,
    ...
) VALUES (...)
```

#### Phase 4: Position Appears in Tab

**Tab:** Positions
**Display:** New position appears in list with initial metrics
**Statistics:** Can be calculated on-the-fly or pre-calculated

### 3.3 Shared Data: Rates Snapshot

All tabs use data from `rates_snapshot` table:

```
rates_snapshot (timestamp, protocol, token, lend_apr, borrow_apr, price, ...)
       ↓                ↓                    ↓
All Strategies    Rate Tables          Positions
  (for APR         (for display)        (for live rates
   projection)                           & calculations)
```

**Loading:** Single query per timestamp, cached in memory during render
**Location:** Lines 1153-1162

### 3.4 Oracle Price Fallback

When protocol prices are missing:

```
rates_snapshot.price_usd  → Try first (protocol price)
       ↓ (if NULL)
oracle_prices.latest_price → Fallback (oracle price)
       ↓ (if NULL)
"N/A" or 0.0              → Missing (display N/A)
```

**Location:** Lines 1164-1240

---

## 4. Position Lifecycle

### 4.1 Lifecycle States

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│  Deploy  │ ──────> │  Active  │ ──────> │  Closed  │
└──────────┘         └──────────┘         └──────────┘
                           │
                           ↓ (can happen multiple times)
                     ┌──────────┐
                     │ Rebalance│
                     └──────────┘
```

### 4.2 Deployment (Creation)

**Trigger:** User clicks deploy button in All Strategies tab

**Step 1: Data Capture**
- Entry timestamp (Unix seconds)
- Entry rates for all 4 legs
- Entry prices for all 4 legs
- Entry collateral ratios and liquidation thresholds
- Deployment USD amount
- Position weights (l_a, b_a, l_b, b_b)
- Entry APR values (net, 5-day, 30-day, 90-day)

**Step 2: Database Record**
```sql
INSERT INTO positions (
    position_id='uuid',
    status='active',
    entry_timestamp='2026-01-19 10:00:00',
    deployment_usd=10000,
    ...
)
```

**Step 3: Initial State**
- No rebalances: `rebalance_count=0`
- No realized PnL: `accumulated_realised_pnl=0`
- Status: `active`

**File:** `analysis/position_service.py` lines 115-350

### 4.3 Active Period

**Characteristics:**
- Position is earning/paying interest
- PnL accumulating (unrealized)
- Rates changing (tracked in rates_snapshot)
- Prices changing (tracked in rates_snapshot)

**Calculations:**
- **Current Value:** `deployment + unrealized_pnl`
- **Unrealized PnL:** Calculated from entry_timestamp to viewing_timestamp
- **Current APR:** Based on live rates

**Statistics:**
- Can be pre-calculated and stored in `position_statistics`
- Can be calculated on-demand via "Calculate Statistics" button

**No Database Updates:** Position record remains unchanged except:
- `last_rebalance_timestamp` (on rebalance)
- `rebalance_count` (on rebalance)
- `accumulated_realised_pnl` (on rebalance)

### 4.4 Rebalancing

**Purpose:** Restore target token ratios when prices shift

**Trigger:** User clicks "🔄 Rebalance Position" button

**Why Rebalance?**
When prices change, actual token amounts drift from target:
- Token2 (USDC) borrowed from Protocol A may be too much/little
- Token2 (USDC) lent to Protocol B may be too much/little
- Need to move Token2 between protocols to restore balance

**Process Flow:**

#### Step 1: Capture Snapshot
**File:** `analysis/position_service.py` lines 1178-1342
**Function:** `capture_rebalance_snapshot()`

```python
snapshot = {
    'opening_timestamp': entry_timestamp or last_rebalance_timestamp,
    'closing_timestamp': current_timestamp,

    # Opening rates & prices (from entry or last rebalance)
    'opening_lend_rate_1A': position['entry_lend_rate_1a'],
    'opening_price_1A': position['entry_price_1a'],
    # ... (all 4 legs)

    # Closing rates & prices (from rates_snapshot at current_timestamp)
    'closing_lend_rate_1A': current_rate_1a,
    'closing_price_1A': current_price_1a,
    # ... (all 4 legs)

    # Calculated metrics
    'realised_pnl': calculated_pnl_for_segment,
    'realised_fees': borrow_fees_for_segment,
    'realised_lend_earnings': total_lend_earnings,
    'realised_borrow_costs': total_borrow_costs,

    # Token amounts
    'entry_token_amount_1A': weight_1a * deployment / opening_price_1a,
    'exit_token_amount_1A': weight_1a * deployment / closing_price_1a,
    # ... (all 4 legs)
}
```

#### Step 2: Create Rebalance Record
**File:** `analysis/position_service.py` lines 1351-1674
**Function:** `create_rebalance_record()`

```sql
INSERT INTO position_rebalances (
    rebalance_id='uuid',
    position_id='parent_position_uuid',
    sequence_number=1,  -- increments with each rebalance
    opening_timestamp='2026-01-19 10:00:00',
    closing_timestamp='2026-01-25 14:30:00',
    deployment_usd=10000,
    l_a=1.45, b_a=0.82, l_b=0.82, b_b=0.48,
    -- All opening/closing rates and prices
    -- All calculated metrics
    realised_pnl=145.23,
    realised_fees=67.22,
    ...
)
```

#### Step 3: Update Position
```sql
UPDATE positions SET
    last_rebalance_timestamp = '2026-01-25 14:30:00',
    rebalance_count = rebalance_count + 1,
    accumulated_realised_pnl = accumulated_realised_pnl + 145.23,
    updated_at = CURRENT_TIMESTAMP
WHERE position_id = 'uuid'
```

#### Step 4: Display in Dashboard

Rebalance history section shows:
```
┌────────────────────────────────────────────────────┐
│ Rebalance #1: Jan 19 10:00 → Jan 25 14:30         │
│ Realised PnL: $145.23 (1.45%)                      │
│ Realised APR: 8.52%                                │
│ Token Changes:                                     │
│   USDC (Navi):   820 → 832 (+12)                  │
│   SUI (AlphaFi): 143.1 → 140.6 (-2.5)            │
└────────────────────────────────────────────────────┘
```

**File:** Lines 2501-2700

### 4.5 Closing

**Purpose:** Finalize position and realize all PnL

**Trigger:** User clicks "❌ Close Position" button

**Process Flow:**

#### Step 1: User Confirmation

Shows modal with steps:
```
1. Create final rebalance snapshot with current PnL
2. Mark position as closed
3. All PnL will be realized and recorded
⚠️  This action cannot be undone.
```

**File:** Lines 2464-2499

#### Step 2: Final Snapshot

Same as rebalance, creates final segment:
- Opening: entry or last rebalance
- Closing: current timestamp
- Calculates final PnL for segment

**File:** `analysis/position_service.py` lines 318-387
**Function:** `close_position()`

```python
# Capture final snapshot
snapshot = service.capture_rebalance_snapshot(position, close_timestamp)

# Create final rebalance record
service.create_rebalance_record(
    position_id,
    snapshot,
    rebalance_reason=f'position_closed:{close_reason}',
    rebalance_notes=close_notes
)
```

#### Step 3: Update Position Status

```sql
UPDATE positions SET
    status = 'closed',
    close_timestamp = '2026-02-06 16:00:00',
    close_reason = 'manual_close',
    close_notes = 'Closed via dashboard',
    updated_at = CURRENT_TIMESTAMP
WHERE position_id = 'uuid'
```

#### Step 4: Final State

- Position no longer appears in active positions
- All PnL is realized in rebalance records
- Complete history preserved
- Cannot be reopened (immutable)

---

## 5. Database Schema & Relationships

### 5.1 Schema Diagram

```
┌──────────────────┐
│  rates_snapshot  │  ← Historical rates & prices
└────────┬─────────┘
         │ (referenced by timestamp)
         ↓
┌──────────────────┐
│    positions     │  ← Main position records
│                  │    (immutable entry state)
│ PK: position_id  │
│ status: active/  │
│         closed   │
└────────┬─────────┘
         │
         ├─────────────────────────┐
         │                         │
         ↓                         ↓
┌─────────────────────┐   ┌──────────────────────┐
│ position_rebalances │   │ position_statistics  │
│                     │   │                      │
│ FK: position_id     │   │ FK: position_id      │
│ sequence_number     │   │ timestamp            │
│ (append-only)       │   │ (pre-calculated)     │
└─────────────────────┘   └──────────────────────┘
```

### 5.2 Table: positions

**Purpose:** Store immutable entry state and mutable current state

**Key Fields:**
```sql
position_id TEXT PRIMARY KEY              -- UUID
status TEXT                               -- 'active' | 'closed' | 'liquidated'
entry_timestamp TIMESTAMP                 -- When position created
deployment_usd DECIMAL(20,10)            -- USD amount deployed

-- Position Weights (constant)
l_a DECIMAL(10,6)                        -- Lend multiplier Protocol A
b_a DECIMAL(10,6)                        -- Borrow multiplier Protocol A
l_b DECIMAL(10,6)                        -- Lend multiplier Protocol B
b_b DECIMAL(10,6)                        -- Borrow multiplier Protocol B

-- Entry State (immutable)
entry_lend_rate_1a DECIMAL(10,6)        -- All 4 leg rates at entry
entry_price_1a DECIMAL(20,10)           -- All 4 leg prices at entry
entry_collateral_ratio_1a DECIMAL(10,6) -- Collateral ratios at entry
entry_liquidation_threshold_1a DECIMAL(10,6) -- Liq thresholds at entry

-- Rebalance Tracking (mutable)
accumulated_realised_pnl DECIMAL(20,10) DEFAULT 0.0
rebalance_count INTEGER DEFAULT 0
last_rebalance_timestamp TIMESTAMP

-- Closure (mutable)
close_timestamp TIMESTAMP
close_reason TEXT
close_notes TEXT
```

**Design Pattern:** Event Sourcing
- Entry state is frozen forever
- Current state evolves through rebalances
- History tracked in separate tables

**File:** `data/schema.sql` lines 166-273

### 5.3 Table: position_rebalances

**Purpose:** Store immutable historical segments

**Key Fields:**
```sql
rebalance_id TEXT PRIMARY KEY            -- UUID
position_id TEXT                         -- FK to positions
sequence_number INTEGER                  -- 1, 2, 3, ...

-- Timing
opening_timestamp TIMESTAMP              -- Segment start
closing_timestamp TIMESTAMP              -- Segment end

-- Weights (copied from position, constant)
deployment_usd DECIMAL(20,10)
l_a, b_a, l_b, b_b DECIMAL(10,6)

-- Opening State (rates & prices at opening_timestamp)
opening_lend_rate_1a DECIMAL(10,6)      -- All 4 legs
opening_price_1a DECIMAL(20,10)         -- All 4 legs

-- Closing State (rates & prices at closing_timestamp)
closing_lend_rate_1a DECIMAL(10,6)      -- All 4 legs
closing_price_1a DECIMAL(20,10)         -- All 4 legs

-- Token Amounts
entry_token_amount_1a DECIMAL(20,10)    -- All 4 legs at opening
exit_token_amount_1a DECIMAL(20,10)     -- All 4 legs at closing

-- Realised Metrics (calculated once)
realised_pnl DECIMAL(20,10)
realised_fees DECIMAL(20,10)
realised_lend_earnings DECIMAL(20,10)
realised_borrow_costs DECIMAL(20,10)

-- Metadata
rebalance_reason TEXT
rebalance_notes TEXT
```

**Design Pattern:** Append-Only
- Records never updated after creation
- Sequence number preserves order
- Complete historical snapshot

**File:** `data/schema.sql` lines 275-372

### 5.4 Table: position_statistics

**Purpose:** Pre-calculated summary statistics for dashboard

**Key Fields:**
```sql
position_id TEXT                         -- FK to positions
timestamp TIMESTAMP                      -- When stats calculated for

-- Core Metrics
total_pnl DECIMAL(20,10)                -- Realized + Unrealized
total_earnings DECIMAL(20,10)           -- Total lend - borrow
base_earnings DECIMAL(20,10)            -- Base APR portion
reward_earnings DECIMAL(20,10)          -- Reward APR portion
total_fees DECIMAL(20,10)               -- All borrow fees

-- Position Value
current_value DECIMAL(20,10)            -- deployment + pnl

-- APRs
realized_apr DECIMAL(10,6)              -- Annualized return
current_apr DECIMAL(10,6)               -- Current rate-based APR

-- Segment Breakdown
live_pnl DECIMAL(20,10)                 -- Unrealized from current segment
realized_pnl DECIMAL(20,10)             -- Sum of closed segments

-- Metadata
calculation_timestamp TIMESTAMP         -- When calculation performed
```

**Design Pattern:** Cache Table
- Calculated during data collection pipeline
- Stored for fast dashboard loading
- Can be recalculated on-demand
- No foreign key constraints (optional)

**File:** `data/schema.sql` lines 374-408

### 5.5 Table: rates_snapshot

**Purpose:** Historical rates and prices for all protocols/tokens

**Key Fields:**
```sql
timestamp TIMESTAMP                      -- Snapshot time
protocol TEXT                            -- 'Navi', 'AlphaFi', etc.
token TEXT                               -- Token symbol
token_contract TEXT                      -- Token contract address

lend_base_apr DECIMAL(10,6)             -- Base lending rate
lend_reward_apr DECIMAL(10,6)           -- Reward lending rate
lend_total_apr DECIMAL(10,6)            -- Total lending rate

borrow_base_apr DECIMAL(10,6)           -- Base borrow rate
borrow_reward_apr DECIMAL(10,6)         -- Reward borrow rate
borrow_total_apr DECIMAL(10,6)          -- Total borrow rate

borrow_fee DECIMAL(10,6)                 -- Upfront borrow fee
price_usd DECIMAL(20,10)                 -- Token price in USD

collateral_ratio DECIMAL(10,6)           -- Max LTV
liquidation_threshold DECIMAL(10,6)      -- Liquidation LTV
borrow_weight DECIMAL(10,6)              -- Risk adjustment
```

**Used By:**
- All Strategies: For strategy discovery
- Positions: For live rate/price lookups
- Calculations: For PnL and APR calculations

**File:** `data/schema.sql` lines 1-85

### 5.6 Relationship Summary

```
positions (1) ──── (N) position_rebalances
    │                      │
    │                      └─ Segments of position history
    └─ Parent position record

positions (1) ──── (N) position_statistics
    │                      │
    └─────────────────────── Pre-calculated summaries
                             at different timestamps

rates_snapshot ──── (referenced by all)
    │
    └─ Provides rates & prices for calculations
```

**Foreign Keys:**
- `position_rebalances.position_id` → `positions.position_id` (CASCADE)
- `position_statistics.position_id` → (no FK, optional)

**Indexes:**
- `positions`: status, entry_timestamp, protocols, tokens
- `position_rebalances`: position_id, sequence_number, timestamps
- `position_statistics`: position_id, timestamp, combined
- `rates_snapshot`: timestamp, protocol, token, combined

---

## 6. Key Functions & Implementation

### 6.1 Main Entry Point

**Function:** `render_positions_table_tab(timestamp_seconds: int)`
**File:** `dashboard/dashboard_renderer.py` lines 1107-2700
**Purpose:** Main rendering function for Positions tab

**Algorithm:**

```python
def render_positions_table_tab(timestamp_seconds: int):
    # Phase 1: Load Data
    active_positions = service.get_active_positions(timestamp_seconds)
    rates_df = load_rates_snapshot(timestamp_seconds)
    oracle_prices = load_oracle_prices()
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds)
    all_rebalances = get_all_rebalance_history(position_ids)

    # Phase 2: Calculate Portfolio Aggregates
    portfolio_metrics = {
        'total_deployed': 0,
        'total_pnl': 0,
        'total_earnings': 0,
        ...
    }

    for position in active_positions:
        stats = all_stats.get(position['position_id'])

        if stats is None:
            # Show "Calculate Statistics" button
            render_calculation_button(position)
        else:
            # Accumulate portfolio metrics
            portfolio_metrics['total_deployed'] += position['deployment_usd']
            portfolio_metrics['total_pnl'] += stats['total_pnl']
            ...

    # Phase 3: Render Portfolio Summary
    render_portfolio_summary(portfolio_metrics)

    # Phase 4: Render Individual Positions
    for position in active_positions:
        render_position_row(position, stats, rebalances)
```

### 6.2 Position Statistics Loading

**Function:** `get_all_position_statistics(position_ids, timestamp)`
**File:** `dashboard/dashboard_renderer.py` lines 993-1041
**Purpose:** Batch load statistics for all positions

**Algorithm:**

```python
def get_all_position_statistics(position_ids: list, timestamp: int) -> dict:
    # Build SQL query with window function
    query = """
    WITH ranked_stats AS (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY position_id
                                  ORDER BY timestamp DESC) as rn
        FROM position_statistics
        WHERE position_id IN (...)
          AND timestamp <= :timestamp
    )
    SELECT * FROM ranked_stats WHERE rn = 1
    """

    # Execute single query for all positions
    result_df = pd.read_sql_query(query, engine, params=params)

    # Convert to dict: position_id -> stats
    stats_dict = {}
    for _, row in result_df.iterrows():
        stats_dict[row['position_id']] = row.to_dict()

    return stats_dict
```

**Performance:** O(1) database query instead of N queries

**Note:** Returns most recent stats at or before timestamp, not exact match. Dashboard checks for exact timestamp match separately.

### 6.3 Statistics Calculation (On-Demand)

**Function:** `calculate_position_statistics(position_id, timestamp, service, get_rate_func, get_borrow_fee_func)`
**File:** `analysis/position_statistics_calculator.py` lines 23-247
**Purpose:** Calculate statistics when pre-calculated values missing

**Algorithm:**

```python
def calculate_position_statistics(...):
    # Step 1: Load position data
    position = service.get_position_by_id(position_id)
    deployment_usd = position['deployment_usd']
    l_a, b_a, l_b, b_b = position['l_a'], ...

    # Step 2: Check for rebalances
    rebalances = service.get_rebalance_history(position_id)

    if rebalances.empty:
        segment_start_ts = entry_timestamp
    else:
        segment_start_ts = rebalances.iloc[-1]['closing_timestamp']

    # Step 3: Calculate live segment (entry/last_rebalance → timestamp)
    base_1A, reward_1A = service.calculate_leg_earnings_split(
        position, '1a', 'Lend', segment_start_ts, timestamp
    )
    # ... repeat for all 4 legs

    live_base_earnings = (base_1A + base_2B) - (base_2A + base_3B)
    live_reward_earnings = reward_1A + reward_2A + reward_2B + reward_3B
    live_total_earnings = live_base_earnings + live_reward_earnings

    # Get fees from calculate_position_value
    pv_result = service.calculate_position_value(
        position, segment_start_ts, timestamp
    )
    live_fees = pv_result['fees']
    live_pnl = live_total_earnings - live_fees

    # Step 4: Sum rebalanced segments from database
    rebalanced_pnl = 0
    rebalanced_earnings = 0
    rebalanced_base = 0
    rebalanced_reward = 0
    rebalanced_fees = 0

    for _, rebal in rebalances.iterrows():
        # Recalculate each segment for consistency
        segment_base, segment_reward = calculate_segment_earnings(rebal)
        segment_total = segment_base + segment_reward
        segment_fees = rebal['realised_fees']
        segment_pnl = segment_total - segment_fees

        rebalanced_pnl += segment_pnl
        rebalanced_earnings += segment_total
        rebalanced_base += segment_base
        rebalanced_reward += segment_reward
        rebalanced_fees += segment_fees

    # Step 5: Calculate totals
    total_pnl = live_pnl + rebalanced_pnl
    total_earnings = live_total_earnings + rebalanced_earnings
    base_earnings = live_base_earnings + rebalanced_base
    reward_earnings = live_reward_earnings + rebalanced_reward
    total_fees = live_fees + rebalanced_fees

    current_value = deployment_usd + total_pnl

    # Step 6: Calculate APRs
    days_elapsed = (timestamp - entry_timestamp) / 86400
    realized_apr = (total_pnl / deployment_usd) * (365 / days_elapsed)

    # Current APR from live rates
    lend_1A = get_rate_func(token1_contract, protocol_a, 'lend')
    borrow_2A = get_rate_func(token2_contract, protocol_a, 'borrow')
    # ... get all 4 rates

    gross_apr = (l_a * lend_1A) + (l_b * lend_2B) - (b_a * borrow_2A) - (b_b * borrow_3B)
    fee_cost = (b_a * borrow_fee_2A) + (b_b * borrow_fee_3B)
    current_apr = gross_apr - fee_cost

    # Return dictionary for database insertion
    return {
        'position_id': position_id,
        'timestamp': timestamp,
        'total_pnl': total_pnl,
        'total_earnings': total_earnings,
        'base_earnings': base_earnings,
        'reward_earnings': reward_earnings,
        'total_fees': total_fees,
        'current_value': current_value,
        'realized_apr': realized_apr,
        'current_apr': current_apr,
        'live_pnl': live_pnl,
        'realized_pnl': rebalanced_pnl,
        'calculation_timestamp': int(time.time())
    }
```

**Key Sub-Functions:**
- `calculate_leg_earnings_split()`: Calculates base/reward split for one leg
- `calculate_position_value()`: Calculates total PnL with fees

### 6.4 Rebalance Snapshot Capture

**Function:** `capture_rebalance_snapshot(position, closing_timestamp)`
**File:** `analysis/position_service.py` lines 1178-1342
**Purpose:** Capture all data needed for rebalance record

**Algorithm:**

```python
def capture_rebalance_snapshot(position, closing_timestamp):
    # Determine segment start
    if position['rebalance_count'] == 0:
        opening_timestamp = position['entry_timestamp']
        opening_rates = position['entry_lend_rate_1a'], ...
        opening_prices = position['entry_price_1a'], ...
    else:
        last_rebalance = get_last_rebalance(position_id)
        opening_timestamp = last_rebalance['closing_timestamp']
        opening_rates = last_rebalance['closing_lend_rate_1a'], ...
        opening_prices = last_rebalance['closing_price_1a'], ...

    # Get closing rates & prices from rates_snapshot
    closing_rates = query_rates(closing_timestamp, protocols, tokens)
    closing_prices = query_prices(closing_timestamp, tokens)

    # Calculate realized metrics for this segment
    pv_result = calculate_position_value(
        position, opening_timestamp, closing_timestamp
    )

    realised_pnl = pv_result['net_earnings']
    realised_fees = pv_result['fees']
    realised_lend_earnings = pv_result['lend_earnings']
    realised_borrow_costs = pv_result['borrow_costs']

    # Calculate token amounts
    deployment = position['deployment_usd']
    entry_amounts = {
        '1a': (position['l_a'] * deployment) / opening_prices['1a'],
        '2a': (position['b_a'] * deployment) / opening_prices['2a'],
        '2b': (position['l_b'] * deployment) / opening_prices['2b'],
        '3b': (position['b_b'] * deployment) / opening_prices['3b']
    }

    exit_amounts = {
        '1a': (position['l_a'] * deployment) / closing_prices['1a'],
        '2a': (position['b_a'] * deployment) / closing_prices['2a'],
        '2b': (position['l_b'] * deployment) / closing_prices['2b'],
        '3b': (position['b_b'] * deployment) / closing_prices['3b']
    }

    # Build snapshot dictionary
    return {
        'opening_timestamp': opening_timestamp,
        'closing_timestamp': closing_timestamp,
        'deployment_usd': deployment,
        'l_a': position['l_a'],
        'b_a': position['b_a'],
        'l_b': position['l_b'],
        'b_b': position['b_b'],
        'opening_lend_rate_1a': opening_rates['1a'],
        'closing_lend_rate_1a': closing_rates['1a'],
        # ... all rates and prices
        'entry_token_amount_1a': entry_amounts['1a'],
        'exit_token_amount_1a': exit_amounts['1a'],
        # ... all token amounts
        'realised_pnl': realised_pnl,
        'realised_fees': realised_fees,
        'realised_lend_earnings': realised_lend_earnings,
        'realised_borrow_costs': realised_borrow_costs
    }
```

### 6.5 Position Closing

**Function:** `close_position(position_id, close_timestamp, close_reason, close_notes)`
**File:** `analysis/position_service.py` lines 318-387
**Purpose:** Close position and create final rebalance

**Algorithm:**

```python
def close_position(position_id, close_timestamp, close_reason, close_notes):
    # Validate position exists and is active
    position = get_position_by_id(position_id)
    if position['status'] != 'active':
        raise ValueError("Position is not active")

    # Capture final snapshot
    snapshot = capture_rebalance_snapshot(position, close_timestamp)

    # Create final rebalance record
    create_rebalance_record(
        position_id,
        snapshot,
        rebalance_reason=f'position_closed:{close_reason}',
        rebalance_notes=close_notes
    )

    # Update position status
    query = """
    UPDATE positions SET
        status = 'closed',
        close_timestamp = ?,
        close_reason = ?,
        close_notes = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE position_id = ?
    """

    cursor.execute(query, (
        to_datetime_str(close_timestamp),
        close_reason,
        close_notes,
        position_id
    ))

    conn.commit()
```

---

## 7. Statistics Architecture

### 7.1 Design Philosophy

**Principle:** Calculate Once, Store, Use Many

```
┌──────────────┐         ┌──────────────────┐         ┌────────────┐
│ Data Pipeline│ ──────> │ position_        │ ──────> │ Dashboard  │
│ (scheduled)  │         │ statistics       │         │ (instant)  │
└──────────────┘         └──────────────────┘         └────────────┘
                                   │
                         ┌─────────┴─────────┐
                         │ Fallback Path:    │
                         │ On-Demand         │
                         │ Calculation       │
                         │ (1-2 seconds)     │
                         └───────────────────┘
```

**Benefits:**
1. **Performance:** Dashboard loads instantly (no calculations)
2. **Consistency:** Same statistics across multiple views
3. **Auditability:** Historical statistics preserved
4. **Flexibility:** Can recalculate if needed

### 7.2 Statistics Flow

#### Path 1: Pre-Calculated (Primary)

```
1. Data Collection Pipeline runs (every 15 minutes)
   ↓
2. For each active position at current timestamp:
   - Calculate statistics via calculate_position_statistics()
   - Save to position_statistics table
   ↓
3. Dashboard queries position_statistics
   ↓
4. Instant display (< 100ms)
```

**File:** Data pipeline integration (TBD)

#### Path 2: On-Demand (Fallback)

```
1. User selects historical timestamp in dashboard
   ↓
2. Dashboard queries position_statistics for that timestamp
   ↓
3. No statistics found (returns None)
   ↓
4. Shows "📊 Calculate Statistics" button
   ↓
5. User clicks button
   ↓
6. calculate_position_statistics() runs
   ↓
7. Saves result to position_statistics table
   ↓
8. Dashboard reloads, displays statistics
```

**File:** `dashboard_renderer.py` lines 1388-1450

### 7.3 Statistics Caching Logic

**Query Logic:**
```python
# Get most recent statistics at or before timestamp
stats = get_position_statistics(position_id, timestamp)

# Check if exact timestamp match
if stats is not None and stats['timestamp'] != timestamp:
    # Stats from different timestamp - treat as missing
    stats = None

if stats is None:
    # Show "Calculate Statistics" button
```

**Location:** Lines 1388-1396

**Why This Matters:**
- Allows viewing positions with stats from nearby timestamps
- Still enables recalculation for exact timestamps
- Balances convenience and accuracy

### 7.4 Statistics Update Strategy

**When to Update:**
1. ✅ During scheduled data collection (every 15 min)
2. ✅ When user clicks "Calculate Statistics"
3. ❌ Never on position view (read-only)

**What to Store:**
- All metrics from calculate_position_statistics()
- Timestamp when statistics were FOR (viewing time)
- Timestamp when calculation was DONE (audit)

**Retention:**
- Keep all historical statistics
- No automatic cleanup
- Enables historical analysis

---

## 8. Design Principles

**Note:** This section highlights key design principles relevant to the Positions Tab. For the complete list of 12+ system-wide design principles, see [design_notes.md](design_notes.md). For deployment and caching architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

**Core Principles Referenced:**
- #1: Timestamps as Unix Seconds (8.1 below)
- #2: Forward-Looking Rates (8.2 below)
- #3: Position Immutability (8.3 below)
- #4: Event Sourcing Pattern (8.4 below)
- #5: Token Identity via Contracts (8.5 below)
- #6: Weight-Based Position Sizing (8.6 below)
- #12: PnL Calculation: Token Amounts × Price, Not Deployment × Weight (8.6 below)
- #13: Explicit Error Handling (implemented in position_statistics_calculator.py)
- #14: Iterative Liquidity Updates in Portfolio Allocation (see allocator_reference.md)

### 8.1 Timestamps as Unix Seconds

**Rule:** All timestamps stored and used internally as Unix seconds (int)

**Why:**
- Timezone-proof
- Easy arithmetic: `days = (end - start) / 86400`
- Precise time-travel
- No pandas/datetime confusion

**Conversion Points:**
```python
# Database → Python
timestamp_int = to_seconds(timestamp_str)  # "2026-01-19 10:00:00" → 1737281600

# Python → Database
timestamp_str = to_datetime_str(timestamp_int)  # 1737281600 → "2026-01-19 10:00:00"

# Display → User
display_str = datetime.fromtimestamp(timestamp_int).strftime('%b %d, %Y %H:%M')
```

**Location:** `utils/time_helpers.py`

### 8.2 Forward-Looking Rates

**Rule:** Rate at timestamp T applies to period [T, T+1)

```
Timeline:    T₀     T₁     T₂     T₃
Rates:       R₀     R₁     R₂     R₃
             ↓──────↓──────↓──────↓
Periods:     [T₀,T₁) [T₁,T₂) [T₂,T₃)
             uses R₀  uses R₁  uses R₂
```

**Why:** Matches protocol behavior - rates published apply to upcoming period

**Implementation:**
```python
for i in range(len(timestamps) - 1):
    current_time = timestamps[i]
    next_time = timestamps[i + 1]
    period_duration = next_time - current_time

    # Get rate at CURRENT time (applies to this period)
    rate = get_rate_at_timestamp(current_time)

    # Calculate earnings for this period
    earnings += deployment * weight * rate * (period_duration / 365.25 days)
```

**Location:** `position_service.py` lines 609-708, 993-1077

### 8.3 Position Immutability

**Rule:** positions table entry state never changes

**Immutable Fields:**
- `entry_timestamp`
- `entry_lend_rate_1a`, `entry_borrow_rate_2a`, ...
- `entry_price_1a`, `entry_price_2a`, ...
- `entry_collateral_ratio_1a`, `entry_collateral_ratio_2b`
- `entry_liquidation_threshold_1a`, `entry_liquidation_threshold_2b`
- `l_a`, `b_a`, `l_b`, `b_b` (weights)
- `deployment_usd`

**Mutable Fields:**
- `status` ('active' → 'closed')
- `last_rebalance_timestamp`
- `rebalance_count`
- `accumulated_realised_pnl`
- `close_timestamp`, `close_reason`, `close_notes`

**Why:**
- Enables audit trail
- Allows historical reproduction
- Prevents accidental data loss
- Separates "what was" from "what is"

### 8.4 Event Sourcing Pattern

**Rule:** Track changes via append-only history

**Implementation:**
```
positions: Entry state (immutable) + Current metadata (mutable)
           ↓
position_rebalances: Append-only segments
           ↓
position_statistics: Pre-calculated summaries (optional cache)
```

**Benefits:**
1. Can replay any position's history
2. Never lose historical data
3. Clear separation of concerns
4. Supports time-travel queries

**Example:**
```sql
-- Get position state at historical timestamp
SELECT *
FROM position_rebalances
WHERE position_id = 'uuid'
  AND opening_timestamp <= '2026-01-25 14:30:00'
  AND closing_timestamp > '2026-01-25 14:30:00'
```

### 8.5 Token Identity via Contracts

**Rule:** Use `token_contract` for all logic, `token` for display only

**Why:** Symbols can be duplicated
- `USDT` (native) vs `suiUSDT` (wrapped) - different contracts
- Same symbol, different tokens, different rates

**Correct:**
```python
# Logic
rate = rates_df[rates_df['token_contract'] == token_contract]['lend_total_apr']

# Display
st.write(f"Token: {token_symbol}")
```

**Incorrect:**
```python
# ❌ WRONG
rate = rates_df[rates_df['token'] == 'USDT']['lend_total_apr']  # Which USDT?!
```

**Location:** Used throughout `position_service.py` and `dashboard_renderer.py`

### 8.6 Weight-Based Position Sizing

**Rule:** Weights (l_a, b_a, l_b, b_b) are used for **position sizing and display**, NOT for PnL calculations.

**Position Sizing (at entry or rebalance):**
```python
# Convert weight → token amount at current price
token_amount = (weight * deployment_usd) / token_price_usd

# Store the token_amount in database
position['entry_token_amount_1a'] = token_amount
```

**PnL Calculation (after entry):**
```python
# Use stored token amount × current price (NOT weight × deployment)
usd_value = token_amount * current_price_usd
earnings = usd_value * rate * time
```

**Why this separation:**
- **Weights** define the strategy structure (constant ratios)
- **Token amounts** are fixed between rebalances (constant quantities)
- **Prices** change continuously
- **PnL** must use actual token quantities to account for price drift

**Updated:** February 9, 2026 - See Design Notes #12

**Example:**
```python
# Position with l_a=1.45, deployment=$10,000, SUI price=$3.20
sui_amount = (1.45 * 10000) / 3.20 = 4531.25 SUI
usd_value = 4531.25 * 3.20 = $14,500

# If SUI price changes to $3.50
new_sui_amount = (1.45 * 10000) / 3.50 = 4142.86 SUI  # fewer SUI needed
new_usd_value = 4142.86 * 3.50 = $14,500  # same USD value
```

### 8.7 Rebalancing Constraints

**Rule:** Only token2 amounts adjust; token1 and token3 fixed

**Why:** Leveraged loop structure requires this

**Structure:**
```
Token1 (SUI)  ─[Lend]─>  Protocol A  ─[Borrow]─>  Token2 (USDC)
                                                        │
                                                        ↓
Token1 (SUI)  <─[Borrow]─  Protocol B  <─[Lend]─  Token2 (USDC)
```

**Rebalance Action:**
- Token2 borrowed from Protocol A: Increase/decrease borrowing
- Token2 lent to Protocol B: Increase/decrease lending
- Token1 amounts: Unchanged
- Token3 amounts: Unchanged

**Location:** Rebalance logic in `position_service.py`

### 8.8 Liquidation Distance Calculation

**Three Scenarios:**

1. **Entry Liquidation Distance:** Using entry amounts + entry prices
2. **Live Liquidation Distance:** Using entry amounts + current prices
3. **Rebalance Liquidation Distance:** Using rebalanced amounts + current prices

**Purpose:**
- **Entry:** Show what liquidation distance was at creation
- **Live:** Show current risk with existing token amounts
- **Rebalance:** Show what risk WOULD BE if rebalancing now

**Why Matters:** Helps users decide when to rebalance

**Formula:**
```python
# For each borrow leg (2A and 3B)
liq_price = (lent_usd * liq_threshold) / borrowed_tokens

liq_distance = (liq_price - current_price) / current_price * 100
# Positive = safe (price can drop X% before liquidation)
# Negative = danger (price already above liquidation)
```

**Location:** Dashboard display lines 1645-2317

---

## 9. File Locations

### 9.1 Dashboard Rendering

**File:** `/Users/donalmoore/Dev/sui-lending-bot/dashboard/dashboard_renderer.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `render_positions_table_tab()` | 1107-2700 | Main entry point for Positions tab |
| `get_all_position_statistics()` | 993-1041 | Batch load statistics for all positions |
| `get_all_rebalance_history()` | 1044-1106 | Batch load rebalance history |
| `get_position_statistics()` | 958-991 | Load statistics for single position |
| Portfolio summary display | 1500-1527 | Portfolio-level metrics |
| Position summary row | 1641 | Collapsed position display |
| Position detail table | 1645-2317 | Expanded 4-leg table |
| Strategy summary | 2213-2236 | Real + Unreal totals |
| Live position summary | 2320-2356 | Unrealized segment metrics |
| Rebalance action | 2390-2461 | Rebalance button and modal |
| Close action | 2403-2499 | Close button and modal |
| Rebalance history | 2501-2700 | Historical segments display |
| Calculate statistics button | 1388-1450 | On-demand calculation UI |

### 9.2 Position Service (Business Logic)

**File:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_service.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `create_position()` | 115-350 | Create new position from strategy |
| `get_active_positions()` | 408-527 | Get positions filtered by timestamp |
| `get_position_by_id()` | 529-607 | Get single position with type conversion |
| `calculate_position_value()` | 609-708 | Calculate PnL and metrics for segment |
| `calculate_leg_earnings_split()` | 1002-1133 | Calculate base/reward split for one leg |
| `rebalance_position()` | 1124-1176 | Execute rebalance workflow |
| `capture_rebalance_snapshot()` | 1178-1342 | Capture all snapshot data |
| `create_rebalance_record()` | 1351-1674 | Insert rebalance record |
| `close_position()` | 318-387 | Close position and finalize PnL |
| `has_future_rebalances()` | 1867-1904 | Check for time-travel conflicts |
| `get_rebalance_history()` | 1676-1751 | Get all rebalances for position |

### 9.3 Statistics Calculation

**File:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_statistics_calculator.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `calculate_position_statistics()` | 23-269 | Main statistics calculation function |
| Live segment calculation | 79-140 | Calculate unrealized earnings |
| Rebalanced segments | 149-216 | Sum realized earnings from history |
| Totals calculation | 218-226 | Combine live + realized |
| APR calculations | 228-253 | Calculate realized and current APRs |

### 9.4 Database Schema

**File:** `/Users/donalmoore/Dev/sui-lending-bot/data/schema.sql`

| Table | Lines | Purpose |
|-------|-------|---------|
| `rates_snapshot` | 1-85 | Historical rates and prices |
| `token_registry` | 86-165 | Token metadata |
| `positions` | 166-273 | Main position records |
| `position_rebalances` | 275-372 | Rebalance history |
| `position_statistics` | 374-408 | Pre-calculated summaries |

### 9.5 Utilities

**File:** `/Users/donalmoore/Dev/sui-lending-bot/utils/time_helpers.py`

| Function | Purpose |
|----------|---------|
| `to_seconds(value)` | Convert any timestamp to Unix seconds (int) |
| `to_datetime_str(seconds)` | Convert Unix seconds to "YYYY-MM-DD HH:MM:SS" |

---

## 10. Formulas & Calculations

### 10.1 PnL Calculation

**CRITICAL:** All PnL calculations use **actual token amounts × current prices**, NOT `deployment × weight`. This accounts for price drift between rebalances. See Design Notes #12 for full rationale.

**Base Earnings (Corrected Formula - February 9, 2026):**
```
For each leg at each timestamp:
  token_amount = position['entry_token_amount_{leg}']  # Constant between rebalances
  price_usd = rates_snapshot.price_usd[timestamp]      # Changes continuously
  usd_value = token_amount × price_usd                 # Actual current value

Base Lend Earnings = Σ (token_amount_1A × price_1A × lend_base_apr_1A × time_fraction)
                   + Σ (token_amount_2B × price_2B × lend_base_apr_2B × time_fraction)

Base Borrow Costs = Σ (token_amount_2A × price_2A × borrow_base_apr_2A × time_fraction)
                  + Σ (token_amount_3B × price_3B × borrow_base_apr_3B × time_fraction)

Net Base Earnings = Base Lend Earnings - Base Borrow Costs
```

**Why this matters:** If token price increases 10% between rebalances, the old formula (`weight × deployment`) would be off by 10%. Using `token_amount × current_price` captures real position value.

**Reward Earnings:**
```
Reward Earnings = Σ (token_amount_1A × price_1A × lend_reward_apr_1A × time_fraction)
                + Σ (token_amount_2A × price_2A × borrow_reward_apr_2A × time_fraction)
                + Σ (token_amount_2B × price_2B × lend_reward_apr_2B × time_fraction)
                + Σ (token_amount_3B × price_3B × borrow_reward_apr_3B × time_fraction)

Note: Borrow rewards REDUCE costs (negative value)
```

**Total Earnings:**
```
Total Earnings = Net Base Earnings + Reward Earnings
```

**Fees:**
```
Initial Fees = (B_A × deployment × borrow_fee_2A) + (B_B × deployment × borrow_fee_3B)

Delta Fees (on rebalance) = |new_amount - old_amount| × borrow_fee × price
                             (if increasing borrow)
```

**PnL:**
```
PnL = Total Earnings - Total Fees

Current Value = Deployment + PnL
```

### 10.2 APR Calculations

**Realized APR:**
```
Realized APR = (Total PnL / Deployment) × (365 / Days Elapsed)

where:
  Days Elapsed = (Current Timestamp - Entry Timestamp) / 86400
```

**Current APR:**
```
Gross APR = (L_A × lend_rate_1A) + (L_B × lend_rate_2B)
          - (B_A × borrow_rate_2A) - (B_B × borrow_rate_3B)

Fee Cost = (B_A × borrow_fee_2A) + (B_B × borrow_fee_3B)

Current APR = Gross APR - Fee Cost
```

**Net APR (Time-Adjusted):**
```
Net APR = Current APR - (Total Fees × 365 / Days Held)
```

**Portfolio APR (Weighted Average):**
```
Weighted APR = Σ(days_elapsed × deployment × position_apr) / Σ(days_elapsed × deployment)

where for each position:
  days_elapsed = (viewing_timestamp - entry_timestamp) / 86400
```

### 10.3 Token Amount Calculations

**Token Amount from USD:**
```
Token Amount = (Weight × Deployment USD) / Token Price USD

Example:
  L_A = 1.45
  Deployment = $10,000
  SUI Price = $3.20

  SUI Amount = (1.45 × 10000) / 3.20 = 4531.25 SUI
```

**USD Value from Token Amount:**
```
USD Value = Token Amount × Token Price USD
```

**Rebalance Requirement:**
```
Entry Token Amount = (Weight × Deployment) / Entry Price
Current Token Amount = (Weight × Deployment) / Current Price

Rebalance Needed = Current Token Amount - Entry Token Amount

Positive = Need to add tokens (borrow more / lend more)
Negative = Need to remove tokens (repay / withdraw)
```

### 10.4 Liquidation Distance

**Liquidation Price (Borrow Legs Only):**
```
For leg 2A (borrow USDC from Protocol A):
  Lent USD = L_A × Deployment
  Borrowed Tokens = Token Amount at leg 2A
  Liq Threshold = liquidation_threshold_1A

  Liq Price = (Lent USD × Liq Threshold) / Borrowed Tokens

For leg 3B (borrow SUI from Protocol B):
  Lent USD = L_B × Deployment
  Borrowed Tokens = Token Amount at leg 3B
  Liq Threshold = liquidation_threshold_2B

  Liq Price = (Lent USD × Liq Threshold) / Borrowed Tokens
```

**Liquidation Distance:**
```
Liq Distance = ((Liq Price - Current Price) / Current Price) × 100%

Positive % = Safe (price can drop X% before liquidation)
Negative % = Danger (price already above liquidation price)
Zero % = At liquidation threshold
```

**Three Scenarios:**

1. **Entry:** Using entry token amounts + entry prices
2. **Live:** Using entry token amounts + current prices
3. **Rebalance:** Using rebalanced token amounts + current prices

### 10.5 Time Calculations

**Time Fraction:**
```
time_fraction = period_duration_seconds / (365.25 × 86400)

where:
  365.25 days = Average year length (accounts for leap years)
  86400 seconds = 1 day
```

**Days Elapsed:**
```
days_elapsed = (end_timestamp - start_timestamp) / 86400
```

**Annualization:**
```
annualized_value = period_value × (365 / days_elapsed)
```

---

## Summary

The Positions Tab is a comprehensive portfolio management interface that:

1. **Displays** complete position details with 4-leg breakdowns
2. **Calculates** PnL, APRs, and earnings in real-time or pre-calculated
3. **Manages** position lifecycle: deploy → rebalance → close
4. **Tracks** complete history through event sourcing pattern
5. **Supports** time-travel for historical analysis
6. **Optimizes** performance through batch queries and caching
7. **Protects** data integrity through immutable records

The architecture separates concerns:
- **positions:** Immutable entry state + mutable metadata
- **position_rebalances:** Append-only historical segments
- **position_statistics:** Optional pre-calculated cache

All calculations follow consistent principles:
- Unix timestamps (int) for time
- Forward-looking rates
- Weight-based sizing (for position structure, NOT for PnL calculation)
- Token amounts × prices (for PnL calculation to account for price drift)
- Token contracts for identity
- Event sourcing for auditability

This design enables powerful features:
- Reproduce any historical state
- Calculate statistics at any timestamp
- Time-travel safely with protection
- Scale to many positions efficiently
- Audit complete position history

---

**Document Status:** Complete
**Version:** 1.1
**Date:** February 9-10, 2026
**Last Updated:** February 10, 2026 - Added cross-references to design_notes.md, ARCHITECTURE.md, and allocator_reference.md
**Next Steps:** Use this as basis for README and user documentation
