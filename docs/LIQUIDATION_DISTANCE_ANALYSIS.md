# Liquidation Distance Analysis

## Problem Summary

The bot calculates liquidation prices for lending and borrowing positions. When using a 20% liquidation distance parameter, the **borrowing side shows exactly 20% distance**, but the **lending side shows only 16.67% distance**.

### Root Cause

The position sizing formula uses:
```python
r = LLTV / (1 + liq_dist)  # e.g., 0.70 / 1.20 = 0.5833
```

This creates **asymmetric price protection** because:
- `LLTV × (1 - liq_dist) ≠ LLTV / (1 + liq_dist)`
- `0.70 × 0.80 = 0.56` vs `0.70 / 1.20 = 0.5833`

The non-linear relationship between price changes and LTV changes means:
- **Lending side** (collateral drops): Price must drop **16.67%** for LTV to increase 20%
- **Borrowing side** (loan token rises): Price must rise **20%** for LTV to increase 20%

## Mathematical Relationship

Given a position with ratio `r` and liquidation threshold `LLTV`:

**Lending liquidation distance (x):**
```
x = 1 - (r / LLTV)
```

**Borrowing liquidation distance (y):**
```
y = (LLTV / r) - 1
```

**Key relationship:**
```
y = x / (1 - x)
```

Or equivalently:
```
1 + y = 1 / (1 - x)
```

### Verification

**Example 1: r = 0.56, LLTV = 0.70**
```
Lending:  x = 1 - (0.56/0.70) = 0.20 (20%)
Borrowing: y = (0.70/0.56) - 1 = 0.25 (25%)

Check: y = x/(1-x) = 0.20/0.80 = 0.25 ✓
```

**Example 2: r = 0.5833, LLTV = 0.70**
```
Lending:  x = 1 - (0.5833/0.70) = 0.1667 (16.67%)
Borrowing: y = (0.70/0.5833) - 1 = 0.20 (20%)

Check: y = x/(1-x) = 0.1667/0.8333 = 0.20 ✓
```

### General Proof

Given:
- Lending distance: `x = 1 - (r/LLTV)`
- Therefore: `r/LLTV = 1 - x`

For borrowing distance:
```
y = (LLTV/r) - 1
  = 1/(r/LLTV) - 1
  = 1/(1-x) - 1
  = [1 - (1-x)] / (1-x)
  = x / (1-x)
```

**Mathematical fact:** For any given `r`, the lending side **always** has less protection than the borrowing side (when r < LLTV).

## Solution: Asymmetric Protection with Minimum Guarantee

### Strategy

Given user requests `liq_dist = 0.20` minimum protection:
1. Calculate `liq_max = liq_dist / (1 - liq_dist)`
2. Use position sizing: `r = LLTV × (1 - liq_dist)`
3. This guarantees **at least** `liq_dist` on the more vulnerable side (lending)
4. Borrowing side automatically gets `liq_max` protection (bonus)

### Implementation

```python
# User input
liq_dist = 0.20  # Minimum protection requested

# Calculate maximum (borrowing side) protection
liq_max = liq_dist / (1 - liq_dist)
# liq_max = 0.20 / 0.80 = 0.25 (25%)

# Position sizing (change from current implementation)
r = LLTV * (1 - liq_dist)
# r = 0.70 * 0.80 = 0.56

# No changes needed to liquidation price calculation
# The existing formulas will automatically produce:
# - Lending side: 20% distance
# - Borrowing side: 25% distance
```

### Current vs New Formula

**Current (incorrect for user expectations):**
```python
r_A = collateral_ratio_A / (1 + self.liq_dist)
# r = 0.70 / 1.20 = 0.5833
# Result: 16.67% lending, 20% borrowing
```

**New (guarantees minimum):**
```python
r_A = collateral_ratio_A * (1 - self.liq_dist)
# r = 0.70 * 0.80 = 0.56
# Result: 20% lending, 25% borrowing
```

### Verification with LLTV = 0.70, liq_dist = 0.20

```python
# New formula
r = 0.70 * (1 - 0.20) = 0.56

# Lending side check
x = 1 - (0.56/0.70) = 1 - 0.8 = 0.20 ✓
# Price must drop 20% for liquidation

# Borrowing side check
y = (0.70/0.56) - 1 = 1.25 - 1 = 0.25 ✓
# Price must rise 25% for liquidation

# Verify relationship
y = x/(1-x) = 0.20/0.80 = 0.25 ✓
```

