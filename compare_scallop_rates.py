#!/usr/bin/env python3
"""
Compare Scallop SDK rates vs API rates for all pools.
This script fetches data using both the SDK and API methods and compares the results.
"""

import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from data.scallop_shared.scallop_base_reader import ScallopBaseReader, ScallopReaderConfig


def get_sdk_data():
    """Fetch data using SDK method"""
    print("Fetching data via SDK...")
    config = ScallopReaderConfig(
        node_script_path='data/scallop_shared/scallop_reader-sdk.mjs',
        debug=False
    )
    reader = ScallopBaseReader(config)

    try:
        # Force SDK method
        markets = reader._get_markets_from_sdk()
        lend_df, borrow_df, collateral_df = reader._transform_to_dataframes(markets)
        return lend_df, borrow_df, collateral_df, None
    except Exception as e:
        return None, None, None, str(e)


def get_api_data():
    """Fetch data using API method"""
    print("Fetching data via API...")
    config = ScallopReaderConfig(
        node_script_path='data/scallop_shared/scallop_reader-sdk.mjs',
        debug=False
    )
    reader = ScallopBaseReader(config)

    try:
        # Force API method
        markets = reader._get_markets_from_api()
        lend_df, borrow_df, collateral_df = reader._transform_to_dataframes(markets)
        return lend_df, borrow_df, collateral_df, None
    except Exception as e:
        return None, None, None, str(e)


