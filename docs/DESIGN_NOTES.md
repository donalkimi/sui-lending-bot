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
