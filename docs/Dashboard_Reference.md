# Sui Lending Bot - Dashboard Reference

**Version**: 3.0
**Last Updated**: March 2026
**System Status**: Production deployment on Railway with Supabase PostgreSQL

> This is a summary document. For detailed positions/portfolio technical reference, see [positions_and_portfolio_reference.md](positions_and_portfolio_reference.md)

---

## Documentation Map

- **[architecture.md](architecture.md)**: Highest-level system overview
- **dashboard_reference.md** (this file): Dashboard tabs, data pipeline, UI flows
- **[positions_and_portfolio_reference.md](positions_and_portfolio_reference.md)**: Positions tab, Portfolio Allocator — complete technical reference
- **[Historical_Data_Reference.md](Historical_Data_Reference.md)**: Historical data system, Analysis tab, basis charting

---

## Overview

The Sui Lending Bot is a dashboard application for analyzing and executing recursive lending strategies across multiple Sui DeFi protocols (AlphaFi, Navi, Suilend, Pebble, Scallop). The system tracks rates, calculates optimal position sizes, manages paper trading positions, and provides historical time-travel functionality.

**Deployment**: Railway (cloud platform) + Supabase PostgreSQL (database)
**Refresh Schedule**: Hourly, at the top of each hour
**Dashboard Framework**: Streamlit

---

## Recent Major Changes (February 2026)

### 1. Entry Token Amount Storage in Positions Table (February 11, 2026)
- **Status**: Complete
- **Change**: Added `entry_token_amount_1a/2a/2b/3b` columns to positions table
- **Formula**: `entry_token_amount = deployment_usd × weight / entry_price`
- **Purpose**: Provides fallback token amounts for positions without rebalances, improves liquidation calculations
- **Backfill**: Created `Scripts/backfill_position_token_amounts.py` to populate existing positions
- **Impact**: Fixes "N/A" liquidation prices, enables accurate rendering without rebalance records

### 2. PnL Calculation Fix: Token Amounts × Price (February 9, 2026)
- **Status**: Complete
- **Issue**: System was calculating PnL using `deployment × weight`, ignoring price drift between rebalances
- **Fix**: Now uses `token_amount × current_price` for accurate position valuation
- **Impact**: Corrects PnL calculations for positions with price volatility between rebalances
- **Files Modified**:
  - `analysis/position_service.py`: Updated `calculate_leg_earnings_split()` to use token amounts
  - `analysis/position_statistics_calculator.py`: Pass correct token amounts for live and rebalanced segments
- **Design Principle**: See Design Notes #12 - Always use actual token quantities, not target weights

### 3. Database Migration: SQLite → Supabase (PostgreSQL)
- **Status**: Complete, deployed on Railway
- **Production Database**: Supabase PostgreSQL (cloud-hosted)
- **Configuration**: `USE_CLOUD_DB=True` in production
- **Legacy**: SQLite was used for initial local development only
- **Connection**: Managed via SQLAlchemy engine factory with connection pooling

### 4. SQLAlchemy Integration
- **Status**: Complete
- **Impact**: Resolved pandas UserWarnings, added connection pooling
- **Pattern**: Dual-mode — SQLAlchemy engines for pandas queries, raw connections for cursor operations
- **Performance**: 20-50% faster with connection pooling on Supabase

### 5. Performance Optimizations (February 3, 2026)
- **Batch Loading**: Eliminated N+1 query problem (6,000+ → 60 queries)
- **Lookup Dictionaries**: Replaced O(n) DataFrame filtering with O(1) dictionary lookups
- **Expected Speedup**: 20-60x faster dashboard rendering

### 6. Portfolio Allocator: Iterative Liquidity Updates (February 10, 2026)
- **Status**: Complete and active
- **Feature**: After each allocation, updates available borrow matrix and recalculates max_size for remaining strategies
- **Impact**: Prevents over-borrowing beyond actual protocol liquidity

