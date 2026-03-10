-- Migration 007: Add per-leg segment earnings columns
-- tokenN_earnings: signed net base contribution (positive=lend, negative=borrow)
-- tokenN_rewards: reward token earnings (always positive, NULL if leg unused)

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS token1_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token1_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token2_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token2_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token3_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token3_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token4_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token4_rewards  DECIMAL(20, 10);

ALTER TABLE position_rebalances
    ADD COLUMN IF NOT EXISTS token1_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token1_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token2_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token2_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token3_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token3_rewards  DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token4_earnings DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS token4_rewards  DECIMAL(20, 10);
