# Sui Lending Bot - Design Notes

## Meta-Rule: Claude and Design Notes

**CRITICAL:** Claude (AI assistant) should NEVER suggest entries for DESIGN_NOTES.md. This document is maintained exclusively by the developer. Claude can READ and FOLLOW these principles, but must never propose additions or modifications.

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

The positions table stores immutable entry state. Position performance is calculated on-the-fly from the rates_snapshot table. Never mutate historical records.

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

### 7. Rate and Number Representation

**Core Principle:** All rates, APRs, fees, and numeric values are stored and calculated as decimals (0.0 to 1.0 scale). Only convert to percentages at the display layer.

**Storage format:**
- **Database:** Decimals (e.g., 0.05 = 5%, 0.0025 = 0.25%)
- **Calculations:** All arithmetic uses decimals (e.g., `rate * amount`)
- **Internal variables:** Decimals throughout Python code

**Display format:**
- **UI/Dashboard:** Convert to percentages when displaying (e.g., `f"{rate * 100:.2f}%"`)
- **User input:** Convert from percentage to decimal when receiving input

**Why:**
- **Consistency:** Eliminates "is this 5 or 0.05?" confusion
- **Math correctness:** Prevents 100x errors in calculations
- **Database compatibility:** Standard financial representation
- **Clear boundary:** Conversion only at display layer

**Example:**
```python
# CORRECT: Store as decimal
entry_net_apr = 0.05  # 5%
display = f"{entry_net_apr * 100:.2f}%"  # "5.00%"

# WRONG: Store as percentage
entry_net_apr = 5.0  # Ambiguous!
display = f"{entry_net_apr}%"  # Could be "5%" or "500%"
```

**Conversion boundaries:**
- **Strategy calculation → Database:** Values are already decimals, store as-is
- **Database → Display:** Multiply by 100 and add "%" symbol
- **User input → Database:** Divide by 100 to convert percentage to decimal

### 8. No sys.path Manipulation

**Rule:** NEVER use `sys.path.append()`, `sys.path.insert()`, or any other sys.path manipulation in the codebase.

**Forbidden pattern:**
```python
# ❌ NEVER DO THIS
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**Why this is bad:**
- Non-standard Python practice
- Breaks IDE tooling and autocomplete
- Makes imports fragile and order-dependent
- Difficult to debug when things go wrong
- Prevents proper package installation

**Correct approach:**
- Install the project as an editable package: `pip install -e .`
- Use proper package structure with `pyproject.toml`
- All imports will work without sys.path manipulation
- Standard Python best practice

**Current state:**
- We have 11 files that still use this anti-pattern (see plan to refactor)
- DO NOT add new instances
- We are working to eliminate all existing instances

### 9. Token Identity: Contract Addresses, Not Symbols

**Core Principle:** All token comparison, matching, filtering, and logic operations MUST use contract addresses. Token symbols are ONLY for display at the UI boundary.

**Why:**
- **Uniqueness:** Contract addresses are globally unique; symbols can be duplicated (e.g., suiUSDT vs USDT are different tokens)
- **Correctness:** Prevents bugs where similar symbols represent different tokens
- **Precision:** Eliminates ambiguity in cross-protocol token matching

**Token symbol usage (CORRECT):**
- ✅ Display in dashboard tables and charts
- ✅ User-facing messages and alerts
- ✅ Logging and debugging output
- ✅ Iterator variables in loops (when contract is retrieved separately)

**Token symbol usage (FORBIDDEN):**
- ❌ DataFrame filtering: `df[df['Token'] == 'USDT']` (use `df[df['Contract'] == '0x...']`)
- ❌ Token equality comparisons for logic: `if token1_symbol == token2_symbol`
- ❌ Merging/joining DataFrames on symbol columns
- ❌ Database queries for rate lookups by symbol
- ❌ Stablecoin filtering by symbol (use contract set instead)

**Architecture layers:**
```
┌──────────────────────┐
│   Protocol APIs      │ Return: symbol + contract
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  protocol_merger.py  │ Matches on: contract (normalized)
│                      │ Stores: both symbol + contract
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  rate_analyzer.py    │ Iterates on: symbols (convenience)
│                      │ Stores results: contract addresses
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Database (rates)    │ Stores: both token + token_contract
│                      │ Queries: by token_contract
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Dashboard/UI        │ Displays: symbols
│                      │ Logic: uses contract from results
└──────────────────────┘
```

**Correct patterns:**
```python
# ✅ CORRECT: Match by contract
token_row = df[df['Contract'] == token_contract]
stablecoin_contracts = {normalize_coin_type(c) for c in STABLECOIN_CONTRACTS}
if contract in stablecoin_contracts:
    # ...

