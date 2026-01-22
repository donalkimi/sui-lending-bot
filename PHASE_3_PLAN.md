# Phase 3: Full Modal Implementation Plan

## Previous Phases Summary

### Phase 1: Database Cache Foundation ✅ COMPLETED
- Created `analysis_cache` and `chart_cache` SQLite tables
- Implemented cache methods in `RateTracker` class
- Modified `refresh_pipeline` to auto-save analysis results
- **Result**: Dashboard loads instantly from cache (0.7ms vs 99.7 seconds)

### Phase 2: Sortable Table with Checkbox Selection ✅ COMPLETED
- Removed clunky expander UI (127 lines deleted)
- Added sortable table with 8 columns (Token Pair, Protocol A/B, Net APR, APR 5d/30d, Days to Breakeven, Max Size)
- Implemented checkbox selection for row interaction
- Added placeholder modal (`show_placeholder_modal()`)
- Added comprehensive debug logging throughout dashboard
- **Result**: Fast, sortable table UI (21-108ms render time)

---

## Phase 3: Full Modal Implementation

### Overview

**Goal**: Replace the placeholder modal with a full-featured strategy details modal

**What**: Comprehensive modal dialog that displays:
- Strategy overview (tokens, protocols, APR metrics)
- Interactive charts (APR trends, position sizing)
- Position deployment calculator
- Risk metrics and warnings
- Action buttons (Deploy, Export, Close)

**Why**:
- Better user experience for evaluating strategies
- Visual representation of strategy performance over time
- Integrated deployment workflow
- Consolidates all strategy details in one place

### Key Features

1. **Strategy Overview Section**
   - Token triple display with logos/icons
   - Protocol pair information
   - Current Net APR (large, prominent)
   - APR 5d, APR 30d metrics
   - Days to breakeven
   - Max position size
   - Liquidity availability

2. **APR Trend Chart**
   - Historical APR data (30 days)
   - Line chart showing Net APR over time
   - Highlight current APR value
   - Show min/max/avg APR over period
   - Cached chart HTML from `chart_cache` table

3. **Position Calculator**
   - Deployment amount input (USD)
   - Calculate position sizes for each leg
   - Show expected returns (daily, weekly, monthly, yearly)
   - Display fees breakdown
   - Real-time breakeven calculation

4. **Risk Metrics**
   - Liquidation distance visualization
   - Collateral health indicator
   - Protocol risks (if applicable)
   - Warning messages for edge cases

5. **Action Buttons**
   - **Deploy**: Opens position deployment flow
   - **Export**: Download strategy details as JSON/CSV
   - **Close**: Dismiss modal

### Design Principles

- **Performance**: Leverage Phase 1 cache infrastructure
  - Use `chart_cache` table for pre-rendered charts
  - Load chart HTML instantly without regeneration
  - Only compute on cache miss

- **Consistency**: Match existing dashboard styling
  - Use same color scheme and fonts
  - Maintain Streamlit's native component look
  - Follow DESIGN_NOTES.md guidelines

- **Responsiveness**: Modal should render quickly
  - Target: <500ms modal open time
  - Lazy load charts (only render when modal opens)
  - Use cached data whenever possible

### Critical Files to Modify

1. **dashboard/dashboard_renderer.py** (~1,400 lines)
   - Replace `show_placeholder_modal()` function
   - Add `render_apr_trend_chart()` helper
   - Add `calculate_position_returns()` helper
   - Add `render_risk_metrics()` helper

2. **dashboard/chart_generator.py** (NEW FILE)
   - Create Plotly chart generation functions
   - Implement APR trend line chart
   - Implement position sizing visualization
   - Cache chart HTML via `RateTracker.save_chart_cache()`

### Modal Layout

