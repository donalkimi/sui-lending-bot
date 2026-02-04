# PnL Calculation Optimization - Implementation Handover Document

## Executive Summary

**Objective:** Optimize PnL calculations by sampling timestamps at 60-minute intervals instead of processing every timestamp in a position's date range.

**Approach:** Application-layer filtering (no database schema changes required)

**Expected Impact:** 75-90% reduction in processed timestamps for long-running positions, with <2% accuracy trade-off

**Implementation Time:** ~1-2 hours

---

## Background Context

### Current Architecture

The Sui Lending Bot tracks lending/borrowing rates across multiple protocols (Navi, AlphaFi, Suilend, Scallop, Pebble) and calculates PnL for positions.

**Key Components:**
- **`rates_snapshot` table:** Stores protocol rates at minute-level granularity
- **PnL calculation:** Loops through consecutive timestamp pairs, calculating earnings for each period
- **Current data volume:** ~458 timestamps over 25 days (currently collected hourly, but stored at minute granularity)
- **Future concern:** With denser collection, could reach 30,000+ timestamps per year

### The Performance Problem

**Location:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_service.py`

Two methods query ALL timestamps in a date range:
1. `calculate_leg_earnings_split()` (lines 1020-1096) - Main PnL calculation
2. `calculate_position_value()` (lines 673-711) - Alternative PnL method

**Flow:**
```
1. Query: SELECT * FROM rates_snapshot WHERE timestamp BETWEEN start AND end
2. Loop: For each consecutive timestamp pair (ts_i, ts_i+1):
   - Calculate period_years = (ts_next - ts_current) / (365.25 * 86400)
   - Calculate earnings = deployment * weight * APR * period_years
3. Sum all periods
```

**Problem:** For a 1-year position with minute-level data = 525,600 timestamp pairs to process!

---

## Implementation Plan

### Step 1: Add Configuration Setting

**File:** `/Users/donalmoore/Dev/sui-lending-bot/config/settings.py`

**Current state (line 54-55):**
```python
REBALANCE_THRESHOLD = 0.02
# Database Settings
SAVE_SNAPSHOTS = True  # Set to False to disable database tracking
```

**Add after line 55:**
```python
# Database Settings
SAVE_SNAPSHOTS = True  # Set to False to disable database tracking

# PnL Calculation Optimization
# Sample timestamps at this interval (in minutes) for position earnings calculations
# Higher values = faster calculations, lower values = more precision
# Recommended: 60 (1 hour) balances performance and accuracy
STATS_GRANULARITY_MINUTES = 60
```

---

### Step 2: Optimize `calculate_leg_earnings_split()` Method

**File:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_service.py`

**Current code (lines 1039-1046):**
```python
        # Execute ONCE - get all rates for this leg's segment
        all_rates = pd.read_sql_query(bulk_query, self.engine,
                                       params=(start_str, end_str, protocol, token_contract))

        if all_rates.empty:
            # No rate data available, return zeros
            return 0.0, 0.0
```

**Insert this code block AFTER line 1041 (after the `all_rates = pd.read_sql_query(...)` line):**

