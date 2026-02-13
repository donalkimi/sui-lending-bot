# Plan: Upgrade Position Rendering & Create Portfolio2 Tab

## Context

**Problem**: Position rendering currently requires passing 10+ parameters to `render_position_expander()`, making it cumbersome to reuse across tabs and creating tight coupling between callers and infrastructure details.

**Solution**: Create a clean batch wrapper API that:
1. Takes minimal parameters (position_ids, timestamp, context)
2. Handles all data loading internally based on `USE_CLOUD_DB` flag
3. Maintains performance through batch loading
4. Enables easy reuse across Positions tab, Portfolio2 tab, and future tabs

**Goals**:
- ✅ Cleaner API for position rendering
- ✅ Zero code duplication across tabs
- ✅ Maintained performance (batch loading)
- ✅ Easier to add new tabs in the future

**Design Principles**: This plan follows all 15 principles from DESIGN_NOTES.md (verified in compliance section).

---

## Architecture Overview

### Current State (Before)

```
Positions Tab
├─ Manually batch loads: stats, rebalances, rates
├─ Manually builds: rate_lookup, oracle_prices
├─ Manually loops through positions
└─ For each position:
   └─ render_position_expander(10+ parameters)
```

### Target State (After)

```
Infrastructure Layer (NEW)
├─ render_positions_batch(position_ids, timestamp, context)
│  ├─ Handles batch loading internally
│  ├─ Handles connection management internally
│  └─ Calls render_position_expander for each position

Positions Tab (REFACTORED)
└─ render_positions_batch(position_ids, timestamp, 'standalone')

Portfolio2 Tab (NEW)
├─ Groups positions by portfolio_id
├─ For each portfolio:
│  └─ render_positions_batch(portfolio_position_ids, timestamp, 'portfolio2')
```

---

## Phase 1: Create Batch Wrapper Infrastructure

**Goal**: Build reusable batch rendering function with clean API

### Stage 1.1: Create Batch Wrapper Function

**File**: `dashboard/position_renderers.py`

**Location**: Add near top of file (after imports, before existing renderers)

**Implementation**:

```python
def render_positions_batch(
    position_ids: List[str],
    timestamp_seconds: int,
    context: str = 'standalone'
) -> None:
    """
    Batch render multiple positions with optimized data loading.

    This is the primary entry point for rendering positions across all tabs.
    Handles all database connections and batch loading internally.

    Args:
        position_ids: List of position IDs to render
        timestamp_seconds: Unix timestamp defining "current time"
        context: Rendering context ('standalone', 'portfolio2', 'portfolio')

    Design Principle #5: Uses Unix seconds for all timestamps
    Design Principle #11: Dashboard as pure view - handles infrastructure internally
    """

    # Handle empty case
    if not position_ids:
        st.info("No positions to display.")
        return

    # ========================================
    # INFRASTRUCTURE SETUP (Internal)
    # ========================================
    # Design Principle: Function handles its own infrastructure
    # based on USE_CLOUD_DB global config

    from dashboard.dashboard_utils import get_db_connection, get_db_engine
    from analysis.position_service import PositionService

    conn = get_db_connection()
    engine = get_db_engine()
    service = PositionService(conn)

    # ========================================
    # BATCH DATA LOADING (Performance Optimization)
    # ========================================
    # Following ARCHITECTURE.md: Batch loading avoids N+1 queries

    # Load all position statistics (1 query for N positions)
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)

    # Load all rebalance history (1 query for N positions)
    all_rebalances = get_all_rebalance_history(position_ids, conn)

    # Load rates snapshot (1 query)
    rates_df = load_rates_snapshot(timestamp_seconds, conn, engine)

    # Build shared lookups (O(1) access for all positions)
    rate_lookup = build_rate_lookup(rates_df)
    oracle_prices = build_oracle_prices(rates_df)

    # ========================================
    # RENDER EACH POSITION
    # ========================================
    # Design Principle #13: Explicit error handling with debug info

    for position_id in position_ids:
        try:
            # Get position data
            position = service.get_position_by_id(position_id)

            if position is None:
                st.warning(f"Position {position_id} not found.")
                continue

            # Retrieve pre-loaded data
            stats = all_stats.get(position_id)
            rebalances = all_rebalances.get(position_id, [])

            # Determine strategy type (default to recursive_lending)
            strategy_type = position.get('strategy_type', 'recursive_lending')

            # Render using existing function
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
                expanded=False
            )

        except Exception as e:
            # Design Principle #13: Fail loudly with debug info, continue execution
            st.error(f"⚠️  Error rendering position {position_id}: {e}")
            print(f"⚠️  Error rendering position {position_id}: {e}")
            print(f"    Available position IDs: {position_ids}")
            # Continue rendering other positions
            continue
```

