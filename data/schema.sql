-- ============================================================================
-- Sui Lending Bot - Database Schema
-- ============================================================================

-- Table 1: rates_snapshot
-- Stores lending/borrow rates, collateral ratios, and prices for supply/borrow tokens
CREATE TABLE IF NOT EXISTS rates_snapshot (
    timestamp TIMESTAMP NOT NULL,
    protocol VARCHAR(50) NOT NULL,
    token VARCHAR(50) NOT NULL,
    token_contract TEXT NOT NULL,
    
    -- Rates (as decimals: 0.0316 = 3.16%)
    lend_base_apr DECIMAL(10,6),
    lend_reward_apr DECIMAL(10,6),
    lend_total_apr DECIMAL(10,6),
    borrow_base_apr DECIMAL(10,6),
    borrow_reward_apr DECIMAL(10,6),
    borrow_total_apr DECIMAL(10,6),
    
    -- Collateral
    collateral_ratio DECIMAL(10,6),
    liquidation_threshold DECIMAL(10,6),
    
    -- Supply/borrow token price
    price_usd DECIMAL(20,10),
    
    -- Liquidity metrics
    utilization DECIMAL(10,6),
    total_supply_usd DECIMAL(20,10),
    total_borrow_usd DECIMAL(20,10),
    available_borrow_usd DECIMAL(20,10),
    
    -- Reward token details (optional, per protocol)
    reward_token VARCHAR(50),
    reward_token_contract TEXT,
    reward_token_price_usd DECIMAL(20,10),
    
    -- Metadata
    market TEXT,
    side TEXT,
    
    -- Composite primary key for PostgreSQL ON CONFLICT support
    PRIMARY KEY (timestamp, protocol, token_contract)
);

-- Indexes for rates_snapshot
CREATE INDEX IF NOT EXISTS idx_rates_time ON rates_snapshot(timestamp);
CREATE INDEX IF NOT EXISTS idx_rates_contract ON rates_snapshot(token_contract);
CREATE INDEX IF NOT EXISTS idx_rates_protocol_contract ON rates_snapshot(protocol, token_contract);


-- Table 2: token_registry
-- Stores every token contract (coin type) seen by the bot, and optional mappings to pricing IDs.
-- pyth_id / coingecko_id are nullable and can be populated over time.
CREATE TABLE IF NOT EXISTS token_registry (
    token_contract TEXT PRIMARY KEY,
    symbol TEXT,
    pyth_id TEXT,
    coingecko_id TEXT,

    seen_on_navi INTEGER DEFAULT 0,
    seen_on_alphafi INTEGER DEFAULT 0,
    seen_on_suilend INTEGER DEFAULT 0,

    seen_as_reserve INTEGER DEFAULT 0,
    seen_as_reward_lend INTEGER DEFAULT 0,
    seen_as_reward_borrow INTEGER DEFAULT 0,

    first_seen TIMESTAMP,
    last_seen TIMESTAMP
);

-- Indexes for token_registry
CREATE INDEX IF NOT EXISTS idx_token_registry_last_seen ON token_registry(last_seen);
CREATE INDEX IF NOT EXISTS idx_token_registry_pyth_id ON token_registry(pyth_id);
CREATE INDEX IF NOT EXISTS idx_token_registry_coingecko_id ON token_registry(coingecko_id);


-- Table 3: reward_token_prices
-- Stores prices for reward tokens (no protocol - last write wins)
CREATE TABLE IF NOT EXISTS reward_token_prices (
    timestamp TIMESTAMP NOT NULL,
    reward_token VARCHAR(50) NOT NULL,
    reward_token_contract TEXT NOT NULL,
    reward_token_price_usd DECIMAL(20,10) NOT NULL,
    
    PRIMARY KEY (timestamp, reward_token_contract)
);

-- Indexes for reward_token_prices
CREATE INDEX IF NOT EXISTS idx_reward_prices_time ON reward_token_prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_reward_prices_contract ON reward_token_prices(reward_token_contract);


-- View: all_token_prices
-- Unified view of supply/borrow + reward token prices
CREATE VIEW IF NOT EXISTS all_token_prices AS
SELECT 
    timestamp,
    token,
    token_contract,
    price_usd,
    protocol,
    'supply_borrow' as source
FROM rates_snapshot

UNION

SELECT 
    timestamp,
    reward_token as token,
    reward_token_contract as token_contract,
    reward_token_price_usd as price_usd,
    NULL as protocol,
    'reward' as source
FROM reward_token_prices;