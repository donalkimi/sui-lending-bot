# Strategy Position Decorator Reference

How tables are generated across the dashboard's three key contexts.
All three use the same renderer registry pattern.

---

## Part 1: The Decorator Registry Pattern (shared infrastructure)

Every strategy renderer is registered via a decorator at class definition time.
This is the foundation for all three tab contexts.

```
position_renderers.py (module load)
│
├── _STRATEGY_RENDERERS = {}          ← global registry dict
│
├── def register_strategy_renderer(strategy_type):      line 161
│       def decorator(cls):
│           _STRATEGY_RENDERERS[strategy_type] = cls
│           return cls
│       return decorator
│
├── @register_strategy_renderer('recursive_lending')    line 1174
│   class RecursiveLendingRenderer(StrategyRendererBase):
│       get_strategy_name()            → "Recursive Lending"
│       build_token_flow_string()      → "T1 → T2 → T3 → T1" (loop back)
│       render_apr_summary_table()     → APR overview row in strategy modal
│       render_detail_table()          → 4-row leg table
│       render_strategy_modal_table()  → 4-row table for Analysis tab
│
├── @register_strategy_renderer('stablecoin_lending')   line 2159
│   class StablecoinLendingRenderer(StrategyRendererBase):
│       get_strategy_name()            → "Stablecoin Lending"
│       build_token_flow_string()      → "T1" (single token)
│       render_apr_summary_table()     → APR overview row; Liq Dist = "N/A"
│       render_detail_table()          → 1-row leg table
│       render_strategy_modal_table()  → 1-row table for Analysis tab
│
├── @register_strategy_renderer('noloop_cross_protocol_lending')  line 2263
│   class NoLoopCrossProtocolRenderer(StrategyRendererBase):
│       get_strategy_name()            → "Cross-Protocol Lending (No Loop)"
│       build_token_flow_string()      → "T1 → T2" (no loop)
│       render_apr_summary_table()     → APR overview row; Fees includes borrow_fee_2a
│       render_detail_table()          → 3-row leg table
│       render_strategy_modal_table()  → 3-row table for Analysis tab
│
├── @register_strategy_renderer('perp_lending')         line 2509
│   class PerpLendingRenderer(StrategyRendererBase):
│       get_strategy_name()            → "Perp Lending"
│       validate_position_data()       → checks required fields
│       get_metrics_layout()           → ['total_pnl', 'total_earnings', ...]
│       build_token_flow_string()      → "TOKEN1 (Spot) ↔ TOKEN3 (Short Perp)"
│       render_apr_summary_table()     → APR overview row; Basis Cost + Fees + Total Fees
│       render_detail_table()          → 2-row leg table (positions/portfolio/modal)
│       render_strategy_modal_table()  → 2-row leg table for Analysis tab only
│
├── @register_strategy_renderer('perp_borrowing')       line 2856
│   @register_strategy_renderer('perp_borrowing_recursive')
│   class PerpBorrowingRenderer(StrategyRendererBase):
│       get_strategy_name()            → "Perp Borrowing"
│       validate_position_data()       → checks required fields
│       get_metrics_layout()           → ['total_pnl', 'total_earnings', ...]
│       build_token_flow_string()      → "T1 (Lend) → Borrow T2 → T3 (Long Perp)"
│       render_apr_summary_table()     → APR overview row; Fees includes B_A × borrow_fee_2a
│       render_detail_table()          → 3-row leg table (positions/portfolio/modal)
│       render_strategy_modal_table()  → 3-row leg table for Analysis tab only
│
└── def get_strategy_renderer(strategy_type):           line 176
        return _STRATEGY_RENDERERS[strategy_type]   ← lookup at runtime
```

**Abstract contract** (`StrategyRendererBase`, line 70):
- `get_strategy_name()` — required, abstract
- `render_detail_table(position, get_rate, get_borrow_fee, get_price_with_fallback, rebalances)` — required, abstract
- `get_metrics_layout()` — required, abstract
- `build_token_flow_string()` — required, abstract
- `validate_position_data()` — required, abstract
- `render_strategy_modal_table()` — optional, raises NotImplementedError by default
- `render_apr_summary_table()` — optional, raises NotImplementedError by default ← NEW

