# Pebble API Output Reference

This document contains sample raw API responses from Pebble Finance for reference.

## Endpoint 1: Market List

**URL:** `https://devapi.pebble-finance.com/market/getMarketList`

**Parameters:**
- `marketType`: One of `MainMarket`, `XSuiMarket`, or `AltCoinMarket`
- `page`: Page number (default: 1)
- `size`: Results per page (default: 100)

**Example:** `https://devapi.pebble-finance.com/market/getMarketList?marketType=MainMarket&page=1&size=100`

## Sample Response Structure

```json
{
  "code": 0,
  "message": "successful",
  "data": {
    "content": [
      {
        "id": 3,
        "marketType": "0ecae6de3e13c04e3168806456b356b87a3a33ce11a7cdd8e265e1113316c6b2::market_type::MainMarket",
        "marketID": "0x9e32dd342898a7dbb503f6ba45c05296b8991dec0963af649fe316d216f56150",
        "token": "0000000000000000000000000000000000000000000000000000000000000002::sui::SUI",
        "name": "MainMarket",
        "liqPenalty": "8.00%",
        "borrowFactor": 1.1,
        "borrowWeight": 1.1,
        "avgSupplyAPY30D": 0.000460658142,
        "avgSupplyAPY90D": 0.006138573391,
        "avgSupplyAPY180D": 0.006138573391,
        "avgBorrowAPY30D": 0.012321512948,
        "avgBorrowAPY90D": 0.022234955234,
        "avgBorrowAPY180D": 0.022234955234,
        "offTime": 0,
        "repayFeeRate": "0.15",
        "tokenInfo": {
          "id": 3,
          "address": "0000000000000000000000000000000000000000000000000000000000000002::sui::SUI",
          "name": "Sui",
          "description": "",
          "price": "1.42790353",
          "symbol": "SUI",
          "symbolK": "SUI",
          "decimals": "9",
          "icon": "https://dev.pebble-finance.com/assets/sui-tBUkZ_hC.png",
          "pythID": "0x23d7315113f5b1d3ba7a83604c44b94d79f4fd69af77f804fc7f920a6dc65744"
        },
        "previousData": null,
        "tokenPrice": null,
        "totalSupply": 12498917915007,
        "totalBorrow": 769199302345,
        "liqLTV": 0.81,
        "maxLTV": 0.8,
        "supplyAPY": 0.000737988883610096,
        "borrowAPY": 0.014202666837096,
        "liqAvailable": 11729718612662,
        "utilization": 0.061541271618566,
        "apy": 0,
        "borrowCap": 90000000000000,
        "supplyCap": 100000000000000,
        "toBeOffShelf": false
      },
      {
        "id": 2,
        "marketType": "0ecae6de3e13c04e3168806456b356b87a3a33ce11a7cdd8e265e1113316c6b2::market_type::MainMarket",
        "marketID": "0x9e32dd342898a7dbb503f6ba45c05296b8991dec0963af649fe316d216f56150",
        "token": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
        "name": "MainMarket",
        "liqPenalty": "7.00%",
        "borrowFactor": 1,
        "borrowWeight": 1,
        "avgSupplyAPY30D": 0.01249146212,
        "avgSupplyAPY90D": 0.00972344878,
        "avgSupplyAPY180D": 0.00972344878,
        "avgBorrowAPY30D": 0.040457809093,
        "avgBorrowAPY90D": 0.035373260511,
        "avgBorrowAPY180D": 0.035373260511,
        "offTime": 0,
        "repayFeeRate": "0.12",
        "tokenInfo": {
          "id": 2,
          "address": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
          "name": "USDC",
          "description": "USDC is a US dollar-backed stablecoin issued by Circle.",
          "price": "0.99974043",
          "symbol": "USDC",
          "symbolK": "USDC",
          "decimals": "6",
          "icon": "https://circle.com/usdc-icon",
          "pythID": "0xeaa020c61cc479712813461ce153894a96a6c00b21ed0cfc2798d1f9a9e9c94a"
        },
        "previousData": null,
        "tokenPrice": null,
        "totalSupply": 8564251258,
        "totalBorrow": 3983537286,
        "liqLTV": 0.91,
        "maxLTV": 0.9,
        "supplyAPY": 0.0245484884630371,
        "borrowAPY": 0.0610400865956591,
        "liqAvailable": 4580713972,
        "utilization": 0.465135499404198,
        "apy": 0,
        "borrowCap": 370000000000,
        "supplyCap": 400000000000,
        "toBeOffShelf": false
      }
    ],
    "pageable": {
      "sort": {
        "sorted": true,
        "unsorted": false,
        "empty": false
      },
      "pageNumber": 0,
      "pageSize": 10,
      "offset": 0,
      "paged": true,
      "unpaged": false
    },
    "totalPages": 1,
    "totalElements": 3,
    "last": true,
    "size": 10,
    "number": 0,
    "sort": {
      "sorted": true,
      "unsorted": false,
      "empty": false
    },
    "numberOfElements": 3,
    "first": true,
    "empty": false
  }
}
```

