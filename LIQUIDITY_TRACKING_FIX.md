# Liquidity Data Tracking Fix - Implementation Handover

**Date:** 2026-01-14
**Status:** 🔧 READY FOR IMPLEMENTATION
**Priority:** HIGH - Blocks historical dashboard functionality
**Estimated Time:** 30-45 minutes

---

## Executive Summary

**Problem:** Historical snapshots have NULL `available_borrow_usd`, causing all strategies to appear in "Zero Liquidity" tab instead of "All Strategies" tab.

**Root Cause:** `rate_tracker.py` hardcodes `available_borrow_usd` to `None` instead of saving the actual liquidity data that's already being fetched from protocol APIs.

**Solution:** Update 2 files (~30 lines total) to pass and save `available_borrow` data to the database.

**Impact:** Fixes historical dashboard completely - strategies will display correctly with real liquidity constraints.

---

## Problem Analysis

### Current Data Flow

```
merge_protocol_data()  →  refresh_pipeline()  →  RateTracker.save_snapshot()  →  Database
    ✅ Fetches liquidity      ✅ Receives it         ❌ Ignores it           ❌ Stores NULL
```

### Evidence

1. **Database schema HAS the column** ([data/schema.sql:32](data/schema.sql#L32))
   ```sql
   available_borrow_usd DECIMAL(20,10),
   ```

2. **Protocol merger FETCHES the data** ([data/protocol_merger.py](data/protocol_merger.py))
   ```python
   return (lend_rates, borrow_rates, collateral_ratios, prices,
           lend_rewards, borrow_rewards, available_borrow, borrow_fees)
   ```

3. **Refresh pipeline RECEIVES but DOESN'T PASS** ([data/refresh_pipeline.py:68-89](data/refresh_pipeline.py#L68-L89))
   ```python
   lend_rates, borrow_rates, ..., available_borrow, borrow_fees = merge_protocol_data()

   tracker.save_snapshot(
       timestamp=ts,
       lend_rates=lend_rates,
       ...
       # ❌ available_borrow NOT PASSED
       # ❌ borrow_fees NOT PASSED
   )
   ```

4. **Rate tracker HARDCODES NULL** ([data/rate_tracker.py:157](data/rate_tracker.py#L157))
   ```python
   'available_borrow_usd': None,  # ❌ Hardcoded!
   ```

### Impact on Dashboard

When `available_borrow_usd` is NULL:
- `max_size` calculation returns NULL/0
- Filter condition `max_size < deployment_usd` catches everything
- ALL strategies moved to "⚠️ Zero Liquidity" tab
- "📊 All Strategies" tab shows "⚠️ No strategies found"

**Dashboard filtering logic** ([dashboard/dashboard_renderer.py:1193-1197](dashboard/dashboard_renderer.py#L1193-L1197)):
```python
zero_liquidity_results = all_results[
    (all_results['max_size'].isna()) |     # ← NULL available_borrow causes this
    (all_results['max_size'] == 0) |
    (all_results['max_size'] < deployment_usd)
]
```

---

## Implementation Plan

### File 1: `data/rate_tracker.py`

#### Change 1.1: Update `save_snapshot()` method signature

**Location:** Lines 49-78
**Action:** Add `available_borrow` and `borrow_fees` parameters

```python
def save_snapshot(
    self,
    timestamp: datetime,
    lend_rates: pd.DataFrame,
    borrow_rates: pd.DataFrame,
    collateral_ratios: pd.DataFrame,
    prices: Optional[pd.DataFrame] = None,
    lend_rewards: Optional[pd.DataFrame] = None,
    borrow_rewards: Optional[pd.DataFrame] = None,
    available_borrow: Optional[pd.DataFrame] = None,  # ← ADD THIS
    borrow_fees: Optional[pd.DataFrame] = None         # ← ADD THIS
):
    """
    Save a complete snapshot of protocol data

    Args:
        timestamp: Snapshot timestamp (datetime object, rounded to minute)
        lend_rates: DataFrame with lending rates (Token, Contract, Protocol1, Protocol2, ...)
        borrow_rates: DataFrame with borrow rates
        collateral_ratios: DataFrame with collateral ratios
        prices: DataFrame with prices (optional)
        lend_rewards: DataFrame with lend reward APRs (optional)
        borrow_rewards: DataFrame with borrow reward APRs (optional)
        available_borrow: DataFrame with available borrow liquidity in USD (optional)  # ← ADD
        borrow_fees: DataFrame with borrow fees as decimals (optional)                 # ← ADD
    """
```

#### Change 1.2: Pass new parameters to `_save_rates_snapshot()`

**Location:** Line 75-78
**Action:** Add parameters to method call

```python
# Before:
rows_saved = self._save_rates_snapshot(
    conn, timestamp, lend_rates, borrow_rates,
    collateral_ratios, prices
)

# After:
rows_saved = self._save_rates_snapshot(
    conn, timestamp, lend_rates, borrow_rates,
    collateral_ratios, prices, available_borrow, borrow_fees  # ← ADD THESE
)
```

#### Change 1.3: Update `_save_rates_snapshot()` signature

**Location:** Line 101-109
**Action:** Add parameters to method signature

```python
def _save_rates_snapshot(
    self,
    conn,
    timestamp: datetime,
    lend_rates: pd.DataFrame,
    borrow_rates: pd.DataFrame,
    collateral_ratios: pd.DataFrame,
    prices: Optional[pd.DataFrame],
    available_borrow: Optional[pd.DataFrame] = None,  # ← ADD THIS
    borrow_fees: Optional[pd.DataFrame] = None        # ← ADD THIS
) -> int:
    """Save to rates_snapshot table"""
```

#### Change 1.4: Extract liquidity data in row-building loop

**Location:** Lines 119-127
**Action:** Add extraction of available_borrow_row (similar to price_row, collateral_row, etc.)

```python
# Build rows for each token/protocol combination
for _, lend_row in lend_rates.iterrows():
    token = lend_row['Token']
    token_contract = lend_row['Contract']

    # Get corresponding rows from other dataframes
    borrow_row = borrow_rates[borrow_rates['Contract'] == token_contract].iloc[0] if not borrow_rates.empty else None
    collateral_row = collateral_ratios[collateral_ratios['Contract'] == token_contract].iloc[0] if not collateral_ratios.empty else None
    price_row = prices[prices['Contract'] == token_contract].iloc[0] if prices is not None and not prices.empty else None
    available_borrow_row = available_borrow[available_borrow['Contract'] == token_contract].iloc[0] if available_borrow is not None and not available_borrow.empty else None  # ← ADD THIS LINE
    borrow_fee_row = borrow_fees[borrow_fees['Contract'] == token_contract].iloc[0] if borrow_fees is not None and not borrow_fees.empty else None  # ← ADD THIS LINE (optional)
```

#### Change 1.5: Extract available_borrow_usd in protocol loop

**Location:** Lines 131-134 (in the `for protocol in protocols:` loop)
**Action:** Extract available_borrow_usd value (similar to lend_base_apr, borrow_base_apr, etc.)

```python
# For each protocol
for protocol in protocols:
    # Get rates
    lend_base_apr = lend_row.get(protocol) if pd.notna(lend_row.get(protocol)) else None
    borrow_base_apr = borrow_row.get(protocol) if borrow_row is not None and pd.notna(borrow_row.get(protocol)) else None
    collateral_ratio = collateral_row.get(protocol) if collateral_row is not None and pd.notna(collateral_row.get(protocol)) else None
    price_usd = price_row.get(protocol) if price_row is not None and pd.notna(price_row.get(protocol)) else None
    available_borrow_usd = available_borrow_row.get(protocol) if available_borrow_row is not None and pd.notna(available_borrow_row.get(protocol)) else None  # ← ADD THIS LINE
```

#### Change 1.6: Use extracted value in row dict

**Location:** Line 157 (in the `rows.append({...})` dict)
**Action:** Change from hardcoded `None` to extracted `available_borrow_usd`

```python
rows.append({
    'timestamp': timestamp,
    'protocol': protocol,
    'token': token,
    'token_contract': token_contract,
    'lend_base_apr': lend_base_apr,
    'lend_reward_apr': None,  # TODO: Extract from lend_rewards
    'lend_total_apr': lend_base_apr,
    'borrow_base_apr': borrow_base_apr,
    'borrow_reward_apr': None,  # TODO: Extract from borrow_rewards
    'borrow_total_apr': borrow_base_apr,
    'collateral_ratio': collateral_ratio,
    'liquidation_threshold': None,
    'price_usd': price_usd,
    'utilization': None,
    'total_supply_usd': None,
    'total_borrow_usd': None,
    'available_borrow_usd': available_borrow_usd,  # ← CHANGE FROM None TO available_borrow_usd
})
```

---

### File 2: `data/refresh_pipeline.py`

#### Change 2.1: Pass liquidity data to tracker

**Location:** Lines 81-89
**Action:** Add `available_borrow` and `borrow_fees` to `save_snapshot()` call

```python
# Before:
tracker.save_snapshot(
    timestamp=ts,
    lend_rates=lend_rates,
    borrow_rates=borrow_rates,
    collateral_ratios=collateral_ratios,
    prices=prices,
    lend_rewards=lend_rewards,
    borrow_rewards=borrow_rewards,
)

# After:
tracker.save_snapshot(
    timestamp=ts,
    lend_rates=lend_rates,
    borrow_rates=borrow_rates,
    collateral_ratios=collateral_ratios,
    prices=prices,
    lend_rewards=lend_rewards,
    borrow_rewards=borrow_rewards,
    available_borrow=available_borrow,  # ← ADD THIS
    borrow_fees=borrow_fees,            # ← ADD THIS
)
```

---

## Testing Procedure

### Pre-Implementation Check

Verify current state shows NULL:

```bash
# Check existing data
sqlite3 data/lending_rates.db "SELECT token, protocol, available_borrow_usd FROM rates_snapshot ORDER BY timestamp DESC LIMIT 5"

# Expected output: All NULL or empty values
```

### Post-Implementation Testing

#### Test 1: Verify Data Collection

```bash
# Run main.py to capture a new snapshot with the fix
python main.py

# Check that available_borrow_usd is populated
sqlite3 data/lending_rates.db "SELECT token, protocol, available_borrow_usd FROM rates_snapshot ORDER BY timestamp DESC LIMIT 10"

# Expected: Should see actual USD values like:
# USDC|Navi|1234567.89
# SUI|AlphaFi|987654.32
# etc.
```

#### Test 2: Verify Historical Dashboard

```bash
# Start dashboard
streamlit run dashboard/streamlit_app.py

# 1. Select "📜 Historical" mode
# 2. Select latest timestamp from dropdown
# 3. Go to "📊 All Strategies" tab

# Expected: Strategies should be visible (not "⚠️ No strategies found")
```

#### Test 3: Check Zero Liquidity Tab

```bash
# In dashboard, go to "⚠️ 0 Liquidity" tab

# Expected:
# - Should only show strategies with ACTUAL low liquidity
# - Not all strategies like before
# - Message should say "X strategies have insufficient liquidity"
```

#### Test 4: Verify Strategy Details

```bash
# In "📊 All Strategies" tab, expand any strategy

# Expected:
# - "Available" column should show liquidity values (e.g., "$1.2M", "$456K")
# - Not "N/A" everywhere
# - "Max Deployable Size" should show realistic values
```

---

## Rollback Plan

### If Something Breaks

**Good news:** This is a safe, additive change!

1. **No schema changes needed** - `available_borrow_usd` column already exists
2. **Backwards compatible** - Optional parameters with defaults
3. **Old snapshots unaffected** - Will continue to have NULL (as before)
4. **New snapshots work** - Will have real liquidity data

**To rollback:**
```bash
# Simply revert the 2 files
git checkout data/rate_tracker.py
git checkout data/refresh_pipeline.py

# Old behavior restored (saves NULL like before)
```

---

## Edge Cases & Considerations

### 1. Missing Liquidity Data from Protocols

**Scenario:** Some protocols don't return available_borrow data

**Handling:** Already handled - the code checks `if available_borrow_row is not None and pd.notna(...)` before extracting. NULL values are acceptable.

### 2. Zero Liquidity vs NULL Liquidity

**NULL:** Protocol doesn't provide data → Allow strategy to show
**Zero:** Protocol reports 0 liquidity → Move to "Zero Liquidity" tab

**Current logic handles this correctly:**
```python
zero_liquidity_results = all_results[
    (all_results['max_size'].isna()) |      # NULL - will still catch these
    (all_results['max_size'] == 0) |        # Zero - catch these too
    (all_results['max_size'] < deployment_usd)  # Insufficient
]
```

### 3. Historical Data Already Captured

**Issue:** Existing snapshots have NULL available_borrow_usd

**Solution:**
- Can't retroactively fix old snapshots (data wasn't captured)
- New snapshots from now on will have liquidity data
- Old snapshots will continue to show in "Zero Liquidity" tab
- Acceptable tradeoff

**Optional enhancement:** Add info message in historical mode:
```python
if mode == 'historical':
    st.info("💡 Snapshots before [date] don't have liquidity data - all strategies may appear in Zero Liquidity tab")
```

### 4. borrow_fee Column

**Status:** Not currently in database schema (unlike available_borrow_usd)

**Decision:** Two options:

**Option A (Recommended):** Skip borrow_fee for now
- Remove `borrow_fee_row` extraction from implementation
- Remove `borrow_fees` parameter from method signatures
- Focus on `available_borrow` only (the critical blocker)
- Add borrow_fee later when needed

**Option B:** Add borrow_fee to schema first
- Update `data/schema.sql` to add `borrow_fee DECIMAL(10,6)`
- Run migration: `sqlite3 data/lending_rates.db < data/schema.sql`
- Then implement full tracking

**Recommendation:** Go with Option A to unblock historical dashboard ASAP

---

## Success Criteria

### Must Have (Critical)
- ✅ New snapshots save `available_borrow_usd` with actual values (not NULL)
- ✅ Historical dashboard "All Strategies" tab shows strategies
- ✅ "Zero Liquidity" tab only shows strategies with actual low liquidity
- ✅ Strategy details show liquidity constraints

### Nice to Have (Optional)
- ✅ Console output confirms liquidity data saved: "✅ Saved snapshot: X rate rows..."
- ✅ No errors or warnings during snapshot capture
- ✅ Database query confirms values present

---

## File Summary

| File | Lines Changed | Type | Risk |
|------|---------------|------|------|
| `data/rate_tracker.py` | ~15-20 | Additive | Low |
| `data/refresh_pipeline.py` | 2 | Additive | Low |
| **Total** | **~17-22** | **Parameters + Logic** | **Low** |

---

## Time Estimate

- **Code changes:** 15 minutes
- **Testing:** 15 minutes
- **Debugging (if needed):** 10 minutes
- **Total:** 30-45 minutes

---

## Questions Before Implementation

1. **Skip borrow_fee tracking?**
   Recommendation: Yes, focus on available_borrow only (the blocker)

2. **Handle PostgreSQL differently?**
   No - same logic works for both SQLite and PostgreSQL (already abstracted)

3. **Add logging for debugging?**
   Optional - could add: `print(f"Saved available_borrow: {available_borrow_usd}")` in loop

---

## Post-Implementation

### Update Documentation

After implementation succeeds, update:

1. **DASHBOARD_HANDOVER.md**
   - Note that liquidity tracking is now enabled
   - Old snapshots (before fix) won't have liquidity data

2. **README.md** (if exists)
   - Mention available_borrow tracking in features

### Monitor Going Forward

Watch for:
- Protocols that consistently return NULL liquidity
- Performance impact (minimal expected - just one column)
- Database size growth (negligible - DECIMAL(20,10) is 12 bytes)

---

## Contact

If issues arise during implementation:
- Check plan file: `.claude/plans/liquidity-tracking-fix.md`
- Review error messages carefully (likely pandas DataFrame key errors)
- Verify protocol_merger output format matches expectations

---

**Ready to implement?** Start with File 1 (rate_tracker.py), then File 2 (refresh_pipeline.py), then test!
