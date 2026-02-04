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

    -- Fees
    borrow_fee DECIMAL(10,6),

    -- Borrow weights (multiplier for borrowed assets, default 1.0)
    borrow_weight DECIMAL(10,6),

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


-- Table 4: positions
-- Stores paper trading position records (Phase 1) with support for real capital (Phase 2)
CREATE TABLE IF NOT EXISTS positions (
    -- Position Identification
    position_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('active', 'closed', 'liquidated')),
    strategy_type TEXT NOT NULL DEFAULT 'recursive_lending',

    -- Phase 1/2 flags
    is_paper_trade BOOLEAN NOT NULL DEFAULT TRUE,
    user_id TEXT,  -- Nullable for Phase 1 (single user), required for multi-user

    -- Strategy Details (all positions are 4-leg levered)
    token1 TEXT NOT NULL,
    token2 TEXT NOT NULL,
    token3 TEXT NOT NULL,
    token1_contract TEXT NOT NULL,
    token2_contract TEXT NOT NULL,
    token3_contract TEXT NOT NULL,
    protocol_A TEXT NOT NULL,
    protocol_B TEXT NOT NULL,

    -- Entry Timestamp (references rates_snapshot timestamp)
    entry_timestamp TIMESTAMP NOT NULL,

    -- Position Sizing (normalized multipliers, scale by deployment_usd for USD amounts)
    deployment_usd DECIMAL(20, 10) NOT NULL,
    L_A DECIMAL(10, 6) NOT NULL,  -- Lend multiplier at Protocol A
    B_A DECIMAL(10, 6) NOT NULL,  -- Borrow multiplier at Protocol A
    L_B DECIMAL(10, 6) NOT NULL,  -- Lend multiplier at Protocol B
    B_B DECIMAL(10, 6) NOT NULL,  -- Borrow multiplier at Protocol B (4th leg)

    -- Entry Rates (as decimals: 0.0316 = 3.16%)
    entry_lend_rate_1A DECIMAL(10, 6) NOT NULL,
    entry_borrow_rate_2A DECIMAL(10, 6) NOT NULL,
    entry_lend_rate_2B DECIMAL(10, 6) NOT NULL,
    entry_borrow_rate_3B DECIMAL(10, 6) NOT NULL,

    -- Entry Prices (leg-level for Step 6)
    entry_price_1A DECIMAL(20, 10) NOT NULL,
    entry_price_2A DECIMAL(20, 10) NOT NULL,
    entry_price_2B DECIMAL(20, 10) NOT NULL,
    entry_price_3B DECIMAL(20, 10) NOT NULL,

    -- Entry Collateral Ratios
    entry_collateral_ratio_1A DECIMAL(10, 6) NOT NULL,
    entry_collateral_ratio_2B DECIMAL(10, 6) NOT NULL,

    -- Entry Liquidation Thresholds
    entry_liquidation_threshold_1A DECIMAL(10, 6) NOT NULL,
    entry_liquidation_threshold_2B DECIMAL(10, 6) NOT NULL,

    -- Entry Strategy APRs (fee-adjusted for different time horizons)
    entry_net_apr DECIMAL(10, 6) NOT NULL,
    entry_apr5 DECIMAL(10, 6) NOT NULL,
    entry_apr30 DECIMAL(10, 6) NOT NULL,
    entry_apr90 DECIMAL(10, 6) NOT NULL,
    entry_days_to_breakeven DECIMAL(10, 2),  -- NULL for backwards compatibility
    entry_liquidation_distance DECIMAL(10, 6) NOT NULL,

    -- Entry Liquidity & Fees
    entry_max_size_usd DECIMAL(20, 10),
    entry_borrow_fee_2A DECIMAL(10, 6),
    entry_borrow_fee_3B DECIMAL(10, 6),

    -- Entry Borrow Weights (captured at entry, remain constant per assumption)
    entry_borrow_weight_2A DECIMAL(10, 6),
    entry_borrow_weight_3B DECIMAL(10, 6),

    -- Slippage Placeholders (for Phase 2)
    expected_slippage_bps DECIMAL(10, 2),
    actual_slippage_bps DECIMAL(10, 2),

    -- Rebalance Tracking
    accumulated_realised_pnl DECIMAL(20, 10) DEFAULT 0.0,
    rebalance_count INTEGER DEFAULT 0,
    last_rebalance_timestamp TIMESTAMP,

    -- Closure Tracking
    close_timestamp TIMESTAMP,
    close_reason TEXT,
    close_notes TEXT,

    -- User Notes
    notes TEXT,

    -- Phase 2 Placeholders (for real capital deployment)
    wallet_address TEXT,
    transaction_hash_open TEXT,
    transaction_hash_close TEXT,
    on_chain_position_id TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for positions
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_protocols ON positions(protocol_A, protocol_B);
CREATE INDEX IF NOT EXISTS idx_positions_tokens ON positions(token1, token2, token3);
CREATE INDEX IF NOT EXISTS idx_positions_is_paper ON positions(is_paper_trade);


