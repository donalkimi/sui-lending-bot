# Positions and Portfolio Rendering - Technical Reference

**Version:** 2.0 (Post-Refactor)
**Status:** Implementation Plan
**Last Updated:** February 16, 2026

---

## Complete Data Flow: Strategy Discovery to Position Deployment

**Critical Understanding**: The generation methods in RateAnalyzer **discover opportunities**, they do NOT create positions in the database. Position creation only happens when a user explicitly clicks "Deploy".

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA COLLECTION (Hourly on Railway)                │
└─────────────────────────────────────────────────────────────┘
   refresh_pipeline()
   ├─ Fetches rates, prices, fees from all protocols
   ├─ Saves to rates_snapshot table (immutable)
   └─ Returns: merged DataFrames

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: STRATEGY DISCOVERY (Analysis Layer)                │
└─────────────────────────────────────────────────────────────┘
   RateAnalyzer.analyze_all_combinations()
   │
   ├─ For each strategy type:
   │  ├─ _generate_stablecoin_strategies()
   │  │  └─ Yields 1-leg strategies (pure analysis, no DB writes)
   │  ├─ _generate_noloop_strategies()
   │  │  └─ Yields 3-leg strategies (pure analysis, no DB writes)
   │  └─ _generate_recursive_strategies()
   │     └─ Yields 4-leg strategies (pure analysis, no DB writes)
   │
   └─ Returns: DataFrame with 100-500+ potential strategies
      └─ NO DATABASE WRITES TO POSITIONS TABLE

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: DASHBOARD DISPLAY ("All Strategies" Tab)           │
└─────────────────────────────────────────────────────────────┘
   User browses strategies
   │
   ├─ Filters by strategy_type, APR, token
   ├─ Sorts by net_apr
   └─ Clicks "Deploy" on ONE strategy
      └─ STILL NO DATABASE WRITES (just UI interaction)

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: POSITION DEPLOYMENT (Creates database record)      │
└─────────────────────────────────────────────────────────────┘
   User confirms in deployment modal
   │
   └─ position_service.create_position()
      ├─ Reads strategy data from Phase 2 DataFrame
      ├─ Creates position_id (UUID)
      ├─ INSERT INTO positions table ← FIRST DB WRITE
      └─ Position now tracked in "Positions" tab
```

**Key Distinction**:
- **Phases 1-3**: Read-only analysis (discovering what's possible)
- **Phase 4**: Write operation (committing capital to a specific strategy)

This is analogous to:
- **Phases 1-3**: Browsing products in an online store
- **Phase 4**: Clicking "Buy Now" and creating an order

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Batch Rendering System](#batch-rendering-system)
4. [Rendering Pipeline](#rendering-pipeline)
5. [Position Expander Details](#position-expander-details)
6. [Tab Implementations](#tab-implementations)
7. [Performance Optimizations](#performance-optimizations)
8. [Code Reference](#code-reference)

---

## System Overview

### Purpose

The position rendering system provides a unified, reusable way to display positions across multiple tabs (Positions, Portfolio2, and future tabs). It follows the principle of "write once, render anywhere" through a clean batch wrapper API.

### Key Features

1. **Batch Rendering**: Load data for multiple positions in 3 queries (not 3×N)
2. **Clean API**: Simple function signature with minimal parameters
3. **Self-Contained**: Handles database connections and infrastructure internally
4. **Reusable**: Same rendering logic across all tabs
5. **Context-Aware**: Different action buttons based on context
6. **Performance**: Optimized for speed with shared lookups

### Design Principles (from DESIGN_NOTES.md)

- **#1**: Timestamp as "current time" - selected timestamp defines "now"
- **#5**: Unix timestamps (seconds as int) internally
- **#11**: Dashboard as pure view layer - infrastructure handled internally
- **#13**: Explicit error handling with debug info

---

## Position Lifecycle: State Machine

This diagram shows all possible states a position can be in and the transitions between them.

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
```

**State Transitions:**

| From State | To State | Trigger | Database Action |
|------------|----------|---------|-----------------|
| **PENDING** | ACTIVE | User confirms deployment | `INSERT INTO positions (status='active')` |
| **ACTIVE** | REBALANCING | User clicks "Rebalance" | None (UI state only) |
| **REBALANCING** | ACTIVE | User confirms rebalance | `INSERT INTO position_rebalances`<br>`UPDATE positions SET entry_* = new_rates` |
| **REBALANCING** | ACTIVE | User clicks "Cancel" | None (return to normal rendering) |
| **ACTIVE** | CLOSED | User clicks "Close" | `UPDATE positions SET status='closed'` |
| **ACTIVE** | LIQUIDATED | Monitoring system detects | `UPDATE positions SET status='liquidated'` |

