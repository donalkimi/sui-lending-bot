# Plan: Apply Positions Rendering to Portfolio Tab

## Context

**Problem**: The Portfolio tab currently shows only basic information when expanded - a simple table listing position metadata (tokens, protocols, deployment USD, entry APR, status). Users cannot see the detailed position breakdowns, statistics, earnings, or rebalance history.

**Goal**: Apply the same detailed rendering created today for the Positions tab to the Portfolio tab. When a user expands a portfolio row, they should see each position rendered with:
- Full position detail (same 4-leg table as Positions tab)
- Live statistics (PnL, earnings breakdowns, base/reward split)
- Rebalance history with segment summaries
- Liquidation distances and risk metrics
- Action buttons (contextual for portfolio positions)

**Why Now**: The positions rendering system was refactored today (Feb 11, 2026) into a reusable, pluggable architecture with `position_renderers.py`. This makes it perfect timing to integrate the same rendering into portfolio expanded views for consistency.

**Key Design Principle**: Reuse the existing `render_position_expander()` function from `position_renderers.py` rather than duplicating code. This ensures:
1. Consistency between Positions tab and Portfolio tab displays
2. Automatic support for multiple strategy types (via renderer registry)
3. Performance optimizations already implemented (batch loading, O(1) lookups)
4. Single source of truth for position rendering logic

---

## Implementation Approach

### Phase 1: Enhance Data Loading in Portfolio Tab

**File**: `dashboard/dashboard_renderer.py`
**Function**: `render_portfolios_tab()` (lines 3707-3897)

**Changes**:

1. **Pre-load position statistics for ALL portfolios** (batch optimization):
   ```python
   # After loading portfolios (around line 3740):

   # Collect all position IDs from all portfolios
   all_position_ids = []
   for _, portfolio in portfolios.iterrows():
       positions_df = portfolio_service.get_portfolio_positions(portfolio['portfolio_id'])
       all_position_ids.extend(positions_df['position_id'].tolist())

   # Batch load statistics for all positions in one query (existing pattern from Positions tab)
   all_stats = get_all_position_statistics(all_position_ids, timestamp_seconds, engine)

   # Batch load rebalance history for all positions in one query
   all_rebalances = get_all_rebalance_history(all_position_ids, conn)
   ```

2. **Build shared rate lookup and oracle prices** (once for entire tab):
   ```python
   # Load rates snapshot once
   rates_df = load_rates_snapshot(timestamp_seconds, conn, engine)

   # Build rate lookup dictionary (O(1) lookups, shared across all portfolios)
   rate_lookup_shared = build_rate_lookup(rates_df)

   # Build oracle prices dictionary
   oracle_prices_shared = build_oracle_prices(rates_df)
   ```

3. **Pass shared data to portfolio detail renderer**:
   - Modify `render_portfolio_detail()` signature to accept:
     - `all_stats` (dict: position_id → stats)
     - `all_rebalances` (dict: position_id → rebalances list)
     - `rate_lookup_shared` (dict: (protocol, token) → rate/price data)
     - `oracle_prices_shared` (dict: token → oracle price)
     - `service` (PositionService instance)

**Rationale**: This follows the same optimization pattern as the Positions tab - load all data once, share across all renderers, avoid N+1 queries.

---

### Phase 2: Refactor Portfolio Detail Rendering

**File**: `dashboard/dashboard_renderer.py`
**Function**: `render_portfolio_detail()` (lines 3900-3992)

**Current Implementation**:
- Shows simple table with columns: Token1, Token2, Token3, Protocol A, Protocol B, Deployment USD, Entry APR, Status
- No position statistics, no detail breakdown, no rebalance history

**New Implementation**:

1. **Replace simple table with position expanders**:
   ```python
   # After portfolio summary section (constraints, exposures, etc.):

   st.markdown("---")
   st.markdown("### 📊 Positions in Portfolio")

   # Get positions for this portfolio
   positions_df = portfolio_service.get_portfolio_positions(portfolio_id)

   if positions_df.empty:
       st.info("No positions in this portfolio")
       return

   # Create rate helper functions (reuse pattern from position_renderers.py)
   get_rate, get_borrow_fee, get_price_with_fallback = create_rate_helpers(
       rate_lookup_shared,
       oracle_prices_shared
   )

   # Render each position using shared renderer
   for idx, position in positions_df.iterrows():
       position_id = position['position_id']

       # Retrieve pre-loaded data
       stats = all_stats.get(position_id)
       rebalances = all_rebalances.get(position_id, [])

       # Determine strategy type (default to 'recursive_lending' if missing)
       strategy_type = position.get('strategy_type', 'recursive_lending')

       # Render using shared position expander
       render_position_expander(
           position=position,
           stats=stats,
           rebalances=rebalances,
           rate_lookup=rate_lookup_shared,
           oracle_prices=oracle_prices_shared,
           service=service,
           timestamp_seconds=timestamp_seconds,
           strategy_type=strategy_type,
           context='portfolio',           # <- Context for different action buttons
           portfolio_id=portfolio_id,      # <- Link back to parent portfolio
           expanded=False                  # <- Start collapsed
       )
   ```

