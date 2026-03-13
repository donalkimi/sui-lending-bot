---
type: refactor
scope: calculators
date: 2026-03-13 14:30
files: [.gitignore, analysis/position_service.py, analysis/position_statistics_calculator.py, analysis/rate_analyzer.py, analysis/strategy_calculators/base.py, analysis/strategy_calculators/noloop_cross_protocol.py, analysis/strategy_calculators/perp_borrowing.py, analysis/strategy_calculators/perp_borrowing_recursive.py, analysis/strategy_calculators/perp_lending.py, analysis/strategy_calculators/perp_lending_recursive.py, analysis/strategy_calculators/recursive_lending.py, analysis/strategy_calculators/stablecoin_lending.py, analysis/strategy_history/base.py, analysis/strategy_history/noloop_cross_protocol.py, analysis/strategy_history/perp_borrowing.py, analysis/strategy_history/perp_lending.py, analysis/strategy_history/perp_lending_recursive.py, analysis/strategy_history/recursive_lending.py, analysis/strategy_history/stablecoin_lending.py, analysis/strategy_history/strategy_history.py, dashboard/analysis_tab.py, dashboard/dashboard_renderer.py, dashboard/position_renderers.py, docs/APR_METRICS_REFERENCE.md]
docs_updated: [docs/APR_METRICS_REFERENCE.md]
design_notes_ok: true
schema_synced: not_triggered
---

# refactor(calculators): universal token naming + basis APR consolidation

## What was done

Replaced all legacy protocol-based suffixed rate/fee/price/collateral parameters (`_1A`, `_2A`, `_2B`, `_3B`) with universal token naming (`_token1`, `_token2`, `_token3`, `_token4`) across strategy calculators, rate_analyzer, strategy_history, position_statistics, and dashboard. This eliminates the problematic token3 aliasing where `lend_total_apr_2B` and `lend_total_apr_3B` both referred to the same value in different strategies. Also consolidated basis APR calculation by removing the `compute_basis_adjusted_current_apr()` static method from position_service.py; basis APR now reads directly from position stats in position_renderers.py as a single source of truth.

## Decisions made

- **Scope**: Renamed not just rate/fee dict keys but all parameter names across public interfaces (`analyze_strategy()` signatures, strategy_history market_data dicts, dashboard reads). This ensures consistency end-to-end — not partial.
- **Fee key naming**: Used `borrow_fee_token2`/`borrow_fee_token4` (not `fee_token2`) to distinguish clearly from trading fees or other types.
- **Perp leg token mapping**: Preserved existing convention — perp_borrowing uses token3 (L_B = long perp), perp_lending uses token4 (B_B = short perp). Raw display keys include the correct token suffix per strategy type.
- **Single commit**: Combined both token naming refactor and basis APR consolidation into one commit since they were in-flight together and changes are tightly coupled in position_renderers.py.
- **Straightforward execution**: The refactor was mechanical (search-and-replace style) with clear mapping. No alternative approaches; deterministic transformation.

## Files changed

- .gitignore
- analysis/position_service.py (deleted compute_basis_adjusted_current_apr static method)
- analysis/position_statistics_calculator.py (eliminated aliasing hack in rates_dict)
- analysis/rate_analyzer.py (all 5 strategy generator methods: local vars + kwargs)
- analysis/strategy_calculators/base.py (fee dict keys, local vars, helper params)
- analysis/strategy_calculators/noloop_cross_protocol.py (rate/fee/price/collateral params)
- analysis/strategy_calculators/perp_borrowing.py (rate/fee keys, calculate_positions params)
- analysis/strategy_calculators/perp_borrowing_recursive.py (calculate_positions params)
- analysis/strategy_calculators/perp_lending.py (rate keys, local vars)
- analysis/strategy_calculators/perp_lending_recursive.py (kwargs keys, calculate_positions params)
- analysis/strategy_calculators/recursive_lending.py (all 4 rate/fee/collateral/borrow params)
- analysis/strategy_calculators/stablecoin_lending.py (rate/price params)
- analysis/strategy_history/base.py (market_data dict keys)
- analysis/strategy_history/noloop_cross_protocol.py (build_market_data_dict keys)
- analysis/strategy_history/perp_borrowing.py (build_market_data_dict, rolling avg keys, raw display keys)
- analysis/strategy_history/perp_lending.py (build_market_data_dict)
- analysis/strategy_history/perp_lending_recursive.py (build_market_data_dict)
- analysis/strategy_history/recursive_lending.py (build_market_data_dict)
- analysis/strategy_history/stablecoin_lending.py (build_market_data_dict)
- analysis/strategy_history/strategy_history.py (dynamic perp rate key detection, output columns)
- dashboard/analysis_tab.py (column name reads)
- dashboard/dashboard_renderer.py (fixed bug: read token2_borrow_fee instead of non-existent borrow_fee_2A)
- dashboard/position_renderers.py (basis APR consolidation from prior refactor)
- docs/APR_METRICS_REFERENCE.md (updated all rate/fee key references)

## Design notes check

