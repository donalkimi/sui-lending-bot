# Suilend SDK Output Reference

This document describes the structure of both raw and parsed Reserve objects returned by the Suilend SDK.

## Table of Contents
1. [Raw Reserve Object](#raw-reserve-object-structure)
2. [Parsed Reserve Object](#parsed-reserve-object-structure)
3. [Nested Object Structures](#nested-object-structures)
4. [Example Usage](#example-usage)
5. [Important Notes](#important-notes)
6. [Conversion Helpers](#conversion-helpers)

## Raw Reserve Object Structure

```javascript
Reserve {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve::Reserve',
  '$isPhantom': [true],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve::Reserve<0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL>',
  '$typeArgs': ['0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::suilend::MAIN_POOL'],

  // Basic identifiers
  id: string,                    // Reserve object ID
  lendingMarketId: string,       // Parent lending market ID
  arrayIndex: bigint,            // Index in the lending market reserves array
  coinType: TypeName,            // TypeName object containing the coin type
  mintDecimals: number,          // Decimal places for the coin

  // Configuration
  config: Cell<ReserveConfig>,   // Reserve configuration wrapped in Cell

  // Pricing
  priceIdentifier: PriceIdentifier,  // Pyth price feed identifier
  price: Decimal,                     // Current price
  smoothedPrice: Decimal,             // Smoothed price (EMA)
  priceLastUpdateTimestampS: bigint,  // Last price update (seconds)

  // Liquidity
  availableAmount: bigint,            // Available liquidity (raw amount)
  ctokenSupply: bigint,               // Total cToken supply
  borrowedAmount: Decimal,            // Total borrowed amount

  // Interest rates
  cumulativeBorrowRate: Decimal,           // Cumulative borrow rate multiplier
  interestLastUpdateTimestampS: bigint,    // Last interest accrual (seconds)

  // Fees
  unclaimedSpreadFees: Decimal,       // Unclaimed protocol spread fees

  // Attributed borrowing
  attributedBorrowValue: Decimal,     // Attributed borrow value (USD)

  // Rewards
  depositsPoolRewardManager: PoolRewardManager,  // Deposit rewards manager
  borrowsPoolRewardManager: PoolRewardManager    // Borrow rewards manager
}
```

---

## Parsed Reserve Object Structure

The parsed reserve object is a simplified, user-friendly version with computed fields and BigNumber objects instead of raw bigints.

```javascript
{
  // Type information
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve::Reserve',

  // Basic identifiers
  id: string,                    // Reserve object ID
  arrayIndex: bigint,            // Index in the lending market reserves array
  coinType: string,              // Coin type as a string (e.g., '0x...::sui::SUI')
  mintDecimals: number,          // Decimal places for the coin

  // Configuration (simplified)
  config: {
    '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve_config::ReserveConfig',

    // LTV parameters
    openLtvPct: number,
    closeLtvPct: number,
    maxCloseLtvPct: number,

    // Weights and limits (as BigNumber)
    borrowWeightBps: BigNumber,
    depositLimit: BigNumber,
    borrowLimit: BigNumber,
    depositLimitUsd: BigNumber,
    borrowLimitUsd: BigNumber,

    // Liquidation
    liquidationBonusBps: number,
    maxLiquidationBonusBps: number,

    // Fees
    borrowFeeBps: number,
    spreadFeeBps: number,
    protocolLiquidationFeeBps: number,

    // Isolation and attributed borrowing
    isolated: boolean,
    openAttributedBorrowLimitUsd: number,
    closeAttributedBorrowLimitUsd: number,

    // Interest rate curve (parsed)
    interestRate: Array<{
      utilization: number,    // Utilization percentage
      apr: number            // APR percentage
    }>
  },

  // Pricing (as BigNumber)
  priceIdentifier: string,       // Pyth price feed ID (hex string)
  price: BigNumber,              // Current price
  smoothedPrice: BigNumber,      // Smoothed price (EMA)
  minPrice: BigNumber,           // Min of price and smoothedPrice
  maxPrice: BigNumber,           // Max of price and smoothedPrice
  priceLastUpdateTimestampS: bigint,

  // Liquidity (as BigNumber)
  availableAmount: BigNumber,         // Available liquidity
  ctokenSupply: BigNumber,            // Total cToken supply
  borrowedAmount: BigNumber,          // Total borrowed amount
  depositedAmount: BigNumber,         // Total deposited (available + borrowed)
  totalDeposits: BigNumber,           // Alias for depositedAmount

  // USD values (as BigNumber)
  availableAmountUsd: BigNumber,      // Available liquidity in USD
  borrowedAmountUsd: BigNumber,       // Total borrowed in USD
  depositedAmountUsd: BigNumber,      // Total deposited in USD

  // Interest rates and fees (as BigNumber)
  cumulativeBorrowRate: BigNumber,    // Cumulative borrow rate multiplier
  interestLastUpdateTimestampS: bigint,
  unclaimedSpreadFees: BigNumber,     // Unclaimed protocol spread fees

  // Attributed borrowing (as BigNumber)
  attributedBorrowValue: BigNumber,

  // Computed metrics (as BigNumber)
  cTokenExchangeRate: BigNumber,      // Exchange rate between cToken and underlying
  borrowAprPercent: BigNumber,        // Current borrow APR (%)
  depositAprPercent: BigNumber,       // Current deposit APR (%)
  utilizationPercent: BigNumber,      // Utilization rate (%)

  // Reward managers (simplified)
  depositsPoolRewardManager: {
    '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolRewardManager',
    id: string,
    totalShares: bigint,
    poolRewards: Array<Object>,      // Parsed pool rewards (non-null only)
    lastUpdateTimeMs: bigint
  },
  borrowsPoolRewardManager: {
    '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolRewardManager',
    id: string,
    totalShares: bigint,
    poolRewards: Array<Object>,      // Parsed pool rewards (non-null only)
    lastUpdateTimeMs: bigint
  },

  // Token metadata
  token: {
    coinType: string,
    symbol: string,
    name: string,
    iconUrl: string | null,
    description: string | null
  },

  // Token metadata aliases (top-level)
  symbol: string,
  name: string,
  iconUrl: string | null,
  description: string | null
}
```

## Nested Object Structures

### TypeName
```javascript
TypeName {
  __StructClass: true,
  '$typeName': '0x1::type_name::TypeName',
  '$isPhantom': [],
  '$fullTypeName': '0x1::type_name::TypeName',
  '$typeArgs': [],
  name: string  // Coin type (e.g., '0000000000000000000000000000000000000000000000000000000000000002::sui::SUI')
}
```

### Cell<ReserveConfig>
```javascript
Cell {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::cell::Cell',
  '$isPhantom': [false],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::cell::Cell<0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve_config::ReserveConfig>',
  '$typeArgs': ['0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve_config::ReserveConfig'],
  element: ReserveConfig
}
```

### ReserveConfig
```javascript
ReserveConfig {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve_config::ReserveConfig',
  '$isPhantom': [],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::reserve_config::ReserveConfig',
  '$typeArgs': [],

  // LTV parameters
  openLtvPct: number,              // Open position LTV percentage (0-100)
  closeLtvPct: number,             // Close position LTV percentage (0-100)
  maxCloseLtvPct: number,          // Maximum close LTV percentage (0-100)

  // Weights
  borrowWeightBps: bigint,         // Borrow weight in basis points

  // Limits
  depositLimit: bigint,            // Deposit limit (raw amount)
  borrowLimit: bigint,             // Borrow limit (raw amount)
  depositLimitUsd: bigint,         // Deposit limit in USD (scaled)
  borrowLimitUsd: bigint,          // Borrow limit in USD (scaled)

  // Liquidation
  liquidationBonusBps: bigint,     // Liquidation bonus in basis points
  maxLiquidationBonusBps: bigint,  // Maximum liquidation bonus in basis points

  // Interest rate curve
  interestRateUtils: Array,        // Utilization rate breakpoints
  interestRateAprs: Array,         // APR at each breakpoint

  // Fees
  borrowFeeBps: bigint,            // Borrow fee in basis points
  spreadFeeBps: bigint,            // Spread fee in basis points
  protocolLiquidationFeeBps: bigint, // Protocol liquidation fee in basis points

  // Isolation mode
  isolated: boolean,               // Whether reserve is isolated

  // Attributed borrowing limits
  openAttributedBorrowLimitUsd: bigint,   // Open attributed borrow limit (USD)
  closeAttributedBorrowLimitUsd: bigint,  // Close attributed borrow limit (USD)

  // Extensibility
  additionalFields: Bag            // Additional fields for future extensions
}
```

### PriceIdentifier
```javascript
PriceIdentifier {
  __StructClass: true,
  '$typeName': '0x8d97f1cd6ac663735be08d1d2b6d02a159e711586461306ce60a2b7a6a565a9e::price_identifier::PriceIdentifier',
  '$isPhantom': [],
  '$fullTypeName': '0x8d97f1cd6ac663735be08d1d2b6d02a159e711586461306ce60a2b7a6a565a9e::price_identifier::PriceIdentifier',
  '$typeArgs': [],
  bytes: Array<number>  // 32-byte array representing Pyth price feed ID
}
```

### Decimal
```javascript
Decimal {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::decimal::Decimal',
  '$isPhantom': [],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::decimal::Decimal',
  '$typeArgs': [],
  value: bigint  // Fixed-point decimal value (scaled by 10^18)
}
```

### PoolRewardManager
```javascript
PoolRewardManager {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolRewardManager',
  '$isPhantom': [],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolRewardManager',
  '$typeArgs': [],

  id: string,                     // Object ID
  totalShares: bigint,            // Total shares in the pool
  poolRewards: Array<PoolReward | null>,  // Array of pool rewards (sparse array)
  lastUpdateTimeMs: bigint        // Last update time (milliseconds)
}
```

### PoolReward
```javascript
PoolReward {
  __StructClass: true,
  '$typeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolReward',
  '$isPhantom': [],
  '$fullTypeName': '0xf95b06141ed4a174f239417323bde3f209b972f5930d8521ea38a52aff3a6ddf::liquidity_mining::PoolReward',
  '$typeArgs': [],

  coinType: TypeName,             // Reward coin type
  rewardsPerShare: bigint,        // Accumulated rewards per share
  totalRewards: bigint,           // Total rewards distributed
  allocatedRewards: bigint        // Allocated but not yet distributed rewards
}
```

## Example Usage

### Working with Raw Reserve Objects

```javascript
// Access basic fields
const reserveId = reserve.id;
const availableLiquidity = reserve.availableAmount;
const mintDecimals = reserve.mintDecimals;

// Access coin type
const coinType = reserve.coinType.name;  // e.g., '0000...::sui::SUI'

// Access configuration
const config = reserve.config.element;
const openLtv = config.openLtvPct;
const borrowLimit = config.borrowLimit;

// Access pricing
const currentPrice = reserve.price.value;  // bigint (scaled by 10^18)
const smoothedPrice = reserve.smoothedPrice.value;

// Access interest rates
const borrowedAmount = reserve.borrowedAmount.value;  // bigint (scaled by 10^18)
const cumulativeBorrowRate = reserve.cumulativeBorrowRate.value;

// Access rewards
const depositRewardsId = reserve.depositsPoolRewardManager.id;
const borrowRewardsId = reserve.borrowsPoolRewardManager.id;
const depositRewards = reserve.depositsPoolRewardManager.poolRewards.filter(r => r !== null);
```

### Working with Parsed Reserve Objects

```javascript
// Access basic fields (same as raw)
const reserveId = parsedReserve.id;
const symbol = parsedReserve.symbol;
const coinType = parsedReserve.coinType;  // Already a string

// Access configuration (simplified)
const config = parsedReserve.config;
const openLtv = config.openLtvPct;
const depositLimit = config.depositLimit.toNumber();  // BigNumber methods

// Access pricing (BigNumber objects)
const currentPrice = parsedReserve.price.toNumber();
const smoothedPrice = parsedReserve.smoothedPrice.toNumber();
const minPrice = parsedReserve.minPrice.toNumber();
const maxPrice = parsedReserve.maxPrice.toNumber();

// Access computed metrics
const borrowApr = parsedReserve.borrowAprPercent.toNumber();
const depositApr = parsedReserve.depositAprPercent.toNumber();
const utilization = parsedReserve.utilizationPercent.toNumber();
const exchangeRate = parsedReserve.cTokenExchangeRate.toNumber();

// Access USD values
const availableUsd = parsedReserve.availableAmountUsd.toNumber();
const borrowedUsd = parsedReserve.borrowedAmountUsd.toNumber();
const depositedUsd = parsedReserve.depositedAmountUsd.toNumber();

// Access liquidity amounts
const availableAmount = parsedReserve.availableAmount.toNumber();
const borrowedAmount = parsedReserve.borrowedAmount.toNumber();
const depositedAmount = parsedReserve.depositedAmount.toNumber();

// Access interest rate curve
config.interestRate.forEach(point => {
  console.log(`At ${point.utilization}% utilization: ${point.apr}% APR`);
});

// Access token metadata
const tokenInfo = parsedReserve.token;
console.log(`${tokenInfo.symbol} (${tokenInfo.name})`);

// Access rewards (already filtered to non-null)
const depositRewards = parsedReserve.depositsPoolRewardManager.poolRewards;
const borrowRewards = parsedReserve.borrowsPoolRewardManager.poolRewards;
```

## Important Notes

### Raw Reserve Objects

1. **Decimal Values**: All `Decimal` objects contain a `value` field that is a `bigint` scaled by 10^18
2. **Timestamps**: Timestamps ending in `S` are in seconds, ending in `Ms` are in milliseconds
3. **Basis Points**: Values ending in `Bps` are in basis points (1/100th of a percent, 10000 = 100%)
4. **Raw Amounts**: Token amounts without explicit scaling use the coin's `mintDecimals`
5. **Sparse Arrays**: `poolRewards` arrays contain `null` values for inactive reward slots
6. **Type Arguments**: The `$typeArgs` arrays contain type parameters for generic structs

### Parsed Reserve Objects

1. **BigNumber Objects**: Most numeric values are converted to BigNumber objects from the `bignumber.js` library
   - Use `.toNumber()` to convert to JavaScript number
   - Use `.toString()` for string representation
   - Use `.toFixed(decimals)` for formatted output
2. **Simplified Structure**: Nested objects are flattened where possible
   - `coinType` is a string, not a TypeName object
   - `config` element is directly accessible
   - `priceIdentifier` is a hex string, not a PriceIdentifier object
3. **Computed Fields**: Additional fields are computed for convenience
   - `minPrice` and `maxPrice`: Min/max of price and smoothedPrice
   - `depositedAmount`: Sum of available and borrowed amounts
   - `totalDeposits`: Alias for depositedAmount
   - `*Usd` fields: USD values for various amounts
   - `borrowAprPercent`, `depositAprPercent`: Current APRs
   - `utilizationPercent`: Current utilization rate
   - `cTokenExchangeRate`: Exchange rate between cToken and underlying
4. **Interest Rate Curve**: Parsed into an array of objects with `utilization` and `apr` fields
5. **Reward Arrays**: `poolRewards` arrays are filtered to remove `null` values
6. **Token Metadata**: Added at both top-level and in `token` object for convenience

## Conversion Helpers

### For Raw Reserve Objects

```javascript
// Convert Decimal to number
function decimalToNumber(decimal) {
  return Number(decimal.value) / 1e18;
}

// Convert raw amount to human-readable
function rawToHuman(rawAmount, decimals) {
  return Number(rawAmount) / Math.pow(10, decimals);
}

// Convert basis points to percentage
function bpsToPercent(bps) {
  return Number(bps) / 100;
}
```

### For Parsed Reserve Objects

```javascript
// BigNumber is already convenient to use
const price = parsedReserve.price.toNumber();
const priceFormatted = parsedReserve.price.toFixed(4);

// Convert token amounts (already in human-readable form)
const availableTokens = parsedReserve.availableAmount.toNumber();

// Access percentages (already calculated)
const borrowApr = parsedReserve.borrowAprPercent.toNumber();
const depositApr = parsedReserve.depositAprPercent.toNumber();
const utilization = parsedReserve.utilizationPercent.toNumber();
```

## Comparison: Raw vs Parsed

| Field | Raw Reserve | Parsed Reserve |
|-------|-------------|----------------|
| `coinType` | `TypeName` object with `.name` property | String (e.g., `'0x...::sui::SUI'`) |
| `config` | Wrapped in `Cell<ReserveConfig>`, access via `.element` | Direct access to config object |
| `price` | `Decimal` object with `.value` (bigint scaled by 10^18) | `BigNumber` object |
| `priceIdentifier` | `PriceIdentifier` object with `.bytes` array | Hex string |
| Numeric amounts | `bigint` or `Decimal` objects | `BigNumber` objects |
| `poolRewards` | Sparse array with `null` values | Filtered array (non-null only) |
| Computed fields | Not present | Includes APRs, USD values, utilization, etc. |
| Token metadata | Not present | Included as `token`, `symbol`, `name`, etc. |
| Interest rate curve | Raw arrays (`interestRateUtils`, `interestRateAprs`) | Parsed array of objects with `utilization` and `apr` |

**Recommendation**: Use **parsed reserves** for most application logic as they provide a cleaner API and computed metrics. Use **raw reserves** only when you need access to the original on-chain data structures.
