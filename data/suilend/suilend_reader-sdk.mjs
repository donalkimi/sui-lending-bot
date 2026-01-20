// suilend_reader-sdk.mjs
import { SuiClient } from "@mysten/sui/client";
import { SuilendClient, getTotalAprPercent, Side, getFilteredRewards } from "@suilend/sdk";
import { parseReserve } from "@suilend/sdk/parsers/reserve";
import { normalizeStructTag } from "@mysten/sui/utils";
import BigNumber from "bignumber.js";
import fs from "fs";
import { execSync } from "child_process";

const LENDING_MARKET_ID = "0x84030d26d85eaa7035084a057f2f11f701b7e2e4eda87551becbc7c97505ece1";
const LENDING_MARKET_TYPE = "0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL";
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const MS_PER_YEAR = 365 * 24 * 60 * 60 * 1000;
const DEBUG = process.env.SUILEND_DEBUG === "1";

async function main() {
  const suiClient = new SuiClient({ url: RPC_URL });
  const suilendClient = await SuilendClient.initialize(
    LENDING_MARKET_ID,
    LENDING_MARKET_TYPE,
    suiClient,
    false
  );

  const reserves = suilendClient.lendingMarket.reserves;

  // DEBUG: Write each reserve object to file BEFORE parsing (only if DEBUG=1)
  if (DEBUG) {
    const debugOutput = [];
    debugOutput.push("=== DEBUG: Raw reserves from Suilend SDK ===");
    debugOutput.push(`Total reserves count: ${reserves.length}\n`);

    reserves.forEach((reserve, idx) => {
      const coinType = normalizeStructTag(reserve.coinType.name);
      debugOutput.push(`\n--- Reserve ${idx + 1}: ${coinType} ---`);
      debugOutput.push(JSON.stringify(reserve, null, 2));
    });

    debugOutput.push("\n=== END DEBUG ===");

    // Write to file
    fs.writeFileSync('suilend_reserves_debug.json', debugOutput.join('\n'), 'utf8');
    console.error("Debug output written to suilend_reserves_debug.json");
  }

  // Step 1: Collect all unique coin types (reserves + rewards)
  const allCoinTypes = new Set();
  for (const reserve of reserves) {
    // Filter out isolated markets
    if (reserve.config?.element?.isolated) continue;

    // Filter out deprecated markets (both limits are zero)
    const depositLimit = Number(reserve.config?.element?.depositLimit || 0);
    const borrowLimit = Number(reserve.config?.element?.borrowLimit || 0);
    if (depositLimit === 0 && borrowLimit === 0) continue;

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

  // Step 2: Fetch metadata from token_registry database (no RPC calls!)
  const coinTypesArray = Array.from(allCoinTypes);
  const coinTypesJson = JSON.stringify(coinTypesArray);

  let coinMetadataMap = {};
  try {
    // Call Python helper to query database
    // Get the directory where this script lives
    const scriptDir = new URL('.', import.meta.url).pathname;
    const pythonScript = `${scriptDir}get_token_metadata.py`;

    const result = execSync(`python3 "${pythonScript}" '${coinTypesJson}'`, {
      encoding: 'utf8'
    });
    coinMetadataMap = JSON.parse(result);

    if (DEBUG) {
      console.error(`Loaded metadata for ${Object.keys(coinMetadataMap).length} tokens from database`);
    }
  } catch (err) {
    console.error(`Failed to load metadata from database: ${err.message}`);
    console.error(`Falling back to extracting symbols from coin types`);

    // Fallback: extract symbol from coin type string
    for (const coinType of allCoinTypes) {
      const parts = coinType.split("::");
      const symbol = parts[parts.length - 1];
      coinMetadataMap[coinType] = {
        symbol: symbol,
        name: symbol,
        iconUrl: null,
        description: null
      };
    }
  }

  // Step 3: Parse reserves (filter out isolated and deprecated)
  const parsedReserves = reserves
    .filter(r => {
      // Filter out isolated markets
      if (r.config?.element?.isolated) return false;

      // Filter out deprecated markets (both limits are zero)
      const depositLimit = Number(r.config?.element?.depositLimit || 0);
      const borrowLimit = Number(r.config?.element?.borrowLimit || 0);
      if (depositLimit === 0 && borrowLimit === 0) return false;

      return true;
    })
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
      price: reserve.price.toFixed(6),
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
