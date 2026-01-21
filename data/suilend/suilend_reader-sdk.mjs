// suilend_reader-sdk.mjs
import { SuiClient } from "@mysten/sui/client";
import { SuilendClient, Side, getFilteredRewards, formatRewards, getDedupedAprRewards } from "@suilend/sdk";
import { parseReserve } from "@suilend/sdk/parsers/reserve";
import { normalizeStructTag } from "@mysten/sui/utils";
import BigNumber from "bignumber.js";
import fs from "fs";
import { execSync } from "child_process";

const LENDING_MARKET_ID = "0x84030d26d85eaa7035084a057f2f11f701b7e2e4eda87551becbc7c97505ece1";
const LENDING_MARKET_TYPE = "0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL";
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const MS_PER_YEAR = 365 * 24 * 60 * 60 * 1000;
const DEBUG = true; // Temporarily enable to check DEEP decimals
const MAX_RETRIES = 1;  // Only retry once
const RETRY_DELAY_MS = 2000;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  for (let attempt = 1; attempt <= MAX_RETRIES + 1; attempt++) {
    try {
      console.error(`[Suilend] Fetching market data (attempt ${attempt}/${MAX_RETRIES + 1})`);

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
    // NOTE: We default to 9 decimals (standard for most Sui tokens including SUI, SPRING_SUI, etc.)
    // This is critical for formatRewards() to calculate APRs correctly
    for (const coinType of allCoinTypes) {
      const parts = coinType.split("::");
      const symbol = parts[parts.length - 1];
      coinMetadataMap[coinType] = {
        symbol: symbol,
        name: symbol,
        decimals: 9,  // Default to 9 decimals for Sui tokens
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

  // Step 4: Price map and reserve map
  const priceMap = {};
  const parsedReserveMap = {};
  parsedReserves.forEach(r => {
    priceMap[r.coinType] = r.price;
    parsedReserveMap[r.coinType] = r;
  });
  // DEBUG: Check SPRING_SUI metadata
  if (DEBUG) {
    const springSuiType = '0x83556891f4a0f233ce7b05cfe7f957d4020492a34f5405b2cb9377d060bef4bf::spring_sui::SPRING_SUI';
    console.error('\n=== CHECKING SPRING_SUI METADATA ===');
    console.error('SPRING_SUI in coinMetadataMap?', springSuiType in coinMetadataMap);
    if (springSuiType in coinMetadataMap) {
      console.error('SPRING_SUI metadata:', coinMetadataMap[springSuiType]);
    }
    console.error('SPRING_SUI in priceMap?', springSuiType in priceMap);
    if (springSuiType in priceMap) {
      console.error('SPRING_SUI price:', priceMap[springSuiType] ? priceMap[springSuiType].toString() : 'undefined');
    }
  }

  // Step 5: Use SDK's formatRewards to get all rewards with correct APR calculations
  const rewardMap = formatRewards(parsedReserveMap, coinMetadataMap, priceMap);

  // Step 6: Build output with APRs

  const output = parsedReserves.map(reserve => {
    // Get rewards from the rewardMap
    const reserveRewards = rewardMap[reserve.coinType];
    const depositRewards = reserveRewards ? reserveRewards[Side.DEPOSIT] : [];
    const borrowRewards = reserveRewards ? reserveRewards[Side.BORROW] : [];

    const filteredDepositRewards = getFilteredRewards(depositRewards);
    const filteredBorrowRewards = getFilteredRewards(borrowRewards);

    // Use getDedupedAprRewards to get only rewards with VALID aprPercent (not NaN)
    const dedupedDepositRewards = getDedupedAprRewards(filteredDepositRewards);
    const dedupedBorrowRewards = getDedupedAprRewards(filteredBorrowRewards);

    // DEBUG: Log deduped rewards for AUSD and DEEP
    if ((reserve.token.symbol === 'AUSD' || reserve.token.symbol === 'DEEP') && DEBUG) {
      console.error(`\n=== DEDUPED REWARDS for ${reserve.token.symbol} (valid APR only) ===`);
      console.error('Filtered count:', filteredDepositRewards.length);
      console.error('Deduped count (valid APR):', dedupedDepositRewards.length);
      dedupedDepositRewards.forEach((reward, i) => {
        console.error(`\nValid Reward ${i}:`);
        console.error('  symbol:', reward.stats.symbol);
        console.error('  rewardCoinType:', reward.stats.rewardCoinType);
        console.error('  mintDecimals:', reward.stats.mintDecimals);
        console.error('  aprPercent:', reward.stats.aprPercent.toString());
        console.error('  price:', reward.stats.price ? reward.stats.price.toString() : 'undefined');
        // Check what's in coinMetadataMap for this reward token
        const rewardMeta = coinMetadataMap[reward.stats.rewardCoinType];
        if (rewardMeta) {
          console.error('  coinMetadataMap decimals:', rewardMeta.decimals);
        }
      });
    }

    // Calculate reward APRs by summing up valid rewards
    const lendBase = reserve.depositAprPercent;
    const lendReward = dedupedDepositRewards.reduce(
      (sum, reward) => sum.plus(reward.stats.aprPercent),
      new BigNumber(0)
    );
    const lendTotal = lendBase.plus(lendReward);

    const borrowBase = reserve.borrowAprPercent;
    const borrowReward = dedupedBorrowRewards.reduce(
      (sum, reward) => sum.plus(reward.stats.aprPercent),
      new BigNumber(0)
    );
    // For borrow, rewards reduce the cost
    const borrowTotal = borrowBase.minus(borrowReward);

    return {
      reserve_id: reserve.id,
      token_symbol: reserve.token.symbol,
      token_contract: reserve.coinType,
      token_decimals: reserve.token.decimals,  // Add decimals to verify DEEP has 6, not 9
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

      // Success - return after logging
      console.log(JSON.stringify(output, null, 2));
      return;

    } catch (err) {
      const isRateLimitOrUnavailable =
        err.status === 503 || err.status === 429 ||
        err.message?.includes('503') || err.message?.includes('429') ||
        err.message?.includes('WebSocket') ||
        err.message?.includes('Stream is closed');

      const isLastAttempt = attempt === MAX_RETRIES + 1;

      if (isRateLimitOrUnavailable && !isLastAttempt) {
        console.error(`[Suilend] Fetch failed (${err.message}). Retrying in ${RETRY_DELAY_MS}ms...`);
        await sleep(RETRY_DELAY_MS);
        continue;
      }

      console.error(`[Suilend] Fetch failed after ${attempt} attempt(s)`);
      throw err;
    }
  }
}

main().catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});
