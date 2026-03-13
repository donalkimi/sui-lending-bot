---
type: feat
scope: dashboard
date: 2026-03-13 15:00
files: [dashboard/dashboard_renderer.py]
docs_updated: []
design_notes_ok: true
schema_synced: not_triggered
---

# feat(dashboard): add token4 column to allocation tab strategy table

## What was done
Added token4 to the allocation tab's "All Strategies" table. The data was already present in the DataFrame from the strategy calculators but was excluded from the display column list (`base_columns` and `column_names`). Also removed two stale debug print statements for stablecoin preferences.

## Decisions made
- Straightforward addition — token4 follows the exact same pattern as token1/2/3 (raw symbol value from calculator output, no transformation needed)
- Non-perp strategies will show blank/None in the token4 column, which is correct behaviour
- Removed debug prints as cleanup since they were in the same area of code

## Files changed
- dashboard/dashboard_renderer.py

## Design notes check
All clear

## Docs updated
None needed

## Schema sync
Not triggered

## Git summary
```
feat(dashboard): add token4 column to allocation tab strategy table

token4 data was already in the DataFrame but excluded from display columns.
Added to base_columns and column_names. Shows perp proxy for perp strategies,
blank for others. Removed two stale debug print statements.
```

## Diff stat
```
 dashboard/dashboard_renderer.py | 8 +++-----
 1 file changed, 3 insertions(+), 5 deletions(-)
```

## Key changes
```diff
diff --git a/dashboard/dashboard_renderer.py b/dashboard/dashboard_renderer.py
--- a/dashboard/dashboard_renderer.py
+++ b/dashboard/dashboard_renderer.py
@@ -2902,7 +2900,7 @@ def render_allocation_tab(all_strategies_df: pd.DataFrame):
                 base_columns = [
                     'strategy_type',
-                    'token1', 'token2', 'token3',
+                    'token1', 'token2', 'token3', 'token4',
                     'protocol_a', 'protocol_b',
                     'net_apr', 'apr5', 'apr30', 'blended_apr', 'stablecoin_multiplier', 'adjusted_apr'
                 ]
@@ -2949,7 +2947,7 @@ def render_allocation_tab(all_strategies_df: pd.DataFrame):
                 column_names = [
                     'Strategy Type',
-                    'Token1', 'Token2', 'Token3',
+                    'Token1', 'Token2', 'Token3', 'Token4',
                     'Protocol A', 'Protocol B',
                     'Net APR', 'APR5', 'APR30', 'Blended APR', 'Stable Mult', 'Adjusted APR'
                 ]
```