**Estimated Lines**: ~80 lines

---

### Stage 1.2: Create Helper Function (Optional)

**File**: `dashboard/position_renderers.py`

**Purpose**: Convenience function for rendering a single position

**Implementation**:

```python
def render_position_single(
    position_id: str,
    timestamp_seconds: int,
    context: str = 'standalone'
) -> None:
    """
    Render a single position.

    Convenience wrapper around render_positions_batch for single position.
    Note: Less efficient than batch rendering - prefer batch when possible.
    """
    render_positions_batch([position_id], timestamp_seconds, context)
```

**Estimated Lines**: ~15 lines

---

## Phase 2: Refactor Positions Tab

**Goal**: Update Positions tab to use new batch wrapper

### Stage 2.1: Update Positions Tab Rendering

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_positions_table_tab()` (lines ~1170-1748)

**Changes**:

**BEFORE** (Current Implementation):
```python
def render_positions_table_tab(timestamp_seconds, conn, engine, service):
    st.markdown("## 💼 Positions")

    # Load active positions
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    position_ids = active_positions['position_id'].tolist()

    # Batch load statistics
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)

    # Batch load rebalance history
    all_rebalances = get_all_rebalance_history(position_ids, conn)

    # Load rates
    rates_df = load_rates_snapshot(timestamp_seconds, conn, engine)
    rate_lookup_shared = build_rate_lookup(rates_df)
    oracle_prices_shared = build_oracle_prices(rates_df)

    # Render each position
    for idx, position in active_positions.iterrows():
        position_id = position['position_id']
        stats = all_stats.get(position_id)
        rebalances = all_rebalances.get(position_id, [])
        strategy_type = position.get('strategy_type', 'recursive_lending')

        render_position_expander(
            position=position,
            stats=stats,
            rebalances=rebalances,
            rate_lookup=rate_lookup_shared,
            oracle_prices=oracle_prices_shared,
            service=service,
            timestamp_seconds=timestamp_seconds,
            strategy_type=strategy_type,
            context='standalone',
            expanded=False
        )
```

**AFTER** (Refactored):
```python
def render_positions_table_tab(timestamp_seconds, conn, engine, service):
    """
    Render Positions tab showing all active positions.

    Design Principle #11: Pure view layer - delegates to batch renderer.
    """
    st.markdown("## 💼 Positions")

    # Load active positions (just metadata)
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

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

**Lines Removed**: ~50 lines (batch loading logic)
**Lines Added**: ~5 lines (batch wrapper call)
**Net Change**: -45 lines

---

### Stage 2.2: Remove Duplicate Helper Functions (Optional Cleanup)

**File**: `dashboard/dashboard_renderer.py`

**Functions to Consider Removing** (if they're duplicated in position_renderers.py):
- `get_all_position_statistics()` - Move to position_renderers.py if not already there
- `get_all_rebalance_history()` - Move to position_renderers.py if not already there
- `build_rate_lookup()` - Should already be in position_renderers.py
- `build_oracle_prices()` - Should already be in position_renderers.py

**Action**: Verify these helpers exist in position_renderers.py, then remove duplicates from dashboard_renderer.py

---

## Phase 3: Create Portfolio2 Tab

**Goal**: Build new Portfolio2 tab using batch wrapper

### Stage 3.1: Add Tab Registration

**File**: `dashboard/dashboard_renderer.py`

**Location**: Main dashboard function (around line 520-540)

**Changes**:

**Add to tab list**:
```python
# In main() or render_dashboard()
tab_positions, tab_portfolio2, tab_rate_tables, ... = st.tabs([
    "💼 Positions",
    "📂 Portfolio2",  # NEW TAB
    "📈 Rate Tables",
    # ... other tabs
])

# Add tab handler
with tab_portfolio2:
    render_portfolio2_tab(timestamp_seconds)
```

**Estimated Changes**: ~5 lines

---

### Stage 3.2: Create Portfolio2 Tab Renderer

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_portfolio2_tab()` (new function, add at end of file)

**Implementation**:

```python
def render_portfolio2_tab(timestamp_seconds: int):
    """
    Render Portfolio2 tab - positions grouped by portfolio.

    Design Principles:
    - #1: timestamp_seconds defines "current time"
    - #5: Uses Unix seconds internally
    - #11: Pure view layer - delegates to batch renderer
    """

    st.markdown("## 📂 Portfolio View")
    st.markdown("Positions grouped by portfolio for portfolio-level analysis")

    # ========================================
    # LOAD POSITIONS AND GROUP BY PORTFOLIO
    # ========================================

    from dashboard.dashboard_utils import get_db_connection
    from analysis.position_service import PositionService

    conn = get_db_connection()
    service = PositionService(conn)

    # Load all active positions
    active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)

    if active_positions.empty:
        st.info("No active positions found.")
        return

    # Group positions by portfolio_id
    portfolio_ids = active_positions['portfolio_id'].unique()

    # Load portfolio metadata for non-NULL portfolio_ids
    portfolios_dict = {}
    for pid in portfolio_ids:
        if pd.notna(pid):
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
            'is_virtual': True
        }

    # ========================================
    # RENDER EACH PORTFOLIO
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

        # Render portfolio expander
        render_portfolio_expander(
            portfolio=portfolio,
            portfolio_positions=portfolio_positions,
            timestamp_seconds=timestamp_seconds
        )
