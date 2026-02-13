# Plan: Add Multi-Strategy Support (3 Strategy Types)

## Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ **COMPLETE** | Strategy Calculator Layer - Created base class, 3 calculators, and registry |
| **Phase 2** | ⏳ Planned | Update Rate Analyzer to support multiple strategy types |
| **Phase 3** | ⏳ Planned | Update Position Service & Creation |
| **Phase 4** | ⏳ Planned | Update Portfolio Allocator |
| **Phase 5** | ⏳ Planned | Create Strategy Renderers |
| **Phase 6** | ⏳ Planned | Update Rebalance Calculation |
| **Phase 7** | ⏳ Planned | Update Dashboard Strategy Display |
| **Phase 8** | ⏳ Planned | Update Refresh Pipeline |

**Last Updated**: February 2026
**Current Phase**: Phase 1 Complete, Ready for Phase 2

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

## Visual Flow Diagrams

### STABLECOIN_LENDING (1-Leg)
```
┌─────────────┐
│   User $    │
│  (Deploy)   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   Protocol A        │
│  Lend USDC @ 4%     │
│   (L_A = 1.0)       │
└─────────────────────┘

Flow: User → Lend USDC → Earn Rate
Risk: Protocol risk only
```

### NOLOOP_CROSS_PROTOCOL_LENDING (3-Leg)
```
┌─────────────┐
│   User $    │
│  (Deploy)   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   Protocol A        │
│  Lend USDC @ 3%     │◄─┐ (Token1 as collateral)
│   (L_A = 1.0)       │  │
├─────────────────────┤  │
│ Borrow DEEP @ 8%    │──┘ (Liquidation risk here!)
│   (B_A = 0.67)      │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│   Protocol B        │
│  Lend DEEP @ 12%    │
│   (L_B = 0.67)      │
└─────────────────────┘

Flow: Lend USDC → Borrow DEEP → Lend DEEP
Risk: DEEP price exposure + liquidation on leg 2A
```

### RECURSIVE_LENDING (4-Leg)
```
┌─────────────┐
│   User $    │
│  (Deploy)   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│   Protocol A        │
│  Lend USDC @ 3%     │◄─┐ (Recursive loop!)
│   (L_A = 2.5)       │  │
├─────────────────────┤  │
│ Borrow DEEP @ 8%    │──┘ (Liquidation risk #1)
│   (B_A = 1.5)       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│   Protocol B        │
│  Lend DEEP @ 12%    │◄─┐ (Collateral for token3)
│   (L_B = 1.5)       │  │
├─────────────────────┤  │
│ Borrow USDY @ 5%    │──┘ (Liquidation risk #2)
│   (B_B = 1.0)       │
└──────┬──────────────┘
       │
       ▼ (Convert USDY → USDC at 1:1)
       │
       └──────────────► Loops back to Protocol A

Flow: Lend USDC → Borrow DEEP → Lend DEEP → Borrow USDY → Convert → Loop
Risk: Market neutral (USDC = USDY), but dual liquidation risks
APR: Highest due to recursive leverage multiplier
```

---

## Architectural Analysis: What's Already Ready?

### ✅ Already Supports Multi-Strategy:

1. **Database Schema** (`data/schema.sql`):
   - `positions.strategy_type` column already exists (defaults to 'recursive_lending')
   - No changes needed - ready to accept new strategy types

2. **Rendering System** (`dashboard/position_renderers.py`):
   - Has registry pattern with `@register_strategy_renderer()` decorator
   - `RecursiveLendingRenderer` fully implemented
   - `FundRateArbRenderer` stub exists as example
   - System automatically routes to correct renderer based on `position.strategy_type`

3. **Rate Data Pipeline** (`data/refresh_pipeline.py`):
   - Fetches all protocol rates/prices/liquidity in unified format
   - No strategy-specific logic - reusable for any strategy type

4. **Rebalance Tracking** (`data/schema.sql`):
   - `position_rebalances` table is strategy-agnostic (event sourcing pattern)
   - Stores opening/closing state for any number of legs
   - No schema changes needed

### ❌ Currently Hardcoded to RECURSIVE_LENDING:

