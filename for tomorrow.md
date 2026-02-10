# Stage 2: Portfolio Detail Enhancement - Individual Strategy Rows

## Objective
Enhance the portfolio detail view to display individual positions as expandable rows (identical to the Positions tab format) instead of the current simple table.

## Current State
When you expand a portfolio in the Portfolios tab, it shows:
- 3 metric cards (Status, Entry Date, Utilization)
- Simple table with columns: token1, token2, token3, protocol_a, protocol_b, deployment_usd, entry_net_apr, status
- Action buttons (Delete/Close for real portfolios)
- Constraints expander (JSON display)

**Location:** `dashboard/dashboard_renderer.py` lines 5074-5166 (`render_portfolio_detail()`)

## Target State
When you expand a portfolio, it should show:
- Same 3 metric cards at top
- **Each position as an expandable row** (like Positions tab)
  - Expander title format: `▶ timestamp | token_flow | protocol_pair | Entry APR% | Current APR% | Net APR% | Value $X | PnL $X | Earnings $X | Base $X | Rewards $X | Fees $X`
  - Inside each position expander:
    - Strategy Summary metrics (5 columns: Total PnL, Total Earnings, Base Earnings, Reward Earnings, Fees)
    - 4-leg detail table (16-18 columns per leg showing rates, prices, liquidation distances, rebalances)
    - Live Position Summary (unrealized vs realized breakdown)
    - Action buttons (Rebalance/Close for individual position)
- Portfolio-level action buttons (Delete/Close portfolio)
- Constraints expander

## Implementation Approach

### File to Modify
`dashboard/dashboard_renderer.py` - function `render_portfolio_detail()` (lines 5074-5166)

### Step 1: Load Required Data (similar to Positions tab)

```python
def render_portfolio_detail(portfolio, timestamp_seconds: int, service):
    # ... existing metric cards code ...

    # Get positions for this portfolio
    if portfolio['portfolio_id'] is None or pd.isna(portfolio['portfolio_id']):
        positions_df = service.get_standalone_positions()
    else:
        positions_df = service.get_portfolio_positions(portfolio['portfolio_id'])

    if positions_df.empty:
        st.info("No positions in this portfolio yet")
        return

    # Batch load statistics
    position_ids = positions_df['position_id'].tolist()
    all_stats = get_all_position_statistics(position_ids, timestamp_seconds, engine)
    all_rebalances = get_all_rebalance_history(position_ids, conn)

    # Load rates snapshot for live rates/prices
    rates_snapshot_df = pd.read_sql_query("""
        SELECT * FROM rates_snapshot
        WHERE timestamp = (
            SELECT MAX(timestamp)
            FROM rates_snapshot
            WHERE timestamp <= %s
        )
    """, conn, params=(to_datetime_str(timestamp_seconds),))

    # Build lookup dictionaries
    rate_lookup = {}
    for _, row in rates_snapshot_df.iterrows():
        key = (row['protocol'], row['token'])
        rate_lookup[key] = {
            'lend_apr': row['lend_total_apr'],
            'borrow_apr': row['borrow_total_apr'],
            'borrow_fee': row['borrow_fee'],
            'price': row['price_usd']
        }

    # Build oracle prices
    oracle_prices = {}
    for _, row in rates_snapshot_df.iterrows():
        if row['token'] not in oracle_prices:
            oracle_prices[row['token']] = row['price_usd']
```

### Step 2: Define Helper Functions (copy from Positions tab)

```python
    # Helper functions (from Positions tab lines 1270-1399)
    def get_rate(token, protocol, rate_type):
        """Get rate from lookup dict."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        return rates.get(rate_type, 0.0)

    def get_price(token, protocol):
        """Get price from protocol rates."""
        key = (protocol, token)
        rates = rate_lookup.get(key, {})
        return rates.get('price', None)

    def get_oracle_price(token_symbol):
        """Get oracle price fallback."""
        return oracle_prices.get(token_symbol)

    def get_price_with_fallback(token, protocol):
        """3-tier price fallback: protocol -> oracle -> None."""
        price = get_price(token, protocol)
        if price is not None and price > 0:
            return price
        price = get_oracle_price(token)
        if price is not None and price > 0:
            return price
        return None

    # ... more helper functions as needed ...
```

### Step 3: Replace Simple Table with Position Expanders

