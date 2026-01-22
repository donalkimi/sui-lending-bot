# Dashboard Refactor Plan - Hybrid with Background Processing

## Overview

Refactor the Streamlit dashboard to load instantly with a sortable data table and modal dialogs, while generating charts and additional analysis variants in the background.

**Key Improvements:**
- ✅ Dashboard loads in <1 second (from cached analysis)
- ✅ Sortable table by Net APR, APR 5d, APR 30d, Liquidity, Max Size
- ✅ Modal popups for strategy details (not new tabs)
- ✅ Charts/variants generate in background (non-blocking)
- ✅ Persistent cache survives page reloads
- ✅ Keeps position deployment functionality

**Implementation Timeline:** 3-4 days

---

## Architecture Flow

```
User Opens Dashboard
  ↓
Check DB cache for (timestamp, liquidation_distance)
  ↓
  ├─ Cache HIT → Load from DB (<1s)
  │                ↓
  │         Display sortable table
  │                ↓
  │         Start background processor
  │                ↓
  │         Generate charts for top 20 (5-10 min)
  │         Compute additional liq_dist variants (3-5 min each)
  │
  └─ Cache MISS → Run analysis with default settings (5-15s)
                        ↓
                  Insert results into DB cache
                        ↓
                  Display sortable table
                        ↓
                  Start background processor
                        ↓
                  Generate charts for top 20 (5-10 min)
                  Compute additional liq_dist variants (3-5 min each)
```

**Key Point:** Analysis always runs ONCE initially (either from cache or fresh computation). Background processing ONLY generates charts and additional liq_distance variants, NOT the initial analysis.

---

## What is a Modal?

A **modal** is a popup dialog overlay that appears on top of the current page, like a dialog box.

In Streamlit, you use the `@st.dialog` decorator to create functions that render content in a modal window. When a user clicks a table row, a modal opens showing strategy details. You close it by clicking outside or pressing X, and you're back to the table.

**No new tabs, no navigation** - everything stays on the same page.

Streamlit documentation: [st.dialog](https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog)

---

## APR Metrics Explained

The dashboard displays three APR metrics:

1. **Net APR** - Current instantaneous APR after all fees
2. **APR 5d** - Annualized return if you pay all fees upfront but exit after 5 days (custom metric)
3. **APR 30d** - 30-day historical average APR

These metrics help evaluate strategies across different time horizons.

---

## Design Principles Compliance

This plan adheres to all core principles from [DESIGN_NOTES.md](c:/Dev/sui-lending-bot/DESIGN_NOTES.md):

### 1. Timestamp as "Current Time"
- ✅ Selected timestamp defines "now" for all queries
- ✅ Historical data uses `WHERE timestamp <= strategy_timestamp`
- ✅ No `datetime.now()` defaults (explicit timestamps everywhere)

### 2. Unix Seconds (Integer Timestamps)
- ✅ All internal processing uses `to_seconds()` → int
- ✅ Conversion only at boundaries (DB/UI)
- ✅ Display uses `to_datetime_str()` → "YYYY-MM-DD HH:MM:SS"

### 3. Rate Representation (Decimals)
- ✅ All rates stored as decimals (0.05 = 5%)
- ✅ Conversion to percentages only at display layer
- ✅ Format: `f"{rate * 100:.2f}%"`

### 4. Token Identity (Contract Addresses)
- ✅ All logic uses contract addresses (via `normalize_coin_type()`)
- ✅ Symbols only for display in UI
- ✅ DataFrame filtering/matching by contract, not symbol

### 5. Streamlit Chart Width
- ✅ Use `width="stretch"` instead of deprecated `use_container_width=True`

### 6. No sys.path Manipulation
- ✅ No new `sys.path.append()` calls

---

## Implementation Plan

### Phase 1: Database Cache Foundation (Day 1)

**Goal:** Add persistent cache tables to database for analysis results and chart data.

#### 1.1 Create Cache Tables

Add to [data/rate_tracker.py](c:/Dev/sui-lending-bot/data/rate_tracker.py):

```python
# New tables:
# 1. analysis_cache
CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_seconds INTEGER NOT NULL,
    liquidation_distance REAL NOT NULL,
    protocol_A TEXT,
    protocol_B TEXT,
    results_json TEXT NOT NULL,  -- JSON serialized all_results
    created_at INTEGER NOT NULL,
    UNIQUE(timestamp_seconds, liquidation_distance)
)

# 2. chart_cache
CREATE TABLE IF NOT EXISTS chart_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_hash TEXT NOT NULL,
    timestamp_seconds INTEGER NOT NULL,
    chart_html TEXT NOT NULL,  -- Plotly HTML
    created_at INTEGER NOT NULL,
    UNIQUE(strategy_hash, timestamp_seconds)
)

# Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_analysis_cache_timestamp
    ON analysis_cache(timestamp_seconds, liquidation_distance)

CREATE INDEX IF NOT EXISTS idx_chart_cache_strategy
    ON chart_cache(strategy_hash, timestamp_seconds)
```

#### 1.2 Add Cache Methods

Add to `RateTracker` class in [data/rate_tracker.py](c:/Dev/sui-lending-bot/data/rate_tracker.py):

