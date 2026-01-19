# Implementation Summary: Realized APR Calculator & Position System Fixes

**Date:** 2026-01-19
**Status:** ✅ Core Implementation Complete | ⚠️ Critical Bug Found in Position Creation

---

## Overview

This document summarizes the major architectural changes made to implement a realized APR calculator for positions and remove the redundant `position_snapshots` table. A critical bug was also discovered in the position creation system that must be fixed before positions can be deployed successfully.

---

## Major Changes Completed

### 1. ✅ Removed position_snapshots Table Architecture

**Problem:** The `position_snapshots` table was redundant - it duplicated data already available in `rates_snapshot`.

**Solution:** Calculate position performance on-the-fly from `rates_snapshot` table.

**Files Changed:**
- **data/schema.sql** - Removed entire `position_snapshots` table definition (previously lines 216-286)
- **data/refresh_pipeline.py** - Removed `create_position_snapshots` parameter and all snapshot creation logic
- **main.py** - Removed hourly snapshot creation logic
- **Scripts/purge_positions.py** - Removed all position_snapshots references
- **DESIGN_NOTES.md** - Updated Event Sourcing principle to reflect new architecture

**Benefits:**
- Single source of truth (rates_snapshot)
- No data duplication
- Simpler maintenance
- Always accurate calculations

---

### 2. ✅ Implemented Realized APR Calculator

**Purpose:** Calculate the actual APR a position has earned from entry until "live" timestamp using ALL historical rate data.

#### Core Algorithm

**Formula:**
```
LE(T) = Total Lend Earnings in $$$
BC(T) = Total Borrow Costs in $$$
FEES = One-time upfront fees in $$$
NET$$$ = LE(T) - BC(T) - FEES
ANNUAL_NET_EARNINGS = NET$$$ / T × 365 (where T = holding days)
Realized APR = ANNUAL_NET_EARNINGS / deployment_usd
```

**Key Principles:**
- Uses forward-looking rates: rates at timestamp T apply to period [T, T+1)
- Queries ALL timestamps in rates_snapshot between entry and live
- Works in $$ amounts until final APR calculation
- "live" timestamp = dashboard selected date (NOT current time)
- Never uses datetime.now()

#### Files Modified

**analysis/position_service.py:**

1. **Refactored calculate_position_value() method** (lines 260-453)
   - Changed from using position_snapshots to querying rates_snapshot directly
   - Queries all unique timestamps between entry and live
   - For each period [t_i, t_{i+1}):
     - Calculates lend earnings: deployment × (L_A × lend_rate_1A + L_B × lend_rate_2B) × time_years
     - Calculates borrow costs: deployment × (B_A × borrow_rate_2A + B_B × borrow_rate_3B) × time_years
   - Calculates one-time fees: deployment × (B_A × fee_2A + B_B × fee_3B)
   - Returns dict with: `current_value`, `lend_earnings`, `borrow_costs`, `fees`, `net_earnings`, `holding_days`, `periods_count`

2. **Added calculate_realized_apr() method** (lines 455-477)
   - Simple 2-line wrapper that calls calculate_position_value()
   - Annualizes net earnings: `(net_earnings / holding_days * 365) / deployment_usd`
   - Returns decimal (0.05 = 5%)

**dashboard/dashboard_renderer.py:**

1. **Updated render_positions_table_tab()** (lines 714-757)
   - Calls calculate_position_value() and calculate_realized_apr()
   - Added 3 new columns to positions table:
     - **Realized APR**: Annualized return rate as percentage
     - **Current Value**: deployment_usd + NET$$$
     - **Net Earnings**: NET$$$ = LE(T) - BC(T) - FEES

2. **Reordered columns for better comparison** (lines 724-757)
   - Grouped related metrics together
   - Entry values next to current values for easy comparison
   - New order:
     - Position identification (Entry Time, Current Time, Token Flow, Protocols)
     - APR progression (Entry APR → Current APR → Realized APR)
     - Value metrics (Current Value, Net Earnings)
     - Position weights (L_A, B_A, L_B, B_B)
     - Rates comparison (Entry Lend 1A → Live Lend 1A, etc.)

3. **Fixed dashboard deployment form** (lines 154-184)
   - Updated create_position() call to pass all required parameters
   - Added position multipliers calculation from get_strategy_history()
   - Fixed parameter list to match create_position() signature

---

## ⚠️ CRITICAL BUG DISCOVERED - Position Creation

### Issue

Positions are being created with NULL/zero entry rates, causing `NoneType * int` error when viewing positions.

**Example:**
```
Position 79aa938a-7e8f-4d10-aa4f-f4147a76bcd1:
entry_lend_rate_1A = 0       (should have rate)
entry_borrow_rate_2A = 0     (should have rate)
entry_lend_rate_2B = 0       (should have rate)
entry_borrow_rate_3B = NULL  (causes NoneType * int error)
```

### Root Cause

**Field name mismatch** between what `create_position()` expects and what RateAnalyzer provides.

### Field Name Mismatches Found

#### 1. Rates (position_service.py lines 104-107)