---

## Part 2: Positions Tab — Detail Table Flow

**Entry point:** `render_positions_table_tab()` (dashboard_renderer.py:1265)

```
Tab 5: 💼 Positions
│
render_positions_table_tab(timestamp_seconds)       dashboard_renderer.py:1265
│
├── service.get_active_positions(timestamp)         → active_positions DataFrame
├── rates_df = SQL query (rates_snapshot at timestamp)
├── all_stats = get_all_position_statistics(...)    → batch load from DB (1 query)
├── all_rebalances = get_all_rebalance_history(...) → batch load from DB (1 query)
│
└── render_positions_batch(                         position_renderers.py:304
        position_ids=[...],
        timestamp_seconds=...,
        context='standalone'
    )
    │
    ├── [infrastructure] build_rate_lookup(rates_df)      → {(protocol,token): {...}}
    ├── [infrastructure] build_oracle_prices(rates_df)    → {token: price}
    ├── [infrastructure] create_rate_helpers(...)
    │       → get_rate(token, protocol, rate_type)
    │       → get_borrow_fee(token, protocol)
    │       → get_price_with_fallback(token, protocol)
    │
    └── for each position_id:
        │
        render_position_expander(                   position_renderers.py:2001
            position=<pd.Series from DB>,
            stats=all_stats[position_id],
            rebalances=all_rebalances[position_id],
            rate_lookup=rate_lookup,
            oracle_prices=oracle_prices,
            ...
            strategy_type='perp_lending'
        )
        │
        ├── renderer = get_strategy_renderer('perp_lending')
        │               → PerpLendingRenderer
        │
        ├── renderer.validate_position_data(position)
        │
        ├── create_rate_helpers(rate_lookup, oracle_prices)
        │       (must precede title — title needs get_price_with_fallback)
        │
        ├── compute_basis_adjusted_current_apr(position, stats, get_price_with_fallback, ts)
        │       perp strategies: current_apr + basis_pnl / deployment_usd
        │       non-perp:        returns current_apr unchanged
        │
        ├── build_position_expander_title(..., current_apr_incl_basis)
        │       perp:     "Current X.XX% | Basis-adj Y.YY%"
        │       non-perp: "Current X.XX%"
        │
        └── with st.expander(title):
            │
            ├── st.caption(renderer.get_strategy_name())    → "Perp Lending"
            │
            ├── render_strategy_summary_metrics(            → metrics tiles
            │       stats, deployment_usd, strategy_type)
            │
            ├── [LIVE SEGMENT TABLE] ──────────────────────────────────────
            │   renderer.render_detail_table(               position_renderers.py:2604
            │       position,                               ← real DB position
            │       get_rate, get_borrow_fee,
            │       get_price_with_fallback,
            │       rebalances_list
            │   )
            │   └── SEE PART 5 for table construction detail
            │
            ├── [HISTORICAL SEGMENTS] (if rebalances exist)
            │   render_historical_segment(...) for each rebalance
            │
            ├── render_position_history_chart(...)          → plotly chart
            │
            └── render_position_actions_standalone(...)     → buttons
```

**Data source:** Real position record from `positions` table in DB.

---

## Part 3: Portfolio Tab — Detail Table Flow

**Entry point:** `render_portfolio2_tab()` (dashboard_renderer.py:3830)

```
Tab 6: 📂 Portfolio View
│
render_portfolio2_tab(timestamp_seconds)            dashboard_renderer.py:3830
│
├── service.get_active_positions(timestamp)         → active_positions DataFrame
├── Group by portfolio_id
│   └── portfolios_dict = {pid: portfolio_metadata}
│       └── (NULL portfolio_id → virtual '__standalone__' portfolio)
│
└── for portfolio_id, portfolio in portfolio_items:
    │
    render_portfolio_expander(                      dashboard_renderer.py:3742
        portfolio=portfolio,
        portfolio_positions=<positions for this portfolio>,
        timestamp_seconds=timestamp_seconds
    )
    │
    ├── calculate_position_summary_stats(...)       → aggregate metrics
    │
    ├── build portfolio title string
    │
    └── with st.expander(title, expanded=False):
        │
        ├── render_position_summary_stats(...)      → summary tiles
        │
        └── render_positions_batch(                 position_renderers.py:304
                position_ids=[...],
                timestamp_seconds=...,
                context='portfolio2'                ← only difference vs Positions tab
            )
            │
            └── [IDENTICAL FLOW TO POSITIONS TAB from here]
                render_position_expander(...)
                └── renderer.render_detail_table(...)
                    └── SEE PART 5 for table construction detail
```