## Key Fields Used in PebbleReader

### Response Structure
- **`code`**: Response code (0 = success)
- **`message`**: Response message
- **`data.content`**: Array of market/pool objects

### Filtering
- **`toBeOffShelf`**: Skip if `true` (marked for removal)

### Token Information
- **`token`**: Token contract address (Sui coin type)
- **`tokenInfo.symbol`**: Token symbol (e.g., "SUI", "USDC")
- **`tokenInfo.decimals`**: Token decimals (string, e.g., "9")
- **`tokenInfo.price`**: USD price (string, e.g., "1.42790353")

### Market Information
- **`marketType`**: Full market type identifier (contract address)
- **`marketID`**: Market identifier
- **`name`**: Market name (e.g., "MainMarket")

### Rates (All as decimals, e.g., 0.05 = 5%)
- **`supplyAPY`**: Base supply APY (already in decimal format)
- **`borrowAPY`**: Base borrow APY (already in decimal format)
- **Note:** Pebble calls these "APY" but they appear to be base rates without compounding

### Liquidity (Raw token amounts - must divide by 10^decimals)
- **`totalSupply`**: Total supplied (raw units)
- **`totalBorrow`**: Total borrowed (raw units)
- **`liqAvailable`**: Available to borrow (raw units)
- **`utilization`**: Borrow utilization (decimal, e.g., 0.061541 = 6.15%)

### Collateral
- **`maxLTV`**: Maximum loan-to-value ratio (decimal, e.g., 0.8 = 80%)
- **`liqLTV`**: Liquidation LTV threshold (decimal, e.g., 0.81 = 81%)

### Fees
- **`repayFeeRate`**: Repayment fee rate (string percentage, e.g., "0.15")
- **`liqPenalty`**: Liquidation penalty (string percentage, e.g., "8.00%")
- **`borrowFactor`**: Borrow factor multiplier (float)
- **`borrowWeight`**: Borrow weight multiplier (float)

### Caps
- **`borrowCap`**: Maximum borrow amount (raw units)
- **`supplyCap`**: Maximum supply amount (raw units)

### Historical Averages
- **`avgSupplyAPY30D`**: 30-day average supply APY
- **`avgSupplyAPY90D`**: 90-day average supply APY
- **`avgSupplyAPY180D`**: 180-day average supply APY
- **`avgBorrowAPY30D`**: 30-day average borrow APY
- **`avgBorrowAPY90D`**: 90-day average borrow APY
- **`avgBorrowAPY180D`**: 180-day average borrow APY

## Data Format Notes

### Rates
- All APY values are returned as decimals (0.05 = 5%), NOT percentages
- No separate base/reward APR breakdown in this endpoint
- Reward APRs must be fetched from separate rewards endpoint (see below)

### Amounts
- `totalSupply`, `totalBorrow`, `liqAvailable` are in raw units
- Must divide by `10^tokenInfo.decimals` to get human-readable amounts
- Example: `totalSupply=12498917915007` with `decimals=9` → 12498.917915007 SUI

### Prices
- `tokenInfo.price` is a string, must convert to float
- Already in USD (no conversion needed)

### Status
- `toBeOffShelf=true` indicates pool is deprecated and should be filtered out
- `offTime=0` indicates pool is active