2. **Handle missing strategy_type gracefully**:
   - Default to `'recursive_lending'` for existing positions
   - Add validation to check if strategy_type is registered
   - Show warning if strategy_type unknown

3. **Keep existing portfolio-level actions**:
   - Portfolio delete/close buttons stay at portfolio level
   - Position-level actions (rebalance, close position) rendered within each position expander

**Rationale**: This reuses all the rendering logic from the Positions tab without duplication, ensuring consistency and maintainability.

---

### Phase 3: Context-Aware Position Actions

**File**: `dashboard/position_renderers.py`
**Function**: `render_position_expander()` (lines 1227-1371)

**Enhancement**: Add context awareness for position action buttons.

**Current Implementation**:
- Always shows "Rebalance" and "Close Position" buttons
- No differentiation between standalone positions vs portfolio positions

**New Implementation**:

1. **Add portfolio context handling** in action button section (around lines 575-602):
   ```python
   # After segment summaries, before rebalance history:

   if context == 'portfolio':
       # Portfolio context: Show position actions with portfolio awareness
       col1, col2, col3 = st.columns(3)
       with col1:
           if st.button("🔄 Rebalance", key=f"rebal_{position['position_id']}"):
               st.info(f"Rebalancing position in portfolio {portfolio_id}")
               # Existing rebalance logic...
       with col2:
           if st.button("❌ Close Position", key=f"close_{position['position_id']}"):
               st.warning("This will remove position from portfolio and close it")
               # Existing close logic...
       with col3:
           if st.button("📤 Remove from Portfolio", key=f"remove_{position['position_id']}"):
               # Set portfolio_id to NULL (move to standalone)
               # Update positions table: SET portfolio_id = NULL WHERE position_id = ...
               st.success(f"Position moved to standalone positions")

   elif context == 'standalone':
       # Standalone context: Existing buttons (no portfolio-specific actions)
       # Current implementation unchanged
   ```

2. **Add visual indicator for portfolio positions**:
   - Show small badge/tag indicating which portfolio the position belongs to
   - Use different background color or border for portfolio positions

**Rationale**: Different contexts require different actions - portfolio positions can be removed from portfolio without closing, standalone positions have simpler workflow.

---

### Phase 4: Handle Strategy Type Population

**Consideration**: Existing positions may not have `strategy_type` populated in the database.

**Solutions**:

**Option A: Infer from position structure** (Recommended)
```python
def infer_strategy_type(position):
    """Infer strategy type from position data."""
    # Check for 4-leg structure (l_a, b_a, l_b, b_b)
    if all(pd.notna(position.get(leg)) for leg in ['l_a', 'b_a', 'l_b', 'b_b']):
        return 'recursive_lending'

    # Future: Check for funding rate arb structure
    # if 'perp_contract' in position:
    #     return 'funding_rate_arb'

    # Default fallback
    return 'recursive_lending'
```

**Option B: Database migration** (If needed for cleaner architecture)
```sql
-- Add strategy_type column if not exists
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS strategy_type TEXT DEFAULT 'recursive_lending';

-- Backfill existing positions
UPDATE positions
SET strategy_type = 'recursive_lending'
WHERE strategy_type IS NULL
  AND l_a IS NOT NULL
  AND b_a IS NOT NULL;
```

**Recommendation**: Start with Option A (inference) for immediate implementation, consider Option B as a future enhancement for cleaner data model.

---

## Critical Files to Modify

### 1. `dashboard/dashboard_renderer.py`

**Changes**:
- **`render_portfolios_tab()`** (lines 3707-3897)
  - Add batch loading for all position statistics
  - Add batch loading for all rebalance history
  - Build shared rate lookup and oracle prices
  - Pass shared data to `render_portfolio_detail()`

- **`render_portfolio_detail()`** (lines 3900-3992)
  - Replace simple position table with `render_position_expander()` calls
  - Create rate helper functions from shared lookups
  - Add strategy_type inference/handling
  - Keep existing portfolio-level actions

**Estimated Changes**: ~100 lines modified, ~80 lines added

---

### 2. `dashboard/position_renderers.py`

**Changes**:
- **`render_position_expander()`** (lines 1227-1371)
  - Add context-aware action buttons for `context='portfolio'`
  - Add "Remove from Portfolio" button for portfolio positions
  - Add visual indicator for portfolio context

**Estimated Changes**: ~40 lines added (new conditional block for portfolio actions)

---

### 3. `analysis/portfolio_service.py` (Optional Enhancement)

**Potential Addition**:
- **`remove_position_from_portfolio(position_id)`**
  ```python
  def remove_position_from_portfolio(self, position_id: str) -> bool:
      """Move position from portfolio to standalone (set portfolio_id = NULL)."""
      query = """
      UPDATE positions
      SET portfolio_id = NULL,
          updated_at = CURRENT_TIMESTAMP
      WHERE position_id = ?
      """
      self.cursor.execute(query, (position_id,))
      self.conn.commit()
      return True
  ```

**Estimated Changes**: ~15 lines added (optional, can be done inline if simpler)

---

