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
    price_usd DECIMAL(18,6),
    
    -- Liquidity metrics (NULL for now, add data later)
    utilization DECIMAL(10,6),
    total_supply_usd DECIMAL(18,2),
    total_borrow_usd DECIMAL(18,2),
    available_borrow_usd DECIMAL(18,2),
    
    PRIMARY KEY (timestamp, protocol, token_contract)
);

-- Indexes for rates_snapshot
CREATE INDEX IF NOT EXISTS idx_rates_time ON rates_snapshot(timestamp);
CREATE INDEX IF NOT EXISTS idx_rates_contract ON rates_snapshot(token_contract);
CREATE INDEX IF NOT EXISTS idx_rates_protocol_contract ON rates_snapshot(protocol, token_contract);


-- Table 2: reward_token_prices
-- Stores prices for reward tokens (no protocol - last write wins)
CREATE TABLE IF NOT EXISTS reward_token_prices (
    timestamp TIMESTAMP NOT NULL,
    reward_token VARCHAR(50) NOT NULL,
    reward_token_contract TEXT NOT NULL,
    reward_token_price_usd DECIMAL(18,6),
    
    PRIMARY KEY (timestamp, reward_token_contract)
);

-- Indexes for reward_token_prices
CREATE INDEX IF NOT EXISTS idx_reward_time ON reward_token_prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_reward_contract ON reward_token_prices(reward_token_contract);


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