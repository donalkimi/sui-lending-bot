# Handover Document: APR Table with Fee-Adjusted Metrics

**Date:** 2026-01-13
**Task:** Add APR comparison table to dashboard with fee-adjusted metrics
**Status:** Plan approved, ready for implementation
**Estimated Effort:** 2-3 hours

---

## Executive Summary

We're adding a new APR comparison table to the dashboard that shows how upfront borrow fees impact returns across different holding periods. This helps users understand the true cost of strategies and make informed decisions about position duration.

**Key Insight:** Short-term positions (5 days) may be unprofitable due to upfront fees consuming all profits. Longer holds amortize fees better.

---

## Background Context

### Current State
- Dashboard shows `net_apr` (base APR without fees)
- Borrow fees ARE collected from protocols but NOT incorporated into APR calculations
- Users can toggle between "levered" (full recursive loop) and "unlevered" (single iteration) strategies
- Fees stored as decimals (e.g., 0.0030 = 30 bps = 0.30%)

### The Problem
Users don't see how upfront borrow fees impact their actual returns over different time horizons. A strategy showing 17.94% APR may actually be negative for a 5-day hold due to fees.

### The Solution
Add a table showing 5 APR metrics:
1. **APR** - Base rate (no fees, current `net_apr`)
2. **APR5** - Return for 5-day hold (fees amortized over 5 days, often negative)
3. **APR30** - Return for 30-day hold (fees amortized over 30 days)
4. **APR90** - Return for 90-day hold (fees amortized over 90 days)
5. **APR(net)** - APR minus annualized fees

---

## Mathematical Foundation (VERIFIED CORRECT)

### Core Formulas

**Given:**
- Positions: `L_A`, `B_A`, `L_B`, `B_B` (leverage multipliers from geometric series)
- Borrow fees: `f_2A`, `f_3B` (decimal format, e.g., 0.0030)
- Current APR: `net_apr` (percentage, without fees)

**APR(net) - Annualized Fee Impact:**
```
APR(net) = net_apr - (B_A × f_2A + B_B × f_3B) × 100%
```

**APR(x) - Time-Adjusted for X Days:**
```
APR(x) = net_apr - [(B_A × f_2A + B_B × f_3B) × 365 / x] × 100%
```

### Example Calculation

**Given:**
- `net_apr = 17.94%`
- `B_A = 0.666`, `B_B = 0.154`
- `f_2A = 0.0030`, `f_3B = 0.0030`

**Fees (upfront, paid once):**
```
Fee_2A = 0.666 × 0.0030 = $0.001998
Fee_3B = 0.154 × 0.0030 = $0.000462
Total_Fees = $0.002460
```

**Results:**
```
APR(net) = 17.94% - 0.25% = 17.69%
APR90 = 17.94% - 1.00% = 16.94%
APR30 = 17.94% - 2.99% = 14.95%
APR5 = 17.94% - 17.96% = -0.02% ← NEGATIVE!
```

**Key Insight:** Fees are annualized (365/x multiplier). Shorter holds = larger fee impact.

---

## Implementation Plan

### Phase 1: Backend Changes

**File:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_calculator.py`

**Location:** Add after `calculate_unlevered_apr()` method (around line 160)

#### Add Helper Function (Flexible for any days)

```python
def calculate_apr_for_days(
    self,
    net_apr: float,
    B_A: float,
    B_B: float,
    borrow_fee_2A: float,
    borrow_fee_3B: float,
    days: int
) -> float:
    """
    Calculate time-adjusted APR for a given holding period

    Args:
        net_apr: Base APR without fees (%)
        B_A: Borrow amount from Protocol A (position multiplier)
        B_B: Borrow amount from Protocol B (position multiplier)
        borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
        borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)
        days: Holding period in days

    Returns:
        Time-adjusted APR accounting for upfront fees (%)

    Formula:
        APRx = net_apr - [(B_A × f_2A + B_B × f_3B) × 365 / days] × 100%
    """
    # Total fee cost (decimal)
    total_fee_cost = B_A * borrow_fee_2A + B_B * borrow_fee_3B

    # Time-adjusted fee impact (percentage)
    fee_impact = (total_fee_cost * 365 / days) * 100

    return net_apr - fee_impact
