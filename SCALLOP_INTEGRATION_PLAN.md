# Scallop SDK Integration Plan

## Overview
Add Scallop protocol as a 4th lending protocol source alongside Navi, AlphaFi, and Suilend by following the existing Node.js SDK integration pattern.

## Critical Files to Modify

### New Files to Create
1. `data/scallop/scallop_reader-sdk.mjs` - Node.js SDK wrapper
2. `data/scallop/scallop_reader.py` - Python interface
3. `data/scallop/package.json` - NPM dependencies

### Existing Files to Modify
1. `data/protocol_merger.py` - Add Scallop to protocol list
2. `package.json` (root) - Update install script

## Implementation Steps

### Step 1: Create Scallop Directory Structure
```
data/scallop/
├── package.json
├── scallop_reader-sdk.mjs
└── scallop_reader.py
```

### Step 2: Create Node.js SDK Wrapper (`scallop_reader-sdk.mjs`)

**Key Implementation Details:**
- Import `@scallop-io/sui-scallop-sdk` and `@mysten/sui/client`
- Read `SUI_RPC_URL` from environment (set by Python)
- Initialize Scallop SDK with address ID and mainnet network
- Create ScallopQuery instance for data fetching
- Fetch all market pools and collateral data
- Transform to match existing schema structure
- Convert all APRs from percentages to decimals (divide by 100)
- Output JSON to stdout for Python consumption

**Data Transformations:**
- APRs: `interestApr` / 100 → decimal (e.g., 5.0 → 0.05)
- Rewards: Sum all reward APRs, divide by 100
- Collateral: LTV/threshold percentages → decimals
- Fees: Already decimal format from SDK
- Prices: Pass through as-is

**Output Schema (per market):**
```json
{
  "token_symbol": "SUI",
  "token_contract": "0x2::sui::SUI",
  "price": "2.45",
  "lend_apr_base": "0.0316",
  "lend_apr_reward": "0.0085",
  "lend_apr_total": "0.0401",
  "borrow_apr_base": "0.0650",
  "borrow_apr_reward": "0.0120",
  "borrow_apr_total": "0.0530",
  "total_supplied": "1000000",
  "total_borrowed": "650000",
  "utilisation": "0.65",
  "available_amount_usd": "857500.00",
  "collateralization_factor": "0.70",
  "liquidation_threshold": "0.75",
  "borrow_fee": "0.003"
}
```

**Pattern to Follow:** See `alphalend_reader-sdk.mjs` (simpler pattern) rather than `suilend_reader-sdk.mjs` (complex reward calculations)

### Step 3: Create Python Reader (`scallop_reader.py`)

**Class Structure:**
```python
@dataclass
class ScallopReaderConfig:
    node_script_path: str
    rpc_url: str = "https://rpc.mainnet.sui.io"

class ScallopReader:
    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
    def _get_all_markets(self) -> List[Dict[str, Any]]
    @staticmethod
    def _to_float(x: Any) -> Optional[float]
```

**Implementation Pattern:**
- Call Node.js script via `subprocess.run()`
- Pass `SUI_RPC_URL` via environment variable
- Parse JSON from stdout
- Transform into 3 DataFrames: lend, borrow, collateral
- **CRITICAL:** APRs come as decimals from JS (already divided by 100)
- No further conversion needed (unlike Suilend which divides again)
- Print progress: `"found {npools} lending pools"`

**DataFrame Schemas:**

Lend DataFrame:
- Token, Supply_base_apr, Supply_reward_apr, Supply_apr
- Price, Total_supply, Utilization, Available_borrow_usd
- Borrow_fee, Token_coin_type

Borrow DataFrame:
- Token, Borrow_base_apr, Borrow_reward_apr, Borrow_apr
- Price, Total_borrow, Utilization, Borrow_fee
- Token_coin_type

Collateral DataFrame:
- Token, Collateralization_factor, Liquidation_threshold
- Token_coin_type

**Pattern to Follow:** Copy structure from `alphafi_reader.py` (lines 1-126)

### Step 4: Create Package.json

```json
{
  "name": "scallop-reader",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@mysten/sui": "^1.45.0",
    "@scallop-io/sui-scallop-sdk": "latest"
  }
}
```

**Note:** Use `@mysten/sui` version consistent with AlphaFi (^1.45.0)

### Step 5: Update Protocol Merger (`protocol_merger.py`)

**Changes Required:**

1. **Import statement (after line 12):**
```python
from data.scallop.scallop_reader import ScallopReader, ScallopReaderConfig
```

2. **Update protocols list (line 142):**
```python
protocols = ["Navi", "AlphaFi", "Suilend", "Scallop"]
```

3. **Add Scallop case in fetch_protocol_data() (after line 78):**
```python
elif protocol_name == "Scallop":
    print("\t\tgetting Scallop rates:")
    config = ScallopReaderConfig(
        node_script_path="data/scallop/scallop_reader-sdk.mjs"
    )
    reader = ScallopReader(config)
    return reader.get_all_data()
```

