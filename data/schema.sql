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

    -- PnL Optimization (added 2026-02-10)
    -- Marks snapshots to use for PnL calculations (one per hour, closest to top of hour)
    use_for_pnl BOOLEAN NOT NULL DEFAULT FALSE,

    -- Perpetual Funding Rates (added 2026-02-17)
    -- Interpolated perp funding rate (annualized) from perp_margin_rates table
    -- Nullable: only populated for tokens with perp markets (e.g., BTC, ETH)
    perp_margin_rate DECIMAL(10,6) DEFAULT NULL,

    -- Composite primary key for PostgreSQL ON CONFLICT support
    PRIMARY KEY (timestamp, protocol, token_contract)
);

-- Indexes for rates_snapshot
CREATE INDEX IF NOT EXISTS idx_rates_time ON rates_snapshot(timestamp);
CREATE INDEX IF NOT EXISTS idx_rates_contract ON rates_snapshot(token_contract);
CREATE INDEX IF NOT EXISTS idx_rates_protocol_contract ON rates_snapshot(protocol, token_contract);

-- PnL optimization indexes (added 2026-02-10)
-- Partial indexes only include rows where use_for_pnl = TRUE for efficiency
CREATE INDEX IF NOT EXISTS idx_rates_pnl_flag ON rates_snapshot(use_for_pnl, timestamp) WHERE use_for_pnl = TRUE;
CREATE INDEX IF NOT EXISTS idx_rates_pnl_lookup ON rates_snapshot(token_contract, protocol, timestamp) WHERE use_for_pnl = TRUE;

-- Perp margin rate index (added 2026-02-17)
-- Partial index only includes rows with perp rates
CREATE INDEX IF NOT EXISTS idx_rates_perp_margin ON rates_snapshot(perp_margin_rate) WHERE perp_margin_rate IS NOT NULL;

-- RLS Policies for rates_snapshot
ALTER TABLE rates_snapshot ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to rates_snapshot"
ON rates_snapshot FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read rates_snapshot"
ON rates_snapshot FOR SELECT TO authenticated
USING (true);


