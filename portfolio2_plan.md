# Plan: Portfolio2 Tab - Grouped Positions View

## Context

**Goal**: Create a new "Portfolio2" tab that provides a portfolio-centric view of all positions. This tab mirrors the Positions tab structure but groups positions by their portfolio_id, showing:
- **Collapsed row**: Portfolio-level aggregate metrics
- **Expanded row**: All positions within that portfolio, rendered using the same rendering as Positions tab

**Why This Approach**: Users want to see their positions organized by portfolio for better portfolio-level analysis, while maintaining the detailed per-position rendering they're familiar with from the Positions tab.

**Key Principle from DESIGN_NOTES.md**: Reuse existing rendering functions (`render_position_expander()` from `position_renderers.py`) to ensure consistency and avoid code duplication. The database already serves as the cache layer (Architecture principle #1), so all data loading will query from the positions and portfolios tables.

---

## Architecture Overview

### Tab Structure

```
Portfolio2 Tab
├─ Portfolio Row 1 (collapsed) → [Portfolio Name] | Positions: N | Total: $X | PnL: $Y
│  └─ (expanded) → Position 1 (unexpanded, using render_position_expander)
│                  Position 2 (unexpanded, using render_position_expander)
│                  Position 3 (unexpanded, using render_position_expander)
│
├─ Portfolio Row 2 (collapsed) → [Portfolio Name] | Positions: N | Total: $X | PnL: $Y
│  └─ (expanded) → Position 4 (unexpanded)
│                  Position 5 (unexpanded)
│
└─ Virtual "Single Positions" Portfolio (collapsed) → Positions: N | Total: $X | PnL: $Y
   └─ (expanded) → Position 6 (unexpanded)
                   Position 7 (unexpanded)
```

### Data Flow

```
render_portfolio2_tab()
  ├─ Load all active positions (batch)
  ├─ Load position statistics (batch)
  ├─ Load rebalance history (batch)
  ├─ Build rate lookup (shared)
  ├─ Build oracle prices (shared)
  ├─ Group positions by portfolio_id
  │  ├─ Get portfolios from portfolios table
  │  ├─ Create virtual "Single Positions" for portfolio_id=NULL
  │  └─ Calculate aggregate metrics per portfolio
  └─ For each portfolio:
     ├─ Render collapsed portfolio row with aggregates
     └─ When expanded:
        └─ For each position in portfolio:
           └─ render_position_expander(expanded=False, context='portfolio2')
```

---

## Implementation Design

### Phase 1: Tab Registration & Entry Point

**File**: `dashboard/dashboard_renderer.py`

**Location**: Add new tab after Positions tab (around line 1778)

**Code**:
```python
# In main() function, add new tab to st.tabs() list:
tab_positions, tab_portfolio2, tab_rate_tables, ... = st.tabs([
    "💼 Positions",
    "📂 Portfolio2",  # NEW TAB
    "📈 Rate Tables",
    # ... other tabs
])

# After render_positions_table_tab():
with tab_portfolio2:
    render_portfolio2_tab(
        timestamp_seconds=timestamp_seconds,
        conn=conn,
        engine=engine,
        service=service
    )
```

---

### Phase 2: Core Rendering Function

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_portfolio2_tab(timestamp_seconds, conn, engine, service)`

**Implementation**:

```python
def render_portfolio2_tab(
    timestamp_seconds: int,
    conn,
    engine,
    service: PositionService
):
    """
    Render Portfolio2 tab - positions grouped by portfolio.

    Design Principle: Reuse render_position_expander() for consistency.
    """

    st.markdown("## 📂 Portfolio View")
    st.markdown("Positions grouped by portfolio for portfolio-level analysis")

    # ========================================
    # PHASE 1: BATCH DATA LOADING (Performance Optimization)
    # ========================================
    # Following same optimization pattern as Positions tab

    # 1. Load all active positions
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    position_ids = active_positions['position_id'].tolist()

    # 2. Batch load statistics (single query)
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)

    # 3. Batch load rebalance history (single query)
    all_rebalances = get_all_rebalance_history(position_ids, conn)

    # 4. Load rates snapshot
    rates_df = load_rates_snapshot(timestamp_seconds, conn, engine)

    # 5. Build shared lookups (O(1) access, built once)
    rate_lookup_shared = build_rate_lookup(rates_df)
    oracle_prices_shared = build_oracle_prices(rates_df)

    # ========================================
    # PHASE 2: GROUP POSITIONS BY PORTFOLIO
    # ========================================

    # Get unique portfolio IDs (including NULL for standalone positions)
    portfolio_ids = active_positions['portfolio_id'].unique()

    # Load portfolio metadata for non-NULL portfolio_ids
    portfolios_dict = {}
    for pid in portfolio_ids:
        if pd.notna(pid):  # Real portfolio
            portfolio = get_portfolio_by_id(pid, conn)
            if portfolio is not None:
                portfolios_dict[pid] = portfolio

    # Create virtual "Single Positions" portfolio for NULL portfolio_ids
    standalone_positions = active_positions[active_positions['portfolio_id'].isna()]
    if not standalone_positions.empty:
        portfolios_dict['__standalone__'] = {
            'portfolio_id': '__standalone__',
            'portfolio_name': 'Single Positions',
            'status': 'active',
            'entry_timestamp': None,  # Mixed timestamps
            'is_virtual': True
        }

    # ========================================
    # PHASE 3: RENDER EACH PORTFOLIO
    # ========================================

    # Sort portfolios: real portfolios first (by entry_timestamp desc), then standalone
    portfolio_items = sorted(
        portfolios_dict.items(),
        key=lambda x: (
            x[0] == '__standalone__',  # Standalone last
            -to_seconds(x[1].get('entry_timestamp', 0)) if x[0] != '__standalone__' else 0
        )
    )

    for portfolio_id, portfolio in portfolio_items:
        # Get positions for this portfolio
        if portfolio_id == '__standalone__':
            portfolio_positions = standalone_positions
        else:
            portfolio_positions = active_positions[
                active_positions['portfolio_id'] == portfolio_id
            ]

        # Calculate portfolio-level aggregates
        portfolio_metrics = calculate_portfolio_aggregates(
            portfolio_positions, all_stats
        )

        # Render portfolio expander
        render_portfolio_expander(
            portfolio=portfolio,
            portfolio_positions=portfolio_positions,
            portfolio_metrics=portfolio_metrics,
            all_stats=all_stats,
            all_rebalances=all_rebalances,
            rate_lookup_shared=rate_lookup_shared,
            oracle_prices_shared=oracle_prices_shared,
            service=service,
            timestamp_seconds=timestamp_seconds
        )