### Numerical Example

**Position with r = 0.56, LLTV = 0.70:**

**Initial state:**
- Collateral: $100 worth of token A at $1.00/token
- Loan: $56 worth of token B at $1.00/token
- LTV: 56%

**Lending liquidation (collateral drops 20%):**
- Token A drops to $0.80/token
- Collateral value: $80
- Loan value: $56 (unchanged)
- LTV: $56/$80 = 70% → **Liquidation!**

**Borrowing liquidation (loan token rises 25%):**
- Token B rises to $1.25/token
- Collateral value: $100 (unchanged)
- Loan value: $70
- LTV: $70/$100 = 70% → **Liquidation!**

## Benefits of This Approach

1. **Conservative**: Over-protects rather than under-protects
2. **User-friendly**: User gets at least what they asked for (20% minimum)
3. **Bonus protection**: Borrowing side gets extra buffer (25%)
4. **Minimal code changes**: Only need to change position sizing formula
5. **No liquidation formula changes**: Existing calculations remain correct

## Implementation Notes

### Files to Modify

**Primary change:**
- `analysis/position_calculator.py` (Line 47-49): Change position sizing formula from `/ (1 + liq_dist)` to `* (1 - liq_dist)`

**No changes needed:**
- Liquidation price calculation formulas (they're already correct)
- Dashboard display logic
- Any other downstream code

### Formula Mapping

For documentation/UI purposes, you can display both distances to users:

```python
def calculate_protection_distances(liq_dist: float) -> tuple[float, float]:
    """
    Calculate actual price protection distances.

    Args:
        liq_dist: User-requested minimum liquidation distance (e.g., 0.20 for 20%)

    Returns:
        (lending_distance, borrowing_distance) as decimals
    """
    lending_dist = liq_dist
    borrowing_dist = liq_dist / (1 - liq_dist)
    return lending_dist, borrowing_dist

# Example:
lending, borrowing = calculate_protection_distances(0.20)
# lending = 0.20 (20%)
# borrowing = 0.25 (25%)
```

This allows the UI to show users:
- "Minimum protection: 20%"
- "Actual protection: Lending 20%, Borrowing 25%"

---

## IMPLEMENTED SOLUTION

**Implementation Date**: January 23, 2026

The quick fix has been implemented using the boundary transformation approach:

### What Changed

1. **File Modified**: `analysis/position_calculator.py`
2. **Location**: `PositionCalculator.__init__()` method (Lines 12-26)
3. **Change**: User input `liq_dist` is transformed to `liq_max` at the boundary

### Implementation Details

```python
def __init__(self, liquidation_distance: float = 0.30):
    # Store original user input for display/reporting purposes
    self.liq_dist_input = liquidation_distance

    # Transform user's minimum liquidation distance to liq_max for internal use
    # This ensures the user gets AT LEAST their requested protection on lending side
    # Formula: liq_max = liq_dist / (1 - liq_dist)
    # Example: 0.20 → 0.25, which gives 20% lending protection and 25% borrowing protection
    self.liq_dist = liquidation_distance / (1 - liquidation_distance)
```

**Key Implementation Detail**: The calculator stores both values:
- `self.liq_dist_input`: Original user input (0.20) - returned in results for display
- `self.liq_dist`: Transformed liq_max (0.25) - used in all internal calculations

This ensures that when results are cached and displayed in the dashboard, they show the user's original requested minimum protection (20%), not the internal liq_max value (25%).

### Results

- User inputs: `0.20` (requesting 20% minimum protection)
- System transforms to: `liq_max = 0.25` internally
- Actual protection: **Lending 20%**, **Borrowing 25%**
- User receives **AT LEAST** their requested protection on the more vulnerable lending side

### No Other Changes Needed

All existing formulas and calculations work unchanged:
- Position sizing formula: `r = LLTV / (1 + self.liq_dist)` (now receives liq_max)
- Liquidation price calculations: unchanged
- Net APR calculations: unchanged
- All downstream logic: unchanged

### Verification

The implementation has been verified with unit tests showing correct behavior across multiple liquidation distance values (10%, 15%, 20%, 25%, 30%).