```python
def save_analysis_cache(
    self,
    timestamp_seconds: int,
    liquidation_distance: float,
    protocol_A: pd.DataFrame,
    protocol_B: pd.DataFrame,
    all_results: List[Dict]
) -> None:
    """
    Save analysis results to cache.

    Args:
        timestamp_seconds: Unix timestamp (int)
        liquidation_distance: Decimal (0.10 = 10%)
        protocol_A, protocol_B: DataFrames with protocol data
        all_results: List of strategy dictionaries
    """
    import json

    results_json = json.dumps({
        'protocol_A': protocol_A.to_dict('records'),
        'protocol_B': protocol_B.to_dict('records'),
        'all_results': all_results
    })

    created_at = int(time.time())

    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO analysis_cache
            (timestamp_seconds, liquidation_distance, protocol_A, protocol_B, results_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            timestamp_seconds,
            liquidation_distance,
            protocol_A.name if hasattr(protocol_A, 'name') else None,
            protocol_B.name if hasattr(protocol_B, 'name') else None,
            results_json,
            created_at
        ))

def load_analysis_cache(
    self,
    timestamp_seconds: int,
    liquidation_distance: float
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, List[Dict]]]:
    """
    Load analysis results from cache.

    Returns:
        Tuple of (protocol_A, protocol_B, all_results) or None if not cached
    """
    import json

    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute("""
            SELECT results_json FROM analysis_cache
            WHERE timestamp_seconds = ? AND liquidation_distance = ?
        """, (timestamp_seconds, liquidation_distance))

        row = cursor.fetchone()
        if not row:
            return None

        data = json.loads(row[0])
        protocol_A = pd.DataFrame(data['protocol_A'])
        protocol_B = pd.DataFrame(data['protocol_B'])
        all_results = data['all_results']

        return (protocol_A, protocol_B, all_results)

def save_chart_cache(
    self,
    strategy_hash: str,
    timestamp_seconds: int,
    chart_html: str
) -> None:
    """Save rendered chart to cache."""
    created_at = int(time.time())

    with sqlite3.connect(self.db_path) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO chart_cache
            (strategy_hash, timestamp_seconds, chart_html, created_at)
            VALUES (?, ?, ?, ?)
        """, (strategy_hash, timestamp_seconds, chart_html, created_at))

def load_chart_cache(
    self,
    strategy_hash: str,
    timestamp_seconds: int
) -> Optional[str]:
    """Load rendered chart from cache. Returns HTML string or None."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute("""
            SELECT chart_html FROM chart_cache
            WHERE strategy_hash = ? AND timestamp_seconds = ?
        """, (strategy_hash, timestamp_seconds))

        row = cursor.fetchone()
        return row[0] if row else None

def compute_strategy_hash(strategy: Dict) -> str:
    """
    Compute unique hash for strategy based on tokens and protocols.
    Uses contract addresses (not symbols) for uniqueness.
    """
    import hashlib

    # Use contract addresses for hashing
    key = f"{strategy['token1_contract']}_{strategy['token2_contract']}_{strategy['token3_contract']}"
    key += f"_{strategy['protocol_A']}_{strategy['protocol_B']}"
    key += f"_{strategy.get('liquidation_distance', 0.10)}"

    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

#### 1.3 Modify refresh_pipeline to Cache Results

Update [data/refresh_pipeline.py](c:/Dev/sui-lending-bot/data/refresh_pipeline.py):

```python
def refresh_pipeline(save_snapshots: bool = True, send_slack_notifications: bool = True) -> RefreshResult:
    """Existing function - add cache saving at the end"""

    # ... existing code ...

    # After analysis completes:
    protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

    # NEW: Save analysis to cache
    if save_snapshots:
        tracker.save_analysis_cache(
            timestamp_seconds=to_seconds(timestamp),
            liquidation_distance=0.10,  # Default liquidation distance
            protocol_A=protocol_A,
            protocol_B=protocol_B,
            all_results=all_results
        )

    # ... rest of existing code ...

    return RefreshResult(
        timestamp=to_seconds(timestamp),
        protocol_A=protocol_A,
        protocol_B=protocol_B,
        all_results=all_results,
        lend_rates=lend_rates,
        # ... etc
    )
```

#### 1.4 Testing (Day 1 End)

```bash
# Test cache tables created
python -c "from data.rate_tracker import RateTracker; rt = RateTracker(); print('Cache tables created')"

# Run refresh_pipeline and verify cache populated
python -c "from data.refresh_pipeline import refresh_pipeline; refresh_pipeline()"

# Verify cache in database
sqlite3 data/rates.db "SELECT COUNT(*) FROM analysis_cache"
```

---

### Phase 2: Replace Expanders with Sortable Table (Day 2)

**Goal:** Remove clunky expanders, add modern sortable data table with column sorting.

#### 2.1 Remove Expander Code

In [dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py):

- Remove `render_all_strategies_tab()` function (lines ~513-639)
- This function uses expanders which we're replacing

#### 2.2 Create Sortable Table Function

Add new function to [dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py):

```python
def display_strategies_table(
    all_results: List[Dict],
    mode: str = 'unified'
) -> Optional[Dict]:
    """
    Display strategies as sortable data table.

    Returns:
        Selected strategy dict or None
    """
    import pandas as pd
    import streamlit as st

    if not all_results:
        st.info("No strategies found matching filters")
        return None

    # Prepare data for table
    table_data = []
    for idx, strategy in enumerate(all_results):
        # Get token symbols for display (logic uses contracts)
        token_pair = f"{strategy['token1']}/{strategy['token2']}/{strategy['token3']}"

        table_data.append({
            '_idx': idx,  # Hidden index for selection
            'Token Pair': token_pair,
            'Protocol A': strategy['protocol_A'],
            'Protocol B': strategy['protocol_B'],
            'Net APR': strategy['net_apr'] * 100,  # Convert decimal to percentage
            'APR 5d': strategy.get('apr_5d', 0) * 100,  # APR if exit after 5 days
            'APR 30d': strategy.get('apr_30d', 0) * 100,  # 30-day historical average
            'Liquidity': strategy.get('liquidity', 0),
            'Max Size': strategy.get('max_size', 0),
        })

    df = pd.DataFrame(table_data)

    # Display table with sortable columns
    event = st.dataframe(
        df.drop(columns=['_idx']),  # Hide index column
        width="stretch",  # Use new parameter (not deprecated use_container_width)
        hide_index=True,
        column_config={
            "Net APR": st.column_config.NumberColumn(
                "Net APR",
                format="%.2f%%",
                help="Current instantaneous APR after all fees"
            ),
            "APR 5d": st.column_config.NumberColumn(
                "APR 5d",
                format="%.2f%%",
                help="Annualized return if you pay all fees upfront but exit after 5 days"
            ),
            "APR 30d": st.column_config.NumberColumn(
                "APR 30d",
                format="%.2f%%",
                help="30-day historical average APR"
            ),
            "Liquidity": st.column_config.NumberColumn(
                "Liquidity",
                format="$%,.0f"
            ),
            "Max Size": st.column_config.NumberColumn(
                "Max Size",
                format="$%,.0f"
            ),
        },
        on_select="rerun",  # Trigger rerun when row selected
        selection_mode="single-row"
    )

    # Check if user selected a row
    if event.selection and event.selection.rows:
        selected_idx = df.iloc[event.selection.rows[0]]['_idx']
        return all_results[selected_idx]

    return None
