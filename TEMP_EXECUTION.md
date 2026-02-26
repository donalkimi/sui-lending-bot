# Plan: Deploy `perp_lending` Strategy — WAL/AlphaFi + WAL-USDC-PERP Short

## Context

The user wants to execute the following strategy on-chain:

1. Swap USDC → WAL (DEX)
2. Lend WAL to AlphaFi
3. Deposit USDC as margin to Bluefin
4. Short WAL-USDC-PERP on Bluefin

This is a **`perp_lending`** strategy (per `BorrowLend_Perp_Strategy.md`):
- **token1 = WAL** (spot token bought and lent to Protocol A)
- **token3 = WAL-USDC-PERP** (shorted on Bluefin, Protocol B)
- **Protocol A = AlphaFi**
- **Protocol B = Bluefin**

The execution engine does **not exist yet** — this is a Phase 2 build.
The plan below describes how to build it for this specific strategy using available SDKs.

---

## Capital Split (Perp Lending Multipliers)

Given total capital = **C USDC** and liquidation distance **d** (e.g. 0.20 = 20%):

```
L_A = 1 / (1 + d)              # e.g. d=0.20 → L_A = 0.833
B_B = L_A                       # perp short notional = spot notional (market neutral)
Bluefin_margin = 1 - L_A = d/(1+d)  # e.g. 0.167
```

**Example — C = $10,000, d = 0.20:**

| Step | Action | Amount |
|------|--------|--------|
| Swap | USDC → WAL | $8,333 USDC |
| Lend | WAL → AlphaFi | $8,333 WAL (L_A × C) |
| Deposit | USDC → Bluefin margin | $1,667 USDC ((1−L_A) × C) |
| Short | WAL-USDC-PERP on Bluefin | $8,333 notional (B_B × C), leverage = 1/d = 5× |

---

## SDK Availability

| Step | SDK | Package | Status in Repo |
|------|-----|---------|----------------|
| Swap USDC→WAL | 7K Protocol aggregator | `@7kprotocol/sdk-ts` | ✅ In node_modules |
| Lend WAL → AlphaFi | AlphaLend SDK | `@alphafi/alphalend-sdk` v1.1.27 | ✅ In node_modules (read-only today) |
| Deposit USDC → Bluefin margin | Bluefin client SDK | `@bluefin-exchange/bluefin-v2-client` | ❓ Needs check |
| Short WAL-USDC-PERP | Same Bluefin client | same | ❓ Needs check |
| Sui transaction signing | Sui SDK | `@mysten/sui.js` or `@mysten/sui` | ✅ Likely in node_modules |

---

## Execution Sequence

### Step 1 — Swap USDC → WAL via 7K Protocol

7K Protocol is a DEX aggregator on Sui that routes across Cetus, Turbos, etc.

```typescript
// Node.js (TypeScript)
import { getQuote, buildTx } from '@7kprotocol/sdk-ts';
import { SuiClient } from '@mysten/sui/client';
import { Ed25519Keypair } from '@mysten/sui/keypairs/ed25519';

const client = new SuiClient({ url: SUI_RPC_URL });
const keypair = Ed25519Keypair.fromSecretKey(PRIVATE_KEY);

// 1a. Get swap quote
const quote = await getQuote({
  tokenIn: USDC_CONTRACT,     // 0x5d4b...::coin::COIN
  tokenOut: WAL_CONTRACT,     // 0x...::wal::WAL
  amountIn: String(l_a_usdc_amount_raw),  // in base units (6 decimals for USDC)
  slippage: 0.005,            // 0.5% slippage tolerance
});

// 1b. Build and execute the swap tx
const { tx } = await buildTx({
  quoteResponse: quote,
  accountAddress: WALLET_ADDRESS,
  slippage: 0.005,
  commission: { partner: PARTNER_ADDRESS, commissionBps: 0 },
});

const result = await client.signAndExecuteTransaction({
  transaction: tx,
  signer: keypair,
  options: { showEffects: true },
});

// result.digest = transaction hash
// Extract actual WAL received from result.effects
```

