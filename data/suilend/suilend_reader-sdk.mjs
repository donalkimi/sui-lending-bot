// suilend_reader-sdk.mjs
import { SuiClient } from "@mysten/sui/client";
import { SuilendClient, getTotalAprPercent, Side, getFilteredRewards } from "@suilend/sdk";
import { parseReserve } from "@suilend/sdk/parsers/reserve";
import { normalizeStructTag } from "@mysten/sui/utils";
import BigNumber from "bignumber.js";

const LENDING_MARKET_ID = "0x84030d26d85eaa7035084a057f2f11f701b7e2e4eda87551becbc7c97505ece1";
const LENDING_MARKET_TYPE = "0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL";
const RPC_URL = "https://rpc.mainnet.sui.io";
const MS_PER_YEAR = 365 * 24 * 60 * 60 * 1000;

async function main() {
  const suiClient = new SuiClient({ url: RPC_URL });
  const suilendClient = await SuilendClient.initialize(
    LENDING_MARKET_ID,
    LENDING_MARKET_TYPE,
    suiClient,
    false
  );

  const reserves = suilendClient.lendingMarket.reserves;

  // Step 1: Collect all unique coin types (reserves + rewards)
  const allCoinTypes = new Set();
  for (const reserve of reserves) {
    if (reserve.config?.element?.isolated) continue;
    allCoinTypes.add(normalizeStructTag(reserve.coinType.name));

    // deposit rewards
    reserve.depositsPoolRewardManager?.poolRewards?.forEach(r =>
      r?.coinType?.name && allCoinTypes.add(normalizeStructTag(r.coinType.name))
    );
    // borrow rewards
    reserve.borrowsPoolRewardManager?.poolRewards?.forEach(r =>
      r?.coinType?.name && allCoinTypes.add(normalizeStructTag(r.coinType.name))
    );
  }

  // Step 2: Fetch metadata
  const coinMetadataMap = {};
  for (const coinType of allCoinTypes) {
    try {
      const metadata = await suiClient.getCoinMetadata({ coinType });
      if (metadata) coinMetadataMap[coinType] = metadata;
    } catch (err) {
      console.error(`Failed to get metadata for ${coinType}:`, err.message);
    }
  }

  // Step 3: Parse reserves
  const parsedReserves = reserves
    .map(r => {
      const coinType = normalizeStructTag(r.coinType.name);
      return coinMetadataMap[coinType] ? parseReserve(r, coinMetadataMap) : null;
    })
    .filter(Boolean);

  // Step 4: Price map
  const priceMap = {};
  parsedReserves.forEach(r => (priceMap[r.coinType] = r.price));

  // Helpers for reward APR calculation
  const getDepositShareUsd = (reserve, share) =>
    share.div(10 ** reserve.mintDecimals).times(reserve.cTokenExchangeRate).times(reserve.price);

  const getBorrowShareUsd = (reserve, share) =>
    share.div(10 ** reserve.mintDecimals).times(reserve.cumulativeBorrowRate).times(reserve.price);

  const formatRewardsForReserve = (reserve, side) => {
    const nowMs = Date.now();
    const poolRewardManager = side === Side.DEPOSIT
      ? reserve.depositsPoolRewardManager
      : reserve.borrowsPoolRewardManager;

    return poolRewardManager.poolRewards.map(poolReward => {
      const isActive = nowMs >= poolReward.startTimeMs && nowMs < poolReward.endTimeMs;
      const rewardPrice = priceMap[poolReward.coinType];

      const aprPercent = rewardPrice
        ? new BigNumber(poolRewardManager.totalShares.toString()).eq(0)
          ? new BigNumber(0)
          : poolReward.totalRewards
              .times(rewardPrice)
              .times(new BigNumber(MS_PER_YEAR).div(poolReward.endTimeMs - poolReward.startTimeMs))
              .div(
                side === Side.DEPOSIT
                  ? getDepositShareUsd(reserve, new BigNumber(poolRewardManager.totalShares.toString()))
                  : getBorrowShareUsd(reserve, new BigNumber(poolRewardManager.totalShares.toString()))
              )
              .times(100)
        : new BigNumber(0);

      return {
        stats: {
          id: poolReward.id,
          isActive,
          rewardIndex: poolReward.rewardIndex,
          reserve,
          rewardCoinType: poolReward.coinType,
          mintDecimals: poolReward.mintDecimals,
          symbol: poolReward.symbol,
          aprPercent,
          side
        },
        obligationClaims: {}
      };
    });
  };

  // Step 5: Build output with APRs
    
  const output = parsedReserves.map(reserve => {
    const depositRewards = formatRewardsForReserve(reserve, Side.DEPOSIT);
    const borrowRewards = formatRewardsForReserve(reserve, Side.BORROW);

    const filteredDepositRewards = getFilteredRewards(depositRewards);
    const filteredBorrowRewards = getFilteredRewards(borrowRewards);

    const lendBase = reserve.depositAprPercent;
    const lendTotal = getTotalAprPercent(Side.DEPOSIT, reserve.depositAprPercent, filteredDepositRewards);
    const lendReward = lendTotal.minus(lendBase);

    const borrowBase = reserve.borrowAprPercent;
    const borrowTotal = getTotalAprPercent(Side.BORROW, reserve.borrowAprPercent, filteredBorrowRewards);
    const borrowReward = borrowBase.minus(borrowTotal);

    return {
      reserve_id: reserve.id,
      token_symbol: reserve.token.symbol,
      token_contract: reserve.coinType,
      lend_apr_base: lendBase.toFixed(3),
      lend_apr_total: lendTotal.toFixed(3),
      lend_apr_reward: lendReward.toFixed(3),
      borrow_apr_base: borrowBase.toFixed(3),
      borrow_apr_total: borrowTotal.toFixed(3),
      borrow_apr_reward: borrowReward.toFixed(3),
      total_supplied: reserve.depositedAmount.toFixed(3),
      total_borrowed: reserve.borrowedAmount.toFixed(3),
      utilisation: reserve.utilizationPercent.toFixed(3),
      collateralization_factor: reserve.config.openLtvPct.toFixed(3),
      liquidation_threshold: reserve.config.closeLtvPct.toFixed(3),
      borrow_fee_bps: reserve.config.borrowFeeBps.toFixed(3),
      spread_fee_bps: reserve.config.spreadFeeBps.toFixed(3),
      available_amount_usd: reserve.availableAmountUsd.toFixed(2)
    };
  });
  console.log(JSON.stringify(output, null, 2));
}

main().catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});
