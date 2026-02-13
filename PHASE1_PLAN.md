# Phase 1: Strategy Calculator Layer - Implementation Plan

## Overview

Refactor strategy-specific calculations into pluggable calculator classes, addressing all data validation and consistency concerns.

---

## Key Design Decisions (Based on Your Feedback)

### 1. **Use `0.0` instead of `None` for unused legs**
- ✅ `b_b = 0.0` (not `None`) for stablecoin and noloop strategies
- **Rationale**: More consistent, clearer semantics (0 = "not used" vs None = "not applicable")

### 2. **Use `float('inf')` for unbounded values**
- ✅ `liquidation_distance = float('inf')` for stablecoin lending (no liquidation risk)
- ✅ `max_size = float('inf')` for stablecoin lending (no liquidity constraints)
- **Rationale**: More semantically correct than `None`, database stores it fine

### 3. **Use total APRs (base + reward already combined)**
- ✅ Use `lend_total_apr` and `borrow_total_apr` from database
- **Schema**: `lend_total_apr = lend_base_apr + lend_reward_apr`
- **Rationale**: Avoids redundant calculations, uses database's pre-computed totals

### 4. **Explicit data validation (fail fast)**
- ✅ Raise errors for missing critical rates (lend_total_apr, borrow_total_apr)
- ✅ Log warnings + use 0.0 fallback for nullable borrow_fee (but track data quality)
- **Rationale**: Prefer explicit failures over silent assumptions

### 5. **No supply cap tracking**
- ✅ `max_size = inf` for stablecoin lending
- **Current state**: Database has `available_borrow_usd` (borrow liquidity) but NOT `available_supply_usd` (lending supply caps)
- **Rationale**: We don't currently track lending supply caps, so no constraint exists

---

## File Structure

```
analysis/
├── strategy_calculators/
│   ├── __init__.py           # Registry + auto-registration
│   ├── base.py               # Abstract base class
│   ├── stablecoin_lending.py # 1-leg calculator
│   ├── noloop_cross_protocol.py # 3-leg calculator
│   └── recursive_lending.py  # 4-leg calculator (extracted)
└── position_calculator.py    # Facade (delegate to calculators)
```

---

## 1.1: Abstract Base Class

**File**: `analysis/strategy_calculators/base.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class StrategyCalculatorBase(ABC):
    """Base class for strategy-specific calculations"""

    @abstractmethod
    def get_strategy_type(self) -> str:
        """Returns strategy type identifier (e.g., 'stablecoin_lending')"""
        pass

    @abstractmethod
    def get_required_legs(self) -> int:
        """Returns number of legs (1, 3, or 4)"""
        pass

    @abstractmethod
    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers/weights for this strategy.

        Returns:
            Dict with keys: l_a, b_a, l_b, b_b (all float, use 0.0 for unused)
        """
        pass

    @abstractmethod
    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for this strategy.

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_*, borrow_total_apr_*
            fees: Dict with borrow_fee_* (nullable)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        pass

    @abstractmethod
    def analyze_strategy(self, **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis returning all metrics.

        Must return dict with at minimum:
            - l_a, b_a, l_b, b_b: Position multipliers
            - net_apr: Decimal net APR
            - liquidation_distance: float (could be inf)
            - max_size: float (could be inf)
            - valid: bool
        """
        pass

    @abstractmethod
    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Calculate token amounts needed to restore target weights.

        Returns None if no rebalancing needed (e.g., stablecoin lending)
        """
        pass
```

**Key Points**:
- All methods must be implemented by subclasses
- Return types are strictly defined
- `b_b` always returned (use `0.0` for 1-leg and 3-leg strategies)

---

## 1.2: Stablecoin Lending Calculator (1-Leg, Simplest)

**File**: `analysis/strategy_calculators/stablecoin_lending.py`