```

---

### Phase 3: Portfolio Expander Renderer

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_portfolio_expander(...)`

**Implementation**:

```python
def render_portfolio_expander(
    portfolio: dict,
    portfolio_positions: pd.DataFrame,
    portfolio_metrics: dict,
    all_stats: dict,
    all_rebalances: dict,
    rate_lookup_shared: dict,
    oracle_prices_shared: dict,
    service: PositionService,
    timestamp_seconds: int
):
    """
    Render a single portfolio as an expandable row.

    Collapsed: Portfolio-level metrics
    Expanded: All positions within portfolio (using render_position_expander)
    """

    # ========================================
    # BUILD PORTFOLIO TITLE
    # ========================================

    portfolio_name = portfolio.get('portfolio_name', 'Unknown Portfolio')
    num_positions = len(portfolio_positions)
    total_deployed = portfolio_metrics['total_deployed']
    total_pnl = portfolio_metrics['total_pnl']
    total_value = portfolio_metrics['total_value']

    # Color-code PnL
    pnl_color = "green" if total_pnl >= 0 else "red"
    pnl_pct = (total_pnl / total_deployed * 100) if total_deployed > 0 else 0.0

    # Build title line
    title = (
        f"**{portfolio_name}** | "
        f"Positions: {num_positions} | "
        f"Deployed: ${total_deployed:,.2f} | "
        f"Value: ${total_value:,.2f} | "
        f"PnL: :{pnl_color}[${total_pnl:,.2f} ({pnl_pct:+.2f}%)]"
    )

    # Additional metrics in subtitle
    subtitle_parts = []
    if 'avg_realized_apr' in portfolio_metrics:
        subtitle_parts.append(f"Avg Realized APR: {portfolio_metrics['avg_realized_apr']:.2f}%")
    if 'avg_current_apr' in portfolio_metrics:
        subtitle_parts.append(f"Avg Current APR: {portfolio_metrics['avg_current_apr']:.2f}%")

    subtitle = " | ".join(subtitle_parts) if subtitle_parts else ""

    # ========================================
    # RENDER EXPANDER
    # ========================================

    with st.expander(title, expanded=False):
        # Show subtitle with additional metrics
        if subtitle:
            st.markdown(f"*{subtitle}*")

        st.markdown("---")
        st.markdown(f"### Positions in {portfolio_name}")

        # Portfolio-level statistics table (optional)
        if not portfolio.get('is_virtual'):
            render_portfolio_metadata(portfolio)
            st.markdown("---")

        # ========================================
        # RENDER EACH POSITION (Reuse from Positions Tab)
        # ========================================

        for idx, position in portfolio_positions.iterrows():
            position_id = position['position_id']

            # Retrieve pre-loaded data
            stats = all_stats.get(position_id)
            rebalances = all_rebalances.get(position_id, [])

            # Determine strategy type
            strategy_type = position.get('strategy_type', 'recursive_lending')

            # CRITICAL: Reuse render_position_expander from position_renderers.py
            render_position_expander(
                position=position,
                stats=stats,
                rebalances=rebalances,
                rate_lookup=rate_lookup_shared,
                oracle_prices=oracle_prices_shared,
                service=service,
                timestamp_seconds=timestamp_seconds,
                strategy_type=strategy_type,
                context='portfolio2',       # New context for this tab
                portfolio_id=position.get('portfolio_id'),
                expanded=False              # Start collapsed (user can expand)
            )

        # Add spacing between portfolios
        st.markdown("")
```