```
┌─────────────────────────────────────────────────┐
│  Strategy Details                          [X]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 USDC / DEEP / USDC                         │
│  Protocol A: Navi  |  Protocol B: AlphaFi      │
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │  Net APR: 11.85%                          │ │
│  │  APR 5d: 5.23%  |  APR 30d: 8.45%         │ │
│  │  Days to Breakeven: 10.8 days             │ │
│  │  Max Size: $1,469,751                     │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌─ APR Trend (30 days) ────────────────────┐ │
│  │                                           │ │
│  │  [Line chart showing APR over time]      │ │
│  │                                           │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌─ Position Calculator ────────────────────┐ │
│  │  Deployment Amount: [$____] USD          │ │
│  │                                           │ │
│  │  Position Sizes:                          │ │
│  │  • Lend A:   $XXX (XX%)                  │ │
│  │  • Borrow A: $XXX (XX%)                  │ │
│  │  • Lend B:   $XXX (XX%)                  │ │
│  │  • Borrow B: $XXX (XX%)                  │ │
│  │                                           │ │
│  │  Expected Returns:                        │ │
│  │  • Daily:   $X.XX                         │ │
│  │  • Monthly: $XX.XX                        │ │
│  │  • Yearly:  $XXX.XX                       │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  ┌─ Risk Metrics ───────────────────────────┐ │
│  │  Liquidation Distance: 20%                │ │
│  │  Health Factor: [████████░░] Good         │ │
│  └───────────────────────────────────────────┘ │
│                                                 │
│  [Deploy Position]  [Export]  [Close]          │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Implementation Steps

### Step 1: Create Chart Generator Module

**File**: [dashboard/chart_generator.py](dashboard/chart_generator.py) (NEW)

**Purpose**: Centralized chart generation and caching logic

**Functions to implement**:

```python
def generate_apr_trend_chart(
    strategy: Dict,
    timestamp_seconds: int,
    tracker: RateTracker
) -> str:
    """
    Generate APR trend line chart for strategy.

    Args:
        strategy: Strategy dict with tokens, protocols, etc.
        timestamp_seconds: Current timestamp (Unix seconds)
        tracker: RateTracker instance for cache access

    Returns:
        HTML string of rendered Plotly chart

    Logic:
        1. Compute strategy hash using RateTracker.compute_strategy_hash()
        2. Check chart_cache table for cached HTML
        3. If cache HIT: return cached HTML
        4. If cache MISS:
           a. Query historical APR data (30 days back)
           b. Generate Plotly line chart
           c. Render to HTML string
           d. Save to chart_cache via tracker.save_chart_cache()
           e. Return HTML string
    """
    pass

def generate_position_sizing_chart(
    strategy: Dict,
    deployment_usd: float
) -> str:
    """
    Generate position sizing visualization (pie chart or bar chart).

    Shows breakdown of:
    - Lend A position
    - Borrow A position
    - Lend B position
    - Borrow B position

    Args:
        strategy: Strategy dict with L_A, B_A, L_B, B_B multipliers
        deployment_usd: USD amount to deploy

    Returns:
        HTML string of rendered Plotly chart
    """
    pass
