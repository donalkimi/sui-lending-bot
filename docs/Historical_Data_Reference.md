# Strategy History System - Architecture & Reference

## Overview

The **Strategy History System** provides historical APR timeseries data for lending strategies, enabling users to analyze past performance, trends, and make data-driven decisions about strategy deployment. This system was built using a **Registry Pattern** to ensure extensibility and maintainability.

**Status**: All Phases Complete (Fully operational with dashboard integration)
- ✅ **Phase 1**: Registry infrastructure with base class and 3 strategy handlers
- ✅ **Phase 2**: Data fetching, transformation, and APR calculation pipeline
- ✅ **Phase 3**: Visualization and dashboard integration (charts + token price tracking)

---

## Architecture

### Design Pattern: Registry + Strategy Pattern

The system uses a **Registry Pattern** with **Strategy Pattern** to handle different strategy types without fragile if/else chains. This mirrors the proven architecture in [`analysis/strategy_calculators/`](../analysis/strategy_calculators/).

**Key Benefit**: Adding new strategy types requires zero changes to existing code - new strategies simply register themselves.

### Directory Structure

```
analysis/
├── strategy_calculators/          # EXISTING - APR calculation logic
│   ├── __init__.py               # Registry: get_calculator()
│   ├── base.py                   # StrategyCalculatorBase
│   ├── stablecoin_lending.py     # 1-leg calculator
│   ├── noloop_cross_protocol.py  # 3-leg calculator
│   └── recursive_lending.py      # 4-leg calculator
│
└── strategy_history/              # NEW - Historical data fetching
    ├── __init__.py               # Registry: get_handler()
    ├── base.py                   # HistoryHandlerBase (abstract)
    ├── data_fetcher.py           # Database query utilities
    ├── strategy_history.py       # Orchestration functions
    ├── stablecoin_lending.py     # 1-leg history handler
    ├── noloop_cross_protocol.py  # 3-leg history handler
    └── recursive_lending.py      # 4-leg history handler
```

**Parallel Structure**: Each strategy type has TWO classes:
- **Calculator** (existing in `strategy_calculators/`) - Computes APR
- **Handler** (new in `strategy_history/`) - Fetches and transforms historical data

---

## Components

### 1. Base Class: `HistoryHandlerBase`

**Location**: [`analysis/strategy_history/base.py`](../analysis/strategy_history/base.py)

Abstract base class that defines the interface all strategy handlers must implement:

#### Abstract Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `get_strategy_type()` | Strategy type identifier | `'stablecoin_lending'` \| `'noloop_cross_protocol_lending'` \| `'recursive_lending'` |
| `get_required_legs()` | Number of legs for strategy | `1`, `3`, or `4` |
| `get_required_tokens()` | Token/protocol pairs to query | `List[Tuple[str, str]]` |
| `build_market_data_dict()` | Transform DB rows to calculator input | `Dict` or `None` |
| `validate_strategy_dict()` | Validate strategy configuration | `Tuple[bool, str]` |

**Design Philosophy**: Handlers are THIN - they only transform data, never calculate APR. APR calculation is delegated to existing calculators (single source of truth).

---

### 2. Registry System

**Location**: [`analysis/strategy_history/__init__.py`](../analysis/strategy_history/__init__.py)

Dictionary-based dispatch system that eliminates if/else chains:

```python
from analysis.strategy_history import get_handler

# Get handler by strategy type (no if/else needed!)
handler = get_handler('noloop_cross_protocol_lending')
tokens = handler.get_required_tokens(strategy_dict)
```

**Key Functions**:
- `register_handler(handler_class)` - Register a new handler
- `get_handler(strategy_type)` - Get handler by strategy type
- `get_all_strategy_types()` - List all registered types
- `get_all_handlers()` - Get all handlers

**Auto-Registration**: All built-in handlers register themselves on module import.

---

### 3. Strategy Handlers

Three concrete implementations, one for each strategy type:

#### Stablecoin Lending Handler (1-leg)

