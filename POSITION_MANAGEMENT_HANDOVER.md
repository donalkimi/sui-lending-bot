# Position Management Framework - Implementation Handover

## Quick Reference

| Step | Feature | Status | Date | Lines Added |
|------|---------|--------|------|-------------|
| **Steps 1-4** | Core Position Management | ✅ **COMPLETE** | Prior | Database schema, PositionService, Deploy button, Positions tab |
| **Step 5** | Snapshot Automation | ✅ **COMPLETE** | 2026-01-14 | ~100 lines |
| **Step 6** | PnL Calculation (Leg-level) | ✅ **COMPLETE** | 2026-01-14 | ~250 lines |
| **Step 7** | Risk Metrics | ✅ **COMPLETE** | 2026-01-14 | ~150 lines |
| **Step 8** | Collateralization Validation | ✅ **COMPLETE** | 2026-01-14 | ~50 lines |

**Implementation Status:** ✅ **ALL STEPS (5-8) COMPLETE**
**Testing Status:** ⏸️ **PENDING** (Sui chain down - awaiting testing)

**Total Implemented:** ~650 lines across Steps 6-8 (Step 5 was ~100 lines)

---

## 🔴 TESTING REQUIRED - ALL STEPS (1-8)

**IMPORTANT:** All Steps 1-8 need testing when Sui chain is back online. The position management framework has been fully implemented but **NOT YET TESTED** with actual data.

### Testing Status by Step

| Step | Component | Implementation | Testing Status |
|------|-----------|----------------|----------------|
| **Steps 1-4** | Database Schema, Position Service Core, Deploy Integration | ✅ Code Complete | ⏸️ **UNTESTED** |
| **Step 5** | Snapshot Automation (hourly + global button) | ✅ **COMPLETE** | ⏸️ **NEEDS TESTING** |
| **Step 6** | Leg-Level PnL Calculation | ✅ **COMPLETE** | ⏸️ **NEEDS TESTING** |
| **Step 7** | Risk Metrics Calculation | ✅ **COMPLETE** | ⏸️ **NEEDS TESTING** |
| **Step 8** | Collateralization Validation | ✅ **COMPLETE** | 2026-01-14 | ⚠️ **NEEDS TESTING** |

**Implementation Date:** 2026-01-14
**Current Status:** All Steps 5-8 implemented, awaiting Sui chain availability for testing

---

# Testing Requirements

## Prerequisites for Testing
- **Sui chain must be operational** (currently down)
- Database schema must be applied/migrated
- Existing positions table may need migration for leg-level prices (`entry_price_2A`, `entry_price_2B`)

## Steps 1-4 Status
According to the original handover plan, Steps 1-4 covered:
- **Step 1:** Database schema design
- **Step 2:** PositionService core methods
- **Step 3:** Deploy button integration
- **Step 4:** Positions tab UI skeleton

**Status:** These appear to be partially implemented based on existing code in:
- `data/schema.sql` - Schema exists with positions and position_snapshots tables
- `analysis/position_service.py` - Core methods implemented
- `dashboard/streamlit_app.py` - Positions tab exists with deploy functionality

**Testing Needed for Steps 1-4:**
- [ ] Verify database schema is fully applied
- [ ] Test position creation from "All Strategies" tab
- [ ] Verify position records are correctly stored
- [ ] Confirm position display in Positions tab

## Steps 5-8 Testing (NEW IMPLEMENTATION)

### Step 5: Snapshot Automation - Testing Checklist

#### Automatic Hourly Snapshots
- [ ] Deploy a test paper position
- [ ] Verify scheduler calls `refresh_pipeline()` at non-hour times (e.g., 15:15, 30:30)
- [ ] Confirm NO position snapshots created at non-hour times (only rates snapshots)
- [ ] Wait for next hour mark (e.g., 16:00, 17:00)
- [ ] Verify scheduler calls `refresh_pipeline(create_position_snapshots=True)`
- [ ] Confirm position snapshot created with timestamp aligned to rates_snapshot
- [ ] Verify subsequent hourly cycles continue creating snapshots
- [ ] Check database: `SELECT * FROM position_snapshots ORDER BY snapshot_timestamp DESC LIMIT 10`

#### Manual Global Snapshot Button
- [ ] Deploy 2-3 test paper positions
- [ ] Navigate to Positions tab
- [ ] Click "📸 Snapshot All" button
- [ ] Verify spinner displays during processing
- [ ] Verify success message shows correct count (e.g., "Created 3 snapshots")
- [ ] Verify position cards refresh to show new snapshot data
- [ ] Check database: Verify all positions have snapshots with same timestamp

#### Error Handling
- [ ] Test with corrupted position data (if possible)
- [ ] Verify error displayed but other positions still snapshot successfully
- [ ] Verify pipeline doesn't crash if automatic snapshots fail
- [ ] Check logs for appropriate error messages

---

### Step 6: PnL Calculation (Leg-Level) - Testing Checklist

#### Leg-Level Price Storage
- [ ] Create a new position after implementation
- [ ] Verify entry prices stored for all legs:
  - `entry_price_1A` (Token1 in Protocol A)
  - `entry_price_2A` (Token2 in Protocol A)
  - `entry_price_2B` (Token2 in Protocol B)
  - `entry_price_3B` (Token3 in Protocol B, NULL if unlevered)
- [ ] Create snapshot and verify snapshot stores leg-level prices:
  - `price_1A`, `price_2A`, `price_2B`, `price_3B`

#### PnL Calculation Accuracy
- [ ] Deploy a levered position
- [ ] Wait for at least 2 snapshots (1 hour with automatic snapshots)
- [ ] Verify PnL breakdown shows all components:
  - Base APR (green if positive, red if negative)
  - Reward APR (green if positive, red if negative)
  - Price (Protocol A Lend - Token1) with % change
  - Price (Protocol A Borrow - Token2) with % change
  - Price (Protocol B Lend - Token2) with % change
  - Price (Protocol B Borrow - Token3) with % change (levered only)
  - Fees (red, showing cost)
- [ ] Verify all amounts sum to total PnL
- [ ] Check database: `SELECT pnl_price_leg1, pnl_price_leg2, pnl_price_leg3, pnl_price_leg4, total_pnl FROM position_snapshots WHERE position_id = 'xxx'`

#### Hedge Validation Display
- [ ] For levered position, verify "Hedge Validation" section displays:
  - Net Token2 Hedge value (green if |value| < $1, orange otherwise)
  - Borrow exposure breakdown
  - Lend exposure breakdown
  - Explanatory note about drift
- [ ] Verify hedge starts near $0 at entry
- [ ] Monitor hedge drift over time as rates compound differently

#### Active vs Closed Position Handling
- [ ] Create position and wait for multiple snapshots
- [ ] Verify PnL updates in real-time using "now" for active positions
- [ ] Close position
- [ ] Verify PnL becomes fixed after closure
- [ ] Verify closed position doesn't include final snapshot rates in calculation

#### Unlevered Position Handling
- [ ] Deploy an unlevered position
- [ ] Verify PnL shows only 3 price legs (no Leg 4)
- [ ] Verify no Protocol B borrow metrics shown
- [ ] Verify `pnl_price_leg4` is NULL or 0 in database

---

### Step 7: Risk Metrics - Testing Checklist

#### Health Factor Calculation
- [ ] Create position and generate snapshot
- [ ] Verify health factors displayed for both protocols:
  - Protocol A health factor
  - Protocol B health factor (if levered)
- [ ] Verify color coding:
  - Green (> 1.5) with "✅ Safe"
  - Orange (1.2-1.5) with "⚠️ Caution"
  - Red (< 1.2) with "⚠️ Danger"
- [ ] Check database: `SELECT health_factor_1A_calc, health_factor_2B_calc FROM position_snapshots WHERE position_id = 'xxx'`

#### LTV (Loan-to-Value) Display
- [ ] Verify LTV percentages displayed for both protocols
- [ ] Verify LTV = borrow_value / collateral_value
- [ ] Manual calculation check:
  - Protocol A LTV = (B_A * price_2A) / (L_A * price_1A)
  - Protocol B LTV = (B_B * price_3B) / (L_B * price_2B) if levered

#### Distance to Liquidation
- [ ] Verify distance to liquidation displayed as percentage
- [ ] Verify calculation: (max_ltv - current_ltv) / max_ltv
- [ ] Verify distance decreases if prices move against position

#### Liquidation Price Calculation
- [ ] Verify liquidation prices displayed for both protocols
- [ ] Verify shows token symbol (e.g., "Liquidation Price (SUI): $1.2345")
- [ ] Manual verification: Price at which LTV would hit liquidation threshold
- [ ] For unlevered positions, verify Protocol B shows "No borrow"

#### Database Storage
- [ ] Verify all risk metrics stored in position_snapshots:
  - `ltv_1A_calc`, `ltv_2B_calc`
  - `liquidation_price_1A_calc`, `liquidation_price_2B_calc`
  - `distance_to_liq_1A_calc`, `distance_to_liq_2B_calc`
  - `health_factor_1A_calc`, `health_factor_2B_calc`
