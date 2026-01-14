# Sui Lending Bot - TODO Roadmap

## TODO Breakdown by Difficulty/Size

### 🟢 QUICK WINS (Small, <2 hours each)
These are straightforward improvements with minimal complexity:

#### ~~1. Clean up dashboard - remove contract addresses~~
- ~~Simple UI change in `streamlit_app.py`~~
- ~~Just remove `Contract` column from dataframe displays~~
- ~~**Effort:** 15 minutes~~
- ✅ **COMPLETED**

#### ~~2. Clean up dashboard - add USDC filter toggle~~
- ~~Add NEW toggle `force_usdc_start` to restrict strategies to USDC as token1~~
- ~~This is independent from existing `force_token3_equals_token1` toggle~~
- ~~Filter results in dashboard to only show strategies where token1=='USDC'~~
- ~~**Effort:** 30 minutes~~
- ✅ **COMPLETED**

#### ~~3. Clean up Slack messaging~~
- ~~Refine the message formats in `slack_notifier.py`~~
- ~~Improve formatting, add emojis, better structure~~
- ~~**Effort:** 1-2 hours~~
- ✅ **COMPLETED**

#### ~~10. Add liquidity metrics to dashboard~~
- ~~Add AvailableBorrowUSD to dashboard and main.py (similar to how prices were added)~~
- ~~Add TotalSupply column~~
- ~~Add Utilization column~~
- ~~**Effort:** 1-2 hours~~
- ✅ **COMPLETED**

#### 13. Incorporate enhanced liquidity and fees into APR display strategy
- **Decision Point:** How to display and use the various APR metrics we've built
  - APR30 (30-day holding period accounting for upfront fees)
  - Levered vs Unlevered APR (already toggleable in dashboard)
  - Fee-adjusted APR calculations
- **Enhanced Liquidity Metrics:**
  - Projected APR change given deposit size
  - "How much supply needed to decrease lending rate by 1%"
  - "How much borrow before borrow rate increases by 1%"
  - Display impact analysis for different position sizes
  - Add liquidity depth visualization
- **Fee Integration:**
  - Incorporate borrow fees into position_calculator.py APR calculations
  - Build APR30 metric (annualized return over 30-day period net of fees)
  - Add fee impact analysis to strategy details
- **Display Strategy:**
  - Determine which metrics to show by default
  - Design UI/UX for switching between different APR views
  - Decide on Slack notification strategy (which APR to highlight)
- **Effort:** 4-6 hours
- **Dependencies:** Tasks 5 (fees) and 10 (basic liquidity) complete

#### ~~12. Dashboard enhancements - leverage/looping toggle~~
- ~~Add "No leverage/looping" toggle to switch between levered and unlevered APR display~~
- ~~Create helper function `get_apr_value()` to return appropriate APR based on toggle~~
- ~~Modify `display_strategy_details()` to conditionally show 3 rows (unlevered) or 4 rows (levered)~~
- ~~Update all tabs (1, 2, 4) to show correct token flow: token1→token2 for unlevered, token1→token2→token3 for levered~~
- ~~Update sorting and filtering to work with both APR columns~~
- ~~Enhance Slack notifications with third table showing top unlevered strategies (9 total rows)~~
- ~~**Effort:** 2-3 hours~~
- ✅ **COMPLETED**

---

### 🟡 MEDIUM TASKS (Medium, 2-8 hours each)
These require some design decisions and moderate implementation:

#### ~~4. Add prices~~
- ~~Protocols already return prices (check Navi: `Oracle_price`)~~
- ~~Extract and display in dashboard~~
- ~~Add to rate tables and strategy display~~
- ~~**Effort:** 2-3 hours~~
- ~~**Dependencies:** Need to verify all 3 protocols return prices~~
- ✅ **COMPLETED**

#### ~~5. Add in fees - find out which protocols charge fees~~
- ~~Research each protocol's fee structure~~
- ~~Suilend already returns `borrow_fee_bps` and `spread_fee_bps`~~
- ~~Navi and AlphaFi fee structures documented~~
- ~~Fees collected and available in data pipeline~~
- ~~**Effort:** 3-4 hours~~
- ✅ **COMPLETED**
- **Note:** Fees are collected but not yet incorporated into APR calculations (see Task 13)

#### ~~6. Track rates in SQL/DB each time~~
- ~~Design simple schema (timestamp, protocol, token, lend_rate, borrow_rate, collateral_ratio)~~
- ~~Add SQLite integration (lightweight, no external dependencies)~~
- ~~Log rates after each `merge_protocol_data()` call~~
- ~~**Effort:** 4-6 hours~~
- ~~**Decision:** SQLite vs PostgreSQL vs time-series DB?~~
- ✅ **COMPLETED**

#### 11. Add time-adjusted APR metrics (accounting for upfront fees)
- Add 10-day APR, 30-day APR, 90-day APR calculations
- Account for upfront fees amortized over holding period
- Formula: `(quoted_apr/365*days - fee_bps/10000) / days * 365`
- Example: 36.5% APR with 30bps fee over 10 days = `(0.365/365*10 - 0.003)/10*365`
- Display alongside standard APR in strategy details
- **Effort:** 2-3 hours
- **Dependencies:** Task 13 (display strategy decision must be made first)
- **Note:** Core APR30 calculation will be built in Task 13; this task focuses on 10/30/90-day variants and additional display options

