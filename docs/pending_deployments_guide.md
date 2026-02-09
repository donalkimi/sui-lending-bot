# Pending Deployments Tab - Technical Guide

## Overview

The Pending Deployments tab is a workflow tool that bridges paper trading (Phase 1) and real capital deployment (Phase 2). It provides step-by-step execution instructions for positions that have been created in the system but not yet executed on-chain.

**System Deployment**: Production system deployed on Railway with Supabase PostgreSQL database. Dashboard accessible 24/7 for position management.

## Purpose

When a user identifies a profitable lending strategy and clicks "Deploy" in the dashboard, the system:
1. Creates a position record in the database with all entry parameters captured
2. Sets the position's `execution_time` to -1 (pending status)
3. The position appears in **both** the Pending Deployments tab (with instructions) and the Positions tab (for tracking)

The user then manually executes the 4 on-chain transactions following the displayed instructions, and marks the position as "executed" when complete.

---

## System Architecture

### High-Level Flow

```
User Selects Strategy → Deploy Button → Position Created (execution_time = -1)
                                              ↓
                                    ┌─────────┴─────────┐
                                    ↓                   ↓
                        Pending Deployments Tab    Positions Tab
                        (execution instructions)   (performance tracking)
                                    ↓
                        User Executes On-Chain Transactions
                                    ↓
                        Mark as Executed Button
                                    ↓
                        execution_time = current Unix timestamp
                                    ↓
                        Position removed from Pending Deployments
                        (still visible in Positions tab)
```

---

## How Deployments Are Calculated

### The 4-Leg Recursive Lending Strategy

Every deployed position is a **recursive lending arbitrage** strategy that exploits rate differentials between two lending protocols. The strategy involves 4 legs (2 lends, 2 borrows) that create a leveraged position.

#### Strategy Components

**Tokens:**
- `token1`: Starting stablecoin (e.g., USDC, USDY) - your initial capital
- `token2`: High-yield token being arbitraged (e.g., DEEP, WAL)
- `token3`: Closing stablecoin (e.g., USDC, USDY) - completes the loop

**Protocols:**
- `protocol_a`: First protocol (e.g., Navi, Scallop)
- `protocol_b`: Second protocol (e.g., Pebble, Suilend)

#### The 4 Legs

```
Leg 1: Lend token1 to Protocol A
  └─> Collateral that allows you to...

Leg 2: Borrow token2 from Protocol A
  └─> Token2 that you then...

Leg 3: Lend token2 to Protocol B
  └─> Collateral that allows you to...

Leg 4: Borrow token3 from Protocol B
  └─> Completes the arbitrage loop
```

**Example:**
```
Starting Capital: $1,000 USDC

Leg 1: Lend $1,513 USDC to Scallop (1.513x multiplier)
  → Earn: 8% APR lending rate

Leg 2: Borrow $2,000 worth of WAL from Scallop (2.0x multiplier)
  → Cost: 15% APR borrow rate + 0.30% upfront fee

Leg 3: Lend $2,000 worth of WAL to Pebble (2.0x multiplier)
  → Earn: 22% APR lending rate

Leg 4: Borrow $513 USDC from Pebble (0.513x multiplier)
  → Cost: 5% APR borrow rate + 0.10% upfront fee

Net APR: (8% + 22%) - (15% + 5%) - fees = ~10% net after fees
```

### Position Multipliers

Each leg has a **multiplier** that determines how much to lend/borrow relative to your deployment amount:

- `L_A` (l_a): Lend multiplier at Protocol A
- `B_A` (b_a): Borrow multiplier at Protocol A
- `L_B` (l_b): Lend multiplier at Protocol B
- `B_B` (b_b): Borrow multiplier at Protocol B

**Calculation:**
```python
# USD amounts per leg
lend_1a_usd = l_a × deployment_usd
borrow_2a_usd = b_a × deployment_usd
lend_2b_usd = l_b × deployment_usd
borrow_3b_usd = b_b × deployment_usd

# Token amounts (divide by price)
token_amount_1a = lend_1a_usd / price_1a
token_amount_2a = borrow_2a_usd / price_2a
token_amount_2b = lend_2b_usd / price_2b
token_amount_3b = borrow_3b_usd / price_3b
```