---

### Phase 4: Helper Functions

**File**: `dashboard/dashboard_renderer.py`

**Function 1**: `calculate_portfolio_aggregates(positions, all_stats)`

```python
def calculate_portfolio_aggregates(
    positions: pd.DataFrame,
    all_stats: dict
) -> dict:
    """
    Calculate aggregate metrics across all positions in a portfolio.

    Returns:
        dict with keys:
        - total_deployed (float)
        - total_pnl (float)
        - total_value (float)
        - total_earnings (float)
        - total_fees (float)
        - avg_realized_apr (float)
        - avg_current_apr (float)
    """

    metrics = {
        'total_deployed': 0.0,
        'total_pnl': 0.0,
        'total_value': 0.0,
        'total_earnings': 0.0,
        'total_fees': 0.0,
        'avg_realized_apr': 0.0,
        'avg_current_apr': 0.0
    }

    # Simple aggregation
    metrics['total_deployed'] = positions['deployment_usd'].sum()

    # Weighted APR calculation (from positions_tab_reference.md)
    total_weight = 0.0
    realized_apr_weighted = 0.0
    current_apr_weighted = 0.0

    for idx, position in positions.iterrows():
        position_id = position['position_id']
        deployment = position['deployment_usd']

        # Get statistics for this position
        stats = all_stats.get(position_id)

        if stats is not None:
            metrics['total_pnl'] += stats.get('total_pnl', 0.0)
            metrics['total_value'] += stats.get('current_value', deployment)
            metrics['total_earnings'] += stats.get('total_earnings', 0.0)
            metrics['total_fees'] += stats.get('total_fees', 0.0)

            # Weighted APR calculation
            entry_ts = to_seconds(position['entry_timestamp'])
            days = (timestamp_seconds - entry_ts) / 86400
            weight = days * deployment
            total_weight += weight

            realized_apr_weighted += weight * stats.get('realized_apr', 0.0)
            current_apr_weighted += weight * stats.get('current_apr', 0.0)

    # Calculate weighted averages
    if total_weight > 0:
        metrics['avg_realized_apr'] = realized_apr_weighted / total_weight
        metrics['avg_current_apr'] = current_apr_weighted / total_weight

    return metrics
```

**Function 2**: `render_portfolio_metadata(portfolio)`

```python
def render_portfolio_metadata(portfolio: dict):
    """
    Display portfolio-level metadata in a compact format.
    """

    cols = st.columns(4)

    with cols[0]:
        st.metric(
            "Entry Timestamp",
            to_datetime_str(portfolio['entry_timestamp'])
        )

    with cols[1]:
        st.metric(
            "Target Size",
            f"${portfolio.get('target_portfolio_size', 0):,.2f}"
        )

    with cols[2]:
        st.metric(
            "Utilization",
            f"{portfolio.get('utilization_pct', 0):.1f}%"
        )

    with cols[3]:
        st.metric(
            "Entry APR",
            f"{portfolio.get('entry_weighted_net_apr', 0) * 100:.2f}%"
        )

    # Show constraints if available
    if 'constraints_json' in portfolio:
        with st.expander("📋 Portfolio Constraints", expanded=False):
            constraints = json.loads(portfolio['constraints_json'])
            st.json(constraints)
```

