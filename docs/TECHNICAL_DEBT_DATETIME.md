# Technical Debt: DateTime vs Unix Seconds in Dashboard

**Status**: Documented Technical Debt
**Date**: 2026-01-28
**Priority**: Low (Non-breaking, design principle violation)

---

## Issue Summary

Dashboard data loaders return `datetime`/`pandas.Timestamp` objects instead of Unix seconds (int), violating the design principle documented in [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) Section 5.

---

## Design Principle (Section 5: Timestamp Representation)

From DESIGN_NOTES.md:

> **Core Principle:** All internal Python code operates on Unix timestamps (seconds as integers).
>
> **Conversion boundaries:**
> - **DB → Code:** Read timestamp string, immediately convert to seconds (int)
> - **Internal processing:** Everything in seconds (integers)

---

## Violation Details

**Location**: [dashboard/data_loaders.py](dashboard/data_loaders.py)

**Current Implementation** (lines 63, 78):
```python
self._timestamp = pd.to_datetime(timestamp)  # Returns pandas.Timestamp
return (..., self._timestamp)  # Returns datetime, not int
```

**Return Type Annotation** (line 67):
```python
def load_data(self) -> Tuple[..., datetime]:
    # Should be: Tuple[..., int]
```

---

## Impact

- **Type confusion**: Downstream code receives `pandas.Timestamp` instead of `int`
- **Design inconsistency**: Database → Code boundary should convert to seconds immediately
- **Non-breaking**: Current implementation works, but violates design principle

---

## Correct Implementation (Per Design Principle)

```python
# data_loaders.py line 63
self._timestamp_str = timestamp
# Convert to seconds immediately at DB → Code boundary
self._timestamp = int(pd.to_datetime(timestamp).timestamp())  # Unix seconds (int)

# Return type annotation (line 67)
def load_data(self) -> Tuple[..., int]:  # Changed from datetime to int
    return (..., self._timestamp)  # Returns int (seconds)
```

**Downstream changes required**:
- Any code expecting `datetime` would need updating
- Convert back to datetime only for display: `pd.Timestamp(seconds, unit='s')`

---

## Decision

**Keep current datetime behavior for backward compatibility.**

**Rationale**:
- Changing return type to `int` requires auditing all downstream usage
- Current implementation is not broken, only violates design principle
- Should be fixed in separate refactoring pass to avoid breaking changes

---

## Recommended Fix (Future Work)

1. **Audit downstream usage**: Identify all code that receives timestamp from data loaders
2. **Update data_loaders.py**: Convert to seconds at boundary (line 63)
3. **Update return type annotations**: Change `datetime` → `int` in all signatures
4. **Update downstream code**: Convert to datetime only for display
5. **Verify**: All dashboard components work with int (seconds)

---

## Related Files

- **Design principle**: [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md) - Section 5
- **Violation location**: [dashboard/data_loaders.py](dashboard/data_loaders.py) - lines 63, 67, 78, 82, 106, 110, 122
- **Potential impact**: Any code that receives timestamp from `UnifiedDataLoader.load_data()` or `HistoricalDataLoader.load_data()`

---

## Notes

- This issue was discovered during LLTV implementation (Phase 5)
- Does not block LLTV feature work
- Low priority: System works correctly, only violates design consistency principle