**State Characteristics:**

| State | In Database? | Earning? | PnL Status | User Actions |
|-------|--------------|----------|------------|--------------|
| **STRATEGY DISCOVERY** | No | N/A | N/A | Browse strategies |
| **PENDING** | No | No | N/A | Confirm or cancel deployment |
| **ACTIVE** | Yes | Yes | Unrealized | Rebalance, Close |
| **REBALANCING** | Yes | Yes | Unrealized | Confirm or cancel rebalance |
| **CLOSED** | Yes | No | Realized | View history only |
| **LIQUIDATED** | Yes | No | Realized (loss) | View history only |

**Key Points:**
- **PENDING** and **REBALANCING** are UI-only states (no database writes until confirmed)
- **ACTIVE** is the primary earning state
- **Rebalancing** creates new segment and resets entry state
- **CLOSED** and **LIQUIDATED** are terminal states (no further transitions)
- **Status field** in database only has 3 values: 'active', 'closed', 'liquidated'

---

## Architecture

### Component Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                   Tab Layer                         │
│  (Positions Tab, Portfolio2 Tab, Future Tabs)       │
│                                                      │
│  - Groups positions (portfolio2: by portfolio_id)   │
│  - Calls batch renderer                             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              Batch Rendering Layer                   │
│         render_positions_batch()                     │
│                                                      │
│  - Handles DB connections (get_db_connection)       │
│  - Batch loads data (3 queries)                     │
│  - Builds shared lookups (rate_lookup, prices)      │
│  - Loops through position_ids                       │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Position Rendering Layer                   │
│         render_position_expander()                   │
│                                                      │
│  - Strategy summary metrics (PnL, earnings)         │
│  - Detail table (4-leg or 3-leg)                    │
│  - Rebalance history                                │
│  - Action buttons (context-aware)                   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│         Strategy-Specific Renderers                  │
│   (RecursiveLendingRenderer, FundingRateArb, ...)   │
│                                                      │
│  - render_detail_table() - Strategy-specific layout │
│  - get_metrics_layout() - Metric definitions        │
│  - build_token_flow_string() - Display format       │
└─────────────────────────────────────────────────────┘
```

---

### Renderer Registry: Strategy Type → Renderer Class Mapping

The system uses a **registry pattern** to map strategy types to renderer classes. This enables different rendering logic for each strategy type (4-leg, 3-leg, 1-leg, etc.) while keeping a common interface.

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

**Key Architectural Benefits:**

| Benefit | Implementation |
|---------|----------------|
| **Plugin Architecture** | Add new renderers without modifying existing code |
| **Strategy-Specific UI** | Each strategy type has custom table layout |
| **Common Interface** | All renderers implement StrategyRendererBase |
| **Type Safety** | Fallback to default renderer if unknown type |
| **Extensibility** | 2-step process to add new renderer |

**File Reference:**
- **Base Class**: `dashboard/strategy_renderers.py` - `StrategyRendererBase`
- **Registry**: `STRATEGY_RENDERERS` dict at module level
- **Usage**: `dashboard/position_renderers.py` - `render_position_expander()`

---

### Data Flow

```
User Opens Tab
    │
    ├─> Tab loads position metadata
    │   (active_positions, portfolio_id grouping)
    │
    ├─> Tab calls render_positions_batch(position_ids, timestamp, context)
    │
    ├─> Batch Renderer:
    │   ├─> Creates DB connections (based on USE_CLOUD_DB)
    │   ├─> Batch loads statistics (1 query)
    │   ├─> Batch loads rebalances (1 query)
    │   ├─> Loads rates snapshot (1 query)
    │   ├─> Builds rate_lookup dict (O(1) access)
    │   └─> Builds oracle_prices dict (O(1) access)
    │
    └─> For each position_id:
        ├─> Get position metadata
        ├─> Retrieve pre-loaded stats
        ├─> Retrieve pre-loaded rebalances
        └─> Call render_position_expander()
            ├─> Build expander title with metrics
            ├─> Render summary metrics (5 columns)
            ├─> Call strategy renderer (e.g., RecursiveLendingRenderer)
            │   └─> Render 4-leg detail table
            ├─> Render rebalance history
            └─> Render action buttons (context-aware)