-- Table 5: position_rebalances
-- Stores historical position segments created through rebalancing
-- Follows event sourcing pattern: records are immutable historical truth
CREATE TABLE IF NOT EXISTS position_rebalances (
    -- Rebalance Identification
    rebalance_id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,

    -- Timing
    opening_timestamp TIMESTAMP NOT NULL,
    closing_timestamp TIMESTAMP NOT NULL,

    -- Position State (multipliers - constant during segment)
    deployment_usd DECIMAL(20, 10) NOT NULL,
    L_A DECIMAL(10, 6) NOT NULL,
    B_A DECIMAL(10, 6) NOT NULL,
    L_B DECIMAL(10, 6) NOT NULL,
    B_B DECIMAL(10, 6) NOT NULL,

    -- Opening State (rates, prices)
    opening_lend_rate_1A DECIMAL(10, 6) NOT NULL,
    opening_borrow_rate_2A DECIMAL(10, 6) NOT NULL,
    opening_lend_rate_2B DECIMAL(10, 6) NOT NULL,
    opening_borrow_rate_3B DECIMAL(10, 6) NOT NULL,
    opening_price_1A DECIMAL(20, 10) NOT NULL,
    opening_price_2A DECIMAL(20, 10) NOT NULL,
    opening_price_2B DECIMAL(20, 10) NOT NULL,
    opening_price_3B DECIMAL(20, 10) NOT NULL,

    -- Closing State (rates, prices)
    closing_lend_rate_1A DECIMAL(10, 6) NOT NULL,
    closing_borrow_rate_2A DECIMAL(10, 6) NOT NULL,
    closing_lend_rate_2B DECIMAL(10, 6) NOT NULL,
    closing_borrow_rate_3B DECIMAL(10, 6) NOT NULL,
    closing_price_1A DECIMAL(20, 10) NOT NULL,
    closing_price_2A DECIMAL(20, 10) NOT NULL,
    closing_price_2B DECIMAL(20, 10) NOT NULL,
    closing_price_3B DECIMAL(20, 10) NOT NULL,

    -- Collateral Ratios
    collateral_ratio_1A DECIMAL(10, 6) NOT NULL,
    collateral_ratio_2B DECIMAL(10, 6) NOT NULL,

    -- Liquidation Thresholds
    liquidation_threshold_1A DECIMAL(10, 6) NOT NULL,
    liquidation_threshold_2B DECIMAL(10, 6) NOT NULL,

    -- Rebalance Actions (text descriptions)
    entry_action_1A TEXT,
    entry_action_2A TEXT,
    entry_action_2B TEXT,
    entry_action_3B TEXT,
    exit_action_1A TEXT,
    exit_action_2A TEXT,
    exit_action_2B TEXT,
    exit_action_3B TEXT,

    -- Token Amounts
    entry_token_amount_1A DECIMAL(20, 10) NOT NULL,
    entry_token_amount_2A DECIMAL(20, 10) NOT NULL,
    entry_token_amount_2B DECIMAL(20, 10) NOT NULL,
    entry_token_amount_3B DECIMAL(20, 10) NOT NULL,
    exit_token_amount_1A DECIMAL(20, 10) NOT NULL,
    exit_token_amount_2A DECIMAL(20, 10) NOT NULL,
    exit_token_amount_2B DECIMAL(20, 10) NOT NULL,
    exit_token_amount_3B DECIMAL(20, 10) NOT NULL,

    -- USD Sizes
    entry_size_usd_1A DECIMAL(20, 10) NOT NULL,
    entry_size_usd_2A DECIMAL(20, 10) NOT NULL,
    entry_size_usd_2B DECIMAL(20, 10) NOT NULL,
    entry_size_usd_3B DECIMAL(20, 10) NOT NULL,
    exit_size_usd_1A DECIMAL(20, 10) NOT NULL,
    exit_size_usd_2A DECIMAL(20, 10) NOT NULL,
    exit_size_usd_2B DECIMAL(20, 10) NOT NULL,
    exit_size_usd_3B DECIMAL(20, 10) NOT NULL,

    -- Realised Metrics (calculated once at rebalance time)
    realised_fees DECIMAL(20, 10) NOT NULL,
    realised_pnl DECIMAL(20, 10) NOT NULL,
    realised_lend_earnings DECIMAL(20, 10) NOT NULL,
    realised_borrow_costs DECIMAL(20, 10) NOT NULL,

    -- Metadata
    rebalance_reason TEXT,
    rebalance_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE CASCADE,
    UNIQUE (position_id, sequence_number)
);