```

#### Add Main Calculation Function

```python
def calculate_fee_adjusted_aprs(
    self,
    net_apr: float,
    positions: Dict,
    borrow_fee_2A: float,
    borrow_fee_3B: float
) -> Dict[str, float]:
    """
    Calculate fee-adjusted APR metrics for multiple time horizons

    Args:
        net_apr: Base APR without fees (%)
        positions: Dict with L_A, B_A, L_B, B_B
        borrow_fee_2A: Borrow fee for token2 from Protocol A (decimal, e.g., 0.0030)
        borrow_fee_3B: Borrow fee for token3 from Protocol B (decimal, e.g., 0.0030)

    Returns:
        Dictionary with apr_net, apr5, apr30, apr90
    """
    B_A = positions['B_A']
    B_B = positions['B_B']

    # Total annualized fee cost (percentage)
    total_fee_cost = (B_A * borrow_fee_2A + B_B * borrow_fee_3B) * 100

    # APR(net) = APR - annualized fees (equivalent to 365-day APR)
    apr_net = net_apr - total_fee_cost

    # Time-adjusted APRs using helper function
    apr5 = self.calculate_apr_for_days(net_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 5)
    apr30 = self.calculate_apr_for_days(net_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 30)
    apr90 = self.calculate_apr_for_days(net_apr, B_A, B_B, borrow_fee_2A, borrow_fee_3B, 90)

    return {
        'apr_net': apr_net,
        'apr5': apr5,
        'apr30': apr30,
        'apr90': apr90
    }
```

#### Integrate into `analyze_strategy()`

**Location:** After calculating `net_apr` (around line 243)

```python
# Calculate fee-adjusted APRs
fee_adjusted_aprs = self.calculate_fee_adjusted_aprs(
    net_apr,
    positions,
    borrow_fee_2A,
    borrow_fee_3B
)

# Add to result dictionary
result.update({
    'apr_net': fee_adjusted_aprs['apr_net'],
    'apr5': fee_adjusted_aprs['apr5'],
    'apr30': fee_adjusted_aprs['apr30'],
    'apr90': fee_adjusted_aprs['apr90']
})
```

---

### Phase 2: Frontend Changes

**File:** `/Users/donalmoore/Dev/sui-lending-bot/dashboard/streamlit_app.py`

**Location:** New helper function `display_apr_table()` added (around line 527), called in main loop BEFORE "Load Historical Chart" button (lines 1004, 1132)

```python
def display_apr_table(strategy_row):
    """
    Display compact APR comparison table

    Args:
        strategy_row: A row from the all_results DataFrame (as a dict or Series)
    """
    # Extract APR values (default to base APR if missing)
    apr_base = strategy_row['net_apr']
    apr_net = strategy_row.get('apr_net', apr_base)
    apr90 = strategy_row.get('apr90', apr_base)
    apr30 = strategy_row.get('apr30', apr_base)
    apr5 = strategy_row.get('apr5', apr_base)

    # Build single row table with APR(net) first, no base APR
    apr_table_data = {
        'APR(net)': [f"{apr_net:.2f}%"],
        'APR5': [f"{apr5:.2f}%"],
        'APR30': [f"{apr30:.2f}%"],
        'APR90': [f"{apr90:.2f}%"]
    }

    apr_df = pd.DataFrame(apr_table_data)

    # Apply styling for negative values
    def highlight_negative_row(row):
        """Highlight negative APR values in red"""
        styles = []
        for val in row:
            if isinstance(val, str) and '%' in val:
                try:
                    numeric_val = float(val.replace('%', ''))
                    if numeric_val < 0:
                        styles.append('color: red; font-weight: bold')
                    else:
                        styles.append('')
                except:
                    styles.append('')
            else:
                styles.append('')
        return styles

    styled_apr_df = apr_df.style.apply(highlight_negative_row, axis=1)

    # Display compact table with header and hide index
    st.markdown("**📊 APR Comparison**")
    st.dataframe(styled_apr_df, hide_index=True)

    # Fee breakdown caption (default to 0 if missing)
    borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)
    borrow_fee_3B = strategy_row.get('borrow_fee_3B', 0.0)
    st.caption(
        f"💰 Fees: token2={borrow_fee_2A*100:.3f}% | token3={borrow_fee_3B*100:.3f}%"
    )

    # Warning for negative short-term holds
    if apr5 < 0:
        st.warning(
            "⚠️ **5-day APR is negative!** Upfront fees make very short-term positions unprofitable."
        )
```

**Called in main loop:**
```python
with st.expander(title, expanded=is_expanded):
    # Display APR comparison table at the top
    display_apr_table(row)

    # Button to load historical chart
    if st.button("📈 Load Historical Chart", key=f"btn_tab1_{idx}"):
        ...
