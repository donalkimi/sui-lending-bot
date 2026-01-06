import pkg from "@suilend/sdk";
import { SuiClient } from "@mysten/sui/client";

const { initializeSuilend } = pkg;

async function test() {
  const suiClient = new SuiClient({ url: "https://fullnode.mainnet.sui.io" });
  const result = await initializeSuilend(suiClient);
  
  console.log("Result keys:", Object.keys(result));
  console.log("\nLending Markets:", result.lendingMarkets?.map(lm => ({
    id: lm.id,
    name: lm.name,
    type: lm.type
  })));
}

test().catch(console.error);
