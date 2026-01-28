# Plan: Switch from Collateral Ratio (maxCF) to Liquidation Threshold (LLTV) for Position Weightings

## Executive Summary

**Current State**: Position weightings (L_A, B_A, L_B, B_B multipliers) are calculated using `collateral_ratio` (maxCF) in the core formula.

**Desired State**: Use `liquidation_threshold` (LLTV) instead of collateral_ratio for the core weighting calculations, but add validation to ensure the resulting weightings still satisfy the maxCF constraint.

**Key Constraint**: `resulting_weightings <= maxCF` must always hold true.

**Rationale**:
- LLTV represents the actual liquidation trigger point (more conservative, e.g., 65%)
- maxCF represents maximum borrowing capacity (more aggressive, e.g., 75%)
- Using LLTV for calculations provides a safer margin
- But we must validate that we don't exceed protocol-defined maxCF limits

---

## Core Formula Change

### Current Formula (Using Collateral Ratio)

**Location**: [analysis/position_calculator.py:61-71](analysis/position_calculator.py#L61-L71)

```python
r_A = (collateral_ratio_A / borrow_weight_A) / (1 + self.liq_dist)
r_B = (collateral_ratio_B / borrow_weight_B) / (1 + self.liq_dist)

L_A = 1.0 / (1.0 - r_A * r_B)
B_A = L_A * r_A
L_B = B_A
B_B = L_B * r_B
```

### Proposed Formula (Using Liquidation Threshold)

```python
# Use liquidation threshold instead of collateral ratio
r_A = (liquidation_threshold_A / borrow_weight_A) / (1 + self.liq_dist)
r_B = (liquidation_threshold_B / borrow_weight_B) / (1 + self.liq_dist)

L_A = 1.0 / (1.0 - r_A * r_B)
B_A = L_A * r_A
L_B = B_A
B_B = L_B * r_B

# CRITICAL VALIDATION: Ensure effective LTV doesn't exceed maxCF
effective_ltv_A = (B_A / L_A) * borrow_weight_A
effective_ltv_B = (B_B / L_B) * borrow_weight_B

if effective_ltv_A > collateral_ratio_A:
    raise ValueError(f"Effective LTV_A ({effective_ltv_A:.4f}) exceeds maxCF_A ({collateral_ratio_A:.4f})")
if effective_ltv_B > collateral_ratio_B:
    raise ValueError(f"Effective LTV_B ({effective_ltv_B:.4f}) exceeds maxCF_B ({collateral_ratio_B:.4f})")
```

**Why This Works**:
- Since `liquidation_threshold < collateral_ratio` typically (e.g., 0.65 < 0.75)
- Using LLTV in the formula will produce **smaller** r_A and r_B values
- This results in **smaller** position multipliers (more conservative)
- The validation ensures we haven't made an error or received bad data

---

## All Locations That Need Changes

### 1. PositionCalculator.calculate_positions() - CORE CHANGE

**File**: [analysis/position_calculator.py](analysis/position_calculator.py)

**Current Signature** (lines 31-36):
```python
def calculate_positions(
    self,
    collateral_ratio_A: float,
    collateral_ratio_B: float,
    borrow_weight_A: float = 1.0,
    borrow_weight_B: float = 1.0
) -> Dict:
```

**New Signature**:
```python
def calculate_positions(
    self,
    liquidation_threshold_A: float,      # CHANGED: was collateral_ratio_A
    liquidation_threshold_B: float,      # CHANGED: was collateral_ratio_B
    collateral_ratio_A: float,           # ADDED: for validation
    collateral_ratio_B: float,           # ADDED: for validation
    borrow_weight_A: float = 1.0,
    borrow_weight_B: float = 1.0
) -> Dict:
```

**Changes Required**:

1. **Lines 61-64**: Replace collateral_ratio with liquidation_threshold
   ```python
   # OLD:
   r_A = (collateral_ratio_A / borrow_weight_A) / (1 + self.liq_dist)
   r_B = (collateral_ratio_B / borrow_weight_B) / (1 + self.liq_dist)

   # NEW:
   r_A = (liquidation_threshold_A / borrow_weight_A) / (1 + self.liq_dist)
   r_B = (liquidation_threshold_B / borrow_weight_B) / (1 + self.liq_dist)
   ```

2. **After line 71**: Add validation block
   ```python
   # Validate that effective LTV doesn't exceed maxCF
   effective_ltv_A = (B_A / L_A) * borrow_weight_A
   effective_ltv_B = (B_B / L_B) * borrow_weight_B

   if effective_ltv_A > collateral_ratio_A:
       raise ValueError(
           f"Effective LTV_A ({effective_ltv_A:.4f}) exceeds maxCF_A ({collateral_ratio_A:.4f}). "
           f"LLTV_A={liquidation_threshold_A:.4f}, borrow_weight_A={borrow_weight_A:.4f}"
       )
   if effective_ltv_B > collateral_ratio_B:
       raise ValueError(
           f"Effective LTV_B ({effective_ltv_B:.4f}) exceeds maxCF_B ({collateral_ratio_B:.4f}). "
           f"LLTV_B={liquidation_threshold_B:.4f}, borrow_weight_B={borrow_weight_B:.4f}"
       )
   ```

3. **Lines 75-83**: Update return dictionary to include both values
   ```python
   return {
       'L_A': L_A,
       'B_A': B_A,
       'L_B': L_B,
       'B_B': B_B,
       'r_A': r_A,
       'r_B': r_B,
       'liquidation_threshold_A': liquidation_threshold_A,  # NEW
       'liquidation_threshold_B': liquidation_threshold_B,  # NEW
       'collateral_ratio_A': collateral_ratio_A,            # ADDED
       'collateral_ratio_B': collateral_ratio_B,            # ADDED
       'effective_ltv_A': effective_ltv_A,                  # NEW
       'effective_ltv_B': effective_ltv_B                   # NEW
   }
   ```

---

### 2. PositionCalculator.analyze_strategy() - PARAMETER PASSING

**File**: [analysis/position_calculator.py:453-457](analysis/position_calculator.py#L453-L457)

**Current Code**:
```python
positions = self.calculate_positions(
    collateral_ratio_token1_A,
    collateral_ratio_token2_B,
    borrow_weight_2A,
    borrow_weight_3B
)
```

**New Code**:
```python
positions = self.calculate_positions(
    liquidation_threshold_token1_A,  # CHANGED: use LLTV
    liquidation_threshold_token2_B,  # CHANGED: use LLTV
    collateral_ratio_token1_A,       # ADDED: for validation
    collateral_ratio_token2_B,       # ADDED: for validation
    borrow_weight_2A,
    borrow_weight_3B
)
```

**Return Dictionary Update** (lines 531-534):
```python
# Already has both values, just ensure they're included:
'collateral_ratio_1A': collateral_ratio_token1_A,
'collateral_ratio_2B': collateral_ratio_token2_B,
'liquidation_threshold_1A': liquidation_threshold_token1_A,
'liquidation_threshold_2B': liquidation_threshold_token2_B,
# ADD new fields:
'effective_ltv_1A': positions['effective_ltv_A'],  # NEW
'effective_ltv_2B': positions['effective_ltv_B']   # NEW
```

---

### 3. RateAnalyzer.analyze_all_combinations() - NO CHANGE NEEDED

**File**: [analysis/rate_analyzer.py:491-539](analysis/rate_analyzer.py#L491-L539)

**Current Code** (already retrieves both values):
```python
collateral_1A = self.get_rate(self.collateral_ratios, token1, protocol_A)
collateral_2B = self.get_rate(self.collateral_ratios, token2, protocol_B)
liquidation_threshold_1A = self.get_liquidation_threshold(token1, protocol_A)
liquidation_threshold_2B = self.get_liquidation_threshold(token2, protocol_B)
```

**Already passes both to calculator** (lines 534-539):
```python
result = self.calculator.analyze_strategy(
    # ... other params ...
    collateral_ratio_token1_A=collateral_1A,
    collateral_ratio_token2_B=collateral_2B,
    liquidation_threshold_token1_A=liquidation_threshold_1A,
    liquidation_threshold_token2_B=liquidation_threshold_2B,
    # ... other params ...
)
```

**Status**: ✅ No changes needed - already structured correctly

---

### 4. PositionService - STORAGE & DISPLAY

**File**: [analysis/position_service.py](analysis/position_service.py)

**Changes Required**:

#### A. create_position() - Add effective_ltv storage (lines 114-119)

```python
# Current:
entry_collateral_ratio_1A = strategy_row.get('collateral_ratio_1A', 0)
entry_collateral_ratio_2B = strategy_row.get('collateral_ratio_2B', 0)
entry_liquidation_threshold_1A = strategy_row.get('liquidation_threshold_1A', 0)
entry_liquidation_threshold_2B = strategy_row.get('liquidation_threshold_2B', 0)

# ADD:
entry_effective_ltv_1A = strategy_row.get('effective_ltv_1A', 0)
entry_effective_ltv_2B = strategy_row.get('effective_ltv_2B', 0)
```

**Note**: Would require schema change to add `entry_effective_ltv_1A` and `entry_effective_ltv_2B` columns to positions table. This is OPTIONAL - could be calculated on-the-fly instead.

#### B. capture_rebalance_snapshot() - Include effective_ltv (lines 688-692)

```python
'collateral_ratio_1A': position['entry_collateral_ratio_1A'],
'collateral_ratio_2B': position['entry_collateral_ratio_2B'],
'liquidation_threshold_1A': position['entry_liquidation_threshold_1A'],
'liquidation_threshold_2B': position['entry_liquidation_threshold_2B'],
# ADD:
'effective_ltv_1A': position.get('entry_effective_ltv_1A', 0),  # NEW
'effective_ltv_2B': position.get('entry_effective_ltv_2B', 0)   # NEW
```

**Status**: OPTIONAL - for enhanced tracking

---

### 5. Dashboard Updates - DISPLAY CHANGES

**File**: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)

**Changes Required**:

#### A. Token details table in All Strategies tab (lines 645-718)

**Current columns**: Token, Protocol, Rate, maxCF, LLTV, Borrow Weight, Weight

**Add new column**: "Effective LTV" to show the actual LTV being used

```python
# Row 1: Lend Token1 in Protocol A (after line 665)
{
    'Token': strategy['token1'],
    'Protocol': strategy['protocol_A'],
    'Rate': f"{strategy['lend_rate_1A'] * 100:.2f}%",
    'maxCF': f"{strategy['collateral_ratio_1A'] * 100:.1f}%",
    'LLTV': f"{strategy['liquidation_threshold_1A'] * 100:.1f}%",
    'Borrow Weight': '-',
    'Effective LTV': f"{strategy['effective_ltv_1A'] * 100:.1f}%",  # NEW
    'Weight': f"{strategy['L_A']:.2f}x"
}
```

Repeat for all 4 rows (Lend1A, Borrow2A, Lend2B, Borrow3B)

**Purpose**: Show users that calculations now use LLTV but effective LTV respects maxCF constraint

---

### 6. Database Schema - OPTIONAL ENHANCEMENTS

**File**: [data/schema.sql](data/schema.sql)

**Optional additions to positions table** (after line 176):
```sql
-- Effective LTV (actual LTV used after LLTV-based calculation)
entry_effective_ltv_1A DECIMAL(10, 6),
entry_effective_ltv_2B DECIMAL(10, 6),
```

**Optional additions to position_rebalances table** (after line 278):
```sql
-- Effective LTV at rebalance time
effective_ltv_1A DECIMAL(10, 6),
effective_ltv_2B DECIMAL(10, 6),
```

**Migration Script** (new file: `data/migrations/add_effective_ltv.sql`):
```sql
-- Migration: Add effective_ltv columns (OPTIONAL)
-- Date: 2026-01-28

ALTER TABLE positions
ADD COLUMN entry_effective_ltv_1A DECIMAL(10, 6) DEFAULT 0.0;

ALTER TABLE positions
ADD COLUMN entry_effective_ltv_2B DECIMAL(10, 6) DEFAULT 0.0;

ALTER TABLE position_rebalances
ADD COLUMN effective_ltv_1A DECIMAL(10, 6) DEFAULT 0.0;

ALTER TABLE position_rebalances
ADD COLUMN effective_ltv_2B DECIMAL(10, 6) DEFAULT 0.0;
```

---

## Implementation Order

**Critical**: Follow this sequence due to dependencies:

### Phase 1: Core Calculation (Foundation)
1. **PositionCalculator.calculate_positions()** - Change formula to use LLTV, add maxCF validation
2. **PositionCalculator.analyze_strategy()** - Update call to calculate_positions()
3. **Test**: Run unit tests to verify calculations work and validation triggers correctly

### Phase 2: Pipeline Integration
4. **RateAnalyzer** - Verify it already passes both values (no changes needed)
5. **Test**: Run refresh_pipeline.py to generate strategies with new calculations

### Phase 3: Storage & Display (Optional)
6. **Database schema** - Add effective_ltv columns if desired
7. **PositionService** - Store effective_ltv values
8. **Dashboard** - Add "Effective LTV" column to token details table
9. **Test**: Deploy test position, verify display

---

## Validation Strategy

### 1. Mathematical Validation

**Test Case 1**: Normal scenario (LLTV < maxCF)
```python
liquidation_threshold_A = 0.65  # 65%
collateral_ratio_A = 0.75        # 75%
borrow_weight_A = 1.0
liquidation_distance = 0.30

# Expected:
r_A = (0.65 / 1.0) / (1 + 0.30) = 0.5
effective_ltv_A = should be <= 0.75
# Should PASS validation
```

**Test Case 2**: Edge case (LLTV very close to maxCF)
```python
liquidation_threshold_A = 0.74  # 74%
collateral_ratio_A = 0.75        # 75%
# With liquidation_distance, should still PASS
```

**Test Case 3**: Invalid data (LLTV > maxCF - data error)
```python
liquidation_threshold_A = 0.80  # 80% (ERROR!)
collateral_ratio_A = 0.75        # 75%
# Should FAIL validation with clear error message
```

**Test Case 4**: High borrow weight
```python
liquidation_threshold_A = 0.65  # 65%
collateral_ratio_A = 0.75        # 75%
borrow_weight_A = 1.5            # Risky asset
# effective_ltv should be higher, verify <= maxCF
```

### 2. Code Testing

**Unit Tests** (new file: `tests/test_lltv_switch.py`):
```python
def test_calculate_positions_uses_lltv():
    """Verify positions calculated from LLTV, not maxCF"""
    calc = PositionCalculator(liquidation_distance=0.30)

    result = calc.calculate_positions(
        liquidation_threshold_A=0.65,
        liquidation_threshold_B=0.70,
        collateral_ratio_A=0.75,
        collateral_ratio_B=0.80,
        borrow_weight_A=1.0,
        borrow_weight_B=1.0
    )

    # Verify multipliers are calculated from LLTV
    assert result['r_A'] == pytest.approx((0.65 / 1.0) / 1.30)
    assert result['r_B'] == pytest.approx((0.70 / 1.0) / 1.30)

    # Verify effective_ltv <= maxCF
    assert result['effective_ltv_A'] <= 0.75
    assert result['effective_ltv_B'] <= 0.80

def test_maxcf_validation_triggers():
    """Verify validation catches violations"""
    calc = PositionCalculator(liquidation_distance=0.0)  # No safety buffer

    with pytest.raises(ValueError, match="exceeds maxCF_A"):
        calc.calculate_positions(
            liquidation_threshold_A=0.80,  # Higher than maxCF!
            liquidation_threshold_B=0.70,
            collateral_ratio_A=0.75,
            collateral_ratio_B=0.80,
            borrow_weight_A=1.0,
            borrow_weight_B=1.0
        )
```

### 3. Integration Testing

**Dashboard Test**:
1. Run `python -m data.refresh_pipeline`
2. Open dashboard, navigate to "All Strategies" tab
3. Expand a strategy, inspect token details table
4. Verify:
   - maxCF column shows protocol's max LTV (e.g., 75%)
   - LLTV column shows liquidation threshold (e.g., 65%)
   - Effective LTV column shows actual LTV used (should be close to LLTV, definitely <= maxCF)
   - Position multipliers (Weight column) are reasonable

**End-to-End Test**:
1. Deploy a test position using new calculations
2. Verify position is created successfully (no validation errors)
3. Check database: `SELECT * FROM positions ORDER BY created_at DESC LIMIT 1`
4. Verify effective_ltv values are present and <= maxCF
5. Monitor position for a few data refresh cycles
6. Verify rebalance snapshots capture effective_ltv correctly

---

## Risk Assessment & Mitigation

### Risk 1: Position Sizes Change
**Impact**: Using LLTV (lower than maxCF) will produce **smaller** position multipliers
- Current (using maxCF=0.75): Might get L_A=3.5x
- New (using LLTV=0.65): Will get L_A=2.8x (more conservative)

**Mitigation**:
- This is INTENDED behavior - safer positions
- Communicate change to users
- Consider adjustable parameter to scale LLTV usage

### Risk 2: Bad Protocol Data
**Impact**: If protocol returns LLTV > maxCF (data error), validation will fail

**Mitigation**:
- Clear error messages indicating data source issue
- Log warnings during data refresh
- Consider data quality checks in protocol readers

### Risk 3: Historical Positions
**Impact**: Existing positions were calculated with maxCF

**Mitigation**:
- Existing positions unaffected (immutable entry state)
- Rebalancing will use new calculation
- Document change in position notes

### Risk 4: Validation False Positives
**Impact**: Validation might trigger on edge cases due to floating point precision

**Mitigation**:
- Add small epsilon tolerance (e.g., `effective_ltv <= collateral_ratio + 0.001`)
- Log warnings before raising errors

---

## Rollback Plan

If issues arise after deployment:

1. **Immediate Rollback** (Code Change):
   - Revert [position_calculator.py:61-64](analysis/position_calculator.py#L61-L64) to use `collateral_ratio` instead of `liquidation_threshold`
   - Remove validation block
   - Redeploy

2. **Data Integrity**:
   - No database changes required (both values already stored)
   - Existing positions unaffected
   - New positions will use old calculation

3. **Testing Rollback**:
   ```bash
   git checkout HEAD~1 -- analysis/position_calculator.py
   python -m data.refresh_pipeline
   # Verify strategies generated correctly
   ```

---

## Success Criteria

✅ **Formula Changed**: `r_A` and `r_B` calculated using liquidation_threshold instead of collateral_ratio

✅ **Validation Added**: Effective LTV validation prevents exceeding maxCF

✅ **All Tests Pass**: Unit tests, integration tests, dashboard tests all green

✅ **Position Sizes Correct**: New positions have smaller, safer multipliers

✅ **Dashboard Updated**: "Effective LTV" column shows actual LTV used

✅ **No Regressions**: Existing functionality (liquidation prices, PnL, etc.) unchanged

✅ **Data Quality**: No validation errors from production protocol data

✅ **Documentation**: Change documented in DESIGN_NOTES.md

---

## Files Summary

### Files to Modify

1. **[analysis/position_calculator.py](analysis/position_calculator.py)** ⭐ CRITICAL
   - Lines 31-36: Update `calculate_positions()` signature
   - Lines 61-64: Change formula to use `liquidation_threshold`
   - Lines 71+: Add validation block
   - Lines 75-83: Update return dictionary
   - Lines 453-457: Update `analyze_strategy()` call to `calculate_positions()`
   - Lines 531-534: Add `effective_ltv` to return dict

2. **[analysis/rate_analyzer.py](analysis/rate_analyzer.py)** ✅ NO CHANGES
   - Already passes both values correctly

3. **[analysis/position_service.py](analysis/position_service.py)** (OPTIONAL)
   - Lines 114-119: Extract `effective_ltv` from strategy_row
   - Lines 154, 171: Add to INSERT statement
   - Lines 688-692: Add to rebalance snapshot

4. **[dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)** (OPTIONAL)
   - Lines 645-718: Add "Effective LTV" column to all 4 token detail rows

5. **[data/schema.sql](data/schema.sql)** (OPTIONAL)
   - Lines 170-176: Add `entry_effective_ltv_1A/2B` columns
   - Lines 272-278: Add `effective_ltv_1A/2B` columns to position_rebalances

6. **[data/migrations/add_effective_ltv.sql](data/migrations/add_effective_ltv.sql)** (NEW, OPTIONAL)
   - Create migration for effective_ltv columns

### Files to Read (No Changes)

- [analysis/rate_analyzer.py](analysis/rate_analyzer.py) - Verify current data flow
- [data/refresh_pipeline.py](data/refresh_pipeline.py) - Verify RateAnalyzer initialization
- [dashboard/streamlit_app.py](dashboard/streamlit_app.py) - Verify dashboard data loading

---

## Key Questions to Answer Before Implementation

1. **Should we store effective_ltv in database?**
   - Pro: Historical tracking, easier querying
   - Con: Can be calculated on-the-fly, extra storage
   - **Recommendation**: Store it - useful for auditing

2. **Should validation be strict (raise error) or permissive (log warning)?**
   - Strict: Prevents bad positions, but might break pipeline if data is wrong
   - Permissive: Allows pipeline to continue, but might create risky positions
   - **Recommendation**: Strict validation, but add data quality checks upstream

3. **Should there be a configuration toggle?**
   - Could add `use_lltv_for_weightings=True` parameter to PositionCalculator
   - Allows easy A/B testing and rollback
   - **Recommendation**: Yes - add toggle for safer deployment

4. **What epsilon tolerance for validation?**
   - `effective_ltv <= collateral_ratio + epsilon`
   - Epsilon = 0.001 (0.1%) or 0.0001 (0.01%)?
   - **Recommendation**: 0.0001 - tight but accounts for float precision

---

## Configuration Toggle (Recommended Addition)

Add to [analysis/position_calculator.py](analysis/position_calculator.py):

```python
def __init__(self, liquidation_distance: float, use_lltv_for_weightings: bool = True):
    self.liquidation_distance = liquidation_distance
    self.use_lltv_for_weightings = use_lltv_for_weightings  # NEW
```

Then in `calculate_positions()`:

```python
if self.use_lltv_for_weightings:
    r_A = (liquidation_threshold_A / borrow_weight_A) / (1 + self.liq_dist)
    r_B = (liquidation_threshold_B / borrow_weight_B) / (1 + self.liq_dist)
else:
    # Legacy behavior: use collateral_ratio
    r_A = (collateral_ratio_A / borrow_weight_A) / (1 + self.liq_dist)
    r_B = (collateral_ratio_B / borrow_weight_B) / (1 + self.liq_dist)
```

This allows easy toggling for testing and rollback.

---

End of Plan
