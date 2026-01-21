# Scallop SDK Output Reference

This document contains a sample raw pool data object returned by the Scallop SDK for reference.

## Sample Pool Data (SUI Token)

```json
{
  "coinName": "sui",
  "symbol": "SUI",
  "marketCoinType": "0xefe8b36d5b2e43728cc323298626b83177803521d195cfb11e15b910e892fddf::reserve::MarketCoin<0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI>",
  "sCoinType": "0xaafc4f740de0dd0dde642a31148fb94517087052f19afb0f7bed1dc41a50c77b::scallop_sui::SCALLOP_SUI",
  "coinPrice": 1.50204657,
  "coinType": "0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI",
  "maxBorrowRate": 0.47564687952399254,
  "borrowRate": 0.02619640645571053,
  "borrowRateScale": 10000000,
  "borrowIndex": 1203352390.7504196,
  "lastUpdated": 1769005507,
  "cashAmount": 3170622350310250,
  "debtAmount": 3394532067983490,
  "marketCoinSupplyAmount": 5959865815872766,
  "reserveAmount": 59824386533725.45,
  "reserveFactor": 0.19999999995343387,
  "borrowWeight": 1,
  "borrowFee": 0.0029999997932463884,
  "baseBorrowRate": 0.015854895813390613,
  "borrowRateOnHighKink": 0.09512937581166625,
  "borrowRateOnMidKink": 0.03170979185961187,
  "highKink": 0.8999999999068677,
  "midKink": 0.7999999998137355,
  "minBorrowAmount": 10000000,
  "isIsolated": false,
  "supplyLimit": 100000000000000000,
  "borrowLimit": 100000000000000000,
  "baseBorrowApr": 0.04999999943710864,
  "baseBorrowApy": 0.05126749587580526,
  "borrowAprOnHighKink": 0.29999999955967066,
  "borrowApyOnHighKink": 0.3496924874138596,
  "borrowAprOnMidKink": 0.09999999960847199,
  "borrowApyOnMidKink": 0.10515578118364433,
  "coinDecimal": 9,
  "maxBorrowApr": 1.499999999266863,
  "maxBorrowApy": 3.4679345206049215,
  "borrowApr": 0.08261298739872873,
  "borrowApy": 0.08611123176519198,
  "growthInterest": 1.6765700131655e-7,
  "supplyAmount": 6505330600877082,
  "supplyCoin": 6505330.600877082,
  "borrowAmount": 3394532637100557.5,
  "borrowCoin": 3394532.6371005573,
  "reserveCoin": 59824.386533725454,
  "utilizationRate": 0.5218078596409672,
  "supplyApr": 0.03448648490846885,
  "supplyApy": 0.03508635271181837,
  "conversionRate": 1.0915229976405831,
  "maxSupplyCoin": 100000000,
  "maxBorrowCoin": 100000000
}
```

## Key Fields Used in Our Reader

### Filtering
- **`borrowLimit`**: Used to filter out deprecated assets (skip if = 0)
- **`supplyLimit`**: Supply cap for the pool

### Rates (All as decimals, e.g., 0.05 = 5%)
- **`supplyApr`**: Base supply APR from vault interest
- **`borrowApr`**: Base borrow APR from vault interest
- **Reward APRs**: Fetched separately from `borrowIncentivePools` and `stakeRewardPools`

### Liquidity
- **`supplyCoin`**: Total supplied (human-readable units)
- **`borrowCoin`**: Total borrowed (human-readable units)
- **`utilizationRate`**: Borrow utilization (decimal)

### Collateral
- **Collateral factors**: Fetched from separate `collaterals` object
- **`isIsolated`**: Whether the market is isolated

### Fees
- **`borrowFee`**: Borrow fee (decimal)

### Price
- **`coinPrice`**: USD price of the token

## Notes

- All APR/APY values are returned as decimals (not percentages)
- Amounts in raw units need to be divided by `10^coinDecimal`
- The `supplyCoin` and `borrowCoin` fields are already in human-readable units
- Deprecated assets have `borrowLimit = 0` and should be filtered out
