-- Migration 009: Fix entry_liquidation_distance generated column formula
--
-- Previous formula divided by liq_price:
--   (liq_price - entry_price) / liq_price
--   e.g. long perp 20% liq dist: (0.8P - P) / 0.8P = -25%  ← wrong
--
-- Correct formula divides by entry_price (same convention as live liq distance):
--   (liq_price - entry_price) / entry_price
--   e.g. long perp 20% liq dist: (0.8P - P) / P = -20%      ← correct
--
-- PostgreSQL does not support ALTER on generated columns — must DROP then ADD.

-- positions table
ALTER TABLE positions
    DROP COLUMN IF EXISTS entry_liquidation_distance_token1,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token2,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token3,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token4;

ALTER TABLE positions
    ADD COLUMN entry_liquidation_distance_token1 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token1 IS NOT NULL AND entry_liquidation_price_token1 != 0
             AND entry_token1_price IS NOT NULL AND entry_token1_price != 0
        THEN (entry_liquidation_price_token1 - entry_token1_price) / entry_token1_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token2 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token2 IS NOT NULL AND entry_liquidation_price_token2 != 0
             AND entry_token2_price IS NOT NULL AND entry_token2_price != 0
        THEN (entry_liquidation_price_token2 - entry_token2_price) / entry_token2_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token3 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token3 IS NOT NULL AND entry_liquidation_price_token3 != 0
             AND entry_token3_price IS NOT NULL AND entry_token3_price != 0
        THEN (entry_liquidation_price_token3 - entry_token3_price) / entry_token3_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token4 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token4 IS NOT NULL AND entry_liquidation_price_token4 != 0
             AND entry_token4_price IS NOT NULL AND entry_token4_price != 0
        THEN (entry_liquidation_price_token4 - entry_token4_price) / entry_token4_price
        ELSE NULL END) STORED;

-- position_rebalances table (denominator = opening_tokenN_price)
ALTER TABLE position_rebalances
    DROP COLUMN IF EXISTS entry_liquidation_distance_token1,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token2,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token3,
    DROP COLUMN IF EXISTS entry_liquidation_distance_token4;

ALTER TABLE position_rebalances
    ADD COLUMN entry_liquidation_distance_token1 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token1 IS NOT NULL AND entry_liquidation_price_token1 != 0
             AND opening_token1_price IS NOT NULL AND opening_token1_price != 0
        THEN (entry_liquidation_price_token1 - opening_token1_price) / opening_token1_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token2 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token2 IS NOT NULL AND entry_liquidation_price_token2 != 0
             AND opening_token2_price IS NOT NULL AND opening_token2_price != 0
        THEN (entry_liquidation_price_token2 - opening_token2_price) / opening_token2_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token3 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token3 IS NOT NULL AND entry_liquidation_price_token3 != 0
             AND opening_token3_price IS NOT NULL AND opening_token3_price != 0
        THEN (entry_liquidation_price_token3 - opening_token3_price) / opening_token3_price
        ELSE NULL END) STORED,
    ADD COLUMN entry_liquidation_distance_token4 DECIMAL(10, 8) GENERATED ALWAYS AS (
        CASE WHEN entry_liquidation_price_token4 IS NOT NULL AND entry_liquidation_price_token4 != 0
             AND opening_token4_price IS NOT NULL AND opening_token4_price != 0
        THEN (entry_liquidation_price_token4 - opening_token4_price) / opening_token4_price
        ELSE NULL END) STORED;
