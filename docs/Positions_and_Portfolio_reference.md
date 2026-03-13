# Positions and Portfolio - Master Technical Reference

**Version:** 3.0 (Merged Master)
**Status:** Active Reference
**Last Updated:** March 2026

---

## Table of Contents

1. [System Overview & Data Flow](#1-system-overview--data-flow)
2. [Dashboard Tab Structure](#2-dashboard-tab-structure)
3. [Position Lifecycle: State Machine](#3-position-lifecycle-state-machine)
4. [Architecture: Rendering System](#4-architecture-rendering-system)
5. [Batch Rendering System](#5-batch-rendering-system)
6. [Rendering Pipeline Details](#6-rendering-pipeline-details)
7. [Position Expander Details](#7-position-expander-details)
8. [PnL Calculation Flow](#8-pnl-calculation-flow)
9. [Tab Implementations: Positions & Portfolio View](#9-tab-implementations-positions--portfolio-view)
10. [Performance Optimizations](#10-performance-optimizations)
11. [Portfolio Allocator System](#11-portfolio-allocator-system)
12. [Allocation Algorithm](#12-allocation-algorithm)
13. [Exposure Calculations](#13-exposure-calculations)
14. [Portfolio Persistence & Dashboard Interface](#14-portfolio-persistence--dashboard-interface)
15. [Database Schema (All Tables)](#15-database-schema-all-tables)
16. [Key Functions & Implementation](#16-key-functions--implementation)
17. [Statistics Architecture](#17-statistics-architecture)
18. [Design Principles](#18-design-principles)
19. [Formulas & Calculations](#19-formulas--calculations)
20. [File Locations & Code Reference](#20-file-locations--code-reference)

---

## 1. System Overview & Data Flow

### Complete Data Flow: Strategy Discovery to Position Deployment

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

---

## 2. Dashboard Tab Structure

### Actual Tab Order (9 Tabs — Verified from `dashboard_renderer.py`)

```
┌─────────────────────────────────────────────────────────────┐
│  Sui Lending Bot Dashboard                                  │
├─────────────────────────────────────────────────────────────┤
│  Tab 1: 📊 All Strategies                                   │
│  Tab 2: 🎯 Allocation          ← Portfolio Allocator UI     │
│  Tab 3: 📈 Rate Tables                                      │
│  Tab 4: ⚠️  0 Liquidity                                     │
│  Tab 5: 💼 Positions           ← THIS DOCUMENT (primary)    │
│  Tab 6: 📂 Portfolio View      ← Positions grouped by port  │
│  Tab 7: 💎 Oracle Prices                                    │
│  Tab 8: 🚀 Pending Deployments                              │
│  Tab 9: 📉 Analysis                                         │
└─────────────────────────────────────────────────────────────┘
```

**Code Reference** (`dashboard/dashboard_renderer.py` line 4251):
```python
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📊 All Strategies",
    "🎯 Allocation",
    "📈 Rate Tables",
    "⚠️ 0 Liquidity",
    "💼 Positions",
    "📂 Portfolio View",
    "💎 Oracle Prices",
    "🚀 Pending Deployments",
    "📉 Analysis",
])
```

**Tab Implementations:**
- Tab 2 (Allocation): `render_allocation_tab(display_results)`
- Tab 5 (Positions): `render_positions_table_tab(timestamp_seconds)`
- Tab 6 (Portfolio View): `render_portfolio2_tab(timestamp_seconds)`

---

## 3. Position Lifecycle: State Machine

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

## 4. Architecture: Rendering System

### Component Hierarchy

```
┌─────────────────────────────────────────────────────┐
│                   Tab Layer                         │
│  (Positions Tab, Portfolio View Tab, Future Tabs)   │
│                                                      │
│  - Groups positions (Portfolio View: by portfolio_id)│
│  - Calls batch renderer                             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              Batch Rendering Layer                   │
│         render_positions_batch()                     │
│                                                      │
│  - Handles DB connections (get_db_connection)       │
│  - Batch loads data (3 queries + basis query)       │
│  - Builds shared lookups (rate_lookup, prices)      │
│  - Builds basis_lookup (perp strategies)            │
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

### Renderer Registry: Strategy Type to Renderer Class Mapping

The system uses a **registry pattern** to map strategy types to renderer classes:

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
```

**Renderer Interface (Base Class):**

```python
class StrategyRendererBase(ABC):
    @abstractmethod
    def render_detail_table(self, position, rebalance, ...):
        """Render strategy-specific detail table (4-leg, 3-leg, etc.)"""
        pass

    @abstractmethod
    def get_metrics_layout(self):
        """Return list of metric definitions: [(label, key, format), ...]"""
        pass

    @abstractmethod
    def build_token_flow_string(self, position):
        """Build human-readable token flow: 'USDC → DEEP → USDC'"""
        pass
```

**Concrete Renderers:**

| Renderer | Legs | Token Flow | Notes |
|----------|------|------------|-------|
| `RecursiveLendingRenderer` | 4 | `USDC → DEEP → USDC` | Lend1A, Borrow2A, Lend2B, Borrow3B |
| `NoLoopRenderer` | 3 | `USDC → DEEP` | No B_B leg (token3 is NULL) |
| `StablecoinRenderer` | 1 | `USDC (Lend Only)` | No borrow legs |

**Extension: Adding a New Renderer:**
1. Create class inheriting `StrategyRendererBase`
2. Register in `STRATEGY_RENDERERS` dict
3. No changes to `render_position_expander()` needed — registry routes automatically

**File Reference:**
- Base Class: `dashboard/strategy_renderers.py` — `StrategyRendererBase`
- Registry: `STRATEGY_RENDERERS` dict at module level
- Usage: `dashboard/position_renderers.py` — `render_position_expander()`

---

## 5. Batch Rendering System

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
- `context`: Rendering context (`'standalone'`, `'portfolio2'`, `'portfolio'`)

**Purpose**: Primary entry point for rendering positions across all tabs. Handles all infrastructure and batch loading internally.

### Internal Architecture

```python
def render_positions_batch(position_ids, timestamp_seconds, context):
    # PHASE 1: INFRASTRUCTURE SETUP
    conn = get_db_connection()
    engine = get_db_engine()
    service = PositionService(conn)

    # PHASE 2: BATCH DATA LOADING (3 queries + basis)
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)
    all_rebalances = get_all_rebalance_history(position_ids, conn)
    rates_df = pd.read_sql_query(rates_query, engine, params=(timestamp_str,))

    # Load spot/perp basis data (for perp strategies)
    basis_lookup: Dict = {}
    # SELECT spot_contract, basis_bid, basis_ask, perp_bid, perp_ask, spot_bid, spot_ask
    # FROM spot_perp_basis WHERE timestamp = ?

    # PHASE 3: BUILD SHARED LOOKUPS
    rate_lookup = build_rate_lookup(rates_df)     # (protocol, token) -> rates dict
    oracle_prices = build_oracle_prices(rates_df)  # token -> price_usd

    # PHASE 4: RENDER EACH POSITION
    for position_id in position_ids:
        position = service.get_position_by_id(position_id)
        stats = all_stats.get(position_id)
        rebalances = all_rebalances.get(position_id, [])
        strategy_type = position.get('strategy_type')

        render_position_expander(
            position=position,
            stats=stats,
            rebalances=rebalances,
            rate_lookup=rate_lookup,
            oracle_prices=oracle_prices,
            service=service,
            timestamp_seconds=timestamp_seconds,
            strategy_type=strategy_type,
            context=context,
            portfolio_id=position.get('portfolio_id'),
            expanded=False,
            basis_lookup=basis_lookup  # passed for perp strategies
        )
```

### Batch Rendering Pipeline: 3 Queries for N Positions

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: render_positions_batch([id1, id2, ..., idN])         │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: BATCH DATA LOADING (3 Queries Total)               │
└─────────────────────────────────────────────────────────────┘
   Query 1: Load ALL position statistics
   ├─ SELECT * FROM position_statistics
   │  WHERE position_id IN (id1, id2, ..., idN)
   │    AND timestamp_seconds = ?
   └─ Returns: dict[position_id] -> stats_dict

   Query 2: Load ALL rebalance history
   ├─ SELECT * FROM position_rebalances
   │  WHERE position_id IN (id1, id2, ..., idN)
   │  ORDER BY position_id, sequence_number
   └─ Returns: dict[position_id] -> list[rebalance_dicts]

   Query 3: Load rates snapshot ONCE
   ├─ SELECT protocol, token, lend_total_apr, borrow_total_apr,
   │         borrow_fee, price_usd FROM rates_snapshot
   │  WHERE timestamp = ?
   └─ Returns: DataFrame with all rates (shared across all positions)

   Query 4: Load spot/perp basis (optional, for perp strategies)
   └─ SELECT spot_contract, basis_bid/ask, perp_bid/ask, spot_bid/ask
      FROM spot_perp_basis WHERE timestamp = ?

PERFORMANCE COMPARISON:
Naive: 3 × N queries — 10 positions = 30 queries (~3s)
Batch: 3 queries total — 10 positions = 3 queries (~400ms)
Speedup: ~N× faster
```

### Performance Analysis

| Positions | Naive (3×N queries) | Batch (3 queries) | Speedup |
|-----------|--------------------|--------------------|---------|
| 1 | ~300ms | ~200ms | 1.5× |
| 5 | ~1,500ms | ~300ms | 5× |
| 10 | ~3,000ms | ~400ms | 10× |
| 20 | ~6,000ms | ~600ms | 20× |

**Memory Usage:**
- Shared lookups: ~100KB for typical rates snapshot
- Statistics: ~5KB per position
- Total for 20 positions: ~200KB (negligible)

---

## 6. Rendering Pipeline Details

### Stage 1: Tab-Level Grouping

**Positions Tab**:
```python
def render_positions_table_tab(timestamp_seconds):
    active_positions = service.get_active_positions(timestamp_seconds)
    position_ids = active_positions['position_id'].tolist()
    render_positions_batch(position_ids, timestamp_seconds, 'standalone')
```

**Portfolio View Tab**:
```python
def render_portfolio2_tab(timestamp_seconds):
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)
    # Group by portfolio_id
    for portfolio_id, portfolio in portfolio_items:
        portfolio_positions = active_positions[active_positions['portfolio_id'] == portfolio_id]
        render_portfolio_expander(portfolio, portfolio_positions, timestamp_seconds)
        # Inside: calls render_positions_batch(position_ids, timestamp_seconds, 'portfolio2')
```

### Stage 2: Batch Data Loading

**Query 1: Position Statistics**
```python
def get_all_position_statistics(position_ids, timestamp_seconds, engine):
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
    # Returns: dict[position_id] -> stats_dict
```

**Query 2: Rebalance History**
```python
def get_all_rebalance_history(position_ids, conn):
    query = """
    SELECT * FROM position_rebalances
    WHERE position_id IN ({placeholders})
    ORDER BY position_id, sequence_number
    """
    # Returns: dict[position_id] -> list[rebalance_dicts]
```

**Query 3: Rates Snapshot**
```python
rates_query = """
SELECT protocol, token, lend_total_apr, borrow_total_apr, borrow_fee, price_usd
FROM rates_snapshot
WHERE timestamp = ?
"""
# Returns: DataFrame with all rates
```

### Stage 3: Build Shared Lookups

**Rate Lookup Dictionary:**
```python
def build_rate_lookup(rates_df):
    """
    Structure:
    {
        ('Navi', 'USDC'): {
            'lend': 0.0316,       # 3.16% lend APR
            'borrow': 0.0485,     # 4.85% borrow APR
            'borrow_fee': 0.0005, # 0.05% fee
            'price': 1.0001       # $1.00 price
        },
        ...
    }
    """
```

**Oracle Prices Dictionary:**
```python
def build_oracle_prices(rates_df):
    """
    Structure:
    {
        'USDC': 1.0001,
        'SUI':  3.4521,
        'DEEP': 0.0452,
        ...
    }
    Uses max price if multiple protocols report different values.
    """
```

### Stage 4: Position-Level Rendering

**Entry Point**: `render_position_expander()`

**Function Signature**:
```python
def render_position_expander(
    position: pd.Series,
    stats: Optional[Dict],
    rebalances: Optional[List],
    rate_lookup: Dict,
    oracle_prices: Dict,
    service,
    timestamp_seconds: int,
    strategy_type: Optional[str] = None,
    context: str = 'standalone',
    portfolio_id: Optional[str] = None,
    expanded: bool = False,
    basis_lookup: Optional[Dict] = None   # For perp strategies: spot_contract -> basis data
) -> None
```

**Key parameter note**: `basis_lookup` is populated from the `spot_perp_basis` table and passed through `render_positions_batch()`. It maps `spot_contract` to a dict of `{basis_bid, basis_ask, perp_bid, perp_ask, spot_bid, spot_ask}`. Used by perp strategies to compute basis-adjusted APR and basis PnL.

**Flow**:
```
render_position_expander()
├─ Build title with metrics (via build_position_expander_title())
│  ├─ Token flow: "USDC → DEEP → USDC"
│  ├─ Protocols: "Navi ↔ Suilend"
│  ├─ Entry APR: "Entry 12.34%"
│  ├─ Current APR: "Current 11.95%"
│  ├─ Net APR (realized): "Net APR 8.20%"
│  ├─ Value: "Value $10,245"
│  ├─ PnL: "PnL $245.32"
│  ├─ Earnings: "Earnings $312.45"
│  ├─ Base/Rewards breakdown
│  └─ Fees: "Fees $67.13"
│
├─ Compute basis-adjusted APR and basis PnL (perp strategies only)
│
├─ Render strategy summary metrics
│  ├─ Total PnL (Real + Unreal)
│  ├─ Total Earnings (Base + Reward)
│  ├─ Base Earnings
│  ├─ Reward Earnings
│  └─ Total Fees (+ Basis PnL for perp)
│
├─ Render LIVE SEGMENT
│  └─ Call strategy renderer → render_detail_table()
│     ├─ Row 1: Lend Token1 at Protocol A
│     ├─ Row 2: Borrow Token2 at Protocol A
│     ├─ Row 3: Lend Token2 at Protocol B
│     └─ Row 4: Borrow Token3 at Protocol B
│
├─ Render HISTORICAL SEGMENTS (if rebalances)
│  └─ For each rebalance: segment summary + detail table
│
└─ Render action buttons (context-aware)
   ├─ context='standalone': Rebalance, Close
   ├─ context='portfolio2': Rebalance, Close, Remove from Portfolio
   └─ context='portfolio':  View Portfolio, Rebalance, Close
```

---

## 7. Position Expander Details

### Title Format

The expander title is built by `build_position_expander_title()` and uses the ISO timestamp format:

```
▶ 2026-01-19 10:00:00 | USDC → DEEP → USDC | Navi ↔ Suilend |
  Entry 12.34% | Current 11.95% | Net APR 8.20% |
  Value $10,245.32 | PnL $245.32 | Earnings $312.45 |
  Base $285.12 | Rewards $27.33 | Fees $67.13
```

**Note:** The entry timestamp is formatted via `to_datetime_str(to_seconds(position['entry_timestamp']))`, which produces the full ISO format `YYYY-MM-DD HH:MM:SS` (e.g., `2026-01-19 10:00:00`), **not** an abbreviated date like "Jan 19, 2026".

For perp strategies, the title also includes:
```
... | Current 11.95% | Basis-adj 12.47% | ... | Basis PnL $+32.10
```

### Strategy Summary Metrics (5 or 6 Columns)

```
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Total PnL   │ Total       │ Base        │ Reward      │ Total Fees  │
│ (Real+Unr)  │ Earnings    │ Earnings    │ Earnings    │             │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ $245.32     │ $312.45     │ $285.12     │ $27.33      │ $67.13      │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

For perp strategies, a **Basis PnL** column is injected between Reward Earnings and Total Fees.

**Breakdown:**
- **Total PnL** = `current_value - deployment_usd`
- **Total Earnings** = `lend_earnings_1A + lend_earnings_2B`
- **Base Earnings** = `base_earnings_1A + base_earnings_2B`
- **Reward Earnings** = `reward_earnings_1A + reward_earnings_2B`
- **Total Fees** = `borrow_fees_2A + borrow_fees_3B`

### Detail Table (4-Leg Recursive Lending)

```
┌──────────┬───────┬────────┬────────────┬──────────────┬──────────────┬──────────────┬─────────────┬───────────────┬──────────┬──────────────┬─────────────┐
│ Protocol │ Token │ Action │ Entry Rate │ Segment Rate │ Live Rate    │ Entry Price  │ Live Price  │ Liq Price ($) │ Fee Rate │ Entry Liq    │ Live Liq    │
├──────────┼───────┼────────┼────────────┼──────────────┼──────────────┼──────────────┼─────────────┼───────────────┼──────────┼──────────────┼─────────────┤
│ Navi     │ USDC  │ Lend   │ 3.00%      │ 3.05%        │ 3.10%        │ $1.0000      │ $1.0001     │ N/A           │ 0.00%    │ N/A          │ N/A         │
│ Navi     │ DEEP  │ Borrow │ 8.50%      │ 8.45%        │ 8.40%        │ $0.0450      │ $0.0480     │ $0.0562       │ 0.05%    │ +28.4%       │ +17.1%      │
│ Suilend  │ DEEP  │ Lend   │ 12.00%     │ 12.05%       │ 12.10%       │ $0.0450      │ $0.0480     │ N/A           │ 0.00%    │ N/A          │ N/A         │
│ Suilend  │ USDC  │ Borrow │ 5.50%      │ 5.45%        │ 5.40%        │ $1.0000      │ $1.0001     │ $1.1250       │ 0.03%    │ +12.5%       │ +12.5%      │
└──────────┴───────┴────────┴────────────┴──────────────┴──────────────┴──────────────┴─────────────┴───────────────┴──────────┴──────────────┴─────────────┘
```

**Column Descriptions:**

| Column | Description | Source |
|--------|-------------|--------|
| Protocol | Protocol name | `position.protocol_a / protocol_b` |
| Token | Token symbol | `position.token1 / token2 / token3` |
| Action | Lend or Borrow | Leg type |
| Entry Rate | APR at position entry | `position.entry_lend_rate_1a`, etc. |
| Segment Rate | APR at segment start | `rebalance.opening_lend_rate_1a` |
| Live Rate | Current APR | `rate_lookup[(protocol, token)]['lend']` |
| Entry Price | Token price at entry | `position.entry_price_1a` |
| Live Price | Current token price | `get_price_with_fallback(token, protocol)` |
| Liq Price ($) | Liquidation price (borrow only) | `calculate_liquidation_price()` |
| Fee Rate (%) | Borrow fee (borrow only) | `rate_lookup[(protocol, token)]['borrow_fee']` |
| Entry Liq Distance | Liq distance at entry | `(liq_price - entry_price) / entry_price` |
| Live Liq Distance | Current liq distance | `(liq_price - live_price) / live_price` |

### Rebalance History

**Format**: Collapsed expanders, one per historical segment

```
▶ Segment 1: 2026-01-15 10:00:00 → 2026-01-20 14:30:00 (5.0 days)
  Realized PnL: $42.31 | Lend Earnings: $58.45 | Borrow Costs: $12.34 | Fees: $3.80
  [When expanded: Shows detail table for segment 1 with segment rates/prices]

▶ Segment 2: 2026-01-20 14:30:00 → 2026-01-25 09:00:00 (4.8 days)
  Realized PnL: $38.12 | Lend Earnings: $52.18 | Borrow Costs: $10.26 | Fees: $3.80
  [When expanded: Shows detail table for segment 2]

● Live Segment: 2026-01-25 09:00:00 → Now (3.2 days)
  [Detail table shown by default]
```

---

## 8. PnL Calculation Flow

PnL is calculated from historical time-series data using all snapshots between entry and current timestamp:

```
STEP 1: Load position metadata
  entry_timestamp, deployment_usd, L_A, B_A, L_B, B_B, tokens, protocols

STEP 2: Load historical rate timestamps
  SELECT DISTINCT timestamp FROM rates_snapshot
  WHERE timestamp >= entry_timestamp AND timestamp <= live_timestamp
  ORDER BY timestamp
  → Returns: [ts1, ts2, ts3, ..., tsN]
  → Defines time periods: [ts1→ts2], [ts2→ts3], ..., [tsN-1→tsN]

STEP 3: Calculate earnings per period (lend legs)
  For each period [T, T+1):
    period_years = (T+1 - T) / seconds_per_year
    lend_earnings_1A = token_amount_1A × price_1A × lend_rate_1A × period_years
    lend_earnings_2B = token_amount_2B × price_2B × lend_rate_2B × period_years

STEP 4: Calculate costs per period (borrow legs)
  For each period [T, T+1):
    borrow_costs_2A = token_amount_2A × price_2A × borrow_rate_2A × period_years
    borrow_costs_3B = token_amount_3B × price_3B × borrow_rate_3B × period_years

STEP 5: Calculate one-time fees (entry only)
  fee_2A = B_A × deployment × borrow_fee_2A
  fee_3B = B_B × deployment × borrow_fee_3B
  total_fees = fee_2A + fee_3B

STEP 6: Sum across all periods
  net_earnings = total_lend_earnings - total_borrow_costs - total_fees
  current_value = deployment_usd + net_earnings
  total_pnl = net_earnings

STEP 7: Calculate realized APR
  holding_days = (live_timestamp - entry_timestamp) / 86400
  annual_net_earnings = net_earnings × (365 / holding_days)
  realized_apr = annual_net_earnings / deployment_usd
```

**Key Points:**
- **Token amounts × prices** used, NOT `deployment × weight` (accounts for price drift)
- **Forward-looking rates**: Rate at timestamp T applies to period [T, T+1)
- **One-time fees**: Charged only at entry (not recurring)
- **Cached results**: Pre-calculated and stored in `position_statistics` table

**File Reference:**
- Calculation Logic: `analysis/position_service.py` — `calculate_position_value()`
- Statistics Storage: `position_statistics` table

---

## 9. Tab Implementations: Positions & Portfolio View

### Positions Tab

**File**: `dashboard/dashboard_renderer.py`
**Function**: `render_positions_table_tab(timestamp_seconds)`
**Dashboard Position**: Tab 5

**Implementation**:
```python
def render_positions_table_tab(timestamp_seconds):
    st.markdown("## 💼 Positions")

    conn = get_db_connection()
    service = PositionService(conn)
    active_positions = service.get_active_positions(timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    position_ids = active_positions['position_id'].tolist()
    render_positions_batch(
        position_ids=position_ids,
        timestamp_seconds=timestamp_seconds,
        context='standalone'
    )
```

**Key Points:**
- Simple wrapper around batch renderer
- Context: `'standalone'` (not part of portfolio)
- ~15 lines of code

### Portfolio View Tab

**File**: `dashboard/dashboard_renderer.py`
**Function**: `render_portfolio2_tab(timestamp_seconds)`
**Dashboard Position**: Tab 6

**Implementation** (from actual code):
```python
def render_portfolio2_tab(timestamp_seconds: int):
    st.markdown("## 📂 Portfolio View")
    st.markdown("Positions grouped by portfolio for portfolio-level analysis")

    conn = get_db_connection()
    service = PositionService(conn)
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        conn.close()
        return

    portfolio_ids = active_positions['portfolio_id'].unique()

    portfolios_dict = {}
    for pid in portfolio_ids:
        if pd.notna(pid):
            portfolio = get_portfolio_by_id(pid, conn)
            if portfolio is not None:
                portfolios_dict[pid] = portfolio

    # Virtual "Single Positions" portfolio for NULL portfolio_ids
    standalone_positions = active_positions[active_positions['portfolio_id'].isna()]
    if not standalone_positions.empty:
        portfolios_dict['__standalone__'] = {
            'portfolio_id': '__standalone__',
            'portfolio_name': 'Single Positions',
            'status': 'active',
            'is_virtual': True
        }

    # Sort: real portfolios first (newest first), standalone last
    portfolio_items = sorted(
        portfolios_dict.items(),
        key=lambda x: (
            x[0] == '__standalone__',
            -to_seconds(x[1].get('entry_timestamp', 0)) if x[0] != '__standalone__' else 0
        )
    )

    for portfolio_id, portfolio in portfolio_items:
        if portfolio_id == '__standalone__':
            portfolio_positions = standalone_positions
        else:
            portfolio_positions = active_positions[
                active_positions['portfolio_id'] == portfolio_id
            ]
        render_portfolio_expander(portfolio, portfolio_positions, timestamp_seconds)

    conn.close()
```

**Key Points:**
- Groups positions by `portfolio_id`
- Virtual "Single Positions" group for NULL portfolio_ids
- Real portfolios sorted newest first, standalone last
- Each portfolio rendered via `render_portfolio_expander()` which calls `render_positions_batch()`
- Context passed to batch renderer: `'portfolio2'`

---

## 10. Performance Optimizations

### Batch Loading Strategy

**Problem**: Naive approach queries database once per position (3×N queries)

**Solution**: Batch load all data upfront (3 queries total regardless of N)

### O(1) Lookup Strategy

**Problem**: Repeated DataFrame filtering is O(N) per lookup
```python
# Naive - O(N) per lookup
rate = rates_df[
    (rates_df['protocol'] == protocol) &
    (rates_df['token'] == token)
]['lend_total_apr'].iloc[0]
```

**Solution**: Build dictionary once, O(1) lookups
```python
# Build once (O(N))
rate_lookup = {(protocol, token): rates for ...}

# Lookup many times (O(1))
rate = rate_lookup[(protocol, token)]['lend']
```

**Speedup**: ~15× faster for typical cases (4 legs × 10 positions = 40 lookups)

### Connection Reuse

```python
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

---

## 11. Portfolio Allocator System

### Purpose

The Portfolio Allocator is a constraint-based portfolio construction system that:
- Analyzes yield opportunities from existing strategies
- Applies user-defined constraints on risk and diversification
- Generates optimal portfolio allocations using a greedy algorithm
- Persists portfolios to the database for tracking
- Calculates exposures based on lending positions only

### Architecture Overview

```
Dashboard Layer (dashboard_renderer.py)
├── Allocation Tab (Tab 2)
│   ├── Constraint Input Section
│   ├── Generate Portfolio Button
│   ├── Portfolio Preview
│   └── Save Portfolio Button
│
└── Portfolio View Tab (Tab 6)
    ├── Portfolio List (grouped by portfolio)
    ├── Portfolio Detail View
    └── Portfolio Actions

Service Layer
├── PortfolioAllocator (analysis/portfolio_allocator.py)
│   ├── calculate_blended_apr()
│   ├── calculate_adjusted_apr()
│   ├── select_portfolio()
│   └── calculate_portfolio_exposures()
│
└── PortfolioService (analysis/portfolio_service.py)
    ├── save_portfolio()
    ├── get_active_portfolios()
    ├── get_portfolio_by_id()
    └── get_portfolio_positions()

Database Layer
├── portfolios table
└── positions table (with portfolio_id FK)
```

### Data Flow

1. **User Input**: User sets portfolio size and constraints in Allocation tab (Tab 2)
2. **Strategy Loading**: System loads strategies from RateAnalyzer
3. **APR Calculations**: Calculate blended APR and adjusted APR for each strategy
4. **Ranking**: Sort strategies by adjusted APR (descending)
5. **Greedy Allocation**: Select strategies respecting all constraints
6. **Preview**: Display portfolio with exposures and metrics
7. **Save**: Persist portfolio to database
8. **View**: Display in Portfolio View tab (Tab 6) with full details

### Constraint Configuration

Constraints are configured in the **Allocation Tab** (Tab 2). Defaults are stored in `config/settings.py` (stablecoin preference multipliers are defined in `config/stablecoins.py`):

```python
# config/stablecoins.py — default multipliers
DEFAULT_STABLECOIN_PREFERENCES = {
    'USDC': 1.00,      # Preferred stablecoin (no penalty)
    'USDY': 0.95,      # 5% APR penalty
    'AUSD': 0.90,      # 10% APR penalty
    'FDUSD': 0.90,     # 10% APR penalty
    'suiUSDT': 0.90,   # 10% APR penalty
    'suiUSDe': 0.90,   # 10% APR penalty
    'USDsui': 0.90,    # 10% APR penalty
}

# config/settings.py
DEFAULT_ALLOCATION_CONSTRAINTS = {
    'token_exposure_limit': 0.30,       # 30%
    'protocol_exposure_limit': 0.40,    # 40%
    'max_single_allocation_pct': 0.40,  # 40%
    'max_strategies': 5,
    'min_apy_confidence': 0.70,
    'apr_weights': {
        'net_apr': 0.30,
        'apr5':    0.30,
        'apr30':   0.30,
        'apr90':   0.10
    },
    'stablecoin_preferences': DEFAULT_STABLECOIN_PREFERENCES,  # From config/stablecoins.py
    'token_exposure_overrides': {}     # Empty by default
}
```

#### Constraint Types

**1. Portfolio Size**
- Input: Number input (USD), default $10,000
- Purpose: Total capital to allocate across selected strategies

**2. Token Exposure Limit**
- Input: Slider (0-100%), default 30%
- Purpose: Maximum exposure to any single token
- Calculation: Aggregate by `token_contract` (not symbol)
- Override: `token_exposure_overrides = {"USDC": 0.50, "USDT": 0.40}`

**3. Protocol Exposure Limit**
- Input: Slider (0-100%), default 40%
- Purpose: Maximum exposure to any single protocol

**4. Max Number of Strategies**
- Input: Number (1-20), default 10
- Note: Actual count may be lower if constraints prevent more allocations

**5. Stablecoin Preferences**
- Input: `{token_symbol: multiplier}` where multiplier is 0.0-1.0
- Default multipliers defined in `config/stablecoins.py` (`DEFAULT_STABLECOIN_PREFERENCES`)
- Purpose: De-prioritize strategies containing certain stablecoins
- Example: `{"USDC": 0.8}` applies 20% penalty to strategies with USDC
- If strategy contains multiple stablecoins from preferences, uses **lowest** multiplier
- Formula: `adjusted_apr = blended_apr × stablecoin_multiplier`

**6. APR Blend Weights**
- Input: Four percentage inputs summing to 100%
- Default: `net_apr=25%, apr5=25%, apr30=25%, apr90=25%`
- Auto-Normalization: Dashboard normalizes weights automatically

**Example APR Weight Configurations:**
- **Aggressive**: `net_apr=70%, apr5=20%, apr30=10%, apr90=0%` (focus on current rates)
- **Balanced**: `net_apr=25%, apr5=25%, apr30=25%, apr90=25%` (equal weight)
- **Conservative**: `net_apr=10%, apr5=10%, apr30=40%, apr90=40%` (focus on stability)

---

## 12. Allocation Algorithm

### Algorithm Type: Greedy Selection

The allocator uses a **greedy algorithm** that selects strategies one at a time in order of adjusted APR, respecting all constraints.

### Algorithm Steps

```python
def select_portfolio(portfolio_size, constraints):
    # Step 1: Filter by confidence (if implemented)
    strategies = filter_by_confidence(strategies, min_confidence=constraints['min_apy_confidence'])

    # Step 2: Calculate blended APR for each strategy
    for strategy in strategies:
        strategy['blended_apr'] = (
            strategy['net_apr'] * apr_weights['net_apr'] +
            strategy['apr5']    * apr_weights['apr5'] +
            strategy['apr30']   * apr_weights['apr30'] +
            strategy['apr90']   * apr_weights['apr90']
        )

    # Step 3: Calculate adjusted APR (apply stablecoin penalty)
    for strategy in strategies:
        stablecoin_multiplier = get_stablecoin_multiplier(strategy, stablecoin_preferences)
        strategy['adjusted_apr'] = strategy['blended_apr'] * stablecoin_multiplier

    # Step 4: Sort by adjusted APR (descending)
    strategies = sort_by(strategies, 'adjusted_apr', descending=True)

    # Step 5: Greedy allocation
    selected = []
    allocated_capital = 0
    token_exposures = {}
    protocol_exposures = {}

    for strategy in strategies:
        if len(selected) >= max_strategies:
            break

        max_amount = calculate_max_allocation(
            strategy,
            remaining_capital=portfolio_size - allocated_capital,
            token_exposures=token_exposures,
            protocol_exposures=protocol_exposures,
            constraints=constraints
        )

        if max_amount > 0:
            selected.append({**strategy, 'allocation_usd': max_amount})
            allocated_capital += max_amount
            update_exposures(strategy, max_amount, token_exposures, protocol_exposures)

    return selected
```

### Max Allocation Calculation

```python
def calculate_max_allocation(strategy, remaining_capital, token_exposures,
                             protocol_exposures, constraints, portfolio_size):
    max_amount = remaining_capital

    # Constraint 1: Strategy max size (liquidity limit)
    if 'max_size_usd' in strategy:
        max_amount = min(max_amount, strategy['max_size_usd'])

    # Constraint 2: Token exposure limits (lending weights only: l_a, l_b)
    for token_num in [1, 2, 3]:
        token_contract = strategy[f'token{token_num}_contract']
        token_symbol   = strategy[f'token{token_num}']
        weight = strategy['l_a'] if token_num == 1 else (strategy['l_b'] if token_num == 2 else 0.0)
        # token3 is only borrowed, not lent — no exposure weight

        if token_symbol in constraints['token_exposure_overrides']:
            token_limit = portfolio_size * constraints['token_exposure_overrides'][token_symbol]
        else:
            token_limit = portfolio_size * constraints['token_exposure_limit']

        current_exposure = token_exposures.get(token_contract, 0.0)
        remaining_room   = token_limit - current_exposure
        max_allocation_for_token = remaining_room / weight if weight > 0 else float('inf')
        max_amount = min(max_amount, max_allocation_for_token)

    # Constraint 3: Protocol exposure limits
    protocol_limit = portfolio_size * constraints['protocol_exposure_limit']
    for protocol, weight in [(strategy['protocol_a'], strategy['l_a']),
                              (strategy['protocol_b'], strategy['l_b'])]:
        current_exposure = protocol_exposures.get(protocol, 0.0)
        remaining_room   = protocol_limit - current_exposure
        max_allocation_for_protocol = remaining_room / weight if weight > 0 else float('inf')
        max_amount = min(max_amount, max_allocation_for_protocol)

    return max(0.0, max_amount)
```

### Key Algorithm Properties

1. **Greedy**: Selects highest adjusted APR first
2. **Constraint-Respecting**: Never violates any constraint
3. **Deterministic**: Same inputs always produce same output
4. **Fast**: O(n log n) base complexity (sorting), O(n²) with iterative updates
5. **Transparent**: Users see exactly why each strategy was selected
6. **Liquidity-Aware**: Accounts for liquidity consumption via iterative updates

### Iterative Liquidity Updates

**Status**: Implemented and Active
**Feature Flag**: `DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES` in `config/settings.py` (default: True)

**Note**: This is a DEBUG flag for testing/comparison only. Once validated, this flag will be removed and iterative updates will be always-on (correct behavior).

#### Problem Statement

The original greedy algorithm calculated `max_size` once per strategy based on initial `available_borrow` values. This had a critical flaw:

```
Initial State: WAL available on Pebble = $100,000

Strategy 1: USDC/WAL/USDC on Pebble/Suilend
  max_size = $100,000 / 1.0 = $100,000 → Allocated: $100,000 WAL borrowed ✓

Strategy 2: USDC/WAL/USDC on Pebble/AlphaFi
  max_size = $100,000 / 1.0 = $100,000 → Allocated: $100,000 WAL borrowed ❌
  (WAL already exhausted — over-borrowed by $100k!)
```

#### Solution: Token×Protocol Matrix

The allocator maintains a **Token×Protocol matrix** tracking available borrow liquidity and updates it after each allocation.

**Matrix Structure:**
```
         Navi      Suilend   Pebble    AlphaFi
USDC     500000    800000    1000000   300000
WAL      150000    200000    100000    50000
DEEP     75000     100000    50000     25000
```

**Updated Algorithm:**
```python
def select_portfolio(portfolio_size, constraints, enable_iterative_updates=True):
    # Steps 1-4: Filter, calculate APRs, sort — unchanged

    # Initialize available_borrow matrix
    if enable_iterative_updates:
        available_borrow = prepare_available_borrow_matrix(strategies)

    selected = []
    for strategy in strategies:
        if len(selected) >= max_strategies:
            break

        max_amount = calculate_max_allocation(strategy, ...)

        if max_amount > 0:
            selected.append({**strategy, 'allocation_usd': max_amount})
            update_exposures(strategy, max_amount, token_exposures, protocol_exposures)

            # Update liquidity and recalculate max_sizes for remaining strategies
            if enable_iterative_updates:
                update_available_borrow(strategy, max_amount, available_borrow)
                recalculate_max_sizes(remaining_strategies, available_borrow)

    return selected
```

#### Implementation Details

**1. Prepare Available Borrow Matrix** (`_prepare_available_borrow_matrix`):
- Collect all unique tokens (token2, token3) and protocols (protocol_a, protocol_b)
- Create DataFrame with tokens as index, protocols as columns
- Populate with `available_borrow_2a` and `available_borrow_3b` values
- Use `max()` when aggregating (multiple strategies may report different values)

**2. Update Available Borrow** (`_update_available_borrow`):
```python
borrow_2A_usd = allocation_amount * b_a  # How much token2 borrowed per $1
borrow_3B_usd = allocation_amount * b_b  # How much token3 borrowed per $1

available_borrow.loc[token2, protocol_a] -= borrow_2A_usd
available_borrow.loc[token3, protocol_b] -= borrow_3B_usd
# Clamp to prevent negative values (log warning if over-borrowed)
```

**3. Recalculate Max Sizes** (`_recalculate_max_sizes`):
```python
max_size = min(
    available_borrow[token2][protocol_a] / b_a,  # b_a=0: inf (no constraint)
    available_borrow[token3][protocol_b] / b_b   # b_b=0: inf (no constraint)
)
```
Only recalculates strategies with `index > current_index` (remaining strategies).

#### Before vs After Comparison

```
WITHOUT Iterative Updates:
Strategy 1: max_size=$100k → allocate $100k → borrow $100k WAL ✓
Strategy 2: max_size=$100k → allocate $100k → borrow $100k WAL ❌ Over-borrowed!
Strategy 3: max_size=$100k → allocate $100k → borrow $100k WAL ❌ Over-borrowed!
Total WAL borrowed: $300k (available: $100k) ❌

WITH Iterative Updates:
Strategy 1: max_size=$100k → allocate $100k → borrow $100k WAL ✓
            → Update: WAL available = $0
            → Recalculate: Strategy 2 max_size = $0, Strategy 3 max_size = $0
Strategy 2: max_size=$0 → allocate $0 ✓
Strategy 3: max_size=$0 → allocate $0 ✓
Total WAL borrowed: $100k (available: $100k) ✅
```

#### Configuration & Testing

```python
# config/settings.py
DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES = get_bool_env(
    'DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES', default=True
)

# Runtime control:
portfolio, debug = allocator.select_portfolio(
    portfolio_size=100000, constraints=constraints, enable_iterative_updates=True
)
```

**Test Script**: `Scripts/test_iterative_updates.py`

**Performance:**
- Without updates: O(N log N) — dominated by sorting
- With updates: O(N²) — recalculate remaining strategies after each allocation
- Typical overhead: 10 strategies <50ms, 100 strategies <500ms

#### Future: Interest Rate Model (IRM) Effects

**Current**: Only liquidity updates implemented.

**Planned**: Account for IRM effects where borrowing from a protocol increases utilization, which raises borrow rates (affecting net APR for remaining strategies).

**Extension Point**: `_apply_market_impact_adjustments()` method has placeholder for phase 2:
```python
def _apply_market_impact_adjustments(strategy, allocation, market_state):
    # Phase 1: Liquidity updates (implemented)
    _update_available_borrow(strategy, allocation, market_state['available_borrow'])
    # Phase 2: Rate updates (future)
    # if 'rate_curves' in market_state:
    #     _update_interest_rate_curves(...)
```

---

## 13. Exposure Calculations

### Critical Design Principle: Lending Only

**Exposures count only lending positions, not borrows.**

Rationale:
- Lending = actual capital at risk on a protocol or in a token
- Borrowing = liability, but capital is immediately re-lent elsewhere
- Counting both would double-count exposure

### Token Exposure Calculation (Legacy/Constraint Use)

```python
def calculate_token_exposure(portfolio_df, portfolio_size):
    """Token exposure = amount of capital lent in that token across all strategies."""
    token_exposures = {}
    for _, strategy in portfolio_df.iterrows():
        allocation = strategy['allocation_usd']
        # Token1: Lent to Protocol A
        token1_lend_amount = allocation * strategy['l_a']
        token_exposures[token1_contract]['usd'] += token1_lend_amount
        # Token2: Lent to Protocol B
        token2_lend_amount = allocation * strategy['l_b']
        token_exposures[token2_contract]['usd'] += token2_lend_amount
        # Token3: Only borrowed, NOT lent — NO EXPOSURE
```

### Token2 De-Leveraged Exposure

**Definition (February 2026)**: Token2 exposure measures the **de-leveraged exposure** to token2 (the borrowed token).

**Formula:**

```
Token2 Exposure = Σ(Ci × B_A / L_A)
```

Since `B_A = L_A × r_A`, this simplifies to:

```
Token2 Exposure = Σ(Ci × r_A)
```

where **r_A** is the collateral ratio at Protocol A.

**Example:**
- Strategy 1: C1=$5,000, r_A=0.70 → Token2 exposure = $5,000 × 0.70 = $3,500
- Strategy 2: C2=$3,000, r_A=0.80 → Token2 exposure = $3,000 × 0.80 = $2,400
- Total = $5,900 (59% of $10,000 portfolio)

### Stablecoin Exposure (Net Lending Position)

**Definition (February 2026)**: Net lending position for a stablecoin, accounting for both lending and borrowing.

**Formula:**

```
Stablecoin Exposure$ = Σ(Ci × L_A) - Σ(Ci × B_B)
```

Where:
- First sum: Strategies where stablecoin is Token1 (lent to Protocol A)
- Second sum: Strategies where stablecoin is Token3 (borrowed from Protocol B)

**Key Insight: Exposure can be negative.**
- Positive: Net lending position (lending more than borrowing)
- Negative: Net borrowing position
- Zero: Balanced

**Example** (Strategy: USDC/WAL/suiUSDT, L_A=1.5, B_B=0.5):
- USDC exposure = +1.5 × c1 (lending USDC)
- suiUSDT exposure = -0.5 × c1 (borrowing suiUSDT)

### Protocol Exposure (Normalized to Deployment)

**Definition (February 2026)**: Capital exposure to each protocol, with Protocol B de-leveraged relative to Protocol A.

**Formula:**
- **Protocol A contribution**: `ci` (full allocation)
- **Protocol B contribution**: `ci × L_B / L_A = ci × r_A` (de-leveraged)

**Example** (Strategy: USDC/WAL/suiUSDT on Navi ↔ Suilend, L_A=1.5, L_B=1.05, allocation=$5,000):
- Navi (Protocol A): $5,000 (full allocation) → 50% of $10k portfolio
- Suilend (Protocol B): $5,000 × (1.05/1.5) = $3,500 → 35% of $10k portfolio

**Intuition:** Protocol A receives initial capital ($1 exposure). Protocol B receives borrowed capital proportional to collateral ratio (r_A × $1 exposure).

### Protocol Exposure Calculation (Code)

```python
def calculate_protocol_exposure(portfolio_df, portfolio_size):
    protocol_exposures = {}
    for _, strategy in portfolio_df.iterrows():
        allocation = strategy['allocation_usd']
        # Protocol A exposure = allocation × l_a
        protocol_exposures[protocol_a]['usd'] += allocation * strategy['l_a']
        # Protocol B exposure = allocation × l_b
        protocol_exposures[protocol_b]['usd'] += allocation * strategy['l_b']
```

---

## 14. Portfolio Persistence & Dashboard Interface

### Save Workflow

1. User generates portfolio in Allocation tab
2. Portfolio preview displays with metrics and strategies
3. User clicks "Save Portfolio"
4. System prompts for portfolio name
5. `PortfolioService.save_portfolio()` creates database records
6. Success message with link to Portfolio View tab
7. Portfolio appears in Portfolio View tab (Tab 6)

### What Gets Saved

**Portfolio-level** (`portfolios` table): ID, name, status, entry timestamp, target size, actual allocated amount, utilization %, entry weighted net APR, constraints JSON, notes.

**Strategy-level** (`positions` table): Each strategy creates a position record linked via `portfolio_id` FK. No separate `portfolio_strategies` table is used.

### Primary Metric: Entry Weighted Net APR

```python
entry_weighted_net_apr = sum(
    strategy['net_apr'] × strategy['allocation_usd']
    for strategy in portfolio
) / total_allocated
```

This uses **net APR** (not blended/adjusted APR) because:
- Blended/adjusted APR is used for **ranking** during selection
- Net APR is the **actual rate** earning now
- For performance tracking, we want actual returns

### Allocation Tab UI (Tab 2)

```
┌─────────────────────────────────────────────────────┐
│ Portfolio Size (USD)                                │
│ [        10000        ]                             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ⚙️ Portfolio Constraints                            │
├─────────────────────────────────────────────────────┤
│ Max Token Exposure    │ Max Protocol Exposure        │
│ [=======○========] 30%│ [=======○========] 40%      │
│ Max # Strategies      │                             │
│ [    10    ]          │                             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ APR Blend Weights (must sum to 100%)               │
├─────────────────────────────────────────────────────┤
│ Net APR:    [25] %   │ 5-Day APR:  [25] %          │
│ 30-Day APR: [25] %   │ 90-Day APR: [25] %          │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Stablecoin Preferences (optional)                   │
│ Token Symbol │ Multiplier (0-1)                     │
│ USDC         │ [0.8]                                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Token Exposure Overrides (optional)                 │
│ Token Symbol │ Max Exposure (%)                     │
│ USDC         │ [50]                                 │
└─────────────────────────────────────────────────────┘

              [🎲 Generate Portfolio]
```

#### After Generation

```
✅ Portfolio Generated
Strategies: 5 | Allocated: $9,850 / $10,000 (98.5%) | Avg Net APR: 8.42%

Token Exposure:
┌───────────┬──────────┬──────┬─────────┐
│ Token     │ USD      │ %    │ Limit % │
├───────────┼──────────┼──────┼─────────┤
│ USDC      │ $2,950   │ 29.9%│ 30%     │
│ SUI       │ $2,100   │ 21.3%│ 30%     │
└───────────┴──────────┴──────┴─────────┘

Protocol Exposure:
┌───────────┬──────────┬──────┬─────────┐
│ Protocol  │ USD      │ %    │ Limit % │
├───────────┼──────────┼──────┼─────────┤
│ Navi      │ $3,940   │ 39.9%│ 40%     │
│ AlphaFi   │ $3,200   │ 32.5%│ 40%     │
└───────────┴──────────┴──────┴─────────┘

              [💾 Save Portfolio]
```

### Portfolio View in Tab 6

Portfolios are listed as expandable sections:

```
▼ Conservative Q1 2026
  Entry: 2026-01-19 10:00:00 | Strategies: 5 | Allocated: $10,000
  Entry Net APR: 8.42%

  Portfolio Details:
  • Status: Active
  • Target Size: $10,000 | Actual: $9,850 (98.5%)
  • Entry Weighted Net APR: 8.42%

  Constraints Used:
  • Token Exposure Limit: 30%
  • Protocol Exposure Limit: 40%
  • Max Strategies: 10

  [Positions rendered here via render_positions_batch()]
```

### Full Interaction Flow

```
User: Set constraints → click "Generate Portfolio"
  ↓
render_allocation_tab()
  ↓
PortfolioAllocator.select_portfolio(portfolio_size, constraints)
  ├─> calculate_blended_apr() for each strategy
  ├─> calculate_adjusted_apr() for each strategy
  ├─> Sort by adjusted_apr
  └─> Greedy loop with iterative liquidity updates
  ↓
render_portfolio_preview()
  ├─> Summary metrics
  └─> PortfolioAllocator.calculate_portfolio_exposures()
  ↓
User clicks "Save Portfolio"
  ↓
PortfolioService.save_portfolio()
  ├─> INSERT INTO portfolios table
  └─> Return portfolio_id
  ↓
Tab 6: render_portfolio2_tab()
  └─> Grouped positions with batch rendering
```

---

## 15. Database Schema (All Tables)

### Table: positions

**Purpose:** Store immutable entry state and mutable current state.

```sql
-- Core identification
position_id TEXT PRIMARY KEY              -- UUID
status TEXT                               -- 'active' | 'closed' | 'liquidated'
strategy_type TEXT                        -- 'recursive_lending', 'noloop', 'stablecoin', etc.
entry_timestamp TIMESTAMP                 -- When position created
deployment_usd DECIMAL(20,10)            -- USD amount deployed

-- Portfolio linkage
portfolio_id TEXT DEFAULT NULL            -- FK to portfolios (added Feb 2026)

-- Position Weights (constant throughout position life)
l_a DECIMAL(10,6)                        -- Lend multiplier Protocol A
b_a DECIMAL(10,6)                        -- Borrow multiplier Protocol A
l_b DECIMAL(10,6)                        -- Lend multiplier Protocol B
b_b DECIMAL(10,6)                        -- Borrow multiplier Protocol B

-- Token & Protocol identifiers
token1 TEXT, token1_contract TEXT         -- Token lent to Protocol A
token2 TEXT, token2_contract TEXT         -- Token borrowed from A, lent to B
token3 TEXT, token3_contract TEXT         -- Token borrowed from B (NULL for noloop)
protocol_a TEXT                           -- First protocol
protocol_b TEXT                           -- Second protocol

-- Entry State (immutable — all captured at creation)
entry_lend_rate_1a DECIMAL(10,6)         -- Lend rate token1 at protocol_a
entry_borrow_rate_2a DECIMAL(10,6)       -- Borrow rate token2 at protocol_a
entry_lend_rate_2b DECIMAL(10,6)         -- Lend rate token2 at protocol_b
entry_borrow_rate_3b DECIMAL(10,6)       -- Borrow rate token3 at protocol_b

entry_price_1a DECIMAL(20,10)            -- All 4 leg prices at entry
entry_price_2a DECIMAL(20,10)
entry_price_2b DECIMAL(20,10)
entry_price_3b DECIMAL(20,10)

-- Token amounts calculated at entry: weight × deployment / price
entry_token_amount_1a DECIMAL(30,10)     -- All 4 leg token amounts at entry (added Feb 2026)
entry_token_amount_2a DECIMAL(30,10)
entry_token_amount_2b DECIMAL(30,10)
entry_token_amount_3b DECIMAL(30,10)

entry_collateral_ratio_1a DECIMAL(10,6)  -- Collateral ratios at entry
entry_collateral_ratio_2b DECIMAL(10,6)
entry_liquidation_threshold_1a DECIMAL(10,6)  -- Liq thresholds at entry
entry_liquidation_threshold_2b DECIMAL(10,6)

-- Entry APR values
entry_net_apr DECIMAL(10,6)
entry_apr5 DECIMAL(10,6)
entry_apr30 DECIMAL(10,6)
entry_apr90 DECIMAL(10,6)

-- Rebalance Tracking (mutable)
accumulated_realised_pnl DECIMAL(20,10) DEFAULT 0.0
rebalance_count INTEGER DEFAULT 0
last_rebalance_timestamp TIMESTAMP

-- Closure (mutable)
close_timestamp TIMESTAMP
close_reason TEXT
close_notes TEXT

-- Timestamps
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Token amount formula:**
```
entry_token_amount = weight × deployment_usd / token_price_usd
Example: l_a=1.45, deployment=$10,000, SUI price=$3.20
  → 1.45 × 10000 / 3.20 = 4,531.25 SUI
```

**Backfill script:** `Scripts/backfill_position_token_amounts.py` — for existing positions added before the `entry_token_amount` columns.

**Design Pattern:** Event Sourcing — entry state is frozen forever.

**File:** `data/schema.sql` lines 166-273

### Table: position_rebalances

**Purpose:** Store immutable historical segments (append-only).

```sql
rebalance_id TEXT PRIMARY KEY            -- UUID
position_id TEXT                         -- FK to positions
sequence_number INTEGER                  -- 1, 2, 3, ... (preserves order)

-- Timing
opening_timestamp TIMESTAMP              -- Segment start
closing_timestamp TIMESTAMP              -- Segment end

-- Weights (copied from position)
deployment_usd DECIMAL(20,10)
l_a DECIMAL(10,6)
b_a DECIMAL(10,6)
l_b DECIMAL(10,6)
b_b DECIMAL(10,6)

-- Opening State (rates & prices at opening_timestamp)
opening_lend_rate_1a DECIMAL(10,6)      -- All 4 legs
opening_borrow_rate_2a DECIMAL(10,6)
opening_lend_rate_2b DECIMAL(10,6)
opening_borrow_rate_3b DECIMAL(10,6)
opening_price_1a DECIMAL(20,10)         -- All 4 leg prices
opening_price_2a DECIMAL(20,10)
opening_price_2b DECIMAL(20,10)
opening_price_3b DECIMAL(20,10)

-- Closing State (rates & prices at closing_timestamp)
closing_lend_rate_1a DECIMAL(10,6)      -- All 4 legs
closing_borrow_rate_2a DECIMAL(10,6)
closing_lend_rate_2b DECIMAL(10,6)
closing_borrow_rate_3b DECIMAL(10,6)
closing_price_1a DECIMAL(20,10)
closing_price_2a DECIMAL(20,10)
closing_price_2b DECIMAL(20,10)
closing_price_3b DECIMAL(20,10)

-- Token Amounts at segment boundaries
entry_token_amount_1a DECIMAL(20,10)    -- All 4 legs at segment opening
entry_token_amount_2a DECIMAL(20,10)
entry_token_amount_2b DECIMAL(20,10)
entry_token_amount_3b DECIMAL(20,10)
exit_token_amount_1a DECIMAL(20,10)     -- All 4 legs at segment closing
exit_token_amount_2a DECIMAL(20,10)
exit_token_amount_2b DECIMAL(20,10)
exit_token_amount_3b DECIMAL(20,10)

-- Realised Metrics (calculated once, never updated)
realised_pnl DECIMAL(20,10)
realised_fees DECIMAL(20,10)
realised_lend_earnings DECIMAL(20,10)
realised_borrow_costs DECIMAL(20,10)

-- Metadata
rebalance_reason TEXT
rebalance_notes TEXT
```

**Design Pattern:** Append-Only — records never updated after creation.

**File:** `data/schema.sql` lines 275-372

### Table: position_statistics

**Purpose:** Pre-calculated summary statistics for dashboard (cache table).

```sql
position_id TEXT                         -- FK to positions (no constraint)
timestamp TIMESTAMP                      -- Timestamp these stats are FOR (viewing time)

-- Core Metrics
total_pnl DECIMAL(20,10)                -- Realized + Unrealized
total_earnings DECIMAL(20,10)           -- Total lend earnings - borrow costs
base_earnings DECIMAL(20,10)            -- Base APR portion of earnings
reward_earnings DECIMAL(20,10)          -- Reward APR portion of earnings
total_fees DECIMAL(20,10)               -- All borrow fees

-- Position Value
current_value DECIMAL(20,10)            -- deployment_usd + total_pnl

-- APRs
realized_apr DECIMAL(10,6)              -- Annualized realized return
current_apr DECIMAL(10,6)               -- Current rate-based APR

-- Segment Breakdown
live_pnl DECIMAL(20,10)                 -- Unrealized from current segment
realized_pnl DECIMAL(20,10)             -- Sum of closed segments

-- Metadata
calculation_timestamp TIMESTAMP         -- When calculation was performed (audit)
```

**Design Pattern:** Cache Table — calculated during data pipeline, stored for fast loading, can be recalculated on-demand.

**File:** `data/schema.sql` lines 374-408

### Table: rates_snapshot

**Purpose:** Historical rates and prices for all protocols/tokens (immutable).

```sql
timestamp TIMESTAMP                      -- Snapshot time
protocol TEXT                            -- 'Navi', 'AlphaFi', 'Suilend', etc.
token TEXT                               -- Token symbol
token_contract TEXT                      -- Token contract address (identity)

lend_base_apr DECIMAL(10,6)             -- Base lending rate
lend_reward_apr DECIMAL(10,6)           -- Reward lending rate
lend_total_apr DECIMAL(10,6)            -- Total lending rate (base + reward)

borrow_base_apr DECIMAL(10,6)           -- Base borrow rate
borrow_reward_apr DECIMAL(10,6)         -- Reward borrow rate
borrow_total_apr DECIMAL(10,6)          -- Total borrow rate

borrow_fee DECIMAL(10,6)                -- Upfront borrow fee (one-time)
price_usd DECIMAL(20,10)                -- Token price in USD

collateral_ratio DECIMAL(10,6)          -- Max LTV
liquidation_threshold DECIMAL(10,6)     -- Liquidation LTV
borrow_weight DECIMAL(10,6)             -- Risk adjustment factor
```

**File:** `data/schema.sql` lines 1-85

**Indexes:**
- `rates_snapshot`: timestamp, protocol, token, combined
- `positions`: status, entry_timestamp, protocols, tokens
- `position_rebalances`: position_id, sequence_number, timestamps
- `position_statistics`: position_id, timestamp, combined

### Table: portfolios

```sql
CREATE TABLE IF NOT EXISTS portfolios (
    -- Portfolio Identification
    portfolio_id TEXT PRIMARY KEY,
    portfolio_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'closed', 'archived')),

    -- Ownership
    is_paper_trade BOOLEAN NOT NULL DEFAULT TRUE,
    user_id TEXT,

    -- Creation & Entry
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    entry_timestamp TIMESTAMP NOT NULL,

    -- Portfolio Size
    target_portfolio_size DECIMAL(20, 10) NOT NULL,
    actual_allocated_usd DECIMAL(20, 10) NOT NULL,
    utilization_pct DECIMAL(5, 2) NOT NULL,

    -- PRIMARY METRIC: Entry Net APR
    entry_weighted_net_apr DECIMAL(10, 6) NOT NULL,

    -- Constraints Used (JSON)
    constraints_json TEXT NOT NULL,

    -- Performance Tracking
    accumulated_realised_pnl DECIMAL(20, 10) DEFAULT 0.0,
    rebalance_count INTEGER DEFAULT 0,
    last_rebalance_timestamp TIMESTAMP,

    -- Closure Tracking
    close_timestamp TIMESTAMP,
    close_reason TEXT,
    close_notes TEXT,

    -- User Notes
    notes TEXT,

    -- Timestamps
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portfolios_status ON portfolios(status);
CREATE INDEX IF NOT EXISTS idx_portfolios_entry_time ON portfolios(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(portfolio_name);
```

### positions Table: portfolio_id Column (FK)

```sql
-- Added to positions table (Feb 2026)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS portfolio_id TEXT DEFAULT NULL;

ALTER TABLE positions
ADD CONSTRAINT fk_positions_portfolio
FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);
```

**Relationship:** One portfolio has many positions. `ON DELETE SET NULL` — if portfolio deleted, positions remain orphaned (not deleted).

### Schema Diagram

```
┌──────────────────┐
│  rates_snapshot  │  ← Historical rates & prices (immutable)
└────────┬─────────┘
         │ (referenced by timestamp)
         ↓
┌──────────────────┐       ┌──────────────┐
│    portfolios    │       │              │
│ PK: portfolio_id │       │              │
└────────┬─────────┘       │              │
         │ (FK)            │              │
         ↓                 │              │
┌──────────────────┐       │              │
│    positions     │  ← Main position records (entry state immutable)
│ PK: position_id  │
│ FK: portfolio_id │
└────────┬─────────┘
         │
         ├─────────────────────────┐
         ↓                         ↓
┌─────────────────────┐   ┌──────────────────────┐
│ position_rebalances │   │ position_statistics  │
│ FK: position_id     │   │ FK: position_id      │
│ (append-only)       │   │ (pre-calculated)     │
└─────────────────────┘   └──────────────────────┘
```

---

## 16. Key Functions & Implementation

### Position Service Functions

**File:** `analysis/position_service.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `create_position()` | 115-350 | Create new position from strategy row |
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
| `compute_basis_adjusted_current_apr()` | — | Compute basis-adjusted APR for perp strategies |
| `calculate_basis_pnl()` | — | Calculate basis PnL for perp strategies |

### Capture Rebalance Snapshot

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

    # Get closing rates & prices from rates_snapshot
    closing_rates = query_rates(closing_timestamp, protocols, tokens)

    # Calculate realized metrics for this segment
    pv_result = calculate_position_value(position, opening_timestamp, closing_timestamp)

    # Calculate token amounts (weight × deployment / price)
    entry_amounts = {leg: (weight * deployment) / opening_price for each leg}
    exit_amounts  = {leg: (weight * deployment) / closing_price for each leg}

    return {
        'opening_timestamp': opening_timestamp,
        'closing_timestamp': closing_timestamp,
        'opening_lend_rate_1a': ..., 'closing_lend_rate_1a': ...,
        'entry_token_amount_1a': ..., 'exit_token_amount_1a': ...,
        'realised_pnl': pv_result['net_earnings'],
        'realised_fees': pv_result['fees'],
        'realised_lend_earnings': pv_result['lend_earnings'],
        'realised_borrow_costs': pv_result['borrow_costs']
    }
```

### Close Position

```python
def close_position(position_id, close_timestamp, close_reason, close_notes):
    position = get_position_by_id(position_id)
    if position['status'] != 'active':
        raise ValueError("Position is not active")

    # Capture final snapshot
    snapshot = capture_rebalance_snapshot(position, close_timestamp)

    # Create final rebalance record
    create_rebalance_record(
        position_id, snapshot,
        rebalance_reason=f'position_closed:{close_reason}',
        rebalance_notes=close_notes
    )

    # Update position status
    UPDATE positions SET
        status = 'closed',
        close_timestamp = close_timestamp,
        close_reason = close_reason,
        close_notes = close_notes,
        updated_at = CURRENT_TIMESTAMP
    WHERE position_id = position_id
```

### Dashboard Renderer Functions

**File:** `dashboard/dashboard_renderer.py`

| Function | Lines | Purpose |
|----------|-------|---------|
| `render_positions_table_tab()` | 1107-2700 | Main entry point for Positions tab |
| `render_portfolio2_tab()` | 3845+ | Portfolio View tab (positions grouped by portfolio) |
| `render_allocation_tab()` | 2445+ | Allocation tab (Tab 2) |
| `render_portfolio_expander()` | — | Single portfolio expander |
| `get_portfolio_by_id()` | — | Load portfolio metadata from database |
| `render_rate_tables_tab()` | — | Rate Tables tab (Tab 3) |
| `render_zero_liquidity_tab()` | — | Zero Liquidity tab (Tab 4) |
| `render_oracle_prices_tab()` | — | Oracle Prices tab (Tab 7) |
| `render_pending_deployments_tab()` | — | Pending Deployments tab (Tab 8) |
| `render_dashboard()` | 3940+ | Main dashboard renderer (all 9 tabs) |

### Position Renderers Functions

**File:** `dashboard/position_renderers.py`

```python
# Main entry point
def render_positions_batch(position_ids, timestamp_seconds, context):
    """Batch render multiple positions with optimized data loading."""

# Convenience wrapper
def render_position_single(position_id, timestamp_seconds, context):
    """Single position — less efficient than batch, prefer batch when possible."""

# Core renderer
def render_position_expander(position, stats, rebalances, rate_lookup, oracle_prices,
                              service, timestamp_seconds, strategy_type, context,
                              portfolio_id, expanded, basis_lookup):
    """Render single position with full detail."""

# Title builder
def build_position_expander_title(position, stats, strategy_type, include_timestamp,
                                   current_apr_incl_basis, basis_pnl):
    """Build ISO timestamp expander title string."""

# Lookup builders
def build_rate_lookup(rates_df):     """Build O(1) rate lookup dictionary."""
def build_oracle_prices(rates_df):   """Build O(1) oracle price dictionary."""

# Helper creator
def create_rate_helpers(rate_lookup, oracle_prices):
    """Create 3 helper functions: get_rate, get_borrow_fee, get_price_with_fallback."""

# Summary renderers
def render_strategy_summary_metrics(stats, deployment, strategy_type, basis_pnl):
    """Render summary metrics (layout depends on strategy type)."""
def render_segment_summary(rebalance):
    """Render segment PnL breakdown."""
```

### Portfolio Allocator Functions

**File:** `analysis/portfolio_allocator.py`

```python
def calculate_blended_apr(strategy_row, apr_weights):
    """Calculate weighted average of net_apr, apr5, apr30, apr90."""

def calculate_adjusted_apr(strategy_row, blended_apr, stablecoin_prefs):
    """Apply stablecoin preference penalty to blended APR."""

def select_portfolio(portfolio_size, constraints, enable_iterative_updates=True):
    """Main greedy algorithm. Returns DataFrame with selected strategies."""

def calculate_portfolio_exposures(portfolio_df, portfolio_size):
    """Calculate token and protocol exposures using lending weights."""

def _calculate_max_allocation(strategy_row, remaining_capital,
                               token_exposures, protocol_exposures,
                               constraints, portfolio_size):
    """Calculate max allocation respecting all constraints."""

def _prepare_available_borrow_matrix(strategies):
    """Build Token×Protocol matrix of available borrow liquidity."""

def _update_available_borrow(strategy, allocation_amount, available_borrow):
    """Update liquidity matrix after allocation (in-place)."""

def _recalculate_max_sizes(strategies, available_borrow):
    """Update max_size for remaining strategies from current matrix."""
```

### Portfolio Service Functions

**File:** `analysis/portfolio_service.py`

```python
def save_portfolio(portfolio_name, portfolio_df, portfolio_size,
                   constraints, entry_timestamp, is_paper_trade, user_id, notes):
    """Save generated portfolio to database. Returns portfolio_id."""

def get_active_portfolios():
    """Get all active portfolios. Returns DataFrame."""

def get_portfolio_by_id(portfolio_id):
    """Get single portfolio. Returns Series or None."""

def get_portfolio_positions(portfolio_id):
    """Get all positions in a portfolio. Returns DataFrame."""

def calculate_portfolio_pnl(portfolio_id, live_timestamp, position_service):
    """Calculate current portfolio PnL. Returns Dict with metrics."""

def close_portfolio(portfolio_id, close_timestamp, close_reason, close_notes):
    """Close portfolio (mark as closed)."""
```

### Function Call Chain

```
Tab Level
  ├─> render_positions_table_tab()       → render_positions_batch()
  └─> render_portfolio2_tab()
      ├─> Group positions by portfolio_id
      └─> render_portfolio_expander()    → render_positions_batch()

Batch Level
  └─> render_positions_batch(position_ids, timestamp, context)
      ├─> get_db_connection()
      ├─> get_db_engine()
      ├─> get_all_position_statistics(position_ids)
      ├─> get_all_rebalance_history(position_ids)
      ├─> rates_query (rates_snapshot)
      ├─> basis_query (spot_perp_basis)
      ├─> build_rate_lookup(rates_df)
      ├─> build_oracle_prices(rates_df)
      └─> For each position_id:
          └─> render_position_expander(..., basis_lookup=basis_lookup)

Position Level
  └─> render_position_expander(...)
      ├─> build_position_expander_title()
      ├─> compute_basis_adjusted_current_apr()   [perp only]
      ├─> calculate_basis_pnl()                  [perp only]
      ├─> render_strategy_summary_metrics()
      ├─> get_strategy_renderer(strategy_type)
      ├─> renderer.render_detail_table()
      ├─> For each rebalance: render_segment_summary()
      └─> Render action buttons (context-aware)
```

---

## 17. Statistics Architecture

### Design Philosophy: Calculate Once, Store, Use Many

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

### Path 1: Pre-Calculated (Primary)

```
1. Data Collection Pipeline runs (every 15 minutes)
2. For each active position at current timestamp:
   - calculate_position_statistics()
   - Save to position_statistics table
3. Dashboard queries position_statistics
4. Instant display (<100ms)
```

### Path 2: On-Demand (Fallback)

```
1. User selects historical timestamp
2. Dashboard queries position_statistics for that timestamp
3. No statistics found (returns None)
4. Shows "📊 Calculate Statistics" button
5. User clicks button
6. calculate_position_statistics() runs (1-2 seconds)
7. Saves to position_statistics table
8. Dashboard reloads, displays statistics
```

### Statistics Caching Logic

```python
stats = get_position_statistics(position_id, timestamp)

# Check for exact timestamp match
if stats is not None and stats['timestamp'] != timestamp:
    stats = None  # Treat as missing — force recalculation

if stats is None:
    # Show "Calculate Statistics" button
```

**Why exact match matters:** Allows viewing positions with nearby-timestamp stats while still enabling recalculation for exact timestamps.

### Statistics Calculation Function

**File:** `analysis/position_statistics_calculator.py`

```python
def calculate_position_statistics(position_id, timestamp, service, get_rate_func, get_borrow_fee_func):
    position = service.get_position_by_id(position_id)
    rebalances = service.get_rebalance_history(position_id)

    # Determine segment start (entry or last rebalance)
    segment_start_ts = (rebalances.iloc[-1]['closing_timestamp']
                        if not rebalances.empty else entry_timestamp)

    # Calculate live segment earnings (token_amount × price × rate × time)
    base_1A, reward_1A = service.calculate_leg_earnings_split(position, '1a', 'Lend', ...)
    # ... all 4 legs

    live_base_earnings   = (base_1A + base_2B) - (base_2A + base_3B)
    live_reward_earnings = reward_1A + reward_2A + reward_2B + reward_3B
    live_fees = pv_result['fees']
    live_pnl  = live_total_earnings - live_fees

    # Sum realized segments from rebalances
    for _, rebal in rebalances.iterrows():
        segment_base, segment_reward = calculate_segment_earnings(rebal)
        rebalanced_pnl      += segment_pnl
        rebalanced_earnings += segment_total
        rebalanced_fees     += segment_fees

    # Totals
    total_pnl      = live_pnl + rebalanced_pnl
    current_value  = deployment_usd + total_pnl

    # APRs
    days_elapsed = (timestamp - entry_timestamp) / 86400
    realized_apr = (total_pnl / deployment_usd) * (365 / days_elapsed)
    current_apr  = gross_apr - fee_cost  # from live rates

    return {
        'position_id': position_id, 'timestamp': timestamp,
        'total_pnl': total_pnl, 'total_earnings': total_earnings,
        'base_earnings': base_earnings, 'reward_earnings': reward_earnings,
        'total_fees': total_fees, 'current_value': current_value,
        'realized_apr': realized_apr, 'current_apr': current_apr,
        'live_pnl': live_pnl, 'realized_pnl': rebalanced_pnl,
        'calculation_timestamp': int(time.time())
    }
```

---

## 18. Design Principles

### #1 — Timestamps as Unix Seconds

**Rule:** All timestamps stored and used internally as Unix seconds (int).

```python
# Database → Python
timestamp_int = to_seconds(timestamp_str)      # "2026-01-19 10:00:00" → 1737281600

# Python → Database
timestamp_str = to_datetime_str(timestamp_int)  # 1737281600 → "2026-01-19 10:00:00"

# Display → User
display_str = datetime.fromtimestamp(timestamp_int).strftime('%Y-%m-%d %H:%M:%S')
```

**File:** `utils/time_helpers.py`

### #2 — Forward-Looking Rates

**Rule:** Rate at timestamp T applies to period [T, T+1).

```
Timeline: T₀     T₁     T₂     T₃
Rates:    R₀     R₁     R₂     R₃
          ↓──────↓──────↓──────↓
Periods:  [T₀,T₁) [T₁,T₂) [T₂,T₃)
           uses R₀  uses R₁  uses R₂
```

**Why:** Matches protocol behavior — rates published apply to upcoming period.

### #3 — Position Immutability

**Rule:** `positions` table entry state never changes.

**Immutable:** `entry_timestamp`, all `entry_*` rates/prices/amounts/thresholds, `l_a`, `b_a`, `l_b`, `b_b`, `deployment_usd`

**Mutable:** `status`, `last_rebalance_timestamp`, `rebalance_count`, `accumulated_realised_pnl`, `close_*`

### #4 — Event Sourcing Pattern

```
positions:            Entry state (immutable) + Current metadata (mutable)
position_rebalances:  Append-only historical segments
position_statistics:  Pre-calculated summaries (optional cache)
```

Benefits: Can replay any historical state, no data loss, time-travel queries.

```sql
-- Get position state at historical timestamp
SELECT * FROM position_rebalances
WHERE position_id = 'uuid'
  AND opening_timestamp <= '2026-01-25 14:30:00'
  AND closing_timestamp > '2026-01-25 14:30:00'
```

### #5 — Token Identity via Contracts

**Rule:** Use `token_contract` for all logic; `token` symbol for display only.

```python
# Correct — use contract
rate = rates_df[rates_df['token_contract'] == token_contract]['lend_total_apr']

# Wrong — symbols can be duplicated (USDT vs suiUSDT)
rate = rates_df[rates_df['token'] == 'USDT']['lend_total_apr']  # Which USDT?!
```

### #6/#12 — Weight-Based Sizing; Token Amounts for PnL

**Weight use:** `token_amount = (weight × deployment_usd) / token_price_usd` (at entry or rebalance)

**PnL calculation:** Use **stored token amount × current price**, NOT `weight × deployment`:

```python
# Correct (accounts for price drift between rebalances)
usd_value = token_amount × current_price_usd
earnings  = usd_value × rate × time

# Wrong (ignores price drift)
usd_value = weight × deployment × rate × time
```

**Why this matters:** If token price increases 10% between rebalances, the naive formula is off by 10%. Using token amounts × current price captures real position value.

```python
# Example:
# l_a=1.45, deployment=$10,000, SUI price=$3.20
sui_amount = (1.45 × 10000) / 3.20 = 4531.25 SUI  # Fixed until next rebalance
# If SUI rises to $3.50:
usd_value = 4531.25 × 3.50 = $15,859  # Actual value (not 1.45 × 10000 = $14,500)
```

### #8 — Liquidation Distance Scenarios

**Three scenarios:**
1. **Entry Liq Distance**: entry_token_amounts + entry_prices
2. **Live Liq Distance**: entry_token_amounts + current_prices
3. **Rebalance Liq Distance**: rebalanced_token_amounts + current_prices

**Formula:**
```python
liq_price = (lent_usd × liq_threshold) / borrowed_tokens
liq_distance = (liq_price - current_price) / current_price × 100
# Positive = safe, Negative = danger
```

### #11 — Dashboard as Pure View Layer

Infrastructure handled internally by `render_positions_batch()`. Tab functions are simple wrappers (~15 lines).

### #13 — Explicit Error Handling

```python
for position_id in position_ids:
    try:
        render_position_expander(...)
    except Exception as e:
        st.error(f"⚠️ Error rendering position {position_id}: {e}")
        continue  # Continue rendering other positions
```

### #14 — Iterative Liquidity Updates in Portfolio Allocation

See [Section 12: Allocation Algorithm — Iterative Liquidity Updates](#12-allocation-algorithm) for complete documentation.

---

## 19. Formulas & Calculations

### PnL Calculation

**Base Earnings (uses token amounts × prices — corrected February 2026):**
```
For each leg at each timestamp period:
  token_amount = position['entry_token_amount_{leg}']  # Constant between rebalances
  price_usd    = rates_snapshot.price_usd[timestamp]   # Changes continuously
  usd_value    = token_amount × price_usd

Base Lend Earnings = Σ (token_amount_1A × price_1A × lend_base_apr_1A × time_fraction)
                   + Σ (token_amount_2B × price_2B × lend_base_apr_2B × time_fraction)

Base Borrow Costs  = Σ (token_amount_2A × price_2A × borrow_base_apr_2A × time_fraction)
                   + Σ (token_amount_3B × price_3B × borrow_base_apr_3B × time_fraction)

Net Base Earnings  = Base Lend Earnings - Base Borrow Costs
```

**Reward Earnings:**
```
Reward Earnings = Σ (token_amount_1A × price_1A × lend_reward_apr_1A × time_fraction)
                + Σ (token_amount_2A × price_2A × borrow_reward_apr_2A × time_fraction)
                + Σ (token_amount_2B × price_2B × lend_reward_apr_2B × time_fraction)
                + Σ (token_amount_3B × price_3B × borrow_reward_apr_3B × time_fraction)

Note: Borrow rewards REDUCE costs (negative value for borrowers)
```

**Total Earnings and PnL:**
```
Total Earnings = Net Base Earnings + Reward Earnings

Initial Fees = (B_A × deployment × borrow_fee_2A) + (B_B × deployment × borrow_fee_3B)
Delta Fees   = |new_amount - old_amount| × borrow_fee × price  (on rebalance, if increasing)

PnL           = Total Earnings - Total Fees
Current Value = Deployment + PnL
```

### APR Calculations

**Realized APR:**
```
Days Elapsed = (Current Timestamp - Entry Timestamp) / 86400
Realized APR = (Total PnL / Deployment) × (365 / Days Elapsed)
```

**Current APR (from live rates):**
```
Gross APR   = (L_A × lend_rate_1A) + (L_B × lend_rate_2B)
            - (B_A × borrow_rate_2A) - (B_B × borrow_rate_3B)

Fee Cost    = (B_A × borrow_fee_2A) + (B_B × borrow_fee_3B)

Current APR = Gross APR - Fee Cost
```

**Net APR (time-adjusted):**
```
Net APR = Current APR - (Total Fees × 365 / Days Held)
```

**Portfolio APR (time-and-capital-weighted):**
```
Weighted APR = Σ(days_elapsed × deployment × position_apr) / Σ(days_elapsed × deployment)
```

### Token Amount Calculations

**Token Amount from USD:**
```
Token Amount = (Weight × Deployment USD) / Token Price USD

Example: L_A=1.45, Deployment=$10,000, SUI Price=$3.20
  SUI Amount = (1.45 × 10000) / 3.20 = 4,531.25 SUI
```

**Rebalance Requirement:**
```
Entry Token Amount   = (Weight × Deployment) / Entry Price
Current Token Amount = (Weight × Deployment) / Current Price

Rebalance Needed = Current Token Amount - Entry Token Amount
  Positive = Need to add tokens (borrow more / lend more)
  Negative = Need to remove tokens (repay / withdraw)
```

### Liquidation Distance

**Liquidation Price (borrow legs only):**
```
For leg 2A (borrow token2 from Protocol A):
  Lent USD         = L_A × Deployment
  Borrowed Tokens  = entry_token_amount_2A (from positions table or last rebalance exit)
  Liq Threshold    = entry_liquidation_threshold_1a

  Liq Price = (Lent USD × Liq Threshold) / Borrowed Tokens

For leg 3B (borrow token3 from Protocol B):
  Lent USD = L_B × Deployment
  Borrowed Tokens = entry_token_amount_3B
  Liq Threshold = entry_liquidation_threshold_2b

  Liq Price = (Lent USD × Liq Threshold) / Borrowed Tokens
```

**Liquidation Distance:**
```
Liq Distance = ((Liq Price - Current Price) / Current Price) × 100%

Positive % = Safe (price can drop X% before liquidation)
Negative % = Danger (price already above liquidation)
Zero %     = At liquidation threshold
```

**Token Amount Sources by Scenario:**
- Initial segment: `entry_token_amount_*` from `positions` table
- After rebalance: `exit_token_amount_*` from last record in `position_rebalances`
- Historical segment: `entry_token_amount_*` from that `position_rebalances` record

### Time Calculations

```
time_fraction = period_duration_seconds / (365.25 × 86400)
  (365.25 days accounts for leap years)

days_elapsed = (end_timestamp - start_timestamp) / 86400

annualized_value = period_value × (365 / days_elapsed)
```

### Portfolio APR Blend

```
blended_apr = (net_apr × w_net) + (apr5 × w_5) + (apr30 × w_30) + (apr90 × w_90)
  where: w_net + w_5 + w_30 + w_90 = 1.0

adjusted_apr = blended_apr × stablecoin_multiplier
  where: stablecoin_multiplier = min multiplier across all stablecoins in strategy
         (1.0 if no stablecoins in preferences)
```

---

## 20. File Locations & Code Reference

### Dashboard Rendering

| File | Purpose |
|------|---------|
| `dashboard/streamlit_app.py` | App entry point, sidebar, timestamp selection |
| `dashboard/dashboard_renderer.py` | All tab implementations, main renderer |
| `dashboard/position_renderers.py` | Batch renderer, position expander, title builder |
| `dashboard/strategy_renderers.py` | Strategy-specific renderers (registry pattern) |
| `dashboard/dashboard_utils.py` | DB connections, batch query helpers |
| `dashboard/data_loaders.py` | `UnifiedDataLoader` for timestamp-based data |
| `dashboard/analysis_tab.py` | Analysis tab (Tab 9) |

### Business Logic

| File | Purpose |
|------|---------|
| `analysis/position_service.py` | Position CRUD, rebalance, close, PnL calculation |
| `analysis/position_statistics_calculator.py` | On-demand statistics calculation |
| `analysis/portfolio_allocator.py` | Greedy allocation algorithm, exposure calculations |
| `analysis/portfolio_service.py` | Portfolio persistence, retrieval |

### Data & Configuration

| File | Purpose |
|------|---------|
| `data/schema.sql` | Full database schema (all tables) |
| `data/refresh_pipeline.py` | Hourly data collection from protocols |
| `config/settings.py` | `DEFAULT_ALLOCATION_CONSTRAINTS`, feature flags |
| `utils/time_helpers.py` | `to_seconds()`, `to_datetime_str()` |

### Scripts

| Script | Purpose |
|--------|---------|
| `Scripts/backfill_position_token_amounts.py` | Backfill `entry_token_amount_*` for existing positions |
| `Scripts/test_iterative_updates.py` | Test iterative liquidity update behavior |

### Dashboard Schema (for reference)

| Table | File Lines | Purpose |
|-------|------------|---------|
| `rates_snapshot` | schema.sql 1-85 | Historical rates and prices |
| `token_registry` | schema.sql 86-165 | Token metadata |
| `positions` | schema.sql 166-273 | Main position records |
| `position_rebalances` | schema.sql 275-372 | Rebalance history |
| `position_statistics` | schema.sql 374-408 | Pre-calculated summaries |
| `portfolios` | schema.sql (added) | Portfolio records |

### Key Constants

```python
# config/settings.py (stablecoin multipliers from config/stablecoins.py)
DEFAULT_ALLOCATION_CONSTRAINTS = {
    'token_exposure_limit': 0.30,
    'protocol_exposure_limit': 0.40,
    'max_single_allocation_pct': 0.40,
    'max_strategies': 5,
    'min_apy_confidence': 0.70,
    'apr_weights': {'net_apr': 0.30, 'apr5': 0.30, 'apr30': 0.30, 'apr90': 0.10},
    'stablecoin_preferences': DEFAULT_STABLECOIN_PREFERENCES,  # From config/stablecoins.py
    'token_exposure_overrides': {}
}

# Feature flag (DEBUG only — will be removed once validated)
DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES = get_bool_env(
    'DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES', default=True
)

# Perp strategy types (used for basis lookup routing)
PERP_STRATEGIES = [...]  # Strategy types that use spot_perp_basis data
```

---

## Summary

This master reference covers the complete positions and portfolio system:

### Core Architecture
- **Batch rendering**: 3 queries for N positions (not 3×N)
- **Shared lookups**: O(1) rate/price access via pre-built dicts
- **Registry pattern**: Strategy-specific renderers, extensible without modifying core
- **Event sourcing**: Immutable entry state + append-only rebalance history

### Portfolio Allocator
- **Greedy selection** by adjusted APR (blended × stablecoin multiplier)
- **Iterative liquidity updates** to prevent over-borrowing from shared pools
- **Lending-only exposures** for accurate risk measurement
- **Constraint system**: token limits, protocol limits, stablecoin penalties, APR blending

### Data Integrity
- Entry state frozen at creation (immutable)
- Rebalances append-only (complete audit trail)
- Token contracts for identity (not symbols)
- Token amounts × prices for PnL (not weights × deployment)
- ISO timestamp format (`2026-01-19 10:00:00`) for expander titles
- Unix seconds internally for all time arithmetic

### Tab Structure (9 Tabs, verified from code)
1. All Strategies, 2. Allocation, 3. Rate Tables, 4. Zero Liquidity,
5. Positions, 6. Portfolio View, 7. Oracle Prices, 8. Pending Deployments, 9. Analysis

---

**For implementation details, see the source files listed in Section 20.**