- [ ] Verify `risk_data_source` = 'calculated' (Phase 1)

---

### Step 8: Collateralization Validation - Testing Checklist

#### Entry Collateral Ratio Storage
- [ ] Create new position
- [ ] Verify entry collateral ratios stored:
  - `entry_collateral_ratio_1A` in positions table
  - `entry_collateral_ratio_2B` in positions table
- [ ] Check database: `SELECT entry_collateral_ratio_1A, entry_collateral_ratio_2B FROM positions WHERE position_id = 'xxx'`

#### Collateral Ratio Drift Tracking
- [ ] Create position with known collateral ratios
- [ ] Generate multiple snapshots over time
- [ ] Verify each snapshot stores:
  - `collateral_ratio_change_1A` (% change from entry)
  - `collateral_ratio_change_2B` (% change from entry)
  - `collateral_warning` (TRUE if |change| > 5%)

#### Drift Warning Display
- [ ] Simulate or wait for collateral ratio change > 5%
- [ ] Verify warning appears in Risk Metrics section:
  - "⚠️ Collateral ratio changed X.X% since entry"
  - Separate warnings for Protocol A and Protocol B
  - Warning color: orange/yellow
- [ ] Verify warning only appears when drift exceeds 5% threshold
- [ ] Verify warning displays for both protocols independently

#### Edge Cases
- [ ] Test with collateral ratio increasing (should warn)
- [ ] Test with collateral ratio decreasing (should warn)
- [ ] Test with drift exactly 5% (should warn at boundary)
- [ ] Test with drift exactly 4.9% (should NOT warn)
- [ ] Verify unlevered position: No Protocol B collateral warning

---

## Integration Testing

### End-to-End Position Lifecycle
- [ ] Deploy a levered position
- [ ] Wait for hourly automatic snapshot
- [ ] Manually create snapshot using "📸 Snapshot All"
- [ ] Verify PnL updates correctly with both snapshots
- [ ] Verify risk metrics update with each snapshot
- [ ] Monitor position for several hours/days
- [ ] Verify collateral drift warnings appear if thresholds exceeded
- [ ] Close position
- [ ] Verify final snapshot created
- [ ] Verify PnL and risk metrics frozen at closure
- [ ] Verify position status = 'closed' in database

### Multiple Position Portfolio Testing
- [ ] Deploy 3-5 positions (mix of levered/unlevered)
- [ ] Click "📸 Snapshot All"
- [ ] Verify all positions snapshotted simultaneously
- [ ] Verify portfolio summary updates correctly
- [ ] Close one position, keep others active
- [ ] Verify only active positions continue receiving snapshots

### Backward Compatibility
- [ ] If old positions exist without leg-level prices:
  - Verify fallback logic works (uses `price_2` for `price_2A` and `price_2B`)
  - Verify no crashes or errors
  - Verify PnL calculation still runs (may be less accurate)
- [ ] Test migration path for existing positions

---

## Database Validation Queries

### Verify Schema Applied
```sql
-- Check positions table has leg-level price columns
PRAGMA table_info(positions);
-- Should show: entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B

-- Check position_snapshots has all new columns
PRAGMA table_info(position_snapshots);
-- Should show: price_1A, price_2A, price_2B, price_3B
-- Should show: pnl_price_leg1, pnl_price_leg2, pnl_price_leg3, pnl_price_leg4
-- Should show: ltv_1A_calc, ltv_2B_calc, liquidation_price_1A_calc, liquidation_price_2B_calc
```

### Verify Data Integrity
```sql
-- Check position snapshots have complete data
SELECT
    position_id,
    snapshot_timestamp,
    price_1A, price_2A, price_2B, price_3B,
    pnl_price_leg1, pnl_price_leg2, pnl_price_leg3, pnl_price_leg4,
    health_factor_1A_calc, ltv_1A_calc, liquidation_price_1A_calc,
    collateral_ratio_change_1A, collateral_warning
FROM position_snapshots
ORDER BY snapshot_timestamp DESC
LIMIT 10;

-- Verify PnL components sum correctly
SELECT
    position_id,
    snapshot_timestamp,
    total_pnl,
    (pnl_base_apr + pnl_reward_apr + pnl_price_leg1 + pnl_price_leg2 +
     pnl_price_leg3 + COALESCE(pnl_price_leg4, 0) + pnl_fees) as calculated_total,
    ABS(total_pnl - (pnl_base_apr + pnl_reward_apr + pnl_price_leg1 + pnl_price_leg2 +
     pnl_price_leg3 + COALESCE(pnl_price_leg4, 0) + pnl_fees)) as difference
FROM position_snapshots
WHERE ABS(total_pnl - (pnl_base_apr + pnl_reward_apr + pnl_price_leg1 + pnl_price_leg2 +
     pnl_price_leg3 + COALESCE(pnl_price_leg4, 0) + pnl_fees)) > 0.01
ORDER BY difference DESC;
-- Should return 0 rows (perfect summation)
```

---

## Known Limitations & Future Work

### Phase 1 Limitations (Current Implementation)
- **No real-time rate queries**: Snapshots use placeholder entry rates (TODO: Query rates_snapshot)
- **No protocol-sourced metrics**: Risk calculations are computed only (no SDK calls)
- **Single-user only**: Multi-user filtering ready but untested
- **No backfill utility**: Must manually call `backfill_snapshots()` if needed

### Phase 2 Enhancements (Not Implemented)
- Query actual rates from rates_snapshot at snapshot time
- Add protocol API calls for health factor validation
- Implement AMM/oracle price sources (Cetus, Pyth, CoinGecko)
- Multi-user support with proper user authentication
- Automated backfilling for missed snapshots
- Alerting system for collateral ratio warnings
- Position rebalancing recommendations

---

## Troubleshooting Common Issues

### Snapshots Not Creating
- **Check:** Is `create_position_snapshots=True` being passed to `refresh_pipeline()`?
- **Check:** Are there active positions? (`SELECT * FROM positions WHERE status = 'active'`)
- **Check:** Logs for price fetching errors (fallback to entry prices should occur)

### PnL Calculation Errors
- **Issue:** "No price found for X on Y"
  - **Solution:** Verify rates_snapshot has data for that token/protocol
  - **Workaround:** Will fallback to entry prices automatically
- **Issue:** PnL components don't sum correctly
  - **Solution:** Check for NULL values in price legs (use COALESCE)

### Risk Metrics Show Inf or 0
- **Issue:** Health factor = Inf
  - **Expected:** Normal for unlevered positions (no borrow)
  - **Check:** Verify borrow amounts > 0 for levered positions
- **Issue:** Liquidation price = 0
  - **Check:** Verify collateral ratios and multipliers > 0

### UI Not Showing Data
- **Issue:** PnL section missing
  - **Check:** Does position have at least one snapshot?
  - **Check:** Browser console for JavaScript errors
- **Issue:** Risk metrics not displaying
  - **Check:** Verify latest snapshot has `health_factor_1A_calc` populated
  - **Check:** Database query: `SELECT * FROM position_snapshots WHERE position_id = 'xxx' ORDER BY snapshot_timestamp DESC LIMIT 1`

---

## Success Criteria

Implementation is considered fully tested and working when:

- [ ] All Steps 5-8 testing checklists completed without errors
- [ ] At least one complete position lifecycle tested (deploy → multiple snapshots → close)
- [ ] PnL calculations verified against manual calculations (within 1% tolerance)
- [ ] Risk metrics color coding displays correctly for all thresholds
- [ ] Collateral drift warnings trigger appropriately at >5% threshold
- [ ] Database integrity queries return expected results
- [ ] No crashes or unhandled exceptions in logs
- [ ] UI displays are clear, accurate, and user-friendly

---

**Status:** Implementation complete, **awaiting Sui chain availability for testing**

**Next Actions When Chain is Available:**
1. Apply/migrate database schema if needed
2. Start with Step 5 testing (snapshot automation)
3. Progress through Steps 6-8 testing checklists
4. Document any bugs or issues found
5. Perform integration testing with real positions
6. Validate against success criteria

---

# Step 5 Enhancement: Snapshot Automation with Scheduler Parameter & Global Button

## Implementation Status: ✅ COMPLETE

**Date Implemented:** 2026-01-14

## Overview
Enhance Step 5 of the Position Management Framework to add:
1. **Scheduler parameter** to enable hourly automatic snapshots
2. **Global "📸 Snapshot All" button** in Positions tab

## Context from Handover Plan
- **Original Step 5:** Lazy snapshots by default (only on position open/close/manual)
- **Optional Enhancement:** Commented-out code for automatic hourly snapshots
- **User Request:** Add scheduler parameter + global snapshot button for all open positions
- **Implementation Decision:** Scheduler parameter approach (not config flag) for explicit control

## Critical Files to Modify

### Modified Files
- **Scheduler file** (e.g., `main.py` or cron script) - Pass `create_position_snapshots` flag on the hour
- `data/refresh_pipeline.py` - Add `create_position_snapshots` parameter and snapshot logic
- `dashboard/positions_tab.py` - Add global "Create Snapshots for All" button
- `analysis/position_service.py` - Add `create_snapshots_for_all_positions()` method

