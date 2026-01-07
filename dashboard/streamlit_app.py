"""
Streamlit dashboard for Sui Lending Bot
streamlit run dashboard/streamlit_app.py

"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from config.stablecoins import STABLECOIN_CONTRACTS
from data.protocol_merger import merge_protocol_data
from analysis.rate_analyzer import RateAnalyzer
from analysis.position_calculator import PositionCalculator


# Page configuration
st.set_page_config(
    page_title="Sui Lending Bot",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .big-metric {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .protocol-badge {
        background-color: #f0f2f6;
        padding: 0.25rem 0.75rem;
        border-radius: 1rem;
        display: inline-block;
        margin: 0.25rem;
    }

    /* Inline liquidation input */
    .liq-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
    }
    .liq-label {
        font-weight: 600;
        white-space: nowrap;
    }
    .liq-input input {
        width: 70px !important;
        padding: 0.25rem 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from all protocols via protocol merger"""
    try:
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards = merge_protocol_data(
            stablecoin_contracts=STABLECOIN_CONTRACTS
        )
        return lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, None
    except Exception as e:
        return None, None, None, str(e)


def main():
    """Main dashboard"""

    # Header
    st.title("🚀 Sui Lending Bot")
    st.markdown("**Cross-Protocol Yield Optimizer**")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Liquidation Distance
        st.markdown('<div class="liq-row">', unsafe_allow_html=True)
        st.markdown(
            '<div class="liq-label">Liquidation Dist (%)</div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="liq-input">', unsafe_allow_html=True)
        liq_dist_text = st.text_input(
            label="Liquidation Dist (%)",
            value=str(int(settings.DEFAULT_LIQUIDATION_DISTANCE * 100)),
            label_visibility="collapsed",
            key="liq_input"
        )
        st.markdown('</div></div>', unsafe_allow_html=True)

        # Validate input
        try:
            liq_value = float(liq_dist_text)
            if not (1 <= liq_value <= 100):
                st.error("Liquidation Dist must be between 1 and 100")
                st.stop()
        except ValueError:
            st.error("Liquidation Dist must be a number")
            st.stop()

        liquidation_distance = liq_value / 100

        st.markdown("---")
        
        # Toggle to force token3 = token1
        force_token3_equals_token1 = st.toggle(
            "Force token3 = token1 (no conversion)",
            value=False,
            help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
        )

        st.markdown("---")

        st.subheader("📊 Data Source")
        st.info(f"Live data from {len(['Navi', 'AlphaFi', 'Suilend'])} protocols")

        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Load data
    with st.spinner("Loading data from protocols..."):
        lend_rates, borrow_rates, collateral_ratios, prices, lend_rewards, borrow_rewards, error = load_data()

    if error:
        st.error(f"❌ Error loading data: {error}")
        st.info("💡 Check that all protocol APIs are accessible")
        st.stop()

    if lend_rates is None or lend_rates.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # Initialize analyzer
    analyzer = RateAnalyzer(
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        prices=prices,
        lend_rewards=lend_rewards,
        borrow_rewards=borrow_rewards,
        liquidation_distance=liquidation_distance,
        force_token3_equals_token1=force_token3_equals_token1
    )

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Best Opportunities",
        "📊 All Strategies",
        "💰 Stablecoin Focus",
        "📈 Rate Tables"
    ])

    # ---------------- Tab 1 ----------------
    with tab1:
        st.header("🏆 Best Opportunities")

        with st.spinner("Analyzing all combinations..."):
            protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()

        if protocol_A and not all_results.empty:
            best = all_results.iloc[0]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Net APR", f"{best['net_apr']:.2f}%")
            col2.metric("Liquidation Distance", f"{best['liquidation_distance']:.0f}%")
            col3.metric("Protocol A", protocol_A)
            col4.metric("Protocol B", protocol_B)

            st.subheader("Strategy Details")
            st.write(f"**Token 1 (Start):** {best['token1']}")
            st.write(f"**Token 2 (Middle):** {best['token2']}")
            st.write(f"**Token 3 (Close):** {best['token3']}")
            
            if best['token1'] != best['token3']:
                st.info(f"💱 This strategy includes stablecoin conversion: {best['token3']} → {best['token1']}")

            st.subheader("Top 10 Strategies")
            st.dataframe(
                all_results.head(10)[['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 'net_apr', 'liquidation_distance']],
                use_container_width=True,
                hide_index=True
            )

    # ---------------- Tab 2 ----------------
    with tab2:
        st.header("📊 All Valid Strategies")

        if not all_results.empty:
            col1, col2, col3 = st.columns(3)

            with col1:
                min_apr = st.number_input("Min APR (%)", value=0.0, step=0.5)

            with col2:
                token_filter = st.multiselect(
                    "Filter by Token",
                    options=analyzer.ALL_TOKENS,
                    default=[]
                )

            with col3:
                protocol_filter = st.multiselect(
                    "Filter by Protocol",
                    options=analyzer.protocols,
                    default=[]
                )

            filtered_results = all_results[all_results['net_apr'] >= min_apr]

            if token_filter:
                filtered_results = filtered_results[
                    filtered_results['token1'].isin(token_filter) |
                    filtered_results['token2'].isin(token_filter)
                ]

            if protocol_filter:
                filtered_results = filtered_results[
                    filtered_results['protocol_A'].isin(protocol_filter) |
                    filtered_results['protocol_B'].isin(protocol_filter)
                ]

            st.dataframe(
                filtered_results[['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 'net_apr', 'liquidation_distance']],
                use_container_width=True,
                hide_index=True
            )

    # ---------------- Tab 3 ----------------
    with tab3:
        st.header("💰 Stablecoin Strategies")

        if protocol_A and protocol_B:
            stablecoin_results = analyzer.find_best_stablecoin_pairs(protocol_A, protocol_B)

            if not stablecoin_results.empty:
                st.dataframe(
                    stablecoin_results[['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 'net_apr', 'liquidation_distance']],
                    use_container_width=True,
                    hide_index=True
                )

    # ---------------- Tab 4 ----------------
    with tab4:
        st.header("📈 Current Rates")

        col1, col2 = st.columns(2)
        col1.subheader("💵 Lending Rates")
        col1.dataframe(lend_rates, use_container_width=True, hide_index=True)

        col2.subheader("💸 Borrow Rates")
        col2.dataframe(borrow_rates, use_container_width=True, hide_index=True)

        st.subheader("🔒 Collateral Ratios")
        st.dataframe(collateral_ratios, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()