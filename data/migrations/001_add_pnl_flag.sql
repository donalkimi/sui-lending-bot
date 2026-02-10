-- Migration: Add use_for_pnl flag to rates_snapshot table
-- Purpose: Optimize PnL calculations by marking hourly snapshots for use
-- Date: 2026-02-10

-- Add use_for_pnl column with default FALSE
ALTER TABLE rates_snapshot
ADD COLUMN IF NOT EXISTS use_for_pnl BOOLEAN NOT NULL DEFAULT FALSE;

-- Add partial index for efficient filtering by PnL flag
-- This index only includes rows where use_for_pnl = TRUE, making it smaller and faster
CREATE INDEX IF NOT EXISTS idx_rates_pnl_flag
ON rates_snapshot(use_for_pnl, timestamp)
WHERE use_for_pnl = TRUE;

-- Add compound partial index for PnL queries (token-specific lookups)
-- This optimizes queries that filter by token_contract, protocol, and timestamp
CREATE INDEX IF NOT EXISTS idx_rates_pnl_lookup
ON rates_snapshot(token_contract, protocol, timestamp)
WHERE use_for_pnl = TRUE;

-- Verify the column was added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'rates_snapshot' AND column_name = 'use_for_pnl';