```

**Design Decisions**:
- Use Plotly for interactive charts (hover tooltips, zoom, pan)
- Cache at strategy+timestamp granularity
- Store as HTML strings (ready to render with `st.components.html()`)
- Include cache hit/miss logging for debugging

---

### Step 2: Implement Position Calculator Helper

**File**: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)

**Function**: `calculate_position_returns(strategy: Dict, deployment_usd: float) -> Dict`

**Purpose**: Calculate expected returns and position sizes

**Implementation**:
```python
def calculate_position_returns(strategy: Dict, deployment_usd: float) -> Dict:
    """
    Calculate position sizes and expected returns.

    Args:
        strategy: Strategy dict with multipliers (L_A, B_A, L_B, B_B) and net_apr
        deployment_usd: USD amount to deploy

    Returns:
        Dict with:
        - lend_a_usd: Lend A position size (USD)
        - borrow_a_usd: Borrow A position size (USD)
        - lend_b_usd: Lend B position size (USD)
        - borrow_b_usd: Borrow B position size (USD)
        - lend_a_pct: Percentage of deployment
        - borrow_a_pct: Percentage of deployment
        - lend_b_pct: Percentage of deployment
        - borrow_b_pct: Percentage of deployment
        - daily_return_usd: Expected daily return (USD)
        - monthly_return_usd: Expected monthly return (USD)
        - yearly_return_usd: Expected yearly return (USD)
        - total_fees_usd: Total upfront fees
        - days_to_breakeven: Days to recover fees

    Logic:
        1. Position sizes = multiplier * deployment_usd
        2. Daily return = deployment_usd * (net_apr / 365)
        3. Monthly return = daily_return * 30
        4. Yearly return = deployment_usd * net_apr
        5. Fees calculated from borrow fees (from strategy dict)
        6. Breakeven = total_fees / daily_return
    """
    net_apr = strategy['net_apr']  # Decimal (0.1185 = 11.85%)

    # Position sizes
    lend_a_usd = strategy['L_A'] * deployment_usd
    borrow_a_usd = strategy['B_A'] * deployment_usd
    lend_b_usd = strategy['L_B'] * deployment_usd
    borrow_b_usd = strategy['B_B'] * deployment_usd

    # Percentages
    lend_a_pct = strategy['L_A'] * 100
    borrow_a_pct = strategy['B_A'] * 100
    lend_b_pct = strategy['L_B'] * 100
    borrow_b_pct = strategy['B_B'] * 100

    # Returns
    yearly_return_usd = deployment_usd * net_apr
    daily_return_usd = yearly_return_usd / 365
    monthly_return_usd = daily_return_usd * 30

    # Fees and breakeven
    total_fees_usd = strategy.get('total_fees_usd', 0)  # From strategy calculation
    days_to_breakeven = strategy.get('days_to_breakeven', 0)

    return {
        'lend_a_usd': lend_a_usd,
        'borrow_a_usd': borrow_a_usd,
        'lend_b_usd': lend_b_usd,
        'borrow_b_usd': borrow_b_usd,
        'lend_a_pct': lend_a_pct,
        'borrow_a_pct': borrow_a_pct,
        'lend_b_pct': lend_b_pct,
        'borrow_b_pct': borrow_b_pct,
        'daily_return_usd': daily_return_usd,
        'monthly_return_usd': monthly_return_usd,
        'yearly_return_usd': yearly_return_usd,
        'total_fees_usd': total_fees_usd,
        'days_to_breakeven': days_to_breakeven
    }