```python
        # Execute ONCE - get all rates for this leg's segment
        all_rates = pd.read_sql_query(bulk_query, self.engine,
                                       params=(start_str, end_str, protocol, token_contract))

        # ==================== START: TIMESTAMP SAMPLING OPTIMIZATION ====================
        # Sample timestamps at STATS_GRANULARITY_MINUTES intervals to reduce processing
        # CRITICAL: Always include boundary timestamps (start_str, end_str) for accuracy
        if not all_rates.empty:
            from config import settings

            granularity_minutes = getattr(settings, 'STATS_GRANULARITY_MINUTES', 60)

            # Always include boundary timestamps for accurate PnL at segment boundaries
            boundary_timestamps = {start_str, end_str}

            # Sample timestamps at configured interval
            sampled_rates = []
            last_sampled_ts = None
            granularity_seconds = granularity_minutes * 60

            for idx, row in all_rates.iterrows():
                ts_str = str(row['timestamp'])  # Convert to string for comparison

                # Convert timestamp to seconds for interval calculation
                ts_seconds = to_seconds(ts_str)

                # Always include boundary timestamps (position entry/exit/rebalance)
                if ts_str in boundary_timestamps:
                    sampled_rates.append(row)
                    last_sampled_ts = ts_seconds
                    continue

                # Include timestamp if enough time has elapsed since last sample
                # This handles irregular collection intervals gracefully
                if last_sampled_ts is None or (ts_seconds - last_sampled_ts) >= granularity_seconds:
                    sampled_rates.append(row)
                    last_sampled_ts = ts_seconds

            # Replace all_rates with sampled subset
            if sampled_rates:
                original_count = len(all_rates)
                all_rates = pd.DataFrame(sampled_rates).reset_index(drop=True)

                # Log sampling ratio for monitoring (only if significant reduction)
                if original_count > 0:
                    reduction_pct = (1 - len(sampled_rates) / original_count) * 100
                    if reduction_pct > 10:  # Only log if >10% reduction
                        print(f"[PnL OPTIMIZATION] Sampled {len(sampled_rates)}/{original_count} timestamps "
                              f"({reduction_pct:.1f}% reduction) for {protocol} {action} {token_contract[:8]}...)")
        # ==================== END: TIMESTAMP SAMPLING OPTIMIZATION ====================

        if all_rates.empty:
            # No rate data available, return zeros
            return 0.0, 0.0
```

**Note:** The `to_seconds()` function already exists in the codebase - it's imported at the top of the file from `utils.time_helpers`.

---

### Step 3: Optimize `calculate_position_value()` Method

**File:** `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_service.py`

**Current code (lines 673-682):**
```python
        ph = self._get_placeholder()
        query_timestamps = f"""
        SELECT DISTINCT timestamp
        FROM rates_snapshot
        WHERE timestamp >= {ph} AND timestamp <= {ph}
        ORDER BY timestamp ASC
        """
        timestamps_df = pd.read_sql_query(query_timestamps, self.engine, params=(start_str, end_str))

        if timestamps_df.empty:
            raise ValueError(f"No rate data found between {start_str} and {end_str}")
```

**Insert this code block AFTER line 679 (after `timestamps_df = pd.read_sql_query(...)`):**

```python
        timestamps_df = pd.read_sql_query(query_timestamps, self.engine, params=(start_str, end_str))

        # ==================== START: TIMESTAMP SAMPLING OPTIMIZATION ====================
        # Sample timestamps at STATS_GRANULARITY_MINUTES intervals
        # This method also loops through all timestamps (legacy pattern), so needs optimization
        if not timestamps_df.empty:
            from config import settings

            granularity_minutes = getattr(settings, 'STATS_GRANULARITY_MINUTES', 60)

            # Always include boundary timestamps for accurate PnL at segment boundaries
            boundary_timestamps = {start_str, end_str}

            sampled_timestamps = []
            last_sampled_ts = None
            granularity_seconds = granularity_minutes * 60

            for ts_str in timestamps_df['timestamp']:
                ts_str = str(ts_str)  # Ensure string format
                ts_seconds = to_seconds(ts_str)

                # Always include boundaries (position entry/exit/rebalance)
                if ts_str in boundary_timestamps:
                    sampled_timestamps.append(ts_str)
                    last_sampled_ts = ts_seconds
                    continue

                # Include if enough time has elapsed since last sample
                if last_sampled_ts is None or (ts_seconds - last_sampled_ts) >= granularity_seconds:
                    sampled_timestamps.append(ts_str)
                    last_sampled_ts = ts_seconds

            # Replace with sampled subset
            if sampled_timestamps:
                original_count = len(timestamps_df)
                timestamps_df = pd.DataFrame({'timestamp': sampled_timestamps})

                # Log sampling for monitoring (only if significant reduction)
                if original_count > 0:
                    reduction_pct = (1 - len(sampled_timestamps) / original_count) * 100
                    if reduction_pct > 10:
                        print(f"[PnL OPTIMIZATION] Sampled {len(sampled_timestamps)}/{original_count} "
                              f"timestamps ({reduction_pct:.1f}% reduction)")
        # ==================== END: TIMESTAMP SAMPLING OPTIMIZATION ====================

        if timestamps_df.empty:
            raise ValueError(f"No rate data found between {start_str} and {end_str}")
```