# ✅ CORRECT: Store both, use contract for logic
lend_row = {
    'Token': symbol,           # For display
    'Contract': contract,      # For logic
    'Supply_apr': rate
}

# ❌ WRONG: Match by symbol
token_row = df[df['Token'] == 'USDT']  # Which USDT?!

# ❌ WRONG: Compare symbols for logic
if token1 == token2:  # Are these symbols or contracts?
    skip_strategy()
```

**Contract normalization:**
- Always use `normalize_coin_type()` when comparing contracts
- Removes leading zeros: `0x00002::sui::SUI` → `0x2::sui::SUI`
- Located in: `data/protocol_merger.py`

**Verification status (as of 2026-01-20):**
- ✅ protocol_merger.py: All logic uses contracts
- ✅ rate_tracker.py: All DataFrame lookups use contracts
- ✅ dashboard_utils.py: Historical queries use contracts
- ✅ rate_analyzer.py: Uses symbols as iterators, stores contracts in results
- ✅ dashboard_renderer.py: Symbol filtering only at UI layer (acceptable)
- ✅ No critical bugs found where symbols are used for logic incorrectly

### 10. Collateral Ratio and Liquidation Threshold Pairing

**Core Principle:** Wherever collateral_ratio parameters are used, liquidation_threshold parameters MUST also be present.

**Why:**
- **Risk Management:** Both values define the safety boundaries of lending positions
- **Completeness:** Collateral ratio without liquidation threshold is incomplete information
- **Database Integrity:** Schema enforces storing both together

**Enforcement:**
- ✅ Function signatures require both as parameters
- ✅ Database tables have both columns
- ✅ Protocol readers fetch both together
- ✅ Type hints cause IDE warnings if missing

**Relationship:**
- `collateral_ratio` (Max LTV): Maximum you can borrow (e.g., 0.70 = 70%)
- `liquidation_threshold` (Liquidation LTV): Point at which liquidation occurs (e.g., 0.75 = 75%)
- **Always: liquidation_threshold > collateral_ratio** (liquidation happens at higher LTV to provide safety buffer)

**Correct patterns:**
```python
# ✅ CORRECT: Both parameters together, with correct relationship
def analyze_strategy(
    collateral_ratio_token1_A: float,          # e.g., 0.70 (70% max borrow)
    collateral_ratio_token2_B: float,          # e.g., 0.30 (30% max borrow)
    liquidation_threshold_token1_A: float,     # e.g., 0.75 (75% liquidation) > 0.70
    liquidation_threshold_token2_B: float,     # e.g., 0.35 (35% liquidation) > 0.30
    ...
)