```

**Estimated Lines**: ~80 lines

---

### Stage 3.3: Create Portfolio Expander Function

**File**: `dashboard/dashboard_renderer.py`

**Function**: `render_portfolio_expander()` (new function)

**Implementation**:

```python
def render_portfolio_expander(
    portfolio: dict,
    portfolio_positions: pd.DataFrame,
    timestamp_seconds: int
):
    """
    Render a single portfolio as an expandable row.

    Collapsed: Portfolio-level aggregate metrics
    Expanded: All positions within portfolio (using batch renderer)

    Design Principle #11: Simple aggregations only (view layer)
    """

    # ========================================
    # CALCULATE PORTFOLIO AGGREGATES
    # ========================================

    portfolio_name = portfolio.get('portfolio_name', 'Unknown Portfolio')
    num_positions = len(portfolio_positions)
    total_deployed = portfolio_positions['deployment_usd'].sum()

    # Simple aggregation - no complex calculations
    # (PnL already pre-calculated in position_statistics)

    # ========================================
    # BUILD PORTFOLIO TITLE
    # ========================================

    title = (
        f"**{portfolio_name}** | "
        f"Positions: {num_positions} | "
        f"Total Deployed: ${total_deployed:,.2f}"
    )

    # ========================================
    # RENDER EXPANDER
    # ========================================

    with st.expander(title, expanded=False):
        st.markdown(f"### Positions in {portfolio_name}")

        # Portfolio metadata (optional)
        if not portfolio.get('is_virtual'):
            render_portfolio_metadata(portfolio)
            st.markdown("---")

        # ========================================
        # BATCH RENDER ALL POSITIONS IN PORTFOLIO
        # ========================================
        # Key design: Delegate to batch renderer

        position_ids = portfolio_positions['position_id'].tolist()

        # Determine context based on portfolio type
        context = 'portfolio2'

        # Use batch renderer (handles everything)
        render_positions_batch(
            position_ids=position_ids,
            timestamp_seconds=timestamp_seconds,
            context=context
        )