### Market Types
The API supports three market types (must query separately):
1. **MainMarket**: Primary lending market
2. **XSuiMarket**: xSUI-specific market
3. **AltCoinMarket**: Alternative token market

## Comparison with Pebble Reader Implementation

### What the reader does:
1. Fetches all three market types separately
2. Filters out deprecated pools (`toBeOffShelf=true`)
3. Converts raw amounts to human-readable units
4. Converts string prices to floats
5. Calculates USD values from token amounts and prices
6. Fetches reward APRs separately (from rewards endpoint)
7. Calculates total APRs (base + reward for supply, base - reward for borrow)

### Borrow Fees
**Note:** This endpoint does NOT provide upfront borrow fees. The reader currently:
- Has no borrow fee data from this endpoint
- May need to add borrow fees from contract data or set to 0.0
- See `data/navi/navi_fees.py` for example of hardcoded fee mapping

---

## Endpoint 2: Market Rewards Configuration

**URL:** `https://devapi.pebble-finance.com/pebbleWeb3Config/getAllMarketConfig`

**Parameters:** None

**Purpose:** Fetch reward APR information for all tokens across all markets

## Sample Response Structure

```json
{
  "code": 0,
  "message": "successful",
  "data": [
    {
      "id": 1,
      "marketType": "0ecae6de3e13c04e3168806456b356b87a3a33ce11a7cdd8e265e1113316c6b2::market_type::MainMarket",
      "marketID": "0x9e32dd342898a7dbb503f6ba45c05296b8991dec0963af649fe316d216f56150",
      "name": "MainMarket",
      "maxLTV": 0.8,
      "warnLTV": 0.75,
      "summaries": [
        {
          "rewards": [
            {
              "apr": 0.47487996792,
              "endTimeMs": 1769666400000,
              "startTimeMs": 1768456800000,
              "totalRewards": "20000000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "18606611",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 1,
          "reserveCoinType": "0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"
        },
        {
          "rewards": [
            {
              "apr": 0.030518743248,
              "endTimeMs": 1769666400000,
              "startTimeMs": 1768456800000,
              "totalRewards": "10000000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "9419599",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 0,
          "reserveCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC"
        },
        {
          "rewards": [
            {
              "apr": 0.000018196272,
              "endTimeMs": 1772758252000,
              "startTimeMs": 1763039890785,
              "totalRewards": "100000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "67451",
              "cumulativeRewardsPerShare": "0"
            },
            {
              "apr": 0,
              "endTimeMs": 1772758252000,
              "startTimeMs": 1763039895273,
              "totalRewards": "100000",
              "rewardCoinType": "0000000000000000000000000000000000000000000000000000000000000002::sui::SUI",
              "allocatedRewards": "67451",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 0,
          "reserveCoinType": "0000000000000000000000000000000000000000000000000000000000000002::sui::SUI"
        }
      ]
    },
    {
      "id": 2,
      "marketType": "0ecae6de3e13c04e3168806456b356b87a3a33ce11a7cdd8e265e1113316c6b2::market_type::XSuiMarket",
      "marketID": "0x3b1873c79446884a379adc12c051887c34b94ebd8776231b09351fe8c83845e2",
      "name": "XSuiMarket",
      "maxLTV": 0.8,
      "warnLTV": 0.75,
      "summaries": [
        {
          "rewards": [
            {
              "apr": 0.171927933264,
              "endTimeMs": 1769666400000,
              "startTimeMs": 1768456800000,
              "totalRewards": "120000000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "108340123",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 0,
          "reserveCoinType": "d1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI"
        }
      ]
    },
    {
      "id": 3,
      "marketType": "0ecae6de3e13c04e3168806456b356b87a3a33ce11a7cdd8e265e1113316c6b2::market_type::AltCoinMarket",
      "marketID": "0x8a6b07774b1302c7a90894208846a68a94acba246ccb521422a9ed013e708f99",
      "name": "AltCoinMarket",
      "maxLTV": 0.8,
      "warnLTV": 0.75,
      "summaries": [
        {
          "rewards": [
            {
              "apr": 0.28542319056,
              "endTimeMs": 1769666400000,
              "startTimeMs": 1768456800000,
              "totalRewards": "10000000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "5786908",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 0,
          "reserveCoinType": "356a26eb9e012a68958082340d4c4116e7f55615cf27affcff209cf0ae544f59::wal::WAL"
        },
        {
          "rewards": [
            {
              "apr": 1.048770582192,
              "endTimeMs": 1769666400000,
              "startTimeMs": 1768456800000,
              "totalRewards": "5000000",
              "rewardCoinType": "dba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC",
              "allocatedRewards": "4641609",
              "cumulativeRewardsPerShare": "0"
            }
          ],
          "rewardType": 1,
          "reserveCoinType": "deeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP"
        }
      ]
    }
  ]
}
```

