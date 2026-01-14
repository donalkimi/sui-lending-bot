// alphalend_reader-sdk.mjs
//https://chatgpt.com/share/6957e3af-a1f0-8006-8b6e-30c8db6f4056

import { SuiClient } from "@mysten/sui/client";
import { AlphalendClient } from "@alphafi/alphalend-sdk";

// Read config from env (so Python can control it)
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const NETWORK = process.env.ALPHAFI_NETWORK || "mainnet";
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2000;

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function getAllMarketsWithRetry(alpha, retries = MAX_RETRIES) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const markets = await alpha.getAllMarkets();

      // Check if markets is undefined or null
      if (markets === undefined || markets === null) {
        throw new Error(`getAllMarkets() returned ${markets}. SDK may have changed.`);
      }

      return markets;
    } catch (err) {
      const isLastAttempt = attempt === retries;
      const isRateLimitOrUnavailable =
        err.status === 503 ||
        err.status === 429 ||
        err.message?.includes('503') ||
        err.message?.includes('429');

      if (isRateLimitOrUnavailable && !isLastAttempt) {
        const delay = RETRY_DELAY_MS * attempt;
        console.error(`Attempt ${attempt}/${retries} failed (${err.status || 'unknown'}). Retrying in ${delay}ms...`);
        await sleep(delay);
        continue;
      }

      // Re-throw if not retryable or last attempt
      throw err;
    }
  }
}

async function main() {
  const suiClient = new SuiClient({ url: RPC_URL });
  const alpha = new AlphalendClient(NETWORK, suiClient);

  const markets = await getAllMarketsWithRetry(alpha);

  // Print JSON for Python to read
  console.log(JSON.stringify(markets));
}

// Run
main().catch(err => {
  console.error("AlphaFi reader failed:", err.message || err);
  process.exit(1);
});