```

---

## Batch Rendering System

### Core Function: `render_positions_batch()`

**Location**: `dashboard/position_renderers.py`

**Signature**:
```python
def render_positions_batch(
    position_ids: List[str],
    timestamp_seconds: int,
    context: str = 'standalone'
) -> None
```

**Parameters**:
- `position_ids`: List of position IDs to render
- `timestamp_seconds`: Unix timestamp defining "current time"
- `context`: Rendering context ('standalone', 'portfolio2', 'portfolio')

**Purpose**: Primary entry point for rendering positions across all tabs. Handles all infrastructure and batch loading internally.

### Internal Architecture

```python
def render_positions_batch(position_ids, timestamp_seconds, context):
    # ========================================
    # PHASE 1: INFRASTRUCTURE SETUP
    # ========================================
    # Creates connections based on USE_CLOUD_DB flag
    conn = get_db_connection()
    engine = get_db_engine()
    service = PositionService(conn)

    # ========================================
    # PHASE 2: BATCH DATA LOADING
    # ========================================
    # Load ALL data in 3 queries (not 3×N)

    # Query 1: Load statistics for ALL positions
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)
    # Returns: dict[position_id] -> stats_dict

    # Query 2: Load rebalances for ALL positions
    all_rebalances = get_all_rebalance_history(position_ids, conn)
    # Returns: dict[position_id] -> list[rebalance_dicts]

    # Query 3: Load rates snapshot once
    rates_df = load_rates_snapshot(timestamp_seconds, conn, engine)
    # Returns: DataFrame with all rates at timestamp

    # ========================================
    # PHASE 3: BUILD SHARED LOOKUPS
    # ========================================
    # Create O(1) lookup dictionaries (shared across all positions)

    rate_lookup = build_rate_lookup(rates_df)
    # Returns: dict[(protocol, token)] -> {lend, borrow, borrow_fee, price}

    oracle_prices = build_oracle_prices(rates_df)
    # Returns: dict[token] -> price_usd

    # ========================================
    # PHASE 4: RENDER EACH POSITION
    # ========================================
    for position_id in position_ids:
        position = service.get_position_by_id(position_id)
        stats = all_stats.get(position_id)
        rebalances = all_rebalances.get(position_id, [])

        render_position_expander(
            position, stats, rebalances,
            rate_lookup, oracle_prices,
            service, timestamp_seconds,
            strategy_type, context,
            portfolio_id, expanded=False
        )
```

---

### Batch Rendering Pipeline: 3 Queries for N Positions

This visual flow shows how the batch rendering system loads data for multiple positions efficiently, using only 3 database queries regardless of the number of positions.

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
═══════════════════════════════════════════════════════════════
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

**Key Points:**
- **Batch loading** = 3 queries for N positions (not 3×N)
- **Shared lookups** = O(1) access to rates/prices (not O(N) DataFrame filtering)
- **Performance scales** linearly with slight overhead (not quadratically)
- **Same pattern** used for Positions tab, Portfolio2 tab, future tabs
- **Memory efficient** = ~200KB total for 20 positions

---

### Performance Analysis

**Complexity**:
- **Without batch loading**: O(3N) queries - 3 queries per position
- **With batch loading**: O(3) queries - 3 queries total for N positions
- **Speedup**: ~N × faster for N positions

**Typical Performance**:
- 1 position: ~200ms (marginal difference)
- 5 positions: ~300ms (5× faster than naive)
- 10 positions: ~400ms (10× faster)
- 20 positions: ~600ms (20× faster)

**Memory Usage**:
- Shared lookups: ~100KB for typical rates snapshot
- Statistics: ~5KB per position
- Total for 20 positions: ~200KB (negligible)

---

## Rendering Pipeline

### Stage 1: Tab-Level Grouping

**Positions Tab**:
```python
def render_positions_table_tab(timestamp_seconds):
    # Load all active positions
    active_positions = service.get_active_positions(timestamp_seconds)

    # Extract IDs
    position_ids = active_positions['position_id'].tolist()

    # Delegate to batch renderer
    render_positions_batch(position_ids, timestamp_seconds, 'standalone')
```

**Portfolio2 Tab**:
```python
def render_portfolio2_tab(timestamp_seconds):
    # Load all active positions
    active_positions = service.get_active_positions(timestamp_seconds)

    # Group by portfolio_id
    for portfolio_id in unique_portfolio_ids:
        portfolio_positions = active_positions[
            active_positions['portfolio_id'] == portfolio_id
        ]
        position_ids = portfolio_positions['position_id'].tolist()

        # Render portfolio expander
        with st.expander(f"Portfolio: {name}"):
            # Delegate to batch renderer
            render_positions_batch(position_ids, timestamp_seconds, 'portfolio2')
