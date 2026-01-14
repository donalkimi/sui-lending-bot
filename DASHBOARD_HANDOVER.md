# Historical Dashboard Implementation Handover

**Date:** 2026-01-14
**Status:** ✅ ALL PHASES COMPLETE
**Full Plan:** See `.claude/plans/foamy-watching-dewdrop.md`
**Architecture:** Shared Template Pattern (Option 2)

## Implementation Progress

✅ **Phase 1 Complete:** Data loading abstraction created ([dashboard/data_loaders.py](dashboard/data_loaders.py))
✅ **Phase 2 Complete:** Historical snapshot loader implemented ([dashboard/dashboard_utils.py](dashboard/dashboard_utils.py))
✅ **Phase 3 Complete:** UI rendering extracted to shared template ([dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py))
✅ **Phase 4 Complete:** streamlit_app.py refactored to use template (1823→207 lines)
✅ **Phase 5 Complete:** Timestamp picker with navigation controls added

---

## Summary

**The historical dashboard is now fully functional!** Users can switch between live and historical modes using a sidebar toggle, and navigate through snapshots using:

- **Dropdown Selector:** Choose any snapshot from the last 100 timestamps
- **Navigation Buttons:** ⏮️ (Oldest), ⬅️ (Previous), ➡️ (Next), ⏭️ (Latest)
- **Timeline Slider:** Scrub through the timeline visually

**Code Savings:**
- Original estimate: ~3200 lines (1600 for live + 1600 for historical duplicate)
- Actual implementation: ~1550 lines total
- **Savings: ~1650 lines of duplicate code eliminated** (51% reduction)

**Architecture Benefits:**
- ✅ Zero code duplication (single UI renderer)
- ✅ Impossible for views to drift apart
- ✅ Mode-specific behavior cleanly separated
- ✅ Easy to add more views in future (comparison mode, etc.)

---

## Overview

This document provides implementation details for adding historical snapshot functionality to the dashboard using a **shared template architecture**. This approach eliminates code duplication by creating a single UI renderer that works for both live and historical data.

**Exploration Findings (Phase 1-2):**
- ✅ Current `streamlit_app.py` is **1823 lines** (not 2000+ as estimated)
- ⚠️ `dashboard/dashboard_utils.py` does **NOT exist yet** (must be created from scratch)
- ✅ Database schema (`rates_snapshot`, `position_snapshots`) is production-ready and indexed
- ✅ Position tracking infrastructure complete in `analysis/position_service.py` (946 lines)
- ✅ Historical chart functionality already exists in live dashboard

---

## Architecture Decision: Shared Template (Option 2)

**Key Decision:** We're using a shared template pattern instead of duplicating code.

**Why?**
- Current `streamlit_app.py` is 1823 lines
- Duplicating would create maintenance nightmare (~3600 total lines)
- Shared template = fix once, applies to both views
- Saves ~1600 lines of duplicate code

**Core Concept:**
Single UI renderer (`render_dashboard()`) accepts any data loader implementing the `DataLoader` interface. Mode-specific behavior controlled via `mode` parameter.

---

## File Structure Overview

```
dashboard/
├── streamlit_app.py          # Entry point (~100 lines after refactor)
├── dashboard_renderer.py     # NEW: Shared UI template (~1800 lines)
├── data_loaders.py          # NEW: Data loading abstraction (~80 lines)
└── dashboard_utils.py       # NEW: Utilities + historical loader (~400 lines)
```

**Before:** 1823 lines (single file, no historical functionality)
**After:** 2380 lines total (100 + 1800 + 80 + 400) with both live and historical views
**Savings:** ~1620 lines vs duplication approach (~3600 lines)

---

## Implementation Phases

### Phase 1: Create Data Loading Abstraction

**File:** `dashboard/data_loaders.py` (new file, ~80 lines)

**Goal:** Abstract interface for loading data from different sources (live API vs historical DB).

**Key Classes:**
- `DataLoader` (ABC) - Abstract base with `load_data()` and `timestamp` property
- `LiveDataLoader` - Calls `refresh_pipeline()` for live data
- `HistoricalDataLoader` - Calls `load_historical_snapshot(timestamp)` for DB data