**Validation before execution:**
- Check `quote.priceImpact < 0.01` (< 1% price impact)
- Check actual price is within `price_tolerance` of `expected_price` from bot

---

### Step 2 — Lend WAL to AlphaFi

AlphaFi has an AlphaLend lending protocol. The SDK (`@alphafi/alphalend-sdk`) is already integrated for reads. Need to find the deposit/supply function.

```typescript
// AlphaLend SDK — deposit pattern (conceptual, verify exact API)
import { AlphaLend } from '@alphafi/alphalend-sdk';

const alphafi = new AlphaLend({ suiClient: client });

// Build deposit transaction
const depositTx = await alphafi.deposit({
  coinType: WAL_CONTRACT,
  amount: wal_amount_raw,        // WAL in base units (9 decimals)
  sender: WALLET_ADDRESS,
});

const result = await client.signAndExecuteTransaction({
  transaction: depositTx,
  signer: keypair,
  options: { showEffects: true },
});
```

**Validation before execution:**
- Verify current AlphaFi WAL supply rate is within `rate_tolerance` of expected
- Confirm WAL amount received from Step 1 matches expected (within slippage)

**Key unknown:** Exact `alphalend-sdk` deposit function signature. The `.mjs` reader at `data/alphalend/alphalend_reader-sdk.mjs` shows SDK initialization patterns — use it as reference.

---

### Step 3 — Deposit USDC as Bluefin Perp Margin

Bluefin perpetuals require depositing margin before opening positions. USDC goes in as collateral.

```typescript
// Bluefin Perp Client — deposit margin
// SDK: @bluefin-exchange/bluefin-v2-client (verify availability)
import { BluefinClient, Networks } from '@bluefin-exchange/bluefin-v2-client';

const bluefinClient = new BluefinClient(
  true,                 // agree to terms
  Networks.PRODUCTION_SUI,
  PRIVATE_KEY,          // wallet private key
  'Ed25519'
);

await bluefinClient.init();

// Deposit USDC as margin
const depositResult = await bluefinClient.depositToBank(
  margin_usdc_amount,   // e.g. 1667.0 USDC
  'USDC'
);

// depositResult.ok = true on success
// depositResult.data = transaction hash
```

**Validation:**
- Confirm Bluefin account balance increased by expected USDC amount
- Check deposit transaction confirmed on-chain

---

### Step 4 — Open Short WAL-USDC-PERP on Bluefin

After margin is deposited, open the short position. Notional = B_B × C, leverage = 1/d.

```typescript
import { ORDER_SIDE, ORDER_TYPE } from '@bluefin-exchange/bluefin-v2-client';

// Place market short order
const orderResult = await bluefinClient.postOrder({
  symbol: 'WAL-PERP',          // market symbol on Bluefin
  side: ORDER_SIDE.SELL,       // short = sell
  orderType: ORDER_TYPE.MARKET,
  quantity: wal_perp_quantity, // in WAL units (= B_B × C / entry_price)
  leverage: Math.round(1 / d), // e.g. 5 for d=0.20
  reduceOnly: false,
});

// orderResult.ok = true on success
// orderResult.data.id = order ID
// orderResult.data.avgFillPrice = actual fill price
```

**Validation before execution:**
- Check Bluefin WAL-USDC-PERP mark price is within `price_tolerance` of `expected_price`
- Check available margin is sufficient for requested leverage
- Check `orderResult.data.avgFillPrice` vs expected (slippage check)

---

## Architecture Integration

Per `docs/Onchain_Execution.md`, execution should live in a **Backend API** (Phase 2).
This strategy touches Phase 2D (swaps), Phase 2C (multi-leg cross-protocol), and Phase 2E (perps).

**Recommended structure for a Node.js backend:**