```

#### 2.3 Update Main Render Function

Modify `render_dashboard()` in [dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py):

```python
def render_dashboard(loader, mode='unified'):
    """Main dashboard renderer - updated to use table instead of expanders"""

    # ... existing code for loading data ...

    # === MAIN TAB: STRATEGIES TABLE ===
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Strategies", "📈 Rate Tables", "💼 Positions", "⚠️ Zero Liquidity"])

    with tab1:
        st.markdown("### Top Lending Strategies")
        st.markdown("Click column headers to sort. Click a row to view details.")

        # Display sortable table
        selected_strategy = display_strategies_table(filtered_results, mode=mode)

        # If user clicked a row, open modal with details
        if selected_strategy:
            show_strategy_modal(selected_strategy, timestamp_seconds)

    # ... rest of tabs ...
```

#### 2.4 Testing (Day 2 End)

```bash
# Run dashboard
streamlit run dashboard/streamlit_app.py

# Test:
# 1. Verify table displays with all columns
# 2. Click "Net APR" header → verify sorts descending/ascending
# 3. Click "Liquidity" header → verify sorts by liquidity
# 4. Click "APR 5d" header → verify sorts correctly
# 5. Verify APR values display as percentages (e.g., "5.23%")
# 6. Verify liquidity/max size display with $ formatting
```

---

### Phase 3: Add Modal Dialog for Strategy Details (Day 2-3)

**Goal:** When user clicks table row, open modal popup with strategy details, chart, and deploy button.

#### 3.1 Create Modal Function

Add to [dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py):

```python
@st.dialog("Strategy Details", width="large")
def show_strategy_modal(strategy: Dict, timestamp_seconds: int):
    """
    Display strategy details in modal dialog.

    Args:
        strategy: Strategy dictionary with all details
        timestamp_seconds: Unix timestamp (int) for cache lookups
    """
    import streamlit as st
    from data.rate_tracker import RateTracker

    # === STRATEGY OVERVIEW ===
    st.markdown(f"### {strategy['token1']}/{strategy['token2']}/{strategy['token3']}")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Protocol A", strategy['protocol_A'])
        st.metric("Protocol B", strategy['protocol_B'])
    with col2:
        st.metric("Net APR", f"{strategy['net_apr'] * 100:.2f}%")
        st.metric("Max Position Size", f"${strategy.get('max_size', 0):,.0f}")

    # === POSITION BREAKDOWN ===
    st.markdown("#### Position Structure")

    # Create breakdown table
    breakdown_data = [
        {
            "Action": "Lend on A",
            "Token": strategy['token1'],
            "Multiplier": f"{strategy['L_A']:.4f}",
            "USD Amount": f"${strategy['L_A'] * 1000:,.2f}",  # Example with $1000
        },
        {
            "Action": "Borrow on A",
            "Token": strategy['token2'],
            "Multiplier": f"{strategy['B_A']:.4f}",
            "USD Amount": f"${strategy['B_A'] * 1000:,.2f}",
        },
        {
            "Action": "Lend on B",
            "Token": strategy['token2'],
            "Multiplier": f"{strategy['L_B']:.4f}",
            "USD Amount": f"${strategy['L_B'] * 1000:,.2f}",
        },
        {
            "Action": "Borrow on B",
            "Token": strategy['token3'],
            "Multiplier": f"{strategy['B_B']:.4f}",
            "USD Amount": f"${strategy['B_B'] * 1000:,.2f}",
        },
    ]

    st.dataframe(
        pd.DataFrame(breakdown_data),
        width="stretch",
        hide_index=True
    )

    st.caption("💡 Multipliers are scaled by deployment_usd. Example shown with $1,000 deployment.")

    # === APR BREAKDOWN ===
    st.markdown("#### APR Details")

    apr_data = {
        "Metric": ["Current Net APR", "APR 5d", "APR 30d"],
        "Value": [
            f"{strategy['net_apr'] * 100:.2f}%",
            f"{strategy.get('apr_5d', 0) * 100:.2f}%",
            f"{strategy.get('apr_30d', 0) * 100:.2f}%",
        ],
        "Description": [
            "Instantaneous APR after all fees",
            "Annualized return if exit after 5 days (fees paid upfront)",
            "30-day historical average APR",
        ]
    }

    st.dataframe(
        pd.DataFrame(apr_data),
        width="stretch",
        hide_index=True
    )

    # === HISTORICAL CHART ===
    st.markdown("#### Historical Performance")

    # Check if chart is cached
    tracker = RateTracker()
    strategy_hash = tracker.compute_strategy_hash(strategy)
    chart_html = tracker.load_chart_cache(strategy_hash, timestamp_seconds)

    if chart_html:
        # Chart is cached - display immediately
        st.components.v1.html(chart_html, height=600, scrolling=True)
    else:
        # Chart not ready - show status
        st.info("📊 Chart is being generated in the background. Refresh in 30-60 seconds.")

        # Get background processor status if available
        if 'bg_processor' in st.session_state:
            status = st.session_state.bg_processor.get_status()
            st.caption(f"Charts ready: {status.get('charts_completed', 0)}/{status.get('charts_total', 0)}")

        # Refresh button
        if st.button("🔄 Refresh to Check", key=f"refresh_chart_{strategy_hash}"):
            st.rerun()

    # === DEPLOY BUTTON ===
    st.divider()

    if st.button("🚀 Deploy Position", type="primary", key=f"deploy_{strategy_hash}"):
        st.session_state.pending_deployment = strategy
        st.session_state.show_deploy_form = True
        st.rerun()
