# Sui Lending Bot - Design Notes

## Critical Principles

### 1. Timestamp as "Current Time"

**Core Principle:** When the user selects a timestamp in the dashboard, that timestamp IS the "live"/"current"/present time. Everything flows from that timestamp.

- **Dashboard queries:** All data fetching should use `WHERE timestamp <= strategy_timestamp`
- **Never use datetime.now():** NEVER default to `datetime.now()` except when collecting fresh market data from protocols
- **Historical context:** The selected timestamp defines "now" - all historical data is everything UP TO that point
- **Time travel:** This allows the dashboard to act as a time machine - showing what was available at any historical moment

**Example:**
```python
# CORRECT: Get all data up to the selected moment
query = "SELECT * FROM rates_snapshot WHERE timestamp <= ? AND ..."
params = (strategy_timestamp, ...)

# WRONG: Using datetime.now() or arbitrary cutoff dates
cutoff = datetime.now() - timedelta(days=30)  # ❌ NO!
```

### 2. No datetime.now() Defaults

**Rule:** `datetime.now()` should NEVER be called anywhere except when collecting new market snapshots.

- **Fail loudly:** If a timestamp is required but missing, throw an error - don't default to now()
- **Explicit timestamps:** All functions must receive timestamps explicitly from the call chain
- **Testing:** This makes the system deterministic and testable with historical data

**Why:** Default timestamps masked bugs and made debugging impossible. All timestamps must be explicit and traceable.

### 3. Position Sizing

Positions use normalized multipliers (L_A, B_A, L_B, B_B) that are scaled by deployment_usd:
- Actual USD amount for any leg = multiplier * deployment_usd
- This allows flexible position sizing without recalculating strategy structure

### 4. Event Sourcing

The positions table stores immutable entry state, while position_snapshots captures state changes over time. Never mutate historical records.

### 5. Timestamp Representation: Unix Seconds

**Core Principle:** Database stays as-is (TIMESTAMP columns with datetime strings). All internal Python code operates on Unix timestamps (seconds as integers).

**Conversion boundaries:**
- **DB → Code:** Read timestamp string, immediately convert to seconds (int)
- **Code → DB:** Convert seconds (int) to datetime string for queries
- **Code → UI:** Convert seconds (int) to datetime string for display
- **UI → Code:** Read datetime string, immediately convert to seconds (int)
- **Internal processing:** Everything in seconds (integers)

**Architecture:**
```
┌──────────────────────┐
│      Database        │ TIMESTAMP columns (datetime strings)
│                      │ "2026-01-16 12:00:00"
└──────────┬───────────┘
           │
           │ Read from DB: to_seconds("2026-01-16 12:00:00") → 1737028800
           │ Write to DB:  to_datetime_str(1737028800) → "2026-01-16 12:00:00"
           │
           ▼
┌──────────────────────┐
│   Python Code        │ Unix timestamps (seconds as int)
│   (Everything)       │ 1737028800
│                      │
│ • rate_analyzer.py   │ All comparisons: seconds > seconds
│ • position_service   │ All math: seconds - seconds
│ • dashboard_utils    │ All logic: if seconds <= seconds
│ • refresh_pipeline   │
└──────────┬───────────┘
           │
           │ Display to user: to_datetime_str(1737028800) → "2026-01-16 12:00:00"
           │ Input from user: to_seconds("2026-01-16 12:00:00") → 1737028800
           │
           ▼
┌──────────────────────┐
│     UI/Dashboard     │ Datetime strings (human readable)
│                      │ "2026-01-16 12:00:00"
└──────────────────────┘
```

**TWO WRAPPER FUNCTIONS HANDLE ALL CONVERSIONS:**
```python
def to_seconds(anything) -> int:
    """
    Handles: str, datetime, pandas.Timestamp, int
    ONE function for EVERYTHING → seconds
    """
    pass

def to_datetime_str(int) -> str:
    """
    ONE format for EVERYTHING: "2026-01-16 12:00:00"
    Used for: DB writes, UI display, everywhere
    """
    pass
```

**Why:**
- **Type safety:** Integers are simple, comparable, and fast
- **No pandas/datetime confusion:** No more "what type is this timestamp?"
- **SQL compatibility:** String format works universally across SQLite and PostgreSQL
- **Clear boundaries:** Conversion happens only at system edges (DB/UI)
- **Easy arithmetic:** Time deltas are just `seconds2 - seconds1`

### 6. Streamlit Chart Width Parameter

**IMPORTANT:** `use_container_width` is deprecated and will be removed after 2025-12-31.

**Always use:**
- `width="stretch"` instead of `use_container_width=True`
- `width="content"` instead of `use_container_width=False`

**Applies to:** st.plotly_chart, st.dataframe, st.table, and other display components
