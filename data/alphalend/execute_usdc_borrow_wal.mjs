// execute_usdc_borrow_wal.mjs
// Strategy: Deposit USDC as collateral at AlphaFi, borrow WAL against it.
//
// Sizes from perp_borrowing calculator (deployment=$10,000, liq_dist=20%):
//   l_a = 1.0  → lend $10,000 USDC
//   b_a = 0.72 → borrow $7,200 worth of WAL  (~93,385 WAL @ $0.0771)
//
// Market data (from rates_snapshot / token_registry):
//   USDC: marketId=6, decimals=6,  collateral_ratio=0.85, liq_threshold=0.90
//   WAL:  marketId=7, decimals=9,  price=$0.0771
//
// Usage:
//   SUI_PRIVATE_KEY=<base64_key> node execute_usdc_borrow_wal.mjs
//   or: SUI_PRIVATE_KEY=<base64_key> DEPLOYMENT_USD=10000 LIQ_DIST=0.20 node execute_usdc_borrow_wal.mjs

import 'dotenv/config';
import { SuiClient } from "@mysten/sui/client";
import { Ed25519Keypair } from "@mysten/sui/keypairs/ed25519";
import { AlphalendClient } from "@alphafi/alphalend-sdk";

// ─── Config ────────────────────────────────────────────────────────────────────

const RPC_URL        = process.env.SUI_RPC_URL || "https://fullnode.mainnet.sui.io";
const PRIVATE_KEY_B64 = process.env.SUI_PRIVATE_KEY;   // base64-encoded 32-byte private key

// Strategy parameters (override via env or edit here)
const DEPLOYMENT_USD  = parseFloat(process.env.DEPLOYMENT_USD  || "10000");
const LIQ_DIST        = parseFloat(process.env.LIQ_DIST        || "0.20");

// AlphaFi market IDs (from getAllMarkets())
const USDC_MARKET_ID  = "6";
const WAL_MARKET_ID   = "7";

// Coin types (from token_registry)
const USDC_TYPE = "0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC";
const WAL_TYPE  = "0x356a26eb9e012a68958082340d4c4116e7f55615cf27affcff209cf0ae544f59::wal::WAL";

// Decimals (from token_registry)
const USDC_DECIMALS = 6;
const WAL_DECIMALS  = 9;

// Market risk params (from rates_snapshot)
const USDC_COLLATERAL_RATIO  = 0.85;
const USDC_LIQ_THRESHOLD     = 0.90;

// Price tolerance: abort if WAL price deviates more than this from DB value
const WAL_PRICE_DB           = 0.0771;   // from rates_snapshot
const PRICE_TOLERANCE        = 0.05;     // 5% max deviation

// ─── Position sizing (perp_borrowing formula) ──────────────────────────────────

