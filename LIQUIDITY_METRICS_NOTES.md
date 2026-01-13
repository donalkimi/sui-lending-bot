# Adding Liquidity Metrics (availableBorrowUSD) - Implementation Notes

**Date:** 2025-01-12  
**Status:** Planning / Ready to implement  
**Priority:** Tomorrow's task (Task 10)

---

## Goal
Add `availableBorrowUSD` column to dashboard strategy displays, specifically:
- **token2_available_borrow_A**: Available borrow liquidity for token2 in protocol_A

Later expand to:
- `SupplyCapUSD` (available supply in USD)
- `TotalSupply` 
- `Utilization`

---

## Current Data Flow

### 1. Protocol Readers (ALREADY HAVE THE DATA!)
Each protocol reader returns DataFrames with multiple columns:

**Navi** (`navi_reader.py`):
```python
lend_df columns:
- Token
- Supply_base_apr, Supply_reward_apr, Supply_apr
- Price
- Total_supply, Total_supply_usd
- Available_borrow, Available_borrow_usd  ← WE WANT THIS!
- Utilization
- Token_coin_type
```

**AlphaFi** (`alphafi_reader.py`):
```python
lend_df columns:
- Token
- Supply_base_apr, Supply_reward_apr, Supply_apr
- Price
- Total_supply, Total_supply_usd
- Available_borrow, Available_borrow_usd  ← WE WANT THIS!
- Utilization
- Token_coin_type
```

**Suilend** (`suilend_reader.py`):
```python
lend_df columns:
- Token
- Supply_base_apr, Supply_reward_apr, Supply_apr
- Price
- Total_supply
- Available_amount_usd  ← WE WANT THIS (different name!)
- Utilization
- Token_coin_type
```

### 2. Protocol Merger (STRIPS DOWN TO SINGLE VALUES)
`protocol_merger.py` extracts ONE value per token/protocol:
```python
# For each token + protocol combination:
lend_row[protocol] = get_rate_for_contract(df, contract, 'Supply_apr')  # Only APR!

# Result: DataFrame like:
# Token | Contract | Navi | AlphaFi | Suilend
# USDC  | 0x...    | 0.05 | 0.04    | 0.06
```

**The matrices (lend_rates, borrow_rates, prices) only contain ONE metric per protocol!**

### 3. Rate Analyzer (ONLY SEES MATRICES)
`rate_analyzer.py` receives:
- `lend_rates` - only has APR values per protocol
- `borrow_rates` - only has APR values per protocol  
- `collateral_ratios` - only has ratio values per protocol
- `prices` - only has price values per protocol

**It does NOT have access to Available_borrow_usd!**

---

## The Core Problem

**Current architecture:**
```
Protocol Readers (full data)
    ↓
Protocol Merger (extracts single metrics into matrices)
    ↓
Rate Analyzer (only sees matrices, not full data)
```

**To add liquidity metrics, need to either:**
1. Build additional matrices (like `available_borrow_df`) 
2. Pass raw protocol data through to analyzer
3. Extract liquidity at strategy evaluation time

---

## Solution Options

### Option 1: Build New Matrices (RECOMMENDED - follows existing pattern)
**Pros:** Clean, follows existing architecture  
**Cons:** Needs changes in 4 files

**Steps:**
1. `protocol_merger.py`: Build `available_borrow_df` (like `prices_df`)
   - Handle name difference: `Available_borrow_usd` vs `Available_amount_usd`
2. `rate_analyzer.py`: Add `available_borrow` parameter to `__init__`
3. `refresh_pipeline.py`: Thread through the new DataFrame
4. `streamlit_app.py`: Display in strategy details

**Files to modify:**
- `protocol_merger.py` (~30 lines added)
- `rate_analyzer.py` (~5 lines added)
- `refresh_pipeline.py` (~10 lines added)
- `streamlit_app.py` (~10 lines added)

### Option 2: Store Raw Protocol Data in Analyzer
**Pros:** Can access any metric later  
**Cons:** Breaks current clean matrix architecture

```python
class RateAnalyzer:
    def __init__(self, lend_rates, borrow_rates, ..., raw_protocol_data=None):
        self.raw_protocol_data = raw_protocol_data  # Dict of protocol -> DataFrames
        # Can query: self.raw_protocol_data['Navi']['lend']['Available_borrow_usd']
```

