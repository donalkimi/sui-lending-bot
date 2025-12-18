# Changelog

## v1.1 - Market Neutral Enforcement (2024-12-17)

### 🔴 CRITICAL FIX: Market Neutral Strategy

**Problem**: The original implementation could start strategies by lending volatile tokens (like DEEP, WAL), which creates directional price exposure and liquidation risk.

**Solution**: Enforced that all strategies must start by lending a stablecoin to remain market neutral.

### Changes:

#### `analysis/rate_analyzer.py`
- **Line ~104**: Added filter to enforce `token1` must be in `STABLECOINS` list
- Updated docstring to clarify market neutral requirement
- Added warning message during analysis

#### `analysis/position_calculator.py`
- Updated `calculate_positions()` docstring to emphasize token1 = stablecoin, token2 = high-yield token
- Updated `analyze_strategy()` docstring to clarify token roles
- Added comments explaining market neutrality

#### New Documentation:
- **STRATEGY_EXPLANATION.md**: Comprehensive explanation of the market-neutral strategy
  - Why starting with stablecoin is critical
  - How the strategy maintains zero net exposure
  - Where the yield comes from (high-yield token spreads)
  - Example calculations and risk management

#### Updated Documentation:
- **README.md**: Updated strategy overview to emphasize market neutral approach

### Impact:

**Before**: 
- Bot could recommend strategies like "Lend DEEP, Borrow USDY"
- These strategies had price exposure to DEEP
- Risk of liquidation if DEEP price dropped

**After**:
- Bot only recommends strategies like "Lend USDY, Borrow DEEP"
- Maintains zero net exposure to volatile token prices
- Only liquidation risk is from extreme volatility, not directional moves

### Migration:

No action required. The bot automatically filters strategies correctly. Your existing Google Sheets data structure remains unchanged.

---

## v1.0 - Initial Release (2024-12-16)

### Features:
- Google Sheets integration for rate data
- Recursive position calculator
- Net APR calculation engine
- Bidirectional protocol pair analysis
- Streamlit dashboard
- Slack notifications
- Setup verification script
- Comprehensive documentation

### Components:
- `data/sheets_reader.py` - Google Sheets API integration
- `analysis/position_calculator.py` - Position size calculations
- `analysis/rate_analyzer.py` - Strategy finder
- `alerts/slack_notifier.py` - Slack integration
- `dashboard/streamlit_app.py` - Web dashboard
- `main.py` - Orchestration and scheduling