```

#### 3.2 Wire Up Table Selection

Already handled in Phase 2.3 - the `display_strategies_table()` function returns selected strategy, and `render_dashboard()` calls `show_strategy_modal()`.

#### 3.3 Testing (Day 3 Mid)

```bash
# Run dashboard
streamlit run dashboard/streamlit_app.py

# Test:
# 1. Click table row → verify modal opens
# 2. Verify strategy overview displays (protocols, APR, max size)
# 3. Verify position breakdown table shows 4 rows (L_A, B_A, L_B, B_B)
# 4. Verify APR breakdown shows 3 metrics (Net APR, APR 5d, APR 30d)
# 5. If chart not cached → verify "Generating..." message shown
# 6. Click deploy button → verify form appears (existing functionality)
# 7. Close modal (click outside or X) → verify back to table
```

---

### Phase 4: Background Processing Service (Day 3-4)

**Goal:** After dashboard loads, spawn background thread to generate charts and compute additional liq_distance variants.

#### 4.1 Create Background Processor

Create new file: [dashboard/background_processor.py](c:/Dev/sui-lending-bot/dashboard/background_processor.py)

```python
"""
Background processing service for chart generation and analysis variants.

Runs in separate thread to avoid blocking UI.
"""

import threading
import queue
import time
import hashlib
from typing import List, Dict, Optional
from data.rate_tracker import RateTracker
from analysis.rate_analyzer import RateAnalyzer
from dashboard.dashboard_utils import get_strategy_history, create_strategy_history_chart


class BackgroundProcessor:
    """
    Manages background tasks for chart generation and analysis variants.

    Tasks run in separate thread and save results to database cache.
    """

    def __init__(self, rate_tracker: RateTracker):
        self.rate_tracker = rate_tracker
        self.task_queue = queue.Queue()
        self.status = {
            'charts_completed': 0,
            'charts_total': 0,
            'liq_distances_completed': 0,
            'liq_distances_total': 0,
        }
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False

    def start(self):
        """Start background worker thread."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()

    def _worker(self):
        """Worker thread that processes tasks from queue."""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)

                if task['type'] == 'chart':
                    self._generate_chart(
                        task['strategy'],
                        task['timestamp_seconds']
                    )
                    self.status['charts_completed'] += 1

                elif task['type'] == 'analysis':
                    self._compute_analysis(
                        task['timestamp_seconds'],
                        task['liq_distance'],
                        task['data_loader']
                    )
                    self.status['liq_distances_completed'] += 1

                self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Background task failed: {e}")
                import traceback
                traceback.print_exc()
                continue

    def queue_chart_generation(
        self,
        strategies: List[Dict],
        timestamp_seconds: int
    ):
        """
        Queue chart generation tasks for multiple strategies.

        Args:
            strategies: List of strategy dicts
            timestamp_seconds: Unix timestamp (int)
        """
        self.status['charts_total'] = len(strategies)
        self.status['charts_completed'] = 0

        for strategy in strategies:
            self.task_queue.put({
                'type': 'chart',
                'strategy': strategy,
                'timestamp_seconds': timestamp_seconds
            })

    def queue_analysis(
        self,
        timestamp_seconds: int,
        liq_distances: List[float],
        data_loader
    ):
        """
        Queue analysis tasks for additional liquidation distances.

        Args:
            timestamp_seconds: Unix timestamp (int)
            liq_distances: List of liquidation distances as decimals (0.05 = 5%)
            data_loader: UnifiedDataLoader instance for loading snapshot data
        """
        self.status['liq_distances_total'] = len(liq_distances)
        self.status['liq_distances_completed'] = 0

        for liq_dist in liq_distances:
            self.task_queue.put({
                'type': 'analysis',
                'timestamp_seconds': timestamp_seconds,
                'liq_distance': liq_dist,
                'data_loader': data_loader
            })

    def _generate_chart(self, strategy: Dict, timestamp_seconds: int):
        """
        Generate historical chart for strategy and save to cache.

        Args:
            strategy: Strategy dict with tokens, protocols, multipliers
            timestamp_seconds: Unix timestamp (int) defining "now"
        """
        try:
            # Fetch historical data up to strategy timestamp
            history_df, L_A, B_A, L_B, B_B = get_strategy_history(
                strategy=strategy,
                strategy_timestamp=timestamp_seconds,  # Unix seconds
                rate_tracker=self.rate_tracker,
                lookback_days=30
            )

            # Generate Plotly chart as HTML
            chart_html = create_strategy_history_chart(
                history_df=history_df,
                strategy=strategy
            )

            # Save to cache
            strategy_hash = self.rate_tracker.compute_strategy_hash(strategy)
            self.rate_tracker.save_chart_cache(
                strategy_hash=strategy_hash,
                timestamp_seconds=timestamp_seconds,
                chart_html=chart_html
            )

            print(f"✅ Chart generated for {strategy['token1']}/{strategy['token2']}/{strategy['token3']}")

        except Exception as e:
            print(f"❌ Chart generation failed for {strategy.get('token1', '?')}: {e}")

    def _compute_analysis(
        self,
        timestamp_seconds: int,
        liq_distance: float,
        data_loader
    ):
        """
        Compute analysis for additional liquidation distance and save to cache.

        Args:
            timestamp_seconds: Unix timestamp (int)
            liq_distance: Liquidation distance as decimal (0.05 = 5%)
            data_loader: UnifiedDataLoader instance
        """
        try:
            # Load snapshot data at this timestamp
            data_tuple = data_loader.load_data()
            if not data_tuple:
                print(f"❌ Failed to load data for analysis at {timestamp_seconds}")
                return

            lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp = data_tuple

            # Run analysis with this liquidation distance
            analyzer = RateAnalyzer(
                lend_rates=lend_rates,
                borrow_rates=borrow_rates,
                collateral_ratios=collateral_ratios,
                prices=prices,
                lend_rewards=lend_rewards,
                borrow_rewards=borrow_rewards,
                available_borrow=available_borrow,
                borrow_fees=borrow_fees,
                liquidation_distance=liq_distance,  # Use custom liquidation distance
                force_usdc_start=False,
                force_token3_equals_token1=False,
                stablecoin_only=False
            )

            protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

            # Save to cache
            self.rate_tracker.save_analysis_cache(
                timestamp_seconds=timestamp_seconds,
                liquidation_distance=liq_distance,
                protocol_A=protocol_A,
                protocol_B=protocol_B,
                all_results=all_results
            )

            print(f"✅ Analysis computed for liq_distance={liq_distance * 100:.0f}% at {timestamp_seconds}")

        except Exception as e:
            print(f"❌ Analysis failed for liq_distance={liq_distance}: {e}")

    def get_status(self) -> Dict:
        """Get current processing status."""
        return self.status.copy()

    def stop(self):
        """Stop background processing."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
