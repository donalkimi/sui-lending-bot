# Modal & Table Style Guide

This document defines the styling conventions used in the All Strategies modal that should be applied consistently across the project.

## Table Display Principles

### 1. Use Pandas Styler for Color Formatting

```python
# Create DataFrame
df = pd.DataFrame(data)

# Define color function
def color_apr(val):
    """Color positive APRs green, negative red"""
    if isinstance(val, str) and '%' in val:
        try:
            numeric_val = float(val.replace('%', ''))
            if numeric_val > 0:
                return 'color: green'
            elif numeric_val < 0:
                return 'color: red'
        except (ValueError, TypeError):
            pass
    return ''

# Apply styling
styled_df = df.style.map(color_apr, subset=['Net APR', 'APR 5d', 'APR 30d'])
st.dataframe(styled_df, width='stretch', hide_index=True)
```

**Color conventions:**
- **Green**: Positive numbers (APRs, rates)
- **Red**: Negative numbers (losses, negative APRs)

### 2. Clean Zero Value Display

Show empty cells instead of "0.00" or "0.00%" for cleaner tables:

```python
# Good - conditional display
'Fees (%)': f"{fee * 100:.2f}%" if fee > 0 else "",
'Fees ($$$)': f"${fee_usd:.2f}" if fee_usd > 0 else "",

# Bad - always shows zero
'Fees (%)': f"{fee * 100:.2f}%",  # Shows "0.00%"
'Fees ($$$)': f"${fee_usd:.2f}",   # Shows "$0.00"
```

### 3. Streamlit DataFrame Configuration

Always use these parameters:

```python
st.dataframe(df, width='stretch', hide_index=True)
```