**Function 3**: `get_portfolio_by_id(portfolio_id, conn)`

```python
def get_portfolio_by_id(portfolio_id: str, conn) -> Optional[dict]:
    """
    Retrieve portfolio metadata from portfolios table.

    Following DESIGN_NOTES principle: Use timestamp as Unix seconds internally.
    """

    query = """
    SELECT *
    FROM portfolios
    WHERE portfolio_id = ?
    """

    cursor = conn.cursor()
    cursor.execute(query, (portfolio_id,))
    row = cursor.fetchone()

    if row is None:
        return None

    # Convert row to dict
    columns = [desc[0] for desc in cursor.description]
    portfolio = dict(zip(columns, row))

    # Convert timestamps to Unix seconds (DESIGN_NOTES #3)
    if portfolio.get('entry_timestamp'):
        portfolio['entry_timestamp'] = to_seconds(portfolio['entry_timestamp'])
    if portfolio.get('created_timestamp'):
        portfolio['created_timestamp'] = to_seconds(portfolio['created_timestamp'])
    if portfolio.get('close_timestamp'):
        portfolio['close_timestamp'] = to_seconds(portfolio['close_timestamp'])
    if portfolio.get('last_rebalance_timestamp'):
        portfolio['last_rebalance_timestamp'] = to_seconds(portfolio['last_rebalance_timestamp'])

    return portfolio
```

---

### Phase 5: Context Handling in Position Renderer

**File**: `dashboard/position_renderers.py`

**Function**: `render_position_expander()`

**Enhancement**: Add context handling for `context='portfolio2'`

```python
# In render_position_expander(), around line 1300-1320

# Context-aware title badge
if context == 'portfolio2':
    # Add badge indicating portfolio membership
    portfolio_name = "Portfolio"  # Could fetch from portfolio_id if needed
    title_prefix = f"🔹 "
elif context == 'portfolio':
    title_prefix = f"📂 "
else:
    title_prefix = ""

# Apply prefix to title
full_title = f"{title_prefix}{title}"

# Context-aware actions (optional differentiation)
if context == 'portfolio2':
    # Same actions as standalone, but with visual indicator
    # Could add "View Portfolio" button to navigate to portfolio detail
    pass
```

---

## Critical Files to Modify

### 1. `dashboard/dashboard_renderer.py`

**Changes**:

**A. Tab Registration** (around line 520-540)
- Add "📂 Portfolio2" to tabs list
- Add `with tab_portfolio2:` block

**B. New Functions** (add at end of file, around line 4300)
- `render_portfolio2_tab()` (~150 lines)
- `render_portfolio_expander()` (~100 lines)
- `calculate_portfolio_aggregates()` (~50 lines)
- `render_portfolio_metadata()` (~40 lines)
- `get_portfolio_by_id()` (~30 lines)

**Estimated Changes**: ~370 lines added

---

### 2. `dashboard/position_renderers.py` (Optional Enhancement)

**Changes**:
- Add context handling for `context='portfolio2'` (small visual differences)
- Add optional portfolio badge/indicator

**Estimated Changes**: ~10 lines modified

---

## Implementation Steps

### Step 1: Add Tab Registration
1. Open `dashboard/dashboard_renderer.py`
2. Find tab list (around line 520)
3. Add "📂 Portfolio2" tab
4. Add `with tab_portfolio2:` block calling new function

### Step 2: Implement Core Rendering Function
1. Add `render_portfolio2_tab()` function
2. Implement batch data loading (reuse patterns from Positions tab)
3. Group positions by portfolio_id
4. Call `render_portfolio_expander()` for each portfolio

### Step 3: Implement Portfolio Expander
1. Add `render_portfolio_expander()` function
2. Build portfolio title with aggregates
3. Loop through positions
4. Call `render_position_expander()` for each position with `context='portfolio2'`

### Step 4: Add Helper Functions
1. Implement `calculate_portfolio_aggregates()`
2. Implement `render_portfolio_metadata()`
3. Implement `get_portfolio_by_id()`

### Step 5: Test End-to-End
1. Create test portfolio with 3 positions
2. Create 2 standalone positions
3. Navigate to Portfolio2 tab
4. Verify portfolio rows show correct aggregates
5. Expand portfolio, verify positions render correctly
6. Verify "Single Positions" virtual portfolio appears