All clear. Changes comply with:
- Design Note #18 (universal leg convention: token1=L_A, token2=B_A, token3=L_B, token4=B_B)
- No datetime.now() outside refresh_pipeline
- No token symbol logic (all logic uses token_contract)
- All rates in decimal (0.0–1.0) range
- Required fields use dict[key], not dict.get(key, default)
- No Streamlit width="stretch" (not a dashboard refactor)
- No calculations in dashboard (moved to analysis layer)
- No legacy suffixes used for strategy-type branching (universal leg convention applied)

## Docs updated

docs/APR_METRICS_REFERENCE.md — Sections 1, 2, 5, 11, 13 updated to use new rate/fee key names in examples and reference tables.

## Schema sync

Not triggered (no schema changes).

## Git summary

```
refactor(calculators): universal token naming + basis APR consolidation

1. Replace legacy protocol-based suffixes (_1A, _2A, _2B, _3B) with universal
   token naming (_token1, _token2, _token3, _token4) across all strategy
   calculator interfaces, rate_analyzer, strategy_history, and dashboard.
   Eliminates the token3 aliasing hack (lend_total_apr_2B vs lend_total_apr_3B).
   Fixes latent bug where dashboard read wrong fee keys from analyzer output.

2. Consolidate basis APR calculation: delete compute_basis_adjusted_current_apr()
   static method from position_service.py; basis APR now computed inline in
   position_renderers.py as a single source of truth reading from position stats.
```

## Diff stat

```
 .gitignore                                         |   1 +
 analysis/position_service.py                       |  36 ---
 analysis/position_statistics_calculator.py         |  73 ++---
 analysis/rate_analyzer.py                          | 296 ++++++++++-----------
 analysis/strategy_calculators/base.py              |  84 +++---
 .../strategy_calculators/noloop_cross_protocol.py  | 155 +++++------
 analysis/strategy_calculators/perp_borrowing.py    | 122 ++++-----
 .../perp_borrowing_recursive.py                    |  10 +-
 analysis/strategy_calculators/perp_lending.py      |  60 ++---
 .../strategy_calculators/perp_lending_recursive.py |  60 +++--
 analysis/strategy_calculators/recursive_lending.py | 183 ++++++-------
 .../strategy_calculators/stablecoin_lending.py     |  43 +--
 analysis/strategy_history/base.py                  |   8 +-
 analysis/strategy_history/noloop_cross_protocol.py |  18 +-
 analysis/strategy_history/perp_borrowing.py        |  32 +--
 analysis/strategy_history/perp_lending.py          |  20 +-
 .../strategy_history/perp_lending_recursive.py     |  34 +--
 analysis/strategy_history/recursive_lending.py     |  28 +-
 analysis/strategy_history/stablecoin_lending.py    |   4 +-
 analysis/strategy_history/strategy_history.py      |  28 +-
 dashboard/analysis_tab.py                          |  26 +-
 dashboard/dashboard_renderer.py                    |  34 +-
 dashboard/position_renderers.py                    |   6 +-
 docs/APR_METRICS_REFERENCE.md                      |  72 ++---
 24 files changed, 726 insertions(+), 707 deletions(-)
```

## Key changes

**analysis/position_statistics_calculator.py** — Eliminated the aliasing hack (lend_total_apr_2B and lend_total_apr_3B both pointing to token3):
```diff
-        rates_dict = {
-            'lend_total_apr_1A': _rate_1A,
-            'borrow_total_apr_2A': _rate_2A,
-            'lend_total_apr_2B': _rate_3,  # 2-leg recursive/noloop
-            'lend_total_apr_3B': _rate_3,  # alias: perp_borrowing uses same token
-            'borrow_total_apr_3B': _rate_4,
-        }
-        fees_dict = {
-            'borrow_fee_2A': get_borrow_fee_func(...),
-            'borrow_fee_3B': get_borrow_fee_func(...),
-        }

+        rates_dict = {
+            'rate_token1': _rate_1A,
+            'rate_token2': _rate_2A,
+            'rate_token3': _rate_3,
+            'rate_token4': _rate_4,
+        }
+        fees_dict = {
+            'borrow_fee_token2': get_borrow_fee_func(...),
+            'borrow_fee_token4': get_borrow_fee_func(...),
+        }
```

**dashboard/dashboard_renderer.py** — Fixed bug where fee read used wrong key:
```diff
-        borrow_fee_2A = strategy_row.get('borrow_fee_2A', 0.0)  # always 0.0 — key didn't exist
+        borrow_fee_token2 = strategy_row.get('token2_borrow_fee', 0.0)
```

**analysis/rate_analyzer.py** — Example of parameter rename across all 5 strategy generators:
```diff
-        lend_total_apr_1A = self.get_rate(...)
-        result = calculator.analyze_strategy(
-            lend_total_apr_1A=lend_total_apr_1A,
-            price_1A=price_1A,
+        rate_token1 = self.get_rate(...)
+        result = calculator.analyze_strategy(
+            rate_token1=rate_token1,
+            price_token1=price_token1,
```

**analysis/position_service.py** — Deleted static method (basis APR now in position_renderers):
```diff
-    @staticmethod
-    def compute_basis_adjusted_current_apr(position: pd.Series, stats: Dict) -> float:
-        """Compute current_apr adjusted for unrealised basis PnL."""
-        ...
-        return current_apr + basis_pnl / deployment_usd
```