**Parameters:**
- `width='stretch'`: Full width (per DESIGN_NOTES.md #6, not deprecated `use_container_width=True`)
- `hide_index=True`: Remove row numbers

### 4. Spacing and Layout

Use minimal spacing for compact layouts:

```python
# Tighter spacing - use blank markdown
st.markdown("")

# Standard spacing - use divider (only when visual separation needed)
st.divider()
```

**Convention:**
- Between tightly related sections: `st.markdown("")`
- Between major sections: `st.divider()` (sparingly)

### 5. Column Width Constraints

Constrain wide inputs using columns:

```python
# Narrow input (1/3 width)
col1, col2 = st.columns([1, 2])
with col1:
    deployment_usd = st.number_input(...)

# Full width button
st.button("Deploy Position", type="primary", use_container_width=True)
```

## Number Formatting

### Percentages
```python
# Storage: decimals (0.05 = 5%)
rate = 0.05

# Display: multiply by 100
display = f"{rate * 100:.2f}%"  # "5.00%"
```

### USD Amounts
```python
# With comma separators, 2 decimal places
amount = 1234.56
display = f"${amount:,.2f}"  # "$1,234.56"
```

### Token Amounts
```python
# Dynamic precision based on price
def get_token_precision(price: float, target_usd: float = 10.0) -> int:
    """Calculate decimal places to show ~$10 worth of precision."""
    import math
    if price <= 0:
        return 3
    decimal_places = math.ceil(-math.log10(price / target_usd))
    return max(3, min(8, decimal_places))

# Usage
precision = get_token_precision(price)
display = f"{token_amount:,.{precision}f}"
```

**Examples:**
- BTC @ $100,000 → 4 decimals (0.0001 BTC = $10)
- ETH @ $3,000 → 3 decimals (0.001 ETH = $3)
- SUI @ $1 → 3 decimals (minimum)

### Weights/Multipliers
```python
# 4 decimal places
weight = 1.2345
display = f"{weight:.4f}"  # "1.2345"
```

## Column Naming Conventions

### Remove "Entry" Prefix in Forward-Looking Views
```python
# In strategy modal (forward-looking)
'Time'               # Not "Entry Time"
'Net APR'            # Not "Entry Net APR"
'Rate'               # Not "Entry Rate"
'Token Amount'       # Not "Entry Token Amount"

# In positions tab (historical tracking)
'Entry Time'         # Keep "Entry" prefix
'Entry Net APR'      # Keep "Entry" prefix
'Entry Rate'         # Keep "Entry" prefix
```

**Rationale:** "Entry" implies historical data. Use for tracking positions, omit for prospective strategies.

### Use Concise Headers
```python
# Good
'Liq Dist'           # Not "Liquidation Distance"
'Fees (%)'           # Clear and concise
'Size ($$$)'         # Clear it's USD amount

# Bad
'Entry Liquidation Distance'  # Too verbose
'Borrow Fee Percentage'       # Too verbose
```

## Table Structure Patterns

### Summary Table (Single Row, Horizontal Metrics)
```python
summary_data = [{
    'Time': timestamp,
    'Token Flow': f"{t1} → {t2} → {t3}",
    'Protocols': f"{pA} ↔ {pB}",
    'Net APR': f"{apr * 100:.2f}%",
    # ... more metrics
}]
summary_df = pd.DataFrame(summary_data)
styled_df = summary_df.style.map(color_function, subset=['Net APR', ...])
st.dataframe(styled_df, width='stretch', hide_index=True)
```

### Detail Table (Multiple Rows, Vertical Breakdown)
```python
detail_data = []
for item in items:
    detail_data.append({
        'Protocol': protocol,
        'Token': token,
        'Action': action,
        'Weight': f"{weight:.4f}",
        'Rate': f"{rate * 100:.2f}%" if rate > 0 else "",
        # ... more columns
    })

detail_df = pd.DataFrame(detail_data)
styled_df = detail_df.style.map(color_function, subset=['Rate'])
st.dataframe(styled_df, width='stretch', hide_index=True)
```

## Modal Structure Template

```python
@st.dialog("Title", width="large")
def show_modal(data: Dict, timestamp_seconds: int):
    """Modal description"""
    import streamlit as st
    import math

    # Helper functions
    def get_token_precision(price: float, target_usd: float = 10.0) -> int:
        # ... implementation
        pass

    # ========================================
    # HEADER
    # ========================================
    st.markdown("## Header")

    # ========================================
    # SUMMARY TABLE
    # ========================================
    summary_data = [{...}]
    summary_df = pd.DataFrame(summary_data)

    def color_function(val):
        # ... color logic
        pass

    styled_summary = summary_df.style.map(color_function, subset=[...])
    st.dataframe(styled_summary, width='stretch', hide_index=True)

    st.markdown("")  # Tight spacing

    # ========================================
    # INPUT SECTION
    # ========================================
    st.markdown("### Section Title")

    col1, col2 = st.columns([1, 2])
    with col1:
        input_value = st.number_input(...)

    st.markdown("")  # Tight spacing

    # ========================================
    # DETAIL TABLE
    # ========================================
    # Calculate values (reactive to input)
    detail_data = []
    for item in items:
        detail_data.append({...})

    detail_df = pd.DataFrame(detail_data)
    styled_detail = detail_df.style.map(color_function, subset=[...])
    st.dataframe(styled_detail, width='stretch', hide_index=True)

    st.markdown("")  # Tight spacing

    # ========================================
    # ACTION BUTTON
    # ========================================
    if st.button("Action", type="primary", use_container_width=True):
        # ... action logic
        pass
```

## Design Principles References

All styling follows [DESIGN_NOTES.md](DESIGN_NOTES.md):

- **#5**: Timestamps as Unix seconds (int), convert only at display
- **#6**: Use `width='stretch'` not `use_container_width=True`
- **#7**: Rates as decimals (0.05), display as percentages (5.00%)
- **#9**: Token symbols for display only, contracts for logic

## Examples from Codebase

**Reference implementation:**
- All Strategies Modal: `dashboard_renderer.py:462-713` (show_strategy_modal)
- Active Positions Expanded Rows: `dashboard_renderer.py:888-995`
- Color formatting pattern: `dashboard_renderer.py:109-120`