### How Multipliers Are Determined

The `PositionCalculator` class (`analysis/position_calculator.py`) computes optimal multipliers based on:

1. **Collateral Ratios**: Maximum loan-to-value (LTV) allowed by each protocol
   - If Protocol A allows 70% LTV, you can borrow up to $0.70 for every $1.00 lent

2. **Liquidation Thresholds**: Safety margins to avoid liquidation
   - Positions are sized to maintain distance from liquidation prices

3. **Borrow Weights**: Risk adjustments that affect effective LTV
   - Some tokens have higher risk weights, reducing borrowing capacity

4. **Available Liquidity**: How much can actually be borrowed
   - Limited by protocol's available borrow capacity

5. **Capital Efficiency**: Maximizing leverage while staying safe
   - Higher multipliers = higher returns but also higher risk

The calculator uses these constraints to determine the maximum safe position size for each leg.

---

## Database Schema

### Core Fields in `positions` Table

```sql
-- Position Identification
position_id TEXT PRIMARY KEY              -- Unique UUID
status TEXT                               -- 'active', 'closed', 'liquidated'
strategy_type TEXT                        -- 'recursive_lending'

-- Execution Tracking (NEW)
execution_time INTEGER DEFAULT -1         -- -1 = pending, Unix timestamp = executed

-- Strategy Definition
token1, token2, token3 TEXT              -- Token symbols
token1_contract, token2_contract, token3_contract TEXT  -- Contract addresses
protocol_A, protocol_B TEXT              -- Protocol names

-- Position Sizing (multipliers)
deployment_usd DECIMAL(20, 10)           -- Capital allocated
L_A, B_A, L_B, B_B DECIMAL(10, 6)       -- Position multipliers (constant)

-- Entry Snapshot (captured at creation time)
entry_timestamp TIMESTAMP                 -- When strategy was identified
entry_lend_rate_1A DECIMAL(10, 6)       -- Rate for Leg 1
entry_borrow_rate_2A DECIMAL(10, 6)     -- Rate for Leg 2
entry_lend_rate_2B DECIMAL(10, 6)       -- Rate for Leg 3
entry_borrow_rate_3B DECIMAL(10, 6)     -- Rate for Leg 4
entry_price_1A, entry_price_2A, entry_price_2B, entry_price_3B  -- Prices
entry_collateral_ratio_1A, entry_collateral_ratio_2B  -- Collateral ratios
entry_liquidation_threshold_1A, entry_liquidation_threshold_2B  -- Liquidation thresholds
entry_net_apr DECIMAL(10, 6)            -- Expected net APR
entry_borrow_fee_2A, entry_borrow_fee_3B  -- Upfront fees
```

### Execution Time Field

The `execution_time` field is the key to the Pending Deployments workflow:

| Value | Meaning | Visible In |
|-------|---------|------------|
| `-1` | Pending execution | Pending Deployments + Positions |
| Unix timestamp (e.g., 1738886400) | Executed at that time | Positions only |

**Design Rationale:**
- Uses integer sentinel value (-1) instead of NULL for explicit pending state
- Follows codebase design constraint: all timestamps are integers
- Differentiates intentional pending from missing data errors
- Allows querying with simple equality check: `WHERE execution_time = -1`

---

## Code Architecture

### Key Components

#### 1. Rate Analysis (`analysis/rate_analyzer.py`)

**Purpose:** Identifies profitable lending strategies by analyzing rate differentials.

**Process:**
1. Loads lending/borrowing rates from database at selected timestamp
2. For each token, considers all possible protocol pairs (A→B)
3. Calls `PositionCalculator` to determine optimal position sizing
4. Calculates net APR accounting for rates, fees, and leverage
5. Returns sorted list of strategies (best APR first)

**Output:** Strategy dictionary with:
```python
{
    'token1': 'USDC',
    'token2': 'DEEP',
    'token3': 'USDY',
    'protocol_a': 'Navi',
    'protocol_b': 'Suilend',
    'l_a': 1.513,  # multipliers
    'b_a': 2.0,
    'l_b': 2.0,
    'b_b': 0.513,
    'net_apr': 0.1185,  # 11.85%
    'lend_rate_1a': 0.08,  # rates
    'borrow_rate_2a': 0.15,
    # ... all other parameters
}
```

