-- Migration: Backfill use_for_pnl flags for historical data
-- Purpose: Mark one snapshot per hour (closest to top of hour) for PnL calculations
-- Date: 2026-02-10
-- Performance: May take several minutes on large datasets

-- Set use_for_pnl = TRUE for snapshots closest to top of hour
WITH hourly_buckets AS (
  SELECT
    DATE_TRUNC('hour', timestamp) AS hour_bucket,
    timestamp,
    protocol,
    token_contract,
    -- Calculate distance from top of hour (in seconds)
    ABS(EXTRACT(EPOCH FROM (timestamp - DATE_TRUNC('hour', timestamp)))) AS seconds_from_hour
  FROM rates_snapshot
),
closest_to_hour AS (
  SELECT
    timestamp,
    protocol,
    token_contract,
    ROW_NUMBER() OVER (
      PARTITION BY DATE_TRUNC('hour', timestamp), protocol, token_contract
      ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - DATE_TRUNC('hour', timestamp)))) ASC
    ) AS rank
  FROM hourly_buckets
)
UPDATE rates_snapshot
SET use_for_pnl = TRUE
WHERE (timestamp, protocol, token_contract) IN (
  SELECT timestamp, protocol, token_contract
  FROM closest_to_hour
  WHERE rank = 1
);

-- Verification Query: Count PnL-flagged snapshots per day
SELECT
  DATE(timestamp) AS date,
  COUNT(*) AS pnl_snapshots,
  COUNT(*) / NULLIF(COUNT(DISTINCT protocol || '|' || token_contract), 0) AS avg_snapshots_per_token
FROM rates_snapshot
WHERE use_for_pnl = TRUE
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 30;

-- Verification Query: Count flagged vs unflagged snapshots
SELECT
  use_for_pnl,
  COUNT(*) AS count,
  ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM rates_snapshot), 2) AS percentage
FROM rates_snapshot
GROUP BY use_for_pnl
ORDER BY use_for_pnl DESC;
