# Sui Lending Bot - TODO Roadmap

## TODO Breakdown by Difficulty/Size

### 🟢 QUICK WINS (Small, <2 hours each)
These are straightforward improvements with minimal complexity:

#### 1. Clean up dashboard - remove contract addresses
- Simple UI change in `streamlit_app.py`
- Just remove `Contract` column from dataframe displays
- **Effort:** 15 minutes

#### 2. Clean up dashboard - add USDC filter toggle
- Add NEW toggle `force_usdc_start` to restrict strategies to USDC as token1
- This is independent from existing `force_token3_equals_token1` toggle
- Filter results in `analyze_all_combinations()` to only show strategies where token1=='USDC'
- **Effort:** 30 minutes

#### 3. Clean up Slack messaging
- Refine the message formats in `slack_notifier.py`
- Improve formatting, add emojis, better structure
- **Effort:** 1-2 hours

---

### 🟡 MEDIUM TASKS (Medium, 2-8 hours each)
These require some design decisions and moderate implementation:

#### 4. Add prices
- Protocols already return prices (check Navi: `Oracle_price`)
- Extract and display in dashboard
- Add to rate tables and strategy display
- **Effort:** 2-3 hours
- **Dependencies:** Need to verify all 3 protocols return prices

#### 5. Add in fees - find out which protocols charge fees
- Research each protocol's fee structure
- Suilend already returns `borrow_fee_bps` and `spread_fee_bps`
- Modify `position_calculator.py` to incorporate fees into APR calculations
- **Effort:** 3-4 hours
- **Research needed:** Navi and AlphaFi fee structures

#### 6. Track rates in SQL/DB each time
- Design simple schema (timestamp, protocol, token, lend_rate, borrow_rate, collateral_ratio)
- Add SQLite integration (lightweight, no external dependencies)
- Log rates after each `merge_protocol_data()` call
- **Effort:** 4-6 hours
- **Decision:** SQLite vs PostgreSQL vs time-series DB?

---

### 🔴 LARGE PROJECTS (Large, 8+ hours each)
These are complex features requiring significant architecture:

#### 7. Track positions in DB - come up with framework
- Design position schema (strategy_id, tokens, protocols, amounts, entry_time, APR, status)
- Build position lifecycle: Created → Active → Monitoring → Closed
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

Last Updated: 2025-01-08

### Phase 1: Polish & Foundation 🟢
- [ ] 1.1 - Dashboard: Remove contract addresses (15 min)
- [ ] 1.2 - Dashboard: Force USDC/token3=token1 (30 min)
- [ ] 1.3 - Slack: Clean up messaging (1-2 hrs)
- [ ] 1.4 - Dashboard: Add prices (2-3 hrs)
- [ ] 1.5 - Database: Track rates history (4-6 hrs)

**Phase 1 Progress: 0/5 complete**

---

### Phase 2: Enhanced Analytics 🟡
- [ ] 2.1 - Fees: Research & add to APR calculations (3-4 hrs)

**Phase 2 Progress: 0/1 complete**

---

### Phase 3: Position Management 🔴
- [ ] 3.1 - Database: Position tracking framework (8-12 hrs)

**Phase 3 Progress: 0/1 complete**

---

### Phase 4: Automation 🔴🔴
- [ ] 4.1 - Slack: Listening & command handling (10-15 hrs)
- [ ] 4.2 - Execution: One-click deploy (20-30 hrs)

**Phase 4 Progress: 0/2 complete**

---

## Overall Progress
**Total: 0/9 tasks complete**
- Phase 1: 0/5 ⚪⚪⚪⚪⚪
- Phase 2: 0/1 ⚪
- Phase 3: 0/1 ⚪
- Phase 4: 0/2 ⚪⚪

---

## Quick Reference
When starting a task, reference this section:

**Current Task:** _None set_

**Working On:** _Nothing in progress_

**Blocked By:** _No blockers_

**Next Up:** Start with Phase 1.1 (Dashboard cleanup - remove contracts)
