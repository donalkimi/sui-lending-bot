# Plan: Implement Charting Functionality for Strategy APR History

## Context

The user wants to bring back charting functionality to visualize strategy net APR over time. This will support:
1. **Deployed Positions**: Track how a deployed position's APR has changed since entry
2. **Strategy Configurations**: Analyze historical APR for any strategy combo (tokens + protocols) for backtesting before deployment
3. **Confidence Metrics** (future): Use historical data to assess whether current APRs are likely to persist

The system already has all necessary infrastructure:
- `rates_snapshot` table: Historical rate data indexed by timestamp, token_contract, protocol
- `position_statistics` table: Pre-calculated position metrics including current_apr
- APR calculation logic in `position_calculator.py` and strategy calculators
- Cache tables (`chart_cache`) ready for use

### Multi-Strategy Support

The system supports 3 strategy types:
1. **STABLECOIN_LENDING**: 1-leg (single token lending, no borrowing)
2. **NOLOOP_CROSS_PROTOCOL_LENDING**: 3-leg (lend → borrow → lend, no loop back)
3. **RECURSIVE_LENDING**: 4-leg (full recursive leverage loop, market-neutral)

The charting functionality must handle all three strategy types correctly, as they have different:
- Number of legs (1, 3, or 4)
- APR calculation formulas
- Token/protocol structures

## Implementation Plan

### 1. Create `analysis/strategy_history.py` - Core History Logic

**File**: `/Users/donalmoore/Dev/sui-lending-bot/analysis/strategy_history.py`

**Dependencies**:
```python
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict
from utils.time_helpers import to_seconds, to_datetime_str
from analysis.strategy_calculators import get_calculator
```

**Key Imports**:
- Strategy calculator registry for multi-strategy support
- Time helpers for consistent timestamp handling
- Plotly for chart generation

Implement two main functions:

#### Function 1: `get_strategy_history()`
```python
def get_strategy_history(
    conn,
    position_id: Optional[str] = None,
    strategy: Optional[Dict] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None
) -> pd.DataFrame:
    """
    Get historical net APR timeseries for a position or strategy configuration.

    Args:
        conn: Database connection
        position_id: If provided, get history for deployed position
        strategy: If provided, dict with:
            - strategy_type: 'stablecoin_lending' | 'noloop_cross_protocol_lending' | 'recursive_lending'
            - token1_contract: Required for all types
            - token2_contract: Required for noloop and recursive, None for stablecoin
            - token3_contract: Required for recursive, None for stablecoin and noloop
            - protocol_a: Required for all types
            - protocol_b: Required for noloop and recursive, None for stablecoin
            - liquidation_distance: Optional, default from settings (only used for noloop and recursive)
        start_timestamp: Unix seconds (default: earliest available)
        end_timestamp: Unix seconds (default: latest available)

    Returns:
        DataFrame with:
            - Index: timestamp (Unix seconds)
            - Column: net_apr (decimal, e.g., 0.0842 = 8.42%)

    Raises:
        ValueError: If neither position_id nor strategy provided, or if both provided
        ValueError: If strategy missing required fields for its strategy_type
    """
```

**Implementation Details**:

**For Positions** (position_id provided):
1. Query position from `positions` table to get entry_timestamp, strategy_type, and strategy details
2. Query `position_statistics` table for pre-calculated current_apr values:
   ```sql
   SELECT timestamp_seconds, current_apr
   FROM position_statistics
   WHERE position_id = ?
     AND timestamp_seconds >= ?
     AND timestamp_seconds <= ?
   ORDER BY timestamp_seconds
   ```
3. If position_statistics is empty (no snapshots yet), fall back to calculating from rates_snapshot:
   - Get strategy calculator: `calculator = get_calculator(position['strategy_type'])`
   - Use calculator to determine required legs and calculate APR
4. Return DataFrame indexed by timestamp

**For Strategies** (strategy dict provided):
1. Validate strategy dict has required fields based on strategy_type:
   - **STABLECOIN_LENDING**: token1_contract, protocol_a (only)
   - **NOLOOP_CROSS_PROTOCOL_LENDING**: token1_contract, token2_contract, protocol_a, protocol_b
   - **RECURSIVE_LENDING**: token1_contract, token2_contract, token3_contract, protocol_a, protocol_b

2. Get strategy calculator: `calculator = get_calculator(strategy['strategy_type'])`