1. **Strategy Generation** (`analysis/rate_analyzer.py`):
   - Only generates 4-leg recursive strategies
   - Hardcoded to analyze token1 → token2 → token3 flow

2. **Position Calculation** (`analysis/position_calculator.py`):
   - `calculate_positions()` uses recursive leverage formula
   - `analyze_strategy()` expects 4 legs (L_A, B_A, L_B, B_B)

3. **Position Creation** (`analysis/position_service.py:261`):
   - Hardcoded: `strategy_type = 'recursive_lending'`
   - No parameter to specify different strategy type

4. **Portfolio Allocator** (`analysis/portfolio_allocator.py`):
   - Assumes all strategies are same type
   - No filtering by strategy type

---

## Implementation Plan

### Phase 1: Refactor Strategy Calculation Layer (Foundation) ✅ COMPLETE

**Status**: ✅ Implemented and tested
**Date**: February 2026
**Files Created**: 5 new files in `analysis/strategy_calculators/`

**What Was Built**:
1. `base.py` - Abstract base class defining calculator interface
2. `stablecoin_lending.py` - 1-leg calculator (simplest strategy)
3. `noloop_cross_protocol.py` - 3-leg calculator (moderate complexity)
4. `recursive_lending.py` - 4-leg calculator (extracted from existing code)
5. `__init__.py` - Registry with auto-registration

**Validation**:
- ✅ All 3 calculators registered successfully
- ✅ Correct leg counts: stablecoin=1, noloop=3, recursive=4
- ✅ Position calculations working correctly
- ✅ Data validation (fail fast on missing data, log warnings for nullable fields)
- ✅ Uses float('inf') for unbounded values
- ✅ Uses 0.0 (not None) for unused legs (b_b)

**Key Design Decisions Implemented**:
- ✅ Use total APRs (base + reward already combined from database)
- ✅ Explicit validation: raise errors for critical missing rates
- ✅ Log warnings for nullable borrow fees with 0.0 fallback
- ✅ max_size = inf for stablecoin lending (no supply cap tracking yet)
- ✅ liquidation_distance = inf for stablecoin (no liquidation risk)

**Files Created**:
```
analysis/strategy_calculators/
├── __init__.py                  (115 lines) - Registry + auto-registration
├── base.py                      (91 lines)  - Abstract base class
├── stablecoin_lending.py        (163 lines) - 1-leg calculator
├── noloop_cross_protocol.py     (291 lines) - 3-leg calculator
└── recursive_lending.py         (381 lines) - 4-leg calculator
```

**Test Output**:
```
✅ Registered strategy types: ['stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending']
✅ stablecoin_lending: 1 legs
✅ noloop_cross_protocol_lending: 3 legs
✅ recursive_lending: 4 legs
✅ Stablecoin lending positions correct
✅ All Phase 1 tests passed!
```

**Next Steps**: Phase 2 - Update RateAnalyzer to use calculator registry and generate strategies for all three types.

---

### Phase 1: Refactor Strategy Calculation Layer (Foundation) [ORIGINAL SPEC]

**Goal**: Abstract strategy-specific calculations into pluggable calculators

#### 1.1 Create Abstract Strategy Calculator Base Class

**New File**: `analysis/strategy_calculators/base.py`

```python
class StrategyCalculatorBase(ABC):
    """Base class for strategy-specific calculations"""

    @abstractmethod
    def get_strategy_type(self) -> str:
        """Returns strategy type identifier (e.g., 'recursive_lending')"""
        pass

    @abstractmethod
    def calculate_positions(self, ...) -> Dict[str, float]:
        """Calculate position multipliers/weights for this strategy"""
        pass

    @abstractmethod
    def calculate_net_apr(self, positions: Dict, rates: Dict, fees: Dict) -> float:
        """Calculate net APR for this strategy"""
        pass

    @abstractmethod
    def analyze_strategy(self, token_combo: Dict, protocol_pair: Tuple,
                         market_data: Dict) -> Dict:
        """Complete strategy analysis returning all metrics"""
        pass

    @abstractmethod
    def get_required_legs(self) -> int:
        """Returns number of legs (3 for unlevered, 4 for recursive)"""
        pass
```