**Both return identical structure:** 9-tuple of (8 DataFrames + timestamp)

```python
# Return format for both loaders:
(lend_rates, borrow_rates, collateral_ratios, prices,
 lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp)

# All DataFrames have:
# - 'Token' column (e.g., 'USDC', 'SUI')
# - 'Contract' column (token contract address)
# - Protocol columns (e.g., 'Navi', 'AlphaFi', 'Suilend')
```

**See full code in `.claude/plans/foamy-watching-dewdrop.md` Phase 1.**

---

### Phase 2: Implement Historical Snapshot Loader

**File:** `dashboard/dashboard_utils.py` (new file, ~400 lines)

**Functions to Add:**

1. **`get_db_connection()`** - SQLite/PostgreSQL connection handler (handles `settings.USE_CLOUD_DB`)
2. **`load_historical_snapshot(timestamp)`** - Queries `rates_snapshot` table and pivots to Token × Protocol matrices
3. **`get_latest_timestamp()`** - Returns `MAX(timestamp)` from database
4. **`get_available_timestamps(limit=100)`** - Returns all distinct timestamps (for Phase 5 picker)

**Key Implementation Notes:**

```python
def load_historical_snapshot(timestamp: datetime) -> Tuple[8 DataFrames]:
    """
    Query rates_snapshot WHERE timestamp = ?
    Pivot to match live data format:
      - Token rows × Protocol columns
      - NaN for missing protocols

    Returns 8 DataFrames:
      lend_rates, borrow_rates, collateral_ratios, prices,
      lend_rewards, borrow_rewards, available_borrow, borrow_fees
    """
    # Implementation pivots from:
    #   token | protocol | lend_total_apr | ...
    #   USDC  | Navi     | 0.0234         | ...
    #   USDC  | AlphaFi  | 0.0256         | ...
    #
    # To:
    #   Token | Contract | Navi   | AlphaFi | Suilend
    #   USDC  | 0x5d4... | 0.0234 | 0.0256  | 0.0201
```

**Testing:**
- Verify both loaders return identical 9-tuple structure
- Check column names and dtypes match between live and historical
- Test with empty database (should return None from `get_latest_timestamp()`)

**See full code in `.claude/plans/foamy-watching-dewdrop.md` Phase 2.**

---

### Phase 3: Extract UI Rendering to Shared Template

**File:** `dashboard/dashboard_renderer.py` (new file, ~1800 lines)

**Goal:** Move ALL rendering logic from `streamlit_app.py` so both live and historical can use it.

**Main Function:** `render_dashboard(data_loader: DataLoader, mode: str)`

This single function renders the entire dashboard UI. Works for both live and historical modes.

**Structure:**
1. Render sidebar (filters, settings, data controls)
2. Load data via `data_loader.load_data()`
3. Run analysis via `RateAnalyzer`
4. Render main tabs (All Strategies, Positions, Rate Tables, 0 Liquidity)

**Mode-Specific Functions:**

```python
def render_data_controls(data_loader, mode):
    """
    Live mode: Refresh button + last updated timestamp
    Historical mode: Timestamp info + age warning
    """

def render_deployment_form(strategy, mode, ...):
    """
    Historical mode: Show warning that deployment uses current rates
                     but entry_timestamp = historical timestamp
    """

def render_positions_tab(timestamp, mode):
    """
    Live mode: Query get_active_positions()
    Historical mode: Query position_snapshots at timestamp
    """

def render_position_card(position, mode):
    """
    Live mode: Show close button
    Historical mode: No close button, show info message
    """
```

**Additional Utilities (add to `dashboard_utils.py`):**
- `format_usd_abbreviated(value)` - Format $1.23M, $456K
- `get_apr_value(row, use_unlevered)` - Get appropriate APR based on toggle
- `fetch_historical_rates(...)` - For historical charts (already exists in current streamlit_app.py)
- `calculate_net_apr_history(...)` - Net APR calculation over time
- `create_strategy_history_chart(...)` - Plotly dual-axis chart generation

