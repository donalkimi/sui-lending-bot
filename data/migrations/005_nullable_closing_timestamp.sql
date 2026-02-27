-- Migration: Drop NOT NULL from position_rebalances.closing_timestamp
-- The initial deployment record for a position uses closing_timestamp = NULL
-- because the segment is still open (no closing event has occurred yet).
-- The column is only populated when the segment is closed by a rebalance or position closure.
ALTER TABLE position_rebalances ALTER COLUMN closing_timestamp DROP NOT NULL;