**Data source:** Real position record from `positions` table in DB (same as Positions tab).

**Key difference from Positions tab:**
- Wrapped in an outer portfolio expander (portfolio-level aggregates)
- `context='portfolio2'` → action buttons render with portfolio context
- Otherwise table generation is **identical**

---

## Part 4: All Strategies Tab — Popup Modal Flow

**Entry point:** `display_strategies_table()` + `show_strategy_modal()` (dashboard_renderer.py:378, 646)

```
Tab 1: 📊 All Strategies
│
display_strategies_table(...)                       dashboard_renderer.py:378
│
├── Builds strategies DataFrame from analysis_cache
├── event = st.dataframe(..., on_select="rerun")
│
└── [on row click] → show_strategy_modal(strategy, timestamp_seconds)
    │
    @st.dialog("Strategy Details", width="large")   dashboard_renderer.py:646
    show_strategy_modal(strategy, timestamp_seconds)
    │
    ├── strategy_type = strategy['strategy_type']   → e.g. 'perp_lending'
    │
    ├── [APR SUMMARY TABLE via renderer]            ← previously inline; now fully migrated
    │   try:
    │       renderer_cls = get_strategy_renderer(strategy_type)
    │       renderer_cls.render_apr_summary_table(strategy, timestamp_seconds)
    │   except NotImplementedError:
    │       ← fallback (dead code — all registered types implement this method)
    │
    │   render_apr_summary_table() columns by strategy family:
    │
    │   Perp strategies (Basis Cost + Fees + Total Fees):
    │       Token Flow, Protocols, Net APR, APR 5d, APR 30d,
    │       Liq Dist, Basis Cost (%), Fees (%), Total Fees (%),
    │       Days to BE, Max Liquidity
    │
    │   Non-perp strategies (simpler — no basis):
    │       Token Flow, Protocols, Net APR, APR 5d, APR 30d,
    │       Liq Dist, Fees (%), Days to BE, Max Liquidity
    │
    │   Fees (%) breakdown by strategy type:
    │       perp_lending:            L_B × 2 × taker_fee  (no borrow fee)
    │       perp_borrowing:          L_B × 2 × taker_fee + B_A × borrow_fee_2a
    │       recursive_lending:       0.00% (fees not stored in result dict)
    │       noloop_cross_protocol:   B_A × borrow_fee_2a
    │       stablecoin_lending:      0.00% (no borrowing)
    │
    ├── [INLINE] Position Calculator:
    │   deployment_usd = st.number_input(...)       ← user input
    │
    ├── renderer_cls = get_strategy_renderer(strategy_type)
    │
    ├── mock_position = pd.Series(                  dashboard_renderer.py:~800
    │       _build_preview_position(strategy, deployment_usd)
    │   )
    │   └── _build_preview_position() maps strategy dict fields
    │       to position-record field names (entry_lend_rate_1a,
    │       entry_price_1a, entry_borrow_rate_3b, etc.)
    │
    ├── [mock rate helpers from strategy dict]
    │   _get_rate(token, protocol, rate_type)
    │   _get_borrow_fee(token, protocol)
    │   _get_price(token, protocol)
    │   _get_basis(token3_contract, token3)
    │
    ├── [DETAIL TABLE via renderer]
    │   renderer_cls.render_detail_table(           dashboard_renderer.py:~853
    │       mock_position,                          ← mock, NOT real DB position
    │       _get_rate, _get_borrow_fee, _get_price,
    │       rebalances=None,
    │       segment_type='live',
    │       get_basis=_get_basis                    ← perp-only kwarg
    │   )
    │   └── SEE PART 5 for table construction detail
    │       (same method as Positions/Portfolio tabs,
    │        different data source)
    │
    └── render historical performance chart
```