### Option 3: Hybrid - Just Pass What You Need
**Pros:** Minimal changes  
**Cons:** Ad-hoc, will need to repeat for each new metric

Just add one more parameter when calling `analyze_strategy()`:
```python
result = self.calculator.analyze_strategy(
    # ... existing params ...
    token2_available_borrow_A=some_value_extracted_earlier
)
```

---

## Recommended Approach

**Go with Option 1** - Build additional matrices following the established pattern.

This is how `prices` was added successfully. It's clean, testable, and maintainable.

### Implementation Checklist:

**Step 1: protocol_merger.py**
- [ ] Create `available_borrow_rows = []` list
- [ ] In token loop, build `available_borrow_row` dict
- [ ] Handle column name differences (Suilend uses `Available_amount_usd`)
- [ ] Create `available_borrow_df = pd.DataFrame(available_borrow_rows)`
- [ ] Filter by `tokens_to_keep`
- [ ] Add to return tuple: `return (..., available_borrow_df)`

**Step 2: rate_analyzer.py**
- [ ] Add `available_borrow: pd.DataFrame` to `__init__` parameters
- [ ] Store as `self.available_borrow = available_borrow`
- [ ] Create `get_available_borrow()` method (similar to `get_price()`)
- [ ] In `analyze_all_combinations()`, extract available borrow value
- [ ] Pass to `analyze_strategy()` if needed for display

**Step 3: refresh_pipeline.py**  
- [ ] Unpack `available_borrow` from `merge_protocol_data()` call
- [ ] Pass to `RateAnalyzer()` constructor
- [ ] Add `available_borrow: pd.DataFrame` to `RefreshResult` dataclass

**Step 4: streamlit_app.py**
- [ ] Update `fetch_protocol_data()` return unpacking
- [ ] Pass `available_borrow` to `run_analysis()`
- [ ] In Tab 3, display Available Borrow table
- [ ] In strategy details, show token2 available borrow metric

---

## Key Implementation Notes

### Column Name Differences
```python
# Navi & AlphaFi use:
'Available_borrow_usd'

# Suilend uses:
'Available_amount_usd'

# Solution in get_rate_for_contract():
value = row.get('Available_borrow_usd')
if pd.isna(value):
    value = row.get('Available_amount_usd')
```

### Testing Checklist
- [ ] Verify all 3 protocols return data
- [ ] Check column alignment (Token, Contract, Navi, AlphaFi, Suilend)
- [ ] Test with missing data (some protocols don't have all tokens)
- [ ] Verify displayed in dashboard Tab 3
- [ ] Verify displayed in strategy details

---

## Follow-up Tasks (After availableBorrowUSD)

Once the pattern is established, add these metrics using the same approach:

1. **TotalSupplyUSD** - from `Total_supply_usd` column
2. **TotalBorrowUSD** - from `Total_borrow_usd` column  
3. **Utilization** - from `Utilization` column (already calculated by protocols)
4. **SupplyCapUSD** - Calculate as `Total_supply_usd - Total_borrow_usd` or fetch if available

---

## Questions to Resolve Tomorrow

1. Do we want to display available borrow in:
   - [ ] Strategy details table?
   - [ ] Top-level metrics?
   - [ ] Only in Tab 3 rate tables?

2. Should we show available borrow for:
   - [ ] Just token2 in protocol_A?
   - [ ] All tokens in both protocols?
   - [ ] Only when it's a constraint (low liquidity warning)?

3. Display format:
   - [ ] Raw USD amount: `$1,234,567`
   - [ ] Abbreviated: `$1.23M`
   - [ ] Both?

---

## Reference: How Prices Were Added

Prices were successfully added following this exact pattern:

1. **protocol_merger.py** (lines ~145-165):
   ```python
   price_row = {'Token': symbol, 'Contract': contract}
   for protocol in protocols:
       df = protocol_data[protocol]['lend']
       price = get_rate_for_contract(df, contract, 'Price')
       price_row[protocol] = price
   price_rows.append(price_row)
   ```

2. **rate_analyzer.py** (lines ~30-40):
   ```python
   def __init__(self, ..., prices: pd.DataFrame, ...):
       self.prices = prices
   ```

3. **Follow the same pattern for available_borrow!**

---

**Next Session:** Start with Step 1 (protocol_merger.py) and work through the checklist.