# ❌ WRONG: Only collateral ratio
def analyze_strategy(
    collateral_ratio_token1_A: float,
    collateral_ratio_token2_B: float,
    ...
)
```

**Architecture layers:**
```
┌──────────────────────┐
│   Protocol APIs      │ Return: both collateral_ratio + liquidation_threshold
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  protocol_merger.py  │ Stores: both values together
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  rate_analyzer.py    │ Retrieves: both values together
│                      │ Passes: both to calculator
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Database (rates)    │ Stores: both collateral_ratio + liquidation_threshold
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  position_calculator │ Uses: collateral_ratio for calculations
│                      │ Stores: both in result dictionary
└──────────────────────┘
```

**Verification status (as of 2026-01-29):**
- ✅ NaviReader: Fetches both together
- ✅ PebbleReader: Fetches both together
- ✅ RateTracker: Stores both in rates_snapshot table
- ✅ RateAnalyzer: Retrieves and passes both to calculator
- ✅ PositionCalculator: Requires both as parameters
- ✅ PositionService: Stores both in positions table
- ✅ All function signatures enforce pairing through type hints

### 11. Dashboard as Pure View Layer

**Core Principle:** Dashboard files should contain NO calculations. All metrics must be pre-calculated and stored in the database.

**Why:**
- **Performance:** Dashboard loads instantly without expensive calculations
- **Consistency:** Single source of truth (database), no discrepancies between views
- **Auditability:** All values are stored and can be inspected/debugged
- **Separation of concerns:** Data collection (refresh_pipeline) vs. data display (dashboard)

**Architecture:**
```
┌──────────────────────┐
│  refresh_pipeline.py │  Calculate once per hour
│  (data collection)   │  - Fetch protocol data
│                      │  - Run rate analysis
│                      │  - Calculate position statistics ← ALL CALCULATIONS HERE
│                      │  - Store in database
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│      Database        │  Single source of truth
│  position_statistics │  - All pre-calculated metrics
│  rates_snapshot      │  - Historical rate data
│  positions           │  - Position details
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  dashboard_renderer  │  Pure view layer
│  (display only)      │  - Read from database
│                      │  - Format for display
│                      │  - NO calculations
└──────────────────────┘
```

**What belongs in dashboard:**
- ✅ Database queries (read-only)
- ✅ Formatting (percentages, currency, colors)
- ✅ UI layout and organization
- ✅ Simple aggregations (sum, average) for display groups
- ✅ Filters and sorting

**What does NOT belong in dashboard:**
- ❌ Position PnL calculations
- ❌ Earnings breakdowns (base/reward)
- ❌ APR calculations
- ❌ Fee calculations
- ❌ Rate interpolations or estimations
- ❌ Complex business logic

**Verification status (as of 2026-02-04):**
- ✅ position_statistics table: All metrics pre-calculated
- ✅ Portfolio Summary: Aggregates stored values
- ✅ Strategy Summary: Displays stored values
- ⚠️ Rebalance details: Still calculating some metrics (to be moved to database)

**Exception:** Formatting calculations like `(value / deployment * 100)` for percentage display are acceptable since they're view-layer transformations, not business logic.

### 12. PnL Calculation: Token Amounts × Price, Not Deployment × Weight

**Core Principle:** All PnL and earnings calculations MUST use actual token amounts multiplied by current prices. NEVER use `deployment_usd × weight` as this ignores price drift between rebalances.

**Why:**
- **Accuracy:** Token quantities are constant between rebalances, but prices change continuously
- **Price drift:** Using weights assumes constant prices, which is incorrect for volatile assets
- **Real value:** `token_amount × current_price` reflects actual position value

**The Problem (Old Approach):**
```python
# ❌ WRONG: Using deployment × weight (ignores price changes)
leg_value = deployment_usd * weight  # e.g., $10,000 × 0.35 = $3,500
earnings = leg_value * rate * time
```

If the token price increases 10% between rebalances, this calculation is off by 10% because it uses the original deployment value, not the current token value.

**The Solution (Current Approach):**
```python
# ✅ CORRECT: Using token amount × current price
token_amount = position['entry_token_amount_2b']  # e.g., 1000 tokens
current_price = get_price_usd_at_timestamp(token, protocol, timestamp)  # e.g., $3.65
leg_value = token_amount * current_price  # 1000 × $3.65 = $3,650
earnings = leg_value * rate * time
```

**Implementation locations:**
- **position_service.py:** `calculate_leg_earnings_split()` - Line 1002-1133
  - Fetches `price_usd` from rates_snapshot for each timestamp
  - Calculates `usd_value = token_amount * price_usd` (Line 1121)
  - Uses `_get_token_amount_for_leg()` helper to extract token amounts (Line 993-1000)

- **position_statistics_calculator.py:** Lines 79-103, 164-177
  - For live segments: Uses `exit_token_amount_*` from last rebalance or position's `entry_token_amount_*`
  - For rebalanced segments: Uses `entry_token_amount_*` from rebalance records
  - Passes correct token amounts to `calculate_leg_earnings_split()`

**Token amount sources:**
- **Position entry:** `entry_token_amount_1a/2a/2b/3b` in positions table (stored at creation)
- **After rebalance:** `exit_token_amount_1a/2a/2b/3b` in position_rebalances table
- **Rebalanced segment:** `entry_token_amount_1a/2a/2b/3b` in position_rebalances table

**Token amount calculation at position creation:**
```python
# Formula: entry_token_amount = deployment_usd × weight / entry_price
entry_token_amount_1a = (l_a * deployment_usd) / entry_price_1a if entry_price_1a > 0 else 0
entry_token_amount_2a = (b_a * deployment_usd) / entry_price_2a if entry_price_2a > 0 else 0
entry_token_amount_2b = (l_b * deployment_usd) / entry_price_2b if entry_price_2b > 0 else 0
entry_token_amount_3b = (b_b * deployment_usd) / entry_price_3b if b_b and entry_price_3b > 0 else None