```python
import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)

class StablecoinLendingCalculator(StrategyCalculatorBase):
    """
    Stablecoin lending calculator (1-leg strategy).

    Mechanics:
        - Lend stablecoin in one protocol
        - No borrowing, no cross-protocol activity
        - Just earn base lending APR + rewards

    Position multipliers:
        - L_A = 1.0 (lend $1 for every $1 deployed)
        - B_A = 0.0 (no borrowing)
        - L_B = 0.0 (no second lending)
        - B_B = 0.0 (no second borrowing)

    Risk profile:
        - No liquidation risk
        - No rebalancing needed
        - No price exposure (stablecoin only)
        - Protocol risk only
    """

    def get_strategy_type(self) -> str:
        return 'stablecoin_lending'

    def get_required_legs(self) -> int:
        return 1

    def calculate_positions(self, **kwargs) -> Dict[str, float]:
        """
        Calculate position multipliers (trivial for stablecoin lending).

        Returns:
            Dict with l_a=1.0, all others=0.0
        """
        return {
            'l_a': 1.0,
            'b_a': 0.0,
            'l_b': 0.0,
            'b_b': 0.0  # Consistent with other strategies (use 0 not None)
        }

    def calculate_net_apr(self, positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for stablecoin lending.

        APR = lend_total_apr_1A (base + reward already combined)

        Args:
            positions: Not used (only one leg)
            rates: Dict with 'lend_total_apr_1A'
            fees: Not used (no borrowing)

        Returns:
            Net APR as decimal
        """
        lend_total_apr = rates.get('lend_total_apr_1A')

        # Validate data quality - fail fast if missing
        if lend_total_apr is None:
            raise ValueError(
                f"Missing lend_total_apr_1A for stablecoin lending strategy. "
                f"This is a critical data quality issue."
            )

        return lend_total_apr

    def analyze_strategy(self,
                        token1: str,
                        protocol_a: str,
                        lend_total_apr_1A: float,
                        price_1A: float,
                        **kwargs) -> Dict[str, Any]:
        """
        Analyze stablecoin lending strategy.

        Args:
            token1: Stablecoin symbol (e.g., 'USDC')
            protocol_a: Protocol name (e.g., 'navi')
            lend_total_apr_1A: Total lending APR (base + reward)
            price_1A: Token price (should be ~$1 for stablecoins)
            **kwargs: Ignored (other strategies need more params)

        Returns:
            Strategy dict with all required fields
        """
        # Validate inputs
        if lend_total_apr_1A is None:
            return {
                'valid': False,
                'error': 'Missing lend_total_apr_1A'
            }

        if price_1A is None or price_1A <= 0:
            return {
                'valid': False,
                'error': 'Invalid or missing price_1A'
            }

        # Calculate positions (trivial)
        positions = self.calculate_positions()

        return {
            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'net_apr': lend_total_apr_1A,
            'apr5': lend_total_apr_1A,   # No fees to amortize
            'apr30': lend_total_apr_1A,
            'apr90': lend_total_apr_1A,
            'days_to_breakeven': 0.0,    # No upfront fees

            # Risk metrics
            'liquidation_distance': float('inf'),  # No liquidation risk
            'max_size': float('inf'),  # No liquidity constraints tracked

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),

            # Note: We don't track lending supply caps in database
            # Only borrow liquidity limits (available_borrow_usd)
        }

    def calculate_rebalance_amounts(self, position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        No rebalancing needed for stablecoin lending (no borrowed assets).

        Returns:
            None (signals no rebalancing required)
        """
        return None
```

---

## 1.3: NoLoop Cross-Protocol Calculator (3-Leg)

**File**: `analysis/strategy_calculators/noloop_cross_protocol.py`

