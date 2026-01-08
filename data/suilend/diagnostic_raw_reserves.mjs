// Diagnostic script to view RAW Suilend reserve objects
// Shows both pre-parsed and post-parsed reserve data

import { SuiClient } from "@mysten/sui/client";
import { SuilendClient, getTotalAprPercent, Side, getFilteredRewards } from "@suilend/sdk";
import { parseReserve } from "@suilend/sdk/parsers/reserve";
import { normalizeStructTag } from "@mysten/sui/utils";

const LENDING_MARKET_ID = "0x84030d26d85eaa7035084a057f2f11f701b7e2e4eda87551becbc7c97505ece1";
const LENDING_MARKET_TYPE = "0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL";
const RPC_URL = "https://rpc.mainnet.sui.io";

async function main() {
  const suiClient = new SuiClient({ url: RPC_URL });
  const suilendClient = await SuilendClient.initialize(
    LENDING_MARKET_ID,
    LENDING_MARKET_TYPE,
    suiClient,
    false
  );

  const reserves = suilendClient.lendingMarket.reserves;
  
  console.log(`Total reserves: ${reserves.length}\n`);
  console.log("Looking for reserve with deposit rewards...\n");
  
  // Find a reserve with deposit rewards
  for (let i = 0; i < reserves.length; i++) {
    const reserve = reserves[i];
    
    // Check if has deposit rewards
    const depositRewards = reserve.depositsPoolRewardManager?.poolRewards || [];
    
    if (depositRewards.length > 0) {
      console.log("=".repeat(80));
      console.log(`FOUND RESERVE #${i} WITH DEPOSIT REWARDS`);
      console.log("=".repeat(80));
      
      // Show RAW reserve object (before parsing)
      console.log("\n1️⃣  RAW RESERVE OBJECT (before parseReserve):");
      console.log("-".repeat(80));
      console.log(JSON.stringify(reserve, null, 2));
      console.log("-".repeat(80));
      
      // Get metadata for parsing
      const coinType = normalizeStructTag(reserve.coinType.name);
      const metadata = await suiClient.getCoinMetadata({ coinType });
      
      if (!metadata) {
        console.log("\n⚠️  No metadata available for parsing");
        break;
      }
      
      // Create minimal metadata map for parsing
      const coinMetadataMap = {};
      
      // Add base token metadata
      coinMetadataMap[coinType] = metadata;
      
      // Add reward token metadata
      for (const poolReward of depositRewards) {
        const rewardCoinType = normalizeStructTag(poolReward.coinType.name);
        try {
          const rewardMetadata = await suiClient.getCoinMetadata({ coinType: rewardCoinType });
          if (rewardMetadata) {
            coinMetadataMap[rewardCoinType] = rewardMetadata;
          }
        } catch (err) {
          console.log(`Failed to get metadata for ${rewardCoinType}`);
        }
      }
      
      // Parse the reserve
      const parsedReserve = parseReserve(reserve, coinMetadataMap);
      
      // Show FULL parsed reserve object
      console.log("\n2️⃣  FULL PARSED RESERVE OBJECT (after parseReserve):");
      console.log("-".repeat(80));
      console.log(JSON.stringify(parsedReserve, null, 2));
      console.log("-".repeat(80));
      
      // Highlight key structures
      console.log("\n3️⃣  KEY STRUCTURES:");
      console.log("-".repeat(80));
      console.log("\ndepositsPoolRewardManager:");
      console.log(JSON.stringify(parsedReserve.depositsPoolRewardManager, null, 2));
      
      console.log("\nborrowsPoolRewardManager:");
      console.log(JSON.stringify(parsedReserve.borrowsPoolRewardManager, null, 2));
      console.log("-".repeat(80));
      
      break;
    }
  }
  
  console.log("\n✅ Diagnostic complete");
}

main().catch(err => {
  console.error("Error:", err);
  process.exit(1);
});