#### 2. Position Calculator (`analysis/position_calculator.py`)

**Purpose:** Computes optimal position multipliers given constraints.

**Inputs:**
- Collateral ratios (max LTV)
- Liquidation thresholds
- Borrow weights
- Available liquidity
- Liquidation distance (safety margin)

**Algorithm:**
1. Start with base lending amount (1.0x deployment)
2. Calculate maximum borrow based on collateral ratio
3. Apply borrow weight adjustments
4. Repeat for second protocol
5. Ensure liquidation distance maintained
6. Scale down if liquidity insufficient
7. Return multipliers: (l_a, b_a, l_b, b_b)

**Key Calculation:**
```python
# Simplified version
l_a = 1.0 + liquidation_distance  # Overcollateralize for safety
b_a = l_a × collateral_ratio_a × (1 / borrow_weight_a)
l_b = b_a  # Lend what you borrowed
b_b = l_b × collateral_ratio_b × (1 / borrow_weight_b)
```

#### 3. Position Service (`analysis/position_service.py`)

**Purpose:** CRUD operations for position records.

**Key Methods:**

**`create_position()`**
- Takes strategy dict and deployment amount
- Generates UUID for position
- Captures **immutable entry snapshot** of all parameters
- Sets `execution_time = -1` (pending)
- Inserts into `positions` table
- Returns position_id

**`mark_position_executed(position_id, execution_time=-1)`**
- Updates `execution_time` to current timestamp (or provided value)
- Position disappears from Pending Deployments tab
- Remains in Positions tab for performance tracking

**`delete_position(position_id)`**
- Hard delete from database
- Use for positions that won't be executed

#### 4. Dashboard Renderer (`dashboard/dashboard_renderer.py`)

**Purpose:** UI layer for displaying strategies and positions.

**Key Functions:**

**`render_pending_deployments_tab()`**
```python
def render_pending_deployments_tab():
    # Query pending positions
    query = "SELECT * FROM positions WHERE execution_time = -1 ORDER BY created_at DESC"
    pending_positions = pd.read_sql_query(query, engine)

    # Display count
    st.metric("Pending Positions", len(pending_positions))

    # Render each position with instructions
    for _, position in pending_positions.iterrows():
        render_pending_position_instructions(position, service)
```

**`render_pending_position_instructions(position, service)`**
- Extracts all position parameters from database row
- Calculates USD amounts: `multiplier × deployment_usd`
- Calculates token amounts: `usd_amount / price`
- Computes acceptable ranges (±0.25% price, ±3% rate)
- Displays 4 legs with formatted instructions
- Provides action buttons:
  - ✅ Mark as Executed
  - 🗑️ Delete Position
  - 📋 Copy Instructions (download text file)

**`calculate_acceptable_ranges(expected_price, expected_rate)`**
- Helper function for tolerance calculations
- Defaults: ±0.25% price tolerance, ±3% rate tolerance
- Future: Will accept custom tolerances per position

---

## Data Flow Through System

### Phase 1: Strategy Discovery

```
1. refresh_pipeline.py runs hourly
   └─> Fetches rates from protocols (Navi, Scallop, Pebble, Suilend)
   └─> Stores in rates_snapshot table with timestamp

2. User opens dashboard
   └─> Selects timestamp (default: latest)
   └─> DataLoader loads rates at that timestamp

3. RateAnalyzer.find_best_protocol_pair()
   └─> For each token, tests all protocol pairs
   └─> Calls PositionCalculator for each pair
   └─> Returns sorted strategies (best APR first)

4. Dashboard displays strategies in "All Strategies" tab
   └─> User clicks on a strategy
   └─> Modal opens showing details
```

### Phase 2: Position Deployment

```
5. User enters deployment amount in modal
   └─> Clicks "🚀 Deploy Position" button

6. show_strategy_modal() calls PositionService.create_position()
   └─> Generates position_id (UUID)
   └─> Captures entry snapshot:
       - Rates, prices, collateral ratios at entry_timestamp
       - Multipliers (L_A, B_A, L_B, B_B) - constant for position lifetime
       - APR metrics (net_apr, apr5, apr30, apr90)
   └─> Sets execution_time = -1 (pending)
   └─> Inserts into positions table

7. Success banner displayed
   └─> "View execution instructions in Pending Deployments tab"
```