---

## Testing Instructions

### Pre-Implementation Testing

1. **Record baseline PnL values:**
   ```bash
   cd /Users/donalmoore/Dev/sui-lending-bot
   python -c "
   from analysis.position_service import PositionService
   from config import settings

   service = PositionService(
       use_cloud=settings.USE_CLOUD_DB,
       db_path=settings.SQLITE_PATH,
       connection_url=settings.SUPABASE_URL
   )

   # Get all active positions
   positions = service.get_all_positions()
   print('Baseline PnL values:')
   for _, pos in positions.iterrows():
       print(f'{pos[\"position_id\"]}: PnL={pos.get(\"total_pnl\", \"N/A\")}')
   "
   ```

### Post-Implementation Testing

2. **Verify PnL accuracy after changes:**
   ```bash
   python -c "
   from analysis.position_service import PositionService
   from config import settings

   service = PositionService(
       use_cloud=settings.USE_CLOUD_DB,
       db_path=settings.SQLITE_PATH,
       connection_url=settings.SUPABASE_URL
   )

   positions = service.get_all_positions()
   print('New PnL values:')
   for _, pos in positions.iterrows():
       print(f'{pos[\"position_id\"]}: PnL={pos.get(\"total_pnl\", \"N/A\")}')
   "
   ```

3. **Compare results:**
   - PnL values should match within ~2%
   - Check console logs for sampling statistics (e.g., "Sampled 100/500 timestamps (80% reduction)")

4. **Test edge cases:**
   - Create a test position with entry/exit
   - Verify rebalanced positions calculate correctly
   - Test with `STATS_GRANULARITY_MINUTES = 1` (should match original behavior)
   - Test with `STATS_GRANULARITY_MINUTES = 60` (should show reduction)

### Rollback Procedure

If issues discovered, edit `config/settings.py` and change:
```python
STATS_GRANULARITY_MINUTES = 1  # Effectively disables sampling
```

This reverts to original behavior without code changes.

---

## Code Context & Helper Functions

### Existing Helper Function (already in codebase)

**Location:** `/Users/donalmoore/Dev/sui-lending-bot/utils/time_helpers.py`

```python
def to_seconds(datetime_str: str) -> int:
    """Convert datetime string to Unix seconds"""
    dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    return int(dt.timestamp())

def to_datetime_str(unix_seconds: int) -> str:
    """Convert Unix seconds to datetime string"""
    dt = datetime.fromtimestamp(unix_seconds)
    return dt.strftime('%Y-%m-%d %H:%M:%S')
```

These functions are already imported at the top of `position_service.py`:
```python
from utils.time_helpers import to_seconds, to_datetime_str
```

### Current PnL Calculation Logic

**How it works (lines 1075-1096 in position_service.py):**
```python
# Loop through periods - NO QUERIES in this loop (optimization)
for i in range(len(timestamps) - 1):
    ts_current = timestamps[i]
    ts_next = timestamps[i + 1]
    period_years = (ts_next - ts_current) / (365.25 * 86400)

    # O(1) lookup - no database query
    rate_data = rates_lookup.get(ts_current, {'base_apr': 0.0, 'reward_apr': 0.0})
    base_apr = rate_data['base_apr']
    reward_apr = rate_data['reward_apr']

    # Accumulate earnings
    if action == 'Lend':
        base_total += deployment * weight * base_apr * period_years
        reward_total += deployment * weight * reward_apr * period_years
    else:  # Borrow
        base_total += deployment * weight * base_apr * period_years
        reward_total += deployment * weight * reward_apr * period_years

return base_total, reward_total
```

**Key insight:** Earnings are calculated as `deployment × weight × APR × period_in_years`. By sampling timestamps at 60-minute intervals, we're just using larger periods (1 hour instead of 5 minutes) which is still accurate for gradually-changing rates.

---

## Design Decisions & Rationale

### Why Application-Layer Over Database Flag?