# Example:
# deployment_usd = $10,000, l_a = 0.35, entry_price_1a = $3.50
# entry_token_amount_1a = 0.35 × $10,000 / $3.50 = 1,000 tokens
```

**Backfill script for existing positions:**
- `Scripts/backfill_position_token_amounts.py` - Populates entry_token_amount columns for positions created before this feature
- Run from project root: `python -m Scripts.backfill_position_token_amounts`

**Critical implementation dates:**
- Token amount storage in positions table: February 11, 2026
- PnL calculations using token amounts: February 9, 2026

**Architecture:**
```
┌──────────────────────┐
│  Position Entry      │ Stores: token amounts at entry
│  (positions table)   │ - entry_token_amount_1a/2a/2b/3b
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Live Segment        │ Uses: token amounts from entry or last rebalance exit
│  Calculation         │ Fetches: price_usd at each timestamp
│                      │ Calculates: token_amount × price_usd × rate × time
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Rebalance           │ Stores: entry + exit token amounts for segment
│  (rebalances table)  │ - entry_token_amount_* (start of segment)
│                      │ - exit_token_amount_* (end of segment)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Next Segment        │ Uses: exit_token_amount_* from previous rebalance
│  Calculation         │ Continues with updated token quantities
└──────────────────────┘
```

**Verification status (as of 2026-02-09):**
- ✅ position_service.py: Uses token_amount × price_usd
- ✅ position_statistics_calculator.py: Passes correct token amounts for all segments
- ✅ Database schema: Stores token amounts in positions and position_rebalances tables
- ✅ Tested: PnL calculations now match manual verification

### 13. Explicit Error Handling: Fail Loudly, Then Continue

**Core Principle:** Never use lazy column checking that silently skips missing columns. Explicitly try to access columns, catch errors, show debugging info, then continue without the column.

### 14. Iterative Liquidity Updates in Portfolio Allocation

**Core Principle:** When allocating capital to strategies in the portfolio allocator, update available borrow liquidity after each allocation and recalculate constraints for remaining strategies. This prevents over-borrowing beyond actual available liquidity.

**Why:**
- **Realism:** Allocating to one strategy reduces available liquidity for subsequent strategies
- **Risk management:** Prevents portfolios that exceed protocol liquidity constraints
- **Correctness:** Ensures max_size accurately reflects remaining available capital

**Implementation (as of February 2026):**

1. **Token×Protocol Matrix:** Available borrow tracked in DataFrame with tokens as rows, protocols as columns
2. **Iterative Updates:** After each allocation:
   - Reduce `available_borrow[token2][protocol_a]` by `allocation * b_a`
   - Reduce `available_borrow[token3][protocol_b]` by `allocation * b_b`
3. **Recalculate max_size:** For all remaining strategies, update `max_size = min(available_borrow_2A / b_a, available_borrow_3B / b_b)`

**Architecture:**
```python
# In select_portfolio():

# 1. Initialize matrix before greedy loop
available_borrow = _prepare_available_borrow_matrix(strategies)

# 2. After each allocation
for strategy in strategies:
    allocate(strategy, amount)

    # Update liquidity
    _update_available_borrow(strategy, amount, available_borrow)

    # Recalculate max_size for remaining strategies
    _recalculate_max_sizes(remaining_strategies, available_borrow)
