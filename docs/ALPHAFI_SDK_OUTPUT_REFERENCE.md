# AlphaFi (AlphaLend) SDK Output Reference

This document describes the structure of market objects returned by the AlphaFi SDK WebSocket connection.

## API Information

**Connection Type:** WebSocket

**Protocol:** Custom WebSocket protocol (via Node.js SDK)

**Response Format:** JSON array of market objects

**Authentication:** None required (public endpoint)

---

## Table of Contents
1. [API Response Structure](#api-response-structure)
2. [Market Object Structure](#market-object-structure)
3. [Nested Object Structures](#nested-object-structures)
4. [Example Market Object](#example-market-object)
5. [Important Notes](#important-notes)
6. [Field Reference Table](#field-reference-table)
7. [Conversion Helpers](#conversion-helpers)

---

## API Response Structure

The SDK returns a JSON array containing all market objects:

```javascript
[
  { /* Market Object 1 */ },
  { /* Market Object 2 */ },
  // ... more markets
]
```

---

## Market Object Structure

Each market object in the response array has the following structure:

```javascript
{
  // === BASIC IDENTIFIERS ===
  marketId: string,                     // Market/pool ID (e.g., "4", "30")
  coinType: string,                     // Full coin type with 0x prefix
                                        // e.g., "0x2::sui::SUI"

  // === TOKEN INFORMATION ===
  decimalDigit: number,                 // Token decimal places (e.g., 9)
  price: string,                        // USD price as string (e.g., "1.43987501")

  // === SUPPLY / BORROW AMOUNTS (Human-Readable) ===
  totalSupply: string,                  // Total supplied in human-readable units
                                        // e.g., "21098004.485531442"
  totalBorrow: string,                  // Total borrowed in human-readable units
                                        // e.g., "11887863.922652113"
  availableLiquidity: string,           // Available to borrow (human-readable)
                                        // e.g., "9210140.562879329"

  // === UTILIZATION ===
  utilizationRate: string,              // Utilization as decimal string
                                        // e.g., "0.56345916178018421424"

  // === SUPPLY APR/APY ===
  supplyApr: {
    interestApr: string,                // Base interest APR as decimal string
                                        // e.g., "3.1484050843574424211"
    stakingApr: string,                 // Staking APR as decimal string (LSTs)
                                        // e.g., "0"
    rewards: Array<{                    // Reward token APRs
      coinType: string,                 // Reward token coin type
      rewardApr: string                 // Reward APR as decimal string
    }>
  },

  // === BORROW APR/APY ===
  borrowApr: {
    interestApr: string,                // Base interest APR as decimal string
                                        // e.g., "6.5736902207688158328"
    rewards: Array<{                    // Reward token APRs (reduce borrow cost)
      coinType: string,                 // Reward token coin type
      rewardApr: string                 // Reward APR as decimal string
    }>
  },

  // === COLLATERAL PARAMETERS ===
  ltv: string,                          // Loan-to-Value as percentage string
                                        // e.g., "85" = 85%
  liquidationThreshold: string,         // Liquidation threshold as percentage string
                                        // e.g., "90" = 90%
  borrowWeight: string,                 // Borrow weight multiplier
                                        // e.g., "1" = 1x, "1.5" = 1.5x, "2" = 2x

  // === FEES ===
  borrowFee: string,                    // Borrow fee as decimal string
                                        // e.g., "0" = 0%

  // === CAPACITY LIMITS ===
  allowedDepositAmount: string,         // Remaining deposit capacity (human-readable)
                                        // e.g., "178901995.514468558"
  allowedBorrowAmount: string,          // Remaining borrow capacity (human-readable)
                                        // e.g., "4990539.6657730406"

  // === TOKEN EXCHANGE RATE ===
  xtokenRatio: string                   // Exchange rate between xToken and underlying
                                        // e.g., "1.034595501448505754"
}
```

---

## Nested Object Structures

### SupplyApr

Supply-side APR breakdown:

```javascript
SupplyApr {
  interestApr: string,      // Base protocol interest APR as decimal
                            // e.g., "3.1484050843574424211" = 3.148%
  stakingApr: string,       // Staking yield component (for LSTs)
                            // e.g., "0" or "1.489264554935931351021456977699067661197729087788067938912439977"
  rewards: Array<Reward>    // Array of reward token APRs
}
```

### BorrowApr

Borrow-side APR breakdown:

```javascript
BorrowApr {
  interestApr: string,      // Base protocol interest APR as decimal
                            // e.g., "6.5736902207688158328" = 6.574%
  rewards: Array<Reward>    // Array of reward token APRs (reduce net cost)
}
```

### Reward

Individual reward token APR:

```javascript
Reward {
  coinType: string,         // Full coin type of reward token
                            // e.g., "0xd1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI"
  rewardApr: string         // Reward APR as decimal string
                            // e.g., "0.66255763729692384292" = 0.663%
}
```

---

## Example Market Object

Complete example of a market object (SUI):

```json
{
  "marketId": "1",
  "price": "1.43987501",
  "coinType": "0x2::sui::SUI",
  "decimalDigit": 9,
  "totalSupply": "21098004.485531442",
  "totalBorrow": "11887863.922652113",
  "utilizationRate": "0.56345916178018421424",
  "supplyApr": {
    "interestApr": "3.1484050843574424211",
    "stakingApr": "0",
    "rewards": [
      {
        "coinType": "0xd1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI",
        "rewardApr": "0.66255763729692384292"
      }
    ]
  },
  "borrowApr": {
    "interestApr": "6.5736902207688158328",
    "rewards": [
      {
        "coinType": "0xd1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI",
        "rewardApr": "4.3973825133202054189"
      }
    ]
  },
  "ltv": "85",
  "availableLiquidity": "9210140.562879329",
  "borrowFee": "0",
  "borrowWeight": "1",
  "liquidationThreshold": "90",
  "allowedDepositAmount": "178901995.514468558",
  "allowedBorrowAmount": "4990539.6657730406",
  "xtokenRatio": "1.034595501448505754"
}
```

---

## Important Notes

### Numeric Formats

All numeric values are returned as **strings** to preserve precision. Key formats:

| Field Pattern | Format | Example | Interpretation |
|---------------|--------|---------|----------------|
| `price` | Decimal string | `"1.43987501"` | USD price |
| `totalSupply`, `totalBorrow` | Human-readable | `"21098004.485531442"` | Already divided by 10^decimals |
| `availableLiquidity` | Human-readable | `"9210140.562879329"` | Already divided by 10^decimals |
| `utilizationRate` | Decimal string | `"0.56345916178018421424"` | 0.563 = 56.3% |
| `interestApr`, `rewardApr` | Decimal string | `"3.1484050843574424211"` | 3.148 = 3.148% APR |
| `ltv`, `liquidationThreshold` | Percentage string | `"85"` | Already a percentage (85%) |
| `borrowWeight` | Multiplier string | `"1"`, `"1.5"`, `"2"` | Borrow weight multiplier |
| `borrowFee` | Decimal string | `"0"`, `"0.003"` | 0.003 = 0.3% |
| `xtokenRatio` | Exchange rate | `"1.034595501448505754"` | 1 xToken = 1.0346 underlying |

### APR Values

**IMPORTANT:** APR values in `supplyApr` and `borrowApr` are **already in percentage decimal form** (not basis points):

```javascript
// Example: interestApr = "3.1484050843574424211" means 3.148% APR
// To convert to decimal for calculations:
const aprDecimal = parseFloat(market.supplyApr.interestApr) / 100;
// 3.1484 / 100 = 0.031484 (decimal form for calculations)
```

### Borrow Weight

The `borrowWeight` field affects the actual borrow power:

- `"1"` = Normal borrow weight (1x)
- `"1.1"` = 10% penalty (reduce borrow power)
- `"1.5"` = 50% penalty (risky assets)
- `"2"` = 100% penalty (high-risk assets)

**Effective Borrow Value** = Borrow Amount × Borrow Weight × Price

### Staking APR (LSTs)

For liquid staking tokens (LSTs) like stSUI or haSUI, the `supplyApr.stakingApr` field contains the underlying staking yield. This can be a very long decimal string with many digits.

### Net Borrow Cost

Borrow rewards **reduce** the effective borrow cost:

```javascript
const borrowCost = parseFloat(market.borrowApr.interestApr);
const borrowRewards = market.borrowApr.rewards.reduce(
  (sum, r) => sum + parseFloat(r.rewardApr),
  0
);
const netBorrowCost = borrowCost - borrowRewards;
// Can be negative if rewards exceed cost!
```

### Token Amounts

All token amounts (`totalSupply`, `totalBorrow`, `availableLiquidity`) are **already in human-readable form**:

```javascript
// These are already divided by 10^decimalDigit
const totalSupply = parseFloat(market.totalSupply);  // No further conversion needed
const totalBorrow = parseFloat(market.totalBorrow);  // No further conversion needed
```

### xToken Exchange Rate

The `xtokenRatio` represents the exchange rate between the protocol's xToken (receipt token) and the underlying asset:

```javascript
// Example: xtokenRatio = "1.034595501448505754"
// This means: 1 xToken = 1.0346 underlying tokens
// Growing over time as interest accrues
```

---

## Field Reference Table

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `marketId` | string | Market/pool identifier |
| `coinType` | string | Full coin type with 0x prefix |
| `decimalDigit` | number | Token decimal places |
| `price` | string | USD price |

### Supply/Borrow Metrics

| Field | Type | Description |
|-------|------|-------------|
| `totalSupply` | string | Total supplied (human-readable) |
| `totalBorrow` | string | Total borrowed (human-readable) |
| `availableLiquidity` | string | Available to borrow (human-readable) |
| `utilizationRate` | string | Utilization as decimal (0.5 = 50%) |

### APR Fields

| Field | Type | Description |
|-------|------|-------------|
| `supplyApr.interestApr` | string | Base supply APR (as decimal percentage) |
| `supplyApr.stakingApr` | string | LST staking APR (as decimal percentage) |
| `supplyApr.rewards[]` | array | Reward token APRs |
| `borrowApr.interestApr` | string | Base borrow APR (as decimal percentage) |
| `borrowApr.rewards[]` | array | Reward token APRs (reduce cost) |

### Collateral Fields

| Field | Type | Description |
|-------|------|-------------|
| `ltv` | string | Loan-to-Value as percentage (85 = 85%) |
| `liquidationThreshold` | string | Liquidation threshold as percentage (90 = 90%) |
| `borrowWeight` | string | Borrow weight multiplier (1, 1.5, 2) |

### Capacity Fields

| Field | Type | Description |
|-------|------|-------------|
| `allowedDepositAmount` | string | Remaining deposit capacity (human-readable) |
| `allowedBorrowAmount` | string | Remaining borrow capacity (human-readable) |

---

## Conversion Helpers

### Python (used in alphafi_reader.py)

```python
def parse_apr(apr_str: str) -> float:
    """Convert APR decimal percentage string to decimal (e.g., "3.148" -> 0.03148)"""
    try:
        return float(apr_str) / 100.0
    except (TypeError, ValueError):
        return 0.0

def parse_utilization(util_str: str) -> float:
    """Convert utilization decimal string to decimal (e.g., "0.563" -> 0.563)"""
    try:
        return float(util_str)
    except (TypeError, ValueError):
        return 0.0

def parse_percentage(pct_str: str) -> float:
    """Convert percentage string to decimal (e.g., "85" -> 0.85)"""
    try:
        return float(pct_str) / 100.0
    except (TypeError, ValueError):
        return 0.0

def parse_human_amount(amount_str: str) -> float:
    """Convert human-readable amount string to float"""
    try:
        return float(amount_str)
    except (TypeError, ValueError):
        return 0.0

# Example usage:
market = api_response[0]

# Get token info
market_id = market['marketId']                # "1"
coin_type = market['coinType']                # "0x2::sui::SUI"
decimals = market['decimalDigit']             # 9

# Get price
price = float(market['price'])                # 1.43987501

# Get collateral params
ltv = parse_percentage(market['ltv'])                              # 0.85
liq_threshold = parse_percentage(market['liquidationThreshold'])   # 0.90
borrow_weight = float(market['borrowWeight'])                      # 1.0

# Get APRs (convert from percentage decimals to decimals)
supply_base_apr = parse_apr(market['supplyApr']['interestApr'])
supply_staking_apr = parse_apr(market['supplyApr']['stakingApr'])
supply_reward_apr = sum(
    parse_apr(r['rewardApr'])
    for r in market['supplyApr']['rewards']
)
total_supply_apr = supply_base_apr + supply_staking_apr + supply_reward_apr

borrow_base_apr = parse_apr(market['borrowApr']['interestApr'])
borrow_reward_apr = sum(
    parse_apr(r['rewardApr'])
    for r in market['borrowApr']['rewards']
)
net_borrow_apr = borrow_base_apr - borrow_reward_apr  # Rewards reduce cost

# Get amounts (already human-readable)
total_supply = parse_human_amount(market['totalSupply'])
total_borrow = parse_human_amount(market['totalBorrow'])
available_liquidity = parse_human_amount(market['availableLiquidity'])

# Get utilization
utilization = parse_utilization(market['utilizationRate'])

# Calculate USD values
total_supply_usd = total_supply * price
total_borrow_usd = total_borrow * price
available_liquidity_usd = available_liquidity * price

# Get exchange rate
xtoken_ratio = float(market['xtokenRatio'])  # 1.0346
```

### JavaScript

```javascript
function parseApr(aprStr) {
  try {
    return parseFloat(aprStr) / 100.0;
  } catch {
    return 0.0;
  }
}

function parsePercentage(pctStr) {
  try {
    return parseFloat(pctStr) / 100.0;
  } catch {
    return 0.0;
  }
}

function parseHumanAmount(amountStr) {
  try {
    return parseFloat(amountStr);
  } catch {
    return 0.0;
  }
}

// Example usage:
const market = apiResponse[0];

const ltv = parsePercentage(market.ltv);  // 0.85
const supplyApr = parseApr(market.supplyApr.interestApr);  // 0.03148
const totalSupply = parseHumanAmount(market.totalSupply);  // 21098004.485531442
const price = parseFloat(market.price);  // 1.43987501

// Calculate total supply APR including rewards
const totalSupplyApr = parseApr(market.supplyApr.interestApr) +
  parseApr(market.supplyApr.stakingApr) +
  market.supplyApr.rewards.reduce((sum, r) => sum + parseApr(r.rewardApr), 0);

// Calculate net borrow APR (after rewards)
const netBorrowApr = parseApr(market.borrowApr.interestApr) -
  market.borrowApr.rewards.reduce((sum, r) => sum + parseApr(r.rewardApr), 0);
```

---

## Comparison: AlphaFi vs Suilend vs Navi

| Aspect | AlphaFi (WebSocket) | Suilend (SDK) | Navi (REST API) |
|--------|---------------------|---------------|-----------------|
| Access Method | WebSocket via SDK | JavaScript SDK | HTTP GET request |
| Price Format | String | BigNumber | token.price (number) + oracle.price (string) |
| APR Format | Decimal percentage strings (e.g., "3.148") | Computed BigNumber (%) | Percentage strings (e.g., "0.019") |
| Token Amounts | Human-readable strings | BigNumber (human-readable) | String (raw or human-readable) |
| LTV Field | `ltv` (percentage string "85") | `config.openLtvPct` (number) | `ltv` (scaled by 1e27) |
| Borrow Weight | `borrowWeight` (string "1", "1.5", "2") | `config.borrowWeightBps` (BigNumber) | Not exposed |
| Rewards | Embedded in APR objects | Separate PoolRewardManager | Embedded in IncentiveApyInfo |
| Utilization | `utilizationRate` (decimal string) | `utilizationPercent` (BigNumber) | Calculated from amounts |

---

## Additional Notes

### Market ID

The `marketId` field is a simple numeric string identifier (e.g., "1", "2", "4") used to reference specific markets. This is the primary key for the market.

### Empty Rewards Arrays

When there are no active rewards, the `rewards` array will be empty (`[]`). Always check array length before iterating.

### Deprecated or Paused Markets

Currently there's no explicit status field. Markets with zero liquidity or extreme parameters may indicate deprecation. Consider filtering based on:
- Very low `totalSupply` or `totalBorrow`
- `allowedDepositAmount` or `allowedBorrowAmount` near zero

### Precision Considerations

Some fields like `stakingApr` can have extremely high precision (50+ decimal places). Use appropriate parsing methods to handle these without losing precision if needed, or round to a reasonable number of decimal places for display.

---

## SDK Connection Example

The AlphaFi SDK uses a WebSocket connection to fetch market data:

```javascript
// Example Node.js SDK usage (conceptual)
const sdk = new AlphaFiSDK();
const markets = await sdk.getMarkets();
// Returns array of market objects as documented above
```

Response:
```json
[
  { "marketId": "1", "coinType": "0x2::sui::SUI", ... },
  { "marketId": "2", "coinType": "0xd1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI", ... },
  // ...
]
```
