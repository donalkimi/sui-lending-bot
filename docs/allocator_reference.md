# Portfolio Allocator System - Reference Documentation

**Version:** 1.0
**Status:** Implemented and Active
**Last Updated:** February 10, 2026

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Constraint Configuration](#constraint-configuration)
4. [Allocation Algorithm](#allocation-algorithm)
5. [Exposure Calculations](#exposure-calculations)
6. [Portfolio Persistence](#portfolio-persistence)
7. [Dashboard Interface](#dashboard-interface)
8. [Database Schema](#database-schema)
9. [Code Reference](#code-reference)

---

## System Overview

### Purpose

The Portfolio Allocator is a constraint-based portfolio construction system that:
- Analyzes yield opportunities from existing strategies
- Applies user-defined constraints on risk and diversification
- Generates optimal portfolio allocations using a greedy algorithm
- Persists portfolios to the database for tracking
- Calculates exposures based on lending positions only

### Key Features

1. **Constraint-Based Selection**: Users define token exposure limits, protocol exposure limits, strategy count, confidence thresholds, and APR weighting preferences
2. **Stablecoin Preferences**: Apply multipliers to strategies containing specific stablecoins
3. **Token-Specific Overrides**: Override default token exposure limits for individual tokens
4. **Blended APR Calculation**: Weighted average of net_apr, apr5, apr30, apr90
5. **Adjusted APR Ranking**: Apply stablecoin penalties before ranking
6. **Strategy Max Size**: Respect liquidity limits for each strategy
7. **Portfolio Persistence**: Save generated portfolios to database with full tracking
8. **Exposure Tracking**: Calculate token and protocol exposures using lending weights only

---

## Architecture

### Component Overview

```
Dashboard Layer (dashboard_renderer.py)
├── Allocation Tab
│   ├── Constraint Input Section
│   ├── Generate Portfolio Button
│   ├── Portfolio Preview
│   └── Save Portfolio Button
│
└── Portfolios Tab
    ├── Portfolio List
    ├── Portfolio Detail View
    └── Portfolio Actions

Service Layer
├── PortfolioAllocator (analysis/portfolio_allocator.py)
│   ├── calculate_blended_apr()
│   ├── calculate_adjusted_apr()
│   ├── select_portfolio()
│   └── calculate_portfolio_exposures()
│
└── PortfolioService (analysis/portfolio_service.py)
    ├── save_portfolio()
    ├── get_active_portfolios()
    ├── get_portfolio_by_id()
    └── get_portfolio_positions()

Database Layer
├── portfolios table
└── positions table (with portfolio_id FK)
```

### Data Flow

1. **User Input**: User sets portfolio size and constraints in Allocation tab
2. **Strategy Loading**: System loads strategies from RateAnalyzer (pre-filtered by dashboard settings)
3. **APR Calculations**: Calculate blended APR and adjusted APR for each strategy
4. **Ranking**: Sort strategies by adjusted APR (descending)
5. **Greedy Allocation**: Select strategies respecting all constraints
6. **Preview**: Display portfolio with exposures and metrics
7. **Save**: Persist portfolio to database
8. **View**: Display in Portfolios tab with full details

---

## Constraint Configuration

### How Constraints Are Set

Constraints are configured in the **Allocation Tab** of the dashboard. The UI provides input controls for each constraint type.

### Constraint Types

#### 1. Portfolio Size
- **Input Type**: Number input (USD)
- **Default**: $10,000
- **Purpose**: Total capital to allocate across selected strategies
- **Location**: Top of Allocation tab
- **Validation**: Must be positive number

#### 2. Token Exposure Limit
- **Input Type**: Slider (0-100%)
- **Default**: 30%
- **Purpose**: Maximum exposure to any single token
- **Calculation**: Aggregate by `token_contract` (not symbol)
- **Example**: With 30% limit and $10k portfolio, max exposure to any token is $3,000

**Token Exposure Override:**
- **Input Type**: Dictionary input `{token_symbol: limit_pct}`
- **Purpose**: Override default limit for specific tokens
- **Example**: `{"USDC": 0.50, "USDT": 0.40}` allows 50% USDC, 40% USDT, but 30% for others

#### 3. Protocol Exposure Limit
- **Input Type**: Slider (0-100%)
- **Default**: 40%
- **Purpose**: Maximum exposure to any single protocol
- **Calculation**: Aggregate by protocol name
- **Example**: With 40% limit and $10k portfolio, max exposure to Navi is $4,000

#### 4. Max Number of Strategies
- **Input Type**: Number input (1-20)
- **Default**: 10
- **Purpose**: Limit portfolio complexity
- **Note**: Actual count may be lower if constraints prevent more allocations

#### 5. Stablecoin Preferences
- **Input Type**: Dictionary input `{token_symbol: multiplier}`
- **Default**: Empty (no penalties)
- **Purpose**: De-prioritize strategies containing certain stablecoins
- **Range**: Multipliers between 0.0 and 1.0
- **Example**: `{"USDC": 0.8}` applies 20% penalty to strategies with USDC

**How It Works:**
- If strategy contains multiple stablecoins from preferences, use the **lowest** multiplier (most conservative)
- If strategy contains no stablecoins from preferences, multiplier = 1.0 (no penalty)
- `adjusted_apr = blended_apr × stablecoin_multiplier`

#### 6. APR Blend Weights
- **Input Type**: Four percentage inputs (must sum to 100%)
- **Default**: `net_apr=25%, apr5=25%, apr30=25%, apr90=25%`
- **Purpose**: Balance short-term vs long-term APR in ranking
- **Auto-Normalization**: Dashboard automatically normalizes weights to sum to 100%

**Example Configurations:**
- **Aggressive**: `net_apr=70%, apr5=20%, apr30=10%, apr90=0%` (focus on current rates)
- **Balanced**: `net_apr=25%, apr5=25%, apr30=25%, apr90=25%` (equal weight)
- **Conservative**: `net_apr=10%, apr5=10%, apr30=40%, apr90=40%` (focus on stability)

### Constraint Storage

Constraints are stored in `config/settings.py` as `DEFAULT_ALLOCATION_CONSTRAINTS`:

```python
DEFAULT_ALLOCATION_CONSTRAINTS = {
    'token_exposure_limit': 0.30,  # 30%
    'protocol_exposure_limit': 0.40,  # 40%
    'max_strategies': 10,
    'min_apy_confidence': 0.0,  # Not yet implemented
    'apr_weights': {
        'net_apr': 0.25,
        'apr5': 0.25,
        'apr30': 0.25,
        'apr90': 0.25
    },
    'stablecoin_preferences': {},  # Empty by default
    'token_exposure_overrides': {}  # Empty by default
}
```

Users can override these defaults in the dashboard, and their choices are passed to the allocator.

---

## Allocation Algorithm

### Algorithm Type: Greedy Selection

The allocator uses a **greedy algorithm** that selects strategies one at a time in order of adjusted APR, respecting all constraints.

### Algorithm Steps

```python
def select_portfolio(portfolio_size, constraints):
    """
    Greedy portfolio selection algorithm.
    """
    # Step 1: Filter by confidence (if implemented)
    strategies = filter_by_confidence(
        strategies,
        min_confidence=constraints['min_apy_confidence']
    )

    # Step 2: Calculate blended APR for each strategy
    for strategy in strategies:
        strategy['blended_apr'] = (
            strategy['net_apr'] * apr_weights['net_apr'] +
            strategy['apr5'] * apr_weights['apr5'] +
            strategy['apr30'] * apr_weights['apr30'] +
            strategy['apr90'] * apr_weights['apr90']
        )

    # Step 3: Calculate adjusted APR (apply stablecoin penalty)
    for strategy in strategies:
        stablecoin_multiplier = get_stablecoin_multiplier(
            strategy,
            stablecoin_preferences
        )
        strategy['adjusted_apr'] = (
            strategy['blended_apr'] * stablecoin_multiplier
        )

    # Step 4: Sort by adjusted APR (descending)
    strategies = sort_by(strategies, 'adjusted_apr', descending=True)

    # Step 5: Greedy allocation
    selected = []
    allocated_capital = 0
    token_exposures = {}
    protocol_exposures = {}

    for strategy in strategies:
        if len(selected) >= max_strategies:
            break

        # Calculate max allocation for this strategy
        max_amount = calculate_max_allocation(
            strategy,
            remaining_capital=portfolio_size - allocated_capital,
            token_exposures=token_exposures,
            protocol_exposures=protocol_exposures,
            constraints=constraints
        )

        if max_amount > 0:
            selected.append({
                **strategy,
                'allocation_usd': max_amount
            })
            allocated_capital += max_amount
            update_exposures(strategy, max_amount, token_exposures, protocol_exposures)

    return selected
```

### Max Allocation Calculation

For each strategy, the system calculates the maximum amount that can be allocated without violating any constraint:

```python
def calculate_max_allocation(strategy, remaining_capital, token_exposures,
                            protocol_exposures, constraints, portfolio_size):
    """
    Calculate maximum allocation respecting all constraints.
    """
    max_amount = remaining_capital

    # Constraint 1: Strategy max size (liquidity limit)
    if 'max_size_usd' in strategy:
        max_amount = min(max_amount, strategy['max_size_usd'])

    # Constraint 2: Token exposure limits
    # Note: Uses lending weights (l_a, l_b), not borrow weights
    for token_num in [1, 2, 3]:
        token_contract = strategy[f'token{token_num}_contract']
        token_symbol = strategy[f'token{token_num}']

        # Get lending weight for this token
        if token_num == 1:
            weight = strategy['l_a']  # Token1 lent to Protocol A
        elif token_num == 2:
            weight = strategy['l_b']  # Token2 lent to Protocol B
        else:
            weight = 0.0  # Token3 is only borrowed, not lent

        # Get token limit (use override if available)
        if token_symbol in constraints['token_exposure_overrides']:
            token_limit = portfolio_size * constraints['token_exposure_overrides'][token_symbol]
        else:
            token_limit = portfolio_size * constraints['token_exposure_limit']

        current_exposure = token_exposures.get(token_contract, 0.0)
        remaining_room = token_limit - current_exposure

        # Max allocation = remaining_room / weight
        max_allocation_for_token = remaining_room / weight if weight > 0 else float('inf')
        max_amount = min(max_amount, max_allocation_for_token)

    # Constraint 3: Protocol exposure limits
    protocol_limit = portfolio_size * constraints['protocol_exposure_limit']

    for protocol, weight in [(strategy['protocol_a'], strategy['l_a']),
                              (strategy['protocol_b'], strategy['l_b'])]:
        current_exposure = protocol_exposures.get(protocol, 0.0)
        remaining_room = protocol_limit - current_exposure

        # Max allocation = remaining_room / weight
        max_allocation_for_protocol = remaining_room / weight if weight > 0 else float('inf')
        max_amount = min(max_amount, max_allocation_for_protocol)

    return max(0.0, max_amount)
```

### Key Algorithm Properties

1. **Greedy**: Selects highest adjusted APR first
2. **Constraint-Respecting**: Never violates any constraint
3. **Deterministic**: Same inputs always produce same output
4. **Fast**: O(n log n) time complexity (dominated by sorting)
5. **Transparent**: Users see exactly why each strategy was selected (adjusted APR)

---

## Exposure Calculations

### Critical Design Principle: Lending Only

**Exposures count only lending positions, not borrows.**

Rationale:
- Lending = actual capital at risk on a protocol or in a token
- Borrowing = liability, but capital is immediately re-lent elsewhere
- Counting both would double-count exposure

### Token2 Exposure (De-Leveraged Exposure)

**New Definition (February 2026)**: Token2 exposure measures the **de-leveraged exposure** to token2 (the borrowed token) across all strategies.

#### Formula

**Token2 Exposure = Σ(Ci × B_A / L_A)** for all strategies i containing token2

Where:
- **Ci** = capital allocated to strategy i
- **B_A** = borrow weight for token2 at protocol A (amount/ratio of token2 borrowed)
- **L_A** = lend weight for token1 at protocol A (amount/ratio of token1 lent)

#### Rationale

By dividing **B_A** by **L_A**, we remove the leverage component and measure the exposure per $1 deployed to the strategy.

Since **B_A = L_A × r_A** (from recursive lending formulas), this simplifies to:

**Token2 Exposure = Σ(Ci × r_A)**

Where **r_A** is the collateral ratio at protocol A.

#### Maximum Exposure

Since **r_A < 1** (collateral ratio is always less than 100%), the maximum token2 exposure is:

**Max Token2 Exposure = 100% of portfolio size**

#### Example

Portfolio:
- **Portfolio Size**: $10,000
- **Strategy 1**: C1 = $5,000, r_A = 0.70 (70% collateral ratio)
  - Token2 exposure = $5,000 × 0.70 = $3,500
- **Strategy 2**: C2 = $3,000, r_A = 0.80 (80% collateral ratio)
  - Token2 exposure = $3,000 × 0.80 = $2,400

**Total Token2 Exposure** = $3,500 + $2,400 = **$5,900 (59% of portfolio)**

#### Intuition

For each $1 deployed to a strategy with token2:
- You lend L_A × $1 of token1 (with leverage)
- You borrow B_A × $1 of token2
- Your **de-leveraged exposure** to token2 = B_A / L_A = r_A

This measures the **risk-adjusted exposure** to token2, normalized by the leverage factor.

---

### Stablecoin Exposure (Net Lending Position)

**New Definition (February 2026)**: Stablecoin exposure measures the **net lending position** for a stablecoin across all strategies, accounting for both lending and borrowing.

#### Formula

**Stablecoin Exposure$$ = Σ(Ci × L_A) - Σ(Ci × B_B)** for all strategies containing the stablecoin

Where:
- **First sum**: All strategies where the stablecoin is Token1 (lent to Protocol A)
- **Second sum**: All strategies where the stablecoin is Token3 (borrowed from Protocol B)
- **Ci** = capital allocated to strategy i
- **L_A** = lend weight for token1 at protocol A
- **B_B** = borrow weight for token3 at protocol B

**Stablecoin Exposure% = Exposure$$ / portfolio_size**

#### Key Insight: Exposure Can Be Negative

Unlike Token2 exposure (which is always positive), stablecoin exposure can be:
- **Positive**: Net lending position (you lend more than you borrow)
- **Negative**: Net borrowing position (you borrow more than you lend)
- **Zero**: Balanced (you lend and borrow equal amounts)

#### Example

Strategy: **USDC/WAL/suiUSDT**
- **Token1** = USDC (lent to Protocol A)
- **Token2** = WAL (borrowed from A, lent to B) - not a stablecoin
- **Token3** = suiUSDT (borrowed from Protocol B)

Parameters:
- L_A = 1.5
- B_B = 0.5
- Allocation = c1
- Portfolio size = C

**Exposures:**
- **USDC exposure** = +1.5 × c1 (positive, we lend USDC)
- **suiUSDT exposure** = -0.5 × c1 (negative, we borrow suiUSDT)

**As percentages:**
- **USDC exposure%** = (1.5 × c1) / C = 150% of allocation
- **suiUSDT exposure%** = (-0.5 × c1) / C = -50% of allocation

#### Intuition

For each $1 deployed to this strategy:
- You lend $1.50 of USDC (positive exposure)
- You borrow $0.50 of suiUSDT (negative exposure)

The net effect:
- **USDC**: You're long $1.50 (risk: protocol failure, USDC depeg)
- **suiUSDT**: You're short $0.50 (risk: suiUSDT depeg, liquidation if suiUSDT appreciates)

#### Token2 Stablecoins

If Token2 is a stablecoin (e.g., strategy USDC/USDT/USDC):
- Token2 exposure uses the **de-leveraged formula** (B_A / L_A) documented above
- Token1 and Token3 positions contribute to this net lending formula

---

### Protocol Exposure (Normalized to Deployment)

**New Definition (February 2026)**: Protocol exposure measures the capital exposure to each protocol, with Protocol B de-leveraged relative to Protocol A.

#### Formula

**Protocol p Exposure$$ = Σ(contributions from all strategies)**

Where contribution depends on which protocol slot:
- **Protocol A contribution**: ci (full allocation)
- **Protocol B contribution**: ci × L_B / L_A (de-leveraged)

**Protocol Exposure% = Exposure$$ / portfolio_size**

#### Simplified Formula

Since **L_B = B_A** (amount borrowed from A is lent to B) and **B_A = L_A × r_A** (from recursive lending), this simplifies to:

**Protocol B contribution = ci × r_A**

Where **r_A** is the collateral ratio at protocol A.

**Key Insight**: The Protocol B exposure formula reduces to the collateral ratio used in Protocol A. This means:
- Protocol A exposure = Full deployment
- Protocol B exposure = Deployment × collateral ratio

#### Rationale

Protocol A receives the initial deployment capital, so its exposure is the full allocation amount.

Protocol B receives borrowed capital that is then lent. By dividing L_B by L_A, we normalize Protocol B's exposure relative to Protocol A's leverage factor. This de-leveraging ensures that Protocol B's exposure reflects the actual risk-adjusted capital at risk.

#### Example

Strategy: **USDC/WAL/suiUSDT** deployed to **Navi (A) ↔ Suilend (B)**

Parameters:
- L_A = 1.5
- L_B = 1.05 (equal to B_A)
- B_A = 1.05
- Allocation = $5,000
- r_A = B_A / L_A = 1.05 / 1.5 = 0.70 (70% collateral ratio)

**Protocol Exposures:**
- **Navi (Protocol A)**: $5,000 (full allocation)
- **Suilend (Protocol B)**: $5,000 × (1.05 / 1.5) = $5,000 × 0.70 = $3,500 (de-leveraged)

**As percentages (portfolio size = $10,000):**
- **Navi exposure%**: $5,000 / $10,000 = 50%
- **Suilend exposure%**: $3,500 / $10,000 = 35%

#### Intuition

For each $1 deployed:
- Protocol A receives the full $1 of initial capital (exposure = $1)
- Protocol B receives borrowed capital equivalent to r_A × $1 (exposure = $0.70)

This captures the fact that Protocol B's risk is proportional to the collateral ratio, not the full leveraged amount.

---

### Token Exposure Calculation (Legacy)

```python
def calculate_token_exposure(portfolio_df, portfolio_size):
    """
    Calculate token exposures from portfolio.

    Token exposure = amount of capital lent in that token across all strategies.
    """
    token_exposures = {}

    for _, strategy in portfolio_df.iterrows():
        allocation = strategy['allocation_usd']

        # Token1: Lent to Protocol A
        token1_contract = strategy['token1_contract']
        token1_symbol = strategy['token1']
        l_a = strategy['l_a']  # Lending weight for Protocol A
        token1_lend_amount = allocation * l_a

        if token1_contract not in token_exposures:
            token_exposures[token1_contract] = {
                'symbol': token1_symbol,
                'usd': 0.0,
                'pct': 0.0
            }
        token_exposures[token1_contract]['usd'] += token1_lend_amount

        # Token2: Lent to Protocol B
        token2_contract = strategy['token2_contract']
        token2_symbol = strategy['token2']
        l_b = strategy['l_b']  # Lending weight for Protocol B
        token2_lend_amount = allocation * l_b

        if token2_contract not in token_exposures:
            token_exposures[token2_contract] = {
                'symbol': token2_symbol,
                'usd': 0.0,
                'pct': 0.0
            }
        token_exposures[token2_contract]['usd'] += token2_lend_amount

        # Token3: Only borrowed, NOT lent - NO EXPOSURE

    # Calculate percentages
    for contract in token_exposures:
        token_exposures[contract]['pct'] = (
            token_exposures[contract]['usd'] / portfolio_size
        )

    return token_exposures
```

**Example:**

Strategy: $10,000 allocation
- Token1 (USDC): lent $6,000 to Protocol A (l_a = 0.6)
- Token2 (WAL): lent $4,000 to Protocol B (l_b = 0.4)
- Token3 (USDC): borrowed $5,000 from Protocol B (not counted)

Token exposures:
- USDC: $6,000 (60% of $10k allocation)
- WAL: $4,000 (40% of $10k allocation)

### Protocol Exposure Calculation

```python
def calculate_protocol_exposure(portfolio_df, portfolio_size):
    """
    Calculate protocol exposures from portfolio.

    Protocol exposure = amount of capital lent to that protocol across all strategies.
    """
    protocol_exposures = {}

    for _, strategy in portfolio_df.iterrows():
        allocation = strategy['allocation_usd']

        protocol_a = strategy['protocol_a']
        protocol_b = strategy['protocol_b']

        l_a = strategy['l_a']  # Lending weight for Protocol A
        l_b = strategy['l_b']  # Lending weight for Protocol B

        # Protocol A exposure = allocation × l_a
        if protocol_a not in protocol_exposures:
            protocol_exposures[protocol_a] = {'usd': 0.0, 'pct': 0.0}
        protocol_exposures[protocol_a]['usd'] += allocation * l_a

        # Protocol B exposure = allocation × l_b
        if protocol_b not in protocol_exposures:
            protocol_exposures[protocol_b] = {'usd': 0.0, 'pct': 0.0}
        protocol_exposures[protocol_b]['usd'] += allocation * l_b

    # Calculate percentages
    for protocol in protocol_exposures:
        protocol_exposures[protocol]['pct'] = (
            protocol_exposures[protocol]['usd'] / portfolio_size
        )

    return protocol_exposures
```

**Example:**

Strategy: $10,000 allocation
- Protocol A (Navi): lent $6,000 (l_a = 0.6)
- Protocol B (Suilend): lent $4,000 (l_b = 0.4)

Protocol exposures:
- Navi: $6,000 (60% of $10k allocation)
- Suilend: $4,000 (40% of $10k allocation)

### Why Use Lending Weights?

The lending weights (l_a, l_b) represent the **fraction of deployment capital that is lent** to each protocol:

- `l_a`: Fraction lent to Protocol A (as Token1)
- `l_b`: Fraction lent to Protocol B (as Token2)
- `b_a`: Fraction borrowed from Protocol A (as Token2) - NOT USED FOR EXPOSURE
- `b_b`: Fraction borrowed from Protocol B (as Token3) - NOT USED FOR EXPOSURE

These weights already account for price differences and collateral ratios, so multiplying by deployment USD gives the actual USD amount lent.

---

## Portfolio Persistence

### Database Integration

Generated portfolios can be saved to the database for tracking and analysis.

### Save Workflow

1. **User generates portfolio** in Allocation tab
2. **Portfolio preview** displays with metrics and strategies
3. **User clicks "Save Portfolio"** button
4. **System prompts for portfolio name**
5. **PortfolioService.save_portfolio()** creates database records
6. **Success message** with link to Portfolios tab
7. **Portfolio appears** in Portfolios tab

### What Gets Saved

#### Portfolio-Level Data (portfolios table)
- Portfolio ID (UUID)
- Portfolio name (user-defined)
- Status ('active', 'closed', 'archived')
- Entry timestamp
- Target portfolio size
- Actual allocated amount
- Utilization percentage
- **Entry weighted net APR** (primary metric)
- Constraints used (as JSON)
- Notes

#### Strategy-Level Data (positions table)
Each strategy in the portfolio creates a position record linked via `portfolio_id`.

**Note:** The system does NOT create separate portfolio_strategies records. Instead, it reuses the existing positions table by adding a `portfolio_id` foreign key column.

### Primary Metric: Entry Weighted Net APR

The portfolio's primary performance metric is **USD-weighted net APR at entry**:

```python
entry_weighted_net_apr = sum(
    strategy['net_apr'] × strategy['allocation_usd']
    for strategy in portfolio
) / total_allocated
```

This represents the portfolio's expected return based on net APR at the time of creation.

**Why net APR, not blended/adjusted APR?**
- Blended APR and adjusted APR are used for **ranking** strategies during selection
- Net APR is the **actual rate** the strategy is earning right now
- For performance tracking, we care about actual returns, not selection scores

---

## Dashboard Interface

### Allocation Tab

#### Location
Second tab in the dashboard: `"🎯 Allocation"`

#### Layout Structure

```
┌─────────────────────────────────────────────────┐
│ Portfolio Size (USD)                            │
│ [        10000        ]                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ ⚙️ Portfolio Constraints                        │
├─────────────────────────────────────────────────┤
│ Column 1              │ Column 2                │
│                       │                         │
│ Max Token Exposure    │ Max Protocol Exposure   │
│ [=======○========] 30%│ [=======○========] 40% │
│                       │                         │
│ Max # Strategies      │                         │
│ [    10    ]          │                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ APR Blend Weights (must sum to 100%)           │
├─────────────────────────────────────────────────┤
│ Net APR:    [25] %   │ 5-Day APR:  [25] %     │
│ 30-Day APR: [25] %   │ 90-Day APR: [25] %     │
│ ✓ Sum = 100.0%                                  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Stablecoin Preferences (optional)               │
├─────────────────────────────────────────────────┤
│ Token Symbol │ Multiplier (0-1)                 │
│ USDC         │ [0.8]                            │
│ [+ Add Stablecoin]                              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Token Exposure Overrides (optional)             │
├─────────────────────────────────────────────────┤
│ Token Symbol │ Max Exposure (%)                 │
│ USDC         │ [50]                             │
│ [+ Add Token]                                   │
└─────────────────────────────────────────────────┘

              [🎲 Generate Portfolio]
```

#### After Generation

```
┌─────────────────────────────────────────────────┐
│ ✅ Portfolio Generated                          │
├─────────────────────────────────────────────────┤
│ Strategies: 5                                   │
│ Allocated:  $9,850 / $10,000 (98.5%)           │
│ Avg Net APR: 8.42%                              │
└─────────────────────────────────────────────────┘

📊 Exposure Breakdown

Token Exposure:
┌───────────┬──────────┬──────┬─────────┐
│ Token     │ USD      │ %    │ Limit % │
├───────────┼──────────┼──────┼─────────┤
│ USDC      │ $2,950   │ 29.9%│ 30%     │
│ SUI       │ $2,100   │ 21.3%│ 30%     │
│ DEEP      │ $1,800   │ 18.3%│ 30%     │
└───────────┴──────────┴──────┴─────────┘

Protocol Exposure:
┌───────────┬──────────┬──────┬─────────┐
│ Protocol  │ USD      │ %    │ Limit % │
├───────────┼──────────┼──────┼─────────┤
│ Navi      │ $3,940   │ 39.9%│ 40%     │
│ AlphaFi   │ $3,200   │ 32.5%│ 40%     │
│ Suilend   │ $2,710   │ 27.5%│ 40%     │
└───────────┴──────────┴──────┴─────────┘

📋 All Strategies (Ranked by Adjusted APR)

┌──────┬─────────┬─────────┬─────────┬─────────┬──────────┬─────────┬──────────┬──────────┬────────────┬──────────────┐
│ Rank │ Token1  │ Token2  │ Token3  │ Proto A │ Proto B  │ Net APR │ APR5     │ APR30    │ Blended    │ Adjusted APR │
│      │         │         │         │         │          │         │          │          │ APR        │              │
├──────┼─────────┼─────────┼─────────┼─────────┼──────────┼─────────┼──────────┼──────────┼────────────┼──────────────┤
│ 1    │ USDC    │ DEEP    │ USDC    │ Navi    │ AlphaFi  │ 8.95%   │ 9.12%    │ 8.88%    │ 8.98%      │ 8.98%        │
│ 2    │ USDC    │ SUI     │ USDC    │ Navi    │ Suilend  │ 8.73%   │ 8.91%    │ 8.65%    │ 8.77%      │ 8.77%        │
│ ...  │         │         │         │         │          │         │          │          │            │              │
└──────┴─────────┴─────────┴─────────┴─────────┴──────────┴─────────┴──────────┴──────────┴────────────┴──────────────┘

📋 Selected Strategies (Portfolio)

┌─────────┬─────────┬─────────┬─────────┬──────────┬────────────┬─────────┬──────────────┐
│ Token1  │ Token2  │ Token3  │ Proto A │ Proto B  │ Allocation │ Net APR │ Adjusted APR │
├─────────┼─────────┼─────────┼─────────┼──────────┼────────────┼─────────┼──────────────┤
│ USDC    │ DEEP    │ USDC    │ Navi    │ AlphaFi  │ $2,500     │ 8.95%   │ 8.98%        │
│ USDC    │ SUI     │ USDC    │ Navi    │ Suilend  │ $2,200     │ 8.73%   │ 8.77%        │
│ ...     │         │         │         │          │            │         │              │
└─────────┴─────────┴─────────┴─────────┴──────────┴────────────┴─────────┴──────────────┘

              [💾 Save Portfolio]
```

### Portfolios Tab

#### Location
Sixth tab in the dashboard: `"📁 Portfolios"`

#### Purpose
Display all saved portfolios with expandable detail views.

#### Portfolio List View

```
┌─────────────────────────────────────────────────────────────────┐
│ 💼 Saved Portfolios                                             │
├─────────────────────────────────────────────────────────────────┤
│ ▶ Conservative Q1 2026                                          │
│   Entry: 2026-01-19 | Strategies: 5 | Allocated: $10,000      │
│   Entry Net APR: 8.42%                                          │
├─────────────────────────────────────────────────────────────────┤
│ ▶ Aggressive Yield                                              │
│   Entry: 2026-01-25 | Strategies: 3 | Allocated: $5,000       │
│   Entry Net APR: 10.25%                                         │
└─────────────────────────────────────────────────────────────────┘
```

#### Portfolio Detail View (Expanded)

```
┌─────────────────────────────────────────────────────────────────┐
│ ▼ Conservative Q1 2026                                          │
├─────────────────────────────────────────────────────────────────┤
│ Portfolio Details:                                              │
│ • Created: 2026-01-19 10:00 AM                                 │
│ • Status: Active                                                │
│ • Target Size: $10,000                                          │
│ • Actual Allocated: $9,850 (98.5%)                             │
│ • Entry Weighted Net APR: 8.42%                                 │
├─────────────────────────────────────────────────────────────────┤
│ Constraints Used:                                               │
│ • Token Exposure Limit: 30%                                     │
│ • Protocol Exposure Limit: 40%                                  │
│ • Max Strategies: 10                                            │
│ • APR Weights: net=25%, apr5=25%, apr30=25%, apr90=25%         │
├─────────────────────────────────────────────────────────────────┤
│ Token Exposures:                                                │
│ • USDC: $2,950 (29.9%)                                         │
│ • SUI: $2,100 (21.3%)                                          │
│ • DEEP: $1,800 (18.3%)                                         │
├─────────────────────────────────────────────────────────────────┤
│ Protocol Exposures:                                             │
│ • Navi: $3,940 (39.9%)                                         │
│ • AlphaFi: $3,200 (32.5%)                                      │
│ • Suilend: $2,710 (27.5%)                                      │
├─────────────────────────────────────────────────────────────────┤
│ Strategies:                                                     │
│ 1. USDC → DEEP → USDC (Navi ↔ AlphaFi)  - $2,500 @ 8.95%     │
│ 2. USDC → SUI → USDC (Navi ↔ Suilend)   - $2,200 @ 8.73%     │
│ 3. ...                                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### portfolios Table

```sql
CREATE TABLE IF NOT EXISTS portfolios (
    -- Portfolio Identification
    portfolio_id TEXT PRIMARY KEY,
    portfolio_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'closed', 'archived')),

    -- Ownership
    is_paper_trade BOOLEAN NOT NULL DEFAULT TRUE,
    user_id TEXT,

    -- Creation & Entry
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    entry_timestamp TIMESTAMP NOT NULL,

    -- Portfolio Size
    target_portfolio_size DECIMAL(20, 10) NOT NULL,
    actual_allocated_usd DECIMAL(20, 10) NOT NULL,
    utilization_pct DECIMAL(5, 2) NOT NULL,

    -- PRIMARY METRIC: Entry Net APR
    entry_weighted_net_apr DECIMAL(10, 6) NOT NULL,

    -- Constraints Used (JSON)
    constraints_json TEXT NOT NULL,

    -- Performance Tracking
    accumulated_realised_pnl DECIMAL(20, 10) DEFAULT 0.0,
    rebalance_count INTEGER DEFAULT 0,
    last_rebalance_timestamp TIMESTAMP,

    -- Closure Tracking
    close_timestamp TIMESTAMP,
    close_reason TEXT,
    close_notes TEXT,

    -- User Notes
    notes TEXT,

    -- Timestamps
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_portfolios_status ON portfolios(status);
CREATE INDEX IF NOT EXISTS idx_portfolios_entry_time ON portfolios(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(portfolio_name);
```

### positions Table (Modified)

```sql
-- Existing positions table with new column added
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS portfolio_id TEXT DEFAULT NULL;

-- Foreign key constraint
ALTER TABLE positions
ADD CONSTRAINT fk_positions_portfolio
FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id)
ON DELETE SET NULL;

-- Index for portfolio queries
CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);
```

### Relationship

- **One-to-Many**: One portfolio has many positions (strategies)
- **Foreign Key**: `positions.portfolio_id → portfolios.portfolio_id`
- **Cascade**: ON DELETE SET NULL (if portfolio deleted, positions remain but are orphaned)

---

## Code Reference

### Key Files

#### 1. analysis/portfolio_allocator.py

**Main Class**: `PortfolioAllocator`

**Key Methods**:
```python
def calculate_blended_apr(strategy_row, apr_weights):
    """Calculate weighted average of net_apr, apr5, apr30, apr90."""

def calculate_adjusted_apr(strategy_row, blended_apr, stablecoin_prefs):
    """Apply stablecoin preference penalty to blended APR."""

def select_portfolio(portfolio_size, constraints):
    """Main greedy algorithm. Returns DataFrame with selected strategies."""

def calculate_portfolio_exposures(portfolio_df, portfolio_size):
    """Calculate token and protocol exposures using lending weights."""

def _calculate_max_allocation(strategy_row, remaining_capital,
                              token_exposures, protocol_exposures,
                              constraints, portfolio_size):
    """Calculate max allocation respecting all constraints."""

def _update_exposures(strategy_row, allocation_amount,
                     token_exposures, protocol_exposures):
    """Update exposure tracking after allocating to strategy."""
```

**File Location**: [analysis/portfolio_allocator.py](../analysis/portfolio_allocator.py)

#### 2. analysis/portfolio_service.py

**Main Class**: `PortfolioService`

**Key Methods**:
```python
def save_portfolio(portfolio_name, portfolio_df, portfolio_size,
                  constraints, entry_timestamp, is_paper_trade,
                  user_id, notes):
    """Save generated portfolio to database. Returns portfolio_id."""

def get_active_portfolios():
    """Get all active portfolios. Returns DataFrame."""

def get_portfolio_by_id(portfolio_id):
    """Get single portfolio. Returns Series or None."""

def get_portfolio_positions(portfolio_id):
    """Get all positions in a portfolio. Returns DataFrame."""

def calculate_portfolio_pnl(portfolio_id, live_timestamp, position_service):
    """Calculate current portfolio PnL. Returns Dict with metrics."""

def close_portfolio(portfolio_id, close_timestamp, close_reason, close_notes):
    """Close portfolio (mark as closed)."""
```

**File Location**: [analysis/portfolio_service.py](../analysis/portfolio_service.py)

#### 3. dashboard/dashboard_renderer.py

**Key Functions**:
```python
def render_allocation_tab(strategies_df, timestamp_seconds, conn, engine):
    """
    Render Allocation tab.
    - Constraint inputs
    - Generate portfolio button
    - Portfolio preview
    - Save portfolio button
    """

def render_portfolio_preview(portfolio_df, portfolio_size, exposures):
    """
    Display generated portfolio.
    - Summary metrics
    - Exposure tables
    - Strategy list
    - Save button
    """

def render_portfolios_tab(timestamp_seconds, conn, engine):
    """
    Render Portfolios tab.
    - List of saved portfolios
    - Expandable detail views
    """

def render_portfolio_detail(portfolio, portfolio_id, conn, engine):
    """
    Display detailed portfolio view.
    - Portfolio metadata
    - Constraints used
    - Exposures
    - Strategy list
    """
```

**File Location**: [dashboard/dashboard_renderer.py](../dashboard/dashboard_renderer.py)

#### 4. config/settings.py

**Key Constant**:
```python
DEFAULT_ALLOCATION_CONSTRAINTS = {
    'token_exposure_limit': 0.30,
    'protocol_exposure_limit': 0.40,
    'max_strategies': 10,
    'min_apy_confidence': 0.0,
    'apr_weights': {
        'net_apr': 0.25,
        'apr5': 0.25,
        'apr30': 0.25,
        'apr90': 0.25
    },
    'stablecoin_preferences': {},
    'token_exposure_overrides': {}
}
```

**File Location**: [config/settings.py](../config/settings.py)

### Interaction Flow

```
User Action: Set constraints and click "Generate Portfolio"
    ↓
dashboard_renderer.render_allocation_tab()
    ↓
PortfolioAllocator.select_portfolio(portfolio_size, constraints)
    ├─> calculate_blended_apr() for each strategy
    ├─> calculate_adjusted_apr() for each strategy
    ├─> Sort by adjusted_apr
    └─> Greedy loop:
        ├─> _calculate_max_allocation()
        └─> _update_exposures()
    ↓
Return selected portfolio DataFrame
    ↓
dashboard_renderer.render_portfolio_preview()
    ├─> Display summary metrics
    └─> PortfolioAllocator.calculate_portfolio_exposures()
    ↓
User clicks "Save Portfolio"
    ↓
PortfolioService.save_portfolio()
    ├─> Insert into portfolios table
    └─> Return portfolio_id
    ↓
Success message with link to Portfolios tab
    ↓
dashboard_renderer.render_portfolios_tab()
    ├─> PortfolioService.get_active_portfolios()
    └─> Display portfolio list with expand/collapse
```

---

## Summary

The Portfolio Allocator system provides a comprehensive constraint-based approach to portfolio construction:

1. **User-Friendly Configuration**: All constraints are configurable via the dashboard UI
2. **Transparent Algorithm**: Greedy selection based on adjusted APR with visible rankings
3. **Accurate Exposure Tracking**: Uses lending weights only, correctly reflects capital at risk
4. **Persistent Portfolios**: Saved portfolios can be tracked over time
5. **Flexible Constraints**: Token overrides, stablecoin preferences, and APR weighting allow fine-tuned control
6. **Integration**: Seamlessly integrated with existing positions and rate analysis systems

The system is production-ready and actively in use for portfolio allocation and tracking.

---

**For questions or issues, refer to the code files linked above or consult the development team.**