**Data source:** Mock position built from `analysis_cache` strategy dict (NOT a real DB position).

**Note:** `render_strategy_modal_table()` on PerpLendingRenderer (line 2750) is **NOT** called
from here. It is called only from the **Analysis tab** (`analysis_tab.py:170`).

---

## Part 5: render_detail_table() — PerpLendingRenderer (the actual table)

**Location:** `position_renderers.py:2604`

Called by all three contexts above with the same method signature.

```
PerpLendingRenderer.render_detail_table(
    position,                   ← pd.Series (real or mock)
    get_rate,                   ← closure: (token, protocol, rate_type) → float
    get_borrow_fee,             ← closure: (token, protocol) → float
    get_price_with_fallback,    ← closure: (token, protocol) → float or tuple
    rebalances=[...]            ← list of rebalance dicts (None in modal)
    segment_type='live'         ← 'live' or 'historical'
)
│
├── [Determine segment data source]
│   if not rebalances:
│       segment_data = build_segment_data_from_position(position)
│   else:
│       segment_data = build_segment_data_from_rebalance(rebalances[-1])
│
│   is_live_segment = segment_data['is_live_segment']
│
├── [ROW 1: Leg 1A — Spot Lend]
│   detail_data.append(
│       RecursiveLendingRenderer._build_lend_leg_row(   ← shared helper
│           position=position,
│           leg_id='leg_1a',
│           token=position['token1'],
│           protocol=position['protocol_a'],
│           weight=position['l_a'],
│           entry_rate=position['entry_lend_rate_1a'],
│           entry_price=position['entry_price_1a'],
│           get_rate=get_rate,
│           get_price_with_fallback=get_price_with_fallback,
│           deployment=deployment,
│           segment_data=segment_data,
│           segment_type=segment_type,
│           borrow_token=None,          ← no liquidation risk for lend-only leg
│           liquidation_threshold=None,
│           ...
│       )
│   )
│
├── [ROW 2: Leg 3B — Short Perp]
│   Computes:
│   ├── entry_rate_3b = position['entry_borrow_rate_3b']
│   ├── entry_price_3b = position['entry_price_3b']
│   ├── live_rate_3b = get_rate(token3, protocol_b, 'borrow_apr')
│   ├── live_price_3b = get_price_with_fallback(token3, protocol_b)
│   ├── perp_fee = get_borrow_fee(token3, protocol_b)
│   ├── liq_dist = position['entry_liquidation_distance']
│   └── perp_liq_price = entry_price_3b * (1 + liq_dist)
│       live_liq_dist = (liq_price - live_price) / live_price
│
│   if is_live_segment:
│       perp_row = {
│           'Protocol', 'Token', 'Action': 'Short Perp',
│           'Position Entry Rate (%)',    ← rate at original position open
│           'Entry Rate (%)',             ← rate at this segment open
│           'Live Rate (%)',              ← current funding rate
│           'Entry Basis',
│           'Entry Price ($)',
│           'Live Price ($)',
│           'Liquidation Price ($)',
│           'Token Amount',
│           'Token Rebalance Required',
│           'Fee Rate (%)',
│           'Entry Liquidation Distance',
│           'Live Liquidation Distance',
│           'Segment Earnings': "TBD",
│           'Segment Fees': "TBD",
│       }
│   else:  ← historical segment
│       perp_row = { ...uses 'Segment Entry Rate', 'Exit Rate', 'Exit Price',
│                        'Segment Entry Liquidation Distance', 'Exit Liquidation Distance' }
│
├── detail_df = pd.DataFrame([leg1a_row, perp_row])
└── st.dataframe(detail_df, width="stretch")
    (no styling applied — perp detail table is unstyled)
```

---

## Part 6: render_apr_summary_table() — columns and fee formulas

**Implemented for all 6 registered strategy types.** All produce a single-row table.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PERP STRATEGIES (perp_lending, perp_borrowing, perp_borrowing_recursive)    │
│ 11 columns                                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
Basis Cost (%), Fees (%), Total Fees (%), Days to BE, Max Liquidity

