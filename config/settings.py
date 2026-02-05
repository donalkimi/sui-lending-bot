"""
Configuration settings for the Sui Lending Bot
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file (local development only)
load_dotenv()

# ==============================================================================
# HELPER FUNCTION
# ==============================================================================

def get_bool_env(key: str, default: bool = False) -> bool:
    """
    Convert environment variable string to boolean.
    
    Accepts: 'true', '1', 'yes', 'on' (case-insensitive) as True
    Accepts: 'false', '0', 'no', 'off', '' (case-insensitive) as False
    """
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

# ==============================================================================
# RAILWAY ENVIRONMENT VARIABLES
# ==============================================================================

# Now you can use the helper - much cleaner!
USE_CLOUD_DB = get_bool_env('USE_CLOUD_DB', default=True)
SUPABASE_URL = os.getenv('SUPABASE_URL')  # PostgreSQL connection string

# RPC Configuration  
SUI_RPC_URL = os.getenv('SUI_RPC_URL', 'https://side-flashy-isle.sui-mainnet.quiknode.pro/6acae20a62b8a6842e8d407b4f6d7f98372dc8bb/')

# Alert Configuration
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/triggers/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')

# ==============================================================================
# VALIDATION (Fail fast if required env vars missing)
# ==============================================================================

if USE_CLOUD_DB and not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL environment variable is required when USE_CLOUD_DB=True. "
        "Set this in Railway: Project Settings → Environment Variables"
    )

if not SLACK_WEBHOOK_URL:
    print("WARNING: SLACK_WEBHOOK_URL not set - notifications will be disabled")

# ==============================================================================
# STRATEGY PARAMETERS (Can be overridden via environment variables)
# ==============================================================================

DEFAULT_LIQUIDATION_DISTANCE = float(os.getenv('DEFAULT_LIQUIDATION_DISTANCE', '0.20'))
MIN_NET_APR_THRESHOLD = float(os.getenv('MIN_NET_APR_THRESHOLD', '-1'))
RATE_SPREAD_THRESHOLD = float(os.getenv('RATE_SPREAD_THRESHOLD', '0.00'))
ALERT_RATE_SPREAD_THRESHOLD = float(os.getenv('ALERT_RATE_SPREAD_THRESHOLD', '2.0'))
ALERT_NET_APR_THRESHOLD = float(os.getenv('ALERT_NET_APR_THRESHOLD', '5.0'))
CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '60'))
REBALANCE_THRESHOLD = float(os.getenv('REBALANCE_THRESHOLD', '0.02'))
SAVE_SNAPSHOTS = get_bool_env('SAVE_SNAPSHOTS', default=True)
# ==============================================================================
# LOCAL DEVELOPMENT ONLY
# ==============================================================================

SQLITE_PATH = "data/lending_rates.db"
DASHBOARD_PORT = 8501
DASHBOARD_TITLE = "Sui Lending Bot - Cross-Protocol Yield Optimizer"