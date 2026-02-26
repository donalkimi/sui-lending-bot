# FOR TOMORROW

## 1. Fix APR — Basis not accounted for in perp display
**Context:** `perp_borrowing.py` calculates `basis_cost` correctly and returns `basis_cost_included` flag. But it's unclear whether the dashboard *displays* basis as a separate line in the strategy table / APR breakdown, or if it's silently folded in. Also check `perp_vs_borrows.py` / other perp strategy calculators.
**Files:** `analysis/strategy_calculators/perp_borrowing.py`, dashboard APR display for perp rows
**Task:** Verify basis is surfaced visibly in the strategy table and not just silently included in net_apr.

---

## 2. Fix deploy button for perp strategy
**Context:** The deploy button is generic — stores `strategy_row.to_dict()` in session state with no perp-specific branching. The `create_position()` call downstream may not handle perp strategy fields correctly (e.g. no token3/B_B leg, funding rate leg instead).
**Files:** `dashboard/dashboard_renderer.py` (deploy button ~line 207), `analysis/position_service.py` `create_position()`
**Task:** Trace the deploy flow for a perp strategy type end-to-end and fix any missing/broken field mapping.

---

## 3. Fix allocation for all strategies
**Context:** `portfolio_allocator.py` is fully generic — ranks all strategy types by the same `adjusted_apr` formula. No type-specific handling for perp (e.g. different liquidity constraints, no borrow leg on protocol_b), stablecoin (1-leg), or noloop (3-leg). Iterative liquidity updates may also apply borrow constraints incorrectly for perp/stablecoin strategies.
**Files:** `analysis/portfolio_allocator.py`
**Task:** Audit `_update_available_borrow()` and `_recalculate_max_sizes()` — ensure they skip/handle legs that don't exist for a given strategy type.

---

## 4. Check rebalance logic for strategies
**Context:** Rebalance logic lives in `position_service.py` and `refresh_pipeline.py`. Perp has a `calculate_rebalance_amounts()` stub but no specific implementation. Rebalance trigger compares liquidation distances — this doesn't apply to perp strategies (no liquidation risk on the lend leg in the same way).
**Files:** `analysis/position_service.py` `check_positions_need_rebalancing()`, `analysis/strategy_calculators/perp_borrowing.py`
**Task:** Ensure perp positions are either excluded from liquidation-based rebalance checks, or have their own trigger condition (e.g. basis spread threshold).

---

## 5. Fix modal display — use same renderers as positions tab
**Context:** The deploy modal at `dashboard_renderer.py:576` already uses `get_strategy_renderer()` and calls `renderer_cls.render_strategy_modal_table()` — the registry pattern is in place. But the *positions tab* uses `render_position_expander()` / `render_positions_batch()` with richer detail (4-leg tables, base/reward split, liq prices, token amounts). The modal may be showing a simpler/different table.
**Files:** `dashboard/dashboard_renderer.py` (modal ~line 576–700), `dashboard/position_renderers.py`, `dashboard/strategy_renderers.py`
**Task:** Align modal table columns/format with what's shown in the Positions tab. Reuse `render_detail_table()` from the renderer classes rather than duplicating layout code.