## Key Fields for Rewards Endpoint

### Response Structure
- **`code`**: Response code (0 = success)
- **`message`**: Response message
- **`data`**: Array of market configurations (one per market type)

### Market Configuration
- **`marketType`**: Full market type identifier (matches Endpoint 1)
- **`marketID`**: Market identifier
- **`name`**: Market name (e.g., "MainMarket", "XSuiMarket", "AltCoinMarket")
- **`maxLTV`**: Maximum loan-to-value ratio (decimal)
- **`warnLTV`**: Warning LTV threshold (decimal)

### Summaries Array
Each summary represents rewards for a specific token:

- **`reserveCoinType`**: Token contract address this reward applies to
- **`rewardType`**: Integer indicating reward category
  - `0` = Supply rewards (lenders receive these)
  - `1` = Borrow rewards (borrowers receive these)
- **`rewards`**: Array of active reward programs for this token

### Reward Program Details
Each reward program contains:

- **`apr`**: Reward APR (decimal, e.g., 0.47487996792 = 47.49%)
- **`rewardCoinType`**: Token contract address of the reward token (e.g., USDC)
- **`totalRewards`**: Total rewards allocated (string, raw units)
- **`allocatedRewards`**: Already allocated rewards (string, raw units)
- **`startTimeMs`**: Program start time (Unix milliseconds)
- **`endTimeMs`**: Program end time (Unix milliseconds)
- **`cumulativeRewardsPerShare`**: Internal accounting (string)

## How Rewards Are Used in PebbleReader

### Reward Aggregation
The reader builds a mapping: `(marketType, reserveCoinType) → {supply_reward_apr, borrow_reward_apr}`

**Process:**
1. Iterate through all markets in the response
2. For each summary, extract `reserveCoinType` and `rewardType`
3. Sum all `apr` values within each `rewards` array
4. Store in mapping based on `rewardType`:
   - `rewardType=0` → Add to `supply_reward_apr`
   - `rewardType=1` → Add to `borrow_reward_apr`

**Example:** SUI token in MainMarket
```python
# Summary 1: rewardType=1 (borrow), apr=0.47487996792
# Summary 2: rewardType=0 (supply), apr=0.000018196272
# Summary 2 has multiple rewards, sum them all

supply_reward_apr = 0.000018196272 + 0  # Two reward programs
borrow_reward_apr = 0.47487996792        # One reward program
```

### Multiple Reward Programs
**Important:** A token can have multiple reward programs for the same side (supply or borrow)

Example: SUI supply rewards in MainMarket
```json
{
  "rewardType": 0,
  "reserveCoinType": "0x2::sui::SUI",
  "rewards": [
    {"apr": 0.000018196272, "rewardCoinType": "USDC"},
    {"apr": 0, "rewardCoinType": "SUI"}
  ]
}
```

**Reader must sum all APRs:**
```python
total_supply_reward = 0.000018196272 + 0 = 0.000018196272
```

### Final APR Calculation
After fetching both endpoints:

**Supply (Lending):**
```python
supply_total_apr = supply_base_apr + supply_reward_apr
# From Endpoint 1     # From Endpoint 2
```

**Borrow:**
```python
borrow_total_apr = borrow_base_apr - borrow_reward_apr
# From Endpoint 1     # From Endpoint 2
# Subtract because rewards reduce borrowing cost
```

## Data Format Notes

