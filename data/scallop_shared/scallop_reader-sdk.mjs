// scallop_reader-sdk.mjs
// Wraps the Scallop SDK to fetch lending market data

import { SuiClient } from "@mysten/sui/client";
import { Scallop } from "@scallop-io/sui-scallop-sdk";

// Read config from env (so Python can control it)
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const NETWORK = "mainnet";
const DEBUG = process.env.SCALLOP_DEBUG === "1";

async function main() {
  console.error("[SDK-JS] Initializing Scallop SDK...");
  const startTime = Date.now();

  // Initialize Scallop SDK with network type
  const scallopSDK = new Scallop({
    networkType: NETWORK,
  });

  console.error("[SDK-JS] Calling scallopSDK.init()...");
  // Initialize the SDK (required before use)
  await scallopSDK.init();
  console.error(`[SDK-JS] SDK initialized in ${Date.now() - startTime}ms`);

  console.error("[SDK-JS] Creating query instance...");
  // Create query instance to fetch market data
  const scallopQuery = await scallopSDK.createScallopQuery();

  console.error(`[SDK-JS] Fetching market data... (elapsed: ${Date.now() - startTime}ms)`);
  // Get all market pools and collateral data
  const marketData = await scallopQuery.queryMarket();
  console.error(`[SDK-JS] Market data fetched (elapsed: ${Date.now() - startTime}ms)`);

  console.error(`[SDK-JS] Fetching borrow incentive pools... (elapsed: ${Date.now() - startTime}ms)`);
  // Get borrow incentive pools for reward APRs
  let borrowIncentivePools = {};
  try {
    borrowIncentivePools = await scallopQuery.getBorrowIncentivePools();
    console.error(`[SDK-JS] Borrow incentive pools fetched (elapsed: ${Date.now() - startTime}ms)`);
  } catch (err) {
    console.error("Warning: getBorrowIncentivePools failed");
    console.error(err.message);
  }

  console.error(`[SDK-JS] Fetching stake reward pools... (elapsed: ${Date.now() - startTime}ms)`);
  // Get stake reward pools for supply reward APRs
  let stakeRewardPools = {};
  try {
    // Get all spool names from market data (sCoinType indicates staking is available)
    const spoolNames = Object.values(marketData.pools || {})
      .filter(pool => pool.sCoinType && pool.sCoinType !== "")
      .map(pool => pool.coinName);

    if (spoolNames.length > 0) {
      stakeRewardPools = await scallopQuery.getStakeRewardPools(spoolNames);
      console.error(`[SDK-JS] Stake reward pools fetched (elapsed: ${Date.now() - startTime}ms)`);
    }
  } catch (err) {
    console.error("Warning: getStakeRewardPools failed");
    console.error(err.message);
  }

  // Get prices from market data (prices are already included in pool data)
  let prices = {};
  if (marketData.pools) {
    for (const [coinName, poolData] of Object.entries(marketData.pools)) {
      if (poolData.price) {
        prices[coinName] = poolData.price;
      }
    }
  }
  console.error(`[SDK-JS] Extracted prices from market data (elapsed: ${Date.now() - startTime}ms)`);

  console.error(`[SDK-JS] Total SDK execution time: ${Date.now() - startTime}ms`);

  // DEBUG: Show raw SDK output
  if (DEBUG) {
    console.error("=== DEBUG: Raw marketData ===");
    console.error(JSON.stringify(marketData, null, 2));
    console.error("\n=== DEBUG: Raw prices ===");
    console.error(JSON.stringify(prices, null, 2));
    console.error("\n=== DEBUG: Borrow incentive pools ===");
    console.error(JSON.stringify(borrowIncentivePools, null, 2));
    console.error("\n=== DEBUG: Stake reward pools ===");
    console.error(JSON.stringify(stakeRewardPools, null, 2));
    console.error("\n=== DEBUG: Available pool keys ===");
    console.error(Object.keys(marketData.pools || {}));

    // Show first pool in detail
    if (marketData.pools) {
      const firstCoin = Object.keys(marketData.pools)[0];
      if (firstCoin) {
        console.error(`\n=== DEBUG: Sample pool data for ${firstCoin} ===`);
        console.error(JSON.stringify(marketData.pools[firstCoin], null, 2));
        console.error(`\n=== DEBUG: Sample collateral data for ${firstCoin} ===`);
        console.error(JSON.stringify(marketData.collaterals?.[firstCoin] || {}, null, 2));
      }
    }
    console.error("\n=== END DEBUG ===\n");
  }

  // Transform market data to our schema
  const markets = [];

  // Process each pool in the market
  if (marketData.pools) {
    for (const [coinName, poolData] of Object.entries(marketData.pools)) {
      // Filter out deprecated assets (borrowLimit = 0)
      if (poolData.borrowLimit === 0) {
        console.error(`${coinName.toUpperCase()} SKIPPED (borrowLimit = 0)`);
        continue;
      }

      // Get the coin type (contract address)
      const coinType = poolData.coinType;
      if (!coinType) continue;

      // Get price (already in pool data)
      const price = poolData.coinPrice || prices[coinName] || null;

      // Get collateral data for this coin
      const collateral = marketData.collaterals?.[coinName] || {};

      // Extract APR data
      // NOTE: Scallop SDK returns APRs as decimals already (0.05 = 5%)
      // supplyApr and borrowApr are the base rates from interest
      const supplyAprBase = poolData.supplyApr || 0;
      const borrowAprBase = poolData.borrowApr || 0;

      // Extract reward APRs from borrow incentive pools
      let borrowRewardApr = 0;
      let supplyRewardApr = 0;

      const incentivePool = borrowIncentivePools[coinName];
      if (incentivePool && incentivePool.points) {
        // Sum all reward APRs from different reward tokens (sSUI, sSCA, etc.)
        for (const [rewardTokenKey, rewardToken] of Object.entries(incentivePool.points)) {
          if (rewardToken.rewardApr) {
            borrowRewardApr += rewardToken.rewardApr;
          }
        }

      }

      // For supply rewards, check stake reward pools
      // (Currently empty from SDK, may need different approach)
      const stakePool = stakeRewardPools[coinName];
      if (stakePool && stakePool.rewards) {
        for (const reward of Object.values(stakePool.rewards || {})) {
          if (reward.rewardApr) {
            supplyRewardApr += reward.rewardApr;
          }
        }
      }

      const lendBaseDecimal = supplyAprBase;
      const lendRewardDecimal = supplyRewardApr;
      const borrowBaseDecimal = borrowAprBase;
      const borrowRewardDecimal = borrowRewardApr;

      // Extract supply/borrow amounts (in coin units, not base units)
      const totalSupplied = poolData.supplyCoin || 0;
      const totalBorrowed = poolData.borrowCoin || 0;

      // Utilization rate (already decimal format from SDK)
      const utilization = poolData.utilizationRate || 0;

      // Calculate available borrow amount in USD
      const availableCoin = totalSupplied - totalBorrowed;
      const availableAmountUsd = price ? availableCoin * price : null;

      // Extract collateral factors from collateral data
      // Scallop uses collateralFactor and liquidationFactor (likely as decimals)
      const collateralizationFactor = collateral.collateralFactor || 0;
      const liquidationThreshold = collateral.liquidationFactor || 0;

      // Extract borrow fee (already in decimal format from SDK)
      const borrowFee = poolData.borrowFee || 0;

      markets.push({
        token_symbol: coinName.toUpperCase(),
        token_contract: coinType,
        price: price ? price.toString() : null,
        lend_apr_base: lendBaseDecimal.toString(),
        lend_apr_reward: lendRewardDecimal.toString(),
        lend_apr_total: (lendBaseDecimal + lendRewardDecimal).toString(),
        borrow_apr_base: borrowBaseDecimal.toString(),
        borrow_apr_reward: borrowRewardDecimal.toString(),
        borrow_apr_total: (borrowBaseDecimal - borrowRewardDecimal).toString(),
        total_supplied: totalSupplied.toString(),
        total_borrowed: totalBorrowed.toString(),
        utilisation: utilization.toString(),
        available_amount_usd: availableAmountUsd ? availableAmountUsd.toString() : null,
        collateralization_factor: collateralizationFactor.toString(),
        liquidation_threshold: liquidationThreshold.toString(),
        borrow_fee: borrowFee.toString(),
      });
    }
  }

  console.error(`[SDK-JS] Transforming data to JSON... (elapsed: ${Date.now() - startTime}ms)`);
  const jsonOutput = JSON.stringify(markets);
  console.error(`[SDK-JS] JSON stringified (${jsonOutput.length} bytes, elapsed: ${Date.now() - startTime}ms)`);

  // Print JSON for Python to read
  console.log(jsonOutput);
  console.error(`[SDK-JS] JSON printed to stdout (elapsed: ${Date.now() - startTime}ms)`);
  console.error(`[SDK-JS] Script finishing... (elapsed: ${Date.now() - startTime}ms)`);
}

// Run
const scriptStartTime = Date.now();
main()
  .then(async () => {
    console.error(`[SDK-JS] main() completed successfully (total elapsed: ${Date.now() - scriptStartTime}ms)`);
    console.error(`[SDK-JS] Waiting for WebSocket connections to close gracefully...`);
    // Allow event loop to drain WebSocket close frames before terminating
    await new Promise(resolve => setTimeout(resolve, 100));
    console.error(`[SDK-JS] Exiting...`);
    process.exit(0);
  })
  .catch((err) => {
    console.error("Scallop reader failed:", err.message || err);
    console.error("\nFull error stack:");
    console.error(err.stack || err);
    process.exit(1);
  });