```

**Estimated Lines**: ~60 lines

---

### Stage 3.4: Create Helper Functions

**File**: `dashboard/dashboard_renderer.py`

**Function 1**: `get_portfolio_by_id()`

```python
def get_portfolio_by_id(portfolio_id: str, conn) -> Optional[dict]:
    """
    Retrieve portfolio metadata from portfolios table.

    Design Principle #5: Converts timestamps to Unix seconds internally.
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

    # Convert timestamps to Unix seconds (Design Principle #5)
    for ts_field in ['entry_timestamp', 'created_timestamp', 'close_timestamp', 'last_rebalance_timestamp']:
        if portfolio.get(ts_field):
            portfolio[ts_field] = to_seconds(portfolio[ts_field])

    return portfolio
```

**Estimated Lines**: ~30 lines

**Function 2**: `render_portfolio_metadata()` (optional)

```python
def render_portfolio_metadata(portfolio: dict):
    """Display portfolio-level metadata in compact format."""

    cols = st.columns(4)

    with cols[0]:
        st.metric("Entry Date", to_datetime_str(portfolio['entry_timestamp'])[:10])

    with cols[1]:
        st.metric("Target Size", f"${portfolio.get('target_portfolio_size', 0):,.0f}")

    with cols[2]:
        st.metric("Utilization", f"{portfolio.get('utilization_pct', 0):.1f}%")

    with cols[3]:
        st.metric("Entry APR", f"{portfolio.get('entry_weighted_net_apr', 0) * 100:.2f}%")
```

**Estimated Lines**: ~20 lines

---

## Phase 4: Testing & Validation

### Stage 4.1: Unit Testing (Optional)

**Create Test File**: `tests/test_position_batch_renderer.py`

**Tests to Add**:
1. Test `render_positions_batch()` with empty list
2. Test `render_positions_batch()` with single position
3. Test `render_positions_batch()` with multiple positions
4. Test `render_positions_batch()` with missing position_id
5. Test context parameter handling

**Mock Strategy**: Mock `get_db_connection()` and `get_db_engine()` to return test fixtures

---

### Stage 4.2: Integration Testing

**Test Case 1: Positions Tab**
- Navigate to Positions tab
- Verify all positions render correctly
- Verify performance (should be same as before)
- Verify statistics, rebalances, and detail tables display

**Test Case 2: Portfolio2 Tab**
- Navigate to Portfolio2 tab
- Verify portfolios are grouped correctly
- Verify "Single Positions" virtual portfolio appears
- Expand portfolio, verify positions render identically to Positions tab
- Expand individual position, verify detail table matches

**Test Case 3: Mixed Scenarios**
- Test with 10+ positions across 3 portfolios
- Test with all positions in one portfolio
- Test with all positions standalone
- Test with empty portfolios (all positions closed)

**Test Case 4: Performance**
- Load Portfolio2 tab with 20 positions across 5 portfolios
- Verify render time < 2 seconds
- Verify batch loading (should see 3 queries, not 60)

---

### Stage 4.3: Validation Checklist

**Positions Tab:**
- ✅ All positions display correctly
- ✅ Statistics match previous implementation
- ✅ Rebalance history displays
- ✅ Action buttons work (Rebalance, Close)
- ✅ Performance maintained (< 2 sec for 10 positions)

**Portfolio2 Tab:**
- ✅ Portfolios grouped correctly
- ✅ Virtual "Single Positions" portfolio appears
- ✅ Portfolio aggregates correct (total deployed, position count)
- ✅ Positions render identically to Positions tab
- ✅ Context parameter works ('portfolio2')
- ✅ Performance maintained (< 2 sec for 20 positions)

**Code Quality:**
- ✅ No code duplication between tabs
- ✅ All DESIGN_NOTES.md principles followed
- ✅ Clean API (minimal parameters)
- ✅ Self-contained functions (handle own infrastructure)

---

## Implementation Steps Summary

### Step 1: Create Batch Wrapper (Phase 1)
1. Add `render_positions_batch()` to position_renderers.py
2. Add `render_position_single()` helper (optional)
3. Test wrapper in isolation

### Step 2: Refactor Positions Tab (Phase 2)
1. Update `render_positions_table_tab()` to use batch wrapper
2. Remove duplicate helper functions
3. Test Positions tab thoroughly
4. Verify performance maintained

### Step 3: Create Portfolio2 Tab (Phase 3)
1. Add tab registration
2. Add `render_portfolio2_tab()` function
3. Add `render_portfolio_expander()` function
4. Add helper functions (`get_portfolio_by_id()`, etc.)
5. Test Portfolio2 tab thoroughly

### Step 4: Validate (Phase 4)
1. Run integration tests
2. Verify performance
3. Check code quality
4. Update documentation

---

## Files Modified Summary

### New Functions Added

**`dashboard/position_renderers.py`** (~95 lines added):
- `render_positions_batch()` - Main batch wrapper (~80 lines)
- `render_position_single()` - Single position helper (~15 lines)

**`dashboard/dashboard_renderer.py`** (~190 lines added, ~50 removed = +140 net):
- `render_portfolio2_tab()` - Portfolio2 tab entry point (~80 lines)
- `render_portfolio_expander()` - Portfolio expander (~60 lines)
- `get_portfolio_by_id()` - Portfolio metadata loader (~30 lines)
- `render_portfolio_metadata()` - Portfolio metadata display (~20 lines)

**Tab registration** (~5 lines):
- Add Portfolio2 to tabs list

### Functions Modified

**`dashboard/dashboard_renderer.py`**:
- `render_positions_table_tab()` - Refactored to use batch wrapper (~45 lines removed)

### Total Changes

- **Lines added**: ~240 lines (new infrastructure + Portfolio2 tab)
- **Lines removed**: ~50 lines (duplicate logic in Positions tab)
- **Net change**: ~190 lines
- **Code duplication eliminated**: ~50 lines per tab (huge win for maintainability)

---

## Design Principles Compliance

### ✅ DESIGN_NOTES.md Compliance (All 15 Principles)

**Principle #1: Timestamp as "Current Time"**
- ✅ All functions use `timestamp_seconds` parameter
- ✅ No datetime.now() calls
- ✅ Timestamp defines "current time" throughout

**Principle #2: No datetime.now() Defaults**
- ✅ `timestamp_seconds` required parameter
- ✅ No default timestamps
- ✅ Fail loudly if missing

**Principle #3: Position Sizing**
- ✅ Reuses existing position multipliers (L_A, B_A, L_B, B_B)

**Principle #4: Event Sourcing**
- ✅ Positions table treated as immutable
- ✅ Performance calculated from rates_snapshot

**Principle #5: Unix Timestamps**
- ✅ All internal timestamps as Unix seconds (int)
- ✅ Conversion only at boundaries (DB/UI)
- ✅ `get_portfolio_by_id()` converts to seconds

**Principle #6: Streamlit Chart Width**
- N/A (no charts added)

**Principle #7: Rate and Number Representation**
- ✅ All rates stored as decimals (0.05 = 5%)
- ✅ Conversion to percentages only at display

**Principle #8: No sys.path Manipulation**
- ✅ No sys.path changes

**Principle #9: Token Identity via Contracts**
- ✅ Reuses existing rendering (uses contracts)

**Principle #10: Collateral Ratio and Liquidation Threshold Pairing**
- ✅ Reuses existing position data (both stored together)

**Principle #11: Dashboard as Pure View Layer**
- ✅ Batch wrapper handles infrastructure
- ✅ No business logic in dashboard functions
- ✅ Simple aggregations only (sum, count)

**Principle #12: PnL Calculation Using Token Amounts**
- ✅ Reuses existing calculations (token amounts × prices)

**Principle #13: Explicit Error Handling**
- ✅ Try/except with debug info
- ✅ Continues on errors
- ✅ Shows available data when errors occur

**Principle #14: Iterative Liquidity Updates**
- N/A (not using allocator)

**Principle #15: No Fallback Values**
- ✅ Shows "N/A" when data missing
- ✅ No silent fallbacks

### ✅ ARCHITECTURE.md Compliance

**Database as Cache**
- ✅ All data from database
- ✅ No direct API calls

**Batch Loading**
- ✅ 3 queries for N positions (not 3×N)
- ✅ Shared lookups (O(1) access)

**Event Sourcing**
- ✅ Immutable position data
- ✅ On-the-fly calculations

---

## Rollback Plan

### If Issues in Phase 1 (Batch Wrapper)
- **Action**: Don't use wrapper yet, keep existing Positions tab as-is
- **Impact**: None (new code not used yet)

### If Issues in Phase 2 (Positions Tab Refactor)
- **Action**: Revert `render_positions_table_tab()` to original implementation
- **Rollback File**: Keep backup of original function
- **Impact**: Positions tab works as before, wrapper unused

### If Issues in Phase 3 (Portfolio2 Tab)
- **Action**: Remove Portfolio2 from tab list, keep wrapper for future use
- **Impact**: Portfolio2 tab not visible, Positions tab unaffected

### Nuclear Rollback
- **Action**: Revert all changes, restore original files
- **Git**: `git revert <commit-hash>`
- **Impact**: System returns to pre-refactor state

---

## Future Enhancements (Out of Scope)

1. **Portfolio-level charts**: Visualize portfolio performance over time
2. **Compare portfolios**: Side-by-side comparison
3. **Export functionality**: Download portfolio/positions as CSV
4. **Filtering**: Filter positions by status, tokens, protocols
5. **Sorting**: Sort portfolios by PnL, size, entry date
6. **Search**: Search positions by token, protocol, or ID
7. **Bulk actions**: Close multiple positions at once

---

## Conclusion

This plan provides a clean, maintainable architecture for position rendering:

**Key Benefits:**
- ✅ **Clean API**: 3 parameters instead of 10+
- ✅ **Zero duplication**: One batch renderer, multiple tabs
- ✅ **Performance**: Batch loading maintained
- ✅ **Maintainability**: Change once, update everywhere
- ✅ **Extensibility**: Easy to add new tabs
- ✅ **Principles compliant**: All 15 DESIGN_NOTES.md principles followed

**Implementation Complexity**: Medium
- **Phase 1**: 2-3 hours (batch wrapper + testing)
- **Phase 2**: 1-2 hours (refactor Positions tab)
- **Phase 3**: 3-4 hours (create Portfolio2 tab)
- **Phase 4**: 1-2 hours (testing & validation)
- **Total**: 7-11 hours

**Risk Level**: Low-Medium
- Phase 1: Low risk (new code, not used yet)
- Phase 2: Medium risk (modifies existing Positions tab)
- Phase 3: Low risk (new tab, isolated)
- Rollback plan available for all phases