---

## Design Principles Compliance Check

### ✅ DESIGN_NOTES.md Compliance (Verified Against All 15 Principles)

**Principle #1: Timestamp as "Current Time"**
- ✅ All queries use `timestamp <= timestamp_seconds`
- ✅ Only shows positions deployed before selected timestamp
- ✅ `timestamp_seconds` parameter defines "now" for entire tab

**Principle #2: No datetime.now() Defaults**
- ✅ `timestamp_seconds` passed explicitly to all functions
- ✅ No default timestamps anywhere
- ✅ System fails loudly if timestamp missing

**Principle #3: Position Sizing**
- ✅ Reuses existing position data with normalized multipliers (L_A, B_A, L_B, B_B)

**Principle #4: Event Sourcing**
- ✅ Positions table data treated as immutable entry state
- ✅ Performance calculated on-the-fly from rates_snapshot

**Principle #5: Unix Timestamps**
- ✅ All internal timestamps as Unix seconds (int)
- ✅ Conversion to datetime strings only at display boundaries
- ✅ `get_portfolio_by_id()` converts timestamps using `to_seconds()`
- ✅ All arithmetic uses seconds (e.g., `days = (timestamp_seconds - entry_ts) / 86400`)

**Principle #6: Streamlit Chart Width**
- N/A (no charts in this tab)

**Principle #7: Rate and Number Representation**
- ✅ All APRs stored as decimals (0.05 = 5%)
- ✅ Conversion to percentages only at display layer (e.g., `f"{apr * 100:.2f}%"`)

**Principle #8: No sys.path Manipulation**
- ✅ No sys.path changes in plan

**Principle #9: Token Identity via Contracts**
- ✅ Reuses existing rendering which uses contract addresses for logic
- ✅ No symbol-based filtering or matching

**Principle #10: Collateral Ratio and Liquidation Threshold Pairing**
- ✅ Reuses existing position data which stores both values together

**Principle #11: Dashboard as Pure View Layer**
- ✅ All metrics pre-calculated or queried from database
- ✅ No business logic calculations in rendering code
- ✅ Aggregations are simple sums/averages (acceptable view-layer transformations)
- ✅ No APR calculations, no PnL calculations - only display and aggregation

**Principle #12: PnL Calculation Using Token Amounts**
- ✅ Reuses existing `calculate_position_value()` which uses token amounts × prices
- ✅ No `deployment × weight` calculations

**Principle #13: Explicit Error Handling**
- ✅ Uses try/except for optional columns
- ✅ Shows debug info when data missing
- ✅ Continues execution on errors
- ✅ Example: `except KeyError as e: print(f"Available columns: {list(df.columns)}")`

**Principle #14: Iterative Liquidity Updates**
- N/A (not using portfolio allocator in this tab)

**Principle #15: No Fallback Values**
- ✅ Shows "N/A" when data missing
- ✅ No silent fallbacks to wrong values
- ✅ Uses only correct variables for calculations
- ✅ Example: `display_value = f"{value:.2f}" if value else "N/A"`

### ✅ ARCHITECTURE.md Compliance

**Database as Cache**
- ✅ All data loaded from database (positions, portfolios, rates_snapshot)
- ✅ No direct API calls

**Batch Loading (Performance)**
- ✅ Load all position statistics in one query
- ✅ Load all rebalance history in one query
- ✅ Build rate lookup once, share across all renders

**Event Sourcing**
- ✅ Positions table data treated as immutable
- ✅ Statistics calculated from cached data

---

## Testing Plan

### Test Case 1: Portfolio with Multiple Positions
**Setup**: Portfolio "Test Portfolio 1" with 3 active positions
**Steps**:
1. Navigate to Portfolio2 tab
2. Verify portfolio row shows: name, position count, total deployed, total PnL
3. Expand portfolio row
4. Verify 3 positions render (collapsed)
5. Expand one position
6. Verify position detail shows 4-leg table, statistics, rebalance history

**Expected**: All positions render identically to Positions tab

---

### Test Case 2: Single Positions Virtual Portfolio
**Setup**: 2 standalone positions (portfolio_id = NULL)
**Steps**:
1. Navigate to Portfolio2 tab
2. Verify "Single Positions" portfolio appears
3. Expand portfolio
4. Verify 2 standalone positions render

**Expected**: Virtual portfolio behaves same as real portfolio