## Implementation Plan

### Part 1: Scheduler Integration - Hourly Position Snapshots
**Approach:** Modify the **scheduler** to call `refresh_pipeline()` with a `create_position_snapshots=True` flag on the hour.

#### Option A: Scheduler-Level Control (RECOMMENDED)
**File:** The scheduler that calls `refresh_pipeline()` (likely `main.py` or a cron script)

**Current pattern:** Scheduler calls `refresh_pipeline()` every 15 minutes

**New pattern:** Scheduler passes flag on the hour
```python
# Scheduler logic (every 15 min)
current_time = datetime.now()

# Create position snapshots only on the hour
create_snapshots = (current_time.minute == 0)

refresh_pipeline(
    timestamp=current_time,
    create_position_snapshots=create_snapshots  # NEW PARAMETER
)
```

**Benefits:**
- Separation of concerns: scheduler controls frequency, pipeline executes
- No conditional logic inside pipeline (cleaner)
- Easy to test: just pass `create_position_snapshots=True` manually
- Aligns with existing pattern: pipeline already accepts `save_snapshots` parameter

---

#### Option B: Pipeline-Level Control (if scheduler can't be modified)
**File:** `data/refresh_pipeline.py`

**Location:** Modify function signature (line 52)

**Add new parameter:**
```python
def refresh_pipeline(
    *,
    timestamp: Optional[datetime] = None,
    stablecoin_contracts=STABLECOIN_CONTRACTS,
    liquidation_distance: float = settings.DEFAULT_LIQUIDATION_DISTANCE,
    save_snapshots: bool = settings.SAVE_SNAPSHOTS,
    create_position_snapshots: bool = False,  # NEW: Default False (manual control)
) -> RefreshResult:
```

**Location:** After line 88 (`tracker.save_snapshot(...)` completes)

**Add position snapshot logic:**
```python
# Line 89-90 (existing code)
tracker.upsert_token_registry(lend_rates, borrow_rates)

# NEW CODE: Position snapshot automation (Lines 91-110)
if create_position_snapshots:
    try:
        from analysis.position_service import PositionService

        # Use same connection as RateTracker
        position_service = PositionService(tracker.conn)
        active_positions = position_service.get_active_positions()

        logger.info(f"Creating snapshots for {len(active_positions)} active positions")

        for _, position in active_positions.iterrows():
            try:
                snapshot_id = position_service.create_snapshot(
                    position['position_id'],
                    snapshot_timestamp=ts  # Use same timestamp as rates_snapshot
                )
                logger.debug(f"Created snapshot {snapshot_id} for position {position['position_id']}")
            except Exception as e:
                logger.error(f"Failed to create snapshot for {position['position_id']}: {e}")
                # Continue to next position - don't block pipeline

    except Exception as e:
        logger.error(f"Position snapshot automation failed: {e}")
        # Don't raise - snapshot failures shouldn't break the pipeline
```

**Then scheduler calls it with:**
```python
# On the hour (minute == 0)
refresh_pipeline(create_position_snapshots=True)

# Every 15 min (minute != 0)
refresh_pipeline(create_position_snapshots=False)
```

**Key Design Decisions:**
1. **Explicit flag:** `create_position_snapshots` parameter controls execution (not config file)
2. **Scheduler decides frequency:** Passes `True` on the hour, `False` otherwise
3. **Same timestamp:** Pass `snapshot_timestamp=ts` to align with rates_snapshot timestamp
4. **Reuse tracker.conn:** No need to create new connection
5. **Error isolation:** Catch exceptions per-position and at outer level to prevent pipeline failures

**Benefits:**
- Pipeline receives rates data every 15 min (unchanged)
- Position snapshots created hourly (4x less frequent)
- Explicit control via parameter (no hidden config toggles)
- Easy to test: just pass `create_position_snapshots=True` manually
- Same timestamp alignment: both rates and position snapshots use same `ts`

---

### Part 2: Global Snapshot Button in Positions Tab
**File:** `dashboard/positions_tab.py` (NEW FILE - to be created in original plan)

**Location:** Top of positions tab layout (before position list rendering)

**Add global button section:**
```python
def render_positions_tab(position_service, conn):
    """Render the Positions tab with portfolio summary and position cards."""

    # Header with global action button
    col1, col2 = st.columns([4, 1])

    with col1:
        st.subheader("📄 Paper Trading Positions")

    with col2:
        if st.button("📸 Snapshot All",
                     key="create_all_snapshots",
                     help="Create snapshots for all active positions"):
            # Get all active positions
            active_positions = position_service.get_active_positions()

            if len(active_positions) == 0:
                st.warning("No active positions to snapshot")
            else:
                with st.spinner(f"Creating snapshots for {len(active_positions)} positions..."):
                    success_count = 0
                    error_count = 0

                    # Create snapshot for each active position
                    for _, position in active_positions.iterrows():
                        try:
                            position_service.create_snapshot(position['position_id'])
                            success_count += 1
                        except Exception as e:
                            st.error(f"Failed to snapshot {position['position_id']}: {str(e)}")
                            error_count += 1

                    # Show summary
                    if success_count > 0:
                        st.success(f"✅ Created {success_count} snapshot(s)")
                    if error_count > 0:
                        st.warning(f"⚠️ {error_count} snapshot(s) failed")

                    # Rerun to refresh display with new snapshots
                    st.rerun()

    st.markdown("---")

    # Rest of positions tab rendering (portfolio summary, position cards, etc.)
    # ... existing code from original plan ...
```

**Alternative Location Option:**
If `positions_tab.py` isn't created yet (original plan Step 4), add to `streamlit_app.py` at the top of the Positions tab section.

**Key Design Decisions:**
1. **Column layout:** Button aligned to the right next to tab header
2. **Batch processing:** Loop through all active positions with progress spinner
3. **Error handling:** Show per-position errors but continue processing all positions
4. **User feedback:** Display success/error counts after batch completes
5. **Auto-refresh:** Call `st.rerun()` to refresh position cards with new snapshots
6. **Help text:** Tooltip explains button purpose