## Implementation Steps

### Step 1: Add Helper Functions (if missing)
- Verify `build_rate_lookup()` exists in `position_renderers.py` (line 140)
- Verify `build_oracle_prices()` exists in `position_renderers.py` (line 162)
- Verify `create_rate_helpers()` exists in `position_renderers.py` (line 180)
- If missing, copy from Positions tab implementation

### Step 2: Modify Portfolio Tab Data Loading
1. Open `dashboard/dashboard_renderer.py`
2. Find `render_portfolios_tab()` function (line 3707)
3. After loading portfolios, add batch loading for:
   - All position IDs from all portfolios
   - Position statistics via `get_all_position_statistics()`
   - Rebalance history via `get_all_rebalance_history()`
4. Build `rate_lookup_shared` and `oracle_prices_shared`

### Step 3: Refactor Portfolio Detail Rendering
1. Find `render_portfolio_detail()` function (line 3900)
2. Update function signature to accept shared data:
   - `all_stats`, `all_rebalances`, `rate_lookup_shared`, `oracle_prices_shared`, `service`
3. Replace simple position table (lines 3930-3956) with loop calling `render_position_expander()`
4. Add strategy_type inference logic

### Step 4: Add Context-Aware Actions
1. Open `dashboard/position_renderers.py`
2. Find action button section in `render_position_expander()` (around line 575)
3. Add conditional for `context == 'portfolio'` with portfolio-specific buttons
4. Implement "Remove from Portfolio" button logic

### Step 5: Test End-to-End
1. Create test portfolio with 2-3 positions
2. Expand portfolio row
3. Verify each position shows:
   - Full 4-leg detail table
   - Statistics (PnL, earnings, base/reward split)
   - Rebalance history (if any)
   - Action buttons (Rebalance, Close, Remove from Portfolio)
4. Test "Remove from Portfolio" button
5. Verify performance (should be fast due to batch loading)

---

## Verification & Testing

### Test Cases

**Test 1: Portfolio with Multiple Positions**
- Create portfolio with 3 positions
- Expand portfolio row
- Verify each position shows detailed rendering
- Check that statistics match Positions tab for same positions

**Test 2: Portfolio with Rebalanced Positions**
- Use portfolio containing positions with rebalance history
- Expand portfolio, expand position
- Verify rebalance history displays correctly
- Compare to Positions tab rendering for consistency

**Test 3: Portfolio Actions**
- Test "Remove from Portfolio" button
- Verify position moves to "Single Positions" virtual portfolio
- Verify position retains all data (stats, history)

**Test 4: Performance**
- Load portfolio with 10+ positions
- Measure rendering time
- Should be <2 seconds (batch loading optimizations)

**Test 5: Missing Data Handling**
- Test portfolio with position missing statistics
- Verify "Calculate Statistics" button appears
- Test calculation and display

**Test 6: Context Differentiation**
- Compare action buttons in Positions tab vs Portfolio tab
- Verify "Remove from Portfolio" only appears in portfolio context
- Verify all other rendering is identical

---

## Edge Cases to Handle

1. **Empty portfolios**: Show "No positions in this portfolio" message
2. **Missing strategy_type**: Default to 'recursive_lending' with inference
3. **Missing statistics**: Show "Calculate Statistics" button (existing pattern)
4. **Missing rebalances**: Render position with entry data only (existing pattern)
5. **Missing rates/prices**: Use oracle fallback, then "N/A" (existing pattern)
6. **Closed positions in portfolio**: Show with grayed out styling, no action buttons
7. **Future rebalances**: Disable rebalance button with time-travel warning (existing pattern)

---

## Expected Outcome

After implementation:

1. **Portfolios tab enhanced** - Expanding a portfolio shows detailed position breakdowns
2. **Consistent rendering** - Positions look identical in both Positions tab and Portfolio tab
3. **Performance maintained** - Batch loading ensures fast rendering even with many positions
4. **Context-aware actions** - Portfolio positions have additional "Remove from Portfolio" option
5. **Zero code duplication** - Reuses existing `render_position_expander()` function
6. **Future-proof** - Automatically supports new strategy types via renderer registry

**User Benefit**: Users can now see complete position details (earnings, PnL, liquidation risk, rebalance history) directly within their portfolio view, without switching tabs.

---

## Rollback Plan

If issues arise:

1. **Phase 1 rollback**: Remove batch loading additions, use old on-demand loading
2. **Phase 2 rollback**: Restore simple position table in `render_portfolio_detail()`
3. **Phase 3 rollback**: Remove portfolio context handling from `render_position_expander()`

The changes are modular and can be reverted incrementally without affecting other parts of the system.

---

## Future Enhancements (Out of Scope)

1. **Portfolio-level rebalancing**: Rebalance all positions in portfolio at once
2. **Portfolio-level statistics**: Aggregate statistics table for entire portfolio
3. **Compare portfolios**: Side-by-side comparison of multiple portfolios
4. **Portfolio charts**: Visualize portfolio composition and performance over time
5. **Export portfolio**: Download portfolio details as CSV/PDF

These can be added later without modifying the core position rendering integration.