```

### Stage 2: Batch Data Loading

**Query 1: Position Statistics**

```python
def get_all_position_statistics(position_ids, timestamp_seconds, engine):
    """
    Load pre-calculated statistics for all positions.

    Query: SELECT * FROM position_statistics
           WHERE position_id IN (?, ?, ...)
             AND timestamp_seconds = ?
    """
    query = """
    SELECT position_id, total_pnl, total_earnings, base_earnings,
           reward_earnings, total_fees, current_value, realized_apr,
           current_apr, holding_days
    FROM position_statistics
    WHERE position_id IN ({placeholders})
      AND timestamp_seconds = ?
    """

    # Returns: dict[position_id] -> stats_dict
```

**Query 2: Rebalance History**

```python
def get_all_rebalance_history(position_ids, conn):
    """
    Load rebalance history for all positions.

    Query: SELECT * FROM position_rebalances
           WHERE position_id IN (?, ?, ...)
           ORDER BY position_id, sequence_number
    """
    query = """
    SELECT *
    FROM position_rebalances
    WHERE position_id IN ({placeholders})
    ORDER BY position_id, sequence_number
    """

    # Returns: dict[position_id] -> list[rebalance_dicts]
```

**Query 3: Rates Snapshot**

```python
def load_rates_snapshot(timestamp_seconds, conn, engine):
    """
    Load rates snapshot for all tokens/protocols at timestamp.

    Query: SELECT * FROM rates_snapshot
           WHERE timestamp = ?
    """
    query = """
    SELECT protocol, token, token_contract,
           lend_total_apr, borrow_total_apr, borrow_fee, price_usd
    FROM rates_snapshot
    WHERE timestamp = ?
    """

    # Returns: DataFrame with all rates
```

### Stage 3: Build Shared Lookups

**Rate Lookup Dictionary**:

```python
def build_rate_lookup(rates_df):
    """
    Build O(1) lookup for rates by (protocol, token).

    Structure:
    {
        ('Navi', 'USDC'): {
            'lend': 0.0316,     # 3.16% lend APR
            'borrow': 0.0485,   # 4.85% borrow APR
            'borrow_fee': 0.0005, # 0.05% fee
            'price': 1.0001     # $1.00 price
        },
        ...
    }
    """
    rate_lookup = {}
    for _, row in rates_df.iterrows():
        key = (row['protocol'], row['token'])
        rate_lookup[key] = {
            'lend': float(row['lend_total_apr']) if pd.notna(row['lend_total_apr']) else 0.0,
            'borrow': float(row['borrow_total_apr']) if pd.notna(row['borrow_total_apr']) else 0.0,
            'borrow_fee': float(row['borrow_fee']) if pd.notna(row['borrow_fee']) else 0.0,
            'price': float(row['price_usd']) if pd.notna(row['price_usd']) else 0.0
        }
    return rate_lookup
```

**Oracle Prices Dictionary**:

```python
def build_oracle_prices(rates_df):
    """
    Build O(1) lookup for oracle prices by token.

    Structure:
    {
        'USDC': 1.0001,
        'SUI': 3.4521,
        'DEEP': 0.0452,
        ...
    }
    """
    oracle_prices = {}
    for _, row in rates_df.iterrows():
        token = row['token']
        price = float(row['price_usd']) if pd.notna(row['price_usd']) else None
        if price and price > 0:
            # Use max price if multiple protocols report different prices
            oracle_prices[token] = max(oracle_prices.get(token, 0), price)
    return oracle_prices
```

### Stage 4: Position-Level Rendering

**Entry Point**: `render_position_expander()`

**Flow**:
```
render_position_expander()
├─ Build title with metrics
│  ├─ Token flow: "USDC → DEEP → USDC"
│  ├─ Protocols: "Navi ↔ Suilend"
│  ├─ Deployment USD: "$10,000"
│  ├─ PnL: "$245.32 (+2.45%)"
│  └─ Current APR: "8.42%"
│
├─ Create rate helper functions
│  ├─ get_rate(token, protocol, rate_type)
│  ├─ get_borrow_fee(token, protocol)
│  └─ get_price_with_fallback(token, protocol)
│
├─ Render strategy summary metrics
│  ├─ Total PnL (Real + Unreal)
│  ├─ Total Earnings (Base + Reward)
│  ├─ Base Earnings
│  ├─ Reward Earnings
│  └─ Total Fees
│
├─ Render LIVE SEGMENT
│  └─ Call strategy renderer
│     └─ render_detail_table()
│        ├─ Row 1: Lend Token1 at Protocol A
│        ├─ Row 2: Borrow Token2 at Protocol A
│        ├─ Row 3: Lend Token2 at Protocol B
│        └─ Row 4: Borrow Token3 at Protocol B
│
├─ Render HISTORICAL SEGMENTS (if rebalances)
│  └─ For each rebalance:
│     ├─ Segment summary (PnL, earnings, fees)
│     └─ Detail table (same as live)
│
└─ Render action buttons (context-aware)
   ├─ context='standalone': Rebalance, Close
   ├─ context='portfolio2': Rebalance, Close, Remove from Portfolio
   └─ context='portfolio': View Portfolio, Rebalance, Close
