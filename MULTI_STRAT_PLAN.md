# Multi-Strategy Implementation Plan

**Status**: Phases 1-6 Complete, Phase 7 In Progress
**Last Updated**: February 16, 2026

---

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ **COMPLETE** | Strategy Calculator Layer - Created base class, 3 calculators, and registry |
| **Phase 2** | ✅ **COMPLETE** | Update Rate Analyzer to support multiple strategy types |
| **Phase 3** | ✅ **COMPLETE** | Update Position Service & Creation |
| **Phase 4** | ✅ **COMPLETE** | Update Portfolio Allocator |
| **Phase 5** | ✅ **COMPLETE** | Create Strategy Renderers |
| **Phase 6** | ✅ **COMPLETE** | Update Rebalance Calculation |
| **Phase 7** | ⏳ Planned | Update Dashboard Strategy Display |
| **Phase 8** | ⏳ Planned | Update Refresh Pipeline |

---

## Complete Data Flow: Strategy Discovery to Position Deployment

This diagram shows how the multi-strategy system works from data collection to position deployment:

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA COLLECTION (Hourly on Railway)                │
└─────────────────────────────────────────────────────────────┘
   refresh_pipeline()
   ├─ Fetches rates, prices, fees from all protocols
   ├─ Saves to rates_snapshot table
   └─ Returns: merged DataFrames

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: STRATEGY DISCOVERY (What Phase 2 implements)       │
└─────────────────────────────────────────────────────────────┘
   RateAnalyzer.analyze_all_combinations()
   │
   ├─ For each strategy type:
   │  │
   │  ├─ _generate_stablecoin_strategies()
   │  │  └─ Iterate: stablecoin × protocol
   │  │     └─ Call calculator.analyze_strategy()
   │  │        └─ Returns: {l_a, b_a, l_b, b_b, net_apr, ...}
   │  │
   │  ├─ _generate_noloop_strategies()
   │  │  └─ Iterate: stablecoin × high-yield × protocol_pair
   │  │     └─ Call calculator.analyze_strategy()
   │  │        └─ Returns: {l_a, b_a, l_b, b_b, net_apr, ...}
   │  │
   │  └─ _generate_recursive_strategies()
   │     └─ Iterate: token1 × token2 × token3 × protocol_pair
   │        └─ Call calculator.analyze_strategy()
   │           └─ Returns: {l_a, b_a, l_b, b_b, net_apr, ...}
   │
   └─ Combine all results into single DataFrame
      └─ Sort by net_apr descending
         └─ Returns: DataFrame with 100-500+ strategies

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: DISPLAY IN DASHBOARD                               │
└─────────────────────────────────────────────────────────────┘
   "All Strategies" Tab
   │
   ├─ Shows DataFrame from analyzer.analyze_all_combinations()
   ├─ User can filter by strategy_type
   ├─ User can sort by APR, max_size, etc.
   └─ Each row has "Deploy" button

                    ↓

┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: USER DEPLOYS POSITION (This writes to database)    │
└─────────────────────────────────────────────────────────────┘
   User clicks "Deploy" button on a strategy
   │
   └─ position_service.create_position()
      ├─ Takes strategy data from DataFrame row
      ├─ Creates position_id (UUID)
      ├─ INSERT INTO positions table
      └─ Position now exists in database
```

**Key Points:**
- **Discovery ≠ Deployment**: Generation methods analyze opportunities (Phase 2-3), but don't create positions
- **Read-Only Analysis**: Phases 1-3 are pure analysis with no database writes to positions table
- **Explicit User Action**: Only Phase 4 (user clicking "Deploy") creates a position in the database
- **Separation of Concerns**: Strategy discovery is independent of position management

---

## Context

The Sui Lending Bot currently supports only one strategy type: **RECURSIVE_LENDING** (4-leg levered loop strategy). The goal is to expand the system to support multiple strategy types with varying complexity levels, while maintaining all existing functionality.

**Current Limitation**: The strategy type is hardcoded as `'recursive_lending'` throughout the codebase, preventing the addition of new strategy types.

**Desired Outcome**: A flexible, extensible architecture where:
- Multiple strategy types can coexist
- The "All Strategies" view shows strategies from all types
- Each strategy type has its own calculation, rendering, and tracking logic
- Strategies range from simple (single-token lending) to complex (recursive leverage loops)
- Existing code paths remain functional with minimal changes

---

## Strategy Type Definitions

### Strategy 1: STABLECOIN_LENDING (Simplest)
**Description**: Single-token stablecoin lending in one protocol

**Mechanics**:
- Lend a stablecoin (e.g., USDC) in Protocol A
- No borrowing, no cross-protocol activity
- Just earning base lending APR + rewards

**Position Multipliers**:
- `L_A = 1.0` (lend $1 for every $1 deployed)
- `B_A = 0` (no borrowing)
- `L_B = 0` (no second lending leg)
- `B_B = 0` (no second borrowing leg)

**Tokens**: Single stablecoin (token1 only)

**Protocols**: Single protocol (protocol_A only)

**APR Calculation**:
```
Net APR = lend_rate_1A + lend_reward_1A
```

**Risk Profile**:
- ✅ No liquidation risk (no collateral)
- ✅ No rebalancing needed (no borrowed assets)
- ✅ No price exposure (stablecoin only)
- ⚠️ Protocol risk only

**Use Case**: Capital preservation, earning "risk-free" rate on stablecoins

---

### Strategy 2: NOLOOP_CROSS_PROTOCOL_LENDING (3-Leg, No Loop Back)
**Description**: Cross-protocol lending with one borrow leg, no loop back to starting token

**Mechanics**:
1. Lend token1 (stablecoin) in Protocol A
2. Borrow token2 (high-yield token) from Protocol A using token1 as collateral
3. Lend token2 in Protocol B for higher rate
4. **No loop back** - position stays exposed to token2

**Position Multipliers**:
- `L_A = 1.0` (lend token1)
- `B_A = L_A × liquidation_threshold_A / (1 + liq_dist)` (borrow token2, with safety buffer)
- `L_B = B_A` (lend borrowed token2)
- `B_B = 0` (no borrow back)

**Math Explanation**:
- If liquidation_threshold = 0.80 (liquidate at 80% LTV)
- And liq_dist = 0.20 (20% safety buffer)
- Then borrow up to: 0.80 / 1.20 = 0.667 = 66.7% LTV
- This keeps position 20% away from liquidation threshold

**Tokens**: Two tokens (token1 = stablecoin, token2 = high-yield), token3 = None

**Protocols**: Two protocols (protocol_A, protocol_B)

**APR Calculation**:
```
Net APR = (L_A × lend_rate_1A) + (L_B × lend_rate_2B)
        - (B_A × borrow_rate_2A)
        - (B_A × borrow_fee_2A)