**Result:** Merged DataFrames will now have 4 protocol columns:
- Token | Contract | Navi | AlphaFi | Suilend | Scallop

### Step 6: Update Root Package.json

**Modify install script (line 6):**
```json
"install-sdks-separately": "cd data/alphalend && npm install && cd ../suilend && npm install && cd ../scallop && npm install"
```

## Data Flow Architecture

```
User runs refresh_pipeline.py
    ↓
protocol_merger.merge_protocol_data()
    ↓
fetch_protocol_data("Scallop")
    ↓
ScallopReader.get_all_data()
    ↓
subprocess.run(["node", "scallop_reader-sdk.mjs"])
    ↓
Scallop SDK: Initialize client → Query markets → Format JSON
    ↓
Python: Parse JSON → Create 3 DataFrames → Return
    ↓
Merge with Navi/AlphaFi/Suilend data by contract address
    ↓
Filter: Keep tokens in 2+ protocols or stablecoins
    ↓
Save to database (rates_snapshot table)
```

## Key Design Principles to Follow

### 1. Rate Representation (DESIGN_NOTES.md #7)
- **Database/Internal:** ALL rates stored as decimals (0.05 = 5%)
- **JS Script:** Convert SDK percentages → decimals before output
- **Python:** Accept decimals as-is, no further conversion
- **Display:** Only convert to percentages in dashboard

### 2. No sys.path Manipulation (DESIGN_NOTES.md #8)
- Use proper relative imports
- NO `sys.path.append()` anywhere in new code
- Follow existing import patterns in other readers

### 3. Subprocess Pattern
- Pass config via environment variables (not command-line args)
- Capture both stdout and stderr
- Check return code before parsing JSON
- Provide clear error messages with both stderr and stdout

### 4. Error Handling
- Graceful degradation: If Scallop fails, continue with other protocols
- Print warnings (⚠️) but don't crash the pipeline
- Return empty DataFrames on error
- Log full error details for debugging

## Testing Strategy

### Unit Test (Manual)
```bash
# 1. Install dependencies
cd data/scallop
npm install

# 2. Test Node.js script directly
node scallop_reader-sdk.mjs

# Expected: JSON array of markets printed to stdout

# 3. Test Python reader
cd ../..
python -c "
from data.scallop.scallop_reader import ScallopReader, ScallopReaderConfig
config = ScallopReaderConfig(node_script_path='data/scallop/scallop_reader-sdk.mjs')
reader = ScallopReader(config)
lend, borrow, coll = reader.get_all_data()
print('Lend markets:', len(lend))
print(lend.head())
"
```

### Integration Test
```bash
# Run full refresh pipeline
python main.py

# Expected output should include:
# "getting Scallop rates:"
# "found X lending pools"
# No errors in Scallop data fetching
```

### Verification Checks

1. **Column Consistency:** All 4 protocols have same column structure
2. **Contract Normalization:** Contracts match across protocols (0x2::sui::SUI format)
3. **APR Scale:** All APRs between 0 and 1 (not 0-100)
4. **Data Completeness:** Scallop column in merged DataFrames has values
5. **Token Count:** More tokens in merged data (Scallop adds unique tokens)

## Edge Cases & Considerations

### 1. Scallop-Only Tokens
- If Scallop has tokens not in other protocols, they'll be filtered out
- UNLESS they're in STABLECOIN_CONTRACTS set
- This is expected behavior per protocol_merger.py logic (line 271)

### 2. SDK Version Compatibility
- Scallop SDK only supports mainnet (no testnet)
- Use `latest` version to get most recent fixes
- SDK is actively maintained (Jan 2026 updates)

### 3. Reward Token Handling
- Scallop has dual rewards (SCA + SUI tokens)
- Sum all reward APRs into single `Supply_reward_apr` field
- Match pattern from AlphaFi (multiple rewards summed)

### 4. Missing Data Fields
- If SDK doesn't provide a field, set to None/null
- Python's `_to_float()` handles None gracefully
- Database allows NULL for optional fields

### 5. Rate Limit Considerations
- AlphaFi has retry logic for 429/503 errors
- Scallop may need similar handling if issues arise
- Can add in future iteration if needed

## Success Criteria

- [ ] Node.js script runs without errors
- [ ] Python reader returns 3 non-empty DataFrames
- [ ] All APRs are in decimal format (0-1 range)
- [ ] Protocol merger includes Scallop column
- [ ] Refresh pipeline completes successfully
- [ ] Database contains Scallop data in rates_snapshot
- [ ] No regression in existing Navi/AlphaFi/Suilend functionality
- [ ] Token registry includes Scallop-supported tokens

## Rollback Plan

If integration fails:
1. Remove Scallop from `protocols` list in protocol_merger.py
2. Comment out Scallop import and elif block
3. System continues with 3 protocols (Navi, AlphaFi, Suilend)
4. No data loss or corruption

## Future Enhancements (Out of Scope)

- Add retry logic for rate limiting (like AlphaFi)
- Fetch historical data via Scallop's indexer API
- Support veSCA boost calculations (requires user position data)
- Add Scallop-specific metrics dashboard