Basis Cost (%) — strategy['basis_cost'] × 100  (gray italic when N/A)
Fees (%)       — see per-type formula below
Total Fees (%) — strategy['total_upfront_fee'] × 100

Fees (%) per type:
    perp_lending:             L_B × 2 × BLUEFIN_TAKER_FEE
    perp_borrowing/recursive: L_B × 2 × BLUEFIN_TAKER_FEE  +  B_A × borrow_fee_2a

Note: days_to_breakeven is IDENTICAL for perp_borrowing and perp_borrowing_recursive
because the amplification factor cancels exactly (both numerator and denominator
scale by the same factor = 1/(1−r(1−d))).

Basis fields stored in strategy dict:
    perp_lending:   basis_bid (entry), basis_ask (exit)
    perp_borrowing: basis_ask (entry), basis_bid (exit)
    basis_spread = basis_ask − basis_bid (from spot_perp_basis table)

┌─────────────────────────────────────────────────────────────────────────────┐
│ NON-PERP STRATEGIES (recursive_lending, noloop_cross_protocol, stablecoin)  │
│ 9 columns — no basis columns                                                │
└─────────────────────────────────────────────────────────────────────────────┘
Token Flow, Protocols, Net APR, APR 5d, APR 30d, Liq Dist,
Fees (%), Days to BE, Max Liquidity

Fees (%) = B_A × borrow_fee_2a + B_B × borrow_fee_3b

Fees per type:
    recursive_lending:    0.00% (borrow fees not stored in result dict)
    noloop_cross_protocol: B_A × borrow_fee_2a (borrow_fee_3b = 0)
    stablecoin_lending:   0.00% (no borrowing)

Liq Dist: "N/A" when liquidation_distance == float('inf') (stablecoin_lending)
```

`format_days_to_breakeven()` lives in `dashboard/dashboard_utils.py:205` to avoid
circular imports (position_renderers.py → dashboard_utils.py, not dashboard_renderer.py).

---

## Part 6b: current_apr and current_apr_incl_basis

### current_apr  (stored in position_statistics)

Calculated in `position_statistics_calculator.py` each data-collection cycle:

```
gross_apr          = l_a * lend_1A + l_b * lend_2B - b_a * borrow_2A - b_b * borrow_3B
borrow_fee_cost    = b_a * borrow_fee_2A + b_b * borrow_fee_3B

perp_trading_fee_apr:
    perp_lending:             b_b * 2 * BLUEFIN_TAKER_FEE   (short perp leg = b_b)
    perp_borrowing/recursive: l_b * 2 * BLUEFIN_TAKER_FEE   (long perp leg  = l_b)
    all other strategies:     0.0

current_apr = gross_apr - borrow_fee_cost - perp_trading_fee_apr
```

Strategy detection uses `position['strategy_type']` — not protocol string matching.

### current_apr_incl_basis  (computed at render time, never stored)

Computed by `compute_basis_adjusted_current_apr()` in `position_renderers.py` during
`render_position_expander()`, immediately before building the expander title.

```
basis_pnl = unrealised $ PnL from spot/perp price divergence since entry

perp_lending (long spot 1a, short perp 3b):
    basis_pnl = (live_spot - entry_spot) * spot_tokens
              - (live_perp - entry_perp) * perp_tokens

perp_borrowing / perp_borrowing_recursive (short spot 2a, long perp 3b):
    basis_pnl = (live_perp - entry_perp) * perp_tokens
              - (live_spot - entry_spot) * spot_tokens