```

---

### Step 3: Replace Placeholder Modal

**File**: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)

**Function**: Replace `show_placeholder_modal()` with full implementation

**Implementation**:
```python
@st.dialog("Strategy Details", width="large")
def show_strategy_modal(strategy: Dict, timestamp_seconds: int):
    """
    Full strategy details modal with charts, calculator, and actions.

    Args:
        strategy: Strategy dict from all_results DataFrame
        timestamp_seconds: Current timestamp for chart generation
    """
    import streamlit as st
    from dashboard.chart_generator import generate_apr_trend_chart
    from data.rate_tracker import RateTracker

    # Header section
    st.markdown(f"## 📊 {strategy['token1']} / {strategy['token2']} / {strategy['token3']}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Protocol A:** {strategy['protocol_A']}")
    with col2:
        st.markdown(f"**Protocol B:** {strategy['protocol_B']}")

    st.divider()

    # Metrics section
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

    with metric_col1:
        st.metric(
            label="Net APR",
            value=f"{strategy['net_apr'] * 100:.2f}%",
            help="Current instantaneous APR after all fees"
        )

    with metric_col2:
        st.metric(
            label="APR 5d",
            value=f"{strategy.get('apr5', 0) * 100:.2f}%",
            help="Annualized return if you exit after 5 days"
        )

    with metric_col3:
        st.metric(
            label="APR 30d",
            value=f"{strategy.get('apr30', 0) * 100:.2f}%",
            help="Annualized return if you exit after 30 days"
        )

    with metric_col4:
        st.metric(
            label="Days to Breakeven",
            value=f"{strategy.get('days_to_breakeven', 0):.1f}",
            help="Days until upfront fees are recovered"
        )

    st.divider()

    # APR Trend Chart
    st.markdown("### 📈 APR Trend (30 days)")

    tracker = RateTracker()
    chart_html = generate_apr_trend_chart(strategy, timestamp_seconds, tracker)

    if chart_html:
        st.components.v1.html(chart_html, height=400)
    else:
        st.info("No historical data available for APR trend chart")

    st.divider()

    # Position Calculator
    st.markdown("### 💰 Position Calculator")

    deployment_usd = st.number_input(
        "Deployment Amount (USD)",
        min_value=100.0,
        max_value=float(strategy.get('max_size', 1000000)),
        value=min(10000.0, float(strategy.get('max_size', 10000))),
        step=100.0,
        help="USD amount to deploy in this strategy"
    )

    position_calc = calculate_position_returns(strategy, deployment_usd)

    # Position breakdown
    st.markdown("**Position Sizes:**")
    pos_col1, pos_col2 = st.columns(2)

    with pos_col1:
        st.markdown(f"• **Lend A**: ${position_calc['lend_a_usd']:,.2f} ({position_calc['lend_a_pct']:.1f}%)")
        st.markdown(f"• **Borrow A**: ${position_calc['borrow_a_usd']:,.2f} ({position_calc['borrow_a_pct']:.1f}%)")

    with pos_col2:
        st.markdown(f"• **Lend B**: ${position_calc['lend_b_usd']:,.2f} ({position_calc['lend_b_pct']:.1f}%)")
        st.markdown(f"• **Borrow B**: ${position_calc['borrow_b_usd']:,.2f} ({position_calc['borrow_b_pct']:.1f}%)")

    # Expected returns
    st.markdown("**Expected Returns:**")
    ret_col1, ret_col2, ret_col3 = st.columns(3)

    with ret_col1:
        st.metric("Daily", f"${position_calc['daily_return_usd']:.2f}")
    with ret_col2:
        st.metric("Monthly", f"${position_calc['monthly_return_usd']:.2f}")
    with ret_col3:
        st.metric("Yearly", f"${position_calc['yearly_return_usd']:.2f}")

    st.divider()

    # Risk Metrics
    st.markdown("### ⚠️ Risk Metrics")

    liquidation_distance = strategy.get('liquidation_distance', 0.20)
    st.markdown(f"**Liquidation Distance**: {liquidation_distance * 100:.0f}%")

    # Health factor visualization
    health_pct = min(100, liquidation_distance * 500)  # Scale for visual
    st.progress(health_pct / 100, text=f"Health Factor: {'Good' if health_pct > 70 else 'Moderate' if health_pct > 50 else 'Risky'}")

    if liquidation_distance < 0.10:
        st.warning("⚠️ Low liquidation distance - higher liquidation risk")

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        if st.button("🚀 Deploy Position", type="primary", use_container_width=True):
            st.session_state.deploy_strategy = strategy
            st.session_state.deploy_amount = deployment_usd
            st.rerun()

    with col2:
        if st.button("📥 Export", use_container_width=True):
            import json
            st.download_button(
                label="Download JSON",
                data=json.dumps(strategy, indent=2),
                file_name=f"strategy_{strategy['token1']}_{strategy['token2']}_{strategy['token3']}.json",
                mime="application/json"
            )

    with col3:
        if st.button("❌ Close", use_container_width=True):
            st.rerun()
```

---

### Step 4: Update Table Row Click Handler

**File**: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)

**Location**: In `render_dashboard()` tab1 section

**Change**:
```python
# OLD (placeholder modal):
if selected_strategy:
    show_placeholder_modal(selected_strategy)

# NEW (full modal):
if selected_strategy:
    show_strategy_modal(selected_strategy, timestamp_seconds)
```

---

### Step 5: Implement Chart Generation Logic

**File**: [dashboard/chart_generator.py](dashboard/chart_generator.py)

**Detailed Implementation for APR Trend Chart**:

```python
import plotly.graph_objects as go
from typing import Dict, Optional
from data.rate_tracker import RateTracker
import pandas as pd