```

---

## Edge Cases to Handle

### 1. Unlevered Strategies (no B_B)
- When toggle is "No leverage/looping", `B_B = 0`
- Only `f_2A` fee applies
- Formula still works: `total_fee_cost = B_A × f_2A + 0 × f_3B`

### 2. Missing Fee Data
- If protocol doesn't return fees, default to `0`
- Display 'N/A' in table

### 3. Negative APRs
- APR5 will often be negative for typical fee levels
- Highlight in red with warning message
- This is expected behavior, not a bug

### 4. Very High Fees
- If fees > 1%, may significantly impact all time horizons
- Consider adding fee impact percentage column

---

## Testing & Verification

### Unit Tests
1. Test `calculate_apr_for_days()` with known values:
   ```python
   # Example: net_apr=17.94%, B_A=0.666, B_B=0.154, f_2A=f_3B=0.003
   # Expected: apr_net ≈ 17.69%, apr30 ≈ 14.95%, apr5 ≈ -0.02%
   ```

2. Verify formula relationships:
   ```python
   assert apr90 > apr30 > apr5  # Fees hurt more on shorter holds
   assert abs(apr_net - net_apr + total_fee_cost) < 0.01  # apr_net formula
   assert apr90 < net_apr  # Fee impact always reduces APR
   ```

### Dashboard Testing
1. Run: `streamlit run dashboard/streamlit_app.py`
2. Expand a strategy in Tab 1 ("Best Opportunities")
3. Verify APR table displays correctly with 5 rows
4. Check calculations manually for one strategy
5. Toggle between levered/unlevered - verify table updates
6. Look for negative APR5 warnings on high-fee strategies

### Edge Case Checks
- Strategy with very high fees (>1%)
- Strategy with near-zero fees
- Unlevered strategy (B_B = 0)
- Missing fee data (should show N/A)

---

## Expected Output

**APR Table in Dashboard (2 rows, 5 columns):**

| Strategy              | APR(net) | APR5   | APR30  | APR90  |
|-----------------------|----------|--------|--------|--------|
| 🔄 USDC→DEEP→AUSD     | 17.69%   | -0.02% | 14.95% | 16.94% |
| ⏹️ USDC→DEEP          | 12.50%   | 8.30%  | 10.20% | 11.80% |

**Table Features:**
- **Position:** Above "Load Historical Chart" button (stays above chart when displayed)
- **Format:** 2 rows (levered + unlevered), 5 columns (Strategy + 4 APR metrics)
- **Row Names:** Emoji at start + token flow
  - Loop emoji (🔄) at start for levered strategy
  - Stop emoji (⏹️) at start for unlevered strategy
- **Order:** APR(net) first (annualized), then shortest to longest timeframes
- **Styling:** Negative values shown in red and bold
- **Below the table:**
  - Fee breakdown caption: "💰 Fees: token2=0.300% | token3=0.300%"
  - Warning message if APR5 is negative for looped strategy

---

## User Benefits

1. **Informed Decision Making:** See true returns accounting for fees
2. **Time Horizon Awareness:** Understand impact of holding period on profitability
3. **Risk Identification:** Quickly spot when short-term positions are unprofitable
4. **Strategy Comparison:** Compare true returns across strategies, not just base APR

---

## Future Enhancements (Not in Current Scope)

- Add APR10, APR60, or other custom time periods (easy with helper function)
- Show fee impact as percentage of base APR
- Add liquidity depth visualization
- Add "breakeven days" calculation (when does APR turn positive?)

---

## Related Files

### Critical Implementation Files
1. `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_calculator.py` - Backend calculations
2. `/Users/donalmoore/Dev/sui-lending-bot/dashboard/streamlit_app.py` - Frontend display

### Reference Files (Context Only)
1. `/Users/donalmoore/Dev/sui-lending-bot/analysis/rate_analyzer.py` - Fee data collection
2. `/Users/donalmoore/Dev/sui-lending-bot/data/*/` - Protocol-specific fee readers
3. `/Users/donalmoore/Dev/sui-lending-bot/TODO.md` - Project roadmap (Task #13)

---

## Detailed Plan

**Full implementation plan:** `/Users/donalmoore/.claude/plans/idempotent-snacking-kettle.md`

---

## Questions & Contact

If you have questions about:
- **Math/formulas:** Refer to "Mathematical Foundation" section above
- **Implementation details:** See `/Users/donalmoore/.claude/plans/idempotent-snacking-kettle.md`
- **Testing:** See "Testing & Verification" section above
- **Edge cases:** See "Edge Cases to Handle" section above

---

## Approval Status

✅ **Mathematical formulas verified correct**
✅ **Plan approved by user**
✅ **Ready for implementation**

**Next Step:** Implement Phase 1 (Backend) then Phase 2 (Frontend)