**WRONG (Current Code):**
```python
entry_lend_rate_1A = strategy_row.get('lend_total_apr_1A', 0)
entry_borrow_rate_2A = strategy_row.get('borrow_total_apr_2A', 0)
entry_lend_rate_2B = strategy_row.get('lend_total_apr_2B', 0)
entry_borrow_rate_3B = strategy_row.get('borrow_total_apr_3B')
```

**CORRECT (Should Be):**
```python
entry_lend_rate_1A = strategy_row.get('lend_rate_1A', 0)
entry_borrow_rate_2A = strategy_row.get('borrow_rate_2A', 0)
entry_lend_rate_2B = strategy_row.get('lend_rate_2B', 0)
entry_borrow_rate_3B = strategy_row.get('borrow_rate_3B')
```

#### 2. Prices (position_service.py lines 110-113)

**WRONG (Current Code):**
```python
entry_price_1A = strategy_row.get('price_1A', 0)
entry_price_2A = strategy_row.get('price_2A', 0)
entry_price_2B = strategy_row.get('price_2B', 0)
entry_price_3B = strategy_row.get('price_3B')
```

**CORRECT (Should Be):**
```python
entry_price_1A = strategy_row.get('P1_A', 0)
entry_price_2A = strategy_row.get('P2_A', 0)
entry_price_2B = strategy_row.get('P2_B', 0)
entry_price_3B = strategy_row.get('P3_B')
```

#### 3. Collateral Ratios (position_service.py lines 116-117)

**Current Code:**
```python
entry_collateral_ratio_1A = strategy_row.get('collateral_ratio_1A', 0)
entry_collateral_ratio_2B = strategy_row.get('collateral_ratio_2B', 0)
```

**Problem:** These fields are NOT included in RateAnalyzer's output.

**Solution:** Add them to position_calculator.py `analyze_strategy()` return dict (after line 376):
```python
'collateral_ratio_1A': collateral_ratio_token1_A,
'collateral_ratio_2B': collateral_ratio_token2_B,
```

These variables already exist in the function (lines 205-206), just need to be added to the return dictionary.

---

## Required Fixes Before Production Use

### Step 1: Fix Field Names in position_service.py

**File:** analysis/position_service.py
**Lines:** 104-117

Apply the corrections shown above for rates, prices, and collateral ratios.

### Step 2: Add Collateral Ratios to RateAnalyzer Output

**File:** analysis/position_calculator.py
**Line:** After line 376 in `analyze_strategy()` method

Add to the return dictionary:
```python
'collateral_ratio_1A': collateral_ratio_token1_A,
'collateral_ratio_2B': collateral_ratio_token2_B,
```

### Step 3: Purge Bad Position Data

After fixing the code, run:
```bash
python3 Scripts/purge_positions.py --force
```

This will delete the incorrectly created position. User can then redeploy with correct data.

---

## Design Principles Followed

✅ **Timestamp as Current Time**: Selected timestamp IS "now"
✅ **No datetime.now()**: All timestamps passed explicitly
✅ **Unix Seconds Internally**: All calculations use int
✅ **Rates as Decimals**: 0.05 = 5%, convert to % only at display
✅ **Forward-Looking**: Rates at T apply to period [T, T+1)
✅ **Event Sourcing**: Read-only queries, no mutations
✅ **Single Source of Truth**: Use rates_snapshot table

---

## Files Modified Summary

### Core Implementation
1. **analysis/position_service.py** - Refactored calculate_position_value(), added calculate_realized_apr()
2. **dashboard/dashboard_renderer.py** - Added new columns, reordered display, fixed deployment form
3. **data/schema.sql** - Removed position_snapshots table
4. **data/refresh_pipeline.py** - Removed snapshot creation logic
5. **main.py** - Removed hourly snapshot creation
6. **Scripts/purge_positions.py** - Removed snapshot references
7. **DESIGN_NOTES.md** - Updated Event Sourcing documentation

### Still Needs Fixing (Critical)
8. **analysis/position_service.py** (lines 104-117) - Fix field name mismatches
9. **analysis/position_calculator.py** (line 376) - Add collateral ratio fields

---

## Testing Recommendations

After applying the critical fixes:

1. **Purge existing position:** `python3 Scripts/purge_positions.py --force`
2. **Deploy a test position** through the dashboard
3. **Verify position creation:**
   ```bash
   sqlite3 data/lending_rates.db "SELECT entry_lend_rate_1A, entry_borrow_rate_2A, entry_lend_rate_2B, entry_borrow_rate_3B FROM positions"
   ```
   All rates should have non-zero values
4. **View position in dashboard** - Should display without errors
5. **Check new columns:** Realized APR, Current Value, Net Earnings should show correct values

---

## Next Steps

1. **URGENT:** Apply the critical fixes to position_service.py and position_calculator.py
2. Purge bad position data
3. Test position creation and viewing
4. Deploy a real position and monitor Realized APR calculation
5. Consider adding unit tests for calculate_position_value() and calculate_realized_apr()

---

## Architecture Impact

**Before:**
- positions table (entry state)
- position_snapshots table (state over time) ← Redundant!
- rates_snapshot table (market rates)

**After:**
- positions table (entry state only)
- rates_snapshot table (single source of truth)
- Calculate everything on-the-fly ← Clean, accurate, simple

**Result:** Simpler architecture, no data duplication, always accurate calculations.