```

---

## PnL Calculation Flow: Token Amounts × Prices Across Time Periods

This flow shows how position PnL is calculated from historical time-series data, not just entry → live snapshots. Each time period uses actual rates from that timestamp.

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

**Example Calculation:**

```
Position Details:
- Deployment: $10,000
- Entry: 2026-02-01 00:00:00
- Live: 2026-02-11 00:00:00 (10 days)
- L_A = 1.5, B_A = 1.0, L_B = 1.0, B_B = 0.7

Time Periods (hourly snapshots):
- Period 1: 2026-02-01 00:00 → 01:00 (1 hour)
  - lend_rate_1A = 3.0%, lend_rate_2B = 12.0%
  - borrow_rate_2A = 8.5%, borrow_rate_3B = 5.5%
  - Earnings: $10k × (1.5×0.03 + 1.0×0.12) × (1/8760) = $0.194
  - Costs: $10k × (1.0×0.085 + 0.7×0.055) × (1/8760) = $0.141
  - Net: $0.053

- Period 2: 2026-02-01 01:00 → 02:00 (1 hour)
  - [Similar calculation with updated rates]
  ...

Total over 240 periods (10 days):
- Total Earnings: $312.45
- Total Costs: $245.12
- Total Fees: $67.13 (one-time at entry)
- Net PnL: $312.45 - $245.12 - $67.13 = $0.20

Realized APR:
- Annual earnings = $0.20 × (365 / 10) = $7.30
- APR = $7.30 / $10,000 = 0.073%
```

**Key Points:**
- **Time-series calculation**: Uses all historical snapshots, not just entry and live
- **Period-accurate rates**: Each period uses actual rates from that timestamp
- **One-time fees**: Charged only at entry (not recurring)
- **Annualized APR**: Actual performance extrapolated to annual rate
- **Cached results**: Pre-calculated and stored in `position_statistics` table

**File Reference:**
- **Calculation Logic**: `analysis/position_service.py` - `calculate_position_value()`
- **Statistics Storage**: `position_statistics` table (cached metrics)
- **Query Pattern**: Load all timestamps between entry and live

---

## Position Expander Details

### Title Format

```
[Date] | [Token Flow] | [Protocols] | Dep: $X → Val: $Y | Entry X% | Curr X% | Real X% | PnL: $Z (+X%)
```

**Example**:
```
2026-01-15 14:30 | USDC → DEEP → USDC | Navi ↔ Suilend |
Dep: $10,000 → Val: $10,245 | Entry 12.34% | Curr 11.95% | Real 8.20% |
PnL: $245.32 (+2.45%)
```

### Strategy Summary Metrics (5 Columns)

```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Total PnL   │ Total       │ Base        │ Reward      │ Total Fees  │
│ (Real+Unr)  │ Earnings    │ Earnings    │ Earnings    │             │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ $245.32     │ $312.45     │ $285.12     │ $27.33      │ $67.13      │
│ (+2.45%)    │             │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

**Breakdown**:
- **Total PnL** = current_value - deployment_usd
- **Total Earnings** = lend_earnings_1A + lend_earnings_2B
- **Base Earnings** = base_earnings_1A + base_earnings_2B
- **Reward Earnings** = reward_earnings_1A + reward_earnings_2B
- **Total Fees** = borrow_fees_2A + borrow_fees_3B

### Detail Table (4-Leg Recursive Lending)

