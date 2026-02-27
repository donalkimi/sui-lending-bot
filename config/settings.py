"""
Configuration settings for the Sui Lending Bot
"""
import os
from dotenv import load_dotenv
from config.stablecoins import STABLECOIN_SYMBOLS

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
SUI_RPC_URL = os.getenv('SUI_RPC_URL', 'https://rpc.mainnet.sui.io')
SUI_FALLBACK_RPC_URL = os.getenv('SUI_FALLBACK_RPC_URL', 'https://sui-rpc.publicnode.com')

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
REBALANCE_THRESHOLD = float(os.getenv('REBALANCE_THRESHOLD', '0.05'))
SAVE_SNAPSHOTS = get_bool_env('SAVE_SNAPSHOTS', default=True)

# ==============================================================================
# BLUEFIN PERPETUAL MARKETS (added 2026-02-17)
# ==============================================================================

# Whitelisted Bluefin perpetual markets to track
# All markets are <BASE>-PERP format, priced in USDC
# Rates are stored as annualized decimals per DESIGN_NOTES.md #7
BLUEFIN_PERP_MARKETS = [
    "BTC",   # Bitcoin perpetual
    "ETH",   # Ethereum perpetual
    "SOL",   # Solana perpetual
    "SUI",   # Sui perpetual
    "WAL",   # Walrus perpetual
    "DEEP",  # DeepBook perpetual
]

# ==============================================================================
# BLUEFIN AMM AGGREGATOR (added 2026-02-23)
# ==============================================================================

# Aggregator endpoint for spot price discovery across all SUI DEXes
BLUEFIN_AGGREGATOR_BASE_URL = "https://aggregator.api.sui-prod.bluefin.io"

# All AMM sources to include in aggregated quotes
BLUEFIN_AGGREGATOR_SOURCES = [
    "suiswap", "turbos", "cetus", "bluemove", "kriya", "kriya_v3",
    "aftermath", "deepbook_v3", "flowx", "flowx_v3", "bluefin",
    "springsui", "obric", "stsui", "steamm", "steamm_oracle_quoter",
    "steamm_oracle_quoter_v2", "magma", "haedal_pmm", "momentum",
    "sevenk_v1", "fullsail", "cetus_dlmm", "ferra_dlmm", "ferra_clmm", "RFQ"
]

# Fixed USDC input amount for the USDC→X offer query (100 USDC, 6 decimals)
BLUEFIN_AMM_USDC_AMOUNT_RAW = 100_000_000

# ==============================================================================
# BLUEFIN PERPETUAL FEES (added 2026-02-18)
# ==============================================================================

# Bluefin trading fees (as decimals, not basis points)
# Maker fee: paid when providing liquidity (limit orders that rest in book)
# Taker fee: paid when taking liquidity (market orders or immediate fills)
BLUEFIN_MAKER_FEE = 0.0001   # 0.01% = 1 basis point
BLUEFIN_TAKER_FEE = 0.00035  # 0.035% = 3.5 basis points

# Conservative assumption: Pay taker fee on both entry and exit
# Actual fees may be lower if using maker orders
# Total upfront cost = 2 × BLUEFIN_TAKER_FEE = 0.07% of position size

# ==============================================================================
# BLUEFIN PERP TO LENDING TOKEN MAPPING (added 2026-02-18)
# ==============================================================================

# Maps Bluefin perpetual markets to compatible spot lending tokens
# Format: {perp_proxy_contract: [spot_token_contract1, spot_token_contract2, ...]}
# Only includes tokens with pyth_id OR coingecko_id in token_registry
# Generated from token_registry table - regenerate when new tokens are added