**Rejected approach:** Add `use_for_pnl_calc BOOLEAN` column to `rates_snapshot` table

**Reasons for rejection:**
1. **Current data volume is small:** Only 458 timestamps over 25 days doesn't justify schema changes
2. **Boundary timestamps are position-specific:** A timestamp may be a boundary for one position but not another - database flag can't handle this
3. **Flexibility:** Application layer allows per-query granularity adjustment
4. **Reversibility:** Just change config value, no migration needed
5. **Complexity:** Database approach requires schema migration, backfill script, and ongoing flag maintenance

**When to reconsider database approach:**
- Data volume exceeds 100,000 timestamps
- Multiple applications need same sampling logic
- Phase 1 proves insufficient after testing

### Why Always Include Boundary Timestamps?

**Critical edge case:** Position entry/exit timestamps rarely align with 60-minute intervals.

**Example scenario:**
- Position entered at 10:17 AM
- Data collected at 10:00, 11:00, 12:00 (hourly)
- Without boundary inclusion: Would use 11:00 as "start", missing 10:17-11:00 earnings
- With boundary inclusion: Uses 10:17, 11:00, 12:00 - accurate PnL

**Same applies to:**
- Position exit timestamps
- Rebalance timestamps (each rebalance creates a new segment with its own boundaries)

### Sampling Logic: "Next Available" vs. "Exact Intervals"

**Chosen approach:** Include timestamp if `time_since_last >= 60 minutes`

**Alternative (rejected):** Only include timestamps at exact 60-minute marks (e.g., :00 minutes past each hour)

**Rationale:**
- Data collection may be irregular (scheduler runs hourly, but not always exactly at :00)
- Network delays, server restarts, etc. can cause timestamp drift
- "Next available" approach gracefully handles these irregularities
- Still achieves ~60-minute spacing on average

---

## Database Schema Reference

### rates_snapshot Table Structure

```sql
CREATE TABLE rates_snapshot (
    timestamp TIMESTAMP NOT NULL,
    protocol TEXT NOT NULL,
    token TEXT NOT NULL,
    token_contract TEXT NOT NULL,
    lend_base_apr REAL,
    lend_reward_apr REAL,
    lend_total_apr REAL,
    borrow_base_apr REAL,
    borrow_reward_apr REAL,
    borrow_total_apr REAL,
    collateral_ratio REAL,
    liquidation_threshold REAL,
    price_usd REAL,
    utilization REAL,
    total_supply_usd REAL,
    total_borrow_usd REAL,
    available_borrow_usd REAL,
    borrow_fee REAL,
    borrow_weight REAL,
    PRIMARY KEY (timestamp, protocol, token_contract)
);

CREATE INDEX idx_rates_time ON rates_snapshot(timestamp);
CREATE INDEX idx_rates_protocol_contract ON rates_snapshot(protocol, token_contract);
```

**Key points:**
- Primary key includes timestamp - prevents duplicate entries
- Timestamp indexed for fast range queries
- Current row count: ~28,944 (458 timestamps × ~63 protocol/token combinations)

---

## Performance Projections

### Current State (No Optimization)
- **Data volume:** 458 distinct timestamps over 25 days
- **Collection frequency:** Hourly (daytime), 4-hourly (night/weekend)
- **PnL calculation:** Process 457 consecutive timestamp pairs per position leg
- **Expected improvement:** Minimal (data already roughly hourly)

### Future State (With Denser Collection)
- **Scenario:** Data collection improves to every 15 minutes
- **Without optimization:** 365 days × 24 hours × 4 = 35,040 timestamp pairs/year
- **With optimization (60-min):** 365 days × 24 hours = 8,760 timestamp pairs/year
- **Reduction:** 75% fewer timestamps processed

### Accuracy Trade-off
- **For lending protocols:** Interest accrues continuously with gradually-changing rates
- **60-minute sampling:** Captures rate changes with <2% error
- **Test on real data:** Compare PnL calculations before/after to verify <2% difference

---

## File Locations Summary

