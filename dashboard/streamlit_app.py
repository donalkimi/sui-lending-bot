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
from data.refresh_pipeline import refresh_pipeline
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
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data(refresh_nonce: int):
    """Run the full refresh pipeline and return a RefreshResult."""
    try:
        result = refresh_pipeline(
            stablecoin_contracts=STABLECOIN_CONTRACTS,
            liquidation_distance=settings.DEFAULT_LIQUIDATION_DISTANCE,
            save_snapshots=getattr(settings, "SAVE_SNAPSHOTS", True),
        )
        return result, None
    except Exception as e:
        return None, str(e)


def display_strategy_details(strategy_row):
    """
    Display expanded strategy details when row is clicked
    
    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
    """
    # Extract all the values we need
    token1 = strategy_row['token1']
    token2 = strategy_row['token2']
    token3 = strategy_row['token3']
    protocol_A = strategy_row['protocol_A']
    protocol_B = strategy_row['protocol_B']
    
    # USD values (multiply by 100 for $100 notional)
    L_A = strategy_row['L_A']
    B_A = strategy_row['B_A']
    L_B = strategy_row['L_B']
    B_B = strategy_row['B_B']
    
    # Rates (already as percentages in the dict)
    lend_rate_1A = strategy_row['lend_rate_1A']
    borrow_rate_2A = strategy_row['borrow_rate_2A']
    lend_rate_2B = strategy_row['lend_rate_2B']
    borrow_rate_3B = strategy_row['borrow_rate_3B']
    
    # Prices
    P1_A = strategy_row['P1_A']
    P2_A = strategy_row['P2_A']
    P2_B = strategy_row['P2_B']
    P3_B = strategy_row['P3_B']
    
    # Token amounts
    T1_A = strategy_row['T1_A']
    T2_A = strategy_row['T2_A']
    T3_B = strategy_row['T3_B']
    
    # Build the table data
    table_data = [
        # Row 1: Protocol A, token1, Lend
        {
            'Protocol': protocol_A,
            'Token': token1,
            'Action': 'Lend',
            'Rate': f"{lend_rate_1A:.2f}%",
            'USD Value': f"${L_A * 100:.2f}",
            'Token Amount': f"{(L_A * 100) / P1_A:.2f}",
            'Price': f"${P1_A:.4f}"
        },
        # Row 2: Protocol A, token2, Borrow
        {
            'Protocol': protocol_A,
            'Token': token2,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_2A:.2f}%",
            'USD Value': f"${B_A * 100:.2f}",
            'Token Amount': f"{(B_A * 100) / P2_A:.2f}",
            'Price': f"${P2_A:.4f}"
        },
        # Row 3: Protocol B, token2, Lend
        # Note: USD value uses token2 price in protocol B, but token amount from protocol A
        {
            'Protocol': protocol_B,
            'Token': token2,
            'Action': 'Lend',
            'Rate': f"{lend_rate_2B:.2f}%",
            'USD Value': f"${((B_A * 100) / P2_A) * P2_B:.2f}",  # token amount * price in B
            'Token Amount': f"{(B_A * 100) / P2_A:.2f}",  # Same amount as borrowed from A
            'Price': f"${P2_B:.4f}"
        },
        # Row 4: Protocol B, token3, Borrow
        {
            'Protocol': protocol_B,
            'Token': token3,
            'Action': 'Borrow',
            'Rate': f"{borrow_rate_3B:.2f}%",
            'USD Value': f"${B_B * 100:.2f}",
            'Token Amount': f"{(B_B * 100) / P3_B:.2f}",
            'Price': f"${P3_B:.4f}"
        }
    ]
    
    # Create DataFrame and display
    details_df = pd.DataFrame(table_data)
    st.dataframe(details_df, use_container_width=True, hide_index=True)