```

**Feature Flag:**
- `DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES` in settings.py (default: True)
- DEBUG ONLY: This flag exists for testing/comparison purposes only
- Once validated, this flag will be removed and iterative updates will be always-on
- Backwards compatible: can be disabled via parameter to select_portfolio()

**Extension Point:** The `_apply_market_impact_adjustments()` pattern allows adding:
- Interest rate curve updates (utilization → rate changes)
- Collateral ratio adjustments
- Other market impact modeling

**Implementation Date:** February 10, 2026

**Note on terminology:** "IRM effects" (effects as noun = impacts/consequences) vs "the IRM affects rates" (affects as verb = influences)

**Why:**
- **Visibility:** Errors are immediately visible in logs, not hidden by defensive code
- **Debuggability:** Shows exactly what columns are available when a mismatch occurs
- **Robustness:** System continues operating despite column naming issues
- **Fast debugging:** Developer sees the problem and available options immediately

**The Problem (Lazy Pattern):**
```python
# ❌ WRONG: Silently skips if column doesn't exist
if 'max_size' in df.columns:
    display_df['max_size'] = df['max_size']
# If column name is wrong, you'll never know!
```

**The Solution (Explicit Pattern):**
```python
# ✅ CORRECT: Fail loudly with debugging info, then continue
try:
    display_df['max_size'] = df['max_size']
except KeyError as e:
    # Log the error with available columns for debugging
    print(f"⚠️  KeyError accessing 'max_size': {e}")
    print(f"    Available columns: {list(df.columns)}")
    # Continue without this column - don't crash the entire render
```

**Pattern requirements:**
1. **Explicit access:** Try to access the column directly (no `if col in df` checks)
2. **Catch KeyError:** Use try/except to catch column access errors
3. **Debug output:** Print/log the error AND list available columns
4. **Continue execution:** Don't raise/re-raise - let the render complete without that column

**Where to apply:**
- ✅ DataFrame column access for optional display columns
- ✅ Dictionary key access for optional fields
- ✅ Series/row indexing for optional values
- ❌ NOT for required fields (those should raise and stop)

**Example - Dashboard column display:**
```python
# Building column list for display
base_columns = ['token1', 'token2', 'protocol_a', 'net_apr']

# Try to add optional max_size column
try:
    if 'max_size' in strategies.columns:
        base_columns.append('max_size')
except Exception as e:
    print(f"⚠️  Error checking for 'max_size' column: {e}")
    print(f"    Available columns: {list(strategies.columns)}")

# Try to format the column
display_df = strategies[base_columns].copy()
try:
    display_df['max_size'] = display_df['max_size'].apply(
        lambda x: f"${x:,.0f}" if pd.notna(x) else "N/A"
    )
except KeyError as e:
    print(f"⚠️  KeyError formatting 'max_size': {e}")
    print(f"    Available columns in display_df: {list(display_df.columns)}")
    # Continue - table will render without this column
```

**Example - Portfolio allocator:**
```python
# Check strategy max size constraint
try:
    strategy_max = strategy_row['max_size']
    if pd.notna(strategy_max) and strategy_max < max_amount:
        max_amount = strategy_max
        constraint_info['limiting_constraint'] = 'strategy_max_size'
except KeyError as e:
    print(f"⚠️  KeyError accessing 'max_size' in strategy_row: {e}")
    print(f"    Available columns: {list(strategy_row.index)}")
    # Continue without max_size constraint
```

**Effect:**
- Developer sees the error immediately in console/logs
- Available columns are shown for quick diagnosis
- System continues operating (graceful degradation)
- No silent failures or hidden bugs

**Implementation date:** February 10, 2026

**Verification status:**
- ✅ dashboard_renderer.py: Strategy table column handling (lines 3754-3786)
- ✅ dashboard_renderer.py: Portfolio preview column handling (lines 4027-4071)
- ✅ portfolio_allocator.py: Strategy max_size constraint (lines 159-169)

### 15. No Fallback Values: Fail Loudly, Debug Quickly

**Core Principle:** NEVER fall back to random/guessed/wrong/alternative variables when the primary variable fails or is missing. Fail loudly and provide proper debug info. Silent fallbacks hide bugs instead of exposing data problems.

**Why:**
- **Bug visibility:** Fallbacks mask the root cause instead of exposing it
- **Data integrity:** Wrong fallback values produce incorrect results that appear correct
- **Fast debugging:** Seeing "N/A" or an error immediately shows where data is missing
- **Trust:** Users can trust displayed values are correct, not approximations

**The Problem (Silent Fallback):**
```python
# ❌ WRONG: Silently use wrong value if correct value is missing
price_for_entry_calc = segment_entry_price if safe_value(segment_entry_price) else entry_price

