-- Migration: Backfill portfolio_id for existing standalone positions
-- Date: 2026-02-10
-- Purpose: Set portfolio_id='single positions' for all positions that don't belong to a portfolio
--
-- According to design notes:
-- - Standalone positions should have portfolio_id='single positions'
-- - Portfolio positions have portfolio_id=<UUID>
-- - NULL portfolio_id means the position was created before this feature

-- Update all positions with NULL portfolio_id to 'single positions'
UPDATE positions
SET portfolio_id = 'single positions'
WHERE portfolio_id IS NULL;

-- Verify the update
SELECT
    COUNT(*) as total_positions,
    SUM(CASE WHEN portfolio_id = 'single positions' THEN 1 ELSE 0 END) as standalone_positions,
    SUM(CASE WHEN portfolio_id != 'single positions' THEN 1 ELSE 0 END) as portfolio_positions
FROM positions;