#### 1.2 Move Recursive Lending Logic to Calculator

**New File**: `analysis/strategy_calculators/recursive_lending.py`

Extract existing logic from `position_calculator.py` into:

```python
class RecursiveLendingCalculator(StrategyCalculatorBase):
    def get_strategy_type(self) -> str:
        return 'recursive_lending'

    def get_required_legs(self) -> int:
        return 4  # 4-leg strategy

    # Move existing calculate_positions(), calculate_net_apr(),
    # analyze_strategy() logic here
```

**Files Modified**:
- `analysis/position_calculator.py` - Keep as facade/utility, delegate to calculators

#### 1.3 Create Stablecoin Lending Calculator

**New File**: `analysis/strategy_calculators/stablecoin_lending.py`

```python
class StablecoinLendingCalculator(StrategyCalculatorBase):
    def get_strategy_type(self) -> str:
        return 'stablecoin_lending'

    def get_required_legs(self) -> int:
        return 1  # Single lending leg

    def calculate_positions(self, ...) -> Dict[str, float]:
        # Simplest calculation: just lend
        return {
            'l_a': 1.0,      # Lend $1 for every $1 deployed
            'b_a': 0.0,      # No borrowing
            'l_b': 0.0,      # No second lending
            'b_b': 0.0       # No second borrowing (consistent with b_a/l_b)
        }

    def calculate_net_apr(self, positions, rates, fees) -> float:
        # APR = lend_total_apr (which includes base + reward)
        # rates['lend_total_apr_1A'] already contains base + reward from database
        # No borrowing costs, no fees

        lend_total_apr = rates['lend_total_apr_1A']

        # Validate data quality - warn if missing
        if lend_total_apr is None:
            raise ValueError(f"Missing lend_total_apr for token1 in protocol_A")

        return lend_total_apr

    def analyze_strategy(self, token1, protocol_a, market_data) -> Dict:
        """
        Analyze stablecoin lending strategy.

        Args:
            token1: Stablecoin symbol (e.g., 'USDC')
            protocol_a: Protocol name (e.g., 'navi')
            market_data: Dict with keys:
                - lend_total_apr_1A: Total lending APR (base + reward)
                - price_1A: Token price
                - ... other protocol data

        Returns:
            Strategy dict with all required fields
        """
        return {
            'l_a': 1.0,
            'b_a': 0.0,
            'l_b': 0.0,
            'b_b': 0.0,
            'net_apr': market_data['lend_total_apr_1A'],
            'liquidation_distance': float('inf'),  # No liquidation risk
            'max_size': float('inf'),  # Not limited by liquidity constraints
            'valid': True,
            # Note: We don't track lending supply caps in the database
            # Only borrow liquidity limits (available_borrow_usd)
        }
```

**Key Characteristics**:
- Simplest strategy: single token, single protocol
- No borrowing, no leverage, no liquidation risk
- No rebalancing needed
- APR = total lending rate (base + reward already combined in database)

**Data Validation**:
- Raises error if `lend_total_apr` is missing (prefer explicit failure over silent 0)
- Uses `float('inf')` for unbounded values (clearer than `None`)
- `max_size = inf` because we don't track lending supply caps

---

#### 1.4 Create NoLoop Cross-Protocol Calculator

**New File**: `analysis/strategy_calculators/noloop_cross_protocol.py`

