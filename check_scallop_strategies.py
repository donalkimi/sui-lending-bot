"""Check if Scallop strategies exist in analysis results"""
from data.refresh_pipeline import refresh_pipeline

print("Running analysis...")
result = refresh_pipeline(save_snapshots=False, send_slack_notifications=False)

if result.all_results is None or result.all_results.empty:
    print("No strategies found!")
else:
    df = result.all_results
    print(f"\nTotal strategies: {len(df)}")

    scallop_a = (df['protocol_A'] == 'ScallopLend') | (df['protocol_A'] == 'ScallopBorrow')
    scallop_b = (df['protocol_B'] == 'ScallopLend') | (df['protocol_B'] == 'ScallopBorrow')
    scallop_strategies = df[scallop_a | scallop_b]

    print(f"\nStrategies with Scallop:")
    print(f"  ScallopLend as Protocol A: {(df['protocol_A'] == 'ScallopLend').sum()}")
    print(f"  ScallopLend as Protocol B: {(df['protocol_B'] == 'ScallopLend').sum()}")
    print(f"  ScallopBorrow as Protocol A: {(df['protocol_A'] == 'ScallopBorrow').sum()}")
    print(f"  ScallopBorrow as Protocol B: {(df['protocol_B'] == 'ScallopBorrow').sum()}")
    print(f"  Total with Scallop: {len(scallop_strategies)}")

    if len(scallop_strategies) > 0:
        print(f"\nTop 5 Scallop strategies by net APR:")
        cols = ['protocol_A', 'protocol_B', 'token1', 'token2', 'token3', 'net_apr']
        print(scallop_strategies[cols].sort_values('net_apr', ascending=False).head())
    else:
        print("\n❌ NO SCALLOP STRATEGIES FOUND")
        print("\nProtocol combinations in results:")
        protocol_pairs = df.groupby(['protocol_A', 'protocol_B']).size().sort_values(ascending=False)
        print(protocol_pairs)
