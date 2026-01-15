"""
Streamlit dashboard for Sui Lending Bot
Entry point with mode navigation (live vs historical)

Usage:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.data_loaders import LiveDataLoader, HistoricalDataLoader
from dashboard.dashboard_renderer import render_dashboard


def main():
    """Main entry point with mode navigation"""

    # Page config
    st.set_page_config(
        page_title="Sui Lending Bot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # === MODE NAVIGATION ===
    with st.sidebar:
        # Toggle: False = Live, True = Historical
        is_historical = st.toggle(
            "Historical Mode",
            value=False,  # Default to Live
            key="mode_selector",
            help="Toggle between Live and Historical data views"
        )
        mode = "📜 Historical" if is_historical else "📊 Live"

    # Clear chart cache when switching modes
    if "last_selected_mode" not in st.session_state:
        st.session_state.last_selected_mode = mode

    if st.session_state.last_selected_mode != mode:
        # Clear all chart-related cache
        keys_to_delete = [k for k in st.session_state.keys() if isinstance(k, str) and k.startswith('chart_')]
        for key in keys_to_delete:
            del st.session_state[key]

        st.session_state.last_selected_mode = mode

    # === RENDER DASHBOARD ===
    if mode == "📊 Live":
        st.title("🤖 Sui Lending Bot - Live Dashboard")

        # Initialize refresh nonce for cache busting
        if "refresh_nonce" not in st.session_state:
            st.session_state.refresh_nonce = 0

        # Create live data loader with cache busting
        @st.cache_data(ttl=300)
        def load_live_data(_refresh_nonce: int):
            """Load live data with cache busting via nonce (underscore prefix prevents hashing)"""
            from data.refresh_pipeline import refresh_pipeline

            try:
                # Fetch fresh data from APIs and save to DB (no Slack notifications for dashboard refresh)
                result = refresh_pipeline(send_slack_notifications=False)

                if result is None:
                    return None, "refresh_pipeline() returned None"

                # Extract data from RefreshResult dataclass (including analysis results)
                return (result.lend_rates, result.borrow_rates, result.collateral_ratios,
                       result.prices, result.lend_rewards, result.borrow_rewards,
                       result.available_borrow, result.borrow_fees, result.timestamp,
                       result.protocol_A, result.protocol_B, result.all_results), None

            except Exception as e:
                return None, str(e)

        # Check if we should skip data reload (e.g., when showing deployment form)
        skip_reload = st.session_state.get('skip_data_reload', False)
        if skip_reload:
            # Clear the flag immediately so next refresh works normally
            st.session_state.skip_data_reload = False
            # Set a flag for render_dashboard to skip analysis too
            st.session_state.skip_analysis = True

            # Use cached data from session state if available (avoids calling load_live_data)
            if 'last_live_data' in st.session_state:
                data_result, error = st.session_state.last_live_data
            else:
                # Fallback to normal load if no cached data
                data_result, error = load_live_data(st.session_state.refresh_nonce)
        else:
            # Normal flow - load data with cache busting
            data_result, error = load_live_data(st.session_state.refresh_nonce)
            # Store result in session state for potential skip_reload use
            st.session_state.last_live_data = (data_result, error)
            # Clear skip_analysis flag for normal flow
            st.session_state.skip_analysis = False

        if error:
            st.error(f"❌ Error loading data: {error}")
            st.info("💡 Check that all protocol APIs are accessible")
            st.stop()

        if data_result is None:
            st.warning("⚠️ No data available. Please check protocol connections.")
            st.stop()

        # Unpack data (now includes analysis results from refresh_pipeline)
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp, protocol_A, protocol_B, all_results = data_result

        # Store analysis results in session state for dashboard to use
        st.session_state.pipeline_analysis_results = (protocol_A, protocol_B, all_results)

        # Create LiveDataLoader wrapper with pre-loaded data
        class PreLoadedLiveDataLoader(LiveDataLoader):
            def __init__(self, preloaded_data):
                super().__init__()
                # Only store the first 9 elements (exclude analysis results)
                self._preloaded_data = preloaded_data[:9]
                self._timestamp = preloaded_data[8]

            def load_data(self):
                """Return pre-loaded data instead of fetching again"""
                return self._preloaded_data

        loader = PreLoadedLiveDataLoader(data_result)

        # Render dashboard
        render_dashboard(loader, mode='live')

    else:  # Historical
        # Get available timestamps
        from dashboard.dashboard_utils import get_available_timestamps

        available_timestamps = get_available_timestamps(limit=100)

        if not available_timestamps:
            st.error("❌ No historical snapshots found in database")
            st.info("Run `main.py` to populate snapshots first")
            st.stop()

        # === TIMESTAMP PICKER IN SIDEBAR ===
        with st.sidebar:
            # Initialize both states
            if "selected_timestamp_index" not in st.session_state:
                st.session_state.selected_timestamp_index = 0  # Active timestamp
            if "pending_timestamp_index" not in st.session_state:
                st.session_state.pending_timestamp_index = 0  # Dropdown selection

            # Parse timestamps for display
            timestamp_options = []
            for ts in available_timestamps:
                try:
                    dt = pd.to_datetime(ts)
                    timestamp_options.append(dt.strftime('%Y-%m-%d %H:%M UTC'))
                except:
                    timestamp_options.append(str(ts))

            # Get the active timestamp for loading data
            selected_timestamp = available_timestamps[st.session_state.selected_timestamp_index]

            # Show viewing timestamp right under the toggle
            st.caption(f"Viewing: {timestamp_options[st.session_state.selected_timestamp_index]}")
            st.divider()

            st.markdown("### 📅 Timestamp Selection")

            # Dropdown (stores to pending, NOT selected)
            pending_index = st.selectbox(
                "Select Snapshot",
                range(len(timestamp_options)),
                format_func=lambda i: timestamp_options[i],
                index=st.session_state.pending_timestamp_index,
                key="timestamp_selector"
            )
            st.session_state.pending_timestamp_index = pending_index

            # Apply button appears when selection differs from active
            if pending_index != st.session_state.selected_timestamp_index:
                st.info(f"Click Apply to load: {timestamp_options[pending_index]}")
                if st.button("✓ Apply Selected Timestamp", width="stretch", type="primary"):
                    st.session_state.selected_timestamp_index = pending_index
                    st.rerun()

        st.title("📜 Historical Snapshot Dashboard")

        # Create historical data loader with selected timestamp
        loader = HistoricalDataLoader(selected_timestamp)

        # Render dashboard
        render_dashboard(loader, mode='historical')


if __name__ == "__main__":
    main()