### Reward APRs
- Already in decimal format (0.47487996792 = 47.49%)
- Can be very small (0.000018196272 = 0.0018%)
- Can be 0 (expired or inactive program)

### Matching with Endpoint 1
Rewards must be matched using:
1. **`marketType`** - Full contract path must match
2. **`reserveCoinType`** - Token contract address must match

**Example matching:**
```python
# From Endpoint 1 (market list):
market = {
    "marketType": "...::market_type::MainMarket",
    "token": "0x2::sui::SUI",
    # ... base rates ...
}

# From Endpoint 2 (rewards):
reward = {
    "marketType": "...::market_type::MainMarket",  # ✓ Match
    "reserveCoinType": "0x2::sui::SUI",           # ✓ Match
    "rewardType": 0,                              # Supply side
    "rewards": [{"apr": 0.000018196272}]
}
```

### Time Validation
The reader currently does NOT validate `startTimeMs`/`endTimeMs`:
- Expired rewards (current time > endTimeMs) are still included
- Future rewards (current time < startTimeMs) are still included
- This could be improved by filtering based on current timestamp

## Implementation Example

```python
def _fetch_rewards_data(self) -> Dict[Tuple[str, str], Dict[str, float]]:
    """
    Fetch rewards data from Pebble API.
    
    Returns:
        Dictionary mapping (market_type, token) -> {supply_reward_apr, borrow_reward_apr}
    """
    response = self.session.get(self.REWARDS_URL, timeout=10)
    data = response.json()
    
    rewards_map = {}
    
    for market in data.get("data", []):
        market_type = market.get("marketType", "")
        
        for summary in market.get("summaries", []):
            token = summary.get("reserveCoinType", "")
            reward_type = summary.get("rewardType")  # 0 = supply, 1 = borrow
            
            # Sum up all reward APRs for this token/type
            total_apr = 0.0
            for reward in summary.get("rewards", []):
                try:
                    total_apr += float(reward.get("apr", 0))
                except (TypeError, ValueError):
                    pass
            
            # Create key combining market and token
            key = (market_type, token)
            if key not in rewards_map:
                rewards_map[key] = {"supply_reward_apr": 0.0, "borrow_reward_apr": 0.0}
            
            if reward_type == 0:  # Supply reward
                rewards_map[key]["supply_reward_apr"] += total_apr
            elif reward_type == 1:  # Borrow reward
                rewards_map[key]["borrow_reward_apr"] += total_apr
    
    return rewards_map
```

## Known Issues and Improvements

### Current Implementation
✅ Sums multiple reward programs correctly
✅ Handles missing reward data gracefully
✅ Separates supply vs borrow rewards

### Potential Improvements
⚠️ **Time validation**: Filter expired/future rewards
⚠️ **Reward token prices**: Could track reward token details
⚠️ **Attribution**: Could store which tokens provide rewards (USDC vs SUI)

---

## Complete Integration Flow

### Step 1: Fetch Market List (Endpoint 1)
```
GET /market/getMarketList?marketType=MainMarket
→ Returns base APRs, liquidity, collateral for each token
```

### Step 2: Fetch Rewards (Endpoint 2)
```
GET /pebbleWeb3Config/getAllMarketConfig
→ Returns reward APRs for each token
```

### Step 3: Merge Data
```python
for pool in market_list:
    token = pool["token"]
    market_type = pool["marketType"]
    
    # Get base rates from Endpoint 1
    supply_base_apr = pool["supplyAPY"]
    borrow_base_apr = pool["borrowAPY"]
    
    # Get reward rates from Endpoint 2
    rewards = rewards_map.get((market_type, token), {})
    supply_reward_apr = rewards.get("supply_reward_apr", 0.0)
    borrow_reward_apr = rewards.get("borrow_reward_apr", 0.0)
    
    # Calculate totals
    supply_total_apr = supply_base_apr + supply_reward_apr
    borrow_total_apr = borrow_base_apr - borrow_reward_apr  # Subtract!
```

### Step 4: Return Unified DataFrames
```python
return (lend_df, borrow_df, collateral_df)
# Each with Supply_apr/Borrow_apr including rewards
```