BLUEFIN_TO_LENDINGS = {
    '0xBTC-USDC-PERP_bluefin': [
        '0x3e8e9423d80e1774a7ca128fccd8bf5f1f7753be658c5e645929037f7c819040::lbtc::LBTC',
        '0x41f9f9344cac094454cd574e333c4fdb132d7bcc9379bcd4aab485b2a63942::wbtc::WBTC',
        '0x876a4b7bce8aeaef60464c11f4026903e9afacab79b9b142686158aa86560b50::xbtc::XBTC',
        '0xaafb102dd0902f5055cadecd687fb5b71ca82ef0e0285d90afde828ec58ca96b::btc::BTC',
    ],
    '0xDEEP-USDC-PERP_bluefin': [
        '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP',
    ],
    '0xETH-USDC-PERP_bluefin': [
        '0xaf8cd5edc19c4512f4259f0bee101a40d41ebed738ade5874359610ef8eeced5::coin::COIN',
        '0xd0e89b2af5e4910726fbcd8b8dd37bb79b29e5f83f7491bca830e94f7f226d29::eth::ETH',
    ],
    '0xSOL-USDC-PERP_bluefin': [
        '0xb7844e289a8410e50fb3ca48d69eb9cf29e27d223ef90353fe1bd8e27ff8f3f8::coin::COIN',
    ],
    '0xSUI-USDC-PERP_bluefin': [
        '0x0000000000000000000000000000000000000000000000000000000000000002::sui::SUI',
        '0x2::sui::SUI',
        '0x549e8b69270defbfafd4f94e17ec44cdbdd99820b33bda2278dea3b9a32d3f55::cert::CERT',
        '0x83556891f4a0f233ce7b05cfe7f957d4020492a34f5405b2cb9377d060bef4bf::spring_sui::SPRING_SUI',
        '0xbde4ba4c2e274a60ce15c1cfff9e5c42e41654ac8b6d906a57efa4bd3c29f47d::hasui::HASUI',
        '0xd1b72982e40348d069bb1ff701e634c117bb5f741f44dff91e472d3b01461e55::stsui::STSUI',
        '0xf325ce1300e8dac124071d3152c5c5ee6174914f8bc2161e88329cf579246efc::afsui::AFSUI',
    ],
    '0xWAL-USDC-PERP_bluefin': [
        '0x356a26eb9e012a68958082340d4c4116e7f55615cf27affcff209cf0ae544f59::wal::WAL',
        '0x8b4d553839b219c3fd47608a0cc3d5fcc572cb25d41b7df3833208586a8d2470::hawal::HAWAL',
        '0xb1b0650a8862e30e3f604fd6c5838bc25464b8d3d827fbd58af7cb9685b832bf::wwal::WWAL',
    ],
}

# ==============================================================================
# ENABLED PROTOCOLS (added for Part 2 of Bluefin integration)
# ==============================================================================

# List of enabled lending/perp protocols to fetch and merge
# This controls which protocols are included in rate snapshots
ENABLED_PROTOCOLS = [
    "Navi",
    "AlphaFi",
    "Suilend",
    "ScallopLend",
    "ScallopBorrow",
    "Pebble",
    "Bluefin"  # Perp funding rates from perp_margin_rates table
]

# ==============================================================================
# PORTFOLIO ALLOCATION SETTINGS
# ==============================================================================

# Portfolio allocation feature flags
# DEBUG: Switch to disable iterative liquidity updates (for testing/comparison only)
# Once validated, this will be removed and iterative updates will be always-on
DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES = get_bool_env('DEBUG_ENABLE_ITERATIVE_LIQUIDITY_UPDATES', default=True)

# Stablecoin preference multipliers (1.0 = preferred, lower = penalty)
# Applied to strategy APR when ranking for portfolio allocation
# Uses canonical stablecoin list from config/stablecoins.py
DEFAULT_STABLECOIN_PREFERENCES = {
    'USDC': 1.00,      # Preferred stablecoin (no penalty)
    'USDY': 0.95,      # 5% APR penalty
    'AUSD': 0.90,      # 10% APR penalty
    'FDUSD': 0.90,     # 10% APR penalty
    'suiUSDT': 0.90,   # 10% APR penalty
}

# Default allocation constraints for portfolio construction
DEFAULT_ALLOCATION_CONSTRAINTS = {
    'token_exposure_limit': 0.30,       # Default: Max 30% exposure to any single token
    'token_exposure_overrides': {},     # Per-token overrides {token_symbol: limit}
                                         # Example: {'USDC': 1.00, 'USDT': 0.60}
    'protocol_exposure_limit': 0.40,    # Max 40% exposure to any single protocol
    'max_single_allocation_pct': 0.40,  # Max 40% of portfolio to any single strategy
    'max_strategies': 5,                 # Max number of strategies in portfolio
    'min_apy_confidence': 0.70,         # Min 70% confidence threshold
    'apr_weights': {                     # Weights for blended APR calculation
        'net_apr': 0.30,                 # Current net APR weight
        'apr5': 0.30,                    # 5-day average APR weight
        'apr30': 0.30,                   # 30-day average APR weight
        'apr90': 0.10,                   # 90-day average APR weight
    },
    'stablecoin_preferences': DEFAULT_STABLECOIN_PREFERENCES  # Stablecoin multipliers
}

# ==============================================================================
# LOCAL DEVELOPMENT ONLY
# ==============================================================================

SQLITE_PATH = "data/lending_rates.db"
DASHBOARD_PORT = 8501
DASHBOARD_TITLE = "Sui Lending Bot - Cross-Protocol Yield Optimizer"
DEFAULT_DEPLOYMENT_USD = float(os.getenv('DEFAULT_DEPLOYMENT_USD', '100'))