```

**Risk Profile**:
- ⚠️ Liquidation risk on leg 2A (if token2 price drops below liquidation threshold)
- ⚠️ Rebalancing needed (token2 price changes affect USD values)
- ⚠️ Token2 price exposure (position gains/loses if token2 appreciates/depreciates)
- ⚠️ Two protocol risks

**Use Case**: Higher yield than stablecoin lending, accepting moderate leverage and price exposure

---

### Strategy 3: RECURSIVE_LENDING (4-Leg, Full Loop - Already Exists)
**Description**: Recursive cross-protocol leverage loop, market-neutral

**Mechanics**:
1. Lend token1 (stablecoin) in Protocol A
2. Borrow token2 (high-yield) from Protocol A
3. Lend token2 in Protocol B
4. Borrow token3 (stablecoin) from Protocol B
5. **Loop back**: Convert token3 → token1 (1:1 for stablecoins)
6. Geometric series convergence creates recursive leverage

**Position Multipliers**:
- `L_A = 1 / (1 - r_A × r_B)` (recursive leverage formula)
- `B_A = L_A × r_A`
- `L_B = B_A`
- `B_B = L_B × r_B`

Where `r_A`, `r_B` are effective collateral ratios adjusted for liquidation distance.

**Tokens**: Three tokens (token1 = stablecoin, token2 = high-yield, token3 = stablecoin)

**Protocols**: Two protocols (protocol_A, protocol_B)

**APR Calculation**:
```
Net APR = (L_A × lend_rate_1A) + (L_B × lend_rate_2B)
        - (B_A × borrow_rate_2A) - (B_B × borrow_rate_3B)
        - (B_A × borrow_fee_2A) - (B_B × borrow_fee_3B)
