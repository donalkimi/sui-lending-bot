-- Migration: Add portfolio tracking tables
-- Purpose: Enable portfolio persistence and performance tracking
-- Date: 2026-02-09
--
-- Design: Portfolios are collections of positions. We reuse the existing positions
-- table by adding a portfolio_id column. Single positions have portfolio_id='single positions'.

-- ==============================================================================
-- TABLE 1: portfolios
-- ==============================================================================
-- Tracks portfolio-level metadata

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
    entry_timestamp TIMESTAMP NOT NULL,  -- Timestamp when portfolio was "deployed"

    -- Portfolio Size
    target_portfolio_size DECIMAL(20, 10) NOT NULL,
    actual_allocated_usd DECIMAL(20, 10) NOT NULL,
    utilization_pct DECIMAL(5, 2) NOT NULL,  -- (actual / target) * 100

    -- PRIMARY METRIC: Entry Net APR
    -- USD-weighted average of strategy net_apr values at entry
    -- Formula: sum(position.entry_net_apr × position.deployment_usd) / total_allocated
    entry_weighted_net_apr DECIMAL(10, 6) NOT NULL,

    -- Constraints Used (JSON for flexibility)
    constraints_json TEXT NOT NULL,  -- Store allocation constraints used

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

-- ==============================================================================
-- TABLE 2: Alter existing positions table
-- ==============================================================================
-- Add portfolio_id column to link positions to portfolios

-- Add portfolio_id column (NULL = standalone position, UUID = part of portfolio)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS portfolio_id TEXT DEFAULT NULL;

-- Add foreign key constraint
ALTER TABLE positions
ADD CONSTRAINT fk_positions_portfolio
FOREIGN KEY (portfolio_id) REFERENCES portfolios(portfolio_id) ON DELETE SET NULL;

-- ==============================================================================
-- INDEXES
-- ==============================================================================

-- Portfolio indexes
CREATE INDEX IF NOT EXISTS idx_portfolios_status ON portfolios(status);
CREATE INDEX IF NOT EXISTS idx_portfolios_entry_time ON portfolios(entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolios_name ON portfolios(portfolio_name);
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);

-- Position portfolio index
CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);

-- ==============================================================================
-- ROW LEVEL SECURITY (Supabase)
-- ==============================================================================

ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY "Service role has full access to portfolios"
ON portfolios
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Authenticated users can read
CREATE POLICY "Authenticated users can read portfolios"
ON portfolios
FOR SELECT
TO authenticated
USING (true);
