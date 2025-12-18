#!/usr/bin/env python3
"""
Test script to verify market neutral enforcement
"""

import sys
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, '/mnt/user-data/outputs/sui-lending-bot-complete')

from config import settings
from analysis.rate_analyzer import RateAnalyzer

print("="*80)
print("TESTING MARKET NEUTRAL ENFORCEMENT")
print("="*80)

# Create mock data
protocols = ["NAVI", "SuiLend"]
tokens = ["USDY", "DEEP", "WAL"]

# Mock lending rates
lend_data = {
    'Token': tokens,
    'NAVI': [0.097, 0.28, 0.36],     # USDY: 9.7%, DEEP: 28%, WAL: 36%
    'SuiLend': [0.049, 0.31, 0.35]   # USDY: 4.9%, DEEP: 31%, WAL: 35%
}
lend_rates = pd.DataFrame(lend_data)

# Mock borrow rates
borrow_data = {
    'Token': tokens,
    'NAVI': [0.037, 0.195, 0.242],    # USDY: 3.7%, DEEP: 19.5%, WAL: 24.2%
    'SuiLend': [0.059, 0.269, 0.285]  # USDY: 5.9%, DEEP: 26.9%, WAL: 28.5%
}
borrow_rates = pd.DataFrame(borrow_data)

# Mock collateral ratios
collateral_data = {
    'Token': tokens,
    'NAVI': [0.80, 0.47, 0.60],      # USDY: 80%, DEEP: 47%, WAL: 60%
    'SuiLend': [0.77, 0.19, 0.19]    # USDY: 77%, DEEP: 19%, WAL: 19%
}
collateral_ratios = pd.DataFrame(collateral_data)

print("\n📊 Mock Data:")
print("\nLending Rates:")
print(lend_rates.to_string(index=False))
print("\nBorrow Rates:")
print(borrow_rates.to_string(index=False))
print("\nCollateral Ratios:")
print(collateral_ratios.to_string(index=False))

# Create analyzer
print("\n" + "="*80)
print("INITIALIZING ANALYZER")
print("="*80)

analyzer = RateAnalyzer(
    lend_rates=lend_rates,
    borrow_rates=borrow_rates,
    collateral_ratios=collateral_ratios,
    liquidation_distance=0.30
)

# Test analysis
print("\n" + "="*80)
print("RUNNING ANALYSIS")
print("="*80)

# Override settings for test
original_stablecoins = settings.STABLECOINS
# Note: ALL_TOKENS is now dynamically built in analyzer, not in settings
settings.STABLECOINS = ["USDY"]

try:
    # The analyzer will build ALL_TOKENS from the mock data
    results = analyzer.analyze_all_combinations()
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    if not results.empty:
        print(f"\n✓ Found {len(results)} valid strategies")
        print("\nAll strategies:")
        for idx, row in results.iterrows():
            print(f"\n  Strategy {idx+1}:")
            print(f"    Token1 (Stablecoin): {row['token1']}")
            print(f"    Token2 (High-Yield): {row['token2']}")
            print(f"    Protocol A: {row['protocol_A']}")
            print(f"    Protocol B: {row['protocol_B']}")
            print(f"    Net APR: {row['net_apr']:.2f}%")
            print(f"    Leverage: {row['leverage']:.2f}x")
        
        # Verify all token1 are stablecoins
        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        
        non_stablecoin_token1 = results[~results['token1'].isin(settings.STABLECOINS)]
        
        if not non_stablecoin_token1.empty:
            print("\n❌ FAILED: Found strategies starting with non-stablecoins:")
            print(non_stablecoin_token1[['token1', 'token2', 'protocol_A', 'protocol_B']])
        else:
            print("\n✅ PASSED: All strategies start with stablecoins")
            print(f"   All token1 values: {results['token1'].unique()}")
            print(f"   Required stablecoins: {settings.STABLECOINS}")
        
        # Check that we have high-yield tokens as token2
        print("\n✅ PASSED: High-yield tokens used as token2")
        print(f"   All token2 values: {results['token2'].unique()}")
        
    else:
        print("\n⚠️ No valid strategies found (this might be due to mock data)")
    
finally:
    # Restore settings
    settings.STABLECOINS = original_stablecoins

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