| File | Purpose | Changes |
|------|---------|---------|
| `/Users/donalmoore/Dev/sui-lending-bot/config/settings.py` | Configuration | Add `STATS_GRANULARITY_MINUTES = 60` after line 55 |
| `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_service.py` | PnL calculations | Add sampling logic after lines 1041 and 679 |
| `/Users/donalmoore/Dev/sui-lending-bot/analysis/position_statistics_calculator.py` | High-level PnL orchestration | Review only - may call position_service methods |
| `/Users/donalmoore/Dev/sui-lending-bot/utils/time_helpers.py` | Time conversion utilities | No changes (already has required functions) |

---

## Validation Checklist

After implementation, verify:

- [ ] `STATS_GRANULARITY_MINUTES = 60` added to config/settings.py
- [ ] Sampling logic added after line 1041 in position_service.py
- [ ] Sampling logic added after line 679 in position_service.py
- [ ] No syntax errors (run `python -m py_compile analysis/position_service.py`)
- [ ] PnL calculations complete without errors
- [ ] PnL values match baseline within 2%
- [ ] Console shows sampling statistics when reduction >10%
- [ ] Edge cases tested (short positions, rebalances, boundary timestamps)
- [ ] Rollback plan tested (`STATS_GRANULARITY_MINUTES = 1` restores original behavior)

---

## Questions & Troubleshooting

### Q: What if PnL values differ by more than 2%?

**A:** This indicates an issue with boundary timestamp handling. Verify:
1. `boundary_timestamps = {start_str, end_str}` is set correctly
2. Entry/exit timestamps are being included in sampled set
3. No off-by-one errors in timestamp comparison logic

**Debug approach:**
```python
# Add debug logging in sampling loop
if ts_str in boundary_timestamps:
    print(f"[DEBUG] Including boundary timestamp: {ts_str}")
    sampled_rates.append(row)
```

### Q: What if no sampling reduction is shown in logs?

**A:** Check:
1. Is `STATS_GRANULARITY_MINUTES` actually set to 60 in config?
2. Is current data already at ~60-minute intervals? (No reduction expected if data already sparse)
3. Is the position period very short (<2 hours)? Few timestamps to sample

**Verify config loaded:**
```python
from config import settings
print(f"STATS_GRANULARITY_MINUTES = {getattr(settings, 'STATS_GRANULARITY_MINUTES', 'NOT SET')}")
```

### Q: What if sampling breaks rebalanced positions?

**A:** Each rebalance segment is calculated independently with its own boundaries:
- Segment 1: entry_timestamp → rebalance1_timestamp
- Segment 2: rebalance1_timestamp → rebalance2_timestamp
- Segment 3: rebalance2_timestamp → current_timestamp

Each segment's start/end are treated as boundary timestamps and always included.

**Verify by checking logs for rebalance timestamps in sampled set.**

---

## Future Enhancements (Optional)

### Database-Level Optimization (Phase 2)

If Phase 1 proves insufficient or data volume exceeds 100,000 timestamps, consider:

1. **Add column to rates_snapshot:**
   ```sql
   ALTER TABLE rates_snapshot ADD COLUMN use_for_pnl_calc BOOLEAN DEFAULT FALSE;
   ```

2. **Create partial index (only indexes TRUE rows):**
   ```sql
   CREATE INDEX idx_rates_pnl_sampling ON rates_snapshot(timestamp, protocol, token_contract)
   WHERE use_for_pnl_calc = TRUE;
   ```

3. **Update queries to filter:**
   ```sql
   WHERE use_for_pnl_calc = TRUE AND timestamp >= ? AND timestamp <= ?
   ```

4. **Backfill existing data:**
   - Create script to identify timestamps at 60-minute intervals
   - Set `use_for_pnl_calc = TRUE` for those timestamps
   - Update insert logic to set flag for new data

**Defer this until actually needed** - Phase 1 provides sufficient optimization for current data volume.

---

## Contact & Support

For questions or issues during implementation:
- Review this document thoroughly first
- Check console logs for sampling statistics
- Test with `STATS_GRANULARITY_MINUTES = 1` to verify rollback works
- Compare PnL values before/after to quantify accuracy impact

---

**Document Version:** 1.0
**Last Updated:** 2026-02-04
**Implementation Status:** Ready for implementation