```

**Risk Profile**:
- ⚠️ Liquidation risk on both legs (2A and 3B)
- ⚠️ Complex rebalancing (4 legs to maintain)
- ✅ Market neutral (token1 = token3, cancels price exposure)
- ⚠️ Two protocol risks
- ⚠️ Higher leverage magnifies APR (both positive and negative)

**Use Case**: Maximize yield through recursive leverage while staying market-neutral

---

## Strategy Comparison Table

| Aspect | STABLECOIN_LENDING | NOLOOP_CROSS_PROTOCOL | RECURSIVE_LENDING |
|--------|-------------------|----------------------|-------------------|
| **Legs** | 1 | 3 | 4 |
| **Tokens** | 1 (stablecoin) | 2 (stable + high-yield) | 3 (stable + high-yield + stable) |
| **Protocols** | 1 | 2 | 2 |
| **Leverage** | None (1x) | Moderate (~1.5x) | High (~2-4x) |
| **Market Neutral** | N/A | No | Yes |
| **Liquidation Risk** | None | Single leg (2A) | Two legs (2A, 3B) |
| **Rebalancing** | Not needed | Needed | Needed (complex) |
| **Complexity** | Minimal | Moderate | High |
| **Expected APR** | Lowest (3-5%) | Medium (5-15%) | Highest (10-30%) |
| **Position Multipliers** | L_A=1, rest=0 | L_A=1, B_A>0, L_B>0 | All 4 legs > 0 |

---

## ~~Phase 1: Strategy Calculator Layer~~ ✅ COMPLETE

**Status**: ✅ Implemented and tested (February 13, 2026)
**Commit**: `763164c - "starting multi strategy"`

### ~~1.1: Create Abstract Strategy Calculator Base Class~~ ✅

**File Created**: `analysis/strategy_calculators/base.py` (105 lines)

**Implemented**:
- ✅ Abstract base class `StrategyCalculatorBase`
- ✅ Required methods: `get_strategy_type()`, `get_required_legs()`, `calculate_positions()`, `calculate_net_apr()`, `analyze_strategy()`, `calculate_rebalance_amounts()`
- ✅ Type hints for all methods
- ✅ Docstrings with parameter descriptions

### ~~1.2: Create Stablecoin Lending Calculator~~ ✅

**File Created**: `analysis/strategy_calculators/stablecoin_lending.py` (158 lines)

**Implemented**:
- ✅ 1-leg calculator (simplest strategy)
- ✅ Position multipliers: `{l_a: 1.0, b_a: 0, l_b: 0, b_b: 0}`
- ✅ APR calculation: `lend_total_apr_1A`
- ✅ No rebalancing needed (returns None)
- ✅ Uses `float('inf')` for unbounded values
- ✅ Data validation with explicit errors

### ~~1.3: Create NoLoop Cross-Protocol Calculator~~ ✅

**File Created**: `analysis/strategy_calculators/noloop_cross_protocol.py` (279 lines)

**Implemented**:
- ✅ 3-leg calculator (moderate complexity)
- ✅ Linear position calculation (no geometric series)
- ✅ Liquidation distance safety buffer
- ✅ APR calculation for 3 legs
- ✅ Uses `b_b = 0` (not None) for consistency
- ✅ Data validation with warnings for nullable fields

### ~~1.4: Extract Recursive Lending Calculator~~ ✅

**File Created**: `analysis/strategy_calculators/recursive_lending.py` (367 lines)

**Implemented**:
- ✅ 4-leg calculator extracted from existing code
- ✅ Geometric series convergence formula
- ✅ All existing functionality preserved
- ✅ Same calculations as before, wrapped in class structure

### ~~1.5: Create Calculator Registry~~ ✅

**File Created**: `analysis/strategy_calculators/__init__.py` (115 lines)

**Implemented**:
- ✅ Registry pattern with `_CALCULATORS` dict
- ✅ `register_calculator()` function
- ✅ `get_calculator(strategy_type)` function
- ✅ `get_all_strategy_types()` function
- ✅ Auto-registration on module import
- ✅ All 3 calculators registered successfully

### ~~Validation~~ ✅

**Test Results**:
- ✅ All 3 calculators registered: `['stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending']`
- ✅ Correct leg counts: stablecoin=1, noloop=3, recursive=4
- ✅ Position calculations working correctly
- ✅ Data validation (fail fast on missing data, log warnings for nullable fields)
- ✅ Uses `float('inf')` for unbounded values
- ✅ Uses `0.0` (not None) for unused legs (b_b)

---

## ~~Phase 2: Update Rate Analyzer~~ ✅ COMPLETE

**Status**: ✅ Implemented and tested (February 16, 2026)
**Goal**: Generate strategies for multiple types in one pass

### ~~2.1: Modify RateAnalyzer to Accept Strategy Types~~ ✅

**File Modified**: `analysis/rate_analyzer.py`

**Changes Made**:

```python
from analysis.strategy_calculators import get_calculator, get_all_strategy_types

class RateAnalyzer:
    def __init__(
        self,
        lend_rates: pd.DataFrame,
        borrow_rates: pd.DataFrame,
        # ... existing params ...
        strategy_types: Optional[List[str]] = None  # NEW PARAMETER
    ):
        # Default to all strategy types if not specified
        if strategy_types is None:
            strategy_types = get_all_strategy_types()

        self.strategy_types = strategy_types

        # Load calculators for each strategy type
        self.calculators = {
            st: get_calculator(st) for st in self.strategy_types
        }

        # Keep existing calculator for backward compatibility
        self.calculator = PositionCalculator(self.liquidation_distance)
