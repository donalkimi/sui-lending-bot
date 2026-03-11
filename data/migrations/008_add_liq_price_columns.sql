-- Migration 008: Add per-token entry liquidation price/distance columns
-- entry_liquidation_price_tokenN: stored by application at create_position and after each rebalance
-- entry_liquidation_distance_tokenN: generated from (liq_price - entry_price) / liq_price
--   negative = price must fall to hit liquidation (lend leg)
--   positive = price must rise to hit liquidation (borrow leg)

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token1 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token2 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token3 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token4 DECIMAL(20, 10);

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token1 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token1 IS NOT NULL AND entry_liquidation_price_token1 != 0
            THEN (entry_liquidation_price_token1 - entry_token1_price) / entry_liquidation_price_token1
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token2 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token2 IS NOT NULL AND entry_liquidation_price_token2 != 0
            THEN (entry_liquidation_price_token2 - entry_token2_price) / entry_liquidation_price_token2
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token3 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token3 IS NOT NULL AND entry_liquidation_price_token3 != 0
            THEN (entry_liquidation_price_token3 - entry_token3_price) / entry_liquidation_price_token3
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token4 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token4 IS NOT NULL AND entry_liquidation_price_token4 != 0
            THEN (entry_liquidation_price_token4 - entry_token4_price) / entry_liquidation_price_token4
            ELSE NULL END) STORED;

ALTER TABLE position_rebalances
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token1 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token2 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token3 DECIMAL(20, 10),
    ADD COLUMN IF NOT EXISTS entry_liquidation_price_token4 DECIMAL(20, 10);

ALTER TABLE position_rebalances
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token1 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token1 IS NOT NULL AND entry_liquidation_price_token1 != 0
            THEN (entry_liquidation_price_token1 - opening_token1_price) / entry_liquidation_price_token1
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token2 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token2 IS NOT NULL AND entry_liquidation_price_token2 != 0
            THEN (entry_liquidation_price_token2 - opening_token2_price) / entry_liquidation_price_token2
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token3 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token3 IS NOT NULL AND entry_liquidation_price_token3 != 0
            THEN (entry_liquidation_price_token3 - opening_token3_price) / entry_liquidation_price_token3
            ELSE NULL END) STORED,
    ADD COLUMN IF NOT EXISTS entry_liquidation_distance_token4 DECIMAL(10, 8)
        GENERATED ALWAYS AS (
            CASE WHEN entry_liquidation_price_token4 IS NOT NULL AND entry_liquidation_price_token4 != 0
            THEN (entry_liquidation_price_token4 - opening_token4_price) / entry_liquidation_price_token4
            ELSE NULL END) STORED;