```
┌──────────┬───────┬────────┬────────────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────────┬───────────────┬───────────────┬──────────┬──────────────┬─────────────┐
│ Protocol │ Token │ Action │ Entry Rate │ Segment Rate │ Live Rate    │ Entry Price  │ Live Price   │ Liq Price   │ Token Amount  │ Rebal Req'd?  │ Fee Rate │ Entry Liq    │ Live Liq    │
│          │       │        │            │              │              │              │              │ ($)         │               │               │ (%)      │ Distance     │ Distance    │
├──────────┼───────┼────────┼────────────┼──────────────┼──────────────┼──────────────┼──────────────┼─────────────┼───────────────┼───────────────┼──────────┼──────────────┼─────────────┤
│ Navi     │ USDC  │ Lend   │ 3.00%      │ 3.05%        │ 3.10%        │ $1.0000      │ $1.0001      │ N/A         │ 1,500.00      │ No            │ 0.00%    │ N/A          │ N/A         │
│ Navi     │ DEEP  │ Borrow │ 8.50%      │ 8.45%        │ 8.40%        │ $0.0450      │ $0.0480      │ $0.0562     │ 28,345.50     │ Yes (+6.7%)   │ 0.05%    │ +28.4%       │ +17.1%      │
│ Suilend  │ DEEP  │ Lend   │ 12.00%     │ 12.05%       │ 12.10%       │ $0.0450      │ $0.0480      │ N/A         │ 28,345.50     │ Yes (+6.7%)   │ 0.00%    │ N/A          │ N/A         │
│ Suilend  │ USDC  │ Borrow │ 5.50%      │ 5.45%        │ 5.40%        │ $1.0000      │ $1.0001      │ $1.1250     │ 852.00        │ No            │ 0.03%    │ +12.5%       │ +12.5%      │
└──────────┴───────┴────────┴────────────┴──────────────┴──────────────┴──────────────┴──────────────┴─────────────┴───────────────┴───────────────┴──────────┴──────────────┴─────────────┘
```

**Column Descriptions**:

| Column | Description | Source |
|--------|-------------|--------|
| Protocol | Protocol name (Navi, Suilend, etc.) | position.protocol_A / protocol_B |
| Token | Token symbol (USDC, DEEP, etc.) | position.token1 / token2 / token3 |
| Action | Lend or Borrow | Leg type (1A=Lend, 2A=Borrow, etc.) |
| Entry Rate | APR at position entry | position.entry_lend_rate_1A, etc. |
| Segment Rate | APR at segment start (after rebalance) | rebalance.opening_lend_rate_1A |
| Live Rate | Current APR at timestamp | rate_lookup[(protocol, token)]['lend'] |
| Entry Price | Token price at entry | position.entry_price_1A |
| Live Price | Current token price | get_price_with_fallback(token, protocol) |
| Liq Price ($) | Liquidation price (borrow legs only) | calculate_liquidation_price() |
| Token Amount | Token quantity | position.entry_token_amount_1A |
| Rebal Req'd? | Price drift % | (live_price - entry_price) / entry_price |
| Fee Rate (%) | Borrow fee (borrow legs only) | rate_lookup[(protocol, token)]['borrow_fee'] |
| Entry Liq Distance | Liq distance at entry | (liq_price - entry_price) / entry_price |
| Live Liq Distance | Current liq distance | (liq_price - live_price) / live_price |

### Rebalance History

**Format**: Collapsed expanders, one per historical rebalance

```
▶ Segment 1: 2026-01-15 → 2026-01-20 (5.0 days)
  Realized PnL: $42.31 | Lend Earnings: $58.45 | Borrow Costs: $12.34 | Fees: $3.80

  [When expanded: Shows detail table for segment 1 with segment rates/prices]

▶ Segment 2: 2026-01-20 → 2026-01-25 (5.0 days)
  Realized PnL: $38.12 | Lend Earnings: $52.18 | Borrow Costs: $10.26 | Fees: $3.80

  [When expanded: Shows detail table for segment 2]

● Live Segment: 2026-01-25 → Now (3.2 days)
  [Detail table shown by default]
```

---

## Tab Implementations

