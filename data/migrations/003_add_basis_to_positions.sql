-- Migration: Add entry basis columns to positions table
-- entry_basis is the direction-specific entry-side basis:
--   perp_lending   → basis_bid (short perp at bid, buy spot at ask)
--   perp_borrowing → basis_ask (long perp at ask, sell spot at bid)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_basis        DECIMAL(10, 8);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_basis_spread DECIMAL(10, 8);