**Benefits:**
- One-click snapshot creation for all positions
- Useful before closing app or for manual checkpoint creation
- Clear user feedback (spinner, success/error counts)
- Non-blocking errors (one failed snapshot doesn't prevent others)

---

### Part 3: Position Service Enhancement
**File:** `analysis/position_service.py` (NEW FILE - to be created in original plan)

**Add convenience method for global snapshot creation:**
```python
class PositionService:
    # ... existing methods from original plan ...

    def create_snapshots_for_all_positions(self, user_id=None, snapshot_timestamp=None):
        """
        Create snapshots for all active positions.

        Args:
            user_id: Optional user filter (None = all users, for multi-user support later)
            snapshot_timestamp: Optional timestamp (None = use latest rates_snapshot)

        Returns:
            dict: {
                'success_count': int,
                'error_count': int,
                'snapshot_ids': list[str],
                'errors': list[dict]  # {position_id, error_message}
            }
        """
        active_positions = self.get_active_positions(user_id=user_id)

        results = {
            'success_count': 0,
            'error_count': 0,
            'snapshot_ids': [],
            'errors': []
        }

        for _, position in active_positions.iterrows():
            try:
                snapshot_id = self.create_snapshot(
                    position['position_id'],
                    snapshot_timestamp=snapshot_timestamp
                )
                results['snapshot_ids'].append(snapshot_id)
                results['success_count'] += 1
            except Exception as e:
                results['errors'].append({
                    'position_id': position['position_id'],
                    'error_message': str(e)
                })
                results['error_count'] += 1

        return results
```

**Benefits:**
- Reusable method for both dashboard button and pipeline automation
- Structured error reporting
- Multi-user ready (accepts optional `user_id` filter)
- Can be used with specific timestamp for backfilling

---

## Implementation Order

1. **Step 1:** Add `create_snapshots_for_all_positions()` to `PositionService`
2. **Step 2:** Add `create_position_snapshots` parameter to `refresh_pipeline.py`
3. **Step 3:** Modify scheduler to pass `create_position_snapshots=True` on the hour
4. **Step 4:** Add global button to `positions_tab.py` or `streamlit_app.py`

---

## Verification Steps

### Test Automatic Hourly Snapshots
1. Deploy a paper position
2. Verify scheduler calls `refresh_pipeline(create_position_snapshots=False)` on 15/30/45 minute marks
3. Verify no position snapshots created (only rates snapshots)
4. Wait until next hour (XX:00)
5. Verify scheduler calls `refresh_pipeline(create_position_snapshots=True)`
6. Verify position snapshot created with timestamp aligned to rates_snapshot
7. Verify subsequent hourly cycles continue creating snapshots

### Test Global Button
1. Deploy 2-3 paper positions
2. Navigate to Positions tab
3. Click "📸 Snapshot All" button
4. Verify spinner displays with progress
5. Verify success message shows correct count (e.g., "Created 3 snapshots")
6. Verify position cards refresh to show new snapshot data
7. Check database: Verify new snapshots exist for all positions with same timestamp

### Test Error Handling
1. Deploy position
2. Manually corrupt position record (invalid token or protocol)
3. Click "📸 Snapshot All" button
4. Verify error displayed for corrupted position
5. Verify other positions still snapshot successfully
6. Verify pipeline doesn't crash if automatic snapshots fail

### Test Multi-User Compatibility (Future)
1. Add `user_id` to position records
2. Call `create_snapshots_for_all_positions(user_id='user1')`
3. Verify only user1's positions snapshotted
4. Call without `user_id` parameter
5. Verify all positions snapshotted

---

## Scheduler Control Pattern

**Default Behavior:**
- Every 15 min: `refresh_pipeline(create_position_snapshots=False)` - rates only
- On the hour: `refresh_pipeline(create_position_snapshots=True)` - rates + positions

**Storage Impact:**
- Manual snapshots only: ~0-10 snapshots per position (user controlled via button)
- Hourly automatic snapshots: ~24 snapshots per position per day
- Future enhancement: Daily snapshots (~1 per day)

**Benefits:**
- Explicit control at scheduler level (no hidden config)
- Easy to change frequency (modify scheduler logic)
- Easy to test (just pass `True` manually)

---

## Summary of Changes

| Component | Change Type | Lines Added | Purpose |
|-----------|-------------|-------------|---------|
| **Scheduler** (e.g., `main.py`) | Add hour check + flag | ~5 lines | Pass `create_position_snapshots=True` on hour |
| `data/refresh_pipeline.py` | Add parameter + automation | ~25 lines | Accept flag, create snapshots when `True` |
| `analysis/position_service.py` | Add batch method | ~30 lines | Reusable snapshot-all logic |
| `dashboard/positions_tab.py` | Add global button | ~40 lines | Manual batch snapshot UI |

**Total:** ~100 lines added

---

## Alignment with Original Plan

This enhancement:
- ✅ Preserves lazy/on-demand default behavior (Phase 1)
- ✅ Adds automatic hourly snapshots via scheduler flag (explicit control)
- ✅ Provides manual control via global button (user-initiated batch operation)
- ✅ Maintains error isolation (snapshot failures don't break pipeline/UI)
- ✅ Supports future multi-user filtering (user_id parameter ready)
- ✅ Aligns with existing pipeline patterns (`save_snapshots` parameter)
- ✅ No changes to Step 6-8 (PnL calculation, risk metrics, etc.)
- ✅ Simpler than config flag approach (scheduler controls frequency)

## Key Architectural Decision

**Why scheduler-level control instead of config flag?**

| Approach | Pros | Cons |
|----------|------|------|
| **Config flag** | Toggle without code change | Hidden behavior, harder to test |
| **Scheduler parameter** ✅ | Explicit control, easy to test, separation of concerns | Requires scheduler modification |

**Choice: Scheduler parameter** - aligns with your insight that the scheduler already calls `refresh_pipeline()` every 15 min with control over timing.

---

## Implementation Summary (2026-01-14)

### Files Modified

#### 1. `analysis/position_service.py` (Lines 602-646)
**Added:** `create_snapshots_for_all_positions()` method
- Batch processes all active positions
- Returns structured results: `{success_count, error_count, snapshot_ids, errors}`
- Non-blocking error handling (continues on individual failures)
- Multi-user ready (optional `user_id` parameter)

```python
def create_snapshots_for_all_positions(
    self,
    user_id: Optional[str] = None,
    snapshot_timestamp: Optional[datetime] = None
) -> Dict:
    # Implementation complete - see file for details
```

#### 2. `data/refresh_pipeline.py` (Lines 52-126)
**Added:** `create_position_snapshots` parameter to function signature
**Added:** Position snapshot automation logic (lines 100-126)
- Only runs if `create_position_snapshots=True` AND `save_snapshots=True`
- Uses same connection as RateTracker
- Uses same timestamp as rates_snapshot for alignment
- Error isolation - failures don't break pipeline

```python
def refresh_pipeline(
    *,
    timestamp: Optional[datetime] = None,
    stablecoin_contracts=STABLECOIN_CONTRACTS,
    liquidation_distance: float = settings.DEFAULT_LIQUIDATION_DISTANCE,
    save_snapshots: bool = settings.SAVE_SNAPSHOTS,
    create_position_snapshots: bool = False,  # NEW PARAMETER
) -> RefreshResult:
```

#### 3. `main.py` (Lines 1-23)
**Added:** Hour detection and flag passing
- Checks if `current_time.minute == 0`
- Passes `create_position_snapshots=True` on the hour
- Passes `timestamp=current_time` for consistency

```python
# Get current time
current_time = datetime.now()

# Create position snapshots only on the hour (Step 5 enhancement)
create_snapshots = (current_time.minute == 0)

if create_snapshots:
    print("⏰ On the hour - will create position snapshots")

# Run full refresh pipeline
result = refresh_pipeline(
    timestamp=current_time,
    save_snapshots=True,
    create_position_snapshots=create_snapshots,
)
```

#### 4. `dashboard/streamlit_app.py` (Lines 1433-1460)
**Added:** Global "📸 Snapshot All" button in Positions tab
- Positioned next to "Active Positions" header
- Displays progress spinner during batch operation
- Shows success/error counts with details
- Calls `st.rerun()` to refresh display after snapshot creation

```python
# Global snapshot button (Step 5 enhancement)
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown("### 📄 Active Positions")
with col2:
    if st.button("📸 Snapshot All", key="snapshot_all_positions",
                 help="Create snapshots for all active positions"):
        # Implementation complete - see file for details
```

### Verification Steps Completed

✅ **Code changes implemented** in all 4 files
✅ **Scheduler logic** added to main.py (hour detection)
✅ **Pipeline parameter** added to refresh_pipeline.py
✅ **Position service method** added for batch snapshot creation
✅ **Dashboard button** added to Positions tab

### Testing Required

- [ ] Deploy a test paper position
- [ ] Run `main.py` at non-hour time (e.g., 15:15) → Verify no position snapshots
- [ ] Run `main.py` at hour mark (e.g., 16:00) → Verify position snapshot created
- [ ] Click "📸 Snapshot All" button → Verify snapshots created and display refreshes
- [ ] Test error handling: Corrupt position → Verify error shown but other positions succeed
- [ ] Verify timestamp alignment: Position snapshots use same timestamp as rates_snapshot

### Known Limitations

1. **No cron/scheduler setup** - `main.py` must be called every 15 minutes by external scheduler
2. **Single-user only** - Multi-user filtering ready but not tested
3. **No backfill** - Only creates snapshots from implementation date forward

---

**Status:** Step 5 implementation complete. Ready for testing. Steps 6-8 remain unimplemented.

---

# Step 6 Review: PnL Calculation Algorithm

## Context from Handover Plan (Lines 298-425)

Step 6 defines the PnL calculation algorithm with 6 components:
1. Base APR (net lend/borrow rates, before fees)
2. Reward APR (protocol rewards)
3. Token price impacts (3 separate components)
4. Fees (one-time upfront costs)

## Critical Architecture Clarifications

### 1. "Current" vs "Now" Definition
- **"Now" = Latest snapshot timestamp in database** (not real-time)
- All PnL calculations are **snapshot-based only**
- No real-time price queries needed
- "Current PnL" = PnL as of the latest snapshot

### 2. Price Exposure Structure

**Original plan aggregates by token** (lines 380-403):
- Token1: `L_A - B_B` (collateral exposure)
- Token2: `L_B - B_A ≈ 0` (hedged)
- Token3: `-B_B` (short borrow)

**User clarification: Break down by LEG, not by token**:
- **Leg 1 (Protocol A lend):** Token1 exposure = `+L_A` (long collateral)
- **Leg 2 (Protocol A borrow):** Token2 exposure = `-B_A` (short borrow)
- **Leg 3 (Protocol B lend):** Token2 exposure = `+L_B` (long collateral)
- **Leg 4 (Protocol B borrow):** Token3 exposure = `-B_B` (short borrow, NULL if unlevered)

**Why leg-level breakdown matters:**
- More transparent (shows all 4 position legs separately)
- Easier debugging (can see which leg has price impact)
- Avoids aggregation confusion (Token2 appears in both protocols)
- Aligns with position sizing table display (4 rows for levered, 3 for unlevered)

### 3. Active Position PnL Calculation

**Question:** For active positions (no exit snapshot yet), how to calculate current PnL?

**Answer:** Use latest snapshot as the "current" point
- Loop through ALL snapshots (including latest)
- Apply forward-looking rates from each snapshot to the next
- For the latest snapshot: Apply rates to period from latest to "now"
- "Now" = time when PnL is being calculated (e.g., dashboard load time)

**Example timeline:**
```
Entry: 10:00 (snapshot_0)
  ↓ Apply snapshot_0 rates for 1 hour
Hour 1: 11:00 (snapshot_1)
  ↓ Apply snapshot_1 rates for 1 hour
Hour 2: 12:00 (snapshot_2 - latest)
  ↓ Apply snapshot_2 rates from 12:00 to NOW (e.g., 12:37)
NOW: 12:37 (no snapshot, just calculation time)
```

## Revised PnL Calculation Algorithm

### Structure Overview

```python
Total PnL = Base APR + Reward APR + Price_Leg1 + Price_Leg2 + Price_Leg3 + Price_Leg4 + Fees

Display:
Total PnL: $X
├── Base APR: +$Y (net of all lend/borrow base rates, BEFORE fees)
├── Reward APR: +$Z (net of all lend/borrow rewards)
├── Price Impact (Leg 1 - Protocol A Lend): +$A (Token1 exposure = +L_A)
├── Price Impact (Leg 2 - Protocol A Borrow): -$B (Token2 exposure = -B_A)
├── Price Impact (Leg 3 - Protocol B Lend): +$C (Token2 exposure = +L_B)
├── Price Impact (Leg 4 - Protocol B Borrow): -$D (Token3 exposure = -B_B, NULL if unlevered)
└── Fees: -$E (one-time upfront borrow fees)
```

### Component Calculations

#### 1. Base APR Earnings (Unchanged from original plan)
```python
# Loop through all snapshots (stop before final for CLOSED positions)
# For ACTIVE positions, loop through all including latest
total_base_apr_pnl = 0

snapshots = get_position_snapshots(position_id)  # Ordered by timestamp ASC
is_active = (position['status'] == 'active')

# For active positions, add implicit "now" snapshot
if is_active:
    now = datetime.now()  # Current time when calculating PnL
    loop_end = len(snapshots)  # Include all snapshots
else:
    loop_end = len(snapshots) - 1  # Stop before final (exit snapshot)

for i in range(loop_end):
    current_snap = snapshots[i]

    # For active positions, last iteration uses "now" as end time
    if is_active and i == len(snapshots) - 1:
        time_delta = now - current_snap['timestamp']
    else:
        next_snap = snapshots[i + 1]
        time_delta = next_snap['timestamp'] - current_snap['timestamp']

    time_years = time_delta.total_seconds() / (365 * 86400)

    # Forward-looking base rates from current snapshot
    base_lend_1A = current_snap['lend_base_apr_1A']
    base_borrow_2A = current_snap['borrow_base_apr_2A']
    base_lend_2B = current_snap['lend_base_apr_2B']
    base_borrow_3B = current_snap['borrow_base_apr_3B']  # NULL for unlevered

    # Calculate base earnings for this period (BEFORE fees)
    earn_A = deployment * L_A * base_lend_1A * time_years
    earn_B = deployment * L_B * base_lend_2B * time_years
    cost_A = deployment * B_A * base_borrow_2A * time_years
    cost_B = deployment * B_B * base_borrow_3B * time_years if B_B else 0

    period_base = earn_A + earn_B - cost_A - cost_B
    total_base_apr_pnl += period_base

PnL_base_apr = total_base_apr_pnl
```

#### 2. Reward APR Earnings (Unchanged from original plan)
```python
# Same loop structure as Base APR
# ... (code identical to original plan)
```

#### 3. Price Impact by Leg (REVISED)

```python
# Get latest snapshot (for active) or final snapshot (for closed)
if position['status'] == 'active':
    latest_snap = snapshots[-1]  # Latest snapshot
else:
    latest_snap = snapshots[-1]  # Exit snapshot

# Leg 1: Protocol A Lend (Token1 exposure)
# Exposure: +L_A (long Token1 collateral)
leg1_exposure_usd = deployment * L_A
price_change_leg1 = (latest_snap['price_1A'] - entry_price_1A) / entry_price_1A
PnL_price_leg1 = leg1_exposure_usd * price_change_leg1

# Leg 2: Protocol A Borrow (Token2 exposure)
# Exposure: -B_A (short Token2 borrow)
leg2_exposure_usd = -deployment * B_A
price_change_leg2 = (latest_snap['price_2A'] - entry_price_2A) / entry_price_2A
PnL_price_leg2 = leg2_exposure_usd * price_change_leg2

# Leg 3: Protocol B Lend (Token2 exposure)
# Exposure: +L_B (long Token2 collateral)
leg3_exposure_usd = deployment * L_B
price_change_leg3 = (latest_snap['price_2B'] - entry_price_2B) / entry_price_2B
PnL_price_leg3 = leg3_exposure_usd * price_change_leg3

# Leg 4: Protocol B Borrow (Token3 exposure, NULL for unlevered)
# Exposure: -B_B (short Token3 borrow)
if B_B:
    leg4_exposure_usd = -deployment * B_B
    price_change_leg4 = (latest_snap['price_3B'] - entry_price_3B) / entry_price_3B
    PnL_price_leg4 = leg4_exposure_usd * price_change_leg4
else:
    PnL_price_leg4 = 0  # Unlevered position has no leg 4

# Total price impact
PnL_price_total = PnL_price_leg1 + PnL_price_leg2 + PnL_price_leg3 + PnL_price_leg4

# Note: Token2 appears in both Leg 2 and Leg 3
# Net Token2 exposure = -B_A + L_B (should be ~0 if hedged)
```

#### 4. Fee Costs (Unchanged from original plan)
```python
# Fees paid at entry (one-time, not time-dependent)
fee_cost_2A = deployment * B_A * entry_borrow_fee_2A
fee_cost_3B = deployment * B_B * entry_borrow_fee_3B if B_B else 0
PnL_fees = -(fee_cost_2A + fee_cost_3B)
```

#### 5. Total PnL
```python
Total_PnL = (PnL_base_apr + PnL_reward_apr +
             PnL_price_leg1 + PnL_price_leg2 + PnL_price_leg3 + PnL_price_leg4 +
             PnL_fees)
```

## Key Design Decisions

1. **Leg-level price breakdown:** 4 separate price impact lines (not 3 aggregated by token)
2. **Snapshot-based only:** No real-time price queries, "current" = latest snapshot
3. **Active position handling:** Apply latest snapshot's rates to period from latest to "now"
4. **Closed position handling:** Stop loop before final snapshot (exit rates not applied)
5. **Token2 hedge validation:** Can verify hedge by checking `PnL_price_leg2 + PnL_price_leg3 ≈ 0`

## Database Schema Impact

**position_snapshots table needs to store leg-level price data:**

```sql
-- Current prices at snapshot time (one per token-protocol pair)
price_1A DECIMAL(20, 10),  -- Token1 price in Protocol A
price_2A DECIMAL(20, 10),  -- Token2 price in Protocol A
price_2B DECIMAL(20, 10),  -- Token2 price in Protocol B
price_3B DECIMAL(20, 10),  -- Token3 price in Protocol B (NULL for unlevered)

-- PnL breakdown stored in snapshots (pre-calculated for performance)
pnl_base_apr DECIMAL(20, 10),
pnl_reward_apr DECIMAL(20, 10),
pnl_price_leg1 DECIMAL(20, 10),  -- Protocol A Lend (Token1)
pnl_price_leg2 DECIMAL(20, 10),  -- Protocol A Borrow (Token2)
pnl_price_leg3 DECIMAL(20, 10),  -- Protocol B Lend (Token2)
pnl_price_leg4 DECIMAL(20, 10),  -- Protocol B Borrow (Token3, NULL if unlevered)
pnl_fees DECIMAL(20, 10),
total_pnl DECIMAL(20, 10)
```

## Display Format in UI

### Positions Tab - PnL Card Section

**With color coding and actual token symbols:**

```
Current Status & PnL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total PnL: +$127.45 (+12.75%)  [GREEN]
Time Elapsed: 3 days, 7 hours

PnL Breakdown:
├── Base APR:                 +$85.23   [GREEN]
├── Reward APR:               +$42.18   [GREEN]
├── Price (A Lend - SUI):     +$15.67  (SUI: +2.3%)   [GREEN]
├── Price (A Borrow - USDC):   -$3.21  (USDC: +1.1%)  [RED]
├── Price (B Lend - USDC):     +$2.89  (USDC: +1.1%)  [GREEN]
├── Price (B Borrow - suiUSDT): -$12.45 (suiUSDT: -5.2%) [RED]
└── Fees:                      -$2.86   [RED]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hedge Validation:
Net Token2 (USDC) Hedge: -$0.32 ✅ [GREEN - effectively hedged]
  ├── Borrow exposure (A): -$3.21
  └── Lend exposure (B):   +$2.89
  Note: Drift accumulates as rate differential compounds over time
```

**Color coding logic:**
```python
def get_pnl_color(value: float, component: str) -> str:
    """
    Return Streamlit color for PnL component.

    Args:
        value: PnL value in USD
        component: Component type ('total', 'hedge', 'price', 'apr', 'fees')

    Returns:
        str: Streamlit color class or markdown indicator
    """
    # Special case: Hedge validation (near-zero is good)
    if component == 'hedge':
        return 'green' if abs(value) < 1.0 else 'orange'

    # Fees are always costs (red), but not "bad"
    if component == 'fees':
        return 'red'  # Neutral red, just showing cost

    # Standard: positive = green, negative = red
    return 'green' if value >= 0 else 'red'
```

**Streamlit implementation:**
```python
# Example rendering
if pnl_component >= 0:
    st.markdown(f"├── Base APR: :green[+${abs(pnl_component):.2f}]")
else:
    st.markdown(f"├── Base APR: :red[-${abs(pnl_component):.2f}]")
```

## Verification Checklist

- [ ] Base APR calculation loops correctly for active vs closed positions
- [ ] Reward APR calculation handles NULL values for unlevered positions
- [ ] Price impact uses leg-level breakdown (4 lines, not 3)
- [ ] Token2 hedge check displayed: `PnL_price_leg2 + PnL_price_leg3`
- [ ] Hedge validation shows green when |value| < $1
- [ ] Fees are negative (cost) and displayed in red
- [ ] Total PnL sums all 7 components correctly
- [ ] "Now" uses `datetime.now()` at calculation time (not real-time prices)
- [ ] Snapshot prices stored correctly for all 4 legs
- [ ] Price helper function `get_pnl_price()` implemented
- [ ] Price helper uses protocol prices (Phase 1)
- [ ] Token symbols displayed (SUI/USDC/suiUSDT, not Token1/2/3)
- [ ] Color coding: green for positive, red for negative
- [ ] UI displays actual token symbols in price breakdown lines

## User Decisions - UI Display

1. **Net Token2 Hedge:** YES - Display as hedging test validation line
   - Starts at zero but drifts as rate differential accumulates
   - Formula: `PnL_price_leg2 + PnL_price_leg3`
   - Shows natural hedge degradation over time

2. **Token naming:** Use actual symbols (SUI/USDC/suiUSDT)
   - Not generic placeholders (Token1/2/3)
   - Display format: `Price (A Lend - SUI): +$15.67 (+2.3%)`

3. **Color coding:** YES - Red for negative, green for positive
   - Positive PnL components: Green
   - Negative PnL components: Red
   - Near-zero hedge: Green if |value| < $1

## Price Source for PnL Calculations

**Critical Design Decision:** PnL needs dedicated price helper function

### Architecture

**Future goal:** Use execution venue prices (Cetus AMM) or oracle prices (Pyth, CoinGecko)
- **Reason:** PnL should reflect where you'd actually trade (real liquidity)
- **Phase 2 consideration:** Add price source configuration (AMM vs Oracle)

**Phase 1 implementation:** Use protocol prices as proxy
- **Reason:** Simple, already available in rates_snapshot
- **Acceptable for paper trading:** Protocol prices are reasonable approximation
- **Plan for upgrade:** Price helper function isolates this logic

### Implementation: Price Helper Function

**File:** `analysis/position_service.py` or new `analysis/price_service.py`

```python
def get_pnl_price(token: str, protocol: str, timestamp: datetime = None) -> float:
    """
    Get price for PnL calculation purposes.

    Phase 1: Returns protocol-reported price from rates_snapshot
    Phase 2: Can be extended to query AMM (Cetus) or oracle (Pyth, CoinGecko)

    Args:
        token: Token symbol (e.g., 'SUI', 'USDC')
        protocol: Protocol name (e.g., 'navi', 'alphafi')
        timestamp: Optional timestamp (None = latest snapshot)

    Returns:
        float: Price in USD

    Design notes:
        - Centralizes price source logic for easy upgrade
        - Can add fallback chain: AMM -> Oracle -> Protocol
        - Can add price staleness checks
        - Can add multiple AMM averaging (TWAP, etc.)
    """
    # Phase 1: Query protocol price from rates_snapshot
    conn = get_db_connection()

    if timestamp:
        query = """
            SELECT price
            FROM rates_snapshot
            WHERE token = ? AND protocol = ? AND timestamp = ?
        """
        result = conn.execute(query, (token, protocol, timestamp)).fetchone()
    else:
        query = """
            SELECT price
            FROM rates_snapshot
            WHERE token = ? AND protocol = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """
        result = conn.execute(query, (token, protocol)).fetchone()

    conn.close()

    if result:
        return result['price']
    else:
        raise ValueError(f"No price found for {token} on {protocol} at {timestamp or 'latest'}")

    # Phase 2 enhancement (commented out for now):
    # try:
    #     # Option 1: Query Cetus AMM for execution price
    #     if settings.PNL_PRICE_SOURCE == 'cetus':
    #         return get_cetus_spot_price(token)
    #
    #     # Option 2: Query Pyth oracle
    #     elif settings.PNL_PRICE_SOURCE == 'pyth':
    #         return get_pyth_price(token)
    #
    #     # Option 3: Query CoinGecko
    #     elif settings.PNL_PRICE_SOURCE == 'coingecko':
    #         return get_coingecko_price(token)
    #
    #     # Fallback: Use protocol price
    #     else:
    #         return get_protocol_price(token, protocol, timestamp)
    #
    # except Exception as e:
    #     logger.warning(f"Failed to get {settings.PNL_PRICE_SOURCE} price for {token}: {e}")
    #     # Fallback to protocol price
    #     return get_protocol_price(token, protocol, timestamp)


def get_leg_price_for_pnl(position: dict, leg: str, snapshot: dict = None) -> float:
    """
    Get price for a specific position leg for PnL calculation.

    Args:
        position: Position record with token/protocol info
        leg: Leg identifier ('1A', '2A', '2B', '3B')
        snapshot: Optional snapshot record (uses latest if None)

    Returns:
        float: Price in USD for that leg

    Usage:
        price_1A = get_leg_price_for_pnl(position, '1A', latest_snapshot)
    """
    leg_config = {
        '1A': ('token1', 'protocol_A'),
        '2A': ('token2', 'protocol_A'),
        '2B': ('token2', 'protocol_B'),
        '3B': ('token3', 'protocol_B'),
    }

    if leg not in leg_config:
        raise ValueError(f"Invalid leg: {leg}")

    token_field, protocol_field = leg_config[leg]
    token = position[token_field]
    protocol = position[protocol_field]

    # If snapshot provided, use its timestamp
    timestamp = snapshot['timestamp'] if snapshot else None

    return get_pnl_price(token, protocol, timestamp)
```

### Usage in PnL Calculation

**Modified price impact calculation:**

```python
# Leg 1: Protocol A Lend (Token1 exposure)
entry_price_1A = position['entry_price_1A']  # From position record
current_price_1A = get_leg_price_for_pnl(position, '1A', latest_snap)

leg1_exposure_usd = deployment * L_A
price_change_leg1 = (current_price_1A - entry_price_1A) / entry_price_1A
PnL_price_leg1 = leg1_exposure_usd * price_change_leg1

# Repeat for legs 2A, 2B, 3B...
```

### Benefits of Price Helper Pattern

1. **Single source of truth:** All PnL calculations use same price source
2. **Easy upgrade path:** Change implementation in one place for Phase 2
3. **Testability:** Can mock price source for testing
4. **Fallback logic:** Can add multiple sources with fallback chain
5. **Price staleness:** Can add validation (e.g., reject prices > 1 hour old)
6. **Multiple AMM support:** Can average prices across Cetus, Turbos, etc.

### Phase 2 Enhancements (Future)

Add to `config/settings.py`:
```python
# PnL price source configuration (Phase 2)
PNL_PRICE_SOURCE = 'protocol'  # Options: 'protocol', 'cetus', 'pyth', 'coingecko'
PNL_PRICE_FALLBACK_CHAIN = ['cetus', 'pyth', 'protocol']  # Fallback order
PNL_PRICE_MAX_AGE_SECONDS = 3600  # Reject stale prices
```

## Step 6 Summary

**Key Changes from Original Plan:**
1. ✅ Changed from 3 aggregated token lines to **4 leg-level price breakdown**
2. ✅ Added **price helper function** (`get_pnl_price()`) for future flexibility
3. ✅ **Net Token2 Hedge validation** displayed as separate line
4. ✅ **Actual token symbols** (SUI/USDC) instead of generic names
5. ✅ **Color coding** for all PnL components (green/red)
6. ✅ **Snapshot-based only** - no real-time price queries

**Files Modified:**
- `analysis/position_service.py` - Add price helper functions + PnL calculation
- `data/schema.sql` - Update position_snapshots table with 4 leg prices
- `dashboard/positions_tab.py` - Render PnL with colors and symbols

**Status:** Step 6 complete. Moving to Steps 7 & 8.

---

# Step 7 & 8 Review: Risk Metrics & Collateralization Validation

## Context from Handover Plan (Lines 426-531)

**Step 7:** Protocol Risk Data Integration (Phase 2 - NOT Phase 1)
- Phase 1: Calculate risk metrics from rates/prices only
- Phase 2: Add protocol-sourced risk from on-chain positions

**Step 8:** Collateralization Validation
- Store entry collateral ratios
- Warn if ratios change >5% during position lifetime

## Step 7: Risk Metrics Calculation (Phase 1)

### Calculated Risk Metrics (from snapshot data)

**File:** `analysis/position_service.py`

```python
def calculate_liquidation_levels(
    position: dict,
    current_prices: dict,
    current_collateral_ratios: dict
) -> dict:
    """
    Calculate risk metrics from observed rates/prices.

    Phase 1: Only source for risk metrics (paper trading)
    Phase 2: Will be compared against protocol-sourced metrics

    Args:
        position: Position record with entry data
        current_prices: Dict of current prices by leg ('1A', '2A', '2B', '3B')
        current_collateral_ratios: Dict of current collateral ratios

    Returns:
        dict: {
            'health_factor_1A': float,  # Protocol A health (collateral / borrow)
            'health_factor_2B': float,  # Protocol B health
            'distance_to_liq_1A': float,  # % buffer before liquidation
            'distance_to_liq_2B': float,
            'ltv_1A': float,  # Loan-to-value ratio
            'ltv_2B': float,
            'liquidation_price_1A': float,  # Price at which liquidation occurs
            'liquidation_price_2B': float,
            'collateral_ratio_drift_1A': float,  # % change from entry
            'collateral_ratio_drift_2B': float
        }
    """
    deployment = position['deployment_usd']
    L_A = position['L_A']
    B_A = position['B_A']
    L_B = position['L_B']
    B_B = position['B_B'] if position['is_levered'] else 0

    # Protocol A: Lend Token1, Borrow Token2
    collateral_1A_usd = deployment * L_A * current_prices['1A']
    borrow_2A_usd = deployment * B_A * current_prices['2A']

    health_factor_1A = collateral_1A_usd / borrow_2A_usd if borrow_2A_usd > 0 else float('inf')
    ltv_1A = borrow_2A_usd / collateral_1A_usd if collateral_1A_usd > 0 else 0

    # Liquidation occurs when LTV reaches collateral ratio threshold
    collateral_ratio_1A = current_collateral_ratios.get('1A', position['entry_collateral_ratio_1A'])
    liquidation_threshold_1A = 1 / collateral_ratio_1A  # Max LTV before liquidation

    # Distance to liquidation = % buffer remaining
    distance_to_liq_1A = (liquidation_threshold_1A - ltv_1A) / liquidation_threshold_1A if liquidation_threshold_1A > 0 else 0

    # Liquidation price: Token1 price at which LTV hits threshold
    # At liquidation: (L_A * liq_price_1A) / (B_A * price_2A) = collateral_ratio_1A
    # Solving for liq_price_1A:
    liquidation_price_1A = (collateral_ratio_1A * borrow_2A_usd) / (deployment * L_A) if L_A > 0 else 0

    # Collateral ratio drift from entry
    entry_collateral_ratio_1A = position['entry_collateral_ratio_1A']
    collateral_ratio_drift_1A = (collateral_ratio_1A - entry_collateral_ratio_1A) / entry_collateral_ratio_1A

    # Protocol B: Lend Token2, Borrow Token3 (if levered)
    if B_B > 0:
        collateral_2B_usd = deployment * L_B * current_prices['2B']
        borrow_3B_usd = deployment * B_B * current_prices['3B']

        health_factor_2B = collateral_2B_usd / borrow_3B_usd if borrow_3B_usd > 0 else float('inf')
        ltv_2B = borrow_3B_usd / collateral_2B_usd if collateral_2B_usd > 0 else 0

        collateral_ratio_2B = current_collateral_ratios.get('2B', position['entry_collateral_ratio_2B'])
        liquidation_threshold_2B = 1 / collateral_ratio_2B

        distance_to_liq_2B = (liquidation_threshold_2B - ltv_2B) / liquidation_threshold_2B if liquidation_threshold_2B > 0 else 0

        liquidation_price_2B = (collateral_ratio_2B * borrow_3B_usd) / (deployment * L_B) if L_B > 0 else 0

        entry_collateral_ratio_2B = position['entry_collateral_ratio_2B']
        collateral_ratio_drift_2B = (collateral_ratio_2B - entry_collateral_ratio_2B) / entry_collateral_ratio_2B
    else:
        # Unlevered position has no Protocol B borrow
        health_factor_2B = float('inf')
        ltv_2B = 0
        distance_to_liq_2B = 1.0  # 100% safe (no borrow)
        liquidation_price_2B = 0
        collateral_ratio_drift_2B = 0

    return {
        'health_factor_1A': health_factor_1A,
        'health_factor_2B': health_factor_2B,
        'distance_to_liq_1A': distance_to_liq_1A,
        'distance_to_liq_2B': distance_to_liq_2B,
        'ltv_1A': ltv_1A,
        'ltv_2B': ltv_2B,
        'liquidation_price_1A': liquidation_price_1A,
        'liquidation_price_2B': liquidation_price_2B,
        'collateral_ratio_drift_1A': collateral_ratio_drift_1A,
        'collateral_ratio_drift_2B': collateral_ratio_drift_2B,
    }
```

### Database Schema for Risk Metrics

**File:** `data/schema.sql` - Add to `position_snapshots` table

```sql
-- Calculated risk metrics (Phase 1)
health_factor_1A DECIMAL(10, 4),       -- Protocol A health factor
health_factor_2B DECIMAL(10, 4),       -- Protocol B health factor (NULL if unlevered)
distance_to_liq_1A DECIMAL(10, 6),     -- % buffer before liquidation (Protocol A)
distance_to_liq_2B DECIMAL(10, 6),     -- % buffer before liquidation (Protocol B, NULL if unlevered)
ltv_1A DECIMAL(10, 6),                 -- Loan-to-value ratio (Protocol A)
ltv_2B DECIMAL(10, 6),                 -- Loan-to-value ratio (Protocol B, NULL if unlevered)
liquidation_price_1A DECIMAL(20, 10),  -- Token1 price at liquidation
liquidation_price_2B DECIMAL(20, 10),  -- Token2 price at liquidation (NULL if unlevered)

-- Collateral ratio tracking (Step 8)
collateral_ratio_1A DECIMAL(10, 6),          -- Current collateral ratio (Protocol A)
collateral_ratio_2B DECIMAL(10, 6),          -- Current collateral ratio (Protocol B, NULL if unlevered)
collateral_ratio_drift_1A DECIMAL(10, 6),    -- % change from entry (Protocol A)
collateral_ratio_drift_2B DECIMAL(10, 6),    -- % change from entry (Protocol B, NULL if unlevered)

-- Phase 2: Protocol-sourced metrics (NOT IMPLEMENTED YET)
health_factor_1A_protocol DECIMAL(10, 4),
health_factor_2B_protocol DECIMAL(10, 4),
ltv_1A_protocol DECIMAL(10, 6),
ltv_2B_protocol DECIMAL(10, 6),
risk_data_source TEXT  -- 'calculated' (Phase 1) or 'both' (Phase 2)
```

## Step 8: Collateralization Validation

### Entry Data Storage

**File:** `data/schema.sql` - Add to `positions` table

```sql
-- Collateral ratios at entry (for drift detection)
entry_collateral_ratio_1A DECIMAL(10, 6),  -- Protocol A collateral ratio at entry
entry_collateral_ratio_2B DECIMAL(10, 6),  -- Protocol B collateral ratio at entry (NULL if unlevered)
```

### Validation Logic

**In `PositionService.create_snapshot()`:**

```python
# Calculate risk metrics
risk_metrics = self.calculate_liquidation_levels(
    position,
    current_prices,
    current_collateral_ratios
)

# Step 8: Collateralization drift validation
warnings = []

# Check Protocol A drift
if abs(risk_metrics['collateral_ratio_drift_1A']) > 0.05:  # 5% threshold
    warnings.append({
        'protocol': position['protocol_A'],
        'leg': '1A',
        'entry_ratio': position['entry_collateral_ratio_1A'],
        'current_ratio': risk_metrics['collateral_ratio_1A'],
        'drift_pct': risk_metrics['collateral_ratio_drift_1A'] * 100,
        'message': f"⚠️ {position['protocol_A']} collateral ratio changed {risk_metrics['collateral_ratio_drift_1A']*100:.1f}% since entry"
    })

# Check Protocol B drift (if levered)
if position['is_levered'] and abs(risk_metrics['collateral_ratio_drift_2B']) > 0.05:
    warnings.append({
        'protocol': position['protocol_B'],
        'leg': '2B',
        'entry_ratio': position['entry_collateral_ratio_2B'],
        'current_ratio': risk_metrics['collateral_ratio_2B'],
        'drift_pct': risk_metrics['collateral_ratio_drift_2B'] * 100,
        'message': f"⚠️ {position['protocol_B']} collateral ratio changed {risk_metrics['collateral_ratio_drift_2B']*100:.1f}% since entry"
    })

# Log warnings
for warning in warnings:
    logger.warning(f"Position {position['position_id']}: {warning['message']}")

# Store warnings in snapshot metadata (optional)
snapshot_metadata = {
    'collateral_ratio_warnings': warnings
}
```

### UI Display

**File:** `dashboard/positions_tab.py`

```python
# Risk Metrics Section
st.markdown("### Risk Metrics")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Protocol A Risk:**")
    health_color = 'green' if health_factor_1A > 1.5 else ('orange' if health_factor_1A > 1.2 else 'red')
    st.markdown(f"Health Factor: :{health_color}[{health_factor_1A:.2f}]")
    st.markdown(f"Distance to Liquidation: {distance_to_liq_1A*100:.1f}%")
    st.markdown(f"LTV: {ltv_1A*100:.1f}%")
    st.markdown(f"Liquidation Price ({token1}): ${liquidation_price_1A:.4f}")

    # Collateral ratio drift warning
    if abs(collateral_ratio_drift_1A) > 0.05:
        st.warning(f"⚠️ Collateral ratio changed {collateral_ratio_drift_1A*100:.1f}% since entry")

with col2:
    if position['is_levered']:
        st.markdown("**Protocol B Risk:**")
        health_color = 'green' if health_factor_2B > 1.5 else ('orange' if health_factor_2B > 1.2 else 'red')
        st.markdown(f"Health Factor: :{health_color}[{health_factor_2B:.2f}]")
        st.markdown(f"Distance to Liquidation: {distance_to_liq_2B*100:.1f}%")
        st.markdown(f"LTV: {ltv_2B*100:.1f}%")
        st.markdown(f"Liquidation Price ({token2}): ${liquidation_price_2B:.4f}")

        # Collateral ratio drift warning
        if abs(collateral_ratio_drift_2B) > 0.05:
            st.warning(f"⚠️ Collateral ratio changed {collateral_ratio_drift_2B*100:.1f}% since entry")
    else:
        st.info("No Protocol B borrow (unlevered position)")
```

## Key Design Decisions

1. **Phase 1: Calculated only** - No protocol API queries (paper trading)
2. **Health factor thresholds:**
   - Green: > 1.5 (safe)
   - Orange: 1.2 - 1.5 (caution)
   - Red: < 1.2 (danger)
3. **Collateral ratio drift:** Warn if >5% change from entry
4. **Liquidation price:** Show exact price at which liquidation occurs
5. **Unlevered positions:** health_factor_2B = infinity, distance = 100%

## Verification Checklist

- [ ] Health factors calculated correctly for both protocols
- [ ] Distance to liquidation shows % buffer remaining
- [ ] LTV ratio = borrow_value / collateral_value
- [ ] Liquidation price formula verified
- [ ] Collateral ratio drift calculated from entry baseline
- [ ] Warnings displayed when drift >5%
- [ ] Unlevered positions handle NULL Protocol B values
- [ ] Color coding: green (>1.5), orange (1.2-1.5), red (<1.2)
- [ ] All risk metrics stored in position_snapshots table

## Phase 2 Enhancements (Future - NOT Phase 1)

When real capital is deployed:
1. Query protocol smart contracts for actual position health
2. Store both calculated and protocol-sourced metrics
3. Compare for validation (alert if large discrepancy)
4. Use protocol metrics as primary, calculated as fallback

**NOT IMPLEMENTED in Phase 1** - paper trading doesn't have on-chain positions.

---

# Steps 7 & 8 Summary

**Step 7: Risk Metrics**
- ✅ Calculate health factors, LTV, distance to liquidation from snapshot data
- ✅ Phase 1: Calculated only (no protocol APIs)
- ✅ Phase 2 ready: Schema includes protocol metric columns (unused in Phase 1)

**Step 8: Collateralization Validation**
- ✅ Store entry collateral ratios in positions table
- ✅ Track drift in each snapshot
- ✅ Warn if >5% change from entry
- ✅ Display warnings in UI

**Files Modified:**
- `data/schema.sql` - Add risk metric columns to position_snapshots, entry ratios to positions
- `analysis/position_service.py` - Add `calculate_liquidation_levels()` method
- `dashboard/positions_tab.py` - Display risk metrics with color coding and warnings

**Status:** Steps 7 & 8 complete. All steps (5-8) reviewed.

---

# Overall Summary: Steps 5-8 Enhancements

## What Was Reviewed

This plan reviews and enhances **Steps 5-8** of the Position Management Framework handover from the previous chat.

### Step 5: Snapshot Automation ✅
**Enhancement:** Changed from config flag to scheduler parameter approach
- Scheduler passes `create_position_snapshots=True` on the hour
- Pipeline receives rates every 15 min, creates position snapshots hourly
- Added global "📸 Snapshot All" button in Positions tab
- **~100 lines added** across 4 files

### Step 6: PnL Calculation Algorithm ✅
**Enhancement:** Added leg-level price breakdown, price helper, hedge validation
- Changed from 3 aggregated token lines to 4 leg-level price impacts
- Added `get_pnl_price()` helper function (Phase 1: protocol prices, Phase 2: AMM/oracle ready)
- Net Token2 Hedge validation displayed separately
- Actual token symbols (SUI/USDC), color coding (green/red)
- **~200 lines added** to position_service.py

### Step 7: Risk Metrics ✅
**Clarification:** Phase 1 uses calculated metrics only (no protocol APIs)
- Health factors, LTV, distance to liquidation
- Liquidation price calculation
- Color coding: green (>1.5), orange (1.2-1.5), red (<1.2)
- Phase 2 schema ready (protocol metric columns unused)
- **~150 lines added** to position_service.py + schema

### Step 8: Collateralization Validation ✅
**Clarification:** Track collateral ratio drift, warn if >5%
- Store entry ratios in positions table
- Calculate drift in each snapshot
- Display warnings in UI when threshold exceeded
- **~50 lines added** to position_service.py + UI

## Total Lines of Code

| Component | Lines Added | Purpose |
|-----------|-------------|---------|
| Step 5 (Snapshots) | ~100 | Hourly automation + global button |
| Step 6 (PnL) | ~200 | Leg-level breakdown, price helper, hedge |
| Step 7 (Risk) | ~150 | Health factors, LTV, liquidation calc |
| Step 8 (Collateral) | ~50 | Drift tracking and warnings |
| **Total** | **~500** | Steps 5-8 enhancements |

## Critical Files Modified

### New Files (from original Steps 1-4)
- `analysis/position_service.py` - Core position management logic
- `dashboard/positions_tab.py` - Positions tab UI

### Modified Files (Steps 5-8 enhancements)
- **Scheduler** (e.g., `main.py`) - Add hourly snapshot flag
- `data/refresh_pipeline.py` - Accept `create_position_snapshots` parameter
- `data/schema.sql` - Add risk metrics, collateral ratios, leg prices to snapshots
- `analysis/position_service.py` - Add price helpers, PnL calc, risk metrics
- `dashboard/positions_tab.py` - Render PnL with colors, display risk metrics

## Key Architectural Decisions

1. **Scheduler controls frequency** (Step 5) - Not config flag
2. **Leg-level price breakdown** (Step 6) - 4 separate lines, not 3 aggregated
3. **Price helper pattern** (Step 6) - Isolates price source for Phase 2 upgrade
4. **Hedge validation** (Step 6) - Displayed separately, shows drift over time
5. **Calculated metrics only** (Step 7) - Phase 1 paper trading, no protocol APIs
6. **5% drift threshold** (Step 8) - Warn when collateral ratios change significantly

## Next Steps After Plan Approval

1. **Implement Steps 1-4** from original handover (if not done yet):
   - Database schema (positions + position_snapshots tables)
   - Position service core methods
   - Deploy button integration
   - Positions tab UI skeleton

2. **Implement Steps 5-8 enhancements** from this plan:
   - Scheduler hourly snapshot logic
   - Price helper functions
   - Leg-level PnL calculation
   - Risk metrics calculation
   - Collateralization validation

3. **Verification**:
   - Deploy test paper position
   - Verify hourly snapshots created automatically
   - Verify PnL breakdown displays correctly with colors
   - Verify hedge validation shows drift
   - Verify risk metrics calculated correctly
   - Verify collateral ratio warnings appear when >5% drift

## Dependencies

- Original Steps 1-4 must be complete before implementing Steps 5-8
- `rates_snapshot` table must exist and be populated
- Scheduler must be callable with parameters

## Phase 2 Readiness

This plan maintains Phase 2 readiness:
- Price helper can be upgraded to AMM/oracle sources
- Risk metric schema includes protocol API columns (unused in Phase 1)
- Multi-user filtering supported via optional `user_id` parameters
- `is_paper_trade` flag ready for live capital deployment

---

# Plan Complete

**All steps (5-8) have been reviewed and enhanced based on user feedback.**

**Ready for implementation approval via ExitPlanMode.**

---

# External Handover Document

**Note:** A comprehensive external handover document should be created at `/Users/donalmoore/Dev/sui-lending-bot/POSITION_MANAGEMENT_HANDOVER.md` containing:

1. **Overview** - What this does, what was reviewed (Steps 5-8)
2. **Architecture Summary** - System flow, position lifecycle, data flow
3. **Implementation Steps** - Detailed code changes for each step
4. **Database Schema** - Full SQL for positions and position_snapshots tables
5. **Code Components** - File structure, key classes & methods
6. **Key Design Decisions** - Rationale for scheduler control, leg-level breakdown, price helpers, etc.
7. **Verification & Testing** - Test plan, expected results, database validation queries
8. **Phase 2 Readiness** - What's ready, what needs adding for live capital
9. **Reference Documents** - Links to plan files
10. **Implementation Checklist** - Prerequisites, per-step tasks, integration testing
11. **Common Issues & Solutions** - Known issues and fixes

**Action:** After plan approval, create this external document by copying the comprehensive content from this plan into a standalone markdown file that can be shared with colleagues or used in future chat sessions.