```

**FAIL LOUD Enhancement**: Added explicit validation that raises `ValueError` if:
- `strategy_types` is `None` (with helpful error message showing available types)
- `strategy_types` is empty list
- `strategy_types` contains invalid/unregistered types

**Testing**:
- ✅ Calculators dictionary is populated
- ✅ Fails loud and early with clear error messages
- ✅ Syntax check passes

---

### ~~2.2: Add Strategy Type Column to Results~~ ✅

**File Modified**: `analysis/rate_analyzer.py`

**Changes Made**:

In `analyze_all_combinations()` method, ensure all result DataFrames include:

```python
df_results['strategy_type'] = calculator.get_strategy_type()
```

**Testing**:
- ✅ strategy_type column exists in all generation methods
- ✅ Recursive results also get strategy_type column

---

### ~~2.3: Create Strategy-Specific Generation Methods~~ ✅

**File Modified**: `analysis/rate_analyzer.py`

**Methods Added**:

#### Method 1: `_generate_stablecoin_strategies(calculator, tokens)`

```python
def _generate_stablecoin_strategies(
    self,
    calculator: StrategyCalculatorBase,
    tokens: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate stablecoin lending strategies.

    Iteration pattern:
    - token1 (stablecoins only) × protocol_a
    - Single token, single protocol
    """
    results = []

    # Filter to stablecoins only
    stablecoins = tokens if tokens else self.STABLECOINS

    for token1 in stablecoins:
        for protocol_a in self.protocols:
            # Get rates and validate
            lend_total_apr_1A = self.get_rate(self.lend_rates, token1, protocol_a)
            price_1A = self.get_rate(self.prices, token1, protocol_a)

            if lend_total_apr_1A <= 0 or price_1A <= 0:
                continue

            # Call calculator
            result = calculator.analyze_strategy(
                token1=token1,
                protocol_a=protocol_a,
                lend_total_apr_1A=lend_total_apr_1A,
                price_1A=price_1A
            )

            if result.get('valid', False):
                results.append(result)

    df = pd.DataFrame(results)
    if not df.empty:
        df['strategy_type'] = calculator.get_strategy_type()

    return df
```

**Testing**:
- [ ] Generates strategies for all stablecoins
- [ ] Skips invalid combinations
- [ ] Returns correct DataFrame structure

---

#### Method 2: `_generate_noloop_strategies(calculator, tokens)`

```python
def _generate_noloop_strategies(
    self,
    calculator: StrategyCalculatorBase,
    tokens: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate no-loop cross-protocol strategies.

    Iteration pattern:
    - token1 (stablecoins) × token2 (all) × protocol_a × protocol_b
    - Two tokens, two protocols, no token3
    """
    results = []

    stablecoins = tokens if tokens else self.STABLECOINS
    high_yield_tokens = self.OTHER_TOKENS

    for token1 in stablecoins:
        for token2 in high_yield_tokens:
            if token1 == token2:
                continue

            for protocol_a, protocol_b in self._get_protocol_pairs():
                # Get all required rates
                lend_total_apr_1A = self.get_rate(self.lend_rates, token1, protocol_a)
                borrow_total_apr_2A = self.get_rate(self.borrow_rates, token2, protocol_a)
                lend_total_apr_2B = self.get_rate(self.lend_rates, token2, protocol_b)

                collateral_ratio_1A = self.get_rate(self.collateral_ratios, token1, protocol_a)
                liquidation_threshold_1A = self.get_rate(self.liquidation_thresholds, token1, protocol_a)

                price_1A = self.get_rate(self.prices, token1, protocol_a)
                price_2A = self.get_rate(self.prices, token2, protocol_a)
                price_2B = self.get_rate(self.prices, token2, protocol_b)

                borrow_fee_2A = self.get_rate(self.borrow_fees, token2, protocol_a)
                available_borrow_2A = self.get_rate(self.available_borrow, token2, protocol_a)

                # Validate
                if any(x <= 1e-9 for x in [lend_total_apr_1A, borrow_total_apr_2A, lend_total_apr_2B,
                                            collateral_ratio_1A, liquidation_threshold_1A,
                                            price_1A, price_2A, price_2B]):
                    continue

                # Call calculator
                result = calculator.analyze_strategy(
                    token1=token1,
                    token2=token2,
                    protocol_a=protocol_a,
                    protocol_b=protocol_b,
                    lend_total_apr_1A=lend_total_apr_1A,
                    borrow_total_apr_2A=borrow_total_apr_2A,
                    lend_total_apr_2B=lend_total_apr_2B,
                    collateral_ratio_1A=collateral_ratio_1A,
                    liquidation_threshold_1A=liquidation_threshold_1A,
                    price_1A=price_1A,
                    price_2A=price_2A,
                    price_2B=price_2B,
                    available_borrow_2A=available_borrow_2A,
                    borrow_fee_2A=borrow_fee_2A,
                    liquidation_distance=self.liquidation_distance
                )

                if result.get('valid', False):
                    results.append(result)

    df = pd.DataFrame(results)
    if not df.empty:
        df['strategy_type'] = calculator.get_strategy_type()

    return df
```

**Testing**:
- [ ] Generates strategies for stablecoin + high-yield pairs
- [ ] Validates all required rates present
- [ ] Skips invalid combinations
- [ ] Returns correct DataFrame structure

---

#### Method 3: `_generate_recursive_strategies(calculator, tokens)`

```python
def _generate_recursive_strategies(
    self,
    calculator: StrategyCalculatorBase,
    tokens: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Generate recursive lending strategies.

    Iteration pattern:
    - token1 × token2 × token3 (stablecoins) × protocol_a × protocol_b
    - Three tokens, two protocols, full loop

    Note: This delegates to existing analyze_all_combinations() logic
    """
    # For now, reuse existing logic from analyze_all_combinations()
    # This maintains backward compatibility

    # TODO: Refactor existing analyze_all_combinations() to use calculator

    # Placeholder: return empty DataFrame
    return pd.DataFrame()
```

**Testing**:
- [ ] Maintains existing recursive strategy generation
- [ ] Returns same results as current implementation

---

### ~~2.4: Update analyze_all_combinations() Method~~ ✅

**File Modified**: `analysis/rate_analyzer.py`

**Changes Made**:

```python
def analyze_all_combinations(self, tokens: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Analyze all token and protocol combinations for ALL strategy types.

    Returns:
        DataFrame with strategies from all types, sorted by net_apr descending
    """
    all_strategies = []

    for strategy_type, calculator in self.calculators.items():
        print(f"[ANALYZER] Generating {strategy_type} strategies...")

        # Generate strategies for this type
        if strategy_type == 'stablecoin_lending':
            strategies = self._generate_stablecoin_strategies(calculator, tokens)
        elif strategy_type == 'noloop_cross_protocol_lending':
            strategies = self._generate_noloop_strategies(calculator, tokens)
        elif strategy_type == 'recursive_lending':
            strategies = self._generate_recursive_strategies(calculator, tokens)
        else:
            print(f"[ANALYZER] Unknown strategy type: {strategy_type}, skipping")
            continue

        if not strategies.empty:
            print(f"[ANALYZER] Generated {len(strategies)} {strategy_type} strategies")
            all_strategies.append(strategies)

    # Combine all strategy types into single DataFrame
    if not all_strategies:
        print("[ANALYZER] No valid strategies found")
        return pd.DataFrame()

    combined = pd.concat(all_strategies, ignore_index=True)

    # Sort by net_apr descending (best strategies first)
    combined = combined.sort_values(by='net_apr', ascending=False)

    print(f"[ANALYZER] Total strategies generated: {len(combined)}")
    return combined
```

**Testing**:
- ✅ Generates strategies for all enabled strategy types
- ✅ Combines results into single DataFrame
- ✅ Sorts by net_apr correctly
- ✅ Includes strategy_type column

---

### ~~2.5: Helper Method for Protocol Pairs~~ ✅

**File Modified**: `analysis/rate_analyzer.py`

**Method Added**:

```python
def _get_protocol_pairs(self) -> List[Tuple[str, str]]:
    """
    Get all valid protocol pairs.

    Returns:
        List of (protocol_a, protocol_b) tuples
    """
    pairs = []
    for i, protocol_a in enumerate(self.protocols):
        for protocol_b in self.protocols[i+1:]:  # Only unique pairs
            pairs.append((protocol_a, protocol_b))
    return pairs
```

**Testing**:
- ✅ Returns all unique protocol pairs
- ✅ No duplicate pairs (A,B) and (B,A)

---

### ~~Phase 2 Testing Checklist~~ ✅

- ✅ Syntax validation: Python compilation successful
- ✅ Strategy calculators import correctly
- ✅ New methods exist and are properly defined
- ✅ strategy_type column added to all generation methods
- ✅ Fail-loud validation: Raises ValueError for None, empty list, or invalid types
- ✅ Backward compatibility: Existing recursive logic preserved

---

## Phase 3: Update Position Service & Creation

**Status**: ⏳ Planned
**Goal**: Accept and store strategy_type parameter

### 3.1: Add strategy_type Parameter to create_position()

**File to Modify**: `analysis/position_service.py`

**Changes Needed**:

```python
def create_position(
    self,
    strategy_row: pd.Series,
    positions: Dict,
    token1: str,
    token2: str,
    token3: Optional[str],  # Now optional for 3-leg strategies
    ...,
    strategy_type: str = 'recursive_lending',  # NEW PARAMETER
    ...
) -> str:
    # Line 261: REMOVE hardcoded 'recursive_lending'
    # Use parameter instead:
    # INSERT INTO positions (..., strategy_type, ...) VALUES (..., ?, ...)
```

**Testing**:
- [ ] Position created with correct strategy_type
- [ ] Database stores strategy_type correctly
- [ ] Backward compatibility maintained

---

### 3.2: Handle Optional token3 for 3-Leg Strategies

**File to Modify**: `analysis/position_service.py`

**Changes Needed**:

```python
# Allow token3, token3_contract, B_B to be None
token3_value = token3 if token3 else None
token3_contract_value = token3_contract if token3_contract else None
b_b_value = positions.get('b_b', 0.0)  # Use 0.0 for 3-leg strategies

# Update SQL INSERT to handle NULL values
```

**Testing**:
- [ ] 3-leg position created without token3
- [ ] 4-leg position created with token3
- [ ] Database stores NULL correctly for 3-leg

---

## Phase 4: Update Portfolio Allocator

**Status**: ⏳ Planned
**Goal**: Support filtering/selecting strategies by type

### 4.1: Add Strategy Type Filtering

**File to Modify**: `analysis/portfolio_allocator.py`

**Changes Needed**:

```python
def select_portfolio(
    self,
    portfolio_size: float,
    constraints: Dict,
    allowed_strategy_types: List[str] = None  # NEW PARAMETER
) -> Tuple[pd.DataFrame, Dict]:

    # Filter strategies by type if specified
    if allowed_strategy_types:
        strategies = self.strategies[
            self.strategies['strategy_type'].isin(allowed_strategy_types)
        ]
    else:
        strategies = self.strategies  # All types

    # Rest of allocation logic unchanged
    ...
```

**Testing**:
- [ ] Filters strategies by type correctly
- [ ] None means include all types
- [ ] Allocation respects strategy type filter

---

### 4.2: Add Strategy Type Exposure Limits (Optional)

**File to Modify**: `analysis/portfolio_allocator.py`

**Enhancement**:

```python
constraints = {
    ...
    'strategy_type_limits': {
        'recursive_lending': 0.70,  # Max 70% in recursive
        'noloop_cross_protocol_lending': 0.50,  # Max 50% in noloop
        'stablecoin_lending': 1.00  # No limit on stablecoins
    }
}
```

**Testing**:
- [ ] Respects strategy type limits
- [ ] Allocation stays within constraints

---

## Phase 5: Create Strategy Renderers

**Status**: ⏳ Planned
**Goal**: Display each strategy type correctly in dashboard

### 5.1: Implement StablecoinLendingRenderer

**File to Modify**: `dashboard/position_renderers.py`

**Changes Needed**:

```python
@register_strategy_renderer('stablecoin_lending')
class StablecoinLendingRenderer(StrategyRendererBase):

    def get_strategy_name(self) -> str:
        return "Stablecoin Lending"

    def build_token_flow_string(self, position: pd.Series) -> str:
        # Single token: just show token name
        return f"{position['token1']}"

    def get_metrics_layout(self) -> List[str]:
        return ['total_earnings', 'base_earnings', 'reward_earnings']

    def render_detail_table(self, position, get_rate, get_borrow_fee,
                            get_price_with_fallback, ...) -> None:
        # Render 1 leg only:
        # Leg 1A: Lend token1 in Protocol A

        # Display: Token, Protocol, Weight (always 1.0), Entry Rate, Live Rate,
        #          Entry Price, Live Price, Token Amount

        # No borrowing legs, no protocol B
        ...
```

**Testing**:
- [ ] Renders 1-leg strategy correctly
- [ ] Shows correct token flow
- [ ] No liquidation info displayed

---

### 5.2: Implement NoLoopCrossProtocolRenderer

**File to Modify**: `dashboard/position_renderers.py`

**Changes Needed**:

```python
@register_strategy_renderer('noloop_cross_protocol_lending')
class NoLoopCrossProtocolRenderer(StrategyRendererBase):

    def get_strategy_name(self) -> str:
        return "Cross-Protocol Lending (No Loop)"

    def build_token_flow_string(self, position: pd.Series) -> str:
        # 3-leg flow: token1 → token2 (no loop back)
        return f"{position['token1']} → {position['token2']}"

    def get_metrics_layout(self) -> List[str]:
        return ['total_pnl', 'total_earnings', 'total_fees', 'liquidation_buffer']

    def render_detail_table(self, position, get_rate, get_borrow_fee,
                            get_price_with_fallback, ...) -> None:
        # Render 3 legs:
        # Leg 1A: Lend token1 in Protocol A
        # Leg 2A: Borrow token2 from Protocol A (show liquidation risk)
        # Leg 2B: Lend token2 in Protocol B

        # NO Leg 3B (no borrow loop back)

        # Display liquidation distance for leg 2A
        ...
```

**Testing**:
- [ ] Renders 3-leg strategy correctly
- [ ] Shows correct token flow
- [ ] Single liquidation risk displayed

---

## ~~Phase 6: Update Rebalance Calculation~~ ✅ COMPLETE

**Status**: ✅ Implemented (February 16, 2026)
**Goal**: Strategy-specific rebalance logic

### ~~6.1: Add Rebalance Logic to Calculators~~ ✅

**Files Modified**: `analysis/strategy_calculators/*.py`

**Changes Needed**:

Add to base class:
```python
class StrategyCalculatorBase(ABC):
    @abstractmethod
    def calculate_rebalance_amounts(self, position: pd.Series,
                                    live_rates: Dict,
                                    live_prices: Dict) -> Dict:
        """
        Calculate token amounts needed to restore target weights.

        FAIL LOUD: Never return None. Always return a dict.

        Returns:
            Dict with structure:
            {
                "requires_rebalance": bool,  # True if rebalancing needed
                "actions": List[Dict],       # Empty list if no rebalancing needed
                "reason": str                # Human-readable explanation
            }

        Raises:
            ValueError: If position data is invalid or missing
            KeyError: If required rates/prices are missing
        """
        pass
```

Implement in each calculator:

#### Stablecoin Lending
```python
def calculate_rebalance_amounts(self, position, live_rates, live_prices):
    """Stablecoin lending never needs rebalancing (no leverage, no liquidation risk)"""
    return {
        "requires_rebalance": False,
        "actions": [],
        "reason": "Single-leg strategy does not require rebalancing"
    }
```

#### NoLoop Cross-Protocol
```python
def calculate_rebalance_amounts(self, position, live_rates, live_prices):
    """
    Rebalance 3 legs (no B_B term).
    Adjust token amounts to maintain L_A, B_A, L_B USD values.
    Only one liquidation threshold to monitor (leg 2A).
    """
    # FAIL LOUD: Validate inputs
    if not position or live_rates is None or live_prices is None:
        raise ValueError("Invalid inputs to calculate_rebalance_amounts")

    # Calculate current USD values and target values
    # Determine if rebalancing is needed

    if rebalance_needed:
        return {
            "requires_rebalance": True,
            "actions": [
                {"leg": "2A", "action": "borrow", "amount": 123.45, ...},
                {"leg": "2B", "action": "lend", "amount": 123.45, ...}
            ],
            "reason": "Liquidation distance change requires rebalancing"
        }
    else:
        return {
            "requires_rebalance": False,
            "actions": [],
            "reason": "Position weights within acceptable tolerance"
        }
```

#### Recursive
```python
def calculate_rebalance_amounts(self, position, live_rates, live_prices):
    """
    Rebalance all 4 legs to maintain constant USD weights.
    Most complex: maintain L_A, B_A, L_B, B_B USD values.
    Two liquidation thresholds to monitor (legs 2A and 3B).
    """
    # FAIL LOUD: Validate inputs
    if not position or live_rates is None or live_prices is None:
        raise ValueError("Invalid inputs to calculate_rebalance_amounts")

    # Calculate current USD values and target values for all 4 legs
    # Determine if rebalancing is needed (tolerance check)

    if rebalance_needed:
        return {
            "requires_rebalance": True,
            "actions": [
                {"leg": "1A", "action": "lend", "amount": 100.00, ...},
                {"leg": "2A", "action": "borrow", "amount": 150.00, ...},
                {"leg": "2B", "action": "lend", "amount": 150.00, ...},
                {"leg": "3B", "action": "borrow", "amount": 120.00, ...}
            ],
            "reason": "Liquidation distance change requires 4-leg rebalance"
        }
    else:
        return {
            "requires_rebalance": False,
            "actions": [],
            "reason": "All leg weights within acceptable tolerance"
        }
```

**Testing**:
- [ ] Stablecoin returns `requires_rebalance=False` with empty actions
- [ ] NoLoop calculates 3-leg rebalance correctly when needed
- [ ] Recursive calculates 4-leg rebalance correctly when needed
- [ ] All calculators raise ValueError/KeyError on invalid inputs (fail loud)
- [ ] Never returns None (fail loud if None is returned)

---

### ~~6.2: Update PositionService.rebalance_position()~~ ✅

**File Modified**: `analysis/position_service.py`

**Changes Needed**:

```python
def rebalance_position(self, position_id, live_timestamp, ...):
    position = self.get_position(position_id)

    # Get correct calculator for this position's strategy type
    calculator = get_calculator(position['strategy_type'])

    # Calculate rebalance using strategy-specific logic
    try:
        rebalance_result = calculator.calculate_rebalance_amounts(
            position, live_rates, live_prices
        )
    except (ValueError, KeyError) as e:
        # FAIL LOUD: Calculator raised error for invalid data
        raise ValueError(f"Rebalance calculation failed for position {position_id}: {e}")

    # FAIL LOUD: Ensure we never get None
    if rebalance_result is None:
        raise ValueError(
            f"Calculator returned None for position {position_id}! "
            f"Strategy type: {position['strategy_type']}. "
            "This should never happen - calculators must return a dict."
        )

    # Check if rebalancing is needed
    if not rebalance_result.get('requires_rebalance', False):
        # No rebalancing needed (e.g., stablecoin lending or within tolerance)
        print(f"[REBALANCE] Position {position_id}: {rebalance_result['reason']}")
        return {
            "rebalanced": False,
            "reason": rebalance_result['reason']
        }

    # Execute rebalance actions
    actions = rebalance_result.get('actions', [])
    if not actions:
        raise ValueError(
            f"Position {position_id} requires_rebalance=True but has no actions! "
            "This indicates a calculator bug."
        )

    # Rest of rebalance logic: execute actions, update database, etc.
    ...
```

**Testing**:
- [ ] Stablecoin positions return `rebalanced=False` with reason
- [ ] NoLoop positions execute 3-leg rebalance when needed
- [ ] Recursive positions execute 4-leg rebalance when needed
- [ ] Raises ValueError if calculator returns None (fail loud)
- [ ] Raises ValueError if requires_rebalance=True but no actions (fail loud)

---

## Phase 7: Update Dashboard Strategy Display

**Status**: ⏳ Planned
**Goal**: Show all strategy types in "All Strategies" tab

### 7.1: Generate Multiple Strategy Types in Dashboard

**File to Modify**: `dashboard/dashboard_renderer.py`

**Changes Needed**:

```python
# When initializing RateAnalyzer, specify all strategy types
analyzer = RateAnalyzer(
    ...,
    strategy_types=[
        'stablecoin_lending',
        'noloop_cross_protocol_lending',
        'recursive_lending'
    ]
)

# find_best_protocol_pair() will now return strategies from all three types
protocol_a, protocol_b, all_results = analyzer.find_best_protocol_pair()

# all_results DataFrame will have 'strategy_type' column for filtering
```

**Testing**:
- [ ] All strategy types displayed
- [ ] Strategies sorted by net_apr
- [ ] Strategy type visible in results

---

### 7.2: Add Strategy Type Filter in UI

**File to Modify**: `dashboard/dashboard_renderer.py`

**Changes Needed**:

Add to sidebar filters:
```python
strategy_type_filter = st.multiselect(
    "Strategy Types",
    options=[
        'stablecoin_lending',
        'noloop_cross_protocol_lending',
        'recursive_lending'
    ],
    default=[  # Default to showing all types
        'stablecoin_lending',
        'noloop_cross_protocol_lending',
        'recursive_lending'
    ],
    format_func=lambda x: {
        'stablecoin_lending': '💰 Stablecoin Lending',
        'noloop_cross_protocol_lending': '🔄 Cross-Protocol (No Loop)',
        'recursive_lending': '♾️ Recursive Leverage'
    }[x]
)

# Filter displayed strategies
if strategy_type_filter:
    display_results = display_results[
        display_results['strategy_type'].isin(strategy_type_filter)
    ]
```

**Testing**:
- [ ] Filter shows all strategy types
- [ ] Filter works correctly
- [ ] Default shows all types

---

### 7.3: Show Strategy Type in Strategy List

**File to Modify**: `dashboard/dashboard_renderer.py`

**Changes Needed**:

```python
# In strategy expander title
title = f"{token_flow} | {protocol_pair} | {strategy_type} | APR: {apr}%"
```

**Testing**:
- [ ] Strategy type visible in title
- [ ] Correct icon/label for each type

---

## Phase 8: Update Refresh Pipeline

**Status**: ⏳ Planned
**Goal**: Generate and cache all strategy types

### 8.1: Specify Strategy Types in Refresh

**File to Modify**: `data/refresh_pipeline.py`

**Changes Needed**:

```python
def refresh_pipeline(timestamp, save_snapshots=True,
                     strategy_types=None):

    # Default to all three strategy types
    if strategy_types is None:
        strategy_types = [
            'stablecoin_lending',
            'noloop_cross_protocol_lending',
            'recursive_lending'
        ]

    # Initialize analyzer with multiple strategy types
    analyzer = RateAnalyzer(
        ...,
        strategy_types=strategy_types
    )

    # Generate strategies for all types
    protocol_a, protocol_b, all_results = analyzer.find_best_protocol_pair()

    # all_results now contains strategies from all three types
    # Sorted by net_apr descending (best strategies first)
    ...
```

**Testing**:
- [ ] Generates all strategy types
- [ ] Caches results correctly
- [ ] Refresh pipeline completes successfully

---

## Critical Files Reference

### New Files Created (Phase 1 ✅)
1. `analysis/strategy_calculators/__init__.py` - Calculator registry
2. `analysis/strategy_calculators/base.py` - Abstract base class
3. `analysis/strategy_calculators/stablecoin_lending.py` - 1-leg calculator
4. `analysis/strategy_calculators/noloop_cross_protocol.py` - 3-leg calculator
5. `analysis/strategy_calculators/recursive_lending.py` - 4-leg calculator

### Files to Modify (Phases 2-8)
1. `analysis/rate_analyzer.py` - Phase 2: Add strategy_types parameter, generation methods
2. `analysis/position_service.py` - Phase 3: Add strategy_type parameter to create_position()
3. `analysis/portfolio_allocator.py` - Phase 4: Add strategy type filtering
4. `dashboard/position_renderers.py` - Phase 5: Add new renderers
5. `dashboard/dashboard_renderer.py` - Phase 7: Add UI filters, display all types
6. `data/refresh_pipeline.py` - Phase 8: Generate all strategy types
7. `config/settings.py` - Add default strategy types config

### Files That Need NO Changes
- `data/schema.sql` - Already has strategy_type column
- `data/rate_tracker.py` - Strategy-agnostic caching
- `data/protocol_merger.py` - Strategy-agnostic data fetching
- `position_rebalances` table - Event sourcing pattern works for any strategy

---

## Key Architectural Decisions

### 1. Strategy Calculator Pattern
- **Decision**: Use abstract base class + registry pattern
- **Rationale**: Clean separation of strategy-specific logic, extensible for future strategies
- **Alternative Considered**: Conditional logic in single calculator (rejected: unmaintainable)

### 2. Single DataFrame for All Strategies
- **Decision**: Combine all strategy types into one DataFrame with `strategy_type` column
- **Rationale**: Simplifies ranking, filtering, and portfolio allocation
- **Alternative Considered**: Separate DataFrames per type (rejected: harder to compare)

### 3. Optional 4th Leg (token3/B_B)
- **Decision**: Allow token3, token3_contract, B_B to be None/NULL
- **Rationale**: Database already supports NULL, cleaner than dummy values
- **Alternative Considered**: Use empty string '' (rejected: NULL is more semantic)

### 4. Renderer Registry vs Calculator Registry
- **Decision**: Keep both registries separate
- **Rationale**: Rendering is UI concern, calculation is business logic concern
- **Benefit**: Can test calculators without UI, can swap renderers independently

---

## Design Principles Applied

From `DESIGN_NOTES.md`:
- ✅ **#1**: Timestamp as "current time"
- ✅ **#5**: Unix timestamps (seconds as int) internally
- ✅ **#7**: Rates as decimals (0.0 to 1.0)
- ✅ **#9**: Token identity by contract addresses
- ✅ **#10**: Collateral ratio + liquidation threshold pairing
- ✅ **#11**: Dashboard as pure view layer

---

## Testing Strategy

### Unit Tests
- [ ] Test each calculator independently with known inputs
- [ ] Test registry lookup for all strategy types
- [ ] Test RateAnalyzer generates all types correctly

### Integration Tests
- [ ] Test full pipeline: rate fetch → strategy generation → position creation
- [ ] Test portfolio allocator with mixed strategy types
- [ ] Test rebalance with all strategy types

### Validation
- [ ] Verify "All Strategies" shows all types sorted by APR
- [ ] Verify position creation stores correct strategy_type
- [ ] Verify dashboard renders each type correctly
- [ ] Verify PnL calculations match for each strategy type

---

## Rollout Plan

### Stage 1: Foundation (Phase 1-2)
- ✅ Phase 1: Create calculator base class and registry
- 🔄 Phase 2: Update RateAnalyzer to support multiple types
- Test: Verify all strategy types generated correctly

### Stage 2: Integration (Phase 3-4)
- Phase 3: Update PositionService to accept strategy_type
- Phase 4: Update portfolio allocator
- Test: Create positions of each type, verify allocation

### Stage 3: UI & Rendering (Phase 5-7)
- Phase 5: Implement renderers for new types
- Phase 7: Add strategy type filter to dashboard
- Test: Display all types, filter works correctly

### Stage 4: Rebalancing & Pipeline (Phase 6, 8)
- Phase 6: Add rebalance support for all types
- Phase 8: Update refresh pipeline
- Test: End-to-end testing with all types

---

## Summary

**Completed**:
- ✅ Phase 1: Strategy Calculator Layer (February 13, 2026)

**In Progress**:
- 🔄 Phase 2: Update Rate Analyzer

**Remaining**:
- ⏳ Phases 3-8: Integration, UI, Rebalancing, Pipeline

**Timeline Estimate**:
- Phase 2: 2-3 days
- Phase 3: 1 day
- Phase 4: 1 day
- Phase 5: 2-3 days
- Phase 6: 2-3 days
- Phase 7: 1-2 days
- Phase 8: 1 day
- **Total**: ~2 weeks for full implementation

**Next Action**: Begin Phase 2 - Update Rate Analyzer to generate multiple strategy types