```python
import logging
from typing import Dict, Any
from .base import StrategyCalculatorBase

logger = logging.getLogger(__name__)

class NoLoopCrossProtocolCalculator(StrategyCalculatorBase):
    """
    No-loop cross-protocol lending calculator (3-leg strategy).

    Mechanics:
        1. Lend token1 (stablecoin) in Protocol A
        2. Borrow token2 (high-yield) from Protocol A (using token1 as collateral)
        3. Lend token2 in Protocol B
        4. No loop back - position stays exposed to token2

    Position multipliers:
        - L_A = 1.0 (lend token1)
        - B_A = L_A × liquidation_threshold_A / (1 + liq_dist)
        - L_B = B_A (lend borrowed token2)
        - B_B = 0.0 (no borrow back)

    Risk profile:
        - Liquidation risk on leg 2A (if token2 price drops)
        - Rebalancing needed (token2 price changes)
        - Token2 price exposure
        - Two protocol risks
    """

    def get_strategy_type(self) -> str:
        return 'noloop_cross_protocol_lending'

    def get_required_legs(self) -> int:
        return 3

    def calculate_positions(self,
                           liquidation_threshold_a: float,
                           collateral_ratio_a: float,
                           liquidation_distance: float = 0.20) -> Dict[str, float]:
        """
        Calculate position multipliers for no-loop cross-protocol strategy.

        Args:
            liquidation_threshold_a: LTV at which liquidation occurs (e.g., 0.80)
            collateral_ratio_a: Max collateral factor (e.g., 0.75)
            liquidation_distance: Safety buffer (default 0.20 = 20%)

        Returns:
            Dict with l_a, b_a, l_b, b_b multipliers

        Example:
            liq_threshold = 0.80, liq_dist = 0.20
            → r_a = 0.80 / 1.20 = 0.667
            → borrow up to 66.7% LTV (staying 20% away from 80% liquidation)
        """
        # No recursive leverage - linear calculation
        l_a = 1.0

        # Borrow up to liquidation_threshold with safety buffer
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
            'b_b': 0.0  # No 4th leg (use 0.0 not None for consistency)
        }

    def calculate_net_apr(self,
                         positions: Dict[str, float],
                         rates: Dict[str, float],
                         fees: Dict[str, float]) -> float:
        """
        Calculate net APR for no-loop cross-protocol strategy.

        Formula:
            APR = (L_A × lend_total_apr_1A) + (L_B × lend_total_apr_2B)
                  - (B_A × borrow_total_apr_2A) - (B_A × borrow_fee_2A)

        Args:
            positions: Dict with l_a, b_a, l_b, b_b
            rates: Dict with lend_total_apr_1A, lend_total_apr_2B, borrow_total_apr_2A
            fees: Dict with borrow_fee_2A (nullable)

        Returns:
            Net APR as decimal (e.g., 0.0524 = 5.24%)
        """
        l_a = positions['l_a']
        b_a = positions['b_a']
        l_b = positions['l_b']

        # Use total APRs (base + reward already combined in database)
        lend_total_1A = rates.get('lend_total_apr_1A')
        lend_total_2B = rates.get('lend_total_apr_2B')
        borrow_total_2A = rates.get('borrow_total_apr_2A')

        # Validate critical rates are present - fail fast
        if lend_total_1A is None:
            raise ValueError("Missing lend_total_apr_1A")
        if lend_total_2B is None:
            raise ValueError("Missing lend_total_apr_2B")
        if borrow_total_2A is None:
            raise ValueError("Missing borrow_total_apr_2A")

        # Calculate earnings and costs
        earnings = (l_a * lend_total_1A) + (l_b * lend_total_2B)
        costs = b_a * borrow_total_2A

        # Borrow fees - nullable in database schema
        # Use .get() with fallback but log warning for data quality tracking
        borrow_fee_2A = fees.get('borrow_fee_2A')
        if borrow_fee_2A is None:
            logger.warning(
                "Missing borrow_fee_2A - assuming 0.0. "
                "This may indicate a data quality issue."
            )
            borrow_fee_2A = 0.0

        fees_cost = b_a * borrow_fee_2A

        return earnings - costs - fees_cost

    def analyze_strategy(self,
                        token1: str,
                        token2: str,
                        protocol_a: str,
                        protocol_b: str,
                        lend_total_apr_1A: float,
                        borrow_total_apr_2A: float,
                        lend_total_apr_2B: float,
                        collateral_ratio_1A: float,
                        liquidation_threshold_1A: float,
                        price_1A: float,
                        price_2A: float,
                        price_2B: float,
                        available_borrow_2A: float = None,
                        borrow_fee_2A: float = None,
                        liquidation_distance: float = 0.20,
                        **kwargs) -> Dict[str, Any]:
        """
        Complete strategy analysis for no-loop cross-protocol lending.

        Args:
            token1: Stablecoin (e.g., 'USDC')
            token2: High-yield token (e.g., 'DEEP')
            protocol_a: First protocol (e.g., 'navi')
            protocol_b: Second protocol (e.g., 'suilend')
            lend_total_apr_1A: Lending APR for token1 on protocol A
            borrow_total_apr_2A: Borrowing APR for token2 on protocol A
            lend_total_apr_2B: Lending APR for token2 on protocol B
            collateral_ratio_1A: Max collateral factor for token1
            liquidation_threshold_1A: Liquidation LTV for token1
            price_1A, price_2A, price_2B: Token prices
            available_borrow_2A: Available borrow liquidity for token2 (optional)
            borrow_fee_2A: Upfront borrow fee for token2 (optional, nullable)
            liquidation_distance: Safety buffer (default 0.20)

        Returns:
            Complete strategy dict
        """
        # Validate inputs
        missing_fields = []
        if lend_total_apr_1A is None:
            missing_fields.append('lend_total_apr_1A')
        if borrow_total_apr_2A is None:
            missing_fields.append('borrow_total_apr_2A')
        if lend_total_apr_2B is None:
            missing_fields.append('lend_total_apr_2B')
        if collateral_ratio_1A is None:
            missing_fields.append('collateral_ratio_1A')
        if liquidation_threshold_1A is None:
            missing_fields.append('liquidation_threshold_1A')

        if missing_fields:
            return {
                'valid': False,
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }

        # Calculate position multipliers
        positions = self.calculate_positions(
            liquidation_threshold_a=liquidation_threshold_1A,
            collateral_ratio_a=collateral_ratio_1A,
            liquidation_distance=liquidation_distance
        )

        # Calculate net APR
        rates = {
            'lend_total_apr_1A': lend_total_apr_1A,
            'lend_total_apr_2B': lend_total_apr_2B,
            'borrow_total_apr_2A': borrow_total_apr_2A
        }
        fees = {
            'borrow_fee_2A': borrow_fee_2A or 0.0
        }
        net_apr = self.calculate_net_apr(positions, rates, fees)

        # Calculate max size based on available borrow liquidity
        max_size = float('inf')
        if available_borrow_2A is not None and available_borrow_2A > 0:
            # Max deployment limited by borrow liquidity
            # deployment × b_a = borrow amount in USD
            # borrow amount in USD ≤ available_borrow_2A
            max_size = available_borrow_2A / positions['b_a']

        # Calculate fee-adjusted APRs (simplified for now)
        # TODO: Implement time-adjusted APRs (5/30/90 day horizons)
        apr5 = net_apr  # Placeholder
        apr30 = net_apr
        apr90 = net_apr
        days_to_breakeven = 0.0  # Placeholder

        return {
            # Position multipliers
            'l_a': positions['l_a'],
            'b_a': positions['b_a'],
            'l_b': positions['l_b'],
            'b_b': positions['b_b'],

            # APR metrics
            'net_apr': net_apr,
            'apr5': apr5,
            'apr30': apr30,
            'apr90': apr90,
            'days_to_breakeven': days_to_breakeven,

            # Risk metrics
            'liquidation_distance': liquidation_distance,
            'max_size': max_size,

            # Metadata
            'valid': True,
            'strategy_type': self.get_strategy_type(),
        }

    def calculate_rebalance_amounts(self,
                                   position: Dict,
                                   live_rates: Dict,
                                   live_prices: Dict) -> Dict:
        """
        Calculate rebalance amounts for 3-leg strategy.

        Maintains constant USD values for L_A, B_A, L_B (no B_B).

        Args:
            position: Position dict with entry data
            live_rates: Current rates
            live_prices: Current prices

        Returns:
            Dict with rebalance token amounts for each leg
        """
        # TODO: Implement rebalancing logic
        # Calculate target USD values based on multipliers
        # Calculate current USD values using live prices
        # Return token amount deltas to restore targets
        raise NotImplementedError("Rebalancing logic not yet implemented")
```