3. Query available timestamps from rates_snapshot (ONLY for required legs):
   ```sql
   -- For STABLECOIN_LENDING (1 leg):
   SELECT DISTINCT timestamp
   FROM rates_snapshot
   WHERE timestamp >= ? AND timestamp <= ?
     AND token_contract = ? AND protocol = ?  -- token1 at protocol_a
   ORDER BY timestamp

   -- For NOLOOP_CROSS_PROTOCOL_LENDING (3 legs):
   SELECT DISTINCT timestamp
   FROM rates_snapshot
   WHERE timestamp >= ? AND timestamp <= ?
     AND (
       (token_contract = ? AND protocol = ?) OR  -- token1 at protocol_a
       (token_contract = ? AND protocol = ?) OR  -- token2 at protocol_a
       (token_contract = ? AND protocol = ?)     -- token2 at protocol_b
     )
   ORDER BY timestamp

   -- For RECURSIVE_LENDING (4 legs):
   SELECT DISTINCT timestamp
   FROM rates_snapshot
   WHERE timestamp >= ? AND timestamp <= ?
     AND (
       (token_contract = ? AND protocol = ?) OR  -- token1 at protocol_a
       (token_contract = ? AND protocol = ?) OR  -- token2 at protocol_a
       (token_contract = ? AND protocol = ?) OR  -- token2 at protocol_b
       (token_contract = ? AND protocol = ?)     -- token3 at protocol_b
     )
   ORDER BY timestamp
   ```

4. For each timestamp:
   - Query rates for required legs from rates_snapshot (based on strategy_type)
   - Use calculator's `analyze_strategy()` method to calculate net_apr
   - Handle missing data gracefully (skip timestamp if any required leg has no data)
5. Return DataFrame indexed by timestamp

**Implementation Pseudocode for Strategy Calculation**:

```python
# Get the appropriate calculator for this strategy type
calculator = get_calculator(strategy['strategy_type'])

# Determine which legs are required
required_legs = calculator.get_required_legs()  # Returns 1, 3, or 4

# Build rates dict based on required legs
rates_dict = {}
if required_legs >= 1:
    # Query leg 1A: token1 at protocol_a
    rates_dict['lend_rate_1A'] = query_rate(timestamp, token1_contract, protocol_a, 'lend')
    rates_dict['lend_reward_1A'] = query_rate(timestamp, token1_contract, protocol_a, 'lend_reward')
    rates_dict['price_1A'] = query_price(timestamp, token1_contract, protocol_a)

if required_legs >= 3:  # noloop and recursive
    # Query leg 2A: token2 at protocol_a
    rates_dict['borrow_rate_2A'] = query_rate(timestamp, token2_contract, protocol_a, 'borrow')
    rates_dict['borrow_fee_2A'] = query_fee(timestamp, token2_contract, protocol_a)
    rates_dict['price_2A'] = query_price(timestamp, token2_contract, protocol_a)
    rates_dict['collateral_ratio_1A'] = query_collateral(timestamp, token1_contract, protocol_a)
    rates_dict['liquidation_threshold_1A'] = query_liq_threshold(timestamp, token1_contract, protocol_a)

    # Query leg 2B: token2 at protocol_b
    rates_dict['lend_rate_2B'] = query_rate(timestamp, token2_contract, protocol_b, 'lend')
    rates_dict['lend_reward_2B'] = query_rate(timestamp, token2_contract, protocol_b, 'lend_reward')
    rates_dict['price_2B'] = query_price(timestamp, token2_contract, protocol_b)

if required_legs >= 4:  # recursive only
    # Query leg 3B: token3 at protocol_b
    rates_dict['borrow_rate_3B'] = query_rate(timestamp, token3_contract, protocol_b, 'borrow')
    rates_dict['borrow_fee_3B'] = query_fee(timestamp, token3_contract, protocol_b)
    rates_dict['price_3B'] = query_price(timestamp, token3_contract, protocol_b)
    rates_dict['collateral_ratio_2B'] = query_collateral(timestamp, token2_contract, protocol_b)
    rates_dict['liquidation_threshold_2B'] = query_liq_threshold(timestamp, token2_contract, protocol_b)

# Validate all required rates are present (not None, not zero)
if not all_rates_valid(rates_dict):
    continue  # Skip this timestamp

# Use calculator to analyze strategy and get net_apr
result = calculator.analyze_strategy(
    token_combo=strategy_tokens,
    protocol_pair=(strategy['protocol_a'], strategy.get('protocol_b')),
    market_data=rates_dict,
    liquidation_distance=strategy.get('liquidation_distance', settings.DEFAULT_LIQUIDATION_DISTANCE)
)

# Extract net_apr from result
net_apr = result['net_apr']
history.append({'timestamp': timestamp, 'net_apr': net_apr})
```

