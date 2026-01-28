-- ============================================================================
-- Migration: Add Borrow Weight Support
-- Date: 2026-01-28
-- Description: Adds borrow_weight column to rates_snapshot table and
--              entry_borrow_weight_2A/3B columns to positions table
-- ============================================================================

-- Add borrow_weight column to rates_snapshot
ALTER TABLE rates_snapshot ADD COLUMN borrow_weight DECIMAL(10,6);

-- Add borrow_weight columns to positions (captured at entry, remain constant)
ALTER TABLE positions ADD COLUMN entry_borrow_weight_2A DECIMAL(10,6);
ALTER TABLE positions ADD COLUMN entry_borrow_weight_3B DECIMAL(10,6);

-- Set default values for existing rows (backward compatibility)
UPDATE rates_snapshot SET borrow_weight = 1.0 WHERE borrow_weight IS NULL;
UPDATE positions SET entry_borrow_weight_2A = 1.0 WHERE entry_borrow_weight_2A IS NULL;
UPDATE positions SET entry_borrow_weight_3B = 1.0 WHERE entry_borrow_weight_3B IS NULL;

-- Verify migration
SELECT 'Migration completed successfully' AS status;
