-- HOMEPOT paper metrics (reproducible SQL)
--
-- These queries are intended to back the quantitative statements in the ICCS draft.
-- They are written for PostgreSQL (and compatible with TimescaleDB).
--
-- Notes:
-- - The schema uses both timezone-aware and timezone-naive timestamps across tables.
--   Use NOW() consistently and interpret results as per your DB configuration.
-- - Replace intervals as needed to match the evaluation window reported in the paper.

-- Q1: Record counts over a fixed window (e.g., last 10 days)
SELECT 'device_metrics' AS table_name, COUNT(*) AS n
FROM device_metrics
WHERE timestamp >= NOW() - INTERVAL '10 days'
UNION ALL
SELECT 'health_checks' AS table_name, COUNT(*) AS n
FROM health_checks
WHERE timestamp >= NOW() - INTERVAL '10 days'
UNION ALL
SELECT 'error_logs' AS table_name, COUNT(*) AS n
FROM error_logs
WHERE timestamp >= NOW() - INTERVAL '10 days'
UNION ALL
SELECT 'api_request_logs' AS table_name, COUNT(*) AS n
FROM api_request_logs
WHERE timestamp >= NOW() - INTERVAL '10 days'
UNION ALL
SELECT 'device_state_history' AS table_name, COUNT(*) AS n
FROM device_state_history
WHERE timestamp >= NOW() - INTERVAL '10 days'
ORDER BY table_name;

-- Q2: Distinct device coverage (by device PK for metrics/health checks)
SELECT
  (SELECT COUNT(DISTINCT device_id) FROM device_metrics WHERE timestamp >= NOW() - INTERVAL '10 days') AS device_metrics_distinct_devices,
  (SELECT COUNT(DISTINCT device_id) FROM health_checks WHERE timestamp >= NOW() - INTERVAL '10 days') AS health_checks_distinct_devices;

-- Q3: Non-null completeness for key telemetry fields (device_metrics)
-- Returns percentages over a window.
SELECT
  100.0 * AVG((cpu_percent IS NOT NULL)::int) AS cpu_non_null_pct,
  100.0 * AVG((memory_percent IS NOT NULL)::int) AS memory_non_null_pct,
  100.0 * AVG((disk_percent IS NOT NULL)::int) AS disk_non_null_pct,
  100.0 * AVG((network_latency_ms IS NOT NULL)::int) AS latency_non_null_pct,
  COUNT(*) AS n_rows
FROM device_metrics
WHERE timestamp >= NOW() - INTERVAL '10 days';

-- Q4: Validity violations for percent-like metrics (> 100)
SELECT
  SUM((cpu_percent > 100)::int) AS cpu_gt_100,
  SUM((memory_percent > 100)::int) AS memory_gt_100,
  SUM((disk_percent > 100)::int) AS disk_gt_100,
  COUNT(*) AS n_rows
FROM device_metrics
WHERE timestamp >= NOW() - INTERVAL '10 days';

-- Q5: Max observed inter-arrival gap (minutes) for health checks (global)
WITH ordered AS (
  SELECT
    timestamp,
    LAG(timestamp) OVER (ORDER BY timestamp) AS prev_ts
  FROM health_checks
  WHERE timestamp >= NOW() - INTERVAL '7 days'
)
SELECT
  MAX(EXTRACT(EPOCH FROM (timestamp - prev_ts)) / 60.0) AS max_gap_minutes
FROM ordered
WHERE prev_ts IS NOT NULL;

-- Q6: Max observed inter-arrival gap (minutes) for health checks (per device)
WITH ordered AS (
  SELECT
    device_id,
    timestamp,
    LAG(timestamp) OVER (PARTITION BY device_id ORDER BY timestamp) AS prev_ts
  FROM health_checks
  WHERE timestamp >= NOW() - INTERVAL '7 days'
)
SELECT
  device_id,
  MAX(EXTRACT(EPOCH FROM (timestamp - prev_ts)) / 60.0) AS max_gap_minutes
FROM ordered
WHERE prev_ts IS NOT NULL
GROUP BY device_id
ORDER BY max_gap_minutes DESC;

-- Q7: Continuity gaps for device metrics (count gaps > 60 minutes, global)
WITH ordered AS (
  SELECT
    timestamp,
    LAG(timestamp) OVER (ORDER BY timestamp) AS prev_ts
  FROM device_metrics
  WHERE timestamp >= NOW() - INTERVAL '10 days'
)
SELECT
  COUNT(*) FILTER (WHERE (EXTRACT(EPOCH FROM (timestamp - prev_ts)) / 60.0) > 60) AS gaps_gt_60min,
  MAX(EXTRACT(EPOCH FROM (timestamp - prev_ts)) / 60.0) AS max_gap_minutes
FROM ordered
WHERE prev_ts IS NOT NULL;

-- Q8: Expected-rate check for smart filtering baseline (288/day per device)
-- This yields observed snapshots/day by device PK and day.
SELECT
  device_id,
  DATE_TRUNC('day', timestamp) AS day,
  COUNT(*) AS n
FROM device_metrics
WHERE timestamp >= NOW() - INTERVAL '10 days'
GROUP BY device_id, DATE_TRUNC('day', timestamp)
ORDER BY day DESC, device_id;
