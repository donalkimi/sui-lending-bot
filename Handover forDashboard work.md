# Sui Lending Bot - Handover Document

## Overview

The Sui Lending Bot is a dashboard application for analyzing and executing recursive lending strategies across multiple Sui DeFi protocols (AlphaFi, Navi, Suilend). The system tracks rates, calculates optimal position sizes, manages paper trading positions, and provides historical time-travel functionality.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard                       │
│                 (dashboard_renderer.py)                      │
│  - All Strategies Tab                                        │
│  - Rate Tables Tab                                           │
│  - Zero Liquidity Tab                                        │
│  - Positions Tab ← FOCUS OF THIS DOCUMENT                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              Analysis & Business Logic Layer                 │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  RateAnalyzer    │  │ PositionService  │               │
│  │  (rate_analyzer) │  │ (position_service)│               │
│  └──────────────────┘  └──────────────────┘               │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │PositionCalculator│  │  UnifiedDataLoader│              │
│  │(position_calculator) │(dashboard_utils)  │              │
│  └──────────────────┘  └──────────────────┘               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Data Collection Layer                     │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  Protocol Merger │  │  Protocol Readers│               │
│  │(protocol_merger) │  │  (NaviReader, etc)│              │
│  └──────────────────┘  └──────────────────┘               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                      SQLite Database                         │
│                                                              │
│  - rates_snapshot: Historical rates, prices, CF, LLTV       │
│  - positions: Active/closed positions (current state)       │
│  - position_rebalances: Historical segments (event sourcing)│
│  - token_registry: Token metadata and contracts             │
│  - reward_token_prices: Reward token prices                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Positions Tab: Deep Dive

### Purpose
The Positions Tab displays and manages paper trading positions with support for:
- Real-time position valuation
- Historical time-travel (view positions at any past timestamp)
- Position rebalancing
- Detailed 4-leg breakdown with liquidation calculations

### Core Design Principles

#### 1. **Timestamp as Current Time** (Critical!)
The dashboard-selected timestamp represents "now" for ALL queries and calculations.

```python
# When user selects 2026-01-20 14:00:00
timestamp_seconds = 1737381600  # Unix seconds

# This becomes "current time" for:
- Position filtering (show positions deployed before/at this time)
- Rate queries (get rates at this timestamp)
- Price lookups (get prices at this timestamp)
- PnL calculations (calculate earnings from entry → this timestamp)
```

**Implications:**
- NEVER use `datetime.now()` except when collecting fresh data
- All timestamps are Unix seconds (int) internally
- Database stores timestamps as strings: `'YYYY-MM-DD HH:MM:SS'` (19 chars, NO microseconds)

#### 2. **Event Sourcing for Rebalances**
The `positions` table stores CURRENT state. The `position_rebalances` table stores historical segments.

```python
# Positions Table: Current state (mutable)
{
    'position_id': '...',
    'L_A': 1.5,           # Current multipliers
    'B_A': 1.2,
    'L_B': 1.2,
    'B_B': 0.85,
    'rebalance_count': 2,  # Number of rebalances
    'entry_timestamp': '2026-01-13 10:52:47'
}

# Position Rebalances Table: Historical segments (immutable)
{
    'rebalance_id': '...',
    'position_id': '...',
    'sequence_number': 1,
    'opening_timestamp': '2026-01-13 10:52:47',  # Segment start
    'closing_timestamp': '2026-01-20 15:00:00',  # Segment end
    'L_A': 1.5,           # Position state during this segment
    'B_A': 1.2,
    'L_B': 1.2,
    'B_B': 0.85,
    'realised_pnl': 125.50  # PnL for this segment only
}
```

#### 3. **Time-Travel Algorithm**
When viewing historical timestamps, retrieve the position state that existed at that time.

**Logic:**
1. If `rebalance_count == 0`: Use current state from `positions` table
2. If rebalanced: Query `position_rebalances` for segment where:
   - `opening_timestamp <= selected_timestamp < closing_timestamp`
3. If found: Use segment state (pre-rebalance multipliers)
4. If not found: Use current state from `positions` table