```

#### 4.2 Integrate Background Processor in Streamlit App

Modify [dashboard/streamlit_app.py](c:/Dev/sui-lending-bot/dashboard/streamlit_app.py):

```python
def main():
    """Main entry point with unified dashboard"""

    # ... existing code for page config, timestamp selection ...

    # === LOAD DATA FOR SELECTED TIMESTAMP ===
    try:
        loader = UnifiedDataLoader(st.session_state.selected_timestamp)
        data_tuple = loader.load_data()

        if data_tuple is None:
            st.error("❌ Failed to load data for selected timestamp")
            st.stop()

        # Unpack the 9-tuple
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp = data_tuple

        # Convert timestamp to seconds (Unix timestamp)
        timestamp_seconds = to_seconds(timestamp)

        # === RENDER DASHBOARD ===
        render_dashboard(loader, mode='unified')

        # === INITIALIZE BACKGROUND PROCESSOR (AFTER DASHBOARD RENDERS) ===
        # Only initialize once per session
        if 'bg_processor' not in st.session_state:
            from dashboard.background_processor import BackgroundProcessor
            from data.rate_tracker import RateTracker

            st.session_state.bg_processor = BackgroundProcessor(
                rate_tracker=RateTracker()
            )
            st.session_state.bg_processor.start()

        # === QUEUE BACKGROUND TASKS (ONLY ONCE PER TIMESTAMP) ===
        cache_key = f"bg_tasks_{timestamp_seconds}_{liquidation_distance}"

        if cache_key not in st.session_state:
            # Get liquidation distance from sidebar filters
            # (assumes render_sidebar_filters() stores in st.session_state)
            liquidation_distance = st.session_state.get('liquidation_distance', 0.10)

            # Get all_results from current analysis
            # (assumes render_dashboard() stores in st.session_state)
            all_results = st.session_state.get('all_results', [])

            if all_results:
                # Queue chart generation for top 20 strategies by Net APR
                top_strategies = sorted(
                    all_results,
                    key=lambda x: x['net_apr'],
                    reverse=True
                )[:20]

                st.session_state.bg_processor.queue_chart_generation(
                    strategies=top_strategies,
                    timestamp_seconds=timestamp_seconds
                )

                # Queue analysis for additional liquidation distances
                # Exclude current liq_distance (already computed)
                additional_liq_dists = [0.05, 0.15, 0.20, 0.25]
                additional_liq_dists = [
                    ld for ld in additional_liq_dists
                    if abs(ld - liquidation_distance) > 0.01  # Allow small floating point diff
                ]

                if additional_liq_dists:
                    st.session_state.bg_processor.queue_analysis(
                        timestamp_seconds=timestamp_seconds,
                        liq_distances=additional_liq_dists,
                        data_loader=loader
                    )

                # Mark tasks as queued for this timestamp
                st.session_state[cache_key] = True

        # === SHOW BACKGROUND STATUS IN SIDEBAR ===
        with st.sidebar:
            st.divider()
            st.markdown("### 🔄 Background Processing")

            status = st.session_state.bg_processor.get_status()

            if status['charts_total'] > 0:
                progress = status['charts_completed'] / status['charts_total']
                st.progress(progress, text=f"Charts: {status['charts_completed']}/{status['charts_total']}")

            if status['liq_distances_total'] > 0:
                st.caption(f"📈 Liq Distances: {status['liq_distances_completed']}/{status['liq_distances_total']} computed")

            # Refresh button to check for new cached data
            if st.button("🔄 Check for Updates", help="Check if background tasks completed"):
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error loading dashboard: {e}")
        st.exception(e)
        st.stop()
