"""
Streamlit dashboard for Sui Lending Bot
Unified dashboard with timestamp selection and live data refresh

Usage:
    streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
from datetime import datetime
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.data_loaders import UnifiedDataLoader
from dashboard.dashboard_renderer import render_dashboard
from dashboard.dashboard_utils import get_available_timestamps
from data.refresh_pipeline import refresh_pipeline
from utils.time_helpers import to_seconds, to_datetime_str


def main():
    """Main entry point with unified dashboard"""

    # Page config
    st.set_page_config(
        page_title="Sui Lending Bot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("🤖 Sui Lending Bot Dashboard")

    # === LOAD AVAILABLE TIMESTAMPS ===
    try:
        available_timestamps = get_available_timestamps()
    except Exception as e:
        st.error(f"❌ Error loading timestamps from database: {e}")
        st.info("💡 Database might be empty. Click 'Get Live Data' to fetch fresh market data.")
        available_timestamps = []

    # === SIDEBAR: DATA SELECTION ===
    with st.sidebar:
        st.markdown("### 📊 Data Selection")

        # Handle empty database case
        if not available_timestamps:
            st.warning("⚠️ No historical data found in database")
            st.info("Click the button below to fetch fresh market data from protocols")

            # Only show "Get Live Data" button when no data exists
            if st.button("🔄 Get Live Market Data", type="primary", key="initial_refresh"):
                with st.spinner("Fetching live market data from protocols..."):
                    try:
                        result = refresh_pipeline(save_snapshots=True, send_slack_notifications=False)
                        if result and result.timestamp:
                            # result.timestamp is already Unix seconds (int)
                            st.session_state['current_seconds'] = result.timestamp
                            # Convert to datetime string for display and selection
                            st.session_state.selected_timestamp = to_datetime_str(result.timestamp)
                            st.success(f"✅ Fresh data loaded at {to_datetime_str(result.timestamp)}")
                            st.rerun()
                        else:
                            st.error("❌ refresh_pipeline() did not return valid data")
                    except Exception as e:
                        st.error(f"❌ Error fetching live data: {e}")
            st.stop()

        # === TIMESTAMP SELECTION ===
        # Initialize selected_timestamp in session state
        if 'selected_timestamp' not in st.session_state:
            st.session_state.selected_timestamp = available_timestamps[0]  # Latest timestamp

        # Parse timestamps for display
        timestamp_display_map = {}
        for ts in available_timestamps:
            try:
                dt = pd.to_datetime(ts)
                display_str = dt.strftime('%Y-%m-%d %H:%M UTC')
                timestamp_display_map[display_str] = ts
            except:
                timestamp_display_map[str(ts)] = ts

        display_options = list(timestamp_display_map.keys())

        # Find current selection index
        try:
            current_timestamp_display = None
            for display_str, ts in timestamp_display_map.items():
                if ts == st.session_state.selected_timestamp:
                    current_timestamp_display = display_str
                    break

            if current_timestamp_display:
                current_index = display_options.index(current_timestamp_display)
            else:
                current_index = 0
                st.session_state.selected_timestamp = available_timestamps[0]
        except:
            current_index = 0
            st.session_state.selected_timestamp = available_timestamps[0]

        # Timestamp dropdown
        selected_display = st.selectbox(
            "Select Timestamp",
            display_options,
            index=current_index,
            help="Choose a timestamp to view historical data, or use 'Get Live Data' button to fetch fresh data"
        )

        # Update session state if selection changed
        new_timestamp = timestamp_display_map[selected_display]
        if new_timestamp != st.session_state.selected_timestamp:
            st.session_state.selected_timestamp = new_timestamp
            # Clear chart cache when timestamp changes
            keys_to_delete = [k for k in st.session_state.keys() if isinstance(k, str) and k.startswith('chart_')]
            for key in keys_to_delete:
                del st.session_state[key]

        # IMMEDIATELY convert selected timestamp to seconds (Unix timestamp)
        # This is the "current time" throughout the session - everything uses this integer
        try:
            current_seconds = to_seconds(st.session_state.selected_timestamp)
            st.session_state['current_seconds'] = current_seconds
        except Exception as e:
            st.error(f"❌ Failed to convert timestamp to seconds: {e}")
            st.stop()

        # Show timestamp age
        try:
            selected_dt = pd.to_datetime(st.session_state.selected_timestamp)
            age = datetime.now() - selected_dt.replace(tzinfo=None)
            hours_old = age.total_seconds() / 3600

            if hours_old < 1:
                age_str = f"{int(age.total_seconds() / 60)} minutes ago"
                age_color = "green"
            elif hours_old < 24:
                age_str = f"{int(hours_old)} hours ago"
                age_color = "orange" if hours_old > 6 else "green"
            else:
                age_str = f"{int(hours_old / 24)} days ago"
                age_color = "red" if hours_old > 720 else "orange"  # Red if >30 days

            st.caption(f"Data from: :{age_color}[{age_str}]")

            # Warning for very old data
            if hours_old > 720:  # 30 days
                st.warning("⚠️ Data is >30 days old")

        except Exception as e:
            st.caption(f"Timestamp: {st.session_state.selected_timestamp}")

        st.divider()

        # === GET LIVE DATA BUTTON ===
        st.markdown("### 🔄 Refresh Data")

        if st.button("🔄 Get Live Market Data", key="refresh_button", help="Fetch fresh data from protocols and create new snapshot"):
            with st.spinner("Fetching live market data from Navi, AlphaFi, and Suilend..."):
                try:
                    result = refresh_pipeline(save_snapshots=True, send_slack_notifications=False)
                    if result and result.timestamp:
                        # result.timestamp is already Unix seconds (int)
                        st.session_state['current_seconds'] = result.timestamp
                        # Convert to datetime string for display and selection
                        st.session_state.selected_timestamp = to_datetime_str(result.timestamp)
                        # Store analysis results from refresh_pipeline to avoid re-running analysis
                        st.session_state.pipeline_analysis_results = (result.protocol_A, result.protocol_B, result.all_results)
                        st.success(f"✅ Fresh data loaded at {to_datetime_str(result.timestamp)}")
                        st.rerun()
                    else:
                        st.error("❌ refresh_pipeline() did not return valid data")
                except Exception as e:
                    st.error(f"❌ Error fetching live data: {e}")
                    st.exception(e)

        st.caption("Fetches real-time protocol data and saves a new snapshot to the database")

    # === LOAD DATA FOR SELECTED TIMESTAMP ===
    # Check if we should skip data reload (e.g., after position deployment)
    if st.session_state.get('skip_data_reload', False):
        # Clear the flag for next run
        st.session_state.skip_data_reload = False
        # Only stop if we're not trying to show the deployment form
        if not st.session_state.get('show_deploy_form', False):
            st.stop()

    try:
        loader = UnifiedDataLoader(st.session_state.selected_timestamp)
        data_tuple = loader.load_data()

        if data_tuple is None:
            st.error("❌ Failed to load data for selected timestamp")
            st.stop()

        # Unpack the 9-tuple
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, available_borrow, borrow_fees, timestamp = data_tuple

        # Render dashboard
        render_dashboard(loader, mode='unified')

    except Exception as e:
        st.error(f"❌ Error loading dashboard: {e}")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
