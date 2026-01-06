"""
Standalone test script for Suilend SDK integration
Outputs a DataFrame with lending market data
"""

import json
import subprocess
import pandas as pd
from pathlib import Path


def get_suilend_data(node_script_path: str = "data/suilend/suilend_reader-sdk.mjs") -> pd.DataFrame:
    """
    Call the Suilend Node.js SDK script and return a formatted DataFrame
    
    Args:
        node_script_path: Path to the suilend_reader-sdk.mjs script
        
    Returns:
        DataFrame with columns: lending_market_id, token, lend_apr, borrow_apr, 
                                lend_reward_apr, borrow_reward_apr
    """
    
    print("🔄 Fetching Suilend data via Node.js SDK...")
    
    # Get absolute path to script
    script_path = Path(node_script_path).resolve()
    
    if not script_path.exists():
        raise FileNotFoundError(f"Script not found at: {script_path}")
    
    # Run the Node.js script
    try:
        result = subprocess.run(
            ["node", str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Node script failed with return code {result.returncode}\n"
                f"STDERR: {result.stderr}\n"
                f"STDOUT: {result.stdout}"
            )
        
        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON from Node script\n"
                f"Error: {e}\n"
                f"Output: {result.stdout[:500]}"
            )
        
        # Extract markets array
        if isinstance(data, dict) and "markets" in data:
            markets = data["markets"]
        elif isinstance(data, list):
            markets = data
        else:
            raise RuntimeError(f"Unexpected data structure: {type(data)}")
        
        print(f"✓ Received {len(markets)} markets from Suilend SDK")
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Node script timed out after 30 seconds")
    except Exception as e:
        raise RuntimeError(f"Failed to execute Node script: {e}")
    
    # Process markets into DataFrame rows
    rows = []
    
    for market in markets:
        coin_type = market.get("coinType", "")
        
        # Extract token symbol from coin type (last part after ::)
        token_symbol = coin_type.split("::")[-1] if coin_type else "UNKNOWN"
        
        # Extract supply APR components
        supply_apr_obj = market.get("supplyApr", {})
        supply_interest_apr = supply_apr_obj.get("interestApr", 0)
        
        # Sum all supply reward APRs
        supply_rewards = supply_apr_obj.get("rewards", [])
        supply_reward_apr = sum(r.get("rewardApr", 0) for r in supply_rewards if r)
        
        # Extract borrow APR components
        borrow_apr_obj = market.get("borrowApr", {})
        borrow_interest_apr = borrow_apr_obj.get("interestApr", 0)
        
        # Sum all borrow reward APRs
        borrow_rewards = borrow_apr_obj.get("rewards", [])
        borrow_reward_apr = sum(r.get("rewardApr", 0) for r in borrow_rewards if r)
        
        # Get market metadata
        ltv = market.get("ltv", 0)
        liq_threshold = market.get("liquidationThreshold", 0)
        utilization = market.get("utilizationRate", 0)
        
        rows.append({
            "lending_market_id": "SUILEND_MAIN",
            "token": token_symbol,
            "coin_type": coin_type,
            "lend_apr": supply_interest_apr,
            "borrow_apr": borrow_interest_apr,
            "lend_reward_apr": supply_reward_apr,
            "borrow_reward_apr": borrow_reward_apr,
            "total_lend_apr": supply_interest_apr + supply_reward_apr,
            "total_borrow_apr": borrow_interest_apr + borrow_reward_apr,
            "ltv": ltv,
            "liquidation_threshold": liq_threshold,
            "utilization_rate": utilization,
        })
    
    # Create DataFrame
    df = pd.DataFrame(rows)
    
    # Sort by total lend APR (descending)
    df = df.sort_values("total_lend_apr", ascending=False)
    
    return df


def main():
    """Main function to test Suilend data fetching"""
    
    print("\n" + "="*80)
    print("SUILEND SDK TEST - Lending Market Data")
    print("="*80 + "\n")
    
    try:
        # Fetch data
        df = get_suilend_data()
        
        # Display summary
        print(f"\n📊 Retrieved {len(df)} markets from Suilend")
        print("\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        print(f"Average Lend APR: {df['total_lend_apr'].mean():.2f}%")
        print(f"Average Borrow APR: {df['total_borrow_apr'].mean():.2f}%")
        print(f"Highest Lend APR: {df['total_lend_apr'].max():.2f}% ({df.loc[df['total_lend_apr'].idxmax(), 'token']})")
        print(f"Highest Borrow APR: {df['total_borrow_apr'].max():.2f}% ({df.loc[df['total_borrow_apr'].idxmax(), 'token']})")
        
        # Display full table
        print("\n" + "="*80)
        print("DETAILED MARKET DATA")
        print("="*80 + "\n")
        
        # Select columns for display
        display_cols = [
            "lending_market_id",
            "token", 
            "lend_apr",
            "borrow_apr",
            "lend_reward_apr",
            "borrow_reward_apr"
        ]
        
        print(df[display_cols].to_string(index=False))
        
        # Save to CSV
        output_file = "suilend_markets.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Full data saved to: {output_file}")
        
        # Display additional details for top 5 markets
        print("\n" + "="*80)
        print("TOP 5 MARKETS BY TOTAL LEND APR")
        print("="*80 + "\n")
        
        top5 = df.head(5)
        for idx, row in top5.iterrows():
            print(f"\n{row['token']}:")
            print(f"  Total Lend APR: {row['total_lend_apr']:.2f}% (Base: {row['lend_apr']:.2f}% + Rewards: {row['lend_reward_apr']:.2f}%)")
            print(f"  Total Borrow APR: {row['total_borrow_apr']:.2f}% (Base: {row['borrow_apr']:.2f}% + Rewards: {row['borrow_reward_apr']:.2f}%)")
            print(f"  LTV: {row['ltv']:.0f}% | Liq Threshold: {row['liquidation_threshold']:.0f}% | Utilization: {row['utilization_rate']*100:.1f}%")
        
        print("\n" + "="*80)
        print("✅ Test completed successfully!")
        print("="*80 + "\n")
        
        return df
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()