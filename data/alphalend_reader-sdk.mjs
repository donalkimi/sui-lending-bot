// alphalend_reader-sdk.mjs
//https://chatgpt.com/share/6957e3af-a1f0-8006-8b6e-30c8db6f4056

import { SuiClient } from "@mysten/sui/client";
import { AlphalendClient } from "@alphafi/alphalend-sdk";

// Read config from env (so Python can control it)
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const NETWORK = process.env.ALPHAFI_NETWORK || "mainnet";

async function main() {
  const suiClient = new SuiClient({ url: RPC_URL });
  const alpha = new AlphalendClient(NETWORK, suiClient);

  // 🔴 THIS IS THE LINE YOU ASKED ABOUT
  const markets = await alpha.getAllMarkets();

  // 🔴 This prints JSON for Python to read
  console.log(JSON.stringify(markets));
}

// Run
main().catch(err => {
  console.error("AlphaFi reader failed:", err);
  process.exit(1);
});