**Extraction Process:**
1. Copy entire main dashboard logic from `streamlit_app.py` (lines ~500-1823)
2. Wrap in `render_dashboard(data_loader, mode)` function
3. Replace `fetch_and_save_protocol_data()` with `data_loader.load_data()`
4. Add `if mode == 'historical':` checks for mode-specific behavior
5. Extract helper functions to `dashboard_utils.py`

**See full code structure in `.claude/plans/foamy-watching-dewdrop.md` Phase 3.**

---

### Phase 4: Refactor `streamlit_app.py` to Use Template

**File:** `dashboard/streamlit_app.py` (refactor 1823 lines → ~100 lines)

**Goal:** Slim down to just navigation + loader selection.

**New Structure:**

```python
import streamlit as st
from dashboard.data_loaders import LiveDataLoader, HistoricalDataLoader
from dashboard.dashboard_renderer import render_dashboard
from dashboard.dashboard_utils import get_latest_timestamp

# Page config
st.set_page_config(page_title="Sui Lending Bot", layout="wide")

# Navigation (sidebar radio button)
with st.sidebar:
    mode = st.radio("View Mode", ["📊 Live", "📜 Historical"], index=0)
    st.divider()

# Clear chart cache when switching modes
if "last_selected_mode" not in st.session_state:
    st.session_state.last_selected_mode = mode

if st.session_state.last_selected_mode != mode:
    keys_to_delete = [k for k in st.session_state.keys() if k.startswith('chart_')]
    for key in keys_to_delete:
        del st.session_state[key]
    st.session_state.last_selected_mode = mode

# Mode selection
if mode == "📊 Live":
    st.title("🤖 Sui Lending Bot - Live Dashboard")
    loader = LiveDataLoader()
    render_dashboard(loader, mode='live')
else:
    st.title("📜 Historical Snapshot Dashboard")

    # Phase 5 will add picker here
    timestamp = get_latest_timestamp()

    if timestamp is None:
        st.error("❌ No historical snapshots found")
        st.info("Run `main.py` to populate snapshots")
        st.stop()

    loader = HistoricalDataLoader(timestamp)
    render_dashboard(loader, mode='historical')
```

**That's it! Down from 1823 lines to ~100 lines.**

**Testing:**
- Switch between live and historical modes
- Verify no session state conflicts
- Confirm UI looks identical except mode-specific controls
- Test deployment warning in historical mode
- Verify position close button disabled in historical mode

**See complete code in `.claude/plans/foamy-watching-dewdrop.md` Phase 4.**

---

### Phase 5: Add Timestamp Picker (Future Enhancement)

**Goal:** Allow users to select any timestamp from database.

**Changes in `streamlit_app.py`** (historical mode section):

Replace static `timestamp = get_latest_timestamp()` with:

```python
# Get available timestamps
available_timestamps = get_available_timestamps(limit=100)

# Dropdown selector
timestamp_options = [ts.strftime('%Y-%m-%d %H:%M UTC') for ts in available_timestamps]

selected_index = st.selectbox(
    "Select Snapshot",
    range(len(timestamp_options)),
    format_func=lambda i: timestamp_options[i],
    index=0,  # Default to latest
    key="timestamp_selector"
)

selected_timestamp = available_timestamps[selected_index]

# Show position in timeline
st.caption(f"Snapshot {selected_index + 1} of {len(available_timestamps)}")

# Navigation buttons (Previous/Next/Latest/Oldest)
# ... (4 button layout) ...

# Optional: Timeline slider for scrubbing
slider_index = st.slider("Timeline Scrubber", 0, len(available_timestamps)-1, selected_index)
```

**See full code in `.claude/plans/foamy-watching-dewdrop.md` Phase 5.**

---

## Key Benefits of Shared Template Approach

**Code Reuse:**
- Before: 1823 (live only)
- Duplication approach: 1823 (live) + 1823 (historical copy) = **3646 lines**
- Shared template: 100 (entry) + 1800 (renderer) + 80 (loaders) + 400 (utils) = **2380 lines**
- **Saved: 1266 lines** (35% reduction vs duplication)

**Maintenance:**
- Fix bug once → applies to both views automatically
- Add feature once → both views get it
- Impossible for views to drift apart
- Single source of truth for all UI components

