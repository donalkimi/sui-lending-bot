# Documentation Diagrams & Flow Charts - Implementation Plan

**Created:** 2026-02-16
**Status:** Ready for Implementation
**Goal:** Add visual diagrams and flow charts across documentation to improve understanding

---

## Overview

This plan adds 10 new visual diagrams/flow charts to the documentation, following the style of the "Complete Data Flow" chart that you found useful in MULTI_STRAT_PLAN.md.

---

## Diagram Inventory

### ✅ Already Exists (Good Examples)

1. **Complete Data Flow** (4-phase diagram)
   - Location: `docs/ARCHITECTURE.md` (lines 87-148)
   - Also in: `MULTI_STRAT_PLAN.md`
   - Style: ASCII box diagram with vertical flow
   - What it shows: Strategy discovery → Position deployment pipeline

---

## Diagrams to Add

### GROUP 1: Core System Flows (Add to ARCHITECTURE.md)

#### 1. **Rebalancing Flow**
**Document:** `docs/ARCHITECTURE.md`
**Section:** New section after "Complete Data Flow" (~line 165)
**Section Title:** "## Rebalancing Flow: Detection → Manual Rebalance → Segment Creation"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: REBALANCE DETECTION (Automatic)                    │
└─────────────────────────────────────────────────────────────┘
   Position Expander Renders
   ├─ Calculates liquidation distance
   ├─ Calculates price drift per token
   ├─ Checks against threshold (15% default)
   └─ Displays "Rebal Req'd?" column with drift %

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: USER DECISION (Manual)                             │
└─────────────────────────────────────────────────────────────┘
   User reviews position
   │
   ├─ Sees rebalance indicator (Yes +6.7%)
   ├─ Sees liquidation distance (17.1% → getting close)
   └─ Clicks "⚖️ Rebalance" button
      └─ Triggers rebalance modal

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: REBALANCE EXECUTION (Database Write)               │
└─────────────────────────────────────────────────────────────┘
   position_service.rebalance_position()
   │
   ├─ INSERT INTO position_rebalances
   │  ├─ sequence_number = next in sequence
   │  ├─ segment_start_timestamp = live_timestamp
   │  ├─ closing_* = rates/prices at rebalance time
   │  ├─ opening_* = NEW rates/prices after rebalance
   │  └─ realized_pnl = PnL for closed segment
   │
   └─ UPDATE positions SET
      ├─ entry_* = NEW rates/prices (reset entry state)
      └─ updated_at = now

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: SEGMENT CREATION (Historical Tracking)             │
└─────────────────────────────────────────────────────────────┘
   Position now has segments
   │
   ├─ Segment 1: entry → rebalance_1 (closed, PnL realized)
   ├─ Segment 2: rebalance_1 → rebalance_2 (closed, PnL realized)
   └─ Live Segment: rebalance_N → now (active, PnL unrealized)
```

**Key Points to Explain:**
- Detection is automatic and visual only
- Execution is manual (user-initiated)
- Each rebalance creates a historical segment
- Position entry state is reset to "new normal"

---

#### 2. **Time-Travel Flow**
**Document:** `docs/ARCHITECTURE.md`
**Section:** New section after "Caching Architecture Overview" (~line 82)
**Section Title:** "## Time-Travel Flow: Timestamp Selection → Data Loading"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: AVAILABLE TIMESTAMPS (Cache Index)                 │
└─────────────────────────────────────────────────────────────┘
   Dashboard loads
   ├─ get_available_timestamps()
   │  └─ SELECT DISTINCT timestamp FROM rates_snapshot
   └─ Returns: [ts1, ts2, ts3, ...] (sorted desc)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: USER SELECTION (Timestamp Picker)                  │
└─────────────────────────────────────────────────────────────┘
   User interacts with dropdown
   │
   ├─ Default: Latest timestamp (most recent)
   ├─ Options: All historical snapshots
   └─ Selects: 2026-02-14 15:00:00
      └─ Converts to Unix seconds: 1739548800

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: DATA LOADING (Cache Lookup)                        │
└─────────────────────────────────────────────────────────────┘
   load_historical_snapshot(timestamp_seconds)
   │
   ├─ SELECT * FROM rates_snapshot
   │  WHERE timestamp = 1739548800
   │
   ├─ Pivot into 8 DataFrames
   │  ├─ lend_rates (Token × Protocol matrix)
   │  ├─ borrow_rates
   │  ├─ collateral_ratios
   │  ├─ prices
   │  ├─ lend_rewards
   │  ├─ borrow_rewards
   │  ├─ available_borrow
   │  └─ borrow_fees
   │
   └─ Returns: (df1, df2, ..., df8, timestamp)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: RENDERING (Dashboard Display)                      │
└─────────────────────────────────────────────────────────────┘
   Dashboard renders with selected timestamp as "now"
   │
   ├─ All strategies use rates from selected timestamp
   ├─ All positions calculate PnL up to selected timestamp
   ├─ All APRs based on selected timestamp's rates
   └─ User can "time travel" to any cached snapshot
```