### Phase 3: Execution (Manual)

```
8. User navigates to Pending Deployments tab
   └─> Query: SELECT * FROM positions WHERE execution_time = -1

9. Position displayed with 4 legs showing:
   Leg 1: Lend X token1 to Protocol A
     - Expected price: $1.000 USD
     - Acceptable price: ≥ $0.9975 USD
     - Expected rate: 8.00%
     - Acceptable rate: ≥ 7.76%

   Leg 2: Borrow Y token2 from Protocol A
     - Expected price: $0.080 USD
     - Acceptable price: ≤ $0.0802 USD
     - Expected rate: 15.00%
     - Acceptable rate: ≤ 15.45%
     - Borrow fee: 0.300% ($6.00)

   [Legs 3 and 4 similarly formatted]

10. User executes 4 on-chain transactions
    └─> Manually connects wallet
    └─> Sends transactions to blockchain
    └─> Waits for confirmations

11. User clicks "✅ Mark as Executed" button
    └─> Calls PositionService.mark_position_executed(position_id)
    └─> Sets execution_time = int(time.time())  # Current Unix timestamp
    └─> Position removed from Pending Deployments tab
```

### Phase 4: Performance Tracking

```
12. Position now visible only in Positions tab
    └─> Query: SELECT * FROM positions WHERE status = 'active'
    └─> Shows current rates, PnL, APR metrics
    └─> Updated daily via position_statistics table

13. refresh_pipeline.py continues calculating metrics
    └─> Uses current rates from rates_snapshot
    └─> Compares to entry rates
    └─> Calculates unrealized PnL
    └─> Stores in position_statistics table
```

---

## Acceptable Ranges Logic

### Purpose

When executing a position on-chain, market conditions may have changed since the position was created. The acceptable ranges tell the user whether it's still safe to execute.

### Tolerances

**Price Tolerance: ±0.25%**
- For lending: Accept prices ≥ 99.75% of expected (protect against price drops)
- For borrowing: Accept prices ≤ 100.25% of expected (protect against price increases)

**Rate Tolerance: ±3%**
- For lending: Accept rates ≥ 97% of expected (protect against rate drops)
- For borrowing: Accept rates ≤ 103% of expected (protect against rate increases)

### Calculation

```python
def calculate_acceptable_ranges(expected_price, expected_rate):
    return {
        'price_low': expected_price × (1 - 0.0025),   # 99.75%
        'price_high': expected_price × (1 + 0.0025),  # 100.25%
        'rate_low': expected_rate × (1 - 0.03),       # 97%
        'rate_high': expected_rate × (1 + 0.03)       # 103%
    }
```

### Display Logic

```
Leg 1 (Lending): "Lend 1513 USDC to Scallop"
  Expected price: $1.000 USD
  Acceptable price: ≥ $0.9975 USD    ← Only show lower bound
  Expected rate: 8.00%
  Acceptable rate: ≥ 7.76%           ← Only show lower bound

Leg 2 (Borrowing): "Borrow 25000 WAL from Scallop"
  Expected price: $0.080 USD
  Acceptable price: ≤ $0.0802 USD    ← Only show upper bound
  Expected rate: 15.00%
  Acceptable rate: ≤ 15.45%          ← Only show upper bound
```

**Rationale:**
- For **lending**: You want prices/rates to stay high (favorable)
- For **borrowing**: You want prices/rates to stay low (favorable)
- Only show the boundary that protects against unfavorable moves

### Future Enhancement

In Phase 2, tolerances will be customizable per position:
1. Add `price_tolerance` and `rate_tolerance` fields to positions table
2. Add tolerance inputs to deployment modal
3. Update `calculate_acceptable_ranges()` to use position-specific values
4. Store tolerances with position for audit trail

---

## Key Design Principles

### 1. Immutable Entry Snapshot