```
execution-api/
├── index.ts                      # Express/Fastify HTTP API
├── strategies/
│   └── perp_lending_wal.ts       # WAL perp_lending executor
├── steps/
│   ├── swap_7k.ts                # Step 1: 7K swap
│   ├── alphafi_deposit.ts        # Step 2: AlphaFi lend
│   ├── bluefin_deposit.ts        # Step 3: Bluefin margin
│   └── bluefin_short.ts          # Step 4: Bluefin short
├── validation.ts                 # Pre/post execution checks
└── wallet.ts                     # Keypair management
```

The bot sends this HTTP POST:
```json
{
  "strategy_type": "perp_lending",
  "token1": "WAL",
  "protocol_a": "AlphaFi",
  "perp_market": "WAL-USDC-PERP",
  "deployment_usd": 10000,
  "liquidation_distance": 0.20,
  "expected_entry_price_wal": 0.82,
  "price_tolerance": 0.01,
  "rate_tolerance": 0.03
}
```

---

## Execution Order & Sequencing

Steps **must** be sequential (each depends on previous output):

```
1. Swap USDC → WAL           [need WAL amount for step 2]
        ↓
2. Lend WAL → AlphaFi        [uses WAL from step 1]
        ↓
3. Deposit USDC → Bluefin    [uses remaining USDC balance]
        ↓
4. Short WAL-USDC-PERP       [requires step 3 margin to be settled]
```

Steps 3 and 4 could potentially be parallelized if Bluefin allows opening a position before margin settles (unlikely — check Bluefin docs).

**Failure handling:**
- Step 1 fails → abort, no on-chain state changed
- Step 2 fails → WAL is in wallet (not lent); log alert, manual recovery needed
- Step 3 fails → WAL already lent to AlphaFi; USDC in wallet; log alert
- Step 4 fails → WAL lent + USDC at Bluefin but no hedge; most dangerous state → alert immediately

---

## Open Questions / TODOs Before Building

1. **AlphaLend SDK deposit API** — find exact function name/signature in `@alphafi/alphalend-sdk`. Check `data/alphalend/alphalend_reader-sdk.mjs` for initialization patterns to reuse.

2. **Bluefin SDK availability** — confirm `@bluefin-exchange/bluefin-v2-client` or `@bluefin-exchange/bluefin-client` exists in node_modules or needs installing.

3. **WAL contract address** — verify WAL contract on Sui mainnet (needed for 7K swap and AlphaFi deposit). Check `config/settings.py` or `BLUEFIN_TO_LENDINGS` mapping.

4. **Bluefin WAL-PERP market symbol** — confirm exact symbol string used by Bluefin API (seen `BLUEFIN_PERP_MARKETS = ["BTC", "ETH", "SOL", "SUI", "WAL", "DEEP"]` in settings — WAL is supported).

5. **7K SDK commission wallet** — the 7K aggregator requires a partner address for fee routing. Use a neutral address or zero-fee setup.

6. **Private key management** — how is the wallet private key stored/accessed? Railway environment variable? Hardware wallet?

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `execution-api/steps/swap_7k.ts` | Create | 7K Protocol swap step |
| `execution-api/steps/alphafi_deposit.ts` | Create | AlphaFi WAL lending step |
| `execution-api/steps/bluefin_deposit.ts` | Create | Bluefin margin deposit step |
| `execution-api/steps/bluefin_short.ts` | Create | Bluefin perp short step |
| `execution-api/strategies/perp_lending_wal.ts` | Create | Orchestrates all 4 steps |
| `execution-api/index.ts` | Create | HTTP API entry point |
| `docs/Onchain_Execution.md` | Update | Mark Phase 2E as in-progress |

---

## Verification

After execution, confirm on-chain state:
1. **AlphaFi**: Call `alphafi_reader.py` → verify WAL supply position exists at expected amount
2. **Bluefin margin**: Call Bluefin API `/v1/account` → verify USDC balance posted
3. **Bluefin perp**: Call Bluefin API `/v1/positions` → verify short WAL-PERP position at expected notional/leverage
4. **Wallet balance**: Confirm USDC and WAL drained from wallet as expected