```python
import logging

logger = logging.getLogger(__name__)

class NoLoopCrossProtocolCalculator(StrategyCalculatorBase):
    def get_strategy_type(self) -> str:
        return 'noloop_cross_protocol_lending'

    def get_required_legs(self) -> int:
        return 3  # 3-leg strategy (no loop back)

    def calculate_positions(self, liquidation_threshold_a,
                           collateral_ratio_a,
                           liquidation_distance=0.20) -> Dict[str, float]:
        """
        Calculate position multipliers for no-loop cross-protocol strategy.

        Args:
            liquidation_threshold_a: LTV at which liquidation occurs (e.g., 0.80)
            collateral_ratio_a: Max collateral factor (e.g., 0.75)
            liquidation_distance: Safety buffer (default 0.20 = 20%)

        Returns:
            Dict with l_a, b_a, l_b, b_b multipliers
        """
        # No recursive leverage - linear calculation
        l_a = 1.0

        # Borrow up to liquidation_threshold with safety buffer
        # Example: liq_threshold=0.80, liq_dist=0.20 → borrow 0.80/1.20 = 66.7%
        r_a = liquidation_threshold_a / (1.0 + liquidation_distance)

        # Use minimum of calculated ratio and collateral factor
        # (Collateral factor is typically lower than liquidation threshold)
        b_a = l_a * min(r_a, collateral_ratio_a)

        # Lend all borrowed tokens in protocol B
        l_b = b_a

        return {
            'l_a': l_a,
            'b_a': b_a,
            'l_b': l_b,
            'b_b': 0.0  # No 4th leg - no loop back (use 0 not None for consistency)
        }

    def calculate_net_apr(self, positions, rates, fees) -> float:
        """
        Calculate net APR for no-loop cross-protocol strategy.

        APR = (L_A × lend_total_apr_1A) + (L_B × lend_total_apr_2B)
              - (B_A × borrow_total_apr_2A) - (B_A × borrow_fee_2A)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_1A, lend_total_apr_2B, borrow_total_apr_2A
            fees: Dict with borrow_fee_2A

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        # Use total APRs (base + reward already combined)
        lend_total_1A = rates['lend_total_apr_1A']
        lend_total_2B = rates['lend_total_apr_2B']
        borrow_total_2A = rates['borrow_total_apr_2A']

        # Validate critical rates are present
        if lend_total_1A is None:
            raise ValueError(f"Missing lend_total_apr_1A")
        if lend_total_2B is None:
            raise ValueError(f"Missing lend_total_apr_2B")
        if borrow_total_2A is None:
            raise ValueError(f"Missing borrow_total_apr_2A")

        # Calculate earnings and costs
        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        # Borrow fees - use .get() with 0.0 fallback since it's nullable in DB
        # But log warning if missing so we know about data quality issues
        borrow_fee_2A = fees.get('borrow_fee_2A', None)
        if borrow_fee_2A is None:
            logger.warning(f"Missing borrow_fee_2A, assuming 0.0")
            borrow_fee_2A = 0.0

        fees_cost = b_a * borrow_fee_2A

        return earnings - costs - fees_cost
```

**Key Differences from Recursive**:
- No geometric series (linear calculation: `b_a = l_a × ratio`)
- No 4th leg (`b_b = 0.0` not `None` for consistency)
- Simpler APR calculation (3 legs instead of 4)
- Still has liquidation risk (on leg 2A only)

**Data Validation**:
- Raises errors for missing critical rates (fail fast)
- Logs warnings for missing borrow fees but continues with 0.0 fallback
- Uses `lend_total_apr` and `borrow_total_apr` (base + reward already combined)

#### 1.5 Create Calculator Registry

**New File**: `analysis/strategy_calculators/__init__.py`

```python
from typing import Dict
from .base import StrategyCalculatorBase
from .stablecoin_lending import StablecoinLendingCalculator
from .noloop_cross_protocol import NoLoopCrossProtocolCalculator
from .recursive_lending import RecursiveLendingCalculator

_CALCULATORS: Dict[str, StrategyCalculatorBase] = {}

def register_calculator(calculator_class: type):
    """Register a calculator class"""
    calc = calculator_class()
    _CALCULATORS[calc.get_strategy_type()] = calc

def get_calculator(strategy_type: str) -> StrategyCalculatorBase:
    """Get calculator by strategy type"""
    if strategy_type not in _CALCULATORS:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    return _CALCULATORS[strategy_type]

def get_all_strategy_types() -> List[str]:
    """Get list of all registered strategy types"""
    return list(_CALCULATORS.keys())

# Auto-register built-in calculators
register_calculator(StablecoinLendingCalculator)
register_calculator(NoLoopCrossProtocolCalculator)
register_calculator(RecursiveLendingCalculator)
```

---

### Phase 2: Update Strategy Generation (Rate Analyzer)

**Goal**: Generate strategies for multiple types in one pass

#### 2.1 Modify RateAnalyzer to Support Multiple Strategy Types