**Edge Cases to Handle**:
- Missing data: Skip timestamps where data is incomplete for required legs
- Zero values: Validate rates/prices are positive before calculating
- Strategy type validation: Fail loudly if strategy_type is unknown or missing
- Optional legs: Handle None values for token3/protocol_b in noloop and stablecoin strategies
- Rebalanced positions: For position_id, only show history from last rebalance to present (live segment)

#### Function 2: `plot_strategy_history()`
```python
def plot_strategy_history(
    conn,
    position_id: Optional[str] = None,
    strategy: Optional[Dict] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    title: Optional[str] = None,
    show_percentages: bool = True
) -> go.Figure:
    """
    Plot historical net APR timeseries for a position or strategy configuration.

    Args:
        conn: Database connection
        position_id: If provided, plot history for deployed position
        strategy: If provided, strategy dict (see get_strategy_history)
        start_timestamp: Unix seconds (default: earliest available)
        end_timestamp: Unix seconds (default: latest available)
        title: Chart title (default: auto-generated)
        show_percentages: If True, format y-axis as percentages (default: True)

    Returns:
        Plotly Figure object
    """
```

**Implementation Details**:

1. Call `get_strategy_history()` with same parameters to get DataFrame
2. Convert timestamps to datetime strings for x-axis labels using `to_datetime_str()`
3. Convert net_apr to percentages if show_percentages=True
4. Create Plotly line chart:
   ```python
   import plotly.graph_objects as go

   fig = go.Figure()

   # Add line trace
   fig.add_trace(go.Scatter(
       x=df.index.map(to_datetime_str),  # Convert Unix seconds to datetime strings
       y=df['net_apr'] * 100 if show_percentages else df['net_apr'],
       mode='lines',
       name='Net APR',
       line=dict(color='#1f77b4', width=2),
       hovertemplate='<b>%{x}</b><br>Net APR: %{y:.2f}%<extra></extra>'
   ))

   # Configure layout
   fig.update_layout(
       title=title or auto_generate_title(position_id, strategy),
       xaxis_title='Date',
       yaxis_title='Net APR (%)',
       hovermode='x unified',
       template='plotly_white'
   )

   return fig
   ```

5. Auto-generate title based on context:
   - Position: "Position {position_id[:8]}: {token1}/{token2}/{token3} ({protocol_a}↔{protocol_b})"
   - Strategy: "Strategy: {token1}/{token2}/{token3} ({protocol_a}↔{protocol_b})"

**Plotly Styling**:
- Use clean template ('plotly_white')
- X-axis: datetime labels with auto-formatting
- Y-axis: percentage format (e.g., "8.42%")
- Hover: Show exact timestamp and APR value
- Responsive: Use `width="stretch"` in Streamlit (not deprecated `use_container_width`)

---

### 2. Add Chart Display to Dashboard

**File**: `/Users/donalmoore/Dev/sui-lending-bot/dashboard/dashboard_renderer.py`

#### Location 1: All Strategies Tab

**Where**: In `render_all_strategies_tab()`, inside the strategy expansion section

**Add Button**:
```python
if st.button("📈 Show Historical APR Chart", key=f"chart_strategy_{strategy_idx}"):
    # Get strategy details from row
    strategy_dict = {
        'token1_contract': strategy_row['token1_contract'],
        'token2_contract': strategy_row['token2_contract'],
        'token3_contract': strategy_row.get('token3_contract'),  # May be None
        'protocol_a': strategy_row['protocol_a'],
        'protocol_b': strategy_row['protocol_b'],
        'liquidation_distance': liquidation_distance  # From sidebar
    }

    # Plot chart
    try:
        fig = plot_strategy_history(
            conn=conn,
            strategy=strategy_dict,
            end_timestamp=timestamp_seconds,  # Use selected dashboard timestamp as "now"
            title=f"{strategy_row['token1']}/{strategy_row['token2']}/{strategy_row.get('token3', 'N/A')} ({strategy_row['protocol_a']}↔{strategy_row['protocol_b']})"
        )
        st.plotly_chart(fig, width="stretch")
    except Exception as e:
        st.error(f"Failed to generate chart: {e}")
```