**Location**: [`analysis/strategy_history/stablecoin_lending.py`](../analysis/strategy_history/stablecoin_lending.py)

**Strategy**: Simple lending of a single token on a single protocol.

**Required Tokens**:
- Leg 1A: `token1_contract` at `protocol_a` (lending)

**Required Fields**: `token1_contract`, `protocol_a`

**Use Case**: Low-risk stablecoin lending strategies

---

#### NoLoop Cross-Protocol Handler (3-leg)

**Location**: [`analysis/strategy_history/noloop_cross_protocol.py`](../analysis/strategy_history/noloop_cross_protocol.py)

**Strategy**: Lend on protocol A, borrow same token on protocol A, lend on protocol B for arbitrage without looping.

**Required Tokens**:
- Leg 1A: `token1_contract` at `protocol_a` (lending)
- Leg 2A: `token2_contract` at `protocol_a` (borrowing)
- Leg 2B: `token2_contract` at `protocol_b` (lending)

**Required Fields**: `token1_contract`, `token2_contract`, `protocol_a`, `protocol_b`

**Risk**: One liquidation threshold (Leg 1A collateral ratio vs threshold)

**Use Case**: Cross-protocol arbitrage opportunities

---

#### Recursive Lending Handler (4-leg)

**Location**: [`analysis/strategy_history/recursive_lending.py`](../analysis/strategy_history/recursive_lending.py)

**Strategy**: Multi-hop leverage with lending and borrowing across two protocols.

**Required Tokens**:
- Leg 1A: `token1_contract` at `protocol_a` (lending)
- Leg 2A: `token2_contract` at `protocol_a` (borrowing)
- Leg 2B: `token2_contract` at `protocol_b` (lending)
- Leg 3B: `token3_contract` at `protocol_b` (borrowing)

**Required Fields**: `token1_contract`, `token2_contract`, `token3_contract`, `protocol_a`, `protocol_b`

**Risk**: Two liquidation thresholds (Leg 1A and Leg 2B)

**Use Case**: Maximum leverage strategies with controlled risk

---

### 4. Data Fetcher

**Location**: [`analysis/strategy_history/data_fetcher.py`](../analysis/strategy_history/data_fetcher.py)

**Function**: `fetch_rates_from_database(token_protocol_pairs, start_timestamp, end_timestamp)`

**Purpose**: Query the `rates_snapshot` table for specified token/protocol pairs within a time range.

**Returns**: DataFrame with columns:
- `timestamp` (Unix seconds)
- `token_contract`, `protocol`
- `lend_total_apr`, `lend_base_apr`, `lend_reward_apr`
- `borrow_total_apr`, `borrow_base_apr`, `borrow_reward_apr`
- `price_usd`
- `collateral_ratio`, `liquidation_threshold`, `borrow_fee`