**File Modified**: `analysis/rate_analyzer.py`

```python
class RateAnalyzer:
    def __init__(self, ..., strategy_types: List[str] = None):
        # Default to all strategy types if not specified
        self.strategy_types = strategy_types or [
            'stablecoin_lending',
            'noloop_cross_protocol_lending',
            'recursive_lending'
        ]
        # Load calculators for each strategy type
        self.calculators = {
            st: get_calculator(st) for st in self.strategy_types
        }

    def analyze_all_combinations(self, tokens=None) -> pd.DataFrame:
        all_strategies = []

        for strategy_type, calculator in self.calculators.items():
            # Generate strategies for this type
            strategies = self._analyze_combinations_for_strategy(
                calculator, tokens
            )
            all_strategies.append(strategies)

        # Combine all strategy types into single DataFrame
        combined = pd.concat(all_strategies, ignore_index=True)

        # Sort by net_apr descending (best strategies first)
        return combined.sort_values(by='net_apr', ascending=False)

    def _analyze_combinations_for_strategy(self,
                                           calculator: StrategyCalculatorBase,
                                           tokens) -> pd.DataFrame:
        """
        Generate strategies for a specific strategy type.

        For STABLECOIN_LENDING:
          - Iterate: token1 (stablecoins only) × protocol_a
          - Single token, single protocol

        For NOLOOP_CROSS_PROTOCOL_LENDING:
          - Iterate: token1 (stablecoins) × token2 (all) × protocol_a × protocol_b
          - Two tokens, two protocols, no token3

        For RECURSIVE_LENDING:
          - Iterate: token1 × token2 × token3 (stablecoins) × protocol_a × protocol_b
          - Three tokens, two protocols, full loop
        """
        strategy_type = calculator.get_strategy_type()

        if strategy_type == 'stablecoin_lending':
            return self._generate_stablecoin_strategies(calculator, tokens)
        elif strategy_type == 'noloop_cross_protocol_lending':
            return self._generate_noloop_strategies(calculator, tokens)
        elif strategy_type == 'recursive_lending':
            return self._generate_recursive_strategies(calculator, tokens)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
```

**Key Changes**:
- Accept `strategy_types` parameter in constructor
- Loop through each strategy type and generate strategies
- Use calculator registry to get correct calculator
- Combine all strategies into single DataFrame with `strategy_type` column

#### 2.2 Add Strategy Type Column to Results

All strategy result DataFrames should include:
```python
df_results['strategy_type'] = calculator.get_strategy_type()
```

---

### Phase 3: Update Position Service & Creation

**Goal**: Accept and store strategy_type parameter

#### 3.1 Add strategy_type Parameter to create_position()

**File Modified**: `analysis/position_service.py`

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
    position_id, 'active', strategy_type,  # <-- Use parameter
    ...
```

**Key Changes**:
- Add `strategy_type` parameter with default
- Pass through to database INSERT
- Validate strategy_type against registry

#### 3.2 Handle Optional token3 for 3-Leg Strategies

**File Modified**: `analysis/position_service.py`

```python
# Allow token3, token3_contract, B_B to be None
token3_contract_value = token3_contract or 'NULL'
b_b_value = positions.get('b_b', None)