**Position**: After the APR comparison table, before strategy details table

#### Location 2: Positions Tab

**Where**: In `render_positions_table_tab()`, inside position expansion

**Add Button**:
```python
if st.button("📈 Show APR History", key=f"chart_position_{position_id}"):
    # Get position entry timestamp
    entry_ts = position['entry_timestamp']

    try:
        fig = plot_strategy_history(
            conn=conn,
            position_id=position_id,
            start_timestamp=entry_ts,
            end_timestamp=timestamp_seconds,  # Dashboard selected timestamp
            title=f"Position {position_id[:8]}: {position['token1']}/{position['token2']}/{position.get('token3', 'N/A')}"
        )
        st.plotly_chart(fig, width="stretch")
    except Exception as e:
        st.error(f"Failed to generate chart: {e}")
```

**Position**: After the "Strategy Summary (Real + Unreal)" section, before the live position token table

---

### 3. Add Plotly Dependency

**File**: `/Users/donalmoore/Dev/sui-lending-bot/pyproject.toml`

Add to `[project.dependencies]`:
```toml
dependencies = [
    # ... existing dependencies ...
    "plotly>=5.18.0",  # Chart visualization
]
```

Then run:
```bash
pip install -e .
```

---

### 4. Update Position Statistics Collection (Optional Enhancement)

**File**: `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_statistics_calculator.py`

**Current Behavior**: position_statistics table is populated during position calculations.

**Recommendation**: Ensure `current_apr` is correctly stored in position_statistics. Verify the field exists and is populated in:
- `calculate_position_statistics_batch()` method

If not already present, add `current_apr` to the calculated statistics dictionary:
```python
statistics = {
    # ... existing fields ...
    'current_apr': calculate_current_apr(position, live_timestamp, conn),
    # ... rest of fields ...
}
```

**Note**: Based on the exploration, position_statistics already has current_apr field in schema. Just verify it's being populated correctly.

---

### 5. Add Chart Caching (Optional Performance Enhancement)

**File**: `/Users/donalmoore/Dev/sui-lending-bot/analysis/strategy_history.py`

Add caching to `plot_strategy_history()`:

```python
def plot_strategy_history(...) -> go.Figure:
    # Generate cache key
    if position_id:
        cache_key = f"position_{position_id}_{start_timestamp}_{end_timestamp}"
    else:
        # Hash strategy dict for cache key
        strategy_str = f"{strategy['token1_contract']}_{strategy['token2_contract']}_{strategy.get('token3_contract', 'None')}_{strategy['protocol_a']}_{strategy['protocol_b']}"
        cache_key = hashlib.md5(strategy_str.encode()).hexdigest()
        cache_key = f"strategy_{cache_key}_{start_timestamp}_{end_timestamp}"

    # Check chart_cache table
    cached = get_cached_chart(conn, cache_key)
    if cached:
        return pio.from_json(cached['chart_json'])

    # Generate chart
    fig = generate_chart(...)

    # Save to cache
    save_chart_cache(conn, cache_key, pio.to_json(fig))

    return fig
```

Helper functions:
```python
def get_cached_chart(conn, cache_key: str) -> Optional[Dict]:
    """Query chart_cache table. Return None if not found or expired (>48 hours)."""

def save_chart_cache(conn, cache_key: str, chart_json: str):
    """Insert into chart_cache table."""
```

**Cache Expiration**: 48 hours (configurable in settings.py)