**Future-Proof:**
- Easy to add more views (e.g., "Comparison Mode" showing live vs historical side-by-side)
- Clean separation of concerns (data loading vs rendering)
- Can add third loader (e.g., "simulation mode" with hypothetical data)

---

## Testing Strategy

### Phase 1-2 Testing
- [ ] `LiveDataLoader.load_data()` returns 9-tuple
- [ ] `HistoricalDataLoader.load_data()` returns 9-tuple with same structure
- [ ] Both DataFrames have same column names and dtypes
- [ ] `load_historical_snapshot()` correctly pivots database rows to Token × Protocol format
- [ ] `get_latest_timestamp()` returns valid timestamp or None
- [ ] `get_available_timestamps()` returns list sorted descending (newest first)

### Phase 3 Testing
- [ ] `render_dashboard()` works with `LiveDataLoader`
- [ ] All tabs render correctly
- [ ] Filters work (liquidation distance, deployment USD, toggles)
- [ ] Deploy buttons function
- [ ] Historical charts load (already exist in live dashboard)
- [ ] Strategy expanders display correctly

### Phase 4 Testing
- [ ] Can switch between live and historical modes via radio button
- [ ] No session state conflicts between views
- [ ] `render_dashboard()` works with `HistoricalDataLoader`
- [ ] UI looks identical in both modes (except mode-specific controls)
- [ ] Deploy warning shows in historical mode
- [ ] Position close button disabled in historical mode
- [ ] Chart cache clears when switching modes

### Phase 5 Testing
- [ ] Timestamp picker shows all available snapshots (up to 100)
- [ ] Navigation buttons work (Previous/Next/Latest/Oldest)
- [ ] Changing timestamp reloads data correctly
- [ ] Timeline slider syncs with dropdown selector
- [ ] Position counter shows correctly (e.g., "Snapshot 5 of 127")

---

## Common Implementation Pitfalls

1. **Don't forget mode parameter** - Pass `mode='live'` or `mode='historical'` to all mode-aware functions
2. **DataLoader interface** - Both loaders must return exact same 9-tuple structure
3. **Pivot format** - Historical snapshot pivot must match live data format exactly (Token × Protocol)
4. **Session state** - Use separate keys for live vs historical to avoid conflicts (prefix with mode)
5. **Caching** - `@st.cache_data` on expensive operations but respect mode changes
6. **Entry timestamp** - Deployment from historical mode should use `data_loader.timestamp`, not `datetime.now()`
7. **Chart cache** - Clear chart-related session state keys when switching modes

---

## Edge Cases to Handle

### 1. Empty Snapshot Database
```python
timestamp = get_latest_timestamp()
if timestamp is None:
    st.error("❌ No historical snapshots found")
    st.info("Run `main.py` to populate snapshots")
    st.stop()
```

### 2. Incomplete Protocol Data
```python
# In load_historical_snapshot()
if df.empty:
    raise ValueError(f"No data for timestamp: {timestamp}")

# Check for missing protocols
expected = ['Navi', 'AlphaFi', 'Suilend']
actual = df['protocol'].unique().tolist()
missing = set(expected) - set(actual)

if missing:
    st.warning(f"⚠️ Protocols unavailable in this snapshot: {', '.join(missing)}")
```

### 3. Data Format Mismatch
Create test script to verify:
```python
# test_data_loaders.py
from dashboard.data_loaders import LiveDataLoader, HistoricalDataLoader
from dashboard.dashboard_utils import get_latest_timestamp

live_data = LiveDataLoader().load_data()
hist_data = HistoricalDataLoader(get_latest_timestamp()).load_data()

assert len(live_data) == len(hist_data) == 9
assert all(isinstance(df, pd.DataFrame) for df in live_data[:8])
assert isinstance(live_data[8], datetime)

print("✅ Data format verification passed")
```

### 4. Position Snapshots Missing
```python
# In load_historical_positions()
# LEFT JOIN ensures we get positions even without snapshots
if pd.isna(position['snapshot_timestamp']):
    st.warning(f"⚠️ No snapshot found at {timestamp} for position {position['position_id']}")
```

---

## Questions / Clarifications