```

#### 4.3 Update Dashboard Renderer to Store all_results

Modify `render_dashboard()` in [dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py):

```python
def render_dashboard(loader, mode='unified'):
    """Main dashboard renderer"""

    # ... existing code for loading data ...

    # Get liquidation_distance and other filters from sidebar
    (liquidation_distance, deployment_usd, force_usdc_start,
     force_token3_equals_token1, stablecoin_only,
     min_apr, token_filter, protocol_filter) = render_sidebar_filters(display_results)

    # Store liquidation_distance in session state for background processor
    st.session_state['liquidation_distance'] = liquidation_distance

    # Check cache first
    cache_key = f"{timestamp_seconds}_{liquidation_distance}"

    if cache_key in st.session_state.analysis_cache:
        # Load from session cache
        protocol_A, protocol_B, all_results = st.session_state.analysis_cache[cache_key]
    else:
        # Check database cache
        tracker = RateTracker()
        cached = tracker.load_analysis_cache(timestamp_seconds, liquidation_distance)

        if cached:
            # Load from DB cache
            protocol_A, protocol_B, all_results = cached
            # Store in session cache for faster access
            st.session_state.analysis_cache[cache_key] = (protocol_A, protocol_B, all_results)
        else:
            # Cache miss - run analysis
            analyzer = RateAnalyzer(
                lend_rates=lend_rates,
                borrow_rates=borrow_rates,
                collateral_ratios=collateral_ratios,
                prices=prices,
                lend_rewards=lend_rewards,
                borrow_rewards=borrow_rewards,
                available_borrow=available_borrow,
                borrow_fees=borrow_fees,
                liquidation_distance=liquidation_distance,
                force_usdc_start=force_usdc_start,
                force_token3_equals_token1=force_token3_equals_token1,
                stablecoin_only=stablecoin_only
            )

            protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

            # Save to both caches
            st.session_state.analysis_cache[cache_key] = (protocol_A, protocol_B, all_results)
            tracker.save_analysis_cache(
                timestamp_seconds=timestamp_seconds,
                liquidation_distance=liquidation_distance,
                protocol_A=protocol_A,
                protocol_B=protocol_B,
                all_results=all_results
            )

    # Store all_results in session state for background processor access
    st.session_state['all_results'] = all_results

    # ... rest of dashboard rendering ...
```

#### 4.4 Testing (Day 4 End)

```bash
# Run dashboard
streamlit run dashboard/streamlit_app.py

# Test initial load:
# 1. Open dashboard → verify table appears in <1s (from cache)
# 2. Check sidebar → verify "Background Processing" section appears
# 3. Verify progress bar shows "Charts: 0/20"
# 4. Wait 30 seconds → click "Check for Updates"
# 5. Verify progress bar updates (e.g., "Charts: 3/20")

# Test chart generation:
# 1. Click table row → open modal
# 2. If chart not ready → verify "Generating..." message
# 3. Wait 60 seconds → click "Refresh to Check"
# 4. Verify chart appears once cached

# Test liq_distance variant:
# 1. Change liq_distance slider to 15%
# 2. If cached → verify table updates instantly
# 3. If not cached → verify spinner, then updates after 5-15s
# 4. Verify background processor queues this variant for future use

# Check database:
sqlite3 data/rates.db "SELECT COUNT(*) FROM chart_cache"
sqlite3 data/rates.db "SELECT COUNT(*) FROM analysis_cache"
```

---

## Files Summary

### Files Created (New)
- **[dashboard/background_processor.py](c:/Dev/sui-lending-bot/dashboard/background_processor.py)** (~250 lines)
  - Background task manager with threading
  - Handles chart generation and analysis variant computation

### Files Modified (Existing)
- **[data/rate_tracker.py](c:/Dev/sui-lending-bot/data/rate_tracker.py)** (+150 lines)
  - Add cache table schemas
  - Add save/load methods for analysis_cache and chart_cache
  - Add compute_strategy_hash() method

- **[data/refresh_pipeline.py](c:/Dev/sui-lending-bot/data/refresh_pipeline.py)** (+20 lines)
  - Save analysis results to DB cache after computation

- **[dashboard/dashboard_renderer.py](c:/Dev/sui-lending-bot/dashboard/dashboard_renderer.py)** (modify ~500 lines)
  - Remove render_all_strategies_tab() with expanders
  - Add display_strategies_table() with sortable columns
  - Add show_strategy_modal() with @st.dialog decorator
  - Update render_dashboard() to check DB cache first
  - Store all_results and liquidation_distance in session state

- **[dashboard/streamlit_app.py](c:/Dev/sui-lending-bot/dashboard/streamlit_app.py)** (+80 lines)
  - Initialize background processor
  - Queue background tasks after dashboard loads
  - Display background status in sidebar

- **[config/settings.py](c:/Dev/sui-lending-bot/config/settings.py)** (+10 lines)
  - Add background processing config (optional)

**Total Code Changes:** ~600 new lines, ~500 modified lines

---

## Performance Targets

### Load Times (Cached)
- ✅ Initial dashboard load: **<1 second**
- ✅ Table sort (click column): **<100ms** (client-side)
- ✅ Modal open: **<300ms**
- ✅ Chart display (if cached): **<500ms**
- ✅ Liq_distance change (if cached): **<500ms**

### Load Times (Uncached)
- Initial analysis run: **5-15 seconds** (one-time cost)
- Liq_distance change (not cached): **5-15 seconds** (queued to background)
- Chart generation (per strategy): **30-60 seconds** (background, non-blocking)

### Background Processing
- Chart generation (20 strategies): **10-20 minutes** (non-blocking)
- Additional liq_distance variants (3 variants): **15-45 seconds each** (non-blocking)

---

## User Experience Flow

### First Time Opening Dashboard (No Cache)

1. **User opens dashboard** (Time: 0:00)
   - Spinner: "Running analysis..."
   - Analysis runs with default settings (liq_dist = 10%)
   - Results saved to DB cache
   - **Dashboard appears** (Time: 0:10)

2. **User sees sortable table** (Time: 0:10)
   - Clicks "Net APR" header → table sorts instantly
   - Clicks "Liquidity" header → table sorts instantly
   - Background processor starts (silent, non-blocking)

3. **User clicks table row** (Time: 0:30)
   - Modal opens with strategy details
   - Chart section shows: "📊 Generating... 2/20 charts ready"
   - User can close modal and keep exploring

4. **User changes liq_distance to 15%** (Time: 1:00)
   - Not cached yet → spinner appears
   - Analysis runs (5-15 seconds)
   - Table updates with new results
   - Background: This variant queued for caching

5. **User clicks "Check for Updates"** (Time: 5:00)
   - Sidebar shows: "Charts: 12/20 ready"
   - User opens strategy modal → chart now displays!

6. **User returns later** (Time: Next Day)
   - Opens dashboard → loads from cache in <1s
   - All 20 charts cached → instant display
   - All liq_distance variants cached → instant switching

### Subsequent Loads (With Cache)

1. **User opens dashboard** → <1 second load
2. **User sorts table** → Instant (client-side)
3. **User opens modal** → Chart displays immediately (cached)
4. **User changes liq_distance** → Instant switch (cached variants)
5. **User deploys position** → Same as current flow (no change)

---

## Verification Testing

### Test 1: Initial Load (No Cache)
```bash
# Clear cache
sqlite3 data/rates.db "DELETE FROM analysis_cache; DELETE FROM chart_cache;"