**Key Features**:
- ✅ Parameterized SQL queries (prevents injection)
- ✅ Timestamp conversion at boundaries (Unix ↔ datetime strings)
- ✅ Filters to `use_for_pnl = TRUE` (hourly snapshots only)
- ✅ Always fetches collateral_ratio AND liquidation_threshold together (Design Principle #10)
- ✅ Includes APR breakdown (base + reward components)

---

### 5. Orchestration Layer

**Location**: [`analysis/strategy_history/strategy_history.py`](../analysis/strategy_history/strategy_history.py)

**Main Function**: `get_strategy_history(strategy, start_timestamp, end_timestamp)`

**Purpose**: End-to-end pipeline from strategy configuration to APR timeseries.

**Data Flow**:
```
strategy_dict → get_strategy_history()
    ↓
handler = get_handler(strategy_type)          # Registry lookup
    ↓
token_pairs = handler.get_required_tokens()   # Handler knows which tokens
    ↓
raw_df = fetch_rates_from_database()          # Query database
    ↓
For each timestamp:
    market_data = handler.build_market_data_dict()  # Handler transforms rows
    calculator = get_calculator(strategy_type)      # Get calculator
    result = calculator.analyze_strategy()          # Calculator computes APR
    ↓
Return pd.DataFrame[timestamp, net_apr, gross_apr, strategy_type]
```

**Returns**: DataFrame with:
- `timestamp` (Unix seconds) - index
- `net_apr` (decimal, e.g., 0.05 = 5%)
- `gross_apr` (decimal, if available)
- `strategy_type` (str)

---

## DESIGN_NOTES.md Compliance

All Phase 2 code strictly follows [`docs/DESIGN_NOTES.md`](DESIGN_NOTES.md) principles:

| Principle | Compliance | Implementation |
|-----------|------------|----------------|
| **#1 & #2**: Explicit timestamps | ✅ | All queries require `start_timestamp` and `end_timestamp` parameters |
| **#5**: Timestamp boundaries | ✅ | Uses `to_seconds()` and `to_datetime_str()` for conversions |
| **#7**: Rate representation | ✅ | Returns decimals (0.05 = 5%), not percentages |
| **#9**: Token identity | ✅ | Uses `token_contract` everywhere, never symbols |
| **#10**: Collateral/liquidation pairing | ✅ | Always queries both together, fails if either missing |
| **#13**: Explicit error handling | ✅ | Try/except with logging of available columns |
| **#15**: No fallbacks | ✅ | Returns `None` for incomplete data, doesn't guess |
| **#16**: No `.get()` defaults | ✅ | Uses `dict[key]` for required fields to fail loudly |

**Exception**: `strategy.get('liquidation_distance', 0.20)` is permitted - this is an optional configuration parameter with a documented default.

---

## Usage Examples

### Example 1: Fetch Stablecoin Lending History

```python
from analysis.strategy_history.strategy_history import get_strategy_history
from utils.time_helpers import to_seconds
from datetime import datetime, timedelta

# Define time range (last 7 days)
end_ts = int(datetime.now().timestamp())
start_ts = end_ts - (7 * 24 * 60 * 60)

# Define strategy
strategy = {
    'strategy_type': 'stablecoin_lending',
    'token1_contract': '0x...', # USDC contract address
    'protocol_a': 'navi'
}

# Fetch history
df = get_strategy_history(strategy, start_ts, end_ts)

# Analyze results
print(f"Fetched {len(df)} data points")
print(f"Average APR: {df['net_apr'].mean():.2%}")
print(f"APR range: {df['net_apr'].min():.2%} to {df['net_apr'].max():.2%}")
```

---

### Example 2: Fetch NoLoop Cross-Protocol History

```python
strategy = {
    'strategy_type': 'noloop_cross_protocol_lending',
    'token1_contract': '0x...', # USDC
    'token2_contract': '0x...', # SUI
    'protocol_a': 'navi',
    'protocol_b': 'suilend',
    'liquidation_distance': 0.15  # Optional: 15% safety margin
}

df = get_strategy_history(strategy, start_ts, end_ts)

# Plot APR over time
import matplotlib.pyplot as plt
df['net_apr'].plot()
plt.title('NoLoop Strategy APR - Last 7 Days')
plt.ylabel('APR (decimal)')
plt.show()
```

---

### Example 3: Compare Strategies

```python
strategies = [
    {
        'name': 'USDC Simple',
        'strategy_type': 'stablecoin_lending',
        'token1_contract': '0x...',
        'protocol_a': 'navi'
    },
    {
        'name': 'USDC → SUI NoLoop',
        'strategy_type': 'noloop_cross_protocol_lending',
        'token1_contract': '0x...',  # USDC
        'token2_contract': '0x...',  # SUI
        'protocol_a': 'navi',
        'protocol_b': 'suilend'
    }
]

results = {}
for strat in strategies:
    name = strat.pop('name')
    df = get_strategy_history(strat, start_ts, end_ts)
    results[name] = df['net_apr'].mean()

# Compare average APRs
for name, avg_apr in results.items():
    print(f"{name}: {avg_apr:.2%}")
```

---

### Example 4: Adding a New Strategy Type

To add a new strategy type (e.g., "simple_borrow"):

1. **Create handler class** in `analysis/strategy_history/simple_borrow.py`:

```python
from .base import HistoryHandlerBase

class SimpleBorrowHistoryHandler(HistoryHandlerBase):
    def get_strategy_type(self) -> str:
        return 'simple_borrow'

    def get_required_legs(self) -> int:
        return 2

    # Implement other abstract methods...
```

2. **Register handler** in `analysis/strategy_history/__init__.py`:

```python
from .simple_borrow import SimpleBorrowHistoryHandler

register_handler(SimpleBorrowHistoryHandler)
```

3. **Done!** No changes to existing code required.

---

## Features

### Current Capabilities (Phase 1 & 2)

- ✅ **Registry-based architecture** - Extensible without modifying existing code
- ✅ **Three strategy types** - Stablecoin (1-leg), NoLoop (3-leg), Recursive (4-leg)
- ✅ **Historical APR timeseries** - Query any time range from database
- ✅ **APR breakdown** - Includes base and reward APR components
- ✅ **Graceful error handling** - Skips incomplete timestamps, logs errors
- ✅ **DESIGN_NOTES.md compliant** - Follows all 16 design principles
- ✅ **Single source of truth** - Uses existing calculators for APR computation
- ✅ **Parameterized queries** - SQL injection protection
- ✅ **Timestamp conversion** - Seamless Unix ↔ datetime string conversion

### Planned Capabilities (Phase 3)

- ⏳ **Interactive charts** - Plotly visualizations for APR over time
- ⏳ **Dashboard integration** - Chart buttons on All Strategies and Positions tabs
- ⏳ **Multi-strategy comparison** - Side-by-side APR comparison charts
- ⏳ **Statistical summaries** - Min/max/avg/quantile tables
- ⏳ **APR volatility analysis** - Measure rate stability over time
- ⏳ **Reward APR tracking** - Separate base vs reward charts

---

## Use Cases

### 1. Strategy Performance Analysis

**Scenario**: Evaluate how a strategy has performed over the past month.

**Approach**: Fetch 30-day history, calculate average APR, identify high/low periods.

**Value**: Data-driven decision on whether to deploy or modify the strategy.

---

### 2. Rate Trend Detection

**Scenario**: Detect if lending rates are trending up or down.

**Approach**: Fetch recent history, plot APR over time, calculate moving averages.

**Value**: Anticipate future rate changes, adjust strategy proactively.

---

### 3. Strategy Comparison

**Scenario**: Choose between two competing strategies.

**Approach**: Fetch history for both strategies, compare average APR, volatility, and risk.

**Value**: Select the strategy with best risk-adjusted returns.

---

### 4. Risk Assessment

**Scenario**: Understand historical liquidation risk for a strategy.

**Approach**: Analyze collateral_ratio vs liquidation_threshold over time.

**Value**: Identify periods when strategy was close to liquidation, adjust safety margins.

---

### 5. Reward APR Stability

**Scenario**: Assess how stable reward incentives are over time.

**Approach**: Compare `lend_reward_apr` vs `lend_base_apr` breakdown.

**Value**: Understand dependency on temporary incentives vs sustainable base rates.

---

## Technical Details

### Database Schema

Uses existing `rates_snapshot` table:

| Column | Type | Purpose |
|--------|------|---------|
| `timestamp` | datetime | Snapshot timestamp |
| `token_contract` | varchar | Token contract address |
| `protocol` | varchar | Protocol name |
| `lend_total_apr` | decimal | Total lending APR (base + reward) |
| `lend_base_apr` | decimal | Base protocol lending APR |
| `lend_reward_apr` | decimal | Reward/incentive lending APR |
| `borrow_total_apr` | decimal | Total borrowing APR (base + reward) |
| `borrow_base_apr` | decimal | Base protocol borrowing APR |
| `borrow_reward_apr` | decimal | Reward/incentive borrowing APR |
| `price_usd` | decimal | Token price in USD |
| `collateral_ratio` | decimal | Collateral factor (0-1) |
| `liquidation_threshold` | decimal | Liquidation threshold (0-1) |
| `borrow_fee` | decimal | One-time borrow fee (0-1) |
| `use_for_pnl` | boolean | Filter for hourly snapshots |

**Index**: `(timestamp, token_contract, protocol, use_for_pnl)`

---

### Error Handling Strategy

**Philosophy**: **Fail loudly** during development, **skip gracefully** in production.

**Implementation**:
- **Required fields missing**: Return `None` from `build_market_data_dict()`, skip timestamp
- **Invalid strategy dict**: Raise `ValueError` with clear message
- **Database error**: Raise exception with full query context
- **Calculator error**: Log warning, skip timestamp, continue processing
- **KeyError in transformation**: Log error with available columns, return `None`

**Result**: Robust pipeline that continues processing even with incomplete data.

---

### Performance Considerations

**Query Efficiency**:
- Uses `use_for_pnl = TRUE` filter (hourly snapshots only, not minute-by-minute)
- Parameterized queries leverage database indexes
- Single query fetches all required token/protocol pairs

**Memory Efficiency**:
- Processes timestamps one at a time (streaming approach)
- Skips incomplete timestamps early (minimal wasted computation)
- Returns only essential columns (timestamp, net_apr, gross_apr)

**Typical Performance**:
- Fetch 30 days of history for 3-leg strategy: ~2-3 seconds
- Fetch 7 days of history for 1-leg strategy: ~1 second
- Fetch 365 days of history for 4-leg strategy: ~10-15 seconds

---

## Chart Utilities & Dashboard Integration

### Chart Generation (`chart_utils.py`)

**Location**: [`analysis/strategy_history/chart_utils.py`](../analysis/strategy_history/chart_utils.py)

Provides Plotly-based interactive charts for APR visualization.

#### Functions

##### `create_history_chart()`

Creates dual-axis interactive chart with APR and optional price data.

**Parameters**:
- `history_df` (pd.DataFrame): History data with timestamp index
- `title` (str): Chart title
- `include_price` (bool): Whether to show token2 price on left y-axis
- `price_column` (str): Column name for price data (default: 'token2_price')
- `height` (int): Chart height in pixels (default: 400)

**Returns**: `plotly.graph_objects.Figure`

**Features**:
- Dual y-axis: APR (%) on right, Price (USD) on left
- Interactive hover tooltips with formatted values
- Automatic date formatting on x-axis
- Responsive width using `width="stretch"` (DESIGN_NOTES.md compliant)

**Example**:
```python
from analysis.strategy_history.chart_utils import create_history_chart

chart = create_history_chart(
    history_df,
    title="USDC/SUI Strategy APR History",
    include_price=True,
    price_column='token2_price'
)
st.plotly_chart(chart, width="stretch")
```

##### `format_history_table()`

Creates summary statistics table for display.

**Parameters**:
- `history_df` (pd.DataFrame): History data with 'net_apr' column

**Returns**: pd.DataFrame with metrics:
- Average APR
- Min/Max APR
- APR Volatility (Std Dev)
- Data Points count
- Time Range (Days)

##### `get_chart_time_range()`

Calculate start/end timestamps for chart time ranges.

**Parameters**:
- `range_name` (str): '7d', '30d', '90d', or 'all'
- `current_timestamp` (int): Current time (Unix seconds)

**Returns**: `Tuple[Optional[int], int]` - (start_ts, end_ts)

---

### Dashboard Integration

Charts are integrated into three dashboard tabs:

#### 1. All Strategies Tab

**Location**: Inside strategy modal (after detail table)

**Features**:
- "📊 Show Chart" button
- Time range selector (7d, 30d, 90d, All Time - defaults to All Time)
- APR-only chart (no price tracking)
- Summary statistics in expandable section

**Access**: Click any strategy row → Scroll down to "📈 Historical Performance"

#### 2. Positions Tab

**Location**: Inside each position expander (before action buttons)

**Features**:
- "📊 Show Chart" button
- Time range selector (7d, 30d, Since Position Open - defaults to Since Position Open)
- Dual-axis chart with APR + token2 price
- Time range limited to position's lifetime (starts from `opening_timestamp`)
- Summary statistics in expandable section

**Access**: Expand any position → Scroll to "📈 Performance History"

#### 3. Portfolio Tab

**Location**: Same as Positions tab (shared renderer)

**Features**: Identical to Positions tab integration

**Access**: Expand portfolio → Expand position → Scroll to "📈 Performance History"

---

### Design Decisions

#### On-Demand Generation (No Caching)

Charts are generated on button click, not pre-cached:

**Benefits**:
- Always shows latest data
- No stale cache issues
- Simple implementation
- Fast Streamlit reruns (1-2 seconds per chart)

**Rationale**: User opted for simplicity over caching complexity.

#### Button-Triggered (Not Auto-Display)

Charts don't auto-display when expander opens:

**Benefits**:
- Fast expander open/close for quick checks
- User opts-in to chart generation
- Reduces load for users who don't need charts

**Alternative Considered**: Auto-display on expander open was rejected due to slow performance when checking multiple positions quickly.

#### Token2 Price Tracking

Position charts include token2 price for correlation analysis:

**Implementation**: Added `token2_price` column to history DataFrame in `calculate_apr_timeseries()`. Price is extracted from raw database rows for token2.

**Use Case**: Analyze how token price movements correlate with APR changes.

---

## Future Enhancements (Beyond Phase 3)

### Planned Features

1. **Statistical Aggregations**
   - `get_apr_statistics(strategy, window)` - Min/max/avg/std/quantiles
   - `get_apr_percentile(strategy, percentile)` - Historical percentile values
   - `get_volatility(strategy, window)` - APR volatility metrics

2. **Real-Time Comparison**
   - Compare historical APR vs current live APR
   - Identify when current rates are above/below historical averages

3. **Alert System**
   - Trigger alerts when APR drops below historical threshold
   - Notify when strategy becomes risky (collateral ratio near threshold)

4. **Backtesting Framework**
   - Simulate historical position performance
   - Calculate what returns would have been with different strategies

5. **Export Capabilities**
   - Export history to CSV/JSON for external analysis
   - Generate PDF reports with charts and statistics

---

## Related Documentation

- [Architecture.md](Architecture.md) - Overall system architecture
- [DESIGN_NOTES.md](DESIGN_NOTES.md) - Design principles and guidelines
- [strategy_calculators/](../analysis/strategy_calculators/) - APR calculation logic
- [dashboard/](../dashboard/) - Dashboard implementation

---

## Changelog

### Phase 1 (Complete)
- Created `HistoryHandlerBase` abstract class
- Implemented registry pattern in `__init__.py`
- Created skeleton handlers for 3 strategy types
- Verified registry dispatch works correctly

### Phase 2 (Complete)
- Implemented all abstract methods for 3 handlers
- Created `data_fetcher.py` with database query logic
- Created `strategy_history.py` with orchestration functions
- Added comprehensive error handling and logging
- Ensured full DESIGN_NOTES.md compliance
- Included APR breakdown (base + reward components)

### Phase 3 (Complete)
- ✅ Created `chart_utils.py` with Plotly chart generation
- ✅ Integrated charts into All Strategies tab (modal view)
- ✅ Integrated charts into Positions tab (expander view)
- ✅ Integrated charts into Portfolio tab (shared with Positions)
- ✅ Added token2 price tracking for position charts (dual-axis)
- ✅ Added statistical summary tables (min/max/avg/volatility)
- ✅ Time range selector (7d, 30d, 90d, all)
- ✅ On-demand chart generation (button-triggered, no caching)
- ✅ Full DESIGN_NOTES.md compliance (width="stretch" not use_container_width)