**Implementation:** `get_position_state_at_timestamp()` in [analysis/position_service.py:1127-1210](analysis/position_service.py#L1127-L1210)

---

## Critical Files & Components

### 1. Dashboard Rendering

**File:** [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)

#### Key Functions:

##### `render_positions_table_tab(timestamp_seconds: int)`
**Location:** Lines 960-1901
**Purpose:** Main entry point for Positions Tab

**Flow:**
```python
1. Connect to database
2. Get active positions filtered by timestamp:
   active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)
3. Handle empty state (no positions at this timestamp)
4. Query rates/prices at selected timestamp
5. For each position:
   - Display summary row (expandable)
   - When expanded: show detailed 4-leg breakdown
6. Calculate position value using calculate_position_value()
7. Display rebalance history
```

**Key Features:**
- **Timestamp Filtering:** Only shows positions deployed before/at selected timestamp
- **Context-Aware Messaging:** Different messages for historical vs current views
- **Expandable Rows:** Summary → Detailed breakdown with token details
- **Time-Travel Paradox Prevention:** Disables rebalance button when viewing past timestamps with future rebalances

##### Helper Functions (Lines 1004-1054)
```python
def get_rate(token, protocol, rate_type):
    """Get lend/borrow rate from rates_df"""

def get_borrow_fee(token, protocol):
    """Get borrow fee from rates_df"""

def get_price(token, protocol):
    """Get price from rates_df"""
    # Returns 0.0 if not found (defensive)
```

**Important:** These helpers query `rates_df`, which is populated at the selected timestamp:
```python
rates_df = pd.read_sql_query("""
    SELECT protocol, token, lend_total_apr, borrow_total_apr, borrow_fee, price_usd
    FROM rates_snapshot
    WHERE timestamp = ?
""", conn, params=(latest_timestamp_str,))
```

### 2. Position Service (Business Logic)

**File:** [analysis/position_service.py](analysis/position_service.py)

#### Key Methods:

##### `get_active_positions(live_timestamp: Optional[int] = None) -> pd.DataFrame`
**Location:** Lines 271-387
**Purpose:** Retrieve active positions, optionally filtered by timestamp

**Signature:**
```python
def get_active_positions(self, live_timestamp: Optional[int] = None) -> pd.DataFrame:
    """
    Get all active positions, optionally filtered by timestamp.

    Args:
        live_timestamp: Unix seconds representing "current time"
                       If provided, only returns positions where entry_timestamp <= live_timestamp

    Returns:
        DataFrame of active positions (may be empty)
    """
```

**Key Features:**
- Backward compatible: `None` returns all active positions
- Filters positions: `positions[positions['entry_timestamp'] <= live_timestamp]`
- Converts all numeric fields from database (handles bytes/corrupted data)
- Returns empty DataFrame if no matches (not an error)

##### `get_position_by_id(position_id: str) -> Optional[pd.Series]`
**Location:** Lines 389-465
**Purpose:** Retrieve single position by ID with defensive data conversion

**Key Features:**
- Converts timestamps to Unix seconds (int)
- Converts ALL numeric fields using `safe_to_int()` and `safe_to_float()`
- Handles bytes data from database (SQLite quirk)
- Returns properly-typed data for downstream consumers

**Defensive Helpers:**
```python
def safe_to_int(value, default=0):
    """Convert bytes/NaN/string to int"""

def safe_to_float(value, default=0.0):
    """Convert bytes/NaN/string to float"""
```

##### `calculate_position_value(position: pd.Series, live_timestamp: int) -> Dict`
**Location:** Lines 469-656
**Purpose:** Calculate current position value and PnL breakdown

**Algorithm:**
1. Validate: `live_timestamp >= entry_timestamp` (safety guard)
2. Extract position parameters (deployment, L_A, B_A, L_B, B_B)
3. Query ALL timestamps between entry and live timestamp
4. For each period `[t_i, t_{i+1})`:
   - Get rates for all 4 legs at `t_i`
   - Calculate earnings/costs for this period
   - Accumulate totals
5. Return:
   ```python
   {
       'current_value': deployment + net_earnings,
       'lend_earnings': LE(T),
       'borrow_costs': BC(T),
       'fees': upfront borrow fees,
       'net_earnings': LE(T) - BC(T) - FEES,
       'holding_days': (live_timestamp - entry_timestamp) / 86400,
       'periods_count': number of time periods
   }
   ```

**Forward-Looking Calculation:**
- Each timestamp's rates apply to the period `[timestamp, next_timestamp)`
- This matches how on-chain interest accrual works

##### `get_position_state_at_timestamp(position_id: str, selected_timestamp: int) -> Optional[Dict]`
**Location:** Lines 1127-1210
**Purpose:** Time-travel: get position state as it existed at a historical timestamp

**Algorithm:**
```python
1. Get current position from positions table
2. If rebalance_count == 0:
   - Return current state (never rebalanced)
3. Query position_rebalances for segment where:
   - opening_timestamp <= selected_timestamp < closing_timestamp
4. If segment found:
   - Return segment state (pre-rebalance multipliers)
5. If no segment:
   - Return current state (before first or after last rebalance)
```

**Use Case:** When viewing historical timestamp Wednesday, but position was rebalanced Thursday, this method returns the pre-rebalance state (as it existed Wednesday).

##### `has_future_rebalances(position_id: str, selected_timestamp: int) -> bool`
**Location:** Lines 1114-1159
**Purpose:** Check if position has been rebalanced AFTER selected timestamp

**Use Case:** Prevent time-travel paradoxes - disable rebalance button when viewing past timestamps with future rebalances.

##### `create_position(...) -> str`
**Location:** Lines 32-181
**Purpose:** Create new position from strategy

**Parameters:**
- `strategy_row`: DataFrame row with strategy details
- `positions`: Dict with `{L_A, B_A, L_B, B_B}` multipliers
- Token info, protocol info, deployment_usd, etc.

**Stored Data:**
- Entry timestamp (Unix seconds → DB string)
- Position multipliers (L_A, B_A, L_B, B_B)
- Entry rates for all 4 legs
- Entry prices for all 4 legs
- Entry collateral ratios and liquidation thresholds
- Entry borrow weights (for LLTV calculation)
- Entry fees and liquidity metrics

##### `create_rebalance_record(...) -> str`
**Location:** Lines 888-1106
**Purpose:** Create immutable historical segment when rebalancing

**Creates:**
- New row in `position_rebalances` table
- Stores opening and closing state (rates, prices, multipliers)
- Calculates realized PnL for this segment
- Updates `positions` table with new current state

### 3. Position Calculator (Strategy Math)

**File:** [analysis/position_calculator.py](analysis/position_calculator.py)

#### Key Methods:

##### `calculate_positions(...) -> Dict`
**Location:** Lines 31-135
**Purpose:** Calculate recursive position sizes (L_A, B_A, L_B, B_B)

**Algorithm:**
```python
# Use LLTV (liquidation threshold) with safety buffer
r_A = (LLTV_A / borrow_weight_A) / (1 + liq_dist)
r_B = (LLTV_B / borrow_weight_B) / (1 + liq_dist)

# Geometric series convergence
L_A = 1 / (1 - r_A * r_B)
B_A = L_A * r_A
L_B = B_A
B_B = L_B * r_B

# Auto-adjustment if effective LTV exceeds maxCF
if effective_LTV_A > collateral_ratio_A:
    r_A = (collateral_ratio_A * 0.995) / borrow_weight_A
    # Recalculate positions
```

**Returns:** `{L_A, B_A, L_B, B_B, r_A, r_B, LLTV_A, LLTV_B, ...}`

##### `calculate_liquidation_price(...) -> Dict`
**Location:** Lines 287-398
**Purpose:** Calculate liquidation price and distance for a token

**Parameters:**
- `collateral_value`: USD value of collateral
- `loan_value`: USD value of loan (adjusted by borrow_weight)
- `lending_token_price`: Current price of collateral token
- `borrowing_token_price`: Current price of borrowed token
- `lltv`: Liquidation threshold (0.75 = 75%)
- `side`: 'lending' (price must drop) or 'borrowing' (price must rise)
- `borrow_weight`: Multiplier for borrowed asset (default 1.0)

**Returns:**
```python
{
    'liq_price': liquidation price,
    'current_price': current price,
    'pct_distance': percentage distance to liquidation,
    'direction': 'up'/'down'/'liquidated'/'impossible'
}
```

**Used By:** Dashboard to display liquidation prices for all 4 legs

### 4. Rate Analyzer (Strategy Discovery)

**File:** [analysis/rate_analyzer.py](analysis/rate_analyzer.py)

##### `analyze_all_combinations(...) -> pd.DataFrame`
**Location:** Lines 273-598
**Purpose:** Find all valid recursive lending strategies

**Process:**
1. Iterate all protocol pairs (AlphaFi ↔ Navi, etc.)
2. Iterate all token combinations
3. For each combination:
   - Get rates, prices, collateral ratios, liquidation thresholds
   - Skip if any missing data or zero values
   - Call `PositionCalculator.analyze_strategy(...)`
   - Store result if valid
4. Return DataFrame sorted by net APR

**Key Validation:**
```python
# Skip if collateral ratios are zero
if collateral_1A <= 1e-9 or collateral_2B <= 1e-9:
    continue

# Skip if liquidation thresholds are zero
if LLTV_1A <= 1e-9 or LLTV_2B <= 1e-9:
    continue

# Skip if any prices are zero
if any(p <= 1e-9 for p in [price_1A, price_2A, price_2B, price_3B]):
    continue
```

---

## Database Schema

### Core Tables

#### `rates_snapshot`
**Purpose:** Historical rates, prices, collateral factors, liquidation thresholds

**Key Columns:**
- `timestamp` (TIMESTAMP): Exact 19 characters `'YYYY-MM-DD HH:MM:SS'` (NO microseconds)
- `protocol` (VARCHAR): AlphaFi, Navi, Suilend
- `token` (VARCHAR): Human-readable token symbol
- `token_contract` (TEXT): Full Sui coin type (unique identifier)
- `lend_total_apr`, `borrow_total_apr` (DECIMAL): Total APRs (base + rewards)
- `price_usd` (DECIMAL): Token price in USD
- `collateral_ratio` (DECIMAL): Max LTV (e.g., 0.70 = 70%)
- `liquidation_threshold` (DECIMAL): Liquidation LTV (e.g., 0.75 = 75%)
- `borrow_weight` (DECIMAL): Multiplier for borrowed assets (default 1.0)
- `borrow_fee` (DECIMAL): One-time borrow fee
- `available_borrow_usd` (DECIMAL): Liquidity available to borrow

**Primary Key:** `(timestamp, protocol, token_contract)`

**Critical:** Timestamp precision MUST be exactly 19 characters. Use [Scripts/truncate_timestamps.py](Scripts/truncate_timestamps.py) if microseconds exist.

#### `positions`
**Purpose:** Active and closed positions (current state)

**Key Columns:**
- `position_id` (TEXT): UUID primary key
- `status` (TEXT): 'active', 'closed', 'liquidated'
- `entry_timestamp` (TIMESTAMP): When position was deployed
- `deployment_usd` (DECIMAL): Initial capital (e.g., 10000.00)
- `L_A`, `B_A`, `L_B`, `B_B` (DECIMAL): Position multipliers
- `token1`, `token2`, `token3` (TEXT): Token symbols (for display)
- `token1_contract`, `token2_contract`, `token3_contract` (TEXT): Token contracts (for queries)
- `protocol_A`, `protocol_B` (TEXT): Protocol names
- `entry_lend_rate_1A`, `entry_borrow_rate_2A`, ... (DECIMAL): Entry rates (decimals, NOT percentages)
- `entry_price_1A`, `entry_price_2A`, ... (DECIMAL): Entry prices
- `entry_collateral_ratio_1A`, `entry_collateral_ratio_2B` (DECIMAL): Entry collateral factors
- `entry_liquidation_threshold_1A`, `entry_liquidation_threshold_2B` (DECIMAL): Entry LLTVs
- `entry_borrow_weight_2A`, `entry_borrow_weight_3B` (DECIMAL): Entry borrow weights
- `rebalance_count` (INTEGER): Number of times rebalanced
- `accumulated_realised_pnl` (DECIMAL): Sum of realized PnL from all rebalances

**Mutable Fields:** Current state can be updated during rebalancing

#### `position_rebalances`
**Purpose:** Immutable historical segments (event sourcing)

**Key Columns:**
- `rebalance_id` (TEXT): UUID primary key
- `position_id` (TEXT): Foreign key to positions
- `sequence_number` (INTEGER): Rebalance order (1, 2, 3, ...)
- `opening_timestamp` (TIMESTAMP): Segment start
- `closing_timestamp` (TIMESTAMP): Segment end
- `L_A`, `B_A`, `L_B`, `B_B` (DECIMAL): Position state during segment (constant)
- `opening_lend_rate_1A`, ..., `closing_lend_rate_1A`, ... (DECIMAL): Rates at open and close
- `opening_price_1A`, ..., `closing_price_1A`, ... (DECIMAL): Prices at open and close
- `realised_pnl` (DECIMAL): PnL for THIS segment only
- `realised_lend_earnings`, `realised_borrow_costs`, `realised_fees` (DECIMAL): Breakdown

**Immutable:** Records are NEVER updated after creation

**Unique Constraint:** `(position_id, sequence_number)`

---

## Common Workflows

### Deploy a New Position

**User Flow:**
1. Navigate to "All Strategies" tab
2. Select a strategy from the sorted list
3. Click "Deploy Strategy" button
4. See confirmation in positions tab

**Code Flow:**
```python
# dashboard_renderer.py (All Strategies Tab)
if st.button("Deploy Strategy"):
    # Build positions dict with multipliers
    positions = {
        'L_A': strategy['L_A'],
        'B_A': strategy['B_A'],
        'L_B': strategy['L_B'],
        'B_B': strategy['B_B']
    }

    # Create position
    service.create_position(
        strategy_row=pd.Series(strategy),
        positions=positions,
        token1=strategy['token1'],
        token2=strategy['token2'],
        token3=strategy['token3'],
        # ... more params
    )
```

### Rebalance a Position

**User Flow:**
1. Navigate to "Positions" tab
2. Expand a position row
3. Click "Rebalance Position" button
4. See updated rates, PnL calculation, and confirmation

**Code Flow:**
```python
# dashboard_renderer.py (Positions Tab)
if st.button("🔄 Rebalance Position"):
    # Check for time-travel paradox
    if service.has_future_rebalances(position_id, timestamp_seconds):
        st.error("Cannot rebalance: future rebalances exist")
        return

    # Build snapshot with opening/closing state
    snapshot = {
        'opening_timestamp': position['entry_timestamp'],
        'closing_timestamp': timestamp_seconds,
        'opening_lend_rate_1A': position['entry_lend_rate_1A'],
        'closing_lend_rate_1A': current_rate_1A,
        # ... all rates and prices
        'L_A': position['L_A'],
        # ... multipliers (remain constant)
        'realised_pnl': calculated_pnl,
        # ... breakdown
    }

    # Create rebalance record
    service.create_rebalance_record(
        position_id=position_id,
        snapshot=snapshot,
        rebalance_reason="User initiated",
        rebalance_notes=notes
    )
```

### Time-Travel to Historical Timestamp

**User Flow:**
1. Use timestamp selector at top of dashboard
2. Select past timestamp (e.g., yesterday)
3. Positions tab shows only positions deployed before/at that time
4. Position values calculated from entry → selected timestamp
5. If position rebalanced after selected time, shows pre-rebalance state

**Code Flow:**
```python
# dashboard_renderer.py (main)
timestamp_seconds = timestamp_selector.get_selected_timestamp()

# Positions Tab
active_positions = service.get_active_positions(live_timestamp=timestamp_seconds)
# Returns only positions where entry_timestamp <= timestamp_seconds

for position in active_positions:
    # Calculate value from entry → timestamp_seconds
    pv_result = service.calculate_position_value(position, timestamp_seconds)

    # Get historical state (if rebalanced after timestamp_seconds)
    historical_state = service.get_position_state_at_timestamp(
        position['position_id'],
        timestamp_seconds
    )
    # Use historical_state for display if different from current
```

---

## Critical Design Considerations

### 1. Timestamp Consistency

**Problem:** Database stored timestamps with microseconds, causing exact match queries to fail.

**Solution:** All timestamps MUST be exactly 19 characters: `'YYYY-MM-DD HH:MM:SS'`

**Prevention:**
- Use [Scripts/truncate_timestamps.py](Scripts/truncate_timestamps.py) to fix existing data
- Ensure data collection pipeline stores timestamps without microseconds
- Use `to_datetime_str()` helper when writing to database:
  ```python
  from utils.time_helpers import to_datetime_str

  timestamp_str = to_datetime_str(unix_seconds)  # Always 19 chars
  ```

### 2. Numeric Type Safety

**Problem:** SQLite sometimes returns numeric values as bytes, causing type errors.

**Solution:** Defensive conversion in `get_position_by_id()` and `get_active_positions()`

**Helpers:**
```python
def safe_to_int(value, default=0):
    """Convert bytes/NaN/string to int"""
    if pd.isna(value):
        return default
    if isinstance(value, bytes):
        return int.from_bytes(value, byteorder='little')
    return int(value)

def safe_to_float(value, default=0.0):
    """Convert bytes/NaN/string to float"""
    if pd.isna(value):
        return default
    if isinstance(value, bytes):
        return float(int.from_bytes(value, byteorder='little'))
    return float(value)
```

**Applied To:**
- `rebalance_count` (INTEGER)
- All multipliers: `L_A`, `B_A`, `L_B`, `B_B`
- All rates and prices
- All collateral ratios and liquidation thresholds

### 3. Token Identity

**Rule:** Use contract addresses for ALL logic. Symbols are ONLY for display.

**Why:** Token symbols can be duplicated (e.g., `suiUSDT` vs `USDT` are different tokens with different contracts).

**Correct:**
```python
# Logic: use contracts
token_row = df[df['token_contract'] == token_contract]

# Display: use symbols
st.write(f"Token: {token_symbol}")
```

**Incorrect:**
```python
# ❌ WRONG: Logic using symbols
token_row = df[df['token'] == 'USDT']  # Which USDT?!
```

### 4. Rates as Decimals

**Rule:** All rates stored as decimals (0.05 = 5%). Convert to percentages ONLY at display layer.

**Correct:**
```python
# Storage
entry_lend_rate_1A = 0.0316  # 3.16%

# Display
display_rate = f"{entry_lend_rate_1A * 100:.2f}%"  # "3.16%"
```

**Incorrect:**
```python
# ❌ WRONG: Storing as percentage
entry_lend_rate_1A = 3.16  # Ambiguous! 3.16% or 316%?
```

### 5. Position Multipliers

**Rule:** Multipliers (L_A, B_A, L_B, B_B) are normalized. Scale by deployment_usd for actual USD amounts.

**Example:**
```python
deployment_usd = 10000.00
L_A = 1.5

# Actual lend amount on Protocol A
lend_amount_usd = L_A * deployment_usd  # $15,000
```

**Why:** Allows flexible position sizing without recalculating strategy structure.

---

## Troubleshooting Guide

### Issue: "Token prices must be positive"

**Cause:** Price lookup failing - either missing data or timestamp mismatch.

**Debug:**
```python
# Check if prices exist at timestamp
query = """
SELECT token, protocol, price_usd
FROM rates_snapshot
WHERE timestamp = ?
AND token IN (?, ?, ?)
"""
result = pd.read_sql_query(query, conn, params=(timestamp_str, token1, token2, token3))
print(result)
```

**Solutions:**
1. Verify timestamp format is exactly 19 characters (no microseconds)
2. Check if data exists at that timestamp
3. Run [Scripts/truncate_timestamps.py](Scripts/truncate_timestamps.py) to fix precision issues

### Issue: "live_timestamp cannot be before entry_timestamp"

**Cause:** Trying to view position at a timestamp before it was deployed.

**Expected Behavior:** Position should not appear in the list (filtered out).

**Debug:**
```python
# Check position entry timestamp
print(f"Position entry: {position['entry_timestamp']}")
print(f"Selected timestamp: {timestamp_seconds}")
print(f"Comparison: {position['entry_timestamp']} <= {timestamp_seconds}")
```

**Solution:** Ensure `get_active_positions()` is called with `live_timestamp` parameter.

### Issue: Bytes conversion errors

**Symptom:** `TypeError: can't concat int to bytes` or similar.

**Cause:** SQLite returning numeric fields as bytes instead of proper types.

**Solution:** Ensure `get_position_by_id()` includes defensive conversion for ALL numeric fields.

**Check:**
```python
# In position_service.py, get_position_by_id() should have:
integer_fields = ['rebalance_count']
float_fields = ['deployment_usd', 'L_A', 'B_A', 'L_B', 'B_B', ...]

for field in integer_fields:
    if field in position:
        position[field] = safe_to_int(position[field])

for field in float_fields:
    if field in position:
        position[field] = safe_to_float(position[field])
```

### Issue: Rebalance button disabled unexpectedly

**Cause:** Time-travel paradox prevention - position has future rebalances.

**Expected Behavior:** When viewing historical timestamp, if position was rebalanced AFTER that timestamp, the rebalance button is disabled with explanation.

**Check:**
```python
# Debug time-travel check
has_future = service.has_future_rebalances(position_id, timestamp_seconds)
print(f"Has future rebalances: {has_future}")

# Query manually
query = """
SELECT COUNT(*) as count
FROM position_rebalances
WHERE position_id = ?
AND opening_timestamp > ?
"""
result = pd.read_sql_query(query, conn, params=(position_id, timestamp_str))
print(f"Future rebalances count: {result['count'].iloc[0]}")
```

**Solution:** This is expected behavior when time-traveling. View at latest timestamp to enable rebalancing.

---

## Utility Functions & Helpers

### Time Helpers
**File:** [utils/time_helpers.py](utils/time_helpers.py)

```python
def to_seconds(value) -> int:
    """Convert any timestamp format to Unix seconds (int)"""
    # Handles: str, datetime, pandas.Timestamp, int

def to_datetime_str(seconds: int) -> str:
    """Convert Unix seconds to DB string format: 'YYYY-MM-DD HH:MM:SS'"""
    # Always returns exactly 19 characters
```

**Usage:**
```python
# DB read
timestamp_str = "2026-01-13 10:52:47"
timestamp_int = to_seconds(timestamp_str)  # 1736766767

# DB write
timestamp_int = 1736766767
timestamp_str = to_datetime_str(timestamp_int)  # "2026-01-13 10:52:47"
```

### Dashboard Utils
**File:** [dashboard/dashboard_utils.py](dashboard/dashboard_utils.py)

```python
def get_db_connection():
    """Get SQLite database connection"""
    # Returns connection to data/sui_lending.db

class UnifiedDataLoader:
    """Load and merge protocol data with historical snapshot support"""

    def load_snapshot(self, timestamp: int) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load rates, prices, liquidity at specific timestamp"""
        # Returns: (rates_df, prices_df, liquidity_df)
```

---

## Scripts & Maintenance

### Data Collection
- `data/refresh_pipeline.py`: Fetch fresh rates/prices from protocols
- `data/protocol_merger.py`: Merge data from multiple protocols

### Position Management
- `Scripts/purge_positions.py`: Delete all positions (use with `--force`)
- `Scripts/delete_invalid_position.py`: Delete specific position by ID

### Database Maintenance
- `Scripts/truncate_timestamps.py`: Fix timestamp precision (remove microseconds)
- `Scripts/backfill_*.py`: Backfill missing data from latest values

---

## Future Enhancements

### Short-Term
1. **Real Capital Integration (Phase 2)**
   - Connect to Sui wallet
   - Execute positions on-chain
   - Track actual transactions

2. **Multi-User Support**
   - User authentication
   - Per-user position tracking
   - Portfolio aggregation

### Long-Term
1. **Advanced Rebalancing**
   - Auto-rebalance based on triggers (APR drop, liquidation risk)
   - Rebalance optimizer (minimize fees)

2. **Risk Management**
   - Real-time liquidation alerts
   - Position health scoring
   - Max drawdown limits

3. **Analytics**
   - Strategy performance comparison
   - Historical backtesting
   - Protocol comparison metrics

---

## Key Takeaways

1. **Timestamp is Sacred:** The selected timestamp represents "now" for ALL operations. Never use `datetime.now()` except when collecting fresh data.

2. **Event Sourcing:** `positions` table = current state (mutable). `position_rebalances` table = historical segments (immutable). Time-travel queries the rebalances table.

3. **Contract Addresses:** Use contracts for ALL logic. Symbols are ONLY for display.

4. **Defensive Programming:** Always convert numeric fields when reading from database (bytes issue). Always validate timestamps are exactly 19 characters.

5. **Forward-Looking Calculation:** Position value is calculated by summing earnings/costs over all time periods from entry to live timestamp. Each timestamp's rates apply to the NEXT period.

---

## Contact & Support

For questions or issues:
- Review [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) for core principles
- Review [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design
- Check database schema: [data/schema.sql](data/schema.sql)

**Critical Files Reference:**
- Dashboard: [dashboard/dashboard_renderer.py](dashboard/dashboard_renderer.py)
- Position Service: [analysis/position_service.py](analysis/position_service.py)
- Position Calculator: [analysis/position_calculator.py](analysis/position_calculator.py)
- Rate Analyzer: [analysis/rate_analyzer.py](analysis/rate_analyzer.py)
- Time Helpers: [utils/time_helpers.py](utils/time_helpers.py)