# Update SQL to handle NULL values correctly
```

---

### Phase 4: Update Portfolio Allocator

**Goal**: Support filtering/selecting strategies by type

#### 4.1 Add Strategy Type Filtering

**File Modified**: `analysis/portfolio_allocator.py`

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

#### 4.2 Add Strategy Type Exposure Limits

**Optional Enhancement** - Add to constraints:
```python
constraints = {
    ...
    'strategy_type_limits': {
        'recursive_lending': 0.70,  # Max 70% in recursive
        'unlevered_lending': 0.50   # Max 50% in unlevered
    }
}
```

---

### Phase 5: Create Strategy Renderers

**Goal**: Display each strategy type correctly in dashboard

#### 5.1 Implement StablecoinLendingRenderer

**File Modified**: `dashboard/position_renderers.py`

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

**Key Characteristics**:
- Token flow: Just token name (e.g., "USDC")
- Single row in detail table
- No liquidation info (no risk)
- Simplest display

---

#### 5.2 Implement NoLoopCrossProtocolRenderer

**File Modified**: `dashboard/position_renderers.py`

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

**Key Differences from Recursive**:
- Token flow: `token1 → token2` (no closing leg)
- Only 3 rows in detail table
- Single liquidation risk indicator (leg 2A only)
- No `b_b` multiplier displayed

---

### Phase 6: Update Rebalance Calculation

**Goal**: Strategy-specific rebalance logic

#### 6.1 Add Rebalance Logic to Calculators

**Files Modified**: `analysis/strategy_calculators/*.py`

Add to base class:
```python
class StrategyCalculatorBase(ABC):
    @abstractmethod
    def calculate_rebalance_amounts(self, position: pd.Series,
                                    live_rates: Dict,
                                    live_prices: Dict) -> Dict:
        """Calculate token amounts needed to restore target weights"""
        pass
```

Implement in each calculator:
- **Stablecoin Lending**: No rebalancing needed (no borrowed assets)
  ```python
  def calculate_rebalance_amounts(self, position, live_rates, live_prices):
      return None  # No rebalancing for single-leg strategy
  ```
- **NoLoop Cross-Protocol**: Rebalance 3 legs (no B_B term)
  - Adjust token amounts to maintain L_A, B_A, L_B USD values
  - Only one liquidation threshold to monitor (leg 2A)
- **Recursive**: Rebalance all 4 legs to maintain constant USD weights
  - Most complex: maintain L_A, B_A, L_B, B_B USD values
  - Two liquidation thresholds to monitor (legs 2A and 3B)

#### 6.2 Update PositionService.rebalance_position()

**File Modified**: `analysis/position_service.py`

```python
def rebalance_position(self, position_id, live_timestamp, ...):
    position = self.get_position(position_id)

    # Get correct calculator for this position's strategy type
    calculator = get_calculator(position['strategy_type'])

    # Calculate rebalance using strategy-specific logic
    rebalance_amounts = calculator.calculate_rebalance_amounts(
        position, live_rates, live_prices
    )

    # Rest of rebalance logic unchanged
    ...
```

---

### Phase 7: Update Dashboard Strategy Display

**Goal**: Show both strategy types in "All Strategies" tab

#### 7.1 Generate Multiple Strategy Types in Dashboard

**File Modified**: `dashboard/dashboard_renderer.py`

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

#### 7.2 Add Strategy Type Filter in UI

**File Modified**: `dashboard/dashboard_renderer.py`

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

#### 7.3 Show Strategy Type in Strategy List

Add column showing strategy type:
```python
# In strategy expander title
title = f"{token_flow} | {protocol_pair} | {strategy_type} | APR: {apr}%"
```

---

### Phase 8: Update Refresh Pipeline

**Goal**: Generate and cache both strategy types

#### 8.1 Specify Strategy Types in Refresh

**File Modified**: `data/refresh_pipeline.py`

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

---

## Critical Files to Modify

### New Files to Create:
1. `analysis/strategy_calculators/__init__.py` - Calculator registry
2. `analysis/strategy_calculators/base.py` - Abstract base class
3. `analysis/strategy_calculators/recursive_lending.py` - Extracted existing 4-leg logic
4. `analysis/strategy_calculators/stablecoin_lending.py` - New 1-leg calculator
5. `analysis/strategy_calculators/noloop_cross_protocol.py` - New 3-leg calculator

### Files to Modify:
1. `analysis/rate_analyzer.py` - Accept strategy_types parameter, loop through types, add generation methods for each type
2. `analysis/position_calculator.py` - Facade pattern, delegate to calculators
3. `analysis/position_service.py` - Add strategy_type parameter to create_position()
4. `analysis/portfolio_allocator.py` - Add strategy type filtering
5. `dashboard/position_renderers.py` - Add StablecoinLendingRenderer and NoLoopCrossProtocolRenderer
6. `dashboard/dashboard_renderer.py` - Display all three strategy types, add filter with icons
7. `data/refresh_pipeline.py` - Specify all three strategy_types when creating analyzer
8. `config/settings.py` - Add default strategy types config, rebalance thresholds per type

### Files That Need NO Changes:
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

## Testing Strategy

### Unit Tests:
1. Test each calculator independently with known inputs
2. Test registry lookup for both strategy types
3. Test RateAnalyzer generates both types correctly

### Integration Tests:
1. Test full pipeline: rate fetch → strategy generation → position creation
2. Test portfolio allocator with mixed strategy types
3. Test rebalance with both strategy types

### Validation:
1. Verify "All Strategies" shows both types sorted by APR
2. Verify position creation stores correct strategy_type
3. Verify dashboard renders each type correctly
4. Verify PnL calculations match for 3-leg vs 4-leg positions

---

## Rollout Plan

### Stage 1: Foundation (No User Impact)
- Create calculator base class and registry
- Extract recursive lending to calculator
- Add tests

### Stage 2: Unlevered Calculator
- Implement UnleveredLendingCalculator
- Add unit tests
- Verify math against manual calculations

### Stage 3: Integration
- Update RateAnalyzer to support multiple types
- Update PositionService to accept strategy_type
- Add strategy_type column to results

### Stage 4: UI & Rendering
- Implement UnleveredLendingRenderer
- Add strategy type filter to dashboard
- Display both types in "All Strategies"

### Stage 5: Portfolio & Rebalancing
- Update portfolio allocator
- Add rebalance support for unlevered
- End-to-end testing

---

## Summary: What Needs to Change vs What's Ready

### ✅ No Changes Needed (Already Extensible):
- Database schema - has strategy_type column
- Rendering system - has registry pattern
- Rebalance table - event sourcing pattern
- Rate fetching - strategy-agnostic
- Price/liquidity data - shared across strategies

### 🔧 Needs Refactoring:
- Strategy calculation logic - extract to pluggable calculators
- Position creation - accept strategy_type parameter
- Rate analyzer - loop through multiple strategy types
- Portfolio allocator - filter by strategy type
- Dashboard - display multiple types, add filter

### ➕ Needs Creation:
- Calculator base class and registry
- RecursiveLendingCalculator (extracted from existing code)
- StablecoinLendingCalculator (new - simplest)
- NoLoopCrossProtocolCalculator (new - 3-leg)
- StablecoinLendingRenderer (new)
- NoLoopCrossProtocolRenderer (new)

---

## Answer to User's Abstract Question

> From an abstract viewpoint, what changes do we need to make and what do we need to create?

**Changes Needed**:
1. ✅ Define mapping from strategy deployment → positions table: **Already exists** (strategy_type column)
2. ✅ Define what rebalance means: **Strategy-specific** - Add calculate_rebalance_amounts() to each calculator
3. ✅ Define how rebalances are stored: **Already exists** (position_rebalances table is strategy-agnostic)
4. ✅ Have calculate_pnl, calculate_apr functions: **Strategy-specific** - Move to calculator classes
5. ✅ Price/rate fetcher: **No changes needed** - Same tokens/protocols used by all strategies

**New Abstractions to Create**:
- **StrategyCalculatorBase**: Abstract interface for strategy-specific math
- **Calculator Registry**: Lookup calculator by strategy_type
- **Strategy-Specific Calculators**: One per strategy type
- **Strategy-Specific Renderers**: One per strategy type (RecursiveLendingRenderer already exists)

**Core Insight**: The system is *already 80% ready* for multiple strategies. The main work is:
1. Extracting hardcoded recursive logic into pluggable calculators
2. Creating two new simple calculators (stablecoin and noloop)
3. Making RateAnalyzer loop through multiple strategy types
4. Passing strategy_type through the call chain

The database, rendering system, and data pipeline are already strategy-agnostic by design!

**Complexity Progression**:
1. **STABLECOIN_LENDING**: Simplest (1 leg, no borrowing, no rebalancing, no liquidation risk)
2. **NOLOOP_CROSS_PROTOCOL_LENDING**: Moderate (3 legs, one borrow, rebalancing needed, single liquidation risk)
3. **RECURSIVE_LENDING**: Most complex (4 legs, recursive leverage, complex rebalancing, dual liquidation risks)

This progression allows users to choose their desired risk/reward profile!