def generate_apr_trend_chart(
    strategy: Dict,
    timestamp_seconds: int,
    tracker: RateTracker
) -> Optional[str]:
    """
    Generate APR trend line chart with caching.
    """
    import time
    start_time = time.time()

    # Compute strategy hash for cache lookup
    strategy_hash = tracker.compute_strategy_hash(strategy)

    # Check cache
    cached_html = tracker.load_chart_cache(strategy_hash, timestamp_seconds)
    if cached_html:
        elapsed = (time.time() - start_time) * 1000
        print(f"[{elapsed:.1f}ms] [CHART] Cache HIT: Loaded chart for {strategy_hash}")
        return cached_html

    print(f"[CHART] Cache MISS: Generating chart for {strategy_hash}")

    # Fetch historical APR data (30 days)
    historical_data = fetch_historical_apr(
        token1_contract=strategy['token1_contract'],
        token2_contract=strategy['token2_contract'],
        token3_contract=strategy['token3_contract'],
        protocol_a=strategy['protocol_A'],
        protocol_b=strategy['protocol_B'],
        end_timestamp=timestamp_seconds,
        days_back=30,
        tracker=tracker
    )

    if historical_data is None or historical_data.empty:
        return None

    # Create Plotly line chart
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=historical_data['date'],
        y=historical_data['net_apr'] * 100,  # Convert to percentage
        mode='lines+markers',
        name='Net APR',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4),
        hovertemplate='%{x}<br>APR: %{y:.2f}%<extra></extra>'
    ))

    # Highlight current APR
    current_apr = strategy['net_apr'] * 100
    fig.add_hline(
        y=current_apr,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Current: {current_apr:.2f}%",
        annotation_position="right"
    )

    # Layout
    fig.update_layout(
        title="APR Trend (Last 30 Days)",
        xaxis_title="Date",
        yaxis_title="Net APR (%)",
        hovermode='x unified',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50),
        template='plotly_white'
    )

    # Render to HTML
    chart_html = fig.to_html(include_plotlyjs='cdn', div_id=f"chart_{strategy_hash}")

    # Save to cache
    tracker.save_chart_cache(strategy_hash, timestamp_seconds, chart_html)

    elapsed = (time.time() - start_time) * 1000
    print(f"[{elapsed:.1f}ms] [CHART] Generated and cached chart for {strategy_hash}")

    return chart_html


def fetch_historical_apr(
    token1_contract: str,
    token2_contract: str,
    token3_contract: str,
    protocol_a: str,
    protocol_b: str,
    end_timestamp: int,
    days_back: int,
    tracker: RateTracker
) -> Optional[pd.DataFrame]:
    """
    Fetch historical APR data for strategy from database.

    Returns DataFrame with columns: [date, net_apr]
    """
    # Query analysis_cache for historical data
    # This requires analysis_cache to have been populated by refresh_pipeline
    # over the past 30 days

    # For now, return None (stub)
    # Full implementation would query analysis_cache and filter by strategy
    return None