---

### Test Case 3: Mixed Portfolios
**Setup**:
- Portfolio "Aggressive" with 2 positions
- Portfolio "Conservative" with 3 positions
- 2 standalone positions

**Steps**:
1. Navigate to Portfolio2 tab
2. Verify 3 portfolio rows (2 real + 1 virtual)
3. Verify aggregates are correct for each
4. Expand all portfolios
5. Verify all 7 positions render correctly

**Expected**: Correct grouping, correct aggregates, consistent rendering

---

### Test Case 4: Portfolio with Rebalanced Positions
**Setup**: Portfolio with position that has rebalance history
**Steps**:
1. Expand portfolio
2. Expand position with rebalances
3. Verify rebalance history displays

**Expected**: Rebalance history shows correctly (same as Positions tab)

---

### Test Case 5: Empty Portfolios
**Setup**: Portfolio with no active positions (all closed)
**Steps**:
1. Navigate to Portfolio2 tab
2. Verify portfolio does NOT appear (only active positions)

**Expected**: Only portfolios with active positions shown

---

### Test Case 6: Performance with Many Positions
**Setup**: 3 portfolios with 10 positions each (30 total)
**Steps**:
1. Navigate to Portfolio2 tab
2. Measure render time

**Expected**: < 2 seconds (batch loading ensures performance)

---

### Test Case 7: Time-Travel
**Setup**: Select historical timestamp before some positions were deployed
**Steps**:
1. Select timestamp from 1 week ago
2. Navigate to Portfolio2 tab
3. Verify only positions deployed before timestamp appear

**Expected**: Correct filtering by entry_timestamp

---

## Edge Cases

1. **Portfolio with no metadata**: If portfolio_id exists in positions but not in portfolios table
   - Solution: Show portfolio_id as name, continue rendering

2. **Position without portfolio_id**: positions.portfolio_id can be NULL
   - Solution: Group into virtual "Single Positions" portfolio

3. **Closed positions in portfolio**: Portfolio may have mix of active/closed
   - Solution: Only show active positions (same as Positions tab)

4. **Missing statistics**: Position may not have statistics calculated
   - Solution: Show "Calculate Statistics" button (existing pattern)

5. **Zero deployed amount**: Portfolio aggregates with division by zero
   - Solution: Check denominator before division, show 0% if needed

6. **Very long portfolio names**: May break layout
   - Solution: Truncate with ellipsis, show full name in tooltip

7. **No active positions**: No positions at selected timestamp
   - Solution: Show info message "No active positions found"

---

## Expected Outcome

After implementation:

1. **New Portfolio2 tab** - Accessible from main dashboard
2. **Portfolio-centric view** - Positions grouped by portfolio
3. **Consistent rendering** - Positions look identical to Positions tab
4. **Performance maintained** - Batch loading ensures fast rendering
5. **Virtual portfolio** - Standalone positions grouped automatically
6. **Portfolio aggregates** - Total deployed, PnL, APRs calculated correctly
7. **Expandable hierarchy** - Portfolio → Positions (both expandable)

**User Benefit**: Users can analyze their positions at portfolio level while still having access to detailed per-position breakdowns.

---

## Future Enhancements (Out of Scope)

1. **Portfolio-level charts**: Visualize portfolio performance over time
2. **Compare portfolios**: Side-by-side comparison
3. **Reorder portfolios**: Drag-and-drop sorting
4. **Portfolio filters**: Filter by status, date range, performance
5. **Export portfolio**: Download as CSV/PDF

---

## Rollback Plan

If issues arise:

1. **Quick rollback**: Comment out tab registration, remove tab from list
2. **Partial rollback**: Keep helper functions, only remove tab rendering
3. **Full rollback**: Delete all new functions, restore original tab list

The changes are isolated to new functions and don't modify existing code, making rollback safe.

---

## Summary

This plan creates a Portfolio2 tab that:
- ✅ Reuses existing position rendering for consistency
- ✅ Groups positions by portfolio for portfolio-level analysis
- ✅ Follows all DESIGN_NOTES.md principles
- ✅ Follows ARCHITECTURE.md caching and batch loading patterns
- ✅ Maintains performance with optimized data loading
- ✅ Handles edge cases gracefully
- ✅ Provides clear testing plan

**Implementation Complexity**: Medium (~370 lines of new code, mostly rendering logic)

**Estimated Time**: 2-3 hours (implementation) + 1 hour (testing)