### 7. Auto-Rebalancing System (February 2026)
- **Status**: Complete
- **Trigger**: Integrated into `refresh_pipeline.py`, runs hourly
- **Logic**: Rebalances positions when liquidation distance changes by more than configured threshold (default 2%)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       EXTERNAL DATA SOURCES                       │
│   (Navi, AlphaFi, Suilend, Pebble, Scallop via protocol readers)│
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │  refresh_pipeline()   │  Hourly on Railway
             └──────────┬────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   Snapshot Save   Analysis Cache   Token Registry
        │               │
        └──────┬──────┘
               ▼
┌────────────────────────────────────────────────────────────────┐
│              DATABASE LAYER (Supabase PostgreSQL)              │
│  rates_snapshot | positions | position_rebalances              │
│  token_registry | analysis_cache | chart_cache                 │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  DASHBOARD (Streamlit)│
              │  9 Tabs              │
              └──────────────────────┘
```

---

## Data Pipeline

### Write Path: refresh_pipeline → Database

The `refresh_pipeline()` function is the sole write entry point. It runs hourly on Railway:

1. **Fetch** — `merge_protocol_data()` calls all protocol readers (Navi REST API, AlphaFi/Suilend/Scallop via Node.js SDK subprocesses)
2. **Normalize** — Merges into 8 unified DataFrames (lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees)
3. **Persist** — `RateTracker.save_snapshot()` inserts ~47 rows into `rates_snapshot` (one per token/protocol combination)
4. **Analyze** — `RateAnalyzer.analyze_all_combinations()` computes 200+ strategies and saves to `analysis_cache`
5. **Check Positions** — `PositionService.check_positions_need_rebalancing()` auto-rebalances positions at threshold
6. **Alert** — `SlackNotifier` sends top strategies notification

**Key property**: `rates_snapshot` is append-only (immutable historical record). The dashboard never calls protocol APIs directly.

### Read Path: Database → Dashboard

When the user opens the dashboard:

1. `get_available_timestamps()` — queries `SELECT DISTINCT timestamp FROM rates_snapshot`
2. User selects a timestamp (defaults to latest)
3. `UnifiedDataLoader.load_snapshot(timestamp)` — queries `rates_snapshot` and pivots to DataFrames
4. `RateAnalyzer` computes strategies (or reads from `analysis_cache` if available)
5. Dashboard renders all 9 tabs from in-memory DataFrames

**Performance**: Total page load < 1 second (vs 10-20 seconds if calling protocol APIs directly)

---

## Time-Travel (Timestamp as "Now")

The selected timestamp IS "current time" for all dashboard calculations. This is a core design principle.

- All data queries use `WHERE timestamp <= selected_timestamp`
- All position PnL is calculated from entry through the selected timestamp
- Time-travel is instant — it is a pure database cache lookup, no API calls
- Any historical market state can be replayed exactly

The timestamp picker in the sidebar defaults to the latest available snapshot. Selecting any past timestamp causes the entire dashboard to render as if that moment is "now."

---

## Two-Tier Caching Strategy

**Tier 1: Protocol Data Cache (`rates_snapshot`)**
Time-series of all rates, prices, fees, and liquidity from all protocols. Append-only. Key: `(timestamp, protocol, token_contract)`.

**Tier 2: Analysis Results Cache (`analysis_cache`)**
Pre-computed strategy analysis results stored as JSON. Keyed by `(timestamp_seconds, liquidation_distance)`. 48-hour retention. If cache hit, strategy tab renders instantly without rerunning `RateAnalyzer`.

---

## Dashboard Tabs (9 Total)

The dashboard is implemented in `dashboard/dashboard_renderer.py` and renders 9 Streamlit tabs.

| # | Tab | Purpose |
|---|-----|---------|
| 1 | All Strategies | Sortable table of all strategies. Click a row to open a modal with APR comparison, leg details, and historical chart. Deploy button launches paper trade confirmation. |
| 2 | Allocation | Portfolio allocator view. Shows greedy allocation of a given capital amount across top strategies, respecting token/protocol exposure limits and iterative liquidity constraints. |
| 3 | Rate Tables | Raw protocol data matrices — lending rates, borrowing rates, collateral ratios, prices, available borrow liquidity, borrow fees. One column per protocol, one row per token. |
| 4 | 0 Liquidity | Strategies where available borrow liquidity is insufficient for the configured deployment size. Useful for tracking strategies that are currently over-subscribed. |
| 5 | Positions | All active and closed paper trade positions with full PnL tracking. Expandable rows show leg details, rebalance history, and segment summaries. See [positions_and_portfolio_reference.md](positions_and_portfolio_reference.md) for complete detail. |
| 6 | Portfolio View | Portfolio-level aggregation of all positions. Groups by strategy type, shows total deployment, aggregated PnL, and per-position breakdown. See [positions_and_portfolio_reference.md](positions_and_portfolio_reference.md) for complete detail. |
| 7 | Oracle Prices | Live oracle prices for all tracked tokens across protocols. Cross-references Pyth/CoinGecko IDs from `token_registry`. |
| 8 | Pending Deployments | Strategies that have been flagged or queued for deployment. See [docs/pending_deployments_guide.md](pending_deployments_guide.md). |
| 9 | Analysis | Historical rate analysis for a selected strategy. Time range selector (7d, 30d, 90d, All). APR chart with rolling average overlays. Basis chart for perp strategies. Historical rates table. See [Historical_Data_Reference.md](Historical_Data_Reference.md). |

---

## Tab 1: All Strategies — Key UI Flows

### Strategy Table
Displays all strategies from `RateAnalyzer.analyze_all_combinations()`. Columns include token flow, protocols, net APR, APR5/30/90, max deployable size, liquidation distance. Sortable by any column. Filters in sidebar: stablecoin-only, min APR, token/protocol filters.

### Strategy Modal (on row click)
Three components:
1. **APR Comparison Table** — Shows loop (4-leg levered) and unlevered (3-leg) variants side by side with net APR, APR5, APR30, APR90, days to breakeven. Each variant has a Deploy button.
2. **Strategy Details Table** — All legs (Protocol, Token, Action, Rate, Weight, Amount, Fee). Shows both levered and unlevered breakdowns.
3. **Historical Chart** — "Show Chart" button loads APR history from `analysis/strategy_history/`. Dual-axis: APR on right y-axis. Time range: 7d, 30d, 90d, All Time.

### Deployment Flow
Clicking Deploy opens a confirmation modal with strategy details, APR projections, position size, liquidation distance, and a notes field. On confirm, calls `PositionService.create_position()` which INSERTs into `positions` table.

---

## Tab 2: Allocation — Key Concepts

The Allocation tab renders the output of `analysis/portfolio_allocator.py`. The allocator uses a greedy algorithm:

1. Filter strategies by confidence threshold
2. Compute blended APR (weighted: 40% net_apr, 30% apr5, 20% apr30, 10% apr90)
3. Apply stablecoin preference adjustments
4. Sort by adjusted APR descending
5. Greedy loop: allocate to each strategy up to token/protocol exposure limits and available liquidity
6. After each allocation, update the Token×Protocol available borrow matrix and recalculate `max_size` for remaining strategies (prevents over-borrowing)

The sidebar controls portfolio size and per-token/protocol exposure limits.

For complete Portfolio Allocator technical detail, see [positions_and_portfolio_reference.md](positions_and_portfolio_reference.md).

---

## Positions and Portfolio Tabs — Summary

The **Positions tab** (Tab 5) shows all paper trade positions with expandable rows. Each row displays entry time, token flow, protocols, deployment size, entry APR, current APR, and running PnL. Expanding a row shows:
- Strategy Summary (combined real + unrealized PnL across all segments)
- Live Position Summary (current segment metrics)
- 4-leg token detail table with base/reward APR split
- Rebalance history with per-segment PnL breakdown
- Rebalance and Close buttons (disabled in time-travel mode when future rebalances exist)

The **Portfolio View tab** (Tab 6) aggregates positions for portfolio-level analysis, grouping by strategy type and showing capital allocation, weighted APR, and total PnL.

For complete technical detail on Positions and Portfolio tabs, see [positions_and_portfolio_reference.md](positions_and_portfolio_reference.md).

---

## Key Architecture Concepts

### Event Sourcing for Positions

Positions use an event-sourcing pattern:
- `positions` table: Entry state captured at deployment (immutable after creation)
- `position_rebalances` table: Each rebalance creates an immutable segment with opening/closing rates, prices, and realized PnL
- Current PnL is always calculated forward from entry state through historical rates

This provides perfect reproducibility: any position's history can be replayed at any timestamp.

### Token Identity: Contracts, Not Symbols

All logic uses `token_contract` (full Sui contract address). Token symbols are only used for display. This prevents collisions between tokens that share symbols but have different contracts (e.g., suiUSDT vs USDT).

### Rates as Decimals

All rates, APRs, and fees are stored and computed as decimals (0.0 to 1.0 scale). Conversion to percentages happens only at the display layer.

### Strategy Calculator Registry

Strategy types are mapped to calculator classes via a registry in `analysis/strategy_calculators/__init__.py`. Current strategy types: `stablecoin_lending`, `noloop_cross_protocol_lending`, `recursive_lending`, `perp_lending`, `perp_borrowing`, `perp_borrowing_recursive`.

Each strategy type also has a corresponding renderer class registered in `dashboard/position_renderers.py` via the `@register_strategy_renderer` decorator. See [Strategy_Position_Decorator_Reference.md](Strategy_Position_Decorator_Reference.md).

---

## File Structure

```
sui-lending-bot/
├── main.py                            # Entry point for refresh pipeline
├── config/
│   └── settings.py                    # USE_CLOUD_DB, thresholds, feature flags
├── data/
│   ├── refresh_pipeline.py            # Hourly orchestration: fetch → save → analyze
│   ├── protocol_merger.py             # Merges data from all protocol readers
│   ├── rate_tracker.py                # RateTracker: DB writes for snapshots and cache
│   ├── schema.sql                     # Database schema (all tables + indexes)
│   └── [protocol]/                    # Per-protocol reader directories
├── analysis/
│   ├── rate_analyzer.py               # RateAnalyzer: generates all strategy combinations
│   ├── position_calculator.py         # PositionCalculator: geometric series position sizing
│   ├── position_service.py            # PositionService: CRUD + PnL calculations
│   ├── portfolio_allocator.py         # PortfolioAllocator: greedy capital allocation
│   ├── strategy_calculators/          # Registry + per-type calculator classes
│   └── strategy_history/              # Registry + per-type historical APR handlers
├── dashboard/
│   ├── dashboard_renderer.py          # Main dashboard: all 9 tabs
│   ├── position_renderers.py          # Strategy renderer registry + per-type renderers
│   ├── analysis_tab.py                # Analysis tab (Tab 9) implementation
│   ├── dashboard_utils.py             # UnifiedDataLoader, get_db_connection()
│   └── db_utils.py                    # SQLAlchemy engine factory (connection pool)
├── utils/
│   └── time_helpers.py                # to_seconds(), to_datetime_str()
├── Scripts/                           # Maintenance scripts (backfill, migrate, purge)
└── docs/                              # Documentation
```

---

## Critical Design Principles

1. **Timestamp as "Now"**: Never use `datetime.now()` in dashboard code. The selected timestamp IS current time.
2. **Database is the Cache**: Dashboard reads only from DB. Protocol APIs are called only in `refresh_pipeline`.
3. **Event Sourcing**: positions table = entry state. position_rebalances = immutable historical segments.
4. **Contract Addresses for Logic**: Always use `token_contract` in queries and logic; symbols for display only.
5. **Decimals Internally**: Rates stored as 0.0-1.0; multiply by 100 only at display layer.
6. **Timestamp Format**: Database timestamps must be exactly 19 characters: `'YYYY-MM-DD HH:MM:SS'`. Use `to_datetime_str()` helper.

---

## Production Configuration

**Environment Variables**:
```
SUPABASE_URL=postgresql://...
SUI_RPC_URL=...
SLACK_WEBHOOK_URL=...
```

**Key settings** (`config/settings.py`):
- `USE_CLOUD_DB = True` — always True in production
- `REBALANCE_THRESHOLD = 0.02` — 2% liquidation distance change triggers auto-rebalance
- `SAVE_SNAPSHOTS = True` — enables rate snapshot caching
- `DEFAULT_LIQUIDATION_DISTANCE` — default buffer used in strategy calculations
