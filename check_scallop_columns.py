"""
Quick diagnostic to check if Scallop columns exist in dataframes
"""
from data.protocol_merger import merge_protocol_data

print("Fetching protocol data...")
lend_df, borrow_df, collateral_df, prices_df, lend_rewards_df, borrow_rewards_df, available_borrow_df, borrow_fees_df = merge_protocol_data()

print("\n" + "="*80)
print("LEND_DF COLUMNS:")
print("="*80)
print(f"Columns: {list(lend_df.columns)}")
print(f"Has ScallopLend: {'ScallopLend' in lend_df.columns}")
print(f"Has ScallopBorrow: {'ScallopBorrow' in lend_df.columns}")

if 'ScallopLend' in lend_df.columns:
    print(f"\nScallopLend non-null values: {lend_df['ScallopLend'].notna().sum()} / {len(lend_df)}")
    print(f"ScallopLend sample values:\n{lend_df[['Token', 'ScallopLend']].head(10)}")

if 'ScallopBorrow' in lend_df.columns:
    print(f"\nScallopBorrow non-null values: {lend_df['ScallopBorrow'].notna().sum()} / {len(lend_df)}")
    print(f"ScallopBorrow sample values:\n{lend_df[['Token', 'ScallopBorrow']].head(10)}")

print("\n" + "="*80)
print("BORROW_DF COLUMNS:")
print("="*80)
print(f"Columns: {list(borrow_df.columns)}")
print(f"Has ScallopLend: {'ScallopLend' in borrow_df.columns}")
print(f"Has ScallopBorrow: {'ScallopBorrow' in borrow_df.columns}")

if 'ScallopLend' in borrow_df.columns:
    print(f"\nScallopLend non-null values: {borrow_df['ScallopLend'].notna().sum()} / {len(borrow_df)}")
    print(f"ScallopLend sample values:\n{borrow_df[['Token', 'ScallopLend']].head(10)}")

if 'ScallopBorrow' in borrow_df.columns:
    print(f"\nScallopBorrow non-null values: {borrow_df['ScallopBorrow'].notna().sum()} / {len(borrow_df)}")
    print(f"ScallopBorrow sample values:\n{borrow_df[['Token', 'ScallopBorrow']].head(10)}")