---

## 1.4: Recursive Lending Calculator (4-Leg, Extract Existing)

**File**: `analysis/strategy_calculators/recursive_lending.py`

```python
from .base import StrategyCalculatorBase
# ... (extract existing logic from position_calculator.py)

class RecursiveLendingCalculator(StrategyCalculatorBase):
    """
    Recursive lending calculator (4-leg strategy with loop).

    Extract existing implementation from position_calculator.py:
    - calculate_positions() → geometric series calculation
    - calculate_net_apr() → 4-leg APR formula
    - analyze_strategy() → complete recursive strategy analysis
    """

    def get_strategy_type(self) -> str:
        return 'recursive_lending'

    def get_required_legs(self) -> int:
        return 4

    # ... Extract existing methods from position_calculator.py
    # Keep same logic, just wrap in class structure
```

---

## 1.5: Calculator Registry

**File**: `analysis/strategy_calculators/__init__.py`

```python
from typing import Dict, List
from .base import StrategyCalculatorBase
from .stablecoin_lending import StablecoinLendingCalculator
from .noloop_cross_protocol import NoLoopCrossProtocolCalculator
from .recursive_lending import RecursiveLendingCalculator

_CALCULATORS: Dict[str, StrategyCalculatorBase] = {}

def register_calculator(calculator_class: type):
    """Register a strategy calculator class."""
    calc = calculator_class()
    strategy_type = calc.get_strategy_type()
    _CALCULATORS[strategy_type] = calc
    return calc

def get_calculator(strategy_type: str) -> StrategyCalculatorBase:
    """Get calculator by strategy type."""
    if strategy_type not in _CALCULATORS:
        available = ', '.join(_CALCULATORS.keys())
        raise ValueError(
            f"Unknown strategy type: '{strategy_type}'. "
            f"Available: {available}"
        )
    return _CALCULATORS[strategy_type]

def get_all_strategy_types() -> List[str]:
    """Get list of all registered strategy types."""
    return list(_CALCULATORS.keys())

# Auto-register built-in calculators on module import
register_calculator(StablecoinLendingCalculator)
register_calculator(NoLoopCrossProtocolCalculator)
register_calculator(RecursiveLendingCalculator)

# Export for convenience
__all__ = [
    'StrategyCalculatorBase',
    'StablecoinLendingCalculator',
    'NoLoopCrossProtocolCalculator',
    'RecursiveLendingCalculator',
    'register_calculator',
    'get_calculator',
    'get_all_strategy_types',
]
```

