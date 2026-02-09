-- Migration: Fix analysis_cache table schema
-- Issue: Column name mismatch - code expects 'timestamp_seconds' but table may have different column
-- Date: 2026-02-09

-- Step 1: Drop existing table if it has wrong schema
-- (Safe because cache is regenerated on next analysis)
DROP TABLE IF EXISTS analysis_cache CASCADE;

-- Step 2: Recreate with correct schema
CREATE TABLE analysis_cache (
    timestamp_seconds INTEGER NOT NULL,
    liquidation_distance DECIMAL(5, 4) NOT NULL,
    results_json TEXT NOT NULL,
    strategy_count INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (timestamp_seconds, liquidation_distance)
);

-- Step 3: Create indexes
CREATE INDEX idx_analysis_cache_timestamp
ON analysis_cache(timestamp_seconds, liquidation_distance);

CREATE INDEX idx_analysis_cache_created
ON analysis_cache(created_at);

-- Step 4: Enable RLS
ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY;

-- Step 5: Create policies
CREATE POLICY "Service role has full access to analysis_cache"
ON analysis_cache
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read analysis_cache"
ON analysis_cache
FOR SELECT
TO authenticated
USING (true);