-- Table 2: token_registry
-- Stores every token contract (coin type) seen by the bot, and optional mappings to pricing IDs.
-- pyth_id / coingecko_id are nullable and can be populated over time.
CREATE TABLE IF NOT EXISTS token_registry (
    token_contract TEXT PRIMARY KEY,
    symbol TEXT,
    decimals INTEGER,              -- ADD THIS
    default_price DECIMAL(20,10),  -- ADD THIS
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

-- RLS Policies for token_registry
ALTER TABLE token_registry ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to token_registry"
ON token_registry FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read token_registry"
ON token_registry FOR SELECT TO authenticated
USING (true);


-- Table 3: oracle_prices
-- Stores latest oracle price data for each token from multiple sources
CREATE TABLE IF NOT EXISTS oracle_prices (
    token_contract TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,

    -- CoinGecko oracle
    coingecko DECIMAL(20,10),
    coingecko_time TIMESTAMP,

    -- Pyth oracle
    pyth DECIMAL(20,10),
    pyth_time TIMESTAMP,

    -- DeFi Llama oracle
    defillama DECIMAL(20,10),
    defillama_time TIMESTAMP,
    defillama_confidence DECIMAL(3,2),

    -- Aggregate latest price (computed from all oracles)
    latest_price DECIMAL(20,10),
    latest_oracle TEXT,
    latest_time TIMESTAMP,

    -- Metadata
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (token_contract) REFERENCES token_registry(token_contract) ON DELETE CASCADE
);

-- Indexes for oracle_prices
CREATE INDEX IF NOT EXISTS idx_oracle_prices_symbol ON oracle_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_oracle_prices_latest_time ON oracle_prices(latest_time);
CREATE INDEX IF NOT EXISTS idx_oracle_prices_coingecko_time ON oracle_prices(coingecko_time);
CREATE INDEX IF NOT EXISTS idx_oracle_prices_pyth_time ON oracle_prices(pyth_time);
CREATE INDEX IF NOT EXISTS idx_oracle_prices_defillama_time ON oracle_prices(defillama_time);

-- RLS Policies for oracle_prices
ALTER TABLE oracle_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to oracle_prices"
ON oracle_prices FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read oracle_prices"
ON oracle_prices FOR SELECT TO authenticated
USING (true);


-- Table 4: perp_margin_rates (added 2026-02-17)
-- Stores historical perpetual funding rates from Bluefin
-- Rates are annualized for consistency with lending rates (DESIGN_NOTES.md #7)
CREATE TABLE IF NOT EXISTS perp_margin_rates (
    timestamp TIMESTAMP NOT NULL,                -- Rounded to nearest hour for consistent querying
    protocol VARCHAR(50) NOT NULL,               -- 'Bluefin'
    market VARCHAR(100) NOT NULL,                -- 'BTC-PERP', 'SUI-PERP', 'ETH-PERP'
    market_address TEXT NOT NULL,                -- Unique contract identifier from Bluefin

    -- Proxy token contract (generated, not from chain)
    -- Format: "0x<base>-<quote>-PERP_<protocol>"
    -- Example: "0xBTC-USDC-PERP_bluefin"
    token_contract TEXT NOT NULL,

    base_token VARCHAR(50) NOT NULL,             -- Base token symbol (e.g., 'BTC')
    quote_token VARCHAR(50) NOT NULL,            -- Quote token symbol (e.g., 'USDC')

    -- Funding rates (annualized decimals: 0.0876 = 8.76% APR)
    -- Stored as decimals per DESIGN_NOTES.md #7
    funding_rate_hourly DECIMAL(10,6),          -- Raw hourly rate (for reference)
    funding_rate_annual DECIMAL(10,6) NOT NULL,  -- Annualized: hourly × 24 × 365

    -- Market metadata
    next_funding_time TIMESTAMP,                 -- Next funding update
    raw_timestamp_ms BIGINT,                     -- Raw funding time from API (milliseconds, before rounding)

    PRIMARY KEY (timestamp, protocol, token_contract)
);

-- Indexes for perp_margin_rates
CREATE INDEX IF NOT EXISTS idx_perp_rates_time ON perp_margin_rates(timestamp);
CREATE INDEX IF NOT EXISTS idx_perp_rates_market ON perp_margin_rates(market_address);
CREATE INDEX IF NOT EXISTS idx_perp_rates_token ON perp_margin_rates(token_contract);
CREATE INDEX IF NOT EXISTS idx_perp_rates_base_token ON perp_margin_rates(base_token);

-- RLS Policies for perp_margin_rates
ALTER TABLE perp_margin_rates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to perp_margin_rates"
ON perp_margin_rates FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read perp_margin_rates"
ON perp_margin_rates FOR SELECT TO authenticated
USING (true);


-- Table 5: reward_token_prices
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

-- RLS Policies for reward_token_prices
ALTER TABLE reward_token_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to reward_token_prices"
ON reward_token_prices FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read reward_token_prices"
ON reward_token_prices FOR SELECT TO authenticated
USING (true);


-- View: all_token_prices
-- Unified view of supply/borrow + reward token prices
-- Note: Views inherit RLS from underlying tables (rates_snapshot and reward_token_prices)
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


-- Table 6: positions
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

    -- Execution tracking (Unix seconds as integer)
    execution_time INTEGER NOT NULL DEFAULT -1,  -- -1 = pending execution, Unix timestamp = executed on-chain

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

    -- Entry Token Amounts (calculated at position creation: deployment_usd * weight / price)
    entry_token_amount_1A DECIMAL(30, 10),  -- Token amount for Leg 1A (lend)
    entry_token_amount_2A DECIMAL(30, 10),  -- Token amount for Leg 2A (borrow)
    entry_token_amount_2B DECIMAL(30, 10),  -- Token amount for Leg 2B (lend)
    entry_token_amount_3B DECIMAL(30, 10),  -- Token amount for Leg 3B (borrow, nullable)

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

    -- Portfolio Linking (NULL = standalone position, UUID = part of portfolio)
    portfolio_id TEXT DEFAULT NULL,

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
CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);

-- RLS Policies for positions
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to positions"
ON positions FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read positions"
ON positions FOR SELECT TO authenticated
USING (true);


-- Table 7: position_rebalances
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

-- RLS Policies for position_rebalances
ALTER TABLE position_rebalances ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to position_rebalances"
ON position_rebalances FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read position_rebalances"
ON position_rebalances FOR SELECT TO authenticated
USING (true);


-- Table 8: position_statistics
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

-- =============================================================================
-- Table 9: analysis_cache
-- Cache for strategy calculation results (for faster dashboard loading)
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_cache (
    timestamp_seconds INTEGER NOT NULL,
    liquidation_distance DECIMAL(5, 4) NOT NULL,
    results_json TEXT NOT NULL,
    strategy_count INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (timestamp_seconds, liquidation_distance)
);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_timestamp
ON analysis_cache(timestamp_seconds, liquidation_distance);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_created
ON analysis_cache(created_at);

-- RLS for analysis_cache
ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to analysis_cache"
ON analysis_cache
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read analysis_cache"
ON analysis_cache
FOR SELECT
TO authenticated
USING (true);

-- =============================================================================
-- Table 10: chart_cache
-- Cache for rendered chart visualizations (for faster dashboard loading)
-- =============================================================================
CREATE TABLE IF NOT EXISTS chart_cache (
    strategy_hash TEXT NOT NULL,
    timestamp_seconds INTEGER NOT NULL,
    chart_html TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (strategy_hash, timestamp_seconds)
);

CREATE INDEX IF NOT EXISTS idx_chart_cache_lookup
ON chart_cache(strategy_hash, timestamp_seconds);

CREATE INDEX IF NOT EXISTS idx_chart_cache_created
ON chart_cache(created_at);

-- RLS for chart_cache
ALTER TABLE chart_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to chart_cache"
ON chart_cache
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read chart_cache"
ON chart_cache
FOR SELECT
TO authenticated
USING (true);

-- =============================================================================
-- Table 11: portfolios
-- Tracks portfolio-level metadata (collections of positions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS portfolios (
    -- Portfolio Identification
    portfolio_id TEXT PRIMARY KEY,
    portfolio_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'closed', 'archived')),

    -- Ownership (Phase 1: single user, Phase 2: multi-user)
    is_paper_trade BOOLEAN NOT NULL DEFAULT TRUE,
    user_id TEXT,

    -- Creation & Entry
    created_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    entry_timestamp TIMESTAMP NOT NULL,

    -- Portfolio Size
    target_portfolio_size DECIMAL(20, 10) NOT NULL,
    actual_allocated_usd DECIMAL(20, 10) NOT NULL,
    utilization_pct DECIMAL(5, 2) NOT NULL,

    -- PRIMARY METRIC: Entry Net APR
    -- USD-weighted average of strategy net_apr values at entry
    -- Formula: sum(position.entry_net_apr × position.deployment_usd) / total_allocated
    entry_weighted_net_apr DECIMAL(10, 6) NOT NULL,

    -- Constraints Used (JSON for flexibility)
    constraints_json TEXT NOT NULL,

    -- Performance Tracking
    accumulated_realised_pnl DECIMAL(20, 10) DEFAULT 0.0,
    rebalance_count INTEGER DEFAULT 0,
    last_rebalance_timestamp TIMESTAMP,

    -- Closure Tracking
    close_timestamp TIMESTAMP,
    close_reason TEXT,
    close_notes TEXT,

    -- User Notes
    notes TEXT,

    -- Timestamps
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for portfolios
CREATE INDEX IF NOT EXISTS idx_portfolios_status ON portfolios(status);
CREATE INDEX IF NOT EXISTS idx_portfolios_entry_time ON portfolios(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(portfolio_name);
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);

-- RLS for portfolios
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to portfolios"
ON portfolios
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read portfolios"
ON portfolios
FOR SELECT
TO authenticated
USING (true);

-- Foreign key constraint for positions -> portfolios
ALTER TABLE positions
ADD CONSTRAINT IF NOT EXISTS fk_positions_portfolio
FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON DELETE SET NULL;

-- =============================================================================
-- Table 12: allocator_settings
-- Stores allocator constraint settings and sidebar filter presets
-- Supports both "last_used" (auto-saved) and named presets
-- =============================================================================
CREATE TABLE IF NOT EXISTS allocator_settings (
    -- Identification
    settings_id TEXT PRIMARY KEY,           -- 'last_used' or UUID for named presets
    settings_name TEXT NOT NULL,            -- Display name (e.g., "Conservative Strategy")

    -- Settings Blob (JSON)
    -- Structure:
    -- {
    --   "allocator_constraints": {
    --     "portfolio_size": 1000.0,
    --     "token2_exposure_limit": 0.30,
    --     "token2_exposure_overrides": {"SUI": 0.40},
    --     "stablecoin_exposure_limit": -1,
    --     "stablecoin_exposure_overrides": {"USDC": -1},
    --     "protocol_exposure_limit": 0.40,
    --     "max_single_allocation_pct": 0.40,
    --     "max_strategies": 5,
    --     "min_apy_confidence": 0.70,
    --     "apr_weights": {"net_apr": 0.30, "apr5": 0.30, "apr30": 0.30, "apr90": 0.10},
    --     "stablecoin_preferences": {"USDC": 1.00, "USDY": 0.95}
    --   },
    --   "sidebar_filters": {
    --     "liquidation_distance": 0.20,
    --     "deployment_usd": 100.0,
    --     "force_usdc_start": false,
    --     "force_token3_equals_token1": false,
    --     "stablecoin_only": false,
    --     "min_net_apr": 0.0,
    --     "token_filter": ["SUI", "DEEP"],
    --     "protocol_filter": ["Navi", "Suilend"]
    --   }
    -- }
    settings_json TEXT NOT NULL,

    -- Ownership (Phase 2 multi-user support)
    user_id TEXT DEFAULT NULL,              -- Nullable for Phase 1

    -- Usage Tracking
    last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    use_count INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT DEFAULT NULL           -- Optional user description
);

-- Indexes for allocator_settings
CREATE INDEX IF NOT EXISTS idx_allocator_settings_name ON allocator_settings(settings_name);
CREATE INDEX IF NOT EXISTS idx_allocator_settings_user ON allocator_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_allocator_settings_last_used ON allocator_settings(last_used_at DESC);

-- RLS for allocator_settings
ALTER TABLE allocator_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to allocator_settings"
ON allocator_settings
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read allocator_settings"
ON allocator_settings
FOR SELECT
TO authenticated
USING (true);
