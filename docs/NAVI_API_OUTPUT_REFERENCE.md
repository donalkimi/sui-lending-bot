# Navi Protocol API Output Reference

This document describes the structure of pool objects returned by the Navi Protocol REST API.

## API Information

**Endpoint:** `https://open-api.naviprotocol.io/api/navi/pools?env=prod&sdk=1.3.4-dev.2`

**Type:** REST API (HTTP GET)

**Response Format:** JSON

**Authentication:** None required (public endpoint)

---

## Table of Contents
1. [API Response Structure](#api-response-structure)
2. [Pool Object Structure](#pool-object-structure)
3. [Nested Object Structures](#nested-object-structures)
4. [Example Pool Object](#example-pool-object)
5. [Important Notes](#important-notes)
6. [Field Reference Table](#field-reference-table)
7. [Conversion Helpers](#conversion-helpers)

---

## API Response Structure

The API returns a JSON object with a `data` array containing all pools:

```javascript
{
  "data": [
    { /* Pool Object 1 */ },
    { /* Pool Object 2 */ },
    // ... more pools
  ]
}
```

---

## Pool Object Structure

Each pool object in the `data` array has the following structure:

```javascript
{
  // === BASIC IDENTIFIERS ===
  id: number,                           // Pool/reserve ID (e.g., 6)
  uniqueId: string,                     // Unique identifier (e.g., "main-6")
  market: string,                       // Market name (e.g., "main")
  status: string,                       // Pool status: "active" or "deprecated"
  tags: string[],                       // Pool tags (e.g., ["sui"])
  
  // === TOKEN INFORMATION ===
  coinType: string,                     // Raw coin type without 0x prefix
  suiCoinType: string,                  // Full coin type with 0x prefix
  token: TokenInfo,                     // Token metadata object (see nested structures)
  
  // === CONTRACT INFORMATION ===
  contract: ContractInfo,               // Contract addresses (see nested structures)
  isDeprecated: boolean,                // Deprecation flag
  isSuiBridge: boolean,                 // Bridge token flag (Sui Bridge)
  isLayerZero: boolean,                 // Bridge token flag (LayerZero)
  isWormhole: boolean,                  // Bridge token flag (Wormhole)
  isIsolated: boolean,                  // Isolation mode flag
  
  // === ORACLE / PRICING ===
  oracleId: number,                     // Oracle identifier
  oracle: OracleInfo,                   // Oracle data object (see nested structures)
  
  // === SUPPLY / BORROW AMOUNTS (Raw Units) ===
  totalSupplyAmount: string,            // Total supplied (raw units, scaled by decimals)
  totalSupply: string,                  // Alternative total supply field
  totalBorrow: string,                  // Total borrowed (raw units)
  borrowedAmount: string,               // Alternative borrowed amount field
  availableBorrow: string,              // Available to borrow (raw units)
  leftSupply: string,                   // Remaining supply capacity
  leftBorrowAmount: string,             // Remaining borrow capacity
  validBorrowAmount: string,            // Valid borrow amount considering caps
  minimumAmount: string,                // Minimum transaction amount
  
  // === CAPACITY CEILINGS (Scaled by 1e27) ===
  borrowCapCeiling: string,             // Maximum borrow cap (scaled by 1e27)
  supplyCapCeiling: string,             // Maximum supply cap (scaled by 1e27)
  
  // === INTEREST RATE INDICES (Scaled by 1e27) ===
  currentBorrowIndex: string,           // Cumulative borrow interest index
  currentSupplyIndex: string,           // Cumulative supply interest index
  currentBorrowRate: string,            // Current borrow rate per second (scaled by 1e27)
  currentSupplyRate: string,            // Current supply rate per second (scaled by 1e27)
  lastUpdateTimestamp: string,          // Last update timestamp (milliseconds)
  
  // === COLLATERAL PARAMETERS (Scaled by 1e27) ===
  ltv: string,                          // Loan-to-Value ratio (scaled by 1e27)
  
  // === TREASURY ===
  treasuryBalance: string,              // Treasury balance (raw units)
  treasuryFactor: string,               // Treasury factor (scaled by 1e27)
  
  // === INTEREST RATE MODEL ===
  borrowRateFactors: BorrowRateFactors, // Interest rate curve parameters
  
  // === LIQUIDATION PARAMETERS ===
  liquidationFactor: LiquidationFactor, // Liquidation settings
  
  // === APR/APY INFORMATION ===
  supplyIncentiveApyInfo: IncentiveApyInfo,  // Supply APR/APY breakdown
  borrowIncentiveApyInfo: IncentiveApyInfo,  // Borrow APR/APY breakdown
  
  // === VALUE AT RISK ===
  var: string                           // Value at Risk metric (USD)
}
```

---

## Nested Object Structures

### TokenInfo

Token metadata including price from token service:

```javascript
TokenInfo {
  coinType: string,      // Full coin type with 0x prefix
                         // e.g., "0xbde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI"
  decimals: number,      // Token decimal places (e.g., 9)
  logoUri: string,       // URL to token logo image
  symbol: string,        // Token symbol (e.g., "haSUI")
  price: number          // Token price in USD from token service (e.g., 1.538)
}
```

### OracleInfo

Oracle price data from Pyth or other oracle:

```javascript
OracleInfo {
  decimal: number,       // Price decimal places (e.g., 9)
  value: string,         // Raw oracle price value (e.g., "1436233370")
  price: string,         // Formatted price string (e.g., "1.43623337")
  oracleId: number,      // Oracle identifier
  valid: boolean         // Whether oracle price is valid/fresh
}
```

**Note:** There are TWO price sources:
- `token.price` - Price from Navi's token service (may be more up-to-date)
- `oracle.price` - Price from on-chain oracle (authoritative for liquidations)

### ContractInfo

On-chain contract addresses:

```javascript
ContractInfo {
  reserveId: string,     // Reserve object ID
                         // e.g., "0x0c9f7a6ca561dc566bd75744bcc71a6af1dc3caf7bd32c099cd640bb5f3bb0e3"
  pool: string           // Pool object ID
                         // e.g., "0x6fd9cb6ebd76bc80340a9443d72ea0ae282ee20e2fd7544f6ffcd2c070d9557a"
}
```

### BorrowRateFactors

Interest rate model parameters (all scaled by 1e27):

```javascript
BorrowRateFactors {
  fields: {
    baseRate: string,              // Base interest rate (e.g., "0")
    multiplier: string,            // Rate multiplier below optimal utilization
                                   // e.g., "133300000000000000000000000"
    jumpRateMultiplier: string,    // Rate multiplier above optimal utilization
                                   // e.g., "3200000000000000000000000000"
    optimalUtilization: string,    // Optimal/kink utilization point
                                   // e.g., "750000000000000000000000000" (75%)
    reserveFactor: string          // Protocol reserve factor
                                   // e.g., "350000000000000000000000000" (35%)
  }
}
```

### LiquidationFactor

Liquidation parameters:

```javascript
LiquidationFactor {
  bonus: string,         // Liquidation bonus (e.g., "0.1" = 10%)
  ratio: string,         // Close factor / liquidation ratio (e.g., "0.35" = 35%)
  threshold: string      // Liquidation threshold (e.g., "0.75" = 75%)
}
```

### IncentiveApyInfo

APR/APY breakdown for supply or borrow side:

```javascript
IncentiveApyInfo {
  vaultApr: string,      // Base protocol APR as percentage string (e.g., "0.019" = 0.019%)
  boostedApr: string,    // Reward/incentive APR as percentage string (e.g., "1.9735" = 1.9735%)
  rewardCoin: string[],  // Array of reward token coin types
                         // e.g., ["0x549e8b69270defbfafd4f94e17ec44cdbdd99820b33bda2278dea3b9a32d3f55::cert::CERT"]
  apy: string,           // Total APY as percentage string (e.g., "4.058" = 4.058%)
  voloApy: string,       // Volo-specific APY component
  stakingYieldApy: string,  // Staking yield component (for LSTs)
                            // e.g., "2.0657508163632876"
  treasuryApy: string    // Treasury yield component
}
```

---

## Example Pool Object

Complete example of a pool object (haSUI):

```json
{
  "borrowCapCeiling": "850000000000000000000000000",
  "coinType": "bde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI",
  "currentBorrowIndex": "1091268110015026935679698915",
  "currentBorrowRate": "6249550491485682586783888",
  "currentSupplyIndex": "1024617602378377445552681164",
  "currentSupplyRate": "190449909037200366887624",
  "id": 6,
  "isIsolated": false,
  "lastUpdateTimestamp": "1769507629342",
  "ltv": "700000000000000000000000000",
  "oracleId": 6,
  "supplyCapCeiling": "4.5e+34",
  "treasuryBalance": "432786500502",
  "treasuryFactor": "650000000000000000000000000",
  "suiCoinType": "0xbde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI",
  "totalSupplyAmount": "28762452701711106",
  "minimumAmount": "4500000",
  "leftSupply": "16237547.298288893",
  "validBorrowAmount": "24448084796454440.1",
  "borrowedAmount": "1348480362588270",
  "leftBorrowAmount": "24448084795105960.1",
  "availableBorrow": "23099604433866170.1",
  "contract": {
    "reserveId": "0x0c9f7a6ca561dc566bd75744bcc71a6af1dc3caf7bd32c099cd640bb5f3bb0e3",
    "pool": "0x6fd9cb6ebd76bc80340a9443d72ea0ae282ee20e2fd7544f6ffcd2c070d9557a"
  },
  "isDeprecated": false,
  "isSuiBridge": false,
  "isLayerZero": false,
  "isWormhole": false,
  "token": {
    "coinType": "0xbde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI",
    "decimals": 9,
    "logoUri": "https://x4rjmmpwhoncvduw.public.blob.vercel-storage.com/lending/token/hasui.svg",
    "symbol": "haSUI",
    "price": 1.538
  },
  "oracle": {
    "decimal": 9,
    "value": "1436233370",
    "price": "1.43623337",
    "oracleId": 6,
    "valid": false
  },
  "totalSupply": "28071402086931472",
  "totalBorrow": "1235700329014197",
  "borrowRateFactors": {
    "fields": {
      "baseRate": "0",
      "multiplier": "133300000000000000000000000",
      "jumpRateMultiplier": "3200000000000000000000000000",
      "optimalUtilization": "750000000000000000000000000",
      "reserveFactor": "350000000000000000000000000"
    }
  },
  "liquidationFactor": {
    "bonus": "0.1",
    "ratio": "0.35",
    "threshold": "0.75"
  },
  "var": "11241.03684966",
  "supplyIncentiveApyInfo": {
    "vaultApr": "0.019",
    "boostedApr": "1.9735",
    "rewardCoin": [
      "0x549e8b69270defbfafd4f94e17ec44cdbdd99820b33bda2278dea3b9a32d3f55::cert::CERT"
    ],
    "apy": "4.058",
    "voloApy": "0",
    "stakingYieldApy": "2.0657508163632876",
    "treasuryApy": "0"
  },
  "borrowIncentiveApyInfo": {
    "vaultApr": "0.624",
    "boostedApr": "0",
    "rewardCoin": [],
    "apy": "0.624",
    "voloApy": "0",
    "stakingYieldApy": "0",
    "treasuryApy": "0"
  },
  "status": "active",
  "tags": ["sui"],
  "uniqueId": "main-6",
  "market": "main"
}
```

---

## Important Notes

### Price Sources

There are **two different price sources** in each pool object:

| Source | Field | Type | Description |
|--------|-------|------|-------------|
| Token Service | `token.price` | `number` | Price from Navi's token price service |
| Oracle | `oracle.price` | `string` | Price from on-chain Pyth oracle |

**Recommendation:** Use `oracle.price` for accurate pricing as it matches on-chain liquidation logic. The `token.price` may be cached or have different update frequency.

### Scaling Factors

| Field Pattern | Scale Factor | Example |
|---------------|--------------|---------|
| `ltv`, `*Factor`, `*Ceiling` | 1e27 | `"700000000000000000000000000"` = 0.70 (70%) |
| `current*Rate`, `current*Index` | 1e27 | Rate per second, needs conversion to APR |
| Raw amounts (`totalSupply`, etc.) | Token decimals | `"28762452701711106"` with 9 decimals = 28,762,452.70 |
| `availableBorrow` | 1e9 (fixed) | Always scaled by 10^9 regardless of token decimals |

### APR Values in IncentiveApyInfo

The APR/APY values in `supplyIncentiveApyInfo` and `borrowIncentiveApyInfo` are **already percentage values** (not decimals):

```javascript
// Example: vaultApr = "0.019" means 0.019% APR, NOT 1.9%
// To convert to decimal for calculations:
const aprDecimal = parseFloat(pool.supplyIncentiveApyInfo.vaultApr) / 100;
// 0.019 / 100 = 0.00019 (decimal form)
```

### Pool Status

Always check `status` field before processing:
- `"active"` - Pool is operational
- `"deprecated"` - Pool is being phased out, skip in analysis

### Bridge Token Flags

Tokens can be bridged from other chains:
- `isSuiBridge: true` - Native Sui Bridge token
- `isLayerZero: true` - LayerZero bridged token
- `isWormhole: true` - Wormhole bridged token

These may have different risk profiles.

---

## Field Reference Table

### Core Fields

| Field | Type | Scale | Description |
|-------|------|-------|-------------|
| `id` | number | - | Pool/reserve ID |
| `status` | string | - | "active" or "deprecated" |
| `token.symbol` | string | - | Token symbol (e.g., "USDC") |
| `token.decimals` | number | - | Token decimal places |
| `token.coinType` | string | - | Full coin type with 0x prefix |
| `token.price` | number | - | USD price from token service |
| `oracle.price` | string | - | USD price from oracle |

### Supply/Borrow Metrics

| Field | Type | Scale | Description |
|-------|------|-------|-------------|
| `totalSupply` | string | token decimals | Total supplied amount |
| `totalBorrow` | string | token decimals | Total borrowed amount |
| `availableBorrow` | string | 1e9 fixed | Available borrow liquidity |
| `ltv` | string | 1e27 | Loan-to-Value ratio |

### APR/APY Fields

| Field | Type | Scale | Description |
|-------|------|-------|-------------|
| `supplyIncentiveApyInfo.vaultApr` | string | percentage | Base supply APR |
| `supplyIncentiveApyInfo.boostedApr` | string | percentage | Reward supply APR |
| `supplyIncentiveApyInfo.apy` | string | percentage | Total supply APY |
| `borrowIncentiveApyInfo.vaultApr` | string | percentage | Base borrow APR |
| `borrowIncentiveApyInfo.boostedApr` | string | percentage | Reward borrow APR |
| `borrowIncentiveApyInfo.apy` | string | percentage | Total borrow APY |

### Liquidation Fields

| Field | Type | Scale | Description |
|-------|------|-------|-------------|
| `liquidationFactor.bonus` | string | decimal | Liquidation bonus (0.1 = 10%) |
| `liquidationFactor.ratio` | string | decimal | Close factor |
| `liquidationFactor.threshold` | string | decimal | Liquidation threshold |

---

## Conversion Helpers

### Python (used in navi_reader.py)

```python
def parse_scaled_value(value: str, scale: float = 1e27) -> float:
    """Convert scaled integer string to decimal"""
    try:
        return int(value) / scale
    except (TypeError, ValueError):
        return 0.0

def parse_apr_percentage(apr_str: str) -> float:
    """Convert APR percentage string to decimal (e.g., "0.019" -> 0.00019)"""
    try:
        return float(apr_str) / 100.0
    except (TypeError, ValueError):
        return 0.0

def parse_token_amount(amount: str, decimals: int) -> float:
    """Convert raw token amount to human-readable"""
    try:
        return float(amount) / (10 ** decimals)
    except (TypeError, ValueError):
        return 0.0

def parse_available_borrow(amount: str) -> float:
    """Convert available borrow (always 1e9 precision)"""
    try:
        return float(amount) / 1e9
    except (TypeError, ValueError):
        return 0.0

# Example usage:
pool = api_response['data'][0]

# Get token info
symbol = pool['token']['symbol']           # "haSUI"
decimals = pool['token']['decimals']       # 9
coin_type = pool['token']['coinType']      # "0x..."

# Get prices
token_price = pool['token']['price']                    # 1.538 (number)
oracle_price = float(pool['oracle']['price'])           # 1.43623337

# Get LTV
ltv = parse_scaled_value(pool['ltv'])                   # 0.70 (70%)

# Get APRs (already percentage, convert to decimal)
supply_base_apr = parse_apr_percentage(pool['supplyIncentiveApyInfo']['vaultApr'])
supply_reward_apr = parse_apr_percentage(pool['supplyIncentiveApyInfo']['boostedApr'])
supply_total_apr = supply_base_apr + supply_reward_apr

borrow_base_apr = parse_apr_percentage(pool['borrowIncentiveApyInfo']['vaultApr'])
borrow_reward_apr = parse_apr_percentage(pool['borrowIncentiveApyInfo']['boostedApr'])
borrow_net_apr = borrow_base_apr - borrow_reward_apr  # Rewards offset cost

# Get amounts
total_supply = parse_token_amount(pool['totalSupply'], decimals)
total_borrow = parse_token_amount(pool['totalBorrow'], decimals)
available_borrow = parse_available_borrow(pool['availableBorrow'])

# Calculate USD values
total_supply_usd = total_supply * oracle_price
total_borrow_usd = total_borrow * oracle_price
available_borrow_usd = available_borrow * oracle_price

# Calculate utilization
utilization = total_borrow / total_supply if total_supply > 0 else 0.0
```

### JavaScript

```javascript
function parseScaledValue(value, scale = 1e27) {
  try {
    return parseInt(value) / scale;
  } catch {
    return 0.0;
  }
}

function parseAprPercentage(aprStr) {
  try {
    return parseFloat(aprStr) / 100.0;
  } catch {
    return 0.0;
  }
}

function parseTokenAmount(amount, decimals) {
  try {
    return parseFloat(amount) / Math.pow(10, decimals);
  } catch {
    return 0.0;
  }
}

// Example usage:
const pool = apiResponse.data[0];

const ltv = parseScaledValue(pool.ltv);  // 0.70
const supplyApr = parseAprPercentage(pool.supplyIncentiveApyInfo.vaultApr);
const oraclePrice = parseFloat(pool.oracle.price);
```

---

## Comparison: Navi vs Suilend

| Aspect | Navi (REST API) | Suilend (SDK) |
|--------|-----------------|---------------|
| Access Method | HTTP GET request | JavaScript SDK |
| Authentication | None | None |
| Price Source | `token.price` (service) + `oracle.price` | `price` / `smoothedPrice` (BigNumber) |
| APR Format | Percentage strings (e.g., "0.019") | Computed `borrowAprPercent` / `depositAprPercent` |
| Scaling | 1e27 for ratios, token decimals for amounts | 1e18 for Decimal objects |
| LTV Field | `ltv` (scaled by 1e27) | `config.openLtvPct` (percentage) |
| Available Borrow | `availableBorrow` (1e9 fixed precision) | `availableAmount` (token decimals) |
| Reward Info | `supplyIncentiveApyInfo.rewardCoin[]` | `depositsPoolRewardManager.poolRewards[]` |

---

## API Request Example

```bash
curl -X GET "https://open-api.naviprotocol.io/api/navi/pools?env=prod&sdk=1.3.4-dev.2" \
  -H "User-Agent: Mozilla/5.0"
```

Response:
```json
{
  "data": [
    { /* Pool 1 */ },
    { /* Pool 2 */ },
    // ...
  ]
}
```