current_apr_incl_basis = current_apr + basis_pnl / deployment_usd
```

`basis_pnl / deployment_usd` is a one-time fraction of capital — no time-scaling.
Non-perp strategies: `current_apr_incl_basis = current_apr` (function returns unchanged).

---

## Summary: What is/isn't via the renderer

| Context | Table | Via renderer? | Method |
|---------|-------|--------------|--------|
| Positions tab | Position detail (legs) | ✅ Yes | `render_detail_table()` |
| Positions tab | Summary metrics tiles | ✅ Yes | `render_strategy_summary_metrics()` → `get_metrics_layout()` |
| Portfolio tab | Portfolio detail (legs) | ✅ Yes | `render_detail_table()` (via batch) |
| All Strategies modal | APR summary row — all strategies | ✅ Yes | `render_apr_summary_table()` |
| All Strategies modal | Position details (legs) | ✅ Yes | `render_detail_table()` with mock_position |
| Analysis tab | Leg details | ✅ Yes | `render_strategy_modal_table()` |

**Note on `render_strategy_modal_table()` for perp_lending (line 2750):**
Different columns from `render_detail_table()`:
- Columns: Protocol, Token, Action, Weight, Rate, APR Contrib, Entry Basis,
  Token Amount, Size ($), Price, Fees (%), Fees ($), Liq Risk, Liq Price, Liq Distance
- Has styling: `_color_apr` on APR Contrib, `_color_liq` on Liq Distance
- Only called from Analysis tab

---

## Key files

| File | Lines | Role |
|------|-------|------|
| [position_renderers.py](dashboard/position_renderers.py) | 70–155 | `StrategyRendererBase` ABC (incl. `render_apr_summary_table` stub) |
| [position_renderers.py](dashboard/position_renderers.py) | 158–210 | Registry decorator + `get_strategy_renderer()` |
| [position_renderers.py](dashboard/position_renderers.py) | 215–303 | `build_rate_lookup`, `create_rate_helpers` |
| [position_renderers.py](dashboard/position_renderers.py) | 304–413 | `render_positions_batch`, `render_position_single` |
| [position_renderers.py](dashboard/position_renderers.py) | 1174– | `RecursiveLendingRenderer` |
| [position_renderers.py](dashboard/position_renderers.py) | 1225– | `RecursiveLendingRenderer.render_apr_summary_table` |
| [position_renderers.py](dashboard/position_renderers.py) | 1949– | `FundRateArbRenderer` (stub — not implemented) |
| [position_renderers.py](dashboard/position_renderers.py) | 2001– | `render_position_expander` (main expander logic) |
| [position_renderers.py](dashboard/position_renderers.py) | 2159– | `StablecoinLendingRenderer` |
| [position_renderers.py](dashboard/position_renderers.py) | 2249– | `StablecoinLendingRenderer.render_apr_summary_table` |
| [position_renderers.py](dashboard/position_renderers.py) | 2263– | `NoLoopCrossProtocolRenderer` |
| [position_renderers.py](dashboard/position_renderers.py) | 2420– | `NoLoopCrossProtocolRenderer.render_apr_summary_table` |
| [position_renderers.py](dashboard/position_renderers.py) | 2509– | `PerpLendingRenderer` |
| [position_renderers.py](dashboard/position_renderers.py) | 2709– | `PerpLendingRenderer.render_apr_summary_table` |
| [position_renderers.py](dashboard/position_renderers.py) | 2750– | `PerpLendingRenderer.render_strategy_modal_table` (analysis tab only) |
| [position_renderers.py](dashboard/position_renderers.py) | 2856– | `PerpBorrowingRenderer` |
| [position_renderers.py](dashboard/position_renderers.py) | 3057– | `PerpBorrowingRenderer.render_apr_summary_table` |
| [position_renderers.py](dashboard/position_renderers.py) | 3136– | `PerpBorrowingRenderer.render_strategy_modal_table` (analysis tab only) |
| [dashboard_renderer.py](dashboard/dashboard_renderer.py) | 646– | `show_strategy_modal` (try renderer → inline fallback dead code) |
| [dashboard_renderer.py](dashboard/dashboard_renderer.py) | 1265– | `render_positions_table_tab` |
| [dashboard_renderer.py](dashboard/dashboard_renderer.py) | 3742– | `render_portfolio_expander` |
| [dashboard_renderer.py](dashboard/dashboard_renderer.py) | 3830– | `render_portfolio2_tab` |
| [dashboard_utils.py](dashboard/dashboard_utils.py) | 205 | `format_days_to_breakeven(days: Optional[float]) → str` |
| [perp_lending.py](analysis/strategy_calculators/perp_lending.py) | — | Stores `basis_bid`, `basis_ask` in result dict |
| [perp_borrowing.py](analysis/strategy_calculators/perp_borrowing.py) | — | Stores `basis_ask`, `basis_bid` in result dict |

---

## Part 7: Positions Tab — perp_borrowing_recursive Flowcharts

Strategy name in code: `perp_borrowing_recursive`
Renderer: `PerpBorrowingRenderer` (shared with `perp_borrowing`)

---

### Flow A — Summary Stats

```
ENTRY
  dashboard_renderer.py
  render_positions_table_tab()
      |
      | (position_ids list loaded from DB)
      v

