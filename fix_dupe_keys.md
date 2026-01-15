# Dashboard Fix: Duplicate Key Error

## Problem Summary

The Streamlit dashboard crashes on startup with the following error:

```
streamlit.errors.StreamlitDuplicateElementKey: There are multiple elements with the same `key='deploy_levered_0_live'`
```

**Error Location:** [dashboard_renderer.py:227](dashboard/dashboard_renderer.py#L227)

---

## Root Cause

Two different tabs (`All Strategies` and `Zero Liquidity`) use independent `enumerate()` loops that generate overlapping button keys.

### The Problem

**Tab 1 - All Strategies** ([dashboard_renderer.py:463](dashboard/dashboard_renderer.py#L463)):
```python
for enum_idx, (idx, row) in enumerate(all_results.iterrows()):
    # ...
    display_apr_table(row, deployment_usd, liquidation_distance, enum_idx, mode, historical_timestamp)
```

**Tab 4 - Zero Liquidity** ([dashboard_renderer.py:870](dashboard/dashboard_renderer.py#L870)):
```python
for enum_idx, (idx, row) in enumerate(zero_liquidity_results.iterrows()):
    # ...
    display_apr_table(row, deployment_usd, 0.2, enum_idx, mode, historical_timestamp)
```

Both loops start from `0`, so they generate **identical button keys**:
```
All Strategies Tab:     deploy_levered_0_live, deploy_levered_1_live, ...
Zero Liquidity Tab:     deploy_levered_0_live, deploy_levered_1_live, ...  ← COLLISION!
```

**Inside `display_apr_table()`** ([dashboard_renderer.py:227, 240](dashboard/dashboard_renderer.py#L227)):
```python
# Levered button
st.button(f"🚀 ${deployment_usd:,.0f}", key=f"deploy_levered_{strategy_idx}_{mode}", ...)

# Unlevered button
st.button(f"🚀 ${deployment_usd:,.0f}", key=f"deploy_unlevered_{strategy_idx}_{mode}", ...)
```

The `strategy_idx` parameter receives `enum_idx`, which is **not globally unique** across tabs.

---

## Solution

Use the DataFrame index (`idx`) instead of the enumeration index (`enum_idx`). The DataFrame index is guaranteed to be unique per row across the entire dataset.

---

## Implementation Steps

### Step 1: Update All Strategies Tab
**File:** [dashboard_renderer.py:463-500](dashboard/dashboard_renderer.py#L463-L500)

**Change line 463:**
```python
# OLD:
for enum_idx, (idx, row) in enumerate(all_results.iterrows()):

# NEW:
for _enum_idx, (idx, row) in enumerate(all_results.iterrows()):
```

**Change line 500:**
```python
# OLD:
fee_caption, warning_message = display_apr_table(
    row, deployment_usd, liquidation_distance, enum_idx, mode, historical_timestamp
)

# NEW:
fee_caption, warning_message = display_apr_table(
    row, deployment_usd, liquidation_distance, idx, mode, historical_timestamp
)
```

---

### Step 2: Update Zero Liquidity Tab
**File:** [dashboard_renderer.py:870-899](dashboard/dashboard_renderer.py#L870-L899)

**Change line 870:**
```python
# OLD:
for enum_idx, (idx, row) in enumerate(zero_liquidity_results.iterrows()):

# NEW:
for _enum_idx, (idx, row) in enumerate(zero_liquidity_results.iterrows()):
```

**Change line 899:**
```python
# OLD:
fee_caption, warning_message = display_apr_table(row, deployment_usd, 0.2, enum_idx, mode, historical_timestamp)

# NEW:
fee_caption, warning_message = display_apr_table(row, deployment_usd, 0.2, idx, mode, historical_timestamp)
```

---

### Step 3: Update Function Documentation
**File:** [dashboard_renderer.py:162](dashboard/dashboard_renderer.py#L162)

**Change:**
```python
# OLD:
        strategy_idx: Index of the strategy for unique button keys

# NEW:
        strategy_idx: Unique identifier for the strategy (DataFrame index) for unique button keys
```

---

## Files to Modify

Only **1 file** needs changes:
- [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py) - 5 small edits

---

## Testing & Verification

### Manual Testing
1. **Run the dashboard:**
   ```bash
   cd dashboard
   streamlit run streamlit_app.py
   ```

2. **Verify no duplicate key error:**
   - Dashboard should load without the `StreamlitDuplicateElementKey` error
   - Check terminal/browser console for no errors

3. **Test All Strategies Tab:**
   - Expand 2-3 strategy rows
   - Click both deploy buttons (levered and unlevered)
   - Verify deployment form opens correctly

4. **Test Zero Liquidity Tab:**
   - Switch to "⚠️ 0 Liquidity" tab
   - Expand 2-3 strategy rows
   - Click deploy buttons
   - Verify no key collision errors

5. **Test Mode Switching:**
   - Switch between Live and Historical modes
   - Verify keys remain unique in both modes

---

## Success Criteria

- ✅ Dashboard loads without `StreamlitDuplicateElementKey` error
- ✅ All deploy buttons work in both All Strategies and Zero Liquidity tabs
- ✅ Keys remain unique when switching between Live/Historical modes
- ✅ No regression in other dashboard functionality

---

## Estimated Impact

- **Lines Changed:** ~5 lines (4 code changes + 1 docstring)
- **Risk Level:** Low (isolated change, no logic changes)
- **Implementation Time:** 5 minutes
- **Testing Time:** 10 minutes
