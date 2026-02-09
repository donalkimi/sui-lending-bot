# Portfolio Allocator - Comprehensive Plan & Implementation Guide

**Version:** 2.0
**Status:** Planning Phase - Architecture Updated
**Last Updated:** February 9, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [Stage 1: Constraint-Based Allocation](#stage-1-constraint-based-allocation)
5. [Portfolio Tab & Management](#portfolio-tab--management)
6. [Stage 2: Cost Calculation](#stage-2-cost-calculation)
7. [Stage 3: Optimization & Reallocation](#stage-3-optimization--reallocation)
8. [Implementation Roadmap](#implementation-roadmap)
9. [Design Decisions](#design-decisions)
10. [Testing Strategy](#testing-strategy)
11. [Migration Plan](#migration-plan)

---

## Overview

### Problem Statement

The Sui Lending Bot currently allows manual position deployment from the "All Strategies" tab. Users must:
- Manually evaluate strategies against their risk preferences
- Manually ensure diversification across tokens and protocols
- Manually monitor positions for rebalancing opportunities
- Have no systematic way to optimize capital allocation
- **Lack portfolio-level organization and tracking**

### Solution: Portfolio Allocator

A portfolio management system that:
1. **Analyzes** yield opportunities from existing strategies that satisfy dashboard settings
2. **Applies** user-defined constraints on portfolio construction
3. **Selects** an optimal portfolio allocation
4. **Deploys** named portfolios containing multiple strategies
5. **Manages** portfolio lifecycle with rebalancing and tracking
6. **(Future)** Calculates costs to switch between portfolio configurations
7. **(Future)** Auto-reallocation based on performance

### Design Philosophy

- **Portfolio-Centric:** Everything is organized by named portfolios, not individual positions
- **Stage 1 (Constraint-Based):** Simple, transparent, user-controlled - focus on constraint enforcement
- **Stage 2 (Cost-Aware):** Add reallocation cost analysis
- **Stage 3 (Optimized):** Upgrade to mathematical optimization with auto-execution

### Key Changes from Original Architecture

**Before (Position-Centric):**
- Individual positions deployed one at a time from "All Strategies" tab
- No grouping or portfolio concept
- Positions Tab shows all positions flatly

**After (Portfolio-Centric):**
- **Named portfolios** containing multiple strategies
- **Allocation Tab** generates optimal portfolio given constraints
- **Deploy portfolio** = deploy all constituent strategies at once
- **Portfolio Tab** (NEW) shows nested structure: Portfolio → Strategies → Rebalances
- **Positions Tab** remains for legacy single-position deployments (will be deprecated)

---

## System Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Dashboard Layer                                   │
│  (dashboard/dashboard_renderer.py)                                      │
│                                                                          │
│  ┌────────────────────────────────┐  ┌────────────────────────────────┐│
│  │  🎯 Allocation Tab (NEW)       │  │  📊 Portfolio Tab (NEW)        ││
│  │  - Portfolio size input        │  │  - List of named portfolios    ││
│  │  - Constraint inputs           │  │  - Expandable nested view:     ││
│  │  - "Generate Portfolio" button │  │    Portfolio → Strategies      ││
│  │  - Portfolio preview           │  │               → Rebalances     ││
│  │  - "Deploy Portfolio" button   │  │  - Portfolio-level metrics     ││
│  │  - Portfolio name input        │  │  - Rebalance portfolios        ││
│  └────────────────────────────────┘  └────────────────────────────────┘│
└──────────────────────┬────────────────────────────┬───────────────────┘
                       │                            │
                       ↓                            ↓
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│     Service Layer                    │  │  PortfolioService (NEW)      │
│  (analysis/portfolio_allocator.py)   │  │  (analysis/portfolio_service)│
│                                      │  │                              │
│  ┌────────────────────────────────┐ │  │  - create_portfolio()        │
│  │  PortfolioAllocator            │ │  │  - deploy_portfolio()        │
│  │  - calculate_apy_confidence()  │ │  │  - get_portfolios()          │
│  │  - calculate_blended_apr()     │ │  │  - rebalance_portfolio()     │
│  │  - select_portfolio()          │ │  │  - calculate_portfolio_pnl() │
│  │  - calculate_exposures()       │ │  │                              │
│  └────────────────────────────────┘ │  └──────────────────────────────┘
└──────────────────────┬───────────────┘
                       │
         ┌─────────────┴──────────────┐
         ↓                            ↓
┌─────────────────┐         ┌──────────────────────────┐
│ RateAnalyzer    │         │ Database                 │
│ (existing)      │         │ - portfolios (NEW)       │
│ - Strategies DF │         │ - portfolio_strategies   │
│                 │         │ - portfolio_rebalances   │
│                 │         │ - rates_snapshot         │
│                 │         │ - positions (legacy)     │
└─────────────────┘         └──────────────────────────┘
```

### Data Flow

#### Portfolio Creation Flow

1. **Allocation Tab - Setup:**
   - User enters portfolio size (e.g., $10,000)
   - User adjusts constraints (token/protocol exposure, max strategies, confidence, APR weights)

2. **Generate Portfolio:**
   - Load strategies from RateAnalyzer (already filtered by dashboard settings)
   - PortfolioAllocator computes confidence scores from historical data
   - Calculate blended APR for each strategy using user weights
   - Greedy algorithm selects strategies respecting constraints
   - Display portfolio preview with summary metrics and strategy list

3. **Deploy Portfolio:**
   - User enters portfolio name (e.g., "Conservative Q1 2026")
   - Click "Deploy Portfolio" button
   - PortfolioService creates portfolio record in database
   - For each strategy in portfolio:
     - Deploy individual position via PositionService
     - Link position to portfolio via portfolio_id
   - Redirect to Portfolio Tab showing new portfolio

#### Portfolio Tracking Flow

1. **Portfolio Tab displays:**
   - List of all portfolios (collapsed rows)
   - Portfolio-level metrics (total value, PnL, weighted APR)

2. **User expands portfolio:**
   - Shows all constituent strategies
   - Each strategy shows current metrics (value, PnL, APR)

3. **User expands strategy:**
   - Shows all rebalance history for that strategy
   - Same detail level as current Positions tab

4. **Rebalance Portfolio:**
   - Calculate aggregate portfolio drift
   - Rebalance individual strategies as needed
   - Record portfolio-level rebalance event

---

## Database Schema

### New Tables

#### 1. `portfolios` Table

**Purpose:** Store portfolio-level information

```sql
CREATE TABLE portfolios (
    portfolio_id TEXT PRIMARY KEY,           -- UUID
    portfolio_name TEXT NOT NULL,            -- User-defined name (e.g., "Conservative Q1 2026")
    status TEXT NOT NULL,                    -- 'active', 'closed', 'rebalancing'

    -- Creation info
    entry_timestamp TIMESTAMP NOT NULL,      -- When portfolio was deployed
    deployment_usd DECIMAL(20,10) NOT NULL,  -- Total portfolio size at creation

    -- Constraints used (for record-keeping)
    token_exposure_limit DECIMAL(10,6),      -- Max token exposure (0-1)
    protocol_exposure_limit DECIMAL(10,6),   -- Max protocol exposure (0-1)
    max_strategies INTEGER,                  -- Max number of strategies
    min_apy_confidence DECIMAL(10,6),        -- Min confidence threshold
    apr_weight_net DECIMAL(10,6),            -- APR weight for net_apr
    apr_weight_5d DECIMAL(10,6),             -- APR weight for apr5
    apr_weight_30d DECIMAL(10,6),            -- APR weight for apr30
    apr_weight_90d DECIMAL(10,6),            -- APR weight for apr90

    -- Current state
    current_value_usd DECIMAL(20,10),        -- Current portfolio value (updated on queries)
    total_pnl DECIMAL(20,10) DEFAULT 0.0,    -- Cumulative PnL
    weighted_apr DECIMAL(10,6),              -- Current weighted APR

    -- Rebalancing tracking
    rebalance_count INTEGER DEFAULT 0,
    last_rebalance_timestamp TIMESTAMP,

    -- Closure
    close_timestamp TIMESTAMP,
    close_reason TEXT,
    close_notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_portfolios_status (status),
    INDEX idx_portfolios_entry_timestamp (entry_timestamp),
    INDEX idx_portfolios_name (portfolio_name)
);
```

#### 2. Update `positions` Table

**Add portfolio relationship:**

```sql
ALTER TABLE positions ADD COLUMN portfolio_id TEXT NOT NULL DEFAULT 'single_trades';
ALTER TABLE positions ADD COLUMN strategy_sequence INTEGER DEFAULT 1;  -- Order within portfolio (1, 2, 3...)

-- Add foreign key constraint (will be enforced after migration)
ALTER TABLE positions ADD CONSTRAINT fk_portfolio
    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
    ON DELETE CASCADE;

-- Add index
CREATE INDEX idx_positions_portfolio_id ON positions(portfolio_id);
```

**Migration Strategy:**

```sql
-- Step 1: Create special "Single Trades" portfolio for legacy positions
INSERT INTO portfolios (
    portfolio_id,
    portfolio_name,
    status,
    entry_timestamp,
    deployment_usd,
    -- Constraints: NULL or default values
    token_exposure_limit,
    protocol_exposure_limit,
    max_strategies,
    min_apy_confidence,
    apr_weight_net,
    apr_weight_5d,
    apr_weight_30d,
    apr_weight_90d
) VALUES (
    'single_trades',  -- Special UUID-like identifier
    'Single Trades (Legacy)',
    'active',
    (SELECT MIN(entry_timestamp) FROM positions),  -- Earliest position timestamp
    0.0,  -- Will be calculated as sum of all positions
    NULL,  -- No constraints for legacy positions
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
);

-- Step 2: Backfill existing positions with portfolio_id = 'single_trades'
UPDATE positions
SET portfolio_id = 'single_trades'
WHERE portfolio_id IS NULL OR portfolio_id = '';

-- Step 3: Set strategy_sequence based on entry_timestamp
WITH numbered_positions AS (
    SELECT
        position_id,
        ROW_NUMBER() OVER (PARTITION BY portfolio_id ORDER BY entry_timestamp) as seq
    FROM positions
)
UPDATE positions p
SET strategy_sequence = np.seq
FROM numbered_positions np
WHERE p.position_id = np.position_id;
```

**Tab Filtering Logic:**

```python
# Positions Tab (legacy single positions)
positions_df = position_service.get_positions(
    portfolio_id='single_trades'
)

# Portfolio Tab (allocated portfolios)
portfolios_df = portfolio_service.get_portfolios(
    exclude_portfolio_id='single_trades'
)
```

#### 3. `portfolio_rebalances` Table

**Purpose:** Track portfolio-level rebalances

```sql
CREATE TABLE portfolio_rebalances (
    rebalance_id TEXT PRIMARY KEY,                    -- UUID
    portfolio_id TEXT NOT NULL,                       -- FK to portfolios
    sequence_number INTEGER NOT NULL,                 -- 1, 2, 3, ...

    -- Timing
    opening_timestamp TIMESTAMP NOT NULL,             -- Rebalance period start
    closing_timestamp TIMESTAMP NOT NULL,             -- Rebalance period end

    -- Portfolio-level metrics
    opening_deployment_usd DECIMAL(20,10),            -- Total deployment at start
    closing_deployment_usd DECIMAL(20,10),            -- Total deployment at end
    realised_pnl DECIMAL(20,10),                      -- PnL for this period
    realised_fees DECIMAL(20,10),                     -- Total fees paid

    -- APR metrics
    opening_weighted_apr DECIMAL(10,6),               -- Weighted APR at start
    closing_weighted_apr DECIMAL(10,6),               -- Weighted APR at end
    realised_apr DECIMAL(10,6),                       -- Actual APR for period

    -- Strategy changes
    strategies_closed INTEGER DEFAULT 0,              -- Number of strategies closed
    strategies_opened INTEGER DEFAULT 0,              -- Number of strategies opened
    capital_reallocated_usd DECIMAL(20,10),           -- Amount moved between strategies

    -- Metadata
    rebalance_reason TEXT,                            -- 'manual', 'auto_drift', 'auto_performance'
    rebalance_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON DELETE CASCADE,

    INDEX idx_portfolio_rebalances_portfolio (portfolio_id),
    INDEX idx_portfolio_rebalances_sequence (portfolio_id, sequence_number)
);
```

### Database Relationships

```
portfolios (1) ──────── (N) positions
    │                         │
    │                         └── Each position belongs to one portfolio
    │
    └─────── (N) portfolio_rebalances
                  │
                  └── Portfolio-level rebalance history

positions (1) ──────── (N) position_rebalances
    │
    └── Strategy-level rebalance history (unchanged from current system)
```

### Data Integrity Rules

1. **Cascade Deletes:** Deleting a portfolio deletes all associated positions and rebalances
2. **Special Portfolio "single_trades":**
   - Contains all legacy individually-deployed positions
   - Cannot be deleted (protected by application logic)
   - Shown in Positions Tab (not Portfolio Tab)
   - Acts as catch-all for positions deployed via "All Strategies" tab
3. **Strategy Sequence:** Auto-incremented within portfolio, based on entry_timestamp order
4. **Status Transitions:** active → closed (no reopening)

---

## Stage 1: Constraint-Based Allocation

### Status: Implementation Ready

### User-Defined Constraints

#### 1. Portfolio Size
- **Type:** USD amount
- **Default:** 500 (changed from deploymentUSD sidebar)
- **Purpose:** Total capital to allocate across strategies
- **UI:** Number input at top of Allocation tab
- **Example:** $10,000 portfolio split across 5 strategies

#### 2. Token Exposure Limit
- **Type:** Percentage (0-100%)
- **Default:** 30%
- **Purpose:** Maximum allocation to any single token
- **Calculation:** Aggregate by token_contract (not symbol!)
- **Example:** If limit is 30% and portfolio is $10,000, max exposure to any token is $3,000

**Why contract-based:** Symbols can be duplicated (e.g., USDT vs suiUSDT). Contracts are unique.

#### 3. Protocol Exposure Limit
- **Type:** Percentage (0-100%)
- **Default:** 40%
- **Purpose:** Maximum allocation to any single protocol
- **Calculation:** Aggregate by protocol name
- **Example:** If limit is 40% and portfolio is $10,000, max exposure to Navi is $4,000

#### 4. Max Number of Strategies
- **Type:** Integer (1-20)
- **Default:** 5
- **Purpose:** Limit portfolio complexity and management overhead
- **Note:** Actual count may be less if constraints prevent more allocations

#### 5. Minimum APY Confidence
- **Type:** Percentage (50-100%)
- **Default:** 70%
- **Purpose:** Only include strategies with high confidence that APY will persist
- **Calculation:** See [APY Confidence Calculation](#apy-confidence-calculation)

#### 6. APR Blend Weights
- **Type:** Four percentages that must sum to 100%
- **Defaults:** netAPR=30%, apr5=30%, apr30=30%, apr90=10%
- **Purpose:** Balance immediate vs long-term APR in strategy ranking
- **Calculation:** `blended_apr = w1*net_apr + w2*apr5 + w3*apr30 + w4*apr90`
- **User Control:** Fully configurable in dashboard UI

**Example Configurations:**
- **Aggressive (short-term):** netAPR=70%, apr5=20%, apr30=10%, apr90=0%
- **Balanced:** netAPR=30%, apr5=30%, apr30=30%, apr90=10% (default)
- **Conservative (long-term):** netAPR=10%, apr5=10%, apr30=40%, apr90=40%

### APY Confidence Calculation

**Method:** Historical analysis with normal distribution assumption

**Algorithm:**
```python
def calculate_apy_confidence(strategy_row, db_connection):
    """
    Calculate confidence that strategy's APY will persist.

    Approach:
    1. Query rates_snapshot for past 60 days of historical APR data
    2. Calculate mean and standard deviation
    3. Assume normal distribution
    4. Project future APR as min(current, mean + 1*std_dev)
    5. Confidence = how close current is to projected
    6. Blend with apr5 and apr30 for additional context

    Returns:
        Float between 0-1 representing confidence (1 = highest confidence)
    """
    token1_contract = strategy_row['token1_contract']
    token2_contract = strategy_row['token2_contract']
    protocol_a = strategy_row['protocol_a']
    protocol_b = strategy_row['protocol_b']

    current_timestamp = strategy_row['timestamp']
    lookback_seconds = 60 * 86400  # 60 days
    start_timestamp = current_timestamp - lookback_seconds

    # Step 1: Query historical APR data for all 4 legs
    # Leg 1A: Token1 lend in Protocol A
    historical_1a = query_historical_apr(
        db_connection,
        token_contract=token1_contract,
        protocol=protocol_a,
        rate_type='lend_total_apr',
        start_ts=start_timestamp,
        end_ts=current_timestamp
    )

    # [... similar for legs 2A, 2B, 3B ...]

    # Step 2: Calculate net APR history
    # Net APR = (lend_1a + lend_2b) - (borrow_2a + borrow_3b)
    net_apr_history = []
    for i in range(len(historical_1a)):
        net_apr = (
            historical_1a[i] * strategy_row['l_a'] +
            historical_2b[i] * strategy_row['l_b'] -
            historical_2a[i] * strategy_row['b_a'] -
            historical_3b[i] * strategy_row['b_b']
        )
        net_apr_history.append(net_apr)

    # Step 3: Calculate mean and std deviation
    if len(net_apr_history) < 7:  # Need at least 1 week of data
        return 0.5  # Default medium confidence if insufficient history

    mean_apr = np.mean(net_apr_history)
    std_apr = np.std(net_apr_history)

    # Step 4: Project future APR
    # Assumption: APR will revert to min(current, mean + 1*std_dev)
    current_net_apr = strategy_row['net_apr']
    projected_apr = min(current_net_apr, mean_apr + std_apr)

    # Step 5: Calculate confidence based on current vs projected
    # If current is much higher than projected, confidence is lower
    if current_net_apr > 0:
        confidence_base = min(1.0, projected_apr / current_net_apr)
    else:
        confidence_base = 0.0

    # Step 6: Blend with apr5 and apr30 for additional context
    # If apr5 and apr30 are close to current, confidence increases
    apr5 = strategy_row['apr5']
    apr30 = strategy_row['apr30']

    # Calculate variance between current and short-term APRs
    if current_net_apr > 0:
        apr5_ratio = min(1.0, apr5 / current_net_apr) if apr5 > 0 else 0.5
        apr30_ratio = min(1.0, apr30 / current_net_apr) if apr30 > 0 else 0.5
    else:
        apr5_ratio = 0.5
        apr30_ratio = 0.5

    # Weighted blend
    confidence = (
        0.50 * confidence_base +     # Historical reversion
        0.30 * apr5_ratio +           # 5-day stability
        0.20 * apr30_ratio            # 30-day stability
    )

    # Clamp to [0, 1]
    return max(0.0, min(1.0, confidence))
```

**Key Insight:** If current APR is significantly above historical mean + 1 std dev, confidence will be lower, reflecting higher risk that APR won't persist.

---

### Refined Statistical Approach (Using Normal Distribution)

**Assumption:** APR follows a normal distribution over the 60-day lookback period.

**Algorithm:**
```python
import numpy as np
from scipy import stats

def calculate_apy_confidence_statistical(strategy_row, db_connection):
    """
    Calculate confidence using statistical p-value approach.

    Approach:
    1. Query 60 days of historical net APR data
    2. Assume normal distribution: APR ~ N(μ, σ²)
    3. Calculate z-score: z = (current_apr - mean) / std_dev
    4. Calculate p-value: p(X >= current_apr | μ, σ)
    5. Map p-value to confidence score
    6. Blend with apr5 and apr30 for additional validation

    Returns:
        Dictionary with:
        - confidence: float (0-1)
        - mean_apr: float
        - std_dev_apr: float
        - z_score: float
        - p_value: float (probability of observing current or higher)
        - percentile: float (0-100, current APR's position in distribution)
    """
    # Step 1-2: Calculate historical net APR (same as before)
    net_apr_history = calculate_net_apr_history(
        strategy_row, db_connection, lookback_days=60
    )

    if len(net_apr_history) < 7:
        return {
            'confidence': 0.5,
            'mean_apr': None,
            'std_dev_apr': None,
            'z_score': None,
            'p_value': None,
            'percentile': None
        }

    # Step 3: Calculate distribution parameters
    mean_apr = np.mean(net_apr_history)
    std_apr = np.std(net_apr_history, ddof=1)  # Sample std dev
    current_apr = strategy_row['net_apr']

    # Step 4: Calculate z-score
    if std_apr > 0:
        z_score = (current_apr - mean_apr) / std_apr
    else:
        z_score = 0.0

    # Step 5: Calculate p-value (probability of observing current or higher)
    # Using survival function: P(X >= x) = 1 - CDF(x)
    p_value = stats.norm.sf(z_score)  # 1 - norm.cdf(z_score)

    # Calculate percentile (where current APR falls in distribution)
    percentile = stats.norm.cdf(z_score) * 100

    # Step 6: Map p-value to confidence
    # Logic: p-value = P(X >= current_apr) directly answers "will APR stay at this level or higher?"
    # - Low p-value (high APR) = low confidence (unlikely to persist)
    # - Medium p-value (median APR) = medium confidence (50/50 chance)
    # - High p-value (low APR) = high confidence (conservative, likely to persist)

    # Direct mapping with slight smoothing to avoid extreme values
    confidence_base = p_value

    # Optional: Apply slight sigmoid to smooth extremes while preserving relationship
    # For now, use direct p-value as it directly answers the question

    # Step 7: Blend with short-term stability (apr5, apr30)
    apr5 = strategy_row['apr5']
    apr30 = strategy_row['apr30']

    # Calculate how consistent short-term APRs are with current
    if current_apr > 0:
        apr5_consistency = min(1.0, apr5 / current_apr) if apr5 > 0 else 0.5
        apr30_consistency = min(1.0, apr30 / current_apr) if apr30 > 0 else 0.5
    else:
        apr5_consistency = 0.5
        apr30_consistency = 0.5

    # Weighted blend (optional - could just use p-value directly)
    # Blend with short-term consistency gives additional validation
    confidence = (
        0.60 * confidence_base +      # Historical distribution (p-value)
        0.25 * apr5_consistency +      # 5-day stability
        0.15 * apr30_consistency       # 30-day stability
    )

    # Alternative: Use p-value directly without blending
    # confidence = confidence_base  # Pure statistical approach

    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))

    return {
        'confidence': confidence,
        'mean_apr': mean_apr,
        'std_dev_apr': std_apr,
        'z_score': z_score,
        'p_value': p_value,
        'percentile': percentile
    }
```

**Interpretation Guide:**

| Z-Score | Percentile | P-Value | Interpretation | Base Confidence (≈ p-value) |
|---------|------------|---------|----------------|------------------------------|
| -2.0 | 2.3% | 0.977 | Very low (bottom 2.3%) | 0.98 (conservative, very safe) |
| -1.0 | 15.9% | 0.841 | Below average | 0.84 (below avg, safe) |
| 0.0 | 50% | 0.500 | Median (typical) | 0.50 (50/50 chance) |
| +1.0 | 84.1% | 0.159 | Above average | 0.16 (above avg, risky) |
| +1.5 | 93.3% | 0.067 | High (top 7%) | 0.07 (high, very risky) |
| +2.0 | 97.7% | 0.023 | Very high (top 2.3%) | 0.02 (unsustainable) |
| +3.0 | 99.9% | 0.001 | Extreme outlier | 0.00 (almost certain to revert) |

**Key Insights:**
1. **Current APR at median** (z=0, p=0.5): **Confidence = 0.50** - 50% chance it stays at or above this level (neutral)
2. **Current APR 2 std devs above mean** (z=+2, p=0.023): **Confidence = 0.02** - only 2.3% chance it stays this high (very risky)
3. **Current APR 2 std devs below mean** (z=-2, p=0.977): **Confidence = 0.98** - 97.7% chance it stays at or above this low level (very conservative)

**Why this works:**
- p-value **directly answers** "What's the probability APR stays at current level or higher?"
- Low confidence for high APRs → discourage allocating to unsustainably high yields
- High confidence for low APRs → encourage conservative positions (safer bet)

**Display in Dashboard:**
```python
# In strategy detail modal or allocation tab
st.markdown(f"""
**Confidence Analysis:**
- Confidence Score: {result['confidence']*100:.1f}%
- Historical Mean APR: {result['mean_apr']*100:.2f}%
- Current APR Percentile: {result['percentile']:.1f}% (z={result['z_score']:.2f})
- Interpretation: {'⚠️ Unusually high' if result['p_value'] < 0.05 else '✅ Typical' if result['p_value'] < 0.75 else '🛡️ Conservative'}
""")
```

**Benefits of This Approach:**
1. ✅ Statistically rigorous (uses proper p-values)
2. ✅ Records all diagnostic metrics (z-score, p-value, percentile)
3. ✅ Intuitive interpretation (percentile ranking)
4. ✅ Penalizes high outliers more than low outliers (conservative bias)
5. ✅ Blends with short-term stability for robustness

---

### UI Design - Allocation Tab

#### Input Section

```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 Portfolio Allocation                                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Portfolio Size (USD)                                         │
│ [     10000     ]  ← Number input                            │
│                                                              │
├──────────────────────────────┬──────────────────────────────┤
│ ⚙️  Portfolio Constraints     │                              │
├──────────────────────────────┴──────────────────────────────┤
│ Exposure Limits              │ APY Confidence & Weighting   │
│                              │                              │
│ Max Token Exposure (%)       │ Minimum APY Confidence (%)   │
│ [========○=====] 30%         │ [============○===] 70%       │
│                              │                              │
│ Max Protocol Exposure (%)    │ Blended APR Weights          │
│ [==========○===] 40%         │ (must sum to 100%)           │
│                              │                              │
│ Max Number of Strategies     │ Net APR Weight (%): [30]     │
│ [5]                          │ 5-Day APR Weight (%): [30]   │
│                              │ 30-Day APR Weight (%): [30]  │
│                              │ 90-Day APR Weight (%): [10]  │
│                              │ ✓ Sum = 100%                 │
└──────────────────────────────┴──────────────────────────────┘

              [🎲 Generate Optimal Portfolio]
```

#### Portfolio Preview Section (After Generation)

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Portfolio Generated: 5 strategies selected                │
├─────────────┬──────────────┬───────────────┬────────────────┤
│Total        │Capital       │Weighted APR   │Diversification │
│Allocated    │Utilization   │               │                │
│$9,850       │98.5%         │8.42%          │0.78            │
└─────────────┴──────────────┴───────────────┴────────────────┘

📊 Exposure Breakdown
[... token and protocol tables ...]

📋 Selected Strategies
[... strategy details table ...]

┌─────────────────────────────────────────────────────────────┐
│ 💾 Deploy Portfolio                                          │
│                                                              │
│ Portfolio Name:                                              │
│ [Conservative Q1 2026                            ]           │
│                                                              │
│         [🚀 Deploy Portfolio]  [📥 Download CSV]             │
└─────────────────────────────────────────────────────────────┘
```

---

## Portfolio Tab & Management

### Tab Structure

**Location:** Add after "Allocation" tab, before "Rate Tables"

```python
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📊 All Strategies",
    "🎯 Allocation",
    "📈 Portfolio",        # NEW - shows allocated portfolios
    "📋 Rate Tables",
    "⚠️ 0 Liquidity",
    "💼 Positions",        # Shows "Single Trades" portfolio (legacy)
    "💎 Oracle Prices",
    "🚀 Pending Deployments"
])
```

**Tab Filtering:**
- **Portfolio Tab:** Shows all portfolios EXCEPT `portfolio_id='single_trades'`
- **Positions Tab:** Shows only `portfolio_id='single_trades'` (legacy individually-deployed positions)

### Nested View Hierarchy

```
Portfolio Tab
│
├── Portfolio 1: "Conservative Q1 2026"  ▶  (collapsed)
│   │  $10,000 | PnL: $142 (1.42%) | APR: 8.42%
│   │
│   ├── (expanded) ▼
│   │   ├── Strategy 1: USDC/DEEP/USDC | Navi ↔ AlphaFi  ▶
│   │   │   │  $2,500 | PnL: $38 | APR: 8.95%
│   │   │   │
│   │   │   ├── (expanded) ▼
│   │   │   │   ├── Rebalance #1: Jan 19 → Jan 25
│   │   │   │   ├── Rebalance #2: Jan 25 → Feb 1
│   │   │   │   └── Live: Feb 1 → Now
│   │   │   │
│   │   │
│   │   ├── Strategy 2: USDC/SUI/USDC | Navi ↔ Suilend  ▶
│   │   │   $2,200 | PnL: $31 | APR: 8.73%
│   │   │
│   │   ├── Strategy 3: ...
│   │   ├── Strategy 4: ...
│   │   └── Strategy 5: ...
│   │
│   └── [🔄 Rebalance Portfolio] [❌ Close Portfolio]
│
├── Portfolio 2: "Aggressive Yield"  ▶  (collapsed)
│   $5,000 | PnL: $87 (1.74%) | APR: 10.25%
│
└── Portfolio 3: "Balanced Growth"  ▶  (collapsed)
    $15,000 | PnL: $203 (1.35%) | APR: 7.89%
```

### Portfolio Summary Row (Collapsed)

**Display:**
```
▶ Conservative Q1 2026 | Created: Jan 19, 2026 | 5 Strategies |
  Value: $10,142 | PnL: $142 (1.42%) | Weighted APR: 8.42% |
  Last Rebalance: 3 days ago
```

**Columns:**
- Expand/collapse arrow
- Portfolio name
- Creation date
- Strategy count
- Current value
- Total PnL ($ and %)
- Weighted APR
- Last rebalance timestamp

### Portfolio Detail View (Expanded)

#### A. Portfolio-Level Metrics

```
┌─────────────────────────────────────────────────────────────┐
│ Portfolio: Conservative Q1 2026                              │
│ Created: January 19, 2026 10:00 AM                          │
│ Status: Active | 5 Strategies | 2 Rebalances                │
├─────────────┬──────────────┬───────────────┬────────────────┤
│Deployment   │Current Value │Total PnL      │Weighted APR    │
│$10,000      │$10,142       │$142 (1.42%)   │8.42%           │
├─────────────┼──────────────┼───────────────┼────────────────┤
│Total        │Base Earnings │Reward Earn    │Fees Paid       │
│Earnings     │              │               │                │
│$195         │$152          │$43            │$53             │
└─────────────┴──────────────┴───────────────┴────────────────┘
```

#### B. Constraints Used

```
📋 Allocation Constraints (at creation)
• Portfolio Size: $10,000
• Token Exposure Limit: 30%
• Protocol Exposure Limit: 40%
• Max Strategies: 5
• Min Confidence: 70%
• APR Weights: netAPR=30%, apr5=30%, apr30=30%, apr90=10%
```

#### C. Current Exposure Breakdown

```
📊 Current Portfolio Exposure
┌──────────────────────┬──────────────────────┐
│ Token Exposure       │ Protocol Exposure    │
│ USDC: $2,950 (29%)   │ Navi: $3,940 (39%)   │
│ SUI:  $2,100 (21%)   │ AlphaFi: $3,200 (32%)│
│ DEEP: $1,800 (18%)   │ Suilend: $2,860 (28%)│
└──────────────────────┴──────────────────────┘
```

#### D. Strategy List (Expandable Rows)

Each strategy row displays:
- Same format as current Positions tab
- Token flow: token1 → token2 → token3
- Protocols: Protocol A ↔ Protocol B
- Entry APR, Current APR, Net APR
- Value, PnL, Earnings breakdown
- Expand to show rebalance history

#### E. Portfolio Actions

```
┌─────────────────────────────────────────────────────────────┐
│ 🔧 Portfolio Actions                                         │
│                                                              │
│ [🔄 Rebalance Portfolio]  [💾 Export Report]  [❌ Close]    │
│                                                              │
│ Note: Rebalancing will adjust individual strategies to      │
│ restore target allocations and respond to market changes.   │
└─────────────────────────────────────────────────────────────┘
```

#### F. Portfolio Rebalance History

```
┌─────────────────────────────────────────────────────────────┐
│ 📜 Portfolio Rebalance History                               │
├─────────────────────────────────────────────────────────────┤
│ Rebalance #1: Jan 19, 2026 → Jan 25, 2026                   │
│ • Realised PnL: $62 (0.62%)                                 │
│ • Realised APR: 8.75%                                        │
│ • Strategies Closed: 0 | Opened: 0                          │
│ • Capital Reallocated: $0 (no strategy changes)             │
│                                                              │
│ Rebalance #2: Jan 25, 2026 → Feb 1, 2026                    │
│ • Realised PnL: $48 (0.48%)                                 │
│ • Realised APR: 8.20%                                        │
│ • Strategies Closed: 1 | Opened: 1                          │
│ • Capital Reallocated: $2,200 (replaced low-performing)     │
│ • Details: [Show More ▼]                                    │
│                                                              │
│ Current Segment: Feb 1, 2026 → Now                          │
│ • Live PnL: $32 (unrealized)                                │
│ • Current APR: 8.42%                                         │
│ • Days Active: 8                                             │
└─────────────────────────────────────────────────────────────┘
```

### Portfolio Service Implementation

**File:** `analysis/portfolio_service.py` (NEW)

**Key Methods:**

```python
class PortfolioService:
    """Service for managing portfolio lifecycle."""

    def __init__(self, conn, engine=None):
        """Initialize with database connection."""
        self.conn = conn
        self.engine = engine
        self.position_service = PositionService(conn, engine)

    def create_portfolio(
        self,
        portfolio_name: str,
        deployment_usd: float,
        constraints: Dict,
        entry_timestamp: int
    ) -> str:
        """
        Create portfolio record in database.

        Args:
            portfolio_name: User-defined name
            deployment_usd: Total portfolio size
            constraints: Dictionary with all constraint values
            entry_timestamp: Unix seconds

        Returns:
            portfolio_id (UUID)
        """
        portfolio_id = str(uuid.uuid4())

        query = """
        INSERT INTO portfolios (
            portfolio_id, portfolio_name, status,
            entry_timestamp, deployment_usd,
            token_exposure_limit, protocol_exposure_limit,
            max_strategies, min_apy_confidence,
            apr_weight_net, apr_weight_5d, apr_weight_30d, apr_weight_90d,
            current_value_usd, weighted_apr
        ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        self.conn.execute(query, (
            portfolio_id,
            portfolio_name,
            to_datetime_str(entry_timestamp),
            deployment_usd,
            constraints['token_exposure_limit'],
            constraints['protocol_exposure_limit'],
            constraints['max_strategies'],
            constraints['min_apy_confidence'],
            constraints['apr_weights']['net_apr'],
            constraints['apr_weights']['apr5'],
            constraints['apr_weights']['apr30'],
            constraints['apr_weights']['apr90'],
            deployment_usd,  # Initial value = deployment
            0.0  # Initial weighted APR (will be calculated)
        ))

        self.conn.commit()
        return portfolio_id

    def deploy_portfolio(
        self,
        portfolio_id: str,
        strategies_df: pd.DataFrame,
        entry_timestamp: int
    ) -> List[str]:
        """
        Deploy all strategies in portfolio.

        Args:
            portfolio_id: Portfolio UUID
            strategies_df: DataFrame with selected strategies and allocation_usd
            entry_timestamp: Unix seconds

        Returns:
            List of position_ids created
        """
        position_ids = []

        for sequence, (idx, strategy) in enumerate(strategies_df.iterrows(), 1):
            # Create position using existing PositionService
            position_id = self.position_service.create_position(
                strategy_row=strategy,
                positions={
                    'l_a': strategy['l_a'],
                    'b_a': strategy['b_a'],
                    'l_b': strategy['l_b'],
                    'b_b': strategy['b_b']
                },
                deployment_usd=strategy['allocation_usd'],
                token1=strategy['token1'],
                token2=strategy['token2'],
                token3=strategy['token3'],
                token1_contract=strategy['token1_contract'],
                token2_contract=strategy['token2_contract'],
                token3_contract=strategy['token3_contract'],
                protocol_a=strategy['protocol_a'],
                protocol_b=strategy['protocol_b'],
                entry_timestamp=entry_timestamp
            )

            # Link position to portfolio
            self._link_position_to_portfolio(position_id, portfolio_id, sequence)

            position_ids.append(position_id)

        self.conn.commit()
        return position_ids

    def _link_position_to_portfolio(
        self,
        position_id: str,
        portfolio_id: str,
        sequence: int
    ):
        """Update position with portfolio_id and sequence."""
        query = """
        UPDATE positions
        SET portfolio_id = ?, strategy_sequence = ?
        WHERE position_id = ?
        """
        self.conn.execute(query, (portfolio_id, sequence, position_id))

    def get_portfolios(
        self,
        live_timestamp: Optional[int] = None,
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get all portfolios with optional filtering.

        Args:
            live_timestamp: Unix seconds (filter by entry <= timestamp)
            status: 'active', 'closed', or None for all

        Returns:
            DataFrame with portfolio records
        """
        query = "SELECT * FROM portfolios WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if live_timestamp:
            query += " AND entry_timestamp <= ?"
            params.append(to_datetime_str(live_timestamp))

        query += " ORDER BY entry_timestamp DESC"

        engine = self.engine if self.engine else self.conn
        df = pd.read_sql_query(query, engine, params=params)

        # Convert timestamps
        if not df.empty:
            df['entry_timestamp'] = df['entry_timestamp'].apply(to_seconds)
            # ... convert other timestamp fields

        return df

    def get_portfolio_strategies(self, portfolio_id: str) -> pd.DataFrame:
        """
        Get all positions (strategies) in a portfolio.

        Args:
            portfolio_id: Portfolio UUID

        Returns:
            DataFrame with positions, ordered by strategy_sequence
        """
        query = """
        SELECT * FROM positions
        WHERE portfolio_id = ?
        ORDER BY strategy_sequence ASC
        """

        engine = self.engine if self.engine else self.conn
        df = pd.read_sql_query(query, engine, params=(portfolio_id,))

        # Convert timestamps and numeric fields
        if not df.empty:
            df = self.position_service._convert_position_types(df)

        return df

    def calculate_portfolio_metrics(
        self,
        portfolio_id: str,
        current_timestamp: int
    ) -> Dict:
        """
        Calculate current portfolio-level metrics.

        Args:
            portfolio_id: Portfolio UUID
            current_timestamp: Unix seconds

        Returns:
            Dictionary with:
            - current_value_usd
            - total_pnl
            - total_earnings
            - base_earnings
            - reward_earnings
            - total_fees
            - weighted_apr
            - token_exposures
            - protocol_exposures
        """
        strategies = self.get_portfolio_strategies(portfolio_id)

        if strategies.empty:
            return {}

        # Calculate metrics for each strategy
        total_value = 0
        total_pnl = 0
        total_earnings = 0
        base_earnings = 0
        reward_earnings = 0
        total_fees = 0

        weighted_apr_sum = 0
        total_deployment = 0

        token_exposures = {}
        protocol_exposures = {}

        for _, strategy in strategies.iterrows():
            entry_ts = strategy['entry_timestamp']
            deployment = strategy['deployment_usd']
            total_deployment += deployment

            # Calculate strategy metrics
            pv_result = self.position_service.calculate_position_value(
                strategy, entry_ts, current_timestamp
            )

            total_value += pv_result['current_value']
            total_pnl += pv_result['net_earnings']
            total_fees += pv_result['fees']

            # Calculate earnings split
            # [Similar to current position statistics calculation]

            # Calculate current APR for this strategy
            current_apr = self._calculate_strategy_current_apr(strategy, current_timestamp)
            weighted_apr_sum += current_apr * deployment

            # Aggregate exposures
            for token_num in [1, 2, 3]:
                contract = strategy[f'token{token_num}_contract']
                symbol = strategy[f'token{token_num}']
                if contract not in token_exposures:
                    token_exposures[contract] = {'symbol': symbol, 'usd': 0}
                token_exposures[contract]['usd'] += deployment

            for protocol in [strategy['protocol_a'], strategy['protocol_b']]:
                if protocol not in protocol_exposures:
                    protocol_exposures[protocol] = {'usd': 0}
                protocol_exposures[protocol]['usd'] += deployment

        weighted_apr = weighted_apr_sum / total_deployment if total_deployment > 0 else 0

        return {
            'current_value_usd': total_value,
            'total_pnl': total_pnl,
            'total_earnings': total_earnings,
            'base_earnings': base_earnings,
            'reward_earnings': reward_earnings,
            'total_fees': total_fees,
            'weighted_apr': weighted_apr,
            'token_exposures': token_exposures,
            'protocol_exposures': protocol_exposures
        }

    def rebalance_portfolio(
        self,
        portfolio_id: str,
        rebalance_timestamp: int,
        reason: str,
        notes: str = ""
    ):
        """
        Rebalance all strategies in portfolio and record portfolio-level event.

        Args:
            portfolio_id: Portfolio UUID
            rebalance_timestamp: Unix seconds
            reason: 'manual', 'auto_drift', 'auto_performance'
            notes: Optional notes
        """
        # Get portfolio and strategies
        portfolio = self.get_portfolio_by_id(portfolio_id)
        strategies = self.get_portfolio_strategies(portfolio_id)

        # Capture opening state
        opening_metrics = self.calculate_portfolio_metrics(
            portfolio_id, portfolio['last_rebalance_timestamp'] or portfolio['entry_timestamp']
        )

        # Rebalance each strategy
        for _, strategy in strategies.iterrows():
            self.position_service.rebalance_position(
                position_id=strategy['position_id'],
                rebalance_timestamp=rebalance_timestamp,
                rebalance_reason=f"portfolio_rebalance:{reason}",
                rebalance_notes=notes
            )

        # Capture closing state
        closing_metrics = self.calculate_portfolio_metrics(
            portfolio_id, rebalance_timestamp
        )

        # Create portfolio rebalance record
        rebalance_id = str(uuid.uuid4())
        sequence_number = portfolio['rebalance_count'] + 1

        query = """
        INSERT INTO portfolio_rebalances (
            rebalance_id, portfolio_id, sequence_number,
            opening_timestamp, closing_timestamp,
            opening_deployment_usd, closing_deployment_usd,
            realised_pnl, realised_fees,
            opening_weighted_apr, closing_weighted_apr,
            rebalance_reason, rebalance_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        self.conn.execute(query, (
            rebalance_id, portfolio_id, sequence_number,
            to_datetime_str(portfolio['last_rebalance_timestamp'] or portfolio['entry_timestamp']),
            to_datetime_str(rebalance_timestamp),
            opening_metrics.get('current_value_usd', 0),
            closing_metrics.get('current_value_usd', 0),
            closing_metrics['total_pnl'] - opening_metrics.get('total_pnl', 0),
            closing_metrics['total_fees'] - opening_metrics.get('total_fees', 0),
            opening_metrics.get('weighted_apr', 0),
            closing_metrics.get('weighted_apr', 0),
            reason,
            notes
        ))

        # Update portfolio
        update_query = """
        UPDATE portfolios SET
            rebalance_count = rebalance_count + 1,
            last_rebalance_timestamp = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE portfolio_id = ?
        """

        self.conn.execute(update_query, (
            to_datetime_str(rebalance_timestamp),
            portfolio_id
        ))

        self.conn.commit()

    def close_portfolio(
        self,
        portfolio_id: str,
        close_timestamp: int,
        close_reason: str,
        close_notes: str = ""
    ):
        """
        Close portfolio and all constituent strategies.

        Args:
            portfolio_id: Portfolio UUID
            close_timestamp: Unix seconds
            close_reason: Reason for closure
            close_notes: Optional notes
        """
        strategies = self.get_portfolio_strategies(portfolio_id)

        # Close each strategy
        for _, strategy in strategies.iterrows():
            self.position_service.close_position(
                position_id=strategy['position_id'],
                close_timestamp=close_timestamp,
                close_reason=f"portfolio_closed:{close_reason}",
                close_notes=close_notes
            )

        # Update portfolio status
        query = """
        UPDATE portfolios SET
            status = 'closed',
            close_timestamp = ?,
            close_reason = ?,
            close_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE portfolio_id = ?
        """

        self.conn.execute(query, (
            to_datetime_str(close_timestamp),
            close_reason,
            close_notes,
            portfolio_id
        ))

        self.conn.commit()
```

---

## Stage 2: Cost Calculation

[Previous content remains unchanged - just add portfolio context where relevant]

---

## Stage 3: Optimization & Reallocation

[Previous content remains unchanged - just add portfolio context where relevant]

---

## Implementation Roadmap

### Phase 1: Core Allocator (Current - Updated)

**Goal:** Working allocation tab with constraint enforcement and portfolio deployment

**Tasks:**
1. ✅ Explore codebase architecture
2. ✅ Design PortfolioAllocator service
3. ⬜ **Create database schema** (2 hours)
   - Create portfolios table
   - Add portfolio_id to positions table
   - Create portfolio_rebalances table
   - Write migration scripts
4. ⬜ **Create portfolio_allocator.py** (3-4 hours)
   - Implement PortfolioAllocator class
   - Implement calculate_apy_confidence() with historical queries
   - Implement calculate_blended_apr()
   - Implement select_portfolio() greedy algorithm
   - Implement calculate_portfolio_exposures()
5. ⬜ **Create portfolio_service.py** (4-5 hours)
   - Implement PortfolioService class
   - Implement create_portfolio()
   - Implement deploy_portfolio()
   - Implement get_portfolios()
   - Implement get_portfolio_strategies()
   - Implement calculate_portfolio_metrics()
   - Implement rebalance_portfolio()
   - Implement close_portfolio()
6. ⬜ **Add allocation tab to dashboard** (3 hours)
   - Implement render_allocation_constraints()
   - Add portfolio size input
   - Implement render_allocation_tab()
   - Add portfolio name input
   - Add deploy portfolio button
   - Update tab creation and ordering
7. ⬜ **Add portfolio tab to dashboard** (4-5 hours)
   - Implement render_portfolio_tab()
   - Implement nested expandable rows
   - Portfolio summary row
   - Strategy rows (reuse from positions tab)
   - Rebalance history
   - Portfolio actions
8. ⬜ **Update config defaults** (15 min)
   - Change deploymentUSD to 500
   - Add DEFAULT_ALLOCATION_CONSTRAINTS
9. ⬜ **End-to-end testing** (2-3 hours)
   - Test portfolio creation flow
   - Test deployment
   - Test portfolio tab display
   - Test nested expansion
   - Test rebalancing
   - Verify exposure calculations
10. ⬜ **Documentation and polish** (1 hour)
    - Update this plan document
    - Add inline comments
    - Create user guide

**Total Time:** 20-25 hours
**Status:** In Progress
**Target Completion:** Next 2-3 implementation sessions

### Phase 2: Cost Analysis
[Remains unchanged]

### Phase 3: Optimization & Auto-Reallocation
[Remains unchanged]

---

## Design Decisions

### Why Separate Portfolio Tab Instead of Replacing Positions Tab?

**Pros:**
- ✅ Clean separation of concerns (portfolios vs legacy single positions)
- ✅ Allows gradual migration without breaking existing functionality
- ✅ Users can compare portfolio-based vs position-based approaches
- ✅ Eventually delete positions tab once portfolios are stable

**Cons:**
- ❌ Two tabs doing similar things (short-term duplication)
- ❌ Slightly more complex dashboard navigation

**Decision:** Create separate Portfolio tab. Positions tab will be marked as "Legacy" and eventually removed once all users have migrated to portfolios.

### Why Nested Expandable Rows?

**Pros:**
- ✅ Clean hierarchy: Portfolio → Strategies → Rebalances
- ✅ Reduces visual clutter
- ✅ User can drill down to desired detail level
- ✅ Familiar pattern (same as current Positions tab)

**Cons:**
- ❌ More clicks to see full detail
- ❌ Slightly more complex rendering logic

**Decision:** Use nested expandable rows. This matches the existing Positions tab pattern and provides a clean way to organize hierarchical data.

### Why Link Positions to Portfolios Instead of Separate Tables?

**Pros:**
- ✅ Reuses existing position infrastructure
- ✅ Easier migration (just add portfolio_id column)
- ✅ Consistent position tracking across both tabs
- ✅ Simpler codebase

**Cons:**
- ❌ Positions table becomes slightly more complex
- ❌ Need special "single_trades" portfolio for legacy positions

**Decision:** Link via portfolio_id foreign key with special "single_trades" portfolio for legacy. This is the most pragmatic approach:
- ✅ No NULL values (cleaner data model)
- ✅ Easy filtering (Positions tab vs Portfolio tab)
- ✅ Consistent: all positions always belong to a portfolio
- ✅ Can still track legacy positions separately

### Why Portfolio Size Input Separate from Sidebar deploymentUSD?

**Clarity:**
- Sidebar deploymentUSD filters strategies by liquidity
- Portfolio size determines total capital to allocate
- These are related but distinct concepts

**Decision:** Keep both. Sidebar default changes to 500. Portfolio size input in Allocation tab starts at 10000 (but user can adjust).

---

## Testing Strategy

[Previous testing strategy remains valid - add portfolio-specific tests:]

### Additional Integration Tests for Portfolios

1. **Portfolio Creation:**
   - Create portfolio with 5 strategies
   - Verify all positions linked correctly
   - Verify portfolio record created

2. **Portfolio Display:**
   - Load portfolio tab
   - Verify all portfolios listed
   - Test expand/collapse functionality
   - Verify metrics calculation

3. **Portfolio Rebalancing:**
   - Rebalance portfolio
   - Verify all strategies rebalanced
   - Verify portfolio rebalance record created
   - Verify metrics updated

4. **Portfolio Closure:**
   - Close portfolio
   - Verify all positions closed
   - Verify portfolio status updated to 'closed'

5. **Mixed State:**
   - Create portfolio
   - Create legacy single position
   - Verify both show in correct tabs
   - Verify no cross-contamination

---

## Migration Plan

### Phase 1: Additive Changes (No Breaking Changes)

**Timeline:** First 2 implementation sessions

1. **Database Migration:**
   - Create new tables (portfolios, portfolio_rebalances)
   - Create special "Single Trades" portfolio with ID 'single_trades'
   - Add portfolio_id column to positions (default 'single_trades')
   - Backfill existing positions with portfolio_id = 'single_trades'
   - Add strategy_sequence column (auto-numbered by entry_timestamp)

2. **Code Implementation:**
   - Create PortfolioService and PortfolioAllocator
   - Update PositionService to handle portfolio_id filtering
   - Add Allocation tab
   - Add Portfolio tab (filters out 'single_trades')
   - Update Positions tab (filters only 'single_trades')

3. **All Strategies Tab:**
   - Deployments still create positions in "Single Trades" portfolio
   - Maintains backward compatibility

**Result:** Clean separation - Portfolio tab for allocated portfolios, Positions tab for legacy single trades.

### Phase 2: Encourage Portfolio Usage

**Timeline:** After Phase 1 is stable (1-2 weeks)

1. Add notice to Positions tab: "💡 New: Try creating a portfolio from the Allocation tab for better organization and constraint-based selection!"
2. Add "Create Portfolio from Selected Positions" button in Positions tab
3. User guide and documentation emphasizing portfolio-based approach
4. Show success metrics in Allocation tab (e.g., "15 portfolios created | $150K allocated")

### Phase 3: Simplification (Optional)

**Timeline:** After most users prefer portfolios (2-3 months)

1. **Option A: Keep both tabs** (Recommended)
   - Positions tab for quick single-strategy deployments
   - Portfolio tab for multi-strategy allocation
   - Both serve different use cases

2. **Option B: Merge into Portfolio tab**
   - Show "Single Trades" as just another portfolio in Portfolio tab
   - Remove Positions tab entirely
   - All Strategies deployments create single-strategy portfolios

**Note:** Phase 1 is the focus. Future phases are optional based on user feedback.

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-09 | 1.0 | Initial plan created | Claude |
| 2026-02-09 | 2.0 | Major architecture update: portfolio-centric approach | Claude |

---

## Appendix: Key Design Principles

[Previous design principles remain unchanged]

---

**End of Plan Document**

This document will be continuously updated as implementation progresses. Each completed task will be marked and actual implementation details will be added.