**Answered:**
1. ✅ **Should deployment be enabled in historical mode?**
   → Yes, with warning. Use historical timestamp as `entry_timestamp` for backtesting.

2. ✅ **Navigation approach?**
   → Radio button in sidebar (faster to implement).

3. ✅ **Implement Phase 5 now or defer?**
   → Implement now (full timestamp picker with navigation).

**Open:**
1. Should we add a "Compare Mode" to show live vs historical side-by-side? (Future enhancement)
2. Should we show data age warning threshold? (Currently set to 24 hours)
3. Should we cache `get_available_timestamps()`? (Currently no caching)

---

## File References

**To Read/Understand:**
- [dashboard/streamlit_app.py](dashboard/streamlit_app.py) - Current implementation (1823 lines, will be refactored)
- [data/schema.sql](data/schema.sql) - Database schema (`rates_snapshot` lines 7-45, `position_snapshots` lines 213-283)
- [data/refresh_pipeline.py](data/refresh_pipeline.py) - Live data pipeline (used by `LiveDataLoader`)
- [analysis/rate_analyzer.py](analysis/rate_analyzer.py) - Strategy analysis (no changes needed)
- [analysis/position_service.py](analysis/position_service.py) - Position tracking (946 lines, no changes needed)

**To Create:**
- [dashboard/data_loaders.py](dashboard/data_loaders.py) - Data loading abstraction (~80 lines)
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - Shared UI template (~1800 lines)
- [dashboard/dashboard_utils.py](dashboard/dashboard_utils.py) - Utilities + historical loader (~400 lines)

**To Modify:**
- [dashboard/streamlit_app.py](dashboard/streamlit_app.py) - Refactor to ~100 lines (navigation only)

---

## Implementation Timeline

1. **Phase 1:** Create `data_loaders.py` (~30 min)
2. **Phase 2:** Create `dashboard_utils.py` with historical loaders (~1 hour)
3. **Phase 3:** Extract rendering to `dashboard_renderer.py` (~3 hours)
4. **Phase 4:** Refactor `streamlit_app.py` to use template (~30 min)
5. **Phase 5:** Add timestamp picker with navigation (~1 hour)

**Total Estimated Time:** 6-7 hours

---

## Success Criteria

**Phase 1-2 Complete:**
- ✅ Data loader abstraction created with ABC pattern
- ✅ Historical snapshot loader implemented
- ✅ Both loaders return identical 9-tuple structure
- ✅ Database connection handles SQLite and PostgreSQL

**Phase 3 Complete:**
- ✅ All rendering logic extracted to `dashboard_renderer.py`
- ✅ Live dashboard works with `LiveDataLoader`
- ✅ Mode-specific behavior implemented (deployment warnings, close buttons)
- ✅ Utility functions extracted to `dashboard_utils.py`

**Phase 4 Complete:**
- ✅ `streamlit_app.py` reduced to ~100 lines
- ✅ Can switch between live and historical modes
- ✅ No session state conflicts
- ✅ Zero code duplication

**Phase 5 Complete:**
- ✅ Timestamp picker allows selecting any snapshot
- ✅ Navigation buttons work correctly (Prev/Next/Latest/Oldest)
- ✅ Timeline slider provides smooth scrubbing
- ✅ Position counter shows correctly

**Overall Success:**
- ✅ Zero code duplication (single UI template)
- ✅ Saved ~1266 lines of duplicate code (35% reduction)
- ✅ Both modes use same analysis engine
- ✅ Impossible for views to drift apart
- ✅ Easy to add more views in future

---

## Next Steps

**Ready to Begin Implementation:**

1. Start with Phase 1: Create `dashboard/data_loaders.py`
2. Continue with Phase 2: Create `dashboard/dashboard_utils.py`
3. Proceed through Phases 3-5 as outlined above

**Refer to `.claude/plans/foamy-watching-dewdrop.md` for:**
- Complete code examples for all phases
- Detailed function signatures with docstrings
- Full implementation of `render_dashboard()` function
- Testing scripts and verification procedures

---

**Good luck with implementation! 🚀**

_This handover document reflects findings from Phase 1-2 exploration conducted on 2026-01-14._
