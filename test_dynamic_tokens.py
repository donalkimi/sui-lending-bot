#!/usr/bin/env python3
"""
Test dynamic token detection from Google Sheets
"""

import sys
import pandas as pd

sys.path.insert(0, '/mnt/user-data/outputs/sui-lending-bot-complete')

from config import settings
from analysis.rate_analyzer import RateAnalyzer

print("="*80)
print("TESTING DYNAMIC TOKEN DETECTION")
print("="*80)

# Create mock data with extra tokens not in settings
tokens = ["USDC", "USDY", "DEEP", "WAL", "BLUE", "BUCK"]  # BLUE and BUCK are NEW
protocols = ["NAVI", "SuiLend"]

# Mock lending rates
lend_data = {
    'Token': tokens,
    'NAVI': [0.046, 0.097, 0.28, 0.36, 0.25, 0.15],
    'SuiLend': [0.049, 0.049, 0.31, 0.35, 0.27, 0.18]
}
lend_rates = pd.DataFrame(lend_data)

# Mock borrow rates
borrow_data = {
    'Token': tokens,
    'NAVI': [0.037, 0.037, 0.195, 0.242, 0.20, 0.12],
    'SuiLend': [0.049, 0.059, 0.269, 0.285, 0.24, 0.14]
}
borrow_rates = pd.DataFrame(borrow_data)

# Mock collateral ratios
collateral_data = {
    'Token': tokens,
    'NAVI': [0.80, 0.80, 0.47, 0.60, 0.50, 0.70],
    'SuiLend': [0.77, 0.77, 0.19, 0.19, 0.25, 0.40]
}
collateral_ratios = pd.DataFrame(collateral_data)

print("\n📊 Mock Google Sheets Data:")
print(f"   Tokens in sheet: {tokens}")
print(f"   Stablecoins (hardcoded in settings): {settings.STABLECOINS}")

# Create analyzer - should detect BLUE and BUCK dynamically
print("\n" + "="*80)
print("CREATING ANALYZER")
print("="*80)

analyzer = RateAnalyzer(
    lend_rates=lend_rates,
    borrow_rates=borrow_rates,
    collateral_ratios=collateral_ratios,
    liquidation_distance=0.30
)

print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

print(f"\n✓ Stablecoins (from settings): {settings.STABLECOINS}")
print(f"✓ Other Tokens (detected dynamically): {analyzer.OTHER_TOKENS}")
print(f"✓ All Tokens (combined): {analyzer.ALL_TOKENS}")

# Verify the detection worked
expected_others = ["DEEP", "WAL", "BLUE", "BUCK"]
detected_others = analyzer.OTHER_TOKENS

if set(detected_others) == set(expected_others):
    print(f"\n✅ PASS: Correctly detected non-stablecoin tokens!")
    print(f"   Expected: {expected_others}")
    print(f"   Detected: {detected_others}")
else:
    print(f"\n❌ FAIL: Token detection mismatch")
    print(f"   Expected: {expected_others}")
    print(f"   Detected: {detected_others}")

# Verify settings.py is clean
try:
    _ = settings.ALL_TOKENS
    print(f"\n⚠️  WARNING: settings.ALL_TOKENS still exists (should be removed)")
except AttributeError:
    print(f"\n✅ PASS: settings.ALL_TOKENS removed from settings.py")

try:
    _ = settings.OTHER_TOKENS
    print(f"⚠️  WARNING: settings.OTHER_TOKENS still exists (should be removed)")
except AttributeError:
    print(f"✅ PASS: settings.OTHER_TOKENS removed from settings.py")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
print("\nResult: Add BLUE and BUCK to your Google Sheets → automatically analyzed!")
