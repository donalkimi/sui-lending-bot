from alphafi_reader import AlphaFiReader, AlphaFiReaderConfig

cfg = AlphaFiReaderConfig(
    node_script_path="alphalend_reader-sdk.mjs",  # adjust path if needed
    rpc_url="https://rpc.mainnet.sui.io",
    network="mainnet",
)

reader = AlphaFiReader(cfg)
lend_df, borrow_df, collateral_df = reader.get_all_data()

print("\nAlphaFi lend_df head(3):")
print(lend_df[["Token", "Token_coin_type", "Supply_apr", "Supply_base_apr", "Supply_reward_apr"]].head(3))

print("\nAlphaFi borrow_df head(3):")
print(borrow_df[["Token", "Token_coin_type", "Borrow_apr", "Borrow_base_apr", "Borrow_reward_apr"]].head(3))

print("\nAlphaFi collateral_df head(3):")
print(collateral_df[["Token", "Token_coin_type", "Collateralization_factor", "Liquidation_threshold"]].head(3))