```python
    st.markdown("### Strategies in Portfolio")

    # Iterate through positions and render each as expandable row
    for _, pos in positions_df.iterrows():
        position_id = pos['position_id']

        # Get statistics
        stats = all_stats.get(position_id)
        rebalances = all_rebalances.get(position_id, [])

        # Build token flow string
        token_flow = f"{pos['token1']}"
        if pos['token2']:
            token_flow += f" → {pos['token2']}"
        if pos['token3']:
            token_flow += f" → {pos['token3']}"

        # Build protocol pair string
        protocol_pair = f"{pos['protocol_a']} ↔ {pos['protocol_b']}"

        # Get metrics
        entry_apr = pos['entry_net_apr'] * 100
        deployment = pos['deployment_usd']

        if stats:
            current_value = stats['current_value']
            current_apr = stats.get('current_apr', 0.0) * 100
            realized_apr = stats.get('realized_apr', 0.0) * 100
            total_pnl = stats['total_pnl']
            total_earnings = stats['total_earnings']
            base_earnings = stats.get('base_earnings', 0.0)
            reward_earnings = stats.get('reward_earnings', 0.0)
            total_fees = stats['total_fees']
        else:
            current_value = deployment
            current_apr = entry_apr
            realized_apr = 0.0
            total_pnl = 0.0
            total_earnings = 0.0
            base_earnings = 0.0
            reward_earnings = 0.0
            total_fees = 0.0

        # Format entry timestamp
        entry_ts_str = to_datetime_str(to_seconds(pos['entry_timestamp']))

        # Build expander title
        title = (
            f"▶ {entry_ts_str} | {token_flow} | {protocol_pair} | "
            f"Entry {entry_apr:.2f}% | Current {current_apr:.2f}% | Net APR {realized_apr:.2f}% | "
            f"Value ${current_value:,.2f} | PnL ${total_pnl:,.2f} | "
            f"Earnings ${total_earnings:,.2f} | Base ${base_earnings:,.2f} | "
            f"Rewards ${reward_earnings:,.2f} | Fees ${total_fees:,.2f}"
        )

        with st.expander(title, expanded=False):
            # Build 4-leg detail table (similar to Positions tab lines 2215-2333)
            detail_data = []

            # Leg 1: Protocol A - Lend token1
            detail_data.append({
                'Protocol': pos['protocol_a'],
                'Token': pos['token1'],
                'Action': 'Lend',
                'Weight': f"{pos['l_a']:.4f}",
                'Entry Rate (%)': f"{pos['entry_lend_rate_a'] * 100:.2f}",
                'Live Rate (%)': f"{get_rate(pos['token1'], pos['protocol_a'], 'lend_apr') * 100:.2f}",
                'Entry Price ($)': f"{pos['entry_price_token1']:.4f}",
                'Live Price ($)': f"{get_price_with_fallback(pos['token1'], pos['protocol_a']) or 0:.4f}",
                # ... more columns ...
            })

            # Leg 2: Protocol A - Borrow token2
            # ... similar structure ...

            # Leg 3: Protocol B - Lend token2
            # ... similar structure ...

            # Leg 4: Protocol B - Borrow token3
            # ... similar structure ...

            # Display detail table
            detail_df = pd.DataFrame(detail_data)
            st.dataframe(detail_df, use_container_width=True)

            # Strategy Summary metrics (similar to Positions tab lines 2348-2371)
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                pnl_pct = (total_pnl / deployment * 100) if deployment > 0 else 0
                st.metric("Total PnL", f"${total_pnl:,.2f}", f"{pnl_pct:.2f}%")
            with col2:
                earnings_pct = (total_earnings / deployment * 100) if deployment > 0 else 0
                st.metric("Total Earnings", f"${total_earnings:,.2f}", f"{earnings_pct:.2f}%")
            # ... more metrics ...
```

### Step 4: Keep Portfolio-Level Actions

```python
    # Portfolio-level actions (outside the position loop)
    if portfolio['portfolio_id'] is not None and not pd.isna(portfolio['portfolio_id']):
        # Real portfolio - show Delete/Close buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete Portfolio", key=f"delete_{portfolio['portfolio_id']}"):
                service.delete_portfolio(portfolio['portfolio_id'])
                st.success("Portfolio deleted")
                st.rerun()
        # ... Close button ...
    else:
        # Virtual portfolio
        st.info("These are standalone positions deployed individually. To manage, use the Positions tab.")
```

## Data Sources Reference

| Data | Source | Used For |
|------|--------|----------|
| positions | `service.get_portfolio_positions()` | Position records |
| position_statistics | `get_all_position_statistics()` | Pre-calculated PnL, APRs, earnings |
| position_rebalances | `get_all_rebalance_history()` | Rebalance history per leg |
| rates_snapshot | SQL query | Live rates, prices, fees |

## Code Sections to Reference

### From Positions Tab (`render_positions_table_tab`)
- **Lines 1270-1399**: Helper functions (get_rate, get_price, etc.)
- **Lines 1401-1562**: Rates snapshot loading and lookup dict building
- **Lines 1776-1779**: Expander title format
- **Lines 2215-2333**: 4-leg detail table construction
- **Lines 2348-2371**: Strategy summary metrics
- **Lines 2379-2449**: Styling functions (color_rate, color_liq_distance, etc.)

## Implementation Steps

1. **Read Positions tab code** for reference (lines 1164-2600)
2. **Modify render_portfolio_detail()** function
3. **Add data loading** (statistics, rebalances, rates snapshot)
4. **Copy helper functions** from Positions tab
5. **Replace simple table** with position expanders loop
6. **Build detail table** for each position (4 legs)
7. **Add strategy metrics** inside each expander
8. **Test with both portfolio types** (real portfolio + virtual "Single Positions")
9. **Verify consistency** with Positions tab numbers

## Testing Checklist

- [ ] Portfolio expander shows correct summary metrics in title
- [ ] Each position expands to show 4-leg detail table
- [ ] Numbers match what's shown in Positions tab
- [ ] Live rates/prices display correctly
- [ ] Liquidation distances calculated properly
- [ ] Rebalance data shows if applicable
- [ ] Action buttons work (Rebalance/Close individual positions)
- [ ] Portfolio Delete/Close buttons still work
- [ ] Virtual "Single Positions" portfolio displays correctly
- [ ] Performance is acceptable (batch loading, no N+1 queries)

## Notes

- This duplicates rendering logic from Positions tab
- Consider refactoring into shared helper function later
- Must maintain consistency between tabs
- Pre-calculated statistics are the source of truth
- Use same styling/coloring functions for consistency