**Key Points to Explain:**
- Selected timestamp IS "now" (Design Principle #1)
- All queries use `WHERE timestamp <= selected_timestamp`
- Dashboard never calls protocol APIs directly
- Time travel is instant (cache lookup)

---

#### 3. **Database Schema Relationships (ERD)**
**Document:** `docs/ARCHITECTURE.md`
**Section:** New section after "Database Relationships" (~line 1401)
**Section Title:** "## Database Schema Visual (ERD)"

**What to Show:**
```
┌─────────────────────────────────────────────────────────┐
│ rates_snapshot (Time-series cache)                      │
├─────────────────────────────────────────────────────────┤
│ PK: (timestamp, protocol, token_contract)               │
│ - timestamp TIMESTAMP                                    │
│ - protocol VARCHAR(50)                                   │
│ - token VARCHAR(50)                                      │
│ - token_contract TEXT ──────┐                           │
│ - lend_total_apr DECIMAL     │                           │
│ - borrow_total_apr DECIMAL   │                           │
│ - price_usd DECIMAL          │                           │
│ - available_borrow_usd       │                           │
│ - ...                        │                           │
└──────────────────────────────┼───────────────────────────┘
                               │
                               │ FK
                               ▼
┌─────────────────────────────────────────────────────────┐
│ token_registry (Metadata cache)                         │
├─────────────────────────────────────────────────────────┤
│ PK: token_contract                                       │
│ - token_contract TEXT                                    │
│ - symbol TEXT                                            │
│ - pyth_id TEXT                                           │
│ - coingecko_id TEXT                                      │
│ - seen_on_navi BOOLEAN                                   │
│ - first_seen TIMESTAMP                                   │
│ - last_seen TIMESTAMP                                    │
└─────────────────────────────────────────────────────────┘
       ▲
       │ FK
       │
┌──────┴──────────────────────────────────────────────────┐
│ positions (Position tracking)                           │
├─────────────────────────────────────────────────────────┤
│ PK: position_id                                          │
│ - position_id TEXT (UUID)                                │
│ - status TEXT ('active'/'closed'/'liquidated')           │
│ - entry_timestamp TIMESTAMP ────┐                        │
│ - token1_contract TEXT ──────┐  │                        │
│ - token2_contract TEXT ───┐  │  │                        │
│ - token3_contract TEXT ──┐│  │  │                        │
│ - deployment_usd DECIMAL ││  │  │                        │
│ - L_A, B_A, L_B, B_B     ││  │  │                        │
│ - entry_lend_rate_1A     ││  │  │                        │
│ - entry_price_1A         ││  │  │                        │
│ - ...                    ││  │  │                        │
└──────────────────────────┼┼──┼──┼────────────────────────┘
                           ││  │  │
                           ││  │  └─> Used to lookup
                           ││  │      rates_snapshot at
                           ││  │      entry_timestamp
                           ││  │
                           ││  └───> FK to token_registry
                           │└──────> FK to token_registry
                           └───────> FK to token_registry
       │
       │ parent
       ▼
┌─────────────────────────────────────────────────────────┐
│ position_rebalances (Segment history)                   │
├─────────────────────────────────────────────────────────┤
│ PK: (position_id, sequence_number)                       │
│ - position_id TEXT ──┘ (FK to positions)                │
│ - sequence_number INT                                    │
│ - segment_start_timestamp TIMESTAMP                      │
│ - segment_end_timestamp TIMESTAMP                        │
│ - closing_lend_rate_1A DECIMAL                           │
│ - opening_lend_rate_1A DECIMAL                           │
│ - realized_pnl DECIMAL                                   │
│ - ...                                                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ portfolios (Portfolio metadata)                         │
├─────────────────────────────────────────────────────────┤
│ PK: portfolio_id                                         │
│ - portfolio_id TEXT (UUID)                               │
│ - portfolio_name TEXT                                    │
│ - created_at TIMESTAMP                                   │
│ - updated_at TIMESTAMP                                   │
└─────────────────────────────────────────────────────────┘
       ▲
       │ FK
       │
┌──────┴──────────────────────────────────────────────────┐
│ position_statistics (Computed metrics cache)            │
├─────────────────────────────────────────────────────────┤
│ PK: (position_id, timestamp_seconds)                     │
│ - position_id TEXT ──┘ (FK to positions)                │
│ - timestamp_seconds INT                                  │
│ - total_pnl DECIMAL                                      │
│ - total_earnings DECIMAL                                 │
│ - realized_apr DECIMAL                                   │
│ - current_apr DECIMAL                                    │
│ - holding_days DECIMAL                                   │
│ - ...                                                    │
└─────────────────────────────────────────────────────────┘
```

**Key Points to Explain:**
- rates_snapshot = Tier 1 cache (protocol data)
- token_registry = Metadata cache
- positions = Event sourcing (immutable entry state)
- position_rebalances = Segment history
- position_statistics = Computed cache (pre-calculated metrics)
- portfolios = Grouping metadata

---

### GROUP 2: Position & Portfolio Flows (Add to Positions_and_Portfolio_reference.md)

#### 4. **PnL Calculation Flow**
**Document:** `docs/Positions_and_Portfolio_reference.md`
**Section:** New section after "Position Performance Calculations" (~line 1092)
**Section Title:** "## PnL Calculation Flow: Token Amounts × Prices Across Segments"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: LOAD POSITION METADATA (Entry State)                │
└─────────────────────────────────────────────────────────────┘
   Get position from positions table
   ├─ entry_timestamp
   ├─ deployment_usd
   ├─ L_A, B_A, L_B, B_B (multipliers)
   ├─ token1, token2, token3
   └─ protocol_A, protocol_B

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 2: LOAD HISTORICAL RATES (Time-series)                 │
└─────────────────────────────────────────────────────────────┘
   SELECT DISTINCT timestamp FROM rates_snapshot
   WHERE timestamp >= entry_timestamp
     AND timestamp <= live_timestamp
   ORDER BY timestamp
   │
   └─ Returns: [ts1, ts2, ts3, ..., tsN]
      └─ Defines time periods: [ts1→ts2], [ts2→ts3], ..., [tsN-1→tsN]

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 3: CALCULATE EARNINGS PER PERIOD (Lend legs)           │
└─────────────────────────────────────────────────────────────┘
   For each time period [T, T+1):
   │
   ├─ period_years = (T+1 - T) / seconds_per_year
   │
   ├─ Get rates at timestamp T:
   │  ├─ lend_rate_1A = rates_snapshot[T, protocol_A, token1]
   │  └─ lend_rate_2B = rates_snapshot[T, protocol_B, token2]
   │
   └─ Calculate earnings:
      ├─ lend_earnings_1A = deployment × L_A × lend_rate_1A × period_years
      ├─ lend_earnings_2B = deployment × L_B × lend_rate_2B × period_years
      └─ period_lend_earnings = lend_earnings_1A + lend_earnings_2B

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 4: CALCULATE COSTS PER PERIOD (Borrow legs)            │
└─────────────────────────────────────────────────────────────┘
   For each time period [T, T+1):
   │
   ├─ Get rates at timestamp T:
   │  ├─ borrow_rate_2A = rates_snapshot[T, protocol_A, token2]
   │  └─ borrow_rate_3B = rates_snapshot[T, protocol_B, token3]
   │
   └─ Calculate costs:
      ├─ borrow_costs_2A = deployment × B_A × borrow_rate_2A × period_years
      ├─ borrow_costs_3B = deployment × B_B × borrow_rate_3B × period_years
      └─ period_borrow_costs = borrow_costs_2A + borrow_costs_3B

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 5: CALCULATE ONE-TIME FEES (Entry only)                │
└─────────────────────────────────────────────────────────────┘
   Get fees at entry_timestamp:
   ├─ borrow_fee_2A = rates_snapshot[entry_timestamp, protocol_A, token2]
   ├─ borrow_fee_3B = rates_snapshot[entry_timestamp, protocol_B, token3]
   │
   └─ Calculate one-time fees:
      ├─ fee_2A = deployment × B_A × borrow_fee_2A
      ├─ fee_3B = deployment × B_B × borrow_fee_3B
      └─ total_fees = fee_2A + fee_3B

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 6: SUM ACROSS ALL PERIODS (Net PnL)                    │
└─────────────────────────────────────────────────────────────┘
   Aggregate all periods:
   ├─ total_lend_earnings = sum(period_lend_earnings for all periods)
   ├─ total_borrow_costs = sum(period_borrow_costs for all periods)
   │
   └─ Calculate net PnL:
      ├─ net_earnings = total_lend_earnings - total_borrow_costs - total_fees
      ├─ current_value = deployment_usd + net_earnings
      └─ total_pnl = current_value - deployment_usd
         └─ (Same as net_earnings)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 7: CALCULATE REALIZED APR (Annualized)                 │
└─────────────────────────────────────────────────────────────┘
   Annualize the earnings:
   ├─ holding_days = (live_timestamp - entry_timestamp) / 86400
   ├─ annual_net_earnings = net_earnings × (365 / holding_days)
   │
   └─ realized_apr = annual_net_earnings / deployment_usd
      └─ Example: $102.34 over 30 days → 12.45% APR
```

**Key Points to Explain:**
- PnL calculated from historical time-series (not just entry → live)
- Each period uses actual rates from that time
- Fees are one-time (charged at entry only)
- APR is annualized actual performance

---

#### 5. **Batch Rendering Pipeline**
**Document:** `docs/Positions_and_Portfolio_reference.md`
**Section:** New section in "Batch Rendering System" (~line 192)
**Section Title:** "## Batch Rendering Pipeline: 3 Queries for N Positions"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: render_positions_batch([id1, id2, ..., idN])         │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: INFRASTRUCTURE SETUP (Once)                         │
└─────────────────────────────────────────────────────────────┘
   Create database connections
   ├─ conn = get_db_connection()
   ├─ engine = get_db_engine()
   └─ service = PositionService(conn)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: BATCH DATA LOADING (3 Queries Total)               │
└─────────────────────────────────────────────────────────────┘
   Query 1: Load ALL position statistics
   ├─ SELECT * FROM position_statistics
   │  WHERE position_id IN (id1, id2, ..., idN)
   │    AND timestamp_seconds = ?
   └─ Returns: dict[position_id] -> stats_dict
      └─ Example: {id1: {pnl: 245.32, apr: 0.0842, ...}, ...}

   Query 2: Load ALL rebalance history
   ├─ SELECT * FROM position_rebalances
   │  WHERE position_id IN (id1, id2, ..., idN)
   │  ORDER BY position_id, sequence_number
   └─ Returns: dict[position_id] -> list[rebalance_dicts]
      └─ Example: {id1: [{seq: 1, ...}, {seq: 2, ...}], ...}

   Query 3: Load rates snapshot ONCE
   ├─ SELECT * FROM rates_snapshot
   │  WHERE timestamp = ?
   └─ Returns: DataFrame with all rates
      └─ Used for ALL positions (shared)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: BUILD SHARED LOOKUPS (O(1) Access)                 │
└─────────────────────────────────────────────────────────────┘
   Build rate_lookup dict
   ├─ rate_lookup[(protocol, token)] = {lend, borrow, fee, price}
   └─ O(1) lookups for all positions

   Build oracle_prices dict
   ├─ oracle_prices[token] = price_usd
   └─ O(1) lookups for all positions

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: RENDER LOOP (N Iterations)                         │
└─────────────────────────────────────────────────────────────┘
   For each position_id in [id1, id2, ..., idN]:
   │
   ├─ position = service.get_position_by_id(position_id)
   ├─ stats = all_stats[position_id]  ← Pre-loaded (O(1))
   ├─ rebalances = all_rebalances[position_id]  ← Pre-loaded (O(1))
   │
   └─ render_position_expander(
      position, stats, rebalances,
      rate_lookup, oracle_prices,  ← Shared lookups
      ...
   )

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: N Position Expanders Rendered in Dashboard          │
└─────────────────────────────────────────────────────────────┘

PERFORMANCE COMPARISON:
┌─────────────────────────────────────────────────────────────┐
│ Naive Approach (No Batching):                               │
│ - Queries: 3 × N (3 queries per position)                   │
│ - 10 positions = 30 queries (~3 seconds)                    │
│ - 20 positions = 60 queries (~6 seconds)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Batch Approach (This Implementation):                       │
│ - Queries: 3 total (regardless of N)                        │
│ - 10 positions = 3 queries (~400ms)                         │
│ - 20 positions = 3 queries (~600ms)                         │
│ - Speedup: ~N × faster                                      │
└─────────────────────────────────────────────────────────────┘
```

**Key Points to Explain:**
- Batch loading = 3 queries for N positions (not 3×N)
- Shared lookups = O(1) access (not O(N) DataFrame filtering)
- Performance scales linearly with slight overhead (not N×)
- Same pattern used for Positions tab, Portfolio2 tab

---

#### 6. **Position Lifecycle State Machine**
**Document:** `docs/Positions_and_Portfolio_reference.md`
**Section:** New section after "System Overview" (~line 89)
**Section Title:** "## Position Lifecycle: State Machine"

**What to Show:**
```
                    ┌──────────────────┐
                    │ STRATEGY         │
                    │ DISCOVERY        │
                    │ (Analysis Only)  │
                    └────────┬─────────┘
                             │
                             │ User clicks "Deploy"
                             ▼
                    ┌──────────────────┐
                    │   PENDING        │
                    │                  │
                    │ - Deployment     │
                    │   modal shown    │
                    │ - User reviews   │
                    │ - Not in DB yet  │
                    └────────┬─────────┘
                             │
                             │ User confirms
                             ▼
                    ┌──────────────────┐
         ┌──────────┤   ACTIVE         │◄──────────┐
         │          │                  │           │
         │          │ - In database    │           │
         │          │ - Earning yield  │           │
         │          │ - PnL tracking   │           │
         │          │ - status='active'│           │
         │          └────────┬─────────┘           │
         │                   │                     │
         │                   │ User clicks         │ User clicks
         │                   │ "Rebalance"         │ "Cancel Rebalance"
         │                   ▼                     │
         │          ┌──────────────────┐           │
         │          │  REBALANCING     │───────────┘
         │          │                  │
         │          │ - Rebalance      │
         │          │   modal shown    │
         │          │ - User reviews   │
         │          │ - Still active   │
         │          └────────┬─────────┘
         │                   │
         │                   │ User confirms rebalance
         │                   ▼
         │          ┌──────────────────┐
         │          │   ACTIVE         │
         │          │ (Rebalanced)     │
         │          │                  │
         │          │ - New segment    │
         │          │ - Entry state    │
         │          │   reset          │
         │          │ - Old segment    │
         │          │   finalized      │
         │          └────────┬─────────┘
         │                   │
         │                   │ User clicks "Close"
         │                   ▼
         │          ┌──────────────────┐
         └─────────►│  CLOSED          │
                    │                  │
                    │ - No longer      │
                    │   earning        │
                    │ - Final PnL      │
                    │   calculated     │
                    │ - status='closed'│
                    └────────┬─────────┘
                             │
                             │ Liquidation event
                             │ (monitoring system)
                             ▼
                    ┌──────────────────┐
                    │  LIQUIDATED      │
                    │                  │
                    │ - Capital lost   │
                    │ - status=        │
                    │   'liquidated'   │
                    └──────────────────┘

STATE TRANSITIONS:
═══════════════════════════════════════════════════════════════
PENDING → ACTIVE:
- Trigger: User confirms deployment modal
- Database: INSERT INTO positions (status='active')
- Creates: position_id (UUID)

ACTIVE → REBALANCING:
- Trigger: User clicks "Rebalance" button
- Database: No change (UI state only)
- Shows: Rebalance confirmation modal

REBALANCING → ACTIVE:
- Trigger: User confirms rebalance modal
- Database: INSERT INTO position_rebalances
- Database: UPDATE positions SET entry_* = new_rates
- Creates: New segment in history

REBALANCING → ACTIVE (Cancel):
- Trigger: User clicks "Cancel"
- Database: No change
- Returns: To normal ACTIVE rendering

ACTIVE → CLOSED:
- Trigger: User clicks "Close" button
- Database: UPDATE positions SET status='closed', close_timestamp=now
- Calculates: Final realized PnL
- Shows: In "Closed Positions" section

ACTIVE → LIQUIDATED:
- Trigger: Monitoring system detects liquidation
- Database: UPDATE positions SET status='liquidated', close_reason='liquidation'
- Alert: Slack notification sent
- Shows: In "Liquidated Positions" section
```

**Key Points to Explain:**
- PENDING is UI-only (not in database)
- ACTIVE is the primary earning state
- REBALANCING is UI-only (shows modal)
- Rebalance creates new segment, resets entry state
- CLOSED and LIQUIDATED are terminal states

---

### GROUP 3: Code Architecture Patterns (Add to new doc or ARCHITECTURE.md)

#### 7. **Portfolio Allocation Flow**
**Document:** `docs/ARCHITECTURE.md` (OR create new `docs/AllocatorPlan.md` if exists)
**Section:** In existing "Phase 5: Portfolio Allocation" (~line 397)
**Section Title:** "## Portfolio Allocation Flow: Iterative Liquidity Updates"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: Strategies DataFrame + Portfolio Constraints          │
└─────────────────────────────────────────────────────────────┘
   Example: 100 strategies, $100k portfolio size
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: PREPARE STRATEGIES (Filtering & Ranking)            │
└─────────────────────────────────────────────────────────────┘
   Filter strategies
   ├─ confidence_threshold (e.g., 5+ data points)
   └─ Remove invalid strategies

   Calculate blended APR
   ├─ Weights: 40% net_apr, 30% apr5, 20% apr30, 10% apr90
   └─ Apply stablecoin preference penalties

   Sort by adjusted APR (descending)
   └─ Best strategies first

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 2: INITIALIZE LIQUIDITY MATRIX (Token × Protocol)      │
└─────────────────────────────────────────────────────────────┘
   Build available_borrow matrix:

            Navi      Suilend   Pebble    AlphaFi
   USDC     500000    800000    1000000   300000
   WAL      150000    200000    100000    50000
   DEEP     75000     100000    50000     25000

   Source: available_borrow_2a, available_borrow_3b from strategies

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ STEP 3: GREEDY ALLOCATION LOOP (With Iterative Updates)     │
└─────────────────────────────────────────────────────────────┘
   For each strategy in ranked order:
   │
   ├─ GET CURRENT MAX SIZE (may have changed)
   │  ├─ max_size = min(
   │  │     available_borrow[token2][protocol_a] / b_a,
   │  │     available_borrow[token3][protocol_b] / b_b
   │  │   )
   │  └─ If max_size <= 0: Skip strategy (no liquidity)
   │
   ├─ CALCULATE MAX ALLOCATION
   │  ├─ Remaining capital: capital_left
   │  ├─ Token exposure limits: max_token2, max_token3
   │  ├─ Protocol exposure limits: max_protocol_a, max_protocol_b
   │  └─ allocation = min(capital_left, max_token2, max_token3,
   │                       max_protocol_a, max_protocol_b, max_size)
   │
   ├─ ALLOCATE TO STRATEGY
   │  ├─ portfolio.append(strategy, allocation)
   │  ├─ capital_left -= allocation
   │  ├─ Update token exposures
   │  └─ Update protocol exposures
   │
   ├─ UPDATE LIQUIDITY MATRIX ◄── KEY INNOVATION
   │  ├─ borrow_2A_usd = allocation × strategy['borrow_weight_2A']
   │  ├─ borrow_3B_usd = allocation × strategy['borrow_weight_3B']
   │  │
   │  ├─ available_borrow[token2][protocol_a] -= borrow_2A_usd
   │  ├─ available_borrow[token3][protocol_b] -= borrow_3B_usd
   │  └─ Clamp negatives to 0
   │
   └─ RECALCULATE MAX SIZES (for remaining strategies)
      └─ Only strategies with index > current
         └─ Avoids redundant recalculation

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Portfolio + Debug Info                              │
└─────────────────────────────────────────────────────────────┘
   Returns:
   ├─ selected_strategies: List of (strategy, allocation) pairs
   ├─ total_allocated: Sum of allocations
   ├─ capital_used: Total capital deployed
   │
   └─ debug_info:
      ├─ Initial available_borrow matrix
      ├─ Final available_borrow matrix
      ├─ Constraints applied per strategy
      └─ Allocation reasoning

EXAMPLE IMPACT:
═══════════════════════════════════════════════════════════════
Scenario: 3 strategies borrowing WAL from Pebble (available: $100k)

WITHOUT iterative updates:
- Strategy 1: Allocate $100k (borrows $100k WAL)
- Strategy 2: Allocate $100k (borrows $100k WAL) ← OVER-BORROW
- Strategy 3: Allocate $100k (borrows $100k WAL) ← OVER-BORROW
- Total borrowed: $300k (200k over limit!) ❌

WITH iterative updates:
- Strategy 1: Allocate $100k (borrows $100k WAL)
  → available_borrow[WAL][Pebble] = 100k - 100k = $0
- Strategy 2: max_size = $0 / b_a = $0 → SKIP ✅
- Strategy 3: max_size = $0 / b_a = $0 → SKIP ✅
- Total borrowed: $100k (respects limit!) ✅
```

**Key Points to Explain:**
- Iterative updates prevent over-borrowing
- Matrix tracks liquidity consumption in real-time
- Greedy algorithm with constraints
- Debug info for troubleshooting

---

#### 8. **Calculator Registry Pattern**
**Document:** `docs/ARCHITECTURE.md` (OR new section in ARCHITECTURE.md)
**Section:** New section after "Phase 4: Strategy Analysis" (~line 333)
**Section Title:** "## Strategy Calculator Registry: Type → Calculator Class Mapping"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ REGISTRY INITIALIZATION (Module Load Time)                   │
└─────────────────────────────────────────────────────────────┘
   analysis/strategy_calculators.py
   │
   └─ STRATEGY_CALCULATORS = {
      'stablecoin': StablecoinStrategyCalculator,
      'noloop': NoLoopStrategyCalculator,
      'recursive_lending': RecursiveLendingStrategyCalculator,
      'funding_rate_arb': FundingRateArbCalculator,
      ...
   }

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ USAGE: RateAnalyzer.analyze_all_combinations()              │
└─────────────────────────────────────────────────────────────┘
   For each strategy_type:
   │
   ├─ Get calculator class from registry:
   │  calculator_class = STRATEGY_CALCULATORS.get(strategy_type)
   │  if not calculator_class:
   │      raise ValueError(f"Unknown strategy type: {strategy_type}")
   │
   ├─ Instantiate calculator:
   │  calculator = calculator_class(merged_data, timestamp)
   │
   └─ Call analyze_strategy():
      result = calculator.analyze_strategy(
         token1, token2, token3,
         protocol_A, protocol_B,
         liquidation_distance
      )

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ CALCULATOR INTERFACE (Base Class)                            │
└─────────────────────────────────────────────────────────────┘
   class StrategyCalculatorBase(ABC):
      @abstractmethod
      def analyze_strategy(self, token1, token2, token3,
                          protocol_A, protocol_B, liq_dist):
         """
         Calculate position sizes, rates, APR, max_size.

         Returns:
            dict with keys: L_A, B_A, L_B, B_B, net_apr,
                           apr5, apr30, apr90, max_size, valid
         """
         pass

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ CONCRETE CALCULATORS (Strategy-Specific)                     │
└─────────────────────────────────────────────────────────────┘
   RecursiveLendingStrategyCalculator:
      ├─ analyze_strategy()
      │  ├─ calculate_positions() [Geometric series]
      │  │  └─ L_A = 1 / (1 - r_A × r_B)
      │  ├─ calculate_net_apr() [4-leg APR]
      │  │  └─ earnings - costs - fees
      │  └─ calculate_max_size() [Liquidity constraint]
      │     └─ min(avail_2A / B_A, avail_3B / B_B)

   NoLoopStrategyCalculator:
      ├─ analyze_strategy()
      │  ├─ calculate_positions() [3-leg, no recursion]
      │  │  └─ L_A = 1.0, B_A = r_A, L_B = r_A, B_B = None
      │  ├─ calculate_net_apr() [3-leg APR]
      │  └─ calculate_max_size() [Liquidity constraint]

   StablecoinStrategyCalculator:
      ├─ analyze_strategy()
      │  ├─ calculate_positions() [1-leg, pure lending]
      │  │  └─ L_A = 1.0, B_A = 0, L_B = 0, B_B = None
      │  ├─ calculate_net_apr() [Single lend APR]
      │  └─ calculate_max_size() [Supply limit]

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ EXTENSION: ADDING NEW STRATEGY TYPE                          │
└─────────────────────────────────────────────────────────────┘
   1. Create new calculator class:
      class MyNewStrategyCalculator(StrategyCalculatorBase):
          def analyze_strategy(self, ...):
              # Custom logic here
              return {...}

   2. Register in STRATEGY_CALCULATORS:
      STRATEGY_CALCULATORS['my_new_strategy'] = MyNewStrategyCalculator

   3. Add generation method in RateAnalyzer:
      def _generate_my_new_strategies(self):
          for ...:
              yield self._build_strategy_row('my_new_strategy', ...)

   4. Call in analyze_all_combinations():
      all_strategies.extend(self._generate_my_new_strategies())

   → NO CHANGES to other parts of codebase
   → Registry automatically routes to new calculator
```

**Key Points to Explain:**
- Registry pattern = plugin architecture
- Each strategy type has dedicated calculator
- Common interface (StrategyCalculatorBase)
- Easy to extend (add new type without modifying existing code)

---

#### 9. **Renderer Registry Pattern**
**Document:** `docs/Positions_and_Portfolio_reference.md`
**Section:** New section in "Architecture" (~line 114)
**Section Title:** "## Renderer Registry: Strategy Type → Renderer Class Mapping"

**What to Show:**
```
┌─────────────────────────────────────────────────────────────┐
│ REGISTRY INITIALIZATION (Module Load Time)                   │
└─────────────────────────────────────────────────────────────┘
   dashboard/strategy_renderers.py
   │
   └─ STRATEGY_RENDERERS = {
      'recursive_lending': RecursiveLendingRenderer,
      'noloop': NoLoopRenderer,
      'stablecoin': StablecoinRenderer,
      'funding_rate_arb': FundingRateArbRenderer,
      ...
   }

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ USAGE: render_position_expander()                           │
└─────────────────────────────────────────────────────────────┘
   Get renderer for strategy type:
   │
   ├─ strategy_type = position['strategy_type']  # e.g., 'recursive_lending'
   │
   ├─ Get renderer class from registry:
   │  renderer_class = STRATEGY_RENDERERS.get(strategy_type)
   │  if not renderer_class:
   │      renderer_class = RecursiveLendingRenderer  # Fallback
   │
   ├─ Instantiate renderer:
   │  renderer = renderer_class()
   │
   └─ Call render methods:
      ├─ renderer.render_detail_table(position, rebalance, ...)
      ├─ renderer.get_metrics_layout()
      └─ renderer.build_token_flow_string(position)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ RENDERER INTERFACE (Base Class)                              │
└─────────────────────────────────────────────────────────────┘
   class StrategyRendererBase(ABC):
      @abstractmethod
      def render_detail_table(self, position, rebalance, ...):
         """
         Render strategy-specific detail table (4-leg, 3-leg, etc.)

         Displays: All legs with rates, prices, amounts, etc.
         """
         pass

      @abstractmethod
      def get_metrics_layout(self):
         """
         Return list of metric definitions for summary.

         Returns: [(label, key, format), ...]
         """
         pass

      @abstractmethod
      def build_token_flow_string(self, position):
         """
         Build human-readable token flow string.

         Returns: "USDC → DEEP → USDC"
         """
         pass

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ CONCRETE RENDERERS (Strategy-Specific)                       │
└─────────────────────────────────────────────────────────────┘
   RecursiveLendingRenderer:
      ├─ render_detail_table()
      │  ├─ 4 rows: Lend1A, Borrow2A, Lend2B, Borrow3B
      │  ├─ Shows: rates, prices, amounts, liq prices
      │  └─ Highlights: rebalance requirements
      │
      ├─ get_metrics_layout()
      │  └─ Returns: [
      │        ('Total PnL', 'total_pnl', '$'),
      │        ('Total Earnings', 'total_earnings', '$'),
      │        ...
      │     ]
      │
      └─ build_token_flow_string()
         └─ Returns: "USDC → DEEP → USDC"

   NoLoopRenderer:
      ├─ render_detail_table()
      │  ├─ 3 rows: Lend1A, Borrow2A, Lend2B
      │  └─ No B_B leg (token3 is NULL)
      │
      ├─ get_metrics_layout()
      │  └─ Same as recursive (no B_B fees)
      │
      └─ build_token_flow_string()
         └─ Returns: "USDC → DEEP"

   StablecoinRenderer:
      ├─ render_detail_table()
      │  ├─ 1 row: Lend1A only
      │  └─ No borrow legs
      │
      ├─ get_metrics_layout()
      │  └─ Returns: [
      │        ('Total Earnings', 'total_earnings', '$'),
      │        ('Base Earnings', 'base_earnings', '$'),
      │        ('Reward Earnings', 'reward_earnings', '$')
      │     ]  # No PnL (no costs/fees)
      │
      └─ build_token_flow_string()
         └─ Returns: "USDC (Lend Only)"

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ EXTENSION: ADDING NEW RENDERER                               │
└─────────────────────────────────────────────────────────────┘
   1. Create new renderer class:
      class MyNewStrategyRenderer(StrategyRendererBase):
          def render_detail_table(self, position, ...):
              # Custom table layout
              ...

          def get_metrics_layout(self):
              return [('Metric1', 'key1', '$'), ...]

          def build_token_flow_string(self, position):
              return f"{position['token1']} → ..."

   2. Register in STRATEGY_RENDERERS:
      STRATEGY_RENDERERS['my_new_strategy'] = MyNewStrategyRenderer

   → NO CHANGES to render_position_expander()
   → Registry automatically routes to new renderer
   → All tabs use new renderer automatically
```

**Key Points to Explain:**
- Registry pattern = plugin architecture
- Each strategy type has dedicated renderer
- Common interface (StrategyRendererBase)
- Positions are rendered based on strategy_type field
- Easy to extend (add new renderer without modifying existing code)

---

## Implementation Order

Recommended order for adding these diagrams:

### Phase 1: Core System (ARCHITECTURE.md)
1. Time-Travel Flow (explains fundamental caching concept)
2. Database Schema Relationships (visual ERD)
3. Rebalancing Flow (common user operation)
4. Portfolio Allocation Flow (complex but important)
5. Calculator Registry Pattern (code architecture)

### Phase 2: Position Details (Positions_and_Portfolio_reference.md)
6. PnL Calculation Flow (explains core metric)
7. Batch Rendering Pipeline (performance optimization)
8. Position Lifecycle State Machine (UI flow)
9. Renderer Registry Pattern (code architecture)

---

## Diagram Style Guide

### Consistency Rules

1. **Box Style**: Use Unicode box drawing characters
   ```
   ┌─────────────────────────────────────────────────┐
   │ PHASE NAME (Context)                            │
   └─────────────────────────────────────────────────┘
   ```

2. **Arrows**: Use vertical arrows for flow
   ```
                       ↓
   ```

3. **Indentation**: Use tree structure for sub-steps
   ```
   Main step
   ├─ Sub-step 1
   │  └─ Sub-sub-step
   └─ Sub-step 2
   ```

4. **Key Points**: Add after diagram
   ```
   **Key Points to Explain:**
   - Point 1
   - Point 2
   ```

5. **Examples**: Add concrete examples in code blocks
   ```python
   # Example code here
   ```

---

## Success Criteria

For each diagram:
- [ ] Shows clear flow from input → output
- [ ] Uses consistent ASCII/Unicode art style
- [ ] Includes "Key Points to Explain" section
- [ ] Placed in correct document and section
- [ ] Referenced in table of contents
- [ ] Includes example data where helpful

---

## Notes

- All diagrams should follow the style of the "Complete Data Flow" that you already like
- Focus on clarity over complexity
- Each diagram should tell one story clearly
- Add cross-references between related diagrams
- Keep ASCII art simple and readable

---

## Future Extensions

Additional diagrams that could be added later:
- API Response Processing (Navi, Suilend, etc.)
- Slack Notification Flow
- Oracle Price Fetching Flow
- Historical Chart Rendering
- Pending Deployments Queue