---

### 🔴  LARGE PROJECTS (Large, 8+ hours each)
These are complex features requiring significant architecture:

#### 7. Track positions in DB - come up with framework
- Design position schema (strategy_id, tokens, protocols, amounts, entry_time, APR, status)
- Build position lifecycle: Created Ã¢â€ â€™ Active Ã¢â€ â€™ Monitoring Ã¢â€ â€™ Closed
- Add position management functions (create, update, close)
- Dashboard integration to display active positions
- **Effort:** 8-12 hours
- **Complexity:** Requires careful data modeling

#### 8. Slack listening functionality - update rates/check positions
- Set up Slack Events API or Socket Mode
- Parse slash commands or mentions
- Implement command handlers (e.g., `/rates`, `/positions`, `/best`)
- Add authentication/authorization
- **Effort:** 10-15 hours
- **Complexity:** Requires Slack app setup, webhooks, event handling

#### 9. One-click deploy strategy + position tracking
- Build transaction construction for each protocol
- Integrate with Sui wallet (CLI or browser extension)
- Execute multi-step strategy atomically
- Link deployed position to tracking system (#7)
- Handle errors, rollbacks, confirmations
- **Effort:** 20-30 hours
- **Complexity:** HIGHEST - requires blockchain integration, wallet management, transaction signing
- **Dependencies:** Needs position tracking framework (#7) first

---

## ONE-PAGER: Progress Tracker

Last Updated: 2026-01-13

### Phase 1: Polish & Foundation 🟢
- [x] 1 - Dashboard: Remove contract addresses (15 min) ✅ *07Jan*
- [x] 2 - Dashboard: Add USDC first deposit toggle (30 min) ✅ *07Jan*
- [x] 3 - Slack: Clean up messaging (1-2 hrs) ✅ *13Jan*
- [x] 4 - Dashboard: Add prices (2-3 hrs) ✅ *07Jan*
- [x] 6 - Database: Track rates history (4-6 hrs) ✅ *08Jan*
- [x] 10 - Dashboard: Add liquidity metrics (1-2 hrs) ✅ *13Jan*
- [x] 12 - Dashboard: Leverage/looping toggle (2-3 hrs) ✅ *13Jan*

**Phase 1 Progress: 7/7 complete ✅**

---

### Phase 2: Enhanced Analytics 🟡
- [x] 5 - Fees: Research & collect fee data (3-4 hrs) ✅ *13Jan*
- [ ] 13 - Enhanced liquidity & fees APR display strategy (4-6 hrs)
- [ ] 11 - Time-adjusted APR variants (2-3 hrs)

**Phase 2 Progress: 1/3 complete**

---

### Phase 3: Position Management 🔴
- [ ] 7 - Database: Position tracking framework (8-12 hrs)

**Phase 3 Progress: 0/1 complete**

---

### Phase 4: Automation 🔴🔴
- [ ] 8 - Slack: Listening & command handling (10-15 hrs)
- [ ] 9 - Execution: One-click deploy (20-30 hrs)

**Phase 4 Progress: 0/2 complete**

---

## Overall Progress
**Total: 8/13 tasks complete**
- Phase 1: 7/7 🟢🟢🟢🟢🟢🟢🟢 ✅ **COMPLETE**
- Phase 2: 1/3 🟡⚪⚪
- Phase 3: 0/1 ⚪
- Phase 4: 0/2 ⚪⚪

---

## Quick Reference
When starting a task, reference this section:

**Current Task:** _None set_

**Working On:** _Nothing in progress_

**Blocked By:** _No blockers_

**Next Up:** Moving to Phase 3 - Position Management! 🔴
- **Task 7 (Position tracking framework)** - NEXT PRIORITY
  - Design position schema and lifecycle management
  - Build foundation for active position monitoring
  - Prerequisite for one-click deploy (Task 9)

**On Hold (Phase 2):**
- Task 13 (Enhanced liquidity & fees display strategy)
- Task 11 (Time-adjusted APR variants)

---

<!-- 
EDITING RULES FOR THIS TODO FILE:
✅ Never delete anything unless explicitly requested
✅ Mark completed tasks with strikethrough ~~like this~~
✅ Keep sequential numbering (1, 2, 3, 4...) - don't renumber when tasks complete
✅ Maintain mapping between detailed tasks and the one-pager progress tracker
✅ Update "Last Updated" date when making changes
✅ Update phase progress counts when tasks are completed
✅ EMOJI ENCODING: Always use proper Unicode emojis (🟢🟡ðŸ”´✅⚪). If emojis appear garbled (🟢Ã¢Å“â€¦⚪), fix with: sed 's/🟢/🟢/g; s/🟡/🟡/g; s/🔴/ðŸ”´/g; s/Ã¢Å“â€¦/✅/g; s/⚪/⚪/g' TODO.md
-->