if safe_value(price_for_entry_calc) and live_liq_price > 0:
    entry_liq_dist_pct = (live_liq_price - price_for_entry_calc) / price_for_entry_calc
    entry_liq_dist_str = f"{entry_liq_dist_pct * 100:+.1f}%"
# If segment_entry_price is missing, uses entry_price instead
# Result: Shows "28.4%" when correct value is "25%" - SILENTLY WRONG!
```

**The Solution (Fail Loudly):**
```python
# ✅ CORRECT: Use only the correct value, fail loudly if missing
if safe_value(segment_entry_price) and live_liq_price > 0 and live_liq_price != float('inf'):
    entry_liq_dist_pct = (live_liq_price - segment_entry_price) / segment_entry_price
    entry_liq_dist_str = f"{entry_liq_dist_pct * 100:+.1f}%"
else:
    entry_liq_dist_str = "N/A"
# If segment_entry_price is missing, shows "N/A" - LOUDLY EXPOSES THE PROBLEM!
```

**Real Example (Bug Found February 11, 2026):**

Position with AlphaFi/LBTC/Borrow leg:
- Entry price (position start): 70562.4637
- Segment entry price (after rebalance): Different value
- Liquidation price: 88228.9698

**With fallback (WRONG):**
```python
# Used entry_price (70562) instead of segment_entry_price
# Result: 28.4% liquidation distance (INCORRECT)
```

**Without fallback (CORRECT):**
```python
# Used segment_entry_price
# Result: 25.0% liquidation distance (CORRECT)
# Or shows "N/A" if segment_entry_price is missing (exposes data problem)
```

**Common fallback anti-patterns to avoid:**
```python
# ❌ WRONG: Fallback to default value
value = correct_value if correct_value else 0.0

# ❌ WRONG: Fallback to related but different value
price = segment_price if segment_price else position_price

# ❌ WRONG: Fallback to calculated approximation
token_amount = stored_amount if stored_amount else (deployment * weight / price)

# ❌ WRONG: Fallback to previous value
current_ltv = live_ltv if live_ltv else entry_ltv

