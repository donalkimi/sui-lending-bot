"""
Streamlit dashboard for Sui Lending Bot
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
from data.sheets_reader import SheetsReader
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
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data():
    """Load data from Google Sheets"""
    try:
        reader = SheetsReader()
        reader.connect()
        lend_rates, borrow_rates, collateral_ratios = reader.get_all_data()
        return lend_rates, borrow_rates, collateral_ratios, None
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
        
        liquidation_distance = st.slider(
            "Liquidation Distance (%)",
            min_value=10,
            max_value=50,
            value=int(settings.DEFAULT_LIQUIDATION_DISTANCE * 100),
            step=5,
            help="Safety buffer from liquidation price"
        ) / 100
        
        st.markdown("---")
        
        st.subheader("📊 Data Source")
        st.info("Data loaded from Google Sheets")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
    
    # Load data
    with st.spinner("Loading data from Google Sheets..."):
        lend_rates, borrow_rates, collateral_ratios, error = load_data()
    
    if error:
        st.error(f"❌ Error loading data: {error}")
        st.info("💡 Make sure you've set up Google Sheets credentials in config/settings.py")
        st.stop()
    
    if lend_rates is None or lend_rates.empty:
        st.warning("⚠️ No data available. Please check your Google Sheets configuration.")
        st.stop()
    
    # Initialize analyzer
    analyzer = RateAnalyzer(
        lend_rates=lend_rates,
        borrow_rates=borrow_rates,
        collateral_ratios=collateral_ratios,
        liquidation_distance=liquidation_distance
    )
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Best Opportunities", 
        "📊 All Strategies", 
        "💰 Stablecoin Focus",
        "📈 Rate Tables"
    ])
    
    # Tab 1: Best Opportunities
    with tab1:
        st.header("🏆 Best Opportunities")
        
        with st.spinner("Analyzing all combinations..."):
            protocol_A, protocol_B, all_results = analyzer.find_best_protocol_pair()
        
        if protocol_A and not all_results.empty:
            best = all_results.iloc[0]
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Net APR", f"{best['net_apr']:.2f}%", help="Annual Percentage Rate")
            
            with col2:
                st.metric("Liquidation Distance", f"{best['liquidation_distance']:.0f}%", help="Safety buffer from liquidation")
            
            with col3:
                st.metric("Protocol A", protocol_A)
            
            with col4:
                st.metric("Protocol B", protocol_B)
            
            # Strategy details
            st.subheader("📋 Strategy Details")
            
            # Check if conversion is happening
            has_conversion = best['token1'] != best['token3']
            
            col1, col2 = st.columns(2)
            
            with col1:
                token_flow = f"{best['token1']} ↔ {best['token2']}"
                if has_conversion:
                    token_flow += f" ↔ {best['token3']} → {best['token1']}"
                
                conversion_info = ""
                if has_conversion:
                    conversion_info = f"\n- **Convert** {best['token3']} → {best['token1']} (1:1)"
                
                st.markdown(f"""
                **Token Flow:** {token_flow}
                
                **Position Sizes:**
                - Lend {best['L_A']:.4f} {best['token1']} in {best['protocol_A']}
                - Borrow {best['B_A']:.4f} {best['token2']} from {best['protocol_A']}
                - Lend {best['L_B']:.4f} {best['token2']} in {best['protocol_B']}
                - Borrow {best['B_B']:.4f} {best['token3']} from {best['protocol_B']}{conversion_info}
                """)
            
            with col2:
                st.markdown(f"""
                **Rates:**
                - Lend {best['token1']} @ {best['lend_rate_1A']:.2f}% APY
                - Borrow {best['token2']} @ {best['borrow_rate_2A']:.2f}% APY
                - Lend {best['token2']} @ {best['lend_rate_2B']:.2f}% APY
                - Borrow {best['token3']} @ {best['borrow_rate_3B']:.2f}% APY
                """)
            
            # Top 10 strategies
            st.subheader("📊 Top 10 Strategies")
            display_cols = ['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 'net_apr', 'liquidation_distance']
            st.dataframe(
                all_results.head(10)[display_cols],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No valid strategies found. Check your data.")
    
    # Tab 2: All Strategies
    with tab2:
        st.header("📊 All Valid Strategies")
        
        if not all_results.empty:
            # Filters
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
            
            # Apply filters
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
            
            st.info(f"Showing {len(filtered_results)} of {len(all_results)} strategies")
            
            # Display table
            display_cols = ['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 
                          'net_apr', 'liquidation_distance', 'L_A', 'B_A', 'L_B', 'B_B']
            st.dataframe(
                filtered_results[display_cols],
                use_container_width=True,
                hide_index=True
            )
            
            # Visualization
            st.subheader("📈 APR Distribution")
            fig = px.histogram(
                all_results,
                x='net_apr',
                nbins=50,
                title='Distribution of Net APR Across All Strategies',
                labels={'net_apr': 'Net APR (%)'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Tab 3: Stablecoin Focus
    with tab3:
        st.header("💰 Stablecoin Strategies")
        
        if protocol_A and protocol_B:
            with st.spinner("Analyzing stablecoin pairs..."):
                stablecoin_results = analyzer.find_best_stablecoin_pairs(protocol_A, protocol_B)
            
            if not stablecoin_results.empty:
                # Top stablecoin strategy
                best_stable = stablecoin_results.iloc[0]
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Best APR", f"{best_stable['net_apr']:.2f}%")
                
                with col2:
                    st.metric("Token Pair", f"{best_stable['token1']} ↔ {best_stable['token2']}")
                
                with col3:
                    st.metric("Liquidation Distance", f"{best_stable['liquidation_distance']:.0f}%")
                
                # All stablecoin strategies
                st.subheader("All Stablecoin Combinations")
                display_cols = ['token1', 'token2', 'token3', 'protocol_A', 'protocol_B', 'net_apr', 'liquidation_distance']
                st.dataframe(
                    stablecoin_results[display_cols],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Heatmap
                st.subheader("📊 Stablecoin APR Heatmap")
                
                # Create pivot table for heatmap
                pivot_data = stablecoin_results.pivot_table(
                    index='token1',
                    columns='token2',
                    values='net_apr',
                    aggfunc='max'
                )
                
                fig = px.imshow(
                    pivot_data,
                    labels=dict(x="Token 2", y="Token 1", color="Net APR (%)"),
                    title="Maximum Net APR for Each Stablecoin Pair",
                    aspect="auto",
                    color_continuous_scale="RdYlGn"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No stablecoin strategies found for the selected protocol pair.")
    
    # Tab 4: Rate Tables
    with tab4:
        st.header("📈 Current Rates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("💵 Lending Rates")
            st.dataframe(lend_rates, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("💸 Borrow Rates")
            st.dataframe(borrow_rates, use_container_width=True, hide_index=True)
        
        st.subheader("🔒 Collateral Ratios")
        st.dataframe(collateral_ratios, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
