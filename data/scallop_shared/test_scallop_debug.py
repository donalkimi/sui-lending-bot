#!/usr/bin/env python3
"""
Quick test script to see raw Scallop SDK output.

Usage:
    python data/scallop_shared/test_scallop_debug.py
"""

from scallop_base_reader import ScallopBaseReader, ScallopReaderConfig

config = ScallopReaderConfig(
    node_script_path="data/scallop_shared/scallop_reader-sdk.mjs",
    debug=True  # Enable debug mode to see raw SDK output
)

print("Fetching Scallop market data with DEBUG mode enabled...")
print("=" * 80)

reader = ScallopBaseReader(config)
lend_df, borrow_df, collateral_df = reader.get_all_data()

print("\n" + "=" * 80)
print(f"Successfully fetched {len(lend_df)} markets")
print("=" * 80)

print("\nFirst market (sample):")
if len(lend_df) > 0:
    print(lend_df.iloc[0].to_dict())