# ✅ CORRECT: Use only the correct value, show N/A if missing
display_value = f"{correct_value:.2f}" if safe_value(correct_value) else "N/A"
```

**When fallbacks ARE acceptable:**
- Default configuration values (e.g., `settings.get('TIMEOUT', 30)`)
- User preference settings with sensible defaults
- UI display preferences (e.g., theme, page size)
- Never for calculations, metrics, or financial values

**Pattern requirements:**
1. **Single source:** Use only the correct variable for calculations
2. **Explicit checks:** Verify the variable is valid before using it
3. **Visible failures:** Display "N/A", "-", or error message when data is missing
4. **Debug info:** Log what was missing and why (for developers)
5. **No approximations:** Don't calculate fallback values from other fields

**Effect:**
- Calculations are either correct or visibly failed (no middle ground)
- Missing data is immediately obvious to users and developers
- Root cause problems get fixed instead of masked
- Users can trust that displayed values are accurate

**Implementation locations:**
- **position_renderers.py (Lines 682-685, 845-848):** Segment entry liquidation distance
  - Removed fallback to `entry_price`
  - Now shows "N/A" if `segment_entry_price` is missing
  - Fixed bug where fallback caused 28.4% instead of 25% for LBTC position

**Implementation date:** February 11, 2026

**Verification status:**
- ✅ position_renderers.py: Removed entry_price fallback for segment calculations
- ⚠️ Codebase audit needed: Check for other inappropriate fallback patterns

### 16. Never Use .get() with Defaults Without Permission

**Core Principle:** NEVER use `.get(key, default)` on dictionaries or DataFrames without explicit permission. Always use direct key access `dict[key]` to fail loudly with KeyError when fields are missing.

**Why:**
- **Hidden bugs:** `.get()` with defaults masks missing data instead of exposing it
- **Silent failures:** Code appears to work but produces incorrect results
- **Data integrity:** Default values (especially 0.0) hide data quality problems
- **False confidence:** Users see numbers that look correct but are wrong

**The Problem (Silent Defaults):**
```python
# ❌ WRONG: Hides missing fields with silent defaults
upfront_fees_pct = (
    strategy.get('b_a', 0.0) * strategy.get('borrow_fee_2a', 0.0) +
    strategy.get('b_b', 0.0) * strategy.get('borrow_fee_3b', 0.0)
)
# Result: If borrow_fee_2a is missing, returns 0.0 instead of failing
# Calculation appears successful but is WRONG
```

**The Solution (Fail Loud):**
```python
# ✅ CORRECT: Fails immediately with KeyError if fields are missing
upfront_fees_pct = (
    strategy['b_a'] * strategy['borrow_fee_2a'] +
    strategy['b_b'] * strategy['borrow_fee_3b']
)
# Result: If borrow_fee_2a is missing, raises KeyError immediately
# Error message shows exactly what's missing: "KeyError: 'borrow_fee_2a'"
```

**Real Examples (Fixed February 16, 2026):**

**Dashboard modal calculations (dashboard_renderer.py lines 599-601):**
- Before: `strategy.get('b_a', 0.0)` - silently defaulted to 0.0
- After: `strategy['b_a']` - fails with KeyError if missing

**Position multipliers (dashboard_renderer.py lines 525-534):**
- Before: `strategy.get('l_a', 0.0)` - silently defaulted to 0.0
- After: `strategy['l_a']` - fails with KeyError if missing

**Position details table (dashboard_renderer.py lines 744-830):**
- Before: `strategy.get('liquidation_threshold_1a', 0.0)` - silently defaulted to 0.0
- After: `strategy['liquidation_threshold_1a']` - fails with KeyError if missing

**When .get() IS acceptable (with explicit permission):**
- Optional UI features that can be omitted without affecting correctness
- User preferences with documented defaults
- Backwards compatibility with explicit comment explaining why
- Must get explicit approval before adding any `.get()` with default

**Pattern requirements:**
1. **Direct access:** Always use `dict[key]` not `dict.get(key, default)`
2. **Required fields:** All calculator output fields are required - no defaults
3. **Fail fast:** Let KeyError propagate immediately
4. **Clear errors:** Error message shows exactly which field is missing
5. **Permission required:** If you think you need a default, ask first

**Common anti-patterns to avoid:**
```python
# ❌ WRONG: Silent defaults everywhere
l_a = strategy.get('l_a', 0.0)
b_a = strategy.get('b_a', 0.0)
price = strategy.get('P1_A', 1.0)
fee = strategy.get('borrow_fee_2a', 0.0)

# ✅ CORRECT: Direct access, fail loud
l_a = strategy['l_a']
b_a = strategy['b_a']
price = strategy['P1_A']
fee = strategy['borrow_fee_2a']
```

**Effect:**
- Missing fields cause immediate, obvious failures
- Error messages pinpoint exactly what's wrong
- Data quality problems get fixed instead of hidden
- Calculations are trustworthy - never based on guessed defaults

**Fixed locations (February 16, 2026):**
- ✅ dashboard_renderer.py: Upfront fees calculation (line 599-601)
- ✅ dashboard_renderer.py: Position calculations (lines 525-534)
- ✅ dashboard_renderer.py: Token amounts and sizes (lines 668-684)
- ✅ dashboard_renderer.py: Position details table (lines 744-830)
- ✅ dashboard_renderer.py: Liquidation calculations (lines 701-736)
- ✅ dashboard_renderer.py: APR summary table (lines 613-617)

**Verification status:**
- ✅ All critical dashboard display code uses direct key access
- ✅ All strategy dict fields are required (no defaults in calculators)
- ⚠️ Remaining `.get()` calls in non-critical display code to be audited