### Positions Tab

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_positions_table_tab(timestamp_seconds)`

**Implementation**:

```python
def render_positions_table_tab(timestamp_seconds):
    """
    Render Positions tab - all active positions in flat list.

    Design: Pure view layer - delegates to batch renderer.
    """
    st.markdown("## 💼 Positions")

    # Load position metadata
    conn = get_db_connection()
    service = PositionService(conn)
    active_positions = service.get_active_positions(timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    # Extract position IDs
    position_ids = active_positions['position_id'].tolist()

    # Delegate to batch renderer (handles everything)
    render_positions_batch(
        position_ids=position_ids,
        timestamp_seconds=timestamp_seconds,
        context='standalone'
    )
```

**Key Points**:
- Simple wrapper around batch renderer
- Context: `'standalone'` (not part of portfolio)
- ~15 lines of code (down from ~60)

---

### Portfolio2 Tab

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_portfolio2_tab(timestamp_seconds)`

**Implementation**:

```python
def render_portfolio2_tab(timestamp_seconds):
    """
    Render Portfolio2 tab - positions grouped by portfolio.

    Design: Groups positions, then delegates to batch renderer.
    """
    st.markdown("## 📂 Portfolio View")

    # Load positions and group by portfolio_id
    conn = get_db_connection()
    service = PositionService(conn)
    active_positions = service.get_active_positions(timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    # Group by portfolio_id
    portfolio_ids = active_positions['portfolio_id'].unique()

    # Load portfolio metadata
    portfolios_dict = {}
    for pid in portfolio_ids:
        if pd.notna(pid):
            portfolio = get_portfolio_by_id(pid, conn)
            if portfolio:
                portfolios_dict[pid] = portfolio

    # Add virtual "Single Positions" portfolio
    standalone_positions = active_positions[active_positions['portfolio_id'].isna()]
    if not standalone_positions.empty:
        portfolios_dict['__standalone__'] = {
            'portfolio_id': '__standalone__',
            'portfolio_name': 'Single Positions',
            'is_virtual': True
        }

    # Render each portfolio
    for portfolio_id, portfolio in sorted(portfolios_dict.items()):
        # Get positions for this portfolio
        if portfolio_id == '__standalone__':
            portfolio_positions = standalone_positions
        else:
            portfolio_positions = active_positions[
                active_positions['portfolio_id'] == portfolio_id
            ]

        # Calculate aggregates
        total_deployed = portfolio_positions['deployment_usd'].sum()
        num_positions = len(portfolio_positions)

        # Render portfolio expander
        with st.expander(
            f"**{portfolio['portfolio_name']}** | "
            f"Positions: {num_positions} | "
            f"Total: ${total_deployed:,.2f}",
            expanded=False
        ):
            st.markdown(f"### Positions in {portfolio['portfolio_name']}")

            # Delegate to batch renderer
            position_ids = portfolio_positions['position_id'].tolist()
            render_positions_batch(
                position_ids=position_ids,
                timestamp_seconds=timestamp_seconds,
                context='portfolio2'
            )
```

**Key Points**:
- Groups positions by portfolio_id
- Virtual "Single Positions" for NULL portfolio_ids
- Each portfolio uses batch renderer
- Context: `'portfolio2'`

---

## Performance Optimizations

### Batch Loading Strategy

**Problem**: Naive approach queries database once per position
```
For each position:
    Query 1: Get statistics
    Query 2: Get rebalances
    Query 3: Get rates
Total: 3 × N queries
```

**Solution**: Batch load all data upfront
```
Query 1: Get statistics for ALL positions
Query 2: Get rebalances for ALL positions
Query 3: Get rates (once)
Total: 3 queries
```

**Speedup**: ~N × faster for N positions

### O(1) Lookup Strategy

**Problem**: Repeated DataFrame filtering is O(N) per lookup
```python
for position in positions:
    for leg in ['1A', '2A', '2B', '3B']:
        rate = rates_df[
            (rates_df['protocol'] == protocol) &
            (rates_df['token'] == token)
        ]['lend_total_apr'].iloc[0]  # O(N) lookup
```

**Solution**: Build dictionary once, O(1) lookups
```python
# Build once (O(N))
rate_lookup = {(protocol, token): rates for ...}

# Lookup many times (O(1))
for position in positions:
    for leg in ['1A', '2A', '2B', '3B']:
        rate = rate_lookup[(protocol, token)]['lend']  # O(1) lookup
```

**Speedup**: ~15× faster for typical cases (4 legs × 10 positions = 40 lookups)

### Connection Reuse

**Implementation**: `get_db_connection()` returns cached/singleton connection

```python
# Module-level cache
_db_connection_cache = None

def get_db_connection():
    global _db_connection_cache
    if _db_connection_cache is None:
        if USE_CLOUD_DB:
            _db_connection_cache = create_engine(SUPABASE_URL).connect()
        else:
            _db_connection_cache = sqlite3.connect(DB_PATH)
    return _db_connection_cache
```

**Benefit**: No connection overhead per batch call

### Memory Efficiency

**Total Memory for 20 Positions**:
- Shared lookups: ~100KB
- Statistics: ~5KB × 20 = 100KB
- Rebalances: ~2KB × 20 = 40KB
- Total: ~240KB (negligible)

**Strategy**: Pre-load all data, share across renderers

---

## Code Reference

### Key Files

#### 1. `dashboard/position_renderers.py`

**Purpose**: Core rendering infrastructure

**Key Functions**:

```python
# Main entry point (NEW)
def render_positions_batch(position_ids, timestamp_seconds, context):
    """Batch render multiple positions with optimized data loading."""

# Helper entry point (NEW)
def render_position_single(position_id, timestamp_seconds, context):
    """Convenience wrapper for single position."""

# Core renderer (EXISTING)
def render_position_expander(position, stats, rebalances, ...):
    """Render single position with full detail."""

# Lookup builders (EXISTING)
def build_rate_lookup(rates_df):
    """Build O(1) rate lookup dictionary."""

def build_oracle_prices(rates_df):
    """Build O(1) oracle price dictionary."""

# Helper creators (EXISTING)
def create_rate_helpers(rate_lookup, oracle_prices):
    """Create 3 helper functions for rate/price lookups."""

# Summary renderers (EXISTING)
def render_strategy_summary_metrics(stats, deployment, strategy_type):
    """Render 5-column summary metrics."""

def render_segment_summary(rebalance):
    """Render segment PnL breakdown."""
```

**Location**: Lines ~1-1400

---

#### 2. `dashboard/dashboard_renderer.py`

**Purpose**: Tab implementations

**Key Functions**:

```python
# Positions Tab (REFACTORED)
def render_positions_table_tab(timestamp_seconds):
    """Render Positions tab using batch renderer."""

# Portfolio2 Tab (NEW)
def render_portfolio2_tab(timestamp_seconds):
    """Render Portfolio2 tab with portfolio grouping."""

# Portfolio expander (NEW)
def render_portfolio_expander(portfolio, portfolio_positions, timestamp_seconds):
    """Render single portfolio with batch renderer."""

# Helper (NEW)
def get_portfolio_by_id(portfolio_id, conn):
    """Load portfolio metadata from database."""
```

**Location**: Lines ~1170-1800 (Positions), ~4300+ (Portfolio2)

---

#### 3. `dashboard/dashboard_utils.py`

**Purpose**: Database utilities

**Key Functions**:

```python
def get_db_connection():
    """Get database connection based on USE_CLOUD_DB flag."""

def get_db_engine():
    """Get SQLAlchemy engine based on USE_CLOUD_DB flag."""

def get_all_position_statistics(position_ids, timestamp_seconds, engine):
    """Batch load statistics for multiple positions."""

def get_all_rebalance_history(position_ids, conn):
    """Batch load rebalance history for multiple positions."""

def load_rates_snapshot(timestamp_seconds, conn, engine):
    """Load rates snapshot at timestamp."""
```

---

### Function Call Chain

```
Tab Level
  │
  ├─> render_positions_table_tab()
  │   └─> render_positions_batch()
  │
  └─> render_portfolio2_tab()
      ├─> Group positions by portfolio_id
      └─> For each portfolio:
          └─> render_positions_batch()

Batch Level
  │
  └─> render_positions_batch(position_ids, timestamp, context)
      ├─> get_db_connection()
      ├─> get_db_engine()
      ├─> get_all_position_statistics(position_ids)
      ├─> get_all_rebalance_history(position_ids)
      ├─> load_rates_snapshot(timestamp)
      ├─> build_rate_lookup(rates_df)
      ├─> build_oracle_prices(rates_df)
      └─> For each position_id:
          └─> render_position_expander()

Position Level
  │
  └─> render_position_expander(position, stats, rebalances, ...)
      ├─> build_position_expander_title()
      ├─> create_rate_helpers(rate_lookup, oracle_prices)
      ├─> render_strategy_summary_metrics()
      ├─> Get strategy renderer (e.g., RecursiveLendingRenderer)
      ├─> renderer.render_detail_table()
      ├─> For each rebalance:
      │   └─> render_segment_summary()
      └─> Render action buttons (context-aware)

Strategy Level
  │
  └─> RecursiveLendingRenderer.render_detail_table()
      ├─> _build_lend_leg_row() × 2
      └─> _build_borrow_leg_row() × 2
```

---

## Summary

This reference document describes the positions and portfolio rendering system after the refactoring:

### Key Improvements

1. **Clean API**: `render_positions_batch(position_ids, timestamp, context)` - 3 parameters
2. **Self-Contained**: Handles infrastructure internally (connections, batch loading)
3. **Reusable**: Same function for Positions tab, Portfolio2 tab, future tabs
4. **Performance**: Batch loading (3 queries for N positions)
5. **Maintainability**: Change once, update everywhere

### Architecture Benefits

- ✅ **Zero code duplication** across tabs
- ✅ **Consistent rendering** (change function → all tabs update)
- ✅ **Easy to extend** (new tabs just call batch renderer)
- ✅ **Performance maintained** (batch loading optimizations preserved)
- ✅ **Clean separation** (infrastructure vs. rendering vs. strategy)

### Design Principles

- ✅ All 15 DESIGN_NOTES.md principles followed
- ✅ ARCHITECTURE.md patterns (database as cache, batch loading)
- ✅ Event sourcing (immutable position data, calculated performance)

---

**For implementation details, see**: `upgradePositions_makePortfolio2.md`