STEP 1: CALCULATE  position_renderers.py L435
  calculate_position_summary_stats(position_ids, timestamp)
      |
      |-- SQL query 1: positions table
      |       returns: deployment_usd, entry_ts, entry_net_apr
      |
      |-- SQL query 2: position_statistics table  (dashboard_renderer.py L1151)
      |       ROW_NUMBER() window fn, latest row per position_id
      |       returns: pnl, total_earnings, base_earnings,
      |                reward_earnings, total_fees,
      |                strategy_net_apr, current_net_apr
      |
      v
  for each position:
      strategy_days  = (now - entry_ts) / 86400
      weight         = strategy_days * deployment_usd

      total_deployed     += deployment_usd
      total_pnl          += pnl
      total_earnings     += total_earnings
      base_earnings      += base_earnings
      reward_earnings    += reward_earnings
      total_fees         += total_fees

      weighted_entry_apr    += weight * entry_net_apr
      weighted_realised_apr += weight * strategy_net_apr
      weighted_current_apr  += weight * current_apr         # net of borrow fees + perp trading fees
      total_weight          += weight
      |
      v
  derived:
      ROI              = total_pnl / total_deployed * 100
      avg_entry_apr    = weighted_entry_apr    / total_weight
      avg_realised_apr = weighted_realised_apr / total_weight
      avg_current_apr  = weighted_current_apr  / total_weight
      |
      v
  returns stats dict

STEP 2: RENDER  position_renderers.py L589
  render_position_summary_stats(stats, "All Positions Summary")

      Row 1 (4 cols):  Total Deployed | Total PnL (+ ROI% delta) | Total Earnings | Base Earnings
      Row 2 (3 cols):  Reward Earnings | Fees | Avg Realised APR
      Row 3 (3 cols):  Avg Current APR
```

---

### Flow B — Details Table (perp_borrowing_recursive)

#### B1 — Batch setup (runs once for all positions on the tab)

```
ENTRY
  dashboard_renderer.py
  render_positions_table_tab()
      |
      v
  position_renderers.py L304
  render_positions_batch(position_ids, timestamp)
      |
      |-- open DB connection, init PositionService
      |
      |-- SQL query 1  get_all_position_statistics(position_ids, timestamp)
      |       -> stats_by_id  dict:  { position_id -> stats dict }
      |
      |-- SQL query 2  get_all_rebalance_history(position_ids)
      |       -> rebalances_by_id  dict:  { position_id -> [rebalance, ...] }
      |
      |-- load_historical_snapshot(timestamp)
      |       -> rates_snapshot_df  (lend_apr, borrow_apr, borrow_fee, price per protocol/token)
      |
      |-- build_rate_lookup(rates_snapshot_df)  L215
      |       -> rate_lookup  dict:  { (protocol, token) -> {lend_apr, borrow_apr, borrow_fee, price} }
      |
      |-- create lookup closures (O(1) access):
      |       get_rate(token, protocol, rate_type)
      |       get_borrow_fee(token, protocol)
      |       get_price_with_fallback(token, protocol)
      |           tier 1: protocol price
      |           tier 2: oracle price
      |           tier 3: 0.0 + warning
      |
      v
  for each position -> B2
