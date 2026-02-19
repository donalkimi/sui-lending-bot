-- ============================================================================
-- Migration: Add Perpetual Funding Rates Support
-- Date: 2026-02-17
-- Description: Add perp_margin_rates table and perp_margin_rate column to rates_snapshot
-- ============================================================================

-- Step 1: Create perp_margin_rates table
CREATE TABLE IF NOT EXISTS perp_margin_rates (
    timestamp TIMESTAMP NOT NULL,
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

    PRIMARY KEY (timestamp, protocol, token_contract)
);

-- Step 2: Create indexes for perp_margin_rates
CREATE INDEX IF NOT EXISTS idx_perp_rates_time ON perp_margin_rates(timestamp);
CREATE INDEX IF NOT EXISTS idx_perp_rates_market ON perp_margin_rates(market_address);
CREATE INDEX IF NOT EXISTS idx_perp_rates_token ON perp_margin_rates(token_contract);
CREATE INDEX IF NOT EXISTS idx_perp_rates_base_token ON perp_margin_rates(base_token);

-- Step 3: Enable RLS and create policies
ALTER TABLE perp_margin_rates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to perp_margin_rates"
ON perp_margin_rates FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Authenticated users can read perp_margin_rates"
ON perp_margin_rates FOR SELECT TO authenticated
USING (true);

-- Step 4: Add perp_margin_rate column to rates_snapshot
-- NOTE (2026-02-19): THIS WAS A MISTAKE!
-- Perp data should go into lend_total_apr/borrow_total_apr like all other protocols.
-- This column was removed and Bluefin now uses standard columns via the protocol merger pipeline.
-- DO NOT RE-ADD THIS COLUMN!
-- The commented-out code below shows the wrong approach for reference:
--
-- ALTER TABLE rates_snapshot
-- ADD COLUMN IF NOT EXISTS perp_margin_rate DECIMAL(10,6) DEFAULT NULL;
--
-- -- Step 5: Create partial index for perp_margin_rate
-- CREATE INDEX IF NOT EXISTS idx_rates_perp_margin
-- ON rates_snapshot(perp_margin_rate)
-- WHERE perp_margin_rate IS NOT NULL;

-- ============================================================================
-- Rollback Instructions (if needed)
-- ============================================================================
-- To rollback this migration, run the following commands:
--
-- DROP INDEX IF EXISTS idx_rates_perp_margin;
-- ALTER TABLE rates_snapshot DROP COLUMN IF EXISTS perp_margin_rate;
-- DROP POLICY IF EXISTS "Authenticated users can read perp_margin_rates" ON perp_margin_rates;
-- DROP POLICY IF EXISTS "Service role has full access to perp_margin_rates" ON perp_margin_rates;
-- DROP INDEX IF EXISTS idx_perp_rates_base_token;
-- DROP INDEX IF EXISTS idx_perp_rates_token;
-- DROP INDEX IF EXISTS idx_perp_rates_market;
-- DROP INDEX IF EXISTS idx_perp_rates_time;
-- DROP TABLE IF EXISTS perp_margin_rates;
-- ============================================================================
