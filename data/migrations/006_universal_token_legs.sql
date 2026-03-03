-- Migration 006: Universal token legs
-- Allow token2/token3 to be NULL when legs are unused
ALTER TABLE positions ALTER COLUMN token2 DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN token2_contract DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN token3 DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN token3_contract DROP NOT NULL;

-- Add token4 / token4_contract for the B_B leg (NULL = leg unused)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS token4 TEXT;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS token4_contract TEXT;

-- Allow rate/price columns to be NULL for unused legs
ALTER TABLE positions ALTER COLUMN entry_token2_rate DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_token2_price DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_token3_rate DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_token3_price DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_token4_rate DROP NOT NULL;
ALTER TABLE positions ALTER COLUMN entry_token4_price DROP NOT NULL;

-- position_rebalances: opening rate/price NULL for unused legs
ALTER TABLE position_rebalances ALTER COLUMN opening_token2_rate DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN opening_token2_price DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN opening_token3_rate DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN opening_token3_price DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN opening_token4_rate DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN opening_token4_price DROP NOT NULL;

-- position_rebalances: entry amount/size NULL for unused legs
ALTER TABLE position_rebalances ALTER COLUMN entry_token2_amount DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN entry_token2_size_usd DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN entry_token3_amount DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN entry_token3_size_usd DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN entry_token4_amount DROP NOT NULL;
ALTER TABLE position_rebalances ALTER COLUMN entry_token4_size_usd DROP NOT NULL;