Once a position is created, its **entry parameters never change**:
- Entry rates, prices, collateral ratios captured at `entry_timestamp`
- Multipliers (L_A, B_A, L_B, B_B) remain constant
- This enables accurate performance tracking over time

**Current performance** is calculated by comparing:
- Entry rates/prices (from position record)
- Current rates/prices (from rates_snapshot at latest timestamp)

### 2. Event Sourcing Pattern

The system uses an **event sourcing** approach:
- `positions` table: Immutable position state at creation
- `position_statistics` table: Daily snapshots of performance metrics
- `position_rebalances` table: Historical segments if position rebalanced

This allows:
- Time-travel: View position performance at any historical timestamp
- Audit trail: Full history of position changes preserved
- Accurate analytics: No data overwritten, only appended

### 3. Timestamp as "Current Time"

The dashboard's selected timestamp **is** the "current time":
- All queries use `WHERE timestamp <= selected_timestamp`
- Never use `datetime.now()` except for fresh data collection
- This enables historical analysis and deterministic testing

### 4. Timestamps as Integers

All timestamps are Unix seconds (integers) throughout the codebase:
- `entry_timestamp`: Stored as TIMESTAMP string in DB, converted to int in Python
- `execution_time`: Stored as INTEGER directly in DB
- Conversion happens only at system boundaries (DB/UI)

**Rationale:**
- Type safety: Integers are simple and comparable
- No pandas/datetime confusion
- Easy arithmetic: `seconds2 - seconds1`
- Sentinel values: -1 for pending, 0 for never, etc.

### 5. Contract Addresses, Not Symbols

All token matching uses **contract addresses**, not symbols:
- Prevents ambiguity (multiple tokens with same symbol)
- Ensures correctness in cross-protocol comparisons
- Symbols used only for display

---

## Error Handling

### Common Scenarios

**1. Position Already Executed**
- User clicks "Mark as Executed" twice
- System: Updates execution_time again (idempotent)
- Position already removed from Pending Deployments tab

**2. Missing Rate Data**
- Position created at timestamp with incomplete rate data
- System: Shows warning, displays "N/A" for missing values
- User can still see position but should investigate why data is missing

**3. Price/Rate Outside Acceptable Range**
- Market moved significantly since position created
- System: Displays acceptable ranges, user makes decision
- User can either wait for better conditions or delete position

**4. Position Deleted Accidentally**
- User clicks "Delete" instead of "Mark as Executed"
- System: Hard delete from database (no undo)
- Future: Add confirmation dialog or soft delete with recycle bin

---

## Future Enhancements

### Phase 2: On-Chain Integration

**Auto-Detection:**
- Integrate wallet connection
- Monitor blockchain for transaction confirmations
- Automatically update `execution_time` when all 4 legs confirmed
- Store transaction hashes for each leg

**Per-Leg Status:**
```sql
ALTER TABLE positions ADD COLUMN leg1_tx_hash TEXT;
ALTER TABLE positions ADD COLUMN leg2_tx_hash TEXT;
ALTER TABLE positions ADD COLUMN leg3_tx_hash TEXT;
ALTER TABLE positions ADD COLUMN leg4_tx_hash TEXT;
```

**Status Indicators:**
- 🟡 Pending (0/4 legs)
- 🟡 In Progress (1-3/4 legs)
- 🟢 Complete (4/4 legs, auto-mark as executed)

### Phase 3: Custom Tolerances

**Per-Position Tolerances:**
```sql
ALTER TABLE positions ADD COLUMN price_tolerance DECIMAL(10, 6) DEFAULT 0.0025;
ALTER TABLE positions ADD COLUMN rate_tolerance DECIMAL(10, 6) DEFAULT 0.03;
```

**UI Enhancement:**
- Add tolerance sliders to deployment modal
- Conservative: ±0.1% price, ±1% rate
- Moderate: ±0.25% price, ±3% rate (default)
- Aggressive: ±0.5% price, ±5% rate

### Phase 4: Smart Execution

**Price/Rate Monitoring:**
- Real-time comparison of current vs expected values
- Alert when conditions favorable for execution
- "Execute Now" button enables when all legs within tolerance

**Batch Execution:**
- Select multiple pending positions
- Execute all transactions in single wallet session
- Progress indicator showing leg completion

