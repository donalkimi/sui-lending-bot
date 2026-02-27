-- Migration: Drop NOT NULL from collateral ratio and liquidation threshold columns
-- Perp strategies (perp_lending, perp_borrowing) legitimately have NULL for these:
--   entry_collateral_ratio_1A: NULL for perp_lending (spot lending has no collateral ratio)
--   entry_collateral_ratio_2B: NULL for all perp strategies (Bluefin has no collateral ratio)
--   entry_liquidation_threshold_1A: NULL for perp_lending
--   entry_liquidation_threshold_2B: NULL for all perp strategies
ALTER TABLE positions ALTER COLUMN entry_collateral_ratio_1A  DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_collateral_ratio_2B  DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_liquidation_threshold_1A DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_liquidation_threshold_2B DROP NOT NULL;

ALTER TABLE position_segments ALTER COLUMN collateral_ratio_1A  DROP NOT NULL;
ALTER TABLE position_segments ALTER COLUMN collateral_ratio_2B  DROP NOT NULL;
ALTER TABLE position_segments ALTER COLUMN liquidation_threshold_1A DROP NOT NULL;
ALTER TABLE position_segments ALTER COLUMN liquidation_threshold_2B DROP NOT NULL;
