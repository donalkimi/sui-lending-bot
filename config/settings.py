"""
Configuration settings for the Sui Lending Bot
"""

# RPC Configuration
SUI_RPC_URL = "https://side-flashy-isle.sui-mainnet.quiknode.pro/6acae20a62b8a6842e8d407b4f6d7f98372dc8bb/"

# Strategy Parameters
DEFAULT_LIQUIDATION_DISTANCE = 0.20  # 315 default safety buffer
MIN_NET_APR_THRESHOLD = -10.5  # Minimum 0.5% net APR to consider
RATE_SPREAD_THRESHOLD = 0.01  # Strategies must have at least 1% spread (lend_rate - borrow_rate)

# Alert Configuration
SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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"
ALERT_RATE_SPREAD_THRESHOLD = 2.0  # Alert when spread > 2%
ALERT_NET_APR_THRESHOLD = 5.0  # Alert when net APR > 5%

# Scheduler Configuration
CHECK_INTERVAL_MINUTES = 15  # Daytime: 15min (8am-6pm), Nighttime: 2hr (6pm-8am)

# Dashboard Configuration
DASHBOARD_PORT = 8501
DASHBOARD_TITLE = "Sui Lending Bot - Cross-Protocol Yield Optimizer"

# Database Configuration
USE_CLOUD_DB = False  # Set to True to use Supabase PostgreSQL
SQLITE_PATH = "data/lending_rates.db"
SUPABASE_URL = None  # Set this when ready: "postgresql://postgres.xxx:..."
# Example: SUPABASE_URL = "postgresql://postgres.abc123:[password]@db.xxx.supabase.co:5432/postgres"

# Rebalancing Settings
# REBALANCE_THRESHOLD: Trigger auto-rebalance detection when liquidation distance changes by this amount
#
# Formula: abs(entry_liq_dist) - abs(current_liq_dist) < REBALANCE_THRESHOLD
#
# Example: 0.02 means the dashboard will show a warning when liq distance changes by more than 2%
#
# Note: Manual rebalance button does NOT check this threshold - user can rebalance anytime.
# This threshold is only used for auto-detection warnings (Phase 5, future implementation).
#
# Recommended values:
#   - Conservative: 0.01 (1%) - More frequent warnings
#   - Moderate: 0.02 (2%) - Balanced approach (default)
#   - Relaxed: 0.05 (5%) - Fewer warnings
REBALANCE_THRESHOLD = 0.02
# Database Settings
SAVE_SNAPSHOTS = True  # Set to False to disable database tracking