function calculatePositions(liqDist, liqThreshold, collateralRatio, borrowWeight = 1.0) {
  const liqMax = liqDist / (1.0 - liqDist);
  const rSafe  = liqThreshold / ((1.0 + liqMax) * borrowWeight);
  const r      = Math.min(rSafe, collateralRatio);
  return { l_a: 1.0, b_a: r };
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function toBaseUnits(usdAmount, priceUsd, decimals) {
  const tokenAmount = usdAmount / priceUsd;
  return BigInt(Math.floor(tokenAmount * 10 ** decimals));
}

function fromBaseUnits(raw, decimals) {
  return Number(raw) / 10 ** decimals;
}

// ─── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  // 1. Validate private key
  if (!PRIVATE_KEY_B64) {
    console.error("ERROR: SUI_PRIVATE_KEY environment variable is not set.");
    console.error("  Export your base64-encoded private key before running:");
    console.error("  export SUI_PRIVATE_KEY=$(cat ~/.sui/keystore | ...)");
    process.exit(1);
  }

  const keypair = Ed25519Keypair.fromSecretKey(PRIVATE_KEY_B64);
  const wallet  = keypair.getPublicKey().toSuiAddress();

  const client  = new SuiClient({ url: RPC_URL });
  const alphafi = new AlphalendClient("mainnet", client);

  // 2. Calculate sizes
  const { l_a, b_a } = calculatePositions(
    LIQ_DIST, USDC_LIQ_THRESHOLD, USDC_COLLATERAL_RATIO
  );

  const usdc_usd    = l_a * DEPLOYMENT_USD;
  const wal_borrow_usd = b_a * DEPLOYMENT_USD;

  console.log(`\n=== perp_borrowing: USDC/WAL @ AlphaFi ===`);
  console.log(`  Wallet:          ${wallet}`);
  console.log(`  Deployment:      $${DEPLOYMENT_USD.toLocaleString()}`);
  console.log(`  Liq distance:    ${(LIQ_DIST * 100).toFixed(0)}%`);
  console.log(`  l_a=${l_a.toFixed(4)}  b_a=${b_a.toFixed(4)}`);
  console.log(`  Lend USDC:       $${usdc_usd.toLocaleString()} USDC`);
  console.log(`  Borrow WAL:      $${wal_borrow_usd.toLocaleString()} notional`);

  // 3. Fetch live WAL price from AlphaFi market data and validate
  console.log(`\n[1/4] Fetching live market data...`);
  const markets = await alphafi.getAllMarkets();
  const walMarket  = markets.find(m => m.marketId === WAL_MARKET_ID);
  const usdcMarket = markets.find(m => m.marketId === USDC_MARKET_ID);

  if (!walMarket || !usdcMarket) {
    console.error("ERROR: Could not find USDC or WAL market in AlphaFi markets.");
    process.exit(1);
  }

  const walPriceLive = parseFloat(walMarket.price.toString());
  const priceDev = Math.abs(walPriceLive - WAL_PRICE_DB) / WAL_PRICE_DB;
  console.log(`  WAL price (DB):   $${WAL_PRICE_DB}`);
  console.log(`  WAL price (live): $${walPriceLive.toFixed(6)}  (deviation: ${(priceDev * 100).toFixed(2)}%)`);

  if (priceDev > PRICE_TOLERANCE) {
    console.error(`ERROR: WAL price moved ${(priceDev * 100).toFixed(2)}% from DB value — exceeds ${(PRICE_TOLERANCE * 100).toFixed(0)}% tolerance. Aborting.`);
    process.exit(1);
  }

  // 4. Calculate raw token amounts using live price
  const usdcRaw = toBaseUnits(usdc_usd, 1.0, USDC_DECIMALS);
  const walRaw  = toBaseUnits(wal_borrow_usd, walPriceLive, WAL_DECIMALS);

  console.log(`  USDC raw units:   ${usdcRaw} (= ${fromBaseUnits(usdcRaw, USDC_DECIMALS).toFixed(2)} USDC)`);
  console.log(`  WAL raw units:    ${walRaw} (= ${fromBaseUnits(walRaw, WAL_DECIMALS).toFixed(2)} WAL)`);

  // 5. Check wallet USDC balance
  console.log(`\n[2/4] Checking wallet balance...`);
  const coins = await client.getCoins({ owner: wallet, coinType: USDC_TYPE });
  const totalUsdc = coins.data.reduce((sum, c) => sum + BigInt(c.balance), 0n);
  console.log(`  Wallet USDC balance: ${fromBaseUnits(totalUsdc, USDC_DECIMALS).toFixed(2)} USDC`);

  if (totalUsdc < usdcRaw) {
    console.error(`ERROR: Insufficient USDC. Have ${fromBaseUnits(totalUsdc, USDC_DECIMALS).toFixed(2)}, need ${fromBaseUnits(usdcRaw, USDC_DECIMALS).toFixed(2)}.`);
    process.exit(1);
  }

  // 6. Supply USDC as collateral
  // positionCapId omitted — SDK creates a new position automatically on first supply
  console.log(`\n[3/4] Supplying ${fromBaseUnits(usdcRaw, USDC_DECIMALS).toFixed(2)} USDC to AlphaFi...`);
  const supplyTx = await alphafi.supply({
    marketId:  USDC_MARKET_ID,
    amount:    usdcRaw,
    coinType:  USDC_TYPE,
    address:   wallet,
  });

  const supplyResult = await client.signAndExecuteTransaction({
    transaction: supplyTx,
    signer:      keypair,
    options:     { showEffects: true, showObjectChanges: true },
  });

  if (supplyResult.effects?.status?.status !== "success") {
    console.error("ERROR: Supply transaction failed.");
    console.error(JSON.stringify(supplyResult.effects, null, 2));
    process.exit(1);
  }

  console.log(`  Supply tx:  ${supplyResult.digest}`);

  // Extract the newly created positionCapId from object changes
  const createdObjects = supplyResult.objectChanges?.filter(c => c.type === "created") ?? [];
  // The position capability is the PositionCap object created for the user
  const posCapObj = createdObjects.find(o =>
    o.objectType?.includes("PositionCap") || o.objectType?.includes("position_cap")
  );

  if (!posCapObj) {
    console.error("ERROR: Could not find positionCapId in supply transaction output.");
    console.error("Created objects:", JSON.stringify(createdObjects, null, 2));
    process.exit(1);
  }

  const positionCapId = posCapObj.objectId;
  console.log(`  positionCapId:  ${positionCapId}`);

  // 7. Borrow WAL against USDC collateral
  console.log(`\n[4/4] Borrowing ${fromBaseUnits(walRaw, WAL_DECIMALS).toFixed(2)} WAL from AlphaFi...`);
  const borrowTx = await alphafi.borrow({
    marketId:             WAL_MARKET_ID,
    amount:               walRaw,
    coinType:             WAL_TYPE,
    positionCapId:        positionCapId,
    address:              wallet,
    priceUpdateCoinTypes: [USDC_TYPE, WAL_TYPE],  // all markets we're in
  });

  const borrowResult = await client.signAndExecuteTransaction({
    transaction: borrowTx,
    signer:      keypair,
    options:     { showEffects: true },
  });

  if (borrowResult.effects?.status?.status !== "success") {
    console.error("ERROR: Borrow transaction failed.");
    console.error(JSON.stringify(borrowResult.effects, null, 2));
    process.exit(1);
  }

  console.log(`  Borrow tx:  ${borrowResult.digest}`);

  // 8. Summary
  console.log(`\n=== Done ===`);
  console.log(`  Supplied:      ${fromBaseUnits(usdcRaw, USDC_DECIMALS).toFixed(2)} USDC`);
  console.log(`  Borrowed:      ${fromBaseUnits(walRaw, WAL_DECIMALS).toFixed(2)} WAL`);
  console.log(`  positionCapId: ${positionCapId}`);
  console.log(`  Supply tx:     ${supplyResult.digest}`);
  console.log(`  Borrow tx:     ${borrowResult.digest}`);
  console.log(`\n  SAVE positionCapId — needed for repay/withdraw.`);

  await new Promise(r => setTimeout(r, 100)); // drain WebSocket
}

main().catch(err => {
  console.error("Fatal error:", err.message || err);
  process.exit(1);
});
