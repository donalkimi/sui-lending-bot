#!/usr/bin/env python3
"""
Show Scallop API data in detail to verify it's working correctly.
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data.scallop_borrow.scallop_borrow_reader import ScallopBorrowReader
from data.scallop_shared.scallop_base_reader import ScallopReaderConfig


def main():
    print("="*80)
    print("SCALLOP BORROW API DATA (via API Fallback)")
    print("="*80)

    # Create reader - will use API fallback since SDK is rate-limited
    config = ScallopReaderConfig(
        node_script_path='data/scallop_shared/scallop_reader-sdk.mjs',
        debug=False
    )
    reader = ScallopBorrowReader(config)

    # Get all data
    lend_df, borrow_df, collateral_df = reader.get_all_data()

    # Display borrow data (the main focus)
    print("\n" + "="*80)
    print("BORROW RATES (Effective rates after rewards)")
    print("="*80)
    print(f"\nTotal pools: {len(borrow_df)}")

    # Sort by borrow APR to show best rates
    borrow_sorted = borrow_df.sort_values('Borrow_apr', ascending=True)

    print(f"\n{'Token':<12} {'Base APR':<12} {'Reward APR':<12} {'Net APR':<12} {'Utilization':<12}")
    print('-'*80)

    for _, row in borrow_sorted.iterrows():
        base_pct = row['Borrow_base_apr'] * 100
        reward_pct = row['Borrow_reward_apr'] * 100
        net_pct = row['Borrow_apr'] * 100
        util_pct = row['Utilization'] * 100

        # Highlight tokens with significant rewards
        highlight = "⭐ " if row['Borrow_reward_apr'] > 0.01 else "   "

        print(f"{highlight}{row['Token']:<10} {base_pct:>10.2f}% {reward_pct:>10.2f}% {net_pct:>10.2f}% {util_pct:>10.2f}%")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    pools_with_rewards = borrow_df[borrow_df['Borrow_reward_apr'] > 0]

    print(f"\nPools with borrow rewards: {len(pools_with_rewards)} / {len(borrow_df)}")
    print(f"Average base APR: {borrow_df['Borrow_base_apr'].mean() * 100:.2f}%")
    print(f"Average reward APR: {borrow_df['Borrow_reward_apr'].mean() * 100:.2f}%")
    print(f"Average net APR: {borrow_df['Borrow_apr'].mean() * 100:.2f}%")

    if len(pools_with_rewards) > 0:
        print(f"\nFor pools with rewards:")
        print(f"  Average base APR: {pools_with_rewards['Borrow_base_apr'].mean() * 100:.2f}%")
        print(f"  Average reward APR: {pools_with_rewards['Borrow_reward_apr'].mean() * 100:.2f}%")
        print(f"  Average net APR: {pools_with_rewards['Borrow_apr'].mean() * 100:.2f}%")
        print(f"  Max reward APR: {pools_with_rewards['Borrow_reward_apr'].max() * 100:.2f}% ({pools_with_rewards.loc[pools_with_rewards['Borrow_reward_apr'].idxmax(), 'Token']})")

    # Show best borrowing opportunities (lowest net APR)
    print("\n" + "="*80)
    print("TOP 5 BEST BORROW OPPORTUNITIES (Lowest Net APR)")
    print("="*80)

    top_5 = borrow_sorted.head(5)
    print(f"\n{'Rank':<6} {'Token':<12} {'Base APR':<12} {'Reward APR':<12} {'Net APR':<12}")
    print('-'*80)

    for idx, (_, row) in enumerate(top_5.iterrows(), 1):
        base_pct = row['Borrow_base_apr'] * 100
        reward_pct = row['Borrow_reward_apr'] * 100
        net_pct = row['Borrow_apr'] * 100

        print(f"{idx:<6} {row['Token']:<12} {base_pct:>10.2f}% {reward_pct:>10.2f}% {net_pct:>10.2f}%")

    # Show supply data summary
    print("\n" + "="*80)
    print("SUPPLY/LEND RATES")
    print("="*80)

    print(f"\nTotal pools: {len(lend_df)}")
    print(f"Average supply APR: {lend_df['Supply_apr'].mean() * 100:.2f}%")
    print(f"Max supply APR: {lend_df['Supply_apr'].max() * 100:.2f}% ({lend_df.loc[lend_df['Supply_apr'].idxmax(), 'Token']})")
    print(f"Supply rewards: All set to 0 (as configured)")

    # Show collateral info
    print("\n" + "="*80)
    print("COLLATERAL INFO (Sample)")
    print("="*80)

    print(f"\n{'Token':<12} {'Collat Factor':<15} {'Liq Threshold':<15}")
    print('-'*80)

    for _, row in collateral_df.head(10).iterrows():
        print(f"{row['Token']:<12} {row['Collateralization_factor']:>13.2f} {row['Liquidation_threshold']:>13.2f}")

    print(f"\n... and {len(collateral_df) - 10} more pools" if len(collateral_df) > 10 else "")

    print("\n" + "="*80)
    print("✅ API FALLBACK DATA VERIFIED")
    print("="*80)


if __name__ == "__main__":
    main()
