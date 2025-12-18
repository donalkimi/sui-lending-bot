"""
Configuration settings for the Sui Lending Bot
"""

# Google Sheets Configuration
GOOGLE_SHEETS_ID = "1fNXulLVL4s2TBVZb0OMOgOWcqR7jL7NoVGO9-JfZ7Zg"
GOOGLE_CREDENTIALS_FILE = "config/credentials.json"

# Sheet names
SHEET_LENDS = "Protocol Lends"
SHEET_BORROWS = "Protocol Borrows"
SHEET_COLLATERAL_RATIOS = "Collateral Ratios"

# Token Configuration
STABLECOINS = ["USDC", "suiUSDT", "USDY", "AUSD", "FDUSD"]

# Strategy Parameters
DEFAULT_LIQUIDATION_DISTANCE = 0.30  # 30% default safety buffer
MIN_NET_APR_THRESHOLD = 0.5  # Minimum 0.5% net APR to consider

# Alert Configuration
SLACK_WEBHOOK_URL = "https://hooks.slack.com/triggers/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"
ALERT_RATE_SPREAD_THRESHOLD = 2.0  # Alert when spread > 2%
ALERT_NET_APR_THRESHOLD = 5.0  # Alert when net APR > 5%

# Scheduler Configuration
CHECK_INTERVAL_MINUTES = 15  # How often to check rates (default: every 15 minutes)

# Dashboard Configuration
DASHBOARD_PORT = 8501
DASHBOARD_TITLE = "Sui Lending Bot - Cross-Protocol Yield Optimizer"