```

---

## Testing Plan

### Test 1: Modal Display

**Actions**:
1. Run dashboard: `streamlit run dashboard/streamlit_app.py`
2. Click checkbox on any strategy row
3. Verify modal opens

**Expected**:
- ✅ Modal displays with "Strategy Details" title
- ✅ Header shows token triple and protocols
- ✅ Metrics section shows Net APR, APR 5d/30d, Days to Breakeven
- ✅ All values formatted correctly (percentages, decimals)

### Test 2: APR Trend Chart

**Actions**:
1. Open modal for strategy
2. Scroll to "APR Trend" section
3. Verify chart displays or shows "No historical data" message

**Expected**:
- ✅ Chart loads (or shows placeholder if no data)
- ✅ Chart is interactive (hover tooltips work)
- ✅ Current APR highlighted with red dashed line
- ✅ Chart cached (second open is instant)

### Test 3: Position Calculator

**Actions**:
1. Open modal
2. Scroll to "Position Calculator" section
3. Change deployment amount
4. Verify calculations update

**Expected**:
- ✅ Position sizes calculate correctly
- ✅ Percentages sum to ~100% (accounting for leverage)
- ✅ Expected returns display (daily, monthly, yearly)
- ✅ Values update in real-time when input changes

### Test 4: Risk Metrics

**Actions**:
1. Open modal
2. Scroll to "Risk Metrics" section
3. Verify liquidation distance displays
4. Check health factor visualization

**Expected**:
- ✅ Liquidation distance shows as percentage
- ✅ Health factor progress bar renders
- ✅ Warning appears if liquidation distance < 10%

### Test 5: Action Buttons

**Actions**:
1. Click "Deploy Position" button
2. Verify deployment flow initiates
3. Click "Export" button
4. Verify JSON downloads
5. Click "Close" button
6. Verify modal closes

**Expected**:
- ✅ Deploy button sets session state variables
- ✅ Export downloads valid JSON file
- ✅ Close button dismisses modal

### Test 6: Performance

**Metrics to measure**:
- Modal open time: <500ms
- Chart load time (cache HIT): <100ms
- Chart generation (cache MISS): <3000ms
- Calculator updates: <50ms

**How to measure**:
- Check console debug logs
- Use browser DevTools Performance tab
- Verify debug print statements show timing

---

## Performance Targets

- Modal open (cache HIT): <500ms
- Modal open (cache MISS): <3000ms
- Position calculator updates: <50ms
- Chart render (cached): <100ms
- Chart generation (first time): <3000ms
- No memory leaks (test with 10+ modal opens)

---

## Success Criteria

- ✅ Placeholder modal replaced with full implementation
- ✅ All modal sections render correctly (overview, chart, calculator, risks, actions)
- ✅ APR trend chart displays with caching
- ✅ Position calculator works with real-time updates
- ✅ Risk metrics display correctly
- ✅ Action buttons functional (Deploy, Export, Close)
- ✅ Performance targets met
- ✅ No breaking changes to existing functionality
- ✅ Comprehensive error handling (missing data, cache failures)

---

## Rollback Plan

If issues arise:

1. **Revert to placeholder modal**:
```bash
git diff dashboard/dashboard_renderer.py  # Review changes
git checkout dashboard/dashboard_renderer.py  # Revert if needed
```

2. **Remove chart_generator.py**:
```bash
rm dashboard/chart_generator.py
```

3. **Verify system works**:
```bash
streamlit run dashboard/streamlit_app.py
```

4. **Check for stale imports**:
- Search for `from dashboard.chart_generator import` references
- Remove if found

---

## Edge Cases to Handle

### Edge Case 1: No Historical Data
- **Scenario**: Strategy is new, no APR history available
- **Solution**: Show "No historical data available" message instead of chart
- **Implementation**: Check if `fetch_historical_apr()` returns None/empty

### Edge Case 2: Cache Miss on Slow Network
- **Scenario**: Chart generation takes >3 seconds
- **Solution**: Show loading spinner while generating
- **Implementation**: Use `st.spinner("Generating chart...")` context manager

### Edge Case 3: Invalid Deployment Amount
- **Scenario**: User enters amount > max_size
- **Solution**: Clamp input to valid range using `max_value` parameter
- **Implementation**: Already handled in `st.number_input()` configuration

### Edge Case 4: Missing Strategy Fields
- **Scenario**: Strategy dict missing expected keys (apr5, apr30, etc.)
- **Solution**: Use `.get()` with default values throughout
- **Implementation**: `strategy.get('apr5', 0)` pattern everywhere

### Edge Case 5: Chart Rendering Failure
- **Scenario**: Plotly fails to generate chart
- **Solution**: Catch exception, log error, return None
- **Implementation**: Wrap chart generation in try/except block

---

## Design Principles Compliance

✅ **Timestamp as "Current Time"**: Modal uses `timestamp_seconds` from context
✅ **Unix Seconds**: All timestamps passed as integers
✅ **Rate Representation**: Rates as decimals, convert to % only for display
✅ **Token Identity**: Use contract addresses in chart_cache hash
✅ **No sys.path Manipulation**: No import hacks in new code
✅ **Event Sourcing**: Charts cached, never mutate existing cache
✅ **Streamlit Parameters**: Use `width="large"` for modal, not deprecated params

---

## Next Steps After Phase 3

Once Phase 3 is complete and tested:

1. **Phase 4**: Background processing for chart generation
   - Pre-generate charts during refresh_pipeline
   - Populate chart_cache proactively
   - Reduce cache MISS scenarios

2. **Future Enhancements**:
   - Multi-strategy comparison modal
   - Export to PDF report
   - Alert notifications for strategy changes
   - Historical performance tracking
