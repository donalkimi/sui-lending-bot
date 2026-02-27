// alphalend_reader-sdk.mjs
//https://chatgpt.com/share/6957e3af-a1f0-8006-8b6e-30c8db6f4056

import { SuiClient } from "@mysten/sui/client";
import { AlphalendClient } from "@alphafi/alphalend-sdk";

// Read config from env (so Python can control it)
const RPC_URL = process.env.SUI_RPC_URL || "https://rpc.mainnet.sui.io";
const FALLBACK_RPC_URL = process.env.SUI_FALLBACK_RPC_URL || "https://sui-rpc.publicnode.com";
const RPC_URLS = [...new Set([RPC_URL, FALLBACK_RPC_URL])];
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
      if (!isLastAttempt) {
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
  let lastErr;
  for (const rpcUrl of RPC_URLS) {
    if (rpcUrl !== RPC_URLS[0]) {
      console.error(`[AlphaFi] Trying fallback RPC: ${rpcUrl}`);
    }
    try {
      const suiClient = new SuiClient({ url: rpcUrl });
      const alpha = new AlphalendClient(NETWORK, suiClient);
      const markets = await getAllMarketsWithRetry(alpha);

      // Print JSON for Python to read
      console.log(JSON.stringify(markets));

      // Allow event loop to drain WebSocket close frames before terminating
      console.error(`[AlphaFi] Waiting for WebSocket connections to close gracefully...`);
      await new Promise(resolve => setTimeout(resolve, 100));
      return;
    } catch (err) {
      lastErr = err;
      console.error(`[AlphaFi] Failed with RPC ${rpcUrl}: ${err.message}`);
    }
  }
  throw lastErr;
}

// Run
main().catch(err => {
  console.error("AlphaFi reader failed:", err.message || err);
  process.exit(1);
});