# Run dashboard
streamlit run dashboard/streamlit_app.py

# Expected:
# - Analysis runs (5-15s)
# - Table appears with sortable columns
# - Sidebar shows "Charts: 0/20"
# - Background processor starts
```

### Test 2: Table Sorting
```bash
# Click each column header:
# - "Net APR" → verify sorts descending (highest APR first)
# - "APR 5d" → verify sorts by 5-day APR
# - "APR 30d" → verify sorts by 30-day average
# - "Liquidity" → verify sorts by liquidity
# - "Max Size" → verify sorts by max position size

# Verify:
# - Sorting is instant (<100ms)
# - No page reload
# - Values display correctly (percentages with %, money with $)
```

### Test 3: Modal Dialog
```bash
# Click table row

# Verify modal opens with:
# ✅ Strategy overview (protocols, Net APR, max size)
# ✅ Position breakdown table (L_A, B_A, L_B, B_B)
# ✅ APR details (Net APR, APR 5d, APR 30d with descriptions)
# ✅ Chart section (either displays or shows "Generating...")
# ✅ Deploy button

# Test modal interactions:
# - Close modal (click outside or X) → back to table
# - Open different strategy → new modal with different data
# - Click deploy → deployment form appears (existing functionality)
```

### Test 4: Background Processing
```bash
# After dashboard loads:
# 1. Check sidebar → verify "Background Processing" section
# 2. Verify progress bar: "Charts: 0/20"
# 3. Wait 30 seconds
# 4. Click "Check for Updates"
# 5. Verify progress bar increments: "Charts: 3/20"
# 6. Wait 5 minutes
# 7. Click "Check for Updates"
# 8. Verify progress bar: "Charts: 15/20"

# Open strategy modal:
# - If chart not ready → "📊 Generating... X/20 charts ready"
# - If chart ready → Plotly chart displays

# Check database:
sqlite3 data/rates.db "SELECT COUNT(*) FROM chart_cache"
# Should show increasing count as charts complete
```

### Test 5: Liq_Distance Change
```bash
# Default liq_distance = 10%

# Change to 15%:
# - If cached → table updates in <500ms
# - If not cached → spinner appears, then updates (5-15s)

# Change to 5%:
# - Same behavior (cached or not)

# Verify:
# - Results differ between liq_distances
# - Each liq_distance is cached separately
# - Background processor queues uncached variants

# Check database:
sqlite3 data/rates.db "SELECT timestamp_seconds, liquidation_distance FROM analysis_cache"
# Should show multiple entries with different liq_distances
```

### Test 6: Cache Persistence
```bash
# 1. Open dashboard → analysis runs (5-15s)
# 2. Close browser tab
# 3. Open dashboard again → should load from cache (<1s)

# Verify:
# - No re-analysis
# - Table displays immediately
# - Charts from previous session still cached

# Check cache hit:
# - Dashboard loads in <1s (not 5-15s)
# - No spinner or "Running analysis..." message
```

### Test 7: Position Deployment
```bash
# 1. Click table row → modal opens
# 2. Click "Deploy Position" button
# 3. Verify deployment form appears (existing functionality)
# 4. Fill form (deployment_usd, etc.)
# 5. Submit
# 6. Verify position created in database
# 7. Verify dashboard updates

# This should work exactly as before (no changes to deployment flow)
```

---

## Cache Cleanup (Optional)

To prevent database from growing indefinitely, add cache cleanup:

```python
# In data/rate_tracker.py