```

#### B2 — Per-position expander

```
  position_renderers.py L2061
  render_position_expander(position, stats, rebalances, get_rate, get_borrow_fee, get_price)
      |
      |-- get_strategy_renderer('perp_borrowing_recursive')
      |       -> PerpBorrowingRenderer
      |          (registered by @register_strategy_renderer on both
      |           'perp_borrowing' and 'perp_borrowing_recursive')
      |
      |-- compute_basis_adjusted_current_apr()  (perp only)
      |-- expander title:  ...current APR [| Basis-adj APR for perp] + PnL + age
      |
      |-- render_strategy_summary_metrics(stats, deployment_usd, 'perp_borrowing_recursive')
      |     L822
      |       PerpBorrowingRenderer.get_metrics_layout()
      |           -> ['total_pnl', 'total_earnings', 'base_earnings',
      |               'reward_earnings', 'total_fees']
      |       5 st.metric() columns
      |           each shows:  $value  and  (value / deployment * 100)% delta
      |
      v
  PerpBorrowingRenderer.render_detail_table(
      position, get_rate, get_borrow_fee, get_price, rebalances)
  -> B3
```

#### B3 — Inside render_detail_table()  (L3135)

```
  SEGMENT DATA SOURCES
      Live segment:
          build_segment_data_from_position(position)
          reads entry_* columns from positions table

      Historical segments (one per rebalance):
          build_segment_data_from_rebalance(rebalance)
          reads opening_* and closing_* columns from rebalances table

  FOR EACH SEGMENT build 3 rows:

  -----------------------------------------------------------------------
  ROW 1 — Leg 1: Stablecoin Lend  (Protocol A)
  -----------------------------------------------------------------------
  helper: RecursiveLendingRenderer._build_lend_leg_row()

  columns:
      Protocol | Token | Action='Lend'
      Entry Rate | Live Rate
      Entry Price | Live Price | Liquidation Price
      Token Amount

  -----------------------------------------------------------------------
  ROW 2 — Leg 2: Spot Borrow  (Protocol A)
  -----------------------------------------------------------------------
  helper: RecursiveLendingRenderer._build_borrow_leg_row()

  columns:
      Protocol | Token | Action='Borrow'
      Entry Rate | Live Rate
      Collateral Info | Liquidation details
      Borrow Fee

  -----------------------------------------------------------------------
  ROW 3 — Leg 3: Long Perp  (Bluefin)
  -----------------------------------------------------------------------
  custom build at L3212

  key calculations:
      liq_price           = entry_price * (1 - liq_dist)
      entry_liq_distance  = -liq_dist
      live_liq_distance   = (liq_price - live_price) / live_price
      funding_rate        = get_rate(token3, 'bluefin', 'lend')
      entry_basis         = spot_price - perp_price at entry

  columns:
      Protocol='Bluefin' | Token | Action='Long Perp'
      Position Entry Rate | Segment Entry Rate | Live/Exit Funding Rate
      Entry Basis
      Entry Price | Live/Exit Price
      Liquidation Price
      Token Amount
      Fee Rate (BLUEFIN_TAKER_FEE)
      Entry Liq Distance | Live Liq Distance
      Segment Earnings | Segment Fees

  -----------------------------------------------------------------------

  FINAL RENDER
      st.dataframe([row1, row2, row3])

      live segment    ->  always visible at top
      historical segs ->  each in a collapsible expander below
```

---

### How recursive differs from non-recursive

```
  CALCULATOR  (analysis/strategy_calculators/)

  PerpBorrowingCalculator  (perp_borrowing.py)
      calculate_positions()     l_a=1.0  b_a=r  l_b=r
      calculate_gross_apr()     earnings - costs
      calculate_net_apr()       gross - perp_fees - borrow_fee - basis_cost
      analyze_strategy()        builds full result dict

      ^-- inherited by:

  PerpBorrowingRecursiveCalculator  (perp_borrowing_recursive.py)
      calculate_positions()     OVERRIDDEN
          q      = r * (1 - liq_dist)
          factor = 1 / (1 - q)         <- geometric series amplifier
          l_a = 1*factor
          b_a = r*factor
          l_b = r*factor
      analyze_strategy()        EXTENDED, adds loop_ratio + loop_amplifier to result dict
      (all other methods inherited unchanged)

  RENDERER  (dashboard/position_renderers.py)

  @register_strategy_renderer('perp_borrowing')
  @register_strategy_renderer('perp_borrowing_recursive')
  class PerpBorrowingRenderer:
      -> identical rendering for both variants
```
