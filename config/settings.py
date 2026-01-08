"""
Configuration settings for the Sui Lending Bot
"""


# Strategy Parameters
DEFAULT_LIQUIDATION_DISTANCE = 0.15  # 315 default safety buffer
MIN_NET_APR_THRESHOLD = -10.5  # Minimum 0.5% net APR to consider

# Alert Configuration
SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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"
ALERT_RATE_SPREAD_THRESHOLD = 2.0  # Alert when spread > 2%
ALERT_NET_APR_THRESHOLD = 5.0  # Alert when net APR > 5%

# Scheduler Configuration
CHECK_INTERVAL_MINUTES = 15  # How often to check rates (default: every 15 minutes)

# Dashboard Configuration
DASHBOARD_PORT = 8501
DASHBOARD_TITLE = "Sui Lending Bot - Cross-Protocol Yield Optimizer"

# Database Configuration
USE_CLOUD_DB = False  # Set to True to use Supabase PostgreSQL
SQLITE_PATH = "data/lending_rates.db"
SUPABASE_URL = None  # Set this when ready: "postgresql://postgres.xxx:..."
# Example: SUPABASE_URL = "postgresql://postgres.abc123:[password]@db.xxx.supabase.co:5432/postgres"

# Database Settings
SAVE_SNAPSHOTS = True  # Set to False to disable database tracking