def cleanup_old_cache(self, days_to_keep: int = 30):
    """
    Delete cache entries older than X days.

    Args:
        days_to_keep: Number of days to keep (default 30)
    """
    cutoff_seconds = int(time.time()) - (days_to_keep * 86400)

    with sqlite3.connect(self.db_path) as conn:
        conn.execute("DELETE FROM analysis_cache WHERE created_at < ?", (cutoff_seconds,))
        conn.execute("DELETE FROM chart_cache WHERE created_at < ?", (cutoff_seconds,))
        conn.commit()
```

Run periodically (e.g., in refresh_pipeline or as cron job).

---

## Rollback Plan

If issues arise during implementation:

1. **Phase 1 Issues (Cache Tables)**
   - Drop tables: `DROP TABLE analysis_cache; DROP TABLE chart_cache;`
   - Remove cache methods from rate_tracker.py
   - Revert refresh_pipeline.py changes

2. **Phase 2 Issues (Sortable Table)**
   - Revert dashboard_renderer.py to use expanders
   - Remove display_strategies_table() function
   - Keep old render_all_strategies_tab() function

3. **Phase 3 Issues (Modal)**
   - Remove @st.dialog function
   - Revert to expander-based detail display

4. **Phase 4 Issues (Background Processor)**
   - Delete dashboard/background_processor.py
   - Remove background processor initialization from streamlit_app.py
   - Charts will not be cached, but dashboard still works

Each phase is independent, so you can rollback selectively.

---

## Future Enhancements (Post-Implementation)

Once core functionality is working:

1. **Chart Caching Improvements**
   - Pre-generate charts for top 50 strategies (not just 20)
   - Add cache warming on startup

2. **Analysis Variants**
   - Support custom liq_distance values (not just presets)
   - Add toggle presets to background queue

3. **Performance Monitoring**
   - Log cache hit/miss rates
   - Track background task completion times
   - Alert on slow queries

4. **UI Polish**
   - Add search box to filter table by token symbol
   - Add "Export to CSV" button
   - Add keyboard shortcuts (e.g., Escape to close modal)

5. **Background Task Status**
   - Show estimated time remaining
   - Add "Cancel all tasks" button
   - Display task queue size

---

## Design Principles Compliance Checklist

✅ **Timestamp as "Current Time"**
- Selected timestamp defines "now" throughout dashboard
- Historical queries use `WHERE timestamp <= strategy_timestamp`
- No `datetime.now()` defaults

✅ **Unix Seconds (Integer Timestamps)**
- All internal processing uses `to_seconds()` → int
- Conversion only at boundaries (DB/UI)
- Display uses `to_datetime_str()`

✅ **Rate Representation (Decimals)**
- All rates stored as decimals (0.05 = 5%)
- Display conversion: `f"{rate * 100:.2f}%"`
- No ambiguity in calculations

✅ **Token Identity (Contract Addresses)**
- All logic uses `normalize_coin_type(contract)`
- Symbols only for display
- DataFrame filtering by contract, not symbol

✅ **Streamlit Chart Width**
- Use `width="stretch"` (not deprecated `use_container_width=True`)

✅ **No sys.path Manipulation**
- No new `sys.path.append()` calls

✅ **Position Sizing**
- Multipliers (L_A, B_A, L_B, B_B) scaled by deployment_usd
- No changes to existing position structure

✅ **Event Sourcing**
- No mutation of historical records
- Cache is additive (never modifies existing snapshots)

---

## Success Criteria

### Functional Requirements
- ✅ Dashboard loads in <1s from cache
- ✅ Table sortable by all columns
- ✅ Modal opens with strategy details
- ✅ Charts display (from cache) or show "Generating..."
- ✅ Position deployment works as before
- ✅ Background processor generates charts without blocking UI
- ✅ Additional liq_distance variants computed in background

### Performance Requirements
- ✅ Cached load: <1s
- ✅ Table sort: <100ms
- ✅ Modal open: <300ms
- ✅ Liq_distance change (cached): <500ms

### User Experience Requirements
- ✅ No full page reloads on table interaction
- ✅ Clear feedback when charts are generating
- ✅ Progress indicator for background tasks
- ✅ All existing functionality preserved (filters, deployment, etc.)

---

## Questions Answered

**Q: What is a modal?**
A: A modal is a popup dialog overlay that appears on top of the page. When you click a table row, a modal window opens showing strategy details. Close it by clicking outside or pressing X, and you're back to the table. No new tabs, no navigation.

**Q: Won't pre-rendering charts take forever?**
A: Yes! That's why we don't pre-render. The dashboard loads first with cached analysis (instant), then charts generate in the background while the user interacts with the table. Charts appear progressively as they complete.

**Q: Can the table be sorted by different metrics?**
A: Yes! Streamlit's `st.dataframe()` supports native column sorting. Click any column header (Net APR, APR 5d, APR 30d, Liquidity, Max Size) to sort. Sorting is instant (client-side, no backend call).

**Q: How does the architecture flow work?**
A:
1. User opens dashboard
2. Check DB cache for (timestamp, liq_distance)
3. If cache hit → load instantly (<1s)
4. If cache miss → run analysis once with default settings (5-15s), save to DB
5. Display sortable table
6. Start background processor (non-blocking)
7. Background: Generate charts + compute liq_distance variants
8. User can interact immediately while background tasks run

**Q: What is APR 5d?**
A: APR 5d is a custom metric showing the annualized return if you pay all fees upfront but exit the position after 5 days. This helps evaluate strategies for short-term holds where upfront fees have significant impact.

---

## Ready to Implement

This plan is complete and ready for implementation. Each phase is clearly defined with:
- ✅ Detailed implementation steps
- ✅ Code examples for key functions
- ✅ Testing procedures
- ✅ Performance targets
- ✅ Design principles compliance
- ✅ Rollback procedures

**Next step:** Begin Phase 1 (Database Cache Foundation)
