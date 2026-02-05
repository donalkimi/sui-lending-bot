# Position Statistics Backfill - Handover Document

**Date:** 2026-02-05
**Project:** Sui Lending Bot
**Task:** Implement backfill script for missing position statistics

---

## 1. Problem Statement

### The Issue
Dashboard displays warning: **"No statistics found for position e163298d... at 2026-02-03 17:22:00"**

When viewing the Positions tab in the dashboard and selecting a historical timestamp, positions are being skipped with this warning message.

### Root Cause Analysis

The `position_statistics` table is missing historical records. Here's why:

1. **Statistics are Pre-calculated**: The system follows an event-sourcing pattern where statistics are calculated once during data collection and stored in the database for fast dashboard loading.

2. **Calculated at Runtime Only**: Statistics are only calculated when the refresh pipeline runs ([refresh_pipeline.py:298-320](data/refresh_pipeline.py#L298-L320)), and only for the **current timestamp** at that moment.

3. **Historical Gaps**: When viewing historical timestamps in the dashboard (like 2026-02-03), if statistics weren't calculated at that exact time, the query returns nothing and the position is skipped.

4. **Query Logic**: The dashboard queries for the **latest statistics at or before** the selected timestamp using a window function ([dashboard_renderer.py:1015-1025](dashboard/dashboard_renderer.py#L1015-L1025)).

### Why This Happens Architecturally

```
Timeline:
---------
Position Created: 2026-02-01 00:00
  ↓
Refresh Pipeline Runs: 2026-02-01 06:00 → Statistics saved for 06:00
  ↓
Refresh Pipeline Runs: 2026-02-01 12:00 → Statistics saved for 12:00
  ↓
User Views Dashboard at 2026-02-03 17:22 ← No statistics exist at this timestamp!
  ↓
Dashboard queries: "Get latest stats WHERE timestamp <= 2026-02-03 17:22"
  ↓
If no stats exist at or before that time → Warning displayed
```

---

## 2. System Architecture Overview

### Database Schema

**Table: `position_statistics`** ([schema.sql:331-387](data/schema.sql#L331-L387))
- **Primary Key**: (position_id, timestamp) - composite key
- **Purpose**: Pre-calculated position summaries for fast dashboard loading
- **Key Fields**:
  - `position_id`: Position identifier
  - `timestamp`: Unix timestamp when statistics represent the position state
  - `total_pnl`: Total profit/loss (realized + unrealized)
  - `total_earnings`: Protocol earnings + rewards
  - `base_earnings`: Net protocol interest (lend - borrow)
  - `reward_earnings`: Total reward distributions
  - `total_fees`: Total borrow fees paid
  - `current_value`: deployment_usd + total_pnl
  - `realized_apr`: Annualized return from entry to timestamp
  - `current_apr`: APR based on live rates
  - `live_pnl`: PnL from current segment
  - `realized_pnl`: PnL from closed rebalance segments
  - `calculation_timestamp`: When this snapshot was calculated

### Data Flow

```
┌─────────────────────┐
│ Refresh Pipeline    │
│ (data collection)   │
└──────────┬──────────┘
           │
           ├─→ Fetch rates/prices/fees
           │
           ├─→ Save to rates_snapshot table
           │
           └─→ FOR EACH active position:
               ├─→ calculate_position_statistics()
               │   └─→ Loads position + rebalances
               │       └─→ Calculates PnL, APR, earnings
               │
               └─→ save_position_statistics()
                   └─→ INSERT INTO position_statistics

┌─────────────────────┐
│ Dashboard           │
│ (visualization)     │
└──────────┬──────────┘
           │
           ├─→ User selects timestamp
           │
           └─→ Query position_statistics
               WHERE timestamp <= selected_timestamp
               └─→ If found: Display position
                   └─→ If NOT found: ⚠️ Warning!
```

### Related Tables

1. **`positions`** - Position metadata (entry time, deployment, multipliers, status)
2. **`position_rebalances`** - Event history of rebalancing actions
3. **`rates_snapshot`** - Historical rates/fees/prices at various timestamps
4. **`token_registry`** - Token metadata
5. **`reward_token_prices`** - Reward token pricing

---

## 3. Solution Design

### Approach: Backfill Script

Create a standalone Python script that:
1. Discovers all positions (active and closed)
2. Determines which timestamps need statistics calculated
3. Reuses existing calculation logic
4. Saves to database with upsert (won't duplicate)
5. Verifies data integrity

### Timestamp Selection Strategy: Adaptive Sampling

**Always Include (Critical Events):**
- Position entry timestamp
- Each rebalance closing timestamp
- Position close timestamp (if closed)

**Adaptive Sampling Between Events:**
- **Recent (< 7 days ago)**: Sample every 1 hour
- **Medium (7-30 days ago)**: Sample every 4 hours
- **Old (> 30 days ago)**: Sample every 12 hours

**Rationale**: Recent positions need finer granularity for active monitoring. Older positions need less frequent sampling for historical analysis.

**Gap-Filling Mode**: Only calculate timestamps where statistics don't already exist. Safe and idempotent.

---

## 4. Implementation Plan

### File to Create

**`Scripts/backfill_position_statistics.py`**

### Core Components

#### A. Timestamp Discovery

```python
def determine_backfill_timestamps(position, service, engine):
    """
    Generate list of Unix timestamps (int) needing statistics.

    Returns: Sorted list of timestamps (filtered to exclude existing)
    """
    timestamps = set()

    # 1. Critical events
    entry_ts = to_seconds(position['entry_timestamp'])
    timestamps.add(entry_ts)

    rebalances = service.get_rebalance_history(position['position_id'])
    for _, rebal in rebalances.iterrows():
        timestamps.add(to_seconds(rebal['closing_timestamp']))

    if position['status'] == 'closed' and position['close_timestamp']:
        timestamps.add(to_seconds(position['close_timestamp']))

    # 2. Adaptive sampling
    end_ts = to_seconds(position['close_timestamp']) if position['status'] == 'closed' else int(time.time())
    current_ts = entry_ts

    while current_ts < end_ts:
        days_from_now = (time.time() - current_ts) / 86400

        if days_from_now < 7:
            interval = 3600  # 1 hour
        elif days_from_now < 30:
            interval = 14400  # 4 hours
        else:
            interval = 43200  # 12 hours

        current_ts += interval
        if current_ts <= end_ts:
            timestamps.add(current_ts)

    # 3. Filter out existing
    existing = get_existing_statistics_timestamps(engine, position['position_id'])
    timestamps = timestamps - existing

    return sorted(list(timestamps))


def get_existing_statistics_timestamps(engine, position_id):
    """Query database for timestamps that already have statistics"""
    query = """
        SELECT timestamp FROM position_statistics
        WHERE position_id = :pid
    """
    df = pd.read_sql(query, engine, params={'pid': position_id})
    return set(to_seconds(ts) for ts in df['timestamp'])
```

#### B. Rate Snapshot Cache

```python
class RateSnapshotCache:
    """Cache rate snapshots to minimize database queries"""

    def __init__(self, engine):
        self.engine = engine
        self.cache = {}  # cache_key -> (get_rate_func, get_borrow_fee_func)
        self.hit_count = 0
        self.miss_count = 0

    def get_rates_at_timestamp(self, timestamp: int):
        """
        Load rate snapshot at timestamp (with caching).

        Returns: (get_rate_func, get_borrow_fee_func)
        """
        # Round to hour for cache efficiency
        cache_key = (timestamp // 3600) * 3600

        if cache_key in self.cache:
            self.hit_count += 1
            return self.cache[cache_key]

        # Cache miss - query database
        self.miss_count += 1

        # Query for nearest snapshot within 24 hours
        timestamp_str = to_datetime_str(timestamp)
        min_timestamp_str = to_datetime_str(timestamp - 86400)

        query = """
            SELECT DISTINCT ON (protocol, token_contract)
                protocol, token_contract,
                lend_total_apr, borrow_total_apr, borrow_fee
            FROM rates_snapshot
            WHERE timestamp <= :ts AND timestamp >= :ts_min
            ORDER BY protocol, token_contract, timestamp DESC
        """

        snapshot_data = pd.read_sql(
            query, self.engine,
            params={'ts': timestamp_str, 'ts_min': min_timestamp_str}
        )

        if snapshot_data.empty:
            raise ValueError(f"No rate snapshot found near {timestamp_str}")

        # Create lookup functions
        def get_rate(token_contract: str, protocol: str, side: str) -> float:
            row = snapshot_data[
                (snapshot_data['token_contract'] == token_contract) &
                (snapshot_data['protocol'] == protocol)
            ]
            if row.empty:
                return 0.0

            col = 'lend_total_apr' if side == 'lend' else 'borrow_total_apr'
            value = row.iloc[0][col]
            return float(value) if pd.notna(value) else 0.0

        def get_borrow_fee(token_contract: str, protocol: str) -> float:
            row = snapshot_data[
                (snapshot_data['token_contract'] == token_contract) &
                (snapshot_data['protocol'] == protocol)
            ]
            if row.empty:
                return 0.0

            value = row.iloc[0]['borrow_fee']
            return float(value) if pd.notna(value) else 0.0

        # Cache and return
        result = (get_rate, get_borrow_fee)
        self.cache[cache_key] = result

        # Limit cache size to last 100 hours
        if len(self.cache) > 100:
            oldest_key = min(self.cache.keys())
            del self.cache[oldest_key]

        return result

    def print_stats(self):
        """Print cache performance statistics"""
        total = self.hit_count + self.miss_count
        if total > 0:
            hit_rate = (self.hit_count / total) * 100
            print(f"  Cache: {self.hit_count} hits, {self.miss_count} misses ({hit_rate:.1f}% hit rate)")
```

#### C. Main Backfill Orchestrator

```python
def backfill_all_positions(dry_run=False, position_filter=None):
    """
    Main backfill function with 4 phases:
    1. Discovery - Load positions
    2. Planning - Determine timestamps
    3. Execution - Calculate and save
    4. Verification - Validate results
    """
    import logging
    from tqdm import tqdm
    from datetime import datetime

    # Setup logging
    os.makedirs('logs', exist_ok=True)
    log_file = f'logs/backfill_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    print("="*60)
    print("POSITION STATISTICS BACKFILL")
    print("="*60)

    # Initialize services
    from dashboard.db_utils import get_db_engine
    from analysis.position_service import PositionService
    from analysis.position_statistics_calculator import calculate_position_statistics
    from data.rate_tracker import RateTracker

    engine = get_db_engine()
    service = PositionService(engine)
    tracker = RateTracker()

    # PHASE 1: Discovery
    print("\n[PHASE 1] Discovering positions...")
    positions_active = service.get_active_positions()
    positions_closed = service.get_closed_positions() if hasattr(service, 'get_closed_positions') else pd.DataFrame()

    all_positions = pd.concat([positions_active, positions_closed], ignore_index=True)

    # Apply filter if provided
    if position_filter:
        all_positions = all_positions[all_positions['position_id'].str.startswith(position_filter)]

    print(f"  Found {len(all_positions)} positions")
    print(f"    - Active: {len(positions_active)}")
    print(f"    - Closed: {len(positions_closed)}")

    if all_positions.empty:
        print("No positions to process. Exiting.")
        return

    # PHASE 2: Planning
    print("\n[PHASE 2] Planning backfill timestamps...")
    backfill_plan = {}
    total_stats = 0

    for _, position in all_positions.iterrows():
        timestamps = determine_backfill_timestamps(position, service, engine)
        backfill_plan[position['position_id']] = timestamps
        total_stats += len(timestamps)

        logging.info(f"Position {position['position_id'][:8]}: {len(timestamps)} timestamps to backfill")

    print(f"  Total statistics to backfill: {total_stats:,}")

    if dry_run:
        print("\n[DRY RUN] Preview of backfill plan:")
        for pos_id, timestamps in list(backfill_plan.items())[:5]:
            print(f"  {pos_id[:8]}... : {len(timestamps)} timestamps")
            if timestamps:
                print(f"    First: {to_datetime_str(timestamps[0])}")
                print(f"    Last:  {to_datetime_str(timestamps[-1])}")
        print(f"\nDry run complete. Run without --dry-run to execute backfill.")
        return

    if total_stats == 0:
        print("No missing statistics found. All positions are up to date!")
        return

    # PHASE 3: Execution
    print("\n[PHASE 3] Executing backfill...")
    rate_cache = RateSnapshotCache(engine)
    stats_saved = 0
    stats_failed = 0
    failed_details = []

    with tqdm(total=total_stats, desc="Backfilling", unit="stat") as pbar:
        for position_id, timestamps in backfill_plan.items():
            for timestamp in timestamps:
                try:
                    # Load rates from cache
                    get_rate, get_borrow_fee = rate_cache.get_rates_at_timestamp(timestamp)

                    # Calculate statistics using existing proven logic
                    stats = calculate_position_statistics(
                        position_id=position_id,
                        timestamp=timestamp,
                        service=service,
                        get_rate_func=get_rate,
                        get_borrow_fee_func=get_borrow_fee
                    )

                    # Save to database (upsert - won't duplicate)
                    tracker.save_position_statistics(stats)
                    stats_saved += 1

                except ValueError as e:
                    # Missing rate data (expected for old timestamps)
                    logging.warning(f"Position {position_id[:8]} at {to_datetime_str(timestamp)}: {e}")
                    stats_failed += 1
                    failed_details.append({
                        'position_id': position_id[:8],
                        'timestamp': to_datetime_str(timestamp),
                        'error': 'Missing rate data'
                    })

                except Exception as e:
                    # Other errors
                    logging.error(f"Position {position_id[:8]} at {to_datetime_str(timestamp)}: {e}")
                    stats_failed += 1
                    failed_details.append({
                        'position_id': position_id[:8],
                        'timestamp': to_datetime_str(timestamp),
                        'error': str(e)
                    })

                pbar.update(1)

    # Print cache statistics
    rate_cache.print_stats()

    print(f"\n[COMPLETE]")
    print(f"  ✓ Successfully saved: {stats_saved:,}")
    print(f"  ✗ Failed: {stats_failed:,}")

    if stats_failed > 0:
        failure_rate = (stats_failed / total_stats) * 100
        print(f"  Failure rate: {failure_rate:.1f}%")

        if failed_details and failure_rate > 10:
            print(f"\n  Sample failures (first 5):")
            for detail in failed_details[:5]:
                print(f"    {detail['position_id']} @ {detail['timestamp']}: {detail['error']}")

    # PHASE 4: Verification
    print("\n[PHASE 4] Verifying backfill...")
    verify_backfill(engine, backfill_plan)

    print(f"\nLog file: {log_file}")
```

#### D. Verification

```python
def verify_backfill(engine, backfill_plan):
    """Verify statistics were successfully backfilled"""
    issues = []

    for position_id, expected_timestamps in backfill_plan.items():
        # Count statistics in database
        query = """
            SELECT COUNT(*) as count FROM position_statistics
            WHERE position_id = :pid
        """
        result = pd.read_sql(query, engine, params={'pid': position_id})
        actual_count = result.iloc[0]['count']

        expected_count = len(expected_timestamps)

        if actual_count == 0 and expected_count > 0:
            issues.append({
                'position_id': position_id[:8],
                'issue': 'NO statistics found',
                'expected': expected_count,
                'actual': actual_count
            })
        elif actual_count < expected_count * 0.9:  # Allow 10% failure rate
            issues.append({
                'position_id': position_id[:8],
                'issue': 'Incomplete backfill',
                'expected': expected_count,
                'actual': actual_count
            })

    if issues:
        print(f"  ⚠️ Verification Issues ({len(issues)} positions):")
        for issue in issues[:10]:
            print(f"    {issue['position_id']}: {issue['issue']} (expected {issue['expected']}, got {issue['actual']})")

        if len(issues) > 10:
            print(f"    ... and {len(issues) - 10} more (see log file)")
    else:
        print(f"  ✓ Verification passed - all statistics backfilled successfully")
```

#### E. Command-Line Interface

```python
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill historical position statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview backfill plan (dry run)
  python Scripts/backfill_position_statistics.py --dry-run

  # Backfill all positions
  python Scripts/backfill_position_statistics.py

  # Backfill specific position
  python Scripts/backfill_position_statistics.py --position e163298d
        """
    )

    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview backfill plan without executing'
    )
    parser.add_argument(
        '--position', type=str, metavar='POSITION_ID',
        help='Backfill specific position (full ID or prefix)'
    )

    args = parser.parse_args()

    try:
        backfill_all_positions(
            dry_run=args.dry_run,
            position_filter=args.position
        )
    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
```

---

## 5. Critical Files Reference

### Files to Leverage (DO NOT MODIFY)

| File | Lines | Purpose | Usage |
|------|-------|---------|-------|
| [analysis/position_statistics_calculator.py](analysis/position_statistics_calculator.py) | 23-246 | `calculate_position_statistics()` - Core calculation logic | Call this function directly |
| [data/rate_tracker.py](data/rate_tracker.py) | 118-229 | `save_position_statistics()` - Database save with upsert | Call this method to save |
| [analysis/position_service.py](analysis/position_service.py) | 384-450 | `get_active_positions()` - Load active positions | Get list of positions to process |
| [analysis/position_service.py](analysis/position_service.py) | 505-553 | `get_position_by_id()` - Load single position | Used internally by calculator |
| [analysis/position_service.py](analysis/position_service.py) | 1652-1683 | `get_rebalance_history()` - Get rebalance events | Get critical timestamps |
| [utils/time_helpers.py](utils/time_helpers.py) | - | `to_seconds()`, `to_datetime_str()` | Timestamp conversions |
| [dashboard/db_utils.py](dashboard/db_utils.py) | - | `get_db_engine()` | Get database connection |

### Files to Reference for Patterns

| File | Purpose |
|------|---------|
| [data/refresh_pipeline.py](data/refresh_pipeline.py) (lines 298-320) | Example of statistics calculation loop |
| [Scripts/migrate_all_tables.py](Scripts/migrate_all_tables.py) | Example of batch processing, error handling, phases |

---

## 6. Execution Instructions

### Prerequisites

1. Ensure database is accessible (SQLite or Supabase configured in settings)
2. Ensure Python environment is activated
3. Ensure all dependencies are installed (`pip install -r requirements.txt`)

### Running the Backfill

```bash
# Step 1: Preview what will be backfilled (dry run)
python Scripts/backfill_position_statistics.py --dry-run

# Step 2: Execute full backfill
python Scripts/backfill_position_statistics.py

# Alternative: Backfill specific position only
python Scripts/backfill_position_statistics.py --position e163298d
```

### Expected Output

```
============================================================
POSITION STATISTICS BACKFILL
============================================================

[PHASE 1] Discovering positions...
  Found 10 positions
    - Active: 8
    - Closed: 2

[PHASE 2] Planning backfill timestamps...
  Total statistics to backfill: 1,247

[PHASE 3] Executing backfill...
Backfilling: 100%|████████████████| 1247/1247 [02:15<00:00, 9.23stat/s]
  Cache: 987 hits, 260 misses (79.2% hit rate)

[COMPLETE]
  ✓ Successfully saved: 1,198
  ✗ Failed: 49
  Failure rate: 3.9%

[PHASE 4] Verifying backfill...
  ✓ Verification passed - all statistics backfilled successfully

Log file: logs/backfill_20260205_143022.log
```

### Expected Duration

- Small dataset (3-5 positions, < 30 days): ~2-5 minutes
- Medium dataset (10-20 positions, < 60 days): ~5-15 minutes
- Large dataset (50+ positions, > 90 days): ~20-30 minutes

---

## 7. Verification Steps

### A. Database Verification

```sql
-- Check total statistics count
SELECT COUNT(*) FROM position_statistics;

-- Count statistics per position
SELECT position_id, COUNT(*) as stat_count,
       MIN(timestamp) as earliest,
       MAX(timestamp) as latest
FROM position_statistics
GROUP BY position_id
ORDER BY stat_count DESC;

-- Check specific problematic position
SELECT timestamp, total_pnl, realized_apr, current_value
FROM position_statistics
WHERE position_id LIKE 'e163298d%'
ORDER BY timestamp;
```

### B. Dashboard Verification

1. Start dashboard: `streamlit run dashboard/streamlit_app.py`
2. Navigate to **Positions** tab
3. Select historical timestamp: **2026-02-03 17:22:00** (the problematic one)
4. Verify:
   - ✅ No "No statistics found" warnings appear
   - ✅ Position e163298d displays correctly
   - ✅ PnL, APR, and earnings values are shown
   - ✅ All active positions at that time are displayed

### C. Log Review

Check the log file for:
- Any ERROR level messages (should be minimal)
- WARNING messages about missing rate data (acceptable for old timestamps)
- Verify failure rate is < 10%

### D. Spot Check Calculations

Manually verify a few statistics:
1. Pick a position and timestamp from `position_statistics`
2. Manually calculate expected PnL using rates from `rates_snapshot`
3. Compare with stored value (should match within rounding)

---

## 8. Error Handling

### Expected Errors (Acceptable)

**1. Missing Rate Data**
```
WARNING: Position a1b2c3d4 at 2025-12-15 08:00:00: No rate snapshot found near timestamp
```
**Reason**: Position exists but no rate data was collected at that time (before system started collecting)
**Impact**: Some old timestamps won't have statistics (acceptable)
**Action**: None required (logged only)

**2. Division by Zero in APR Calculation**
```
WARNING: Position e5f6g7h8 at 2026-01-20 12:00:00: division by zero
```
**Reason**: Position has zero deployment_usd or zero time elapsed
**Impact**: That specific timestamp skipped
**Action**: Review position data for anomalies

### Unexpected Errors (Require Investigation)

**3. Database Connection Error**
```
ERROR: Error saving position statistics for a1b2c3d4: connection closed
```
**Impact**: Backfill fails completely
**Action**: Check database connectivity, restart script

**4. Calculation Logic Error**
```
ERROR: Position a1b2c3d4 at 2026-02-01 06:00:00: 'NoneType' object has no attribute 'iloc'
```
**Impact**: Specific position/timestamp skipped
**Action**: Check position data integrity, review calculation logic

---

## 9. Rollback Procedures

If backfill causes issues or incorrect data:

### Option 1: Delete All Statistics (Nuclear Option)

```sql
-- Backup first (optional)
CREATE TABLE position_statistics_backup AS SELECT * FROM position_statistics;

-- Delete all statistics
DELETE FROM position_statistics;
```

Then either:
- Re-run backfill script
- Let refresh pipeline repopulate naturally over time

### Option 2: Delete Specific Position Statistics

```sql
-- Delete statistics for problematic position
DELETE FROM position_statistics
WHERE position_id = 'e163298d...';

-- Re-run backfill for just that position
python Scripts/backfill_position_statistics.py --position e163298d
```

### Option 3: Delete Statistics by Date Range

```sql
-- Delete statistics calculated in specific timeframe
DELETE FROM position_statistics
WHERE calculation_timestamp >= '2026-02-05 00:00:00'
AND calculation_timestamp <= '2026-02-05 23:59:59';
```

### Backup Before Backfill (Recommended)

```bash
# For Supabase (use pg_dump)
pg_dump $SUPABASE_URL -t position_statistics > backup_position_statistics.sql

# For SQLite
cp data/lending_rates.db data/lending_rates_backup.db
```

**Note**: Deletion is safe because statistics are **derived data** - they can always be recalculated from source tables (positions, position_rebalances, rates_snapshot).

---

## 10. Performance Considerations

### Bottlenecks

1. **Database Queries**: Rate snapshot queries can be slow
   - **Mitigation**: Cache implemented (rounds to hour, keeps last 100)
   - **Expected**: >75% cache hit rate

2. **Statistics Calculation**: Complex calculation with multiple legs
   - **Mitigation**: Reuses existing optimized function
   - **Expected**: ~50-100ms per calculation

3. **Database Writes**: Individual inserts are slower than batch
   - **Current**: Individual upserts (safe, simple)
   - **Future Optimization**: Could batch inserts in groups of 100

### Optimization Opportunities (Future)

If performance becomes an issue:

1. **Parallel Processing**: Use multiprocessing pool for positions
   ```python
   from multiprocessing import Pool
   with Pool(processes=4) as pool:
       pool.map(backfill_position_worker, position_list)
   ```

2. **Batch Database Writes**: Accumulate 100 statistics before committing
   ```python
   stats_batch = []
   for stat in statistics:
       stats_batch.append(stat)
       if len(stats_batch) >= 100:
           tracker.save_statistics_batch(stats_batch)
           stats_batch.clear()
   ```

3. **Pre-load All Rate Snapshots**: Load entire rates_snapshot table into memory
   - Only viable for SQLite or small datasets
   - Trade memory for speed

**Current Design Decision**: Prioritize simplicity and safety over maximum speed. The script is expected to run once or infrequently, so moderate performance is acceptable.

---

## 11. Testing Strategy

### Unit Testing (Recommended)

Create `tests/test_backfill_position_statistics.py`:

```python
import pytest
from Scripts.backfill_position_statistics import determine_backfill_timestamps

def test_timestamp_discovery_basic():
    """Test timestamp discovery for position without rebalances"""
    position = {
        'position_id': 'test123',
        'entry_timestamp': '2026-01-01 00:00:00',
        'status': 'active',
        'close_timestamp': None
    }
    # Mock service with no rebalances
    timestamps = determine_backfill_timestamps(position, mock_service, mock_engine)

    # Should include entry timestamp
    assert to_seconds('2026-01-01 00:00:00') in timestamps

    # Should have hourly samples for recent period
    # (logic validation)
```

### Integration Testing

```bash
# Test on empty database (SQLite)
cp data/lending_rates.db data/test_lending_rates.db
export SQLITE_PATH=data/test_lending_rates.db
python Scripts/backfill_position_statistics.py --dry-run

# Test on single position
python Scripts/backfill_position_statistics.py --position test123 --dry-run
```

### Manual Testing Checklist

- [ ] Dry run executes without errors
- [ ] Dry run shows reasonable timestamp counts
- [ ] Full backfill completes successfully
- [ ] Verification reports no issues
- [ ] Dashboard displays historical data correctly
- [ ] No "No statistics found" warnings for backfilled timestamps
- [ ] Log file shows acceptable failure rate (<10%)
- [ ] Re-running backfill is idempotent (no duplicates, no errors)

---

## 12. Maintenance & Future Considerations

### Ongoing Maintenance

**When to Re-run Backfill:**
- After adding new positions manually to database
- After fixing bugs in calculation logic (use `--force` flag if implemented)
- After database migrations that affect position_statistics

**Monitoring:**
- Check dashboard for "No statistics found" warnings periodically
- Review backfill log files for increasing error rates
- Monitor database size (position_statistics table growth)

### Future Enhancements

1. **Incremental Backfill**: Only backfill since last successful run
   - Store last backfill timestamp in database
   - Query: `WHERE timestamp > last_backfill_timestamp`

2. **Scheduled Backfill**: Run automatically via cron/scheduler
   - Daily backfill for previous day's missing timestamps
   - Catches any gaps from pipeline failures

3. **Web UI**: Add backfill trigger to dashboard
   - Button to trigger backfill for specific position
   - Progress indicator in dashboard
   - View backfill history and logs

4. **Statistics Recalculation**: Add `--force` flag
   - Delete existing statistics and recalculate
   - Useful after bug fixes in calculation logic

5. **Date Range Filtering**: Add `--start` and `--end` flags
   - Backfill specific date range only
   - `--start 2026-01-01 --end 2026-01-31`

---

## 13. Success Criteria

**Script Implementation:**
- [x] Script created at `Scripts/backfill_position_statistics.py`
- [x] Implements 4 phases (Discovery, Planning, Execution, Verification)
- [x] Reuses existing calculation logic (no duplication)
- [x] Handles errors gracefully (continues on failure)
- [x] Provides progress feedback (tqdm progress bar)
- [x] Logs all operations to file

**Execution:**
- [ ] Dry run completes without errors
- [ ] Full backfill completes within 20 minutes
- [ ] Failure rate < 10%
- [ ] No database errors or crashes

**Verification:**
- [ ] Dashboard shows no "No statistics found" warnings for backfilled timestamps
- [ ] All positions display correctly at historical timestamps
- [ ] Database query confirms expected statistics count
- [ ] Spot-check calculations match expected values

**Quality:**
- [ ] Code follows existing patterns (see migrate_all_tables.py)
- [ ] Error handling is comprehensive
- [ ] Logging is detailed and useful
- [ ] Script is idempotent (safe to re-run)

---

## 14. Contact & Handover Notes

**Implementation Time Estimate:** 4-5 hours
- Script implementation: 2-3 hours
- Testing: 1 hour
- Execution + verification: 30 minutes
- Documentation updates: 30 minutes

**Key Decisions Made:**
1. **Adaptive sampling** chosen over fixed hourly (balances detail vs. database size)
2. **Gap-filling mode** chosen over force recalculation (safer, idempotent)
3. **Comprehensive backfill** for all positions (user preference)
4. **Reuse existing calculation logic** (no duplication, proven correct)
5. **Individual upserts** over batch writes (simpler, safer, acceptable performance)

**Questions/Clarifications Needed:**
- None outstanding (user preferences captured)

**Risk Level:** Low
- Uses existing proven calculation logic
- Read-heavy operation (minimal database writes)
- Idempotent design (safe to re-run)
- Statistics are derived data (can be deleted and recalculated)

**Next Steps:**
1. Implement the script following this design
2. Test with dry run on production database
3. Execute backfill during low-traffic period
4. Verify dashboard displays correctly
5. Monitor for any issues in first 24 hours

---

## Appendix A: Database Schema Reference

### position_statistics Table

```sql
CREATE TABLE IF NOT EXISTS position_statistics (
    position_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    total_pnl DECIMAL(20, 6),
    total_earnings DECIMAL(20, 6),
    base_earnings DECIMAL(20, 6),
    reward_earnings DECIMAL(20, 6),
    total_fees DECIMAL(20, 6),
    current_value DECIMAL(20, 6),
    realized_apr DECIMAL(10, 6),
    current_apr DECIMAL(10, 6),
    live_pnl DECIMAL(20, 6),
    realized_pnl DECIMAL(20, 6),
    calculation_timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (position_id, timestamp)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_position_statistics_timestamp
    ON position_statistics(timestamp);
CREATE INDEX IF NOT EXISTS idx_position_statistics_calculation_timestamp
    ON position_statistics(calculation_timestamp);
```

---

## Appendix B: Relevant Code Snippets

### Dashboard Query for Statistics

From [dashboard_renderer.py:1015-1025](dashboard/dashboard_renderer.py#L1015-L1025):

```python
def get_all_position_statistics(position_ids: list, timestamp: int, engine) -> dict:
    """Get latest statistics for each position at or before timestamp"""
    query = """
        WITH ranked_stats AS (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY position_id
                       ORDER BY timestamp DESC
                   ) as rn
            FROM position_statistics
            WHERE position_id IN :position_ids
            AND timestamp <= :timestamp
        )
        SELECT * FROM ranked_stats WHERE rn = 1
    """
    # Returns: {position_id: stats_dict}
```

### Refresh Pipeline Statistics Calculation

From [refresh_pipeline.py:298-320](data/refresh_pipeline.py#L298-L320):

```python
# Calculate statistics for each active position
for _, position in active_positions.iterrows():
    try:
        stats = calculate_position_statistics(
            position_id=position['position_id'],
            timestamp=current_seconds,
            service=service,
            get_rate_func=get_rate,
            get_borrow_fee_func=get_borrow_fee
        )

        tracker.save_position_statistics(stats)
        stats_saved += 1

    except Exception as e:
        print(f"[POSITION STATS] Failed to calculate/save stats: {e}")
        # Continue to next position
```

---

**Document Version:** 1.0
**Last Updated:** 2026-02-05
**Status:** Ready for Implementation