**Cache Table** (already exists in schema):
```sql
CREATE TABLE IF NOT EXISTS chart_cache (
    strategy_hash TEXT PRIMARY KEY,
    timestamp_seconds INTEGER NOT NULL,
    chart_html TEXT NOT NULL,  -- Store chart as JSON instead
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Note**: Consider renaming `chart_html` to `chart_json` in schema for clarity, or use it as-is for JSON storage.

---

## Critical Files to Modify

1. **NEW FILE**: `/Users/donalmoore/Dev/sui-lending-bot/analysis/strategy_history.py`
   - Core charting logic
   - Two functions: `get_strategy_history()` and `plot_strategy_history()`

2. **MODIFY**: `/Users/donalmoore/Dev/sui-lending-bot/dashboard/dashboard_renderer.py`
   - Add chart buttons to All Strategies tab (Lines ~513-638, in strategy expansion)
   - Add chart buttons to Positions tab (Lines ~721-962, in position expansion)

3. **MODIFY**: `/Users/donalmoore/Dev/sui-lending-bot/pyproject.toml`
   - Add plotly dependency

4. **VERIFY** (no changes unless needed): `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_statistics_calculator.py`
   - Ensure current_apr is being populated in position_statistics table

## Testing Strategy

### Test 1: Position History Chart
1. Deploy a position via dashboard
2. Wait for multiple snapshots to be collected (or backfill with test data)
3. Navigate to Positions tab
4. Expand position
5. Click "📈 Show APR History"
6. Verify chart displays with correct date range (entry_timestamp → now)

### Test 2: Strategy History Chart - RECURSIVE_LENDING
1. Navigate to All Strategies tab
2. Filter to show only RECURSIVE_LENDING strategies
3. Expand a 4-leg strategy
4. Click "📈 Show Historical APR Chart"
5. Verify chart displays with full historical range
6. Verify APR values match manual calculation for sample timestamp

### Test 3: Strategy History Chart - NOLOOP_CROSS_PROTOCOL_LENDING
1. Navigate to All Strategies tab
2. Filter to show only NOLOOP_CROSS_PROTOCOL_LENDING strategies
3. Expand a 3-leg strategy
4. Click "📈 Show Historical APR Chart"
5. Verify chart displays (should have data if strategy type implemented)
6. Verify no errors from missing token3/leg 3B data

### Test 4: Strategy History Chart - STABLECOIN_LENDING
1. Navigate to All Strategies tab
2. Filter to show only STABLECOIN_LENDING strategies
3. Expand a 1-leg strategy
4. Click "📈 Show Historical APR Chart"
5. Verify chart displays (should have data if strategy type implemented)
6. Verify no errors from missing token2/token3 data

### Test 5: Missing Data Handling
1. Use strategy with limited historical data (new token with sparse rates_snapshot)
2. Verify chart gracefully handles gaps (skips timestamps with missing data)
3. Verify error message if no data available
4. Verify "N/A" displayed instead of crash when critical data missing

### Test 6: Strategy Type Validation
1. Attempt to chart strategy with invalid strategy_type
2. Verify clear error message with available strategy types listed
3. Verify system doesn't crash

### Test 7: Time Period Filtering (future enhancement)
1. Select custom start/end dates
2. Verify chart displays only selected range

### Test 8: Performance with Large Datasets
1. Query recursive strategy with >1000 timestamps
2. Verify chart renders within reasonable time (<3 seconds)
3. Consider pagination or sampling for very large datasets
4. Compare performance: stablecoin (1 leg) vs recursive (4 legs)

## Design Principles Applied

### From DESIGN_NOTES.md:

1. **Timestamp as Current Time** (Principle #1):
   - Use dashboard's selected timestamp as end_timestamp (time-travel support)
   - Never use `datetime.now()` - require explicit timestamp parameter
   - All queries use `WHERE timestamp <= end_timestamp`

2. **Unix Seconds Internally** (Principle #5):
   - All timestamp handling uses integers (Unix seconds)
   - Convert to datetime strings only at display boundaries using `to_datetime_str()`
   - Convert from any format using `to_seconds()`
   - Database reads/writes use consistent 19-character format: 'YYYY-MM-DD HH:MM:SS'

3. **Token Identity by Contract** (Principle #9):
   - All queries use token_contract (not symbol) for matching
   - Use `normalize_coin_type()` for contract comparison
   - Token symbols ONLY for display purposes

4. **Rates as Decimals** (Principle #7):
   - Store APR as decimals (0.0842), convert to percentages (8.42%) only in display layer
   - All internal calculations use decimal format
   - Multiply by 100 only when rendering charts or UI

5. **Event Sourcing** (Principle #4):
   - For positions, respect rebalance history (show only live segment by default)
   - Positions table stores immutable entry state
   - Performance calculated on-the-fly from rates_snapshot

6. **No datetime.now() Defaults** (Principle #2):
   - Require explicit timestamps, fail loudly if missing
   - Use dashboard timestamp selection as "now"

7. **Explicit Error Handling** (Principle #13):
   - Try to access data explicitly, catch KeyError/ValueError
   - Print available columns/options when errors occur
   - Continue execution, don't crash (show "N/A" or skip timestamp)

8. **No Fallback Values** (Principle #15):
   - Never use wrong fallback values (e.g., entry_price when segment_price needed)
   - Fail loudly with "N/A" or skip data point if correct value missing
   - Show debugging info to developer

### Multi-Strategy Architecture:

9. **Strategy Type Awareness**:
   - Use strategy calculator registry: `get_calculator(strategy_type)`
   - Each strategy type has different leg requirements (1, 3, or 4 legs)
   - Query only required legs (don't query token3 for noloop strategies)
   - Use calculator's `analyze_strategy()` method for APR calculation

10. **Pluggable Calculators**:
    - Never hardcode strategy type logic in charting code
    - Delegate all strategy-specific calculations to calculator classes
    - Support future strategy types without modifying charting code

## Future Enhancements (Out of Scope for Initial Implementation)

1. **Lookback Statistics**:
   - Percentile ranking: "Current APR is at 75th percentile"
   - Volatility metrics: "Standard deviation: 1.2%"
   - Trend analysis: "APR trending up over last 30 days"

2. **Multiple APR Metrics**:
   - Toggle between net_apr, apr5, apr30, apr90
   - Component breakdown (lend earnings, borrow costs, fees)
   - Base vs reward split

3. **Comparison Charts**:
   - Compare multiple strategies on same chart
   - Compare protocol performance

4. **Interactive Features**:
   - Date range selector
   - Zoom/pan controls
   - Download chart as PNG

5. **Annotations**:
   - Mark rebalance events on chart
   - Mark significant APR changes
   - Add notes/comments to chart

## Verification Checklist

### Core Implementation
- [ ] `strategy_history.py` created with both functions implemented
- [ ] Plotly added to dependencies and installed
- [ ] Strategy calculator registry imported and used correctly
- [ ] Time helpers (to_seconds, to_datetime_str) used for all timestamp operations

### Dashboard Integration
- [ ] Chart buttons added to All Strategies tab
- [ ] Chart buttons added to Positions tab
- [ ] Charts render with `width="stretch"` (not deprecated `use_container_width`)

### Multi-Strategy Support
- [ ] RECURSIVE_LENDING (4-leg) strategies chart correctly
- [ ] NOLOOP_CROSS_PROTOCOL_LENDING (3-leg) strategies chart correctly (when implemented)
- [ ] STABLECOIN_LENDING (1-leg) strategies chart correctly (when implemented)
- [ ] Unknown strategy_type raises clear error with available types listed
- [ ] Only required legs queried (no queries for token3 in noloop strategies)

### Data Handling
- [ ] Missing data handled gracefully (skips timestamps, doesn't crash)
- [ ] Zero values validated before calculating (skips timestamps with zero rates/prices)
- [ ] Contract addresses used for all queries (not symbols)
- [ ] Rates stored as decimals, converted to percentages only in chart display

### Time-Travel & History
- [ ] Time-travel works (respects dashboard timestamp selection)
- [ ] For positions: Only shows history from last rebalance to selected timestamp
- [ ] For strategies: Shows full historical range up to selected timestamp
- [ ] Timestamp handling uses Unix seconds internally

### Performance & UX
- [ ] Performance acceptable for large datasets (<3 seconds for 1000 timestamps)
- [ ] Error handling displays user-friendly messages
- [ ] Chart styling consistent with dashboard theme
- [ ] Loading indicators shown while calculating (for slow queries)

### Design Principles Compliance
- [ ] No `datetime.now()` used - all timestamps explicit
- [ ] Explicit error handling with debug info (no silent fallbacks)
- [ ] Fails loudly with "N/A" when correct data missing (no wrong fallback values)
- [ ] Token identity by contract (all queries use token_contract)

## Success Criteria

1. Users can click a button in All Strategies tab and see historical APR chart for any strategy
2. Users can click a button in Positions tab and see historical APR chart for any deployed position
3. Charts display with correct date ranges and APR values
4. Charts handle missing data gracefully without crashing
5. Chart generation completes within 3 seconds for typical datasets
6. Code follows all design principles documented in design_notes.md

---

**Implementation Time Estimate**: 4-6 hours
- Core logic (strategy_history.py): 2-3 hours
- Dashboard integration: 1-2 hours
- Testing and refinement: 1 hour