---

## Appendix: Example Walkthrough

### Scenario: Deploying a $10,000 Position

**Step 1: Strategy Identified**
```
Token Pair: USDC → DEEP → USDY
Protocol Pair: Navi ↔ Suilend
Net APR: 12.85%
Max Size: $50,000 USD
```

**Step 2: User Deploys $10,000**
```
Position Created:
  position_id: a3f7e89c-1234-5678-90ab-cdef12345678
  deployment_usd: 10000
  execution_time: -1 (pending)

Multipliers:
  L_A: 1.45 (lend 1.45x = $14,500 USDC)
  B_A: 1.20 (borrow 1.20x = $12,000 DEEP)
  L_B: 1.20 (lend 1.20x = $12,000 DEEP)
  B_B: 0.75 (borrow 0.75x = $7,500 USDY)
```

**Step 3: Pending Deployments Instructions**
```
Position a3f7e89c | USDC → DEEP → USDY | Navi ↔ Suilend | $10,000

Leg 1: Lend 14,500.00 USDC to Navi
  Expected price: $1.000000 USD
  Acceptable price: ≥ $0.997500 USD
  Expected rate: 7.50%
  Acceptable rate: ≥ 7.28%

Leg 2: Borrow 150,000.00 DEEP from Navi
  Expected price: $0.080000 USD
  Acceptable price: ≤ $0.080200 USD
  Expected rate: 18.00%
  Acceptable rate: ≤ 18.54%
  Borrow fee: 0.250% ($30.00)

Leg 3: Lend 150,000.00 DEEP to Suilend
  Expected price: $0.080000 USD
  Acceptable price: ≥ $0.079800 USD
  Expected rate: 25.00%
  Acceptable rate: ≥ 24.25%

Leg 4: Borrow 7,500.00 USDY from Suilend
  Expected price: $1.000000 USD
  Acceptable price: ≤ $1.002500 USD
  Expected rate: 4.00%
  Acceptable rate: ≤ 4.12%
  Borrow fee: 0.100% ($7.50)
```

**Step 4: User Executes On-Chain**
1. Connects wallet to Navi
2. Lends 14,500 USDC (transaction confirmed)
3. Borrows 150,000 DEEP (transaction confirmed)
4. Connects wallet to Suilend
5. Lends 150,000 DEEP (transaction confirmed)
6. Borrows 7,500 USDY (transaction confirmed)

**Step 5: Mark as Executed**
- User clicks "✅ Mark as Executed"
- `execution_time` updated to 1738886400 (Feb 6, 2026 12:00:00)
- Position removed from Pending Deployments
- Position tracking begins in Positions tab

**Step 6: Performance Tracking**
```
Day 1:
  Deployed: $10,000
  Current Value: $10,003
  PnL: +$3 (+0.03%)
  Daily APR: 10.95%

Day 30:
  Deployed: $10,000
  Current Value: $10,107
  PnL: +$107 (+1.07%)
  Actual APR: 13.02% (vs 12.85% expected)
```

---

## Glossary

**APR (Annual Percentage Rate):** Annualized yield, expressed as decimal (0.1285 = 12.85%)

**Collateral Ratio:** Maximum loan-to-value, e.g., 0.70 = can borrow $0.70 per $1.00 collateral

**Execution Time:** Unix timestamp when position was executed on-chain, or -1 if pending

**Leg:** One of the 4 operations (2 lends, 2 borrows) that comprise a position

**Liquidation Distance:** Safety margin between current LTV and liquidation threshold

**Liquidation Threshold:** LTV at which position gets liquidated, e.g., 0.75 = liquidation at 75% LTV

**Multiplier:** Scaling factor for position sizing, e.g., 1.45 = lend 1.45x deployment amount

**Pending Deployment:** Position created in database but not yet executed on-chain (execution_time = -1)

**Recursive Lending:** Strategy that uses borrowed assets as collateral to borrow more

**Sentinel Value:** Special value indicating a state, e.g., -1 = pending, 0 = never

**Strategy:** A configuration of tokens and protocols with calculated APR and position sizing

**Unix Timestamp:** Seconds since Jan 1, 1970 UTC, used for all time values in codebase
