// list_markets.mjs — dump AlphaFi market IDs, coin types, and decimals
import { SuiClient } from "@mysten/sui/client";
import { AlphalendClient } from "@alphafi/alphalend-sdk";

const RPC_URL = process.env.SUI_RPC_URL || "https://fullnode.mainnet.sui.io";

const client = new SuiClient({ url: RPC_URL });
const alphafi = new AlphalendClient("mainnet", client);

const markets = await alphafi.getAllMarkets();

if (!markets) {
  console.error("getAllMarkets() returned nothing");
  process.exit(1);
}

// Print a clean table
console.log("\nAlphaFi Markets:\n");
console.log(
  "marketId".padEnd(12),
  "symbol".padEnd(10),
  "decimals".padEnd(10),
  "supplyAPR".padEnd(12),
  "borrowAPR".padEnd(12),
  "coinType"
);
console.log("-".repeat(110));

for (const m of markets) {
  const symbol = m.coinType.split("::").at(-1) ?? "?";
  const supplyApr = (Number(m.supplyApr?.interestApr ?? 0) * 100).toFixed(2) + "%";
  const borrowApr = (Number(m.borrowApr?.interestApr ?? 0) * 100).toFixed(2) + "%";
  console.log(
    String(m.marketId).padEnd(12),
    symbol.padEnd(10),
    String(m.decimalDigit).padEnd(10),
    supplyApr.padEnd(12),
    borrowApr.padEnd(12),
    m.coinType
  );
}

await new Promise(resolve => setTimeout(resolve, 100)); // drain WebSocket