---

## Data Flow Summary

### Database Schema (rates_snapshot table)
```
Columns used by calculators:
- lend_total_apr = lend_base_apr + lend_reward_apr (pre-computed)
- borrow_total_apr = borrow_base_apr - borrow_reward_apr (pre-computed)
- borrow_fee (NULLABLE - may be NULL, default to 0.0 with warning)
- collateral_ratio (collateral factor)
- liquidation_threshold (LTV at liquidation)
- price_usd
- available_borrow_usd (borrow liquidity limit)
```

### Calculator Input/Output
```
Input:
  rates: {lend_total_apr_1A, borrow_total_apr_2A, ...}
  fees: {borrow_fee_2A, ...}  # Nullable
  thresholds: {liquidation_threshold_a, collateral_ratio_a, ...}
  prices: {price_1A, price_2A, ...}

Output:
  {
    l_a, b_a, l_b, b_b: float (use 0.0 for unused legs)
    net_apr: float
    liquidation_distance: float (could be inf)
    max_size: float (could be inf)
    valid: bool
  }
```

---

## Testing Checklist

### Unit Tests
- [ ] StablecoinLendingCalculator
  - [ ] calculate_positions() returns l_a=1.0, rest=0.0
  - [ ] calculate_net_apr() uses lend_total_apr
  - [ ] analyze_strategy() returns liquidation_distance=inf, max_size=inf
  - [ ] Missing lend_total_apr raises error
  - [ ] calculate_rebalance_amounts() returns None

- [ ] NoLoopCrossProtocolCalculator
  - [ ] calculate_positions() linear calculation (no geometric series)
  - [ ] b_a = liq_threshold / (1 + liq_dist)
  - [ ] b_b = 0.0 (not None)
  - [ ] calculate_net_apr() uses total APRs
  - [ ] Missing borrow_fee logs warning, uses 0.0
  - [ ] Missing critical rates raise errors

- [ ] Calculator Registry
  - [ ] All three calculators auto-registered on import
  - [ ] get_calculator() retrieves correct calculator
  - [ ] get_calculator() raises error for unknown type
  - [ ] get_all_strategy_types() returns ['stablecoin_lending', 'noloop_cross_protocol_lending', 'recursive_lending']

---

## Critical Implementation Notes

1. **Database Rate Naming**:
   - Use `lend_total_apr` not `lend_rate` (avoid ambiguity)
   - Use `borrow_total_apr` not `borrow_rate`
   - Both already include rewards (base ± reward)

2. **Nullable Fields**:
   - `borrow_fee` is nullable in database schema
   - Use `.get(field, None)` → check if None → log warning → fallback to 0.0
   - Track data quality issues via logging

3. **Infinity vs None**:
   - Use `float('inf')` for unbounded values (semantically clearer)
   - PostgreSQL and SQLite both store it correctly
   - Easier to handle in downstream calculations (no None checks)

4. **Consistency**:
   - Always return all 4 multipliers (l_a, b_a, l_b, b_b)
   - Use `0.0` for unused legs (not None)
   - Simplifies downstream code (no special cases)

5. **Supply Caps**:
   - Current database schema has `available_borrow_usd` (borrow liquidity)
   - Does NOT have `available_supply_usd` (lending supply caps)
   - Therefore, stablecoin lending has no `max_size` constraint

---

## Next Steps

After Phase 1 is complete:
- **Phase 2**: Update RateAnalyzer to use calculator registry
- **Phase 3**: Update PositionService.create_position() to accept strategy_type
- **Phase 4**: Update PortfolioAllocator for multi-strategy support
- **Phase 5**: Create renderers for new strategy types
- **Phase 6**: Implement rebalancing logic
- **Phase 7**: Add UI filters and display
- **Phase 8**: Update refresh pipeline
