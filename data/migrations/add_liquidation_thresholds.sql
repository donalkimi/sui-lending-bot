-- Migration: Add liquidation_threshold columns to positions and position_rebalances tables
-- Date: 2026-01-28
-- Purpose: Add liquidation_threshold fields to mirror collateral_ratio fields throughout position tracking

-- Add to positions table
ALTER TABLE positions
ADD COLUMN entry_liquidation_threshold_1A DECIMAL(10, 6) DEFAULT 0.0;

ALTER TABLE positions
ADD COLUMN entry_liquidation_threshold_2B DECIMAL(10, 6) DEFAULT 0.0;

-- Add to position_rebalances table
ALTER TABLE position_rebalances
ADD COLUMN liquidation_threshold_1A DECIMAL(10, 6) DEFAULT 0.0;

ALTER TABLE position_rebalances
ADD COLUMN liquidation_threshold_2B DECIMAL(10, 6) DEFAULT 0.0;