-- Indexes for position_rebalances
CREATE INDEX IF NOT EXISTS idx_rebalances_position ON position_rebalances(position_id);
CREATE INDEX IF NOT EXISTS idx_rebalances_sequence ON position_rebalances(position_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_rebalances_timestamps ON position_rebalances(opening_timestamp, closing_timestamp);


-- Table 6: position_statistics
-- Pre-calculated position summary statistics for fast dashboard loading
-- Follows event sourcing pattern: immutable snapshots of position state at each timestamp
CREATE TABLE IF NOT EXISTS position_statistics (
    -- Identification
    position_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- Core Metrics (all in USD)
    total_pnl DECIMAL(20, 10) NOT NULL,           -- Realized + Unrealized PnL
    total_earnings DECIMAL(20, 10) NOT NULL,      -- Total protocol earnings + rewards
    base_earnings DECIMAL(20, 10) NOT NULL,       -- Net protocol interest (lend - borrow)
    reward_earnings DECIMAL(20, 10) NOT NULL,     -- Total reward distributions
    total_fees DECIMAL(20, 10) NOT NULL,          -- Total borrow fees paid

    -- Position Value
    current_value DECIMAL(20, 10) NOT NULL,       -- deployment_usd + total_pnl

    -- APR Metrics (as decimals: 0.05 = 5%)
    realized_apr DECIMAL(10, 6),                  -- Annualized return from entry to now
    current_apr DECIMAL(10, 6),                   -- Current APR based on live rates

    -- Segment Breakdown
    live_pnl DECIMAL(20, 10),                     -- PnL from current live segment
    realized_pnl DECIMAL(20, 10),                 -- PnL from all closed rebalance segments

    -- Metadata
    calculation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When this was calculated

    PRIMARY KEY (position_id, timestamp),
    FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE CASCADE
);

-- Indexes for position_statistics
CREATE INDEX IF NOT EXISTS idx_position_statistics_timestamp ON position_statistics(timestamp);
CREATE INDEX IF NOT EXISTS idx_position_statistics_position_id ON position_statistics(position_id);
CREATE INDEX IF NOT EXISTS idx_position_statistics_position_time ON position_statistics(position_id, timestamp);

-- Enable RLS for position_statistics
ALTER TABLE position_statistics ENABLE ROW LEVEL SECURITY;

-- RLS Policies for position_statistics
-- Allow service role full access (for backend data collection)
CREATE POLICY "Service role has full access to position_statistics"
ON position_statistics
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Allow authenticated users to read position statistics
CREATE POLICY "Authenticated users can read position_statistics"
ON position_statistics
FOR SELECT
TO authenticated
USING (true);