def compare_dataframes(sdk_df, api_df, df_name):
    """Compare two dataframes and show differences"""
    print(f"\n{'='*80}")
    print(f"COMPARING {df_name}")
    print('='*80)

    # Check if both exist
    if sdk_df is None and api_df is None:
        print("Both SDK and API failed!")
        return

    if sdk_df is None:
        print("SDK failed, only API data available")
        print(f"API has {len(api_df)} pools")
        return

    if api_df is None:
        print("API failed, only SDK data available")
        print(f"SDK has {len(sdk_df)} pools")
        return

    # Compare pool counts
    print(f"\nPool counts:")
    print(f"  SDK: {len(sdk_df)} pools")
    print(f"  API: {len(api_df)} pools")

    # Get common tokens
    sdk_tokens = set(sdk_df['Token'].tolist())
    api_tokens = set(api_df['Token'].tolist())

    common_tokens = sdk_tokens & api_tokens
    sdk_only = sdk_tokens - api_tokens
    api_only = api_tokens - sdk_tokens

    print(f"\nToken overlap:")
    print(f"  Common: {len(common_tokens)} tokens")
    if sdk_only:
        print(f"  SDK only: {sorted(sdk_only)}")
    if api_only:
        print(f"  API only: {sorted(api_only)}")

    # Compare values for common tokens
    if common_tokens and df_name == "BORROW DATA":
        print(f"\n{'Token':<10} {'Metric':<20} {'SDK':<15} {'API':<15} {'Diff %':<10}")
        print('-'*80)

        comparison_rows = []

        for token in sorted(common_tokens):
            sdk_row = sdk_df[sdk_df['Token'] == token].iloc[0]
            api_row = api_df[api_df['Token'] == token].iloc[0]

            # Compare borrow APRs
            metrics = [
                ('Borrow_base_apr', 'Base APR'),
                ('Borrow_reward_apr', 'Reward APR'),
                ('Borrow_apr', 'Total APR'),
            ]

            for col, label in metrics:
                sdk_val = sdk_row[col]
                api_val = api_row[col]

                # Calculate difference
                if sdk_val != 0:
                    diff_pct = ((api_val - sdk_val) / sdk_val) * 100
                elif api_val != 0:
                    diff_pct = 100.0
                else:
                    diff_pct = 0.0

                # Format for display
                sdk_str = f"{sdk_val*100:.4f}%"
                api_str = f"{api_val*100:.4f}%"
                diff_str = f"{diff_pct:+.2f}%"

                # Highlight significant differences
                highlight = "⚠️ " if abs(diff_pct) > 5 else ""

                print(f"{token:<10} {label:<20} {sdk_str:<15} {api_str:<15} {highlight}{diff_str:<10}")

                comparison_rows.append({
                    'Token': token,
                    'Metric': label,
                    'SDK_Value': sdk_val,
                    'API_Value': api_val,
                    'Diff_Percent': diff_pct
                })

        # Summary statistics
        comp_df = pd.DataFrame(comparison_rows)
        print(f"\n{'Summary Statistics:'}")
        print('-'*80)

        for metric in ['Base APR', 'Reward APR', 'Total APR']:
            metric_data = comp_df[comp_df['Metric'] == metric]
            if len(metric_data) > 0:
                max_diff = metric_data['Diff_Percent'].abs().max()
                avg_diff = metric_data['Diff_Percent'].abs().mean()
                print(f"{metric:<20} Max diff: {max_diff:>6.2f}%  Avg diff: {avg_diff:>6.2f}%")

    elif common_tokens and df_name == "LEND DATA":
        print(f"\n{'Token':<10} {'Metric':<20} {'SDK':<15} {'API':<15} {'Diff %':<10}")
        print('-'*80)

        for token in sorted(common_tokens):
            sdk_row = sdk_df[sdk_df['Token'] == token].iloc[0]
            api_row = api_df[api_df['Token'] == token].iloc[0]

            # Compare supply APRs
            metrics = [
                ('Supply_base_apr', 'Base APR'),
                ('Supply_reward_apr', 'Reward APR'),
                ('Supply_apr', 'Total APR'),
            ]

            for col, label in metrics:
                sdk_val = sdk_row[col]
                api_val = api_row[col]

                # Calculate difference
                if sdk_val != 0:
                    diff_pct = ((api_val - sdk_val) / sdk_val) * 100
                elif api_val != 0:
                    diff_pct = 100.0
                else:
                    diff_pct = 0.0

                # Format for display
                sdk_str = f"{sdk_val*100:.4f}%"
                api_str = f"{api_val*100:.4f}%"
                diff_str = f"{diff_pct:+.2f}%"

                # Highlight significant differences
                highlight = "⚠️ " if abs(diff_pct) > 5 else ""

                print(f"{token:<10} {label:<20} {sdk_str:<15} {api_str:<15} {highlight}{diff_str:<10}")

    elif common_tokens and df_name == "COLLATERAL DATA":
        print(f"\n{'Token':<10} {'Metric':<25} {'SDK':<15} {'API':<15} {'Match':<10}")
        print('-'*80)

        for token in sorted(common_tokens)[:10]:  # Show first 10
            sdk_row = sdk_df[sdk_df['Token'] == token].iloc[0]
            api_row = api_df[api_df['Token'] == token].iloc[0]

            metrics = [
                ('Collateralization_factor', 'Collateral Factor'),
                ('Liquidation_threshold', 'Liquidation Threshold'),
            ]

            for col, label in metrics:
                sdk_val = sdk_row[col]
                api_val = api_row[col]

                match = "✅" if abs(sdk_val - api_val) < 0.001 else "❌"

                print(f"{token:<10} {label:<25} {sdk_val:<15.4f} {api_val:<15.4f} {match:<10}")

        if len(common_tokens) > 10:
            print(f"... and {len(common_tokens) - 10} more tokens")


def main():
    print("="*80)
    print("SCALLOP SDK vs API COMPARISON")
    print("="*80)

    # Get SDK data
    sdk_lend, sdk_borrow, sdk_collateral, sdk_error = get_sdk_data()

    if sdk_error:
        print(f"\n⚠️  SDK Error: {sdk_error}")

    # Get API data
    api_lend, api_borrow, api_collateral, api_error = get_api_data()

    if api_error:
        print(f"\n⚠️  API Error: {api_error}")

    # Compare all three dataframes
    compare_dataframes(sdk_borrow, api_borrow, "BORROW DATA")
    compare_dataframes(sdk_lend, api_lend, "LEND DATA")
    compare_dataframes(sdk_collateral, api_collateral, "COLLATERAL DATA")

    print("\n" + "="*80)
    print("COMPARISON COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