def main():
    """Main dashboard"""

    # Header
    st.title("🚀 Sui Lending Bot")
    st.markdown("**Cross-Protocol Yield Optimizer**")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Liquidation Distance - inline with label
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("**Liquidation Dist (%)**")
        with col2:
            liq_dist_text = st.text_input(
                label="Liq Dist",
                value=str(int(settings.DEFAULT_LIQUIDATION_DISTANCE * 100)),
                label_visibility="collapsed",
                key="liq_input"
            )

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
        
        # Toggle to force token1 = USDC (NEW - placed first)
        force_usdc_start = st.toggle(
            "Force token1 = USDC",
            value=True,
            help="When enabled, only shows strategies starting with USDC"
        )
        
        # Toggle to force token3 = token1
        force_token3_equals_token1 = st.toggle(
            "Force token3 = token1 (no conversion)",
            value=True,
            help="When enabled, only shows strategies where the closing stablecoin matches the starting stablecoin"
        )

        st.markdown("---")

        st.subheader("📊 Data Source")
        st.info(f"Live data from {len(['Navi', 'AlphaFi', 'Suilend'])} protocols")

        if "refresh_nonce" not in st.session_state:
            st.session_state.refresh_nonce = 0

        if st.button("🔄 Refresh Data", use_container_width=True):
            # Bust only the cached data load by changing the cache key (refresh_nonce)
            st.session_state.refresh_nonce += 1
            st.rerun()

        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

    # Load data
    with st.spinner("Loading data from protocols..."):
        result, error = load_data(st.session_state.refresh_nonce)

    if error:
        st.error(f"❌ Error loading data: {error}")
        st.info("💡 Check that all protocol APIs are accessible")
        st.stop()

    if result is None:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    lend_rates = result.lend_rates
    borrow_rates = result.borrow_rates
    collateral_ratios = result.collateral_ratios
    prices = result.prices
    lend_rewards = result.lend_rewards
    borrow_rewards = result.borrow_rewards

    if lend_rates.empty or borrow_rates.empty or collateral_ratios.empty:
        st.warning("⚠️ No data available. Please check protocol connections.")
        st.stop()

    # Analysis results (already computed in refresh_pipeline)
    protocol_A = result.protocol_A
    protocol_B = result.protocol_B
    all_results = result.all_results
    stablecoin_results = result.stablecoin_results
    

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
            # Results already computed in refresh_pipeline
            pass

        if protocol_A and not all_results.empty:
            # Apply USDC filter if enabled
            if force_usdc_start:
                all_results = all_results[all_results['token1'] == 'USDC']
            # Apply token3=token1 filter if enabled
            if force_token3_equals_token1:
                all_results = all_results[all_results['token3'] == all_results['token1']]

            if all_results.empty:
                st.warning("⚠️ No strategies found with current filters")
            else:
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
                
                for idx, row in all_results.head(10).iterrows():
                    with st.expander(
                        f"▶ {row['token1']} → {row['token2']} → {row['token3']} | "
                        f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                        f"{row['net_apr']:.2f}% APR"
                    ):
                        display_strategy_details(row)

    # ---------------- Tab 2 ----------------
    with tab2:
        st.header("📊 All Valid Strategies")

        if not all_results.empty:
            # Apply USDC filter if enabled
            if force_usdc_start:
                all_results = all_results[all_results['token1'] == 'USDC']
            # Apply token3=token1 filter if enabled
            if force_token3_equals_token1:
                all_results = all_results[all_results['token3'] == all_results['token1']]

            if all_results.empty:
                st.warning("⚠️ No strategies found with current filters")
            else:
                col1, col2, col3 = st.columns(3)

                with col1:
                    min_apr = st.number_input("Min APR (%)", value=0.0, step=0.5)

                with col2:
                    token_filter = st.multiselect(
                        "Filter by Token",
                        options=sorted(set(all_results['token1']).union(set(all_results['token2'])).union(set(all_results['token3']))) if not all_results.empty else [],
                        default=[]
                    )

                with col3:
                    protocol_filter = st.multiselect(
                        "Filter by Protocol",
                        options=['Navi','AlphaFi','Suilend'],
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

                # Display with expanders
                for idx, row in filtered_results.iterrows():
                    with st.expander(
                        f"▶ {row['token1']} → {row['token2']} → {row['token3']} | "
                        f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                        f"{row['net_apr']:.2f}% APR"
                    ):
                        display_strategy_details(row)

    # ---------------- Tab 3 ----------------
    with tab3:
        st.header("💰 Stablecoin Strategies")

        if protocol_A and protocol_B:
            stablecoin_results = stablecoin_results

            if not stablecoin_results.empty:
                # Apply USDC filter if enabled
                if force_usdc_start:
                    all_results = all_results[all_results['token1'] == 'USDC']
                # Apply token3=token1 filter if enabled
                if force_token3_equals_token1:
                    all_results = all_results[all_results['token3'] == all_results['token1']]

                if stablecoin_results.empty:
                    st.warning("⚠️ No strategies found with current filters")
                else:
                    # Display with expanders
                    for idx, row in stablecoin_results.iterrows():
                        with st.expander(
                            f"▶ {row['token1']} → {row['token2']} → {row['token3']} | "
                            f"{row['protocol_A']} ↔ {row['protocol_B']} | "
                            f"{row['net_apr']:.2f}% APR"
                        ):
                            display_strategy_details(row)

    # ---------------- Tab 4 ----------------
    with tab4:
        st.header("📈 Current Rates")

        col1, col2 = st.columns(2)
        
        col1.subheader("💵 Lending Rates")
        lend_display = lend_rates.drop(columns=['Contract']) if 'Contract' in lend_rates.columns else lend_rates
        col1.dataframe(lend_display, use_container_width=True, hide_index=True)

        col2.subheader("💸 Borrow Rates")
        borrow_display = borrow_rates.drop(columns=['Contract']) if 'Contract' in borrow_rates.columns else borrow_rates
        col2.dataframe(borrow_display, use_container_width=True, hide_index=True)

        st.subheader("🔒 Collateral Ratios")
        collateral_display = collateral_ratios.drop(columns=['Contract']) if 'Contract' in collateral_ratios.columns else collateral_ratios
        st.dataframe(collateral_display, use_container_width=True, hide_index=True)
        
        st.subheader("💰 Prices")
        prices_display = prices.drop(columns=['Contract']) if 'Contract' in prices.columns else prices
        st.dataframe(prices_display, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()