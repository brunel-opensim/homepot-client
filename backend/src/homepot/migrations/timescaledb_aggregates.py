"""Create continuous aggregates for device metrics analysis.

This migration creates materialized views that pre-compute common metrics queries
for significantly faster dashboard and analytics performance.
"""

import logging
from typing import Dict

from homepot.timescale import TimescaleDBManager

logger = logging.getLogger(__name__)


async def create_hourly_device_metrics(ts_manager: TimescaleDBManager) -> bool:
    """Create continuous aggregate for hourly device metrics.

    Pre-computes hourly averages for:
    - CPU usage
    - Memory usage
    - Disk usage
    - Transaction counts
    - Error counts
    - Network latency

    Query performance: 10-50x faster than querying raw data
    """
    query = """
        SELECT time_bucket('1 hour', timestamp) AS hour,
               device_id,
               COUNT(*) as check_count,
               AVG(CAST(response_data->>'system'->>'cpu_percent' AS FLOAT)) as avg_cpu,
               MAX(CAST(response_data->>'system'->>'cpu_percent' AS FLOAT)) as max_cpu,
               AVG(CAST(response_data->>'system'->>'memory_percent' AS FLOAT)) as avg_memory,
               MAX(CAST(response_data->>'system'->>'memory_percent' AS FLOAT)) as max_memory,
               AVG(CAST(response_data->>'system'->>'disk_percent' AS FLOAT)) as avg_disk,
               MAX(CAST(response_data->>'system'->>'disk_percent' AS FLOAT)) as max_disk,
               SUM(CAST(response_data->>'app_metrics'->>'transactions_count' AS INTEGER)) as total_transactions,
               SUM(CAST(response_data->>'app_metrics'->>'errors_count' AS INTEGER)) as total_errors,
               AVG(CAST(response_data->>'network'->>'latency_ms' AS FLOAT)) as avg_latency,
               AVG(response_time_ms) as avg_response_time,
               COUNT(*) FILTER (WHERE NOT is_healthy) as unhealthy_count
        FROM health_checks
        GROUP BY hour, device_id
    """

    return await ts_manager.create_continuous_aggregate(
        view_name="device_metrics_hourly",
        hypertable="health_checks",
        query=query,
        refresh_interval="1 hour",
    )


async def create_daily_device_metrics(ts_manager: TimescaleDBManager) -> bool:
    """Create continuous aggregate for daily device metrics.

    Pre-computes daily summaries for long-term trends and reporting.
    Query performance: 50-100x faster than querying raw data
    """
    query = """
        SELECT time_bucket('1 day', timestamp) AS day,
               device_id,
               COUNT(*) as check_count,
               AVG(CAST(response_data->>'system'->>'cpu_percent' AS FLOAT)) as avg_cpu,
               MAX(CAST(response_data->>'system'->>'cpu_percent' AS FLOAT)) as max_cpu,
               AVG(CAST(response_data->>'system'->>'memory_percent' AS FLOAT)) as avg_memory,
               MAX(CAST(response_data->>'system'->>'memory_percent' AS FLOAT)) as max_memory,
               AVG(CAST(response_data->>'system'->>'disk_percent' AS FLOAT)) as avg_disk,
               MAX(CAST(response_data->>'system'->>'disk_percent' AS FLOAT)) as max_disk,
               SUM(CAST(response_data->>'app_metrics'->>'transactions_count' AS INTEGER)) as total_transactions,
               SUM(CAST(response_data->>'app_metrics'->>'errors_count' AS INTEGER)) as total_errors,
               AVG(CAST(response_data->>'network'->>'latency_ms' AS FLOAT)) as avg_latency,
               AVG(response_time_ms) as avg_response_time,
               COUNT(*) FILTER (WHERE NOT is_healthy) as unhealthy_count,
               AVG(CAST(response_data->>'system'->>'uptime_seconds' AS BIGINT)) as avg_uptime
        FROM health_checks
        GROUP BY day, device_id
    """

    return await ts_manager.create_continuous_aggregate(
        view_name="device_metrics_daily",
        hypertable="health_checks",
        query=query,
        refresh_interval="6 hours",
    )


async def create_site_metrics_hourly(ts_manager: TimescaleDBManager) -> bool:
    """Create continuous aggregate for site-level hourly metrics.

    Aggregates metrics across all devices in each site for site-wide monitoring.
    """
    query = """
        SELECT time_bucket('1 hour', hc.timestamp) AS hour,
               d.site_id,
               COUNT(DISTINCT hc.device_id) as device_count,
               COUNT(*) as total_checks,
               AVG(CAST(hc.response_data->>'system'->>'cpu_percent' AS FLOAT)) as avg_cpu,
               AVG(CAST(hc.response_data->>'system'->>'memory_percent' AS FLOAT)) as avg_memory,
               SUM(CAST(hc.response_data->>'app_metrics'->>'transactions_count' AS INTEGER)) as total_transactions,
               SUM(CAST(hc.response_data->>'app_metrics'->>'errors_count' AS INTEGER)) as total_errors,
               AVG(hc.response_time_ms) as avg_response_time,
               COUNT(*) FILTER (WHERE NOT hc.is_healthy) as unhealthy_checks
        FROM health_checks hc
        LEFT JOIN devices d ON hc.device_id = d.id
        WHERE d.site_id IS NOT NULL
        GROUP BY hour, d.site_id
    """

    return await ts_manager.create_continuous_aggregate(
        view_name="site_metrics_hourly",
        hypertable="health_checks",
        query=query,
        refresh_interval="1 hour",
    )


async def setup_timescaledb_aggregates(session) -> Dict[str, bool]:
    """Set up all continuous aggregates for device metrics.

    Args:
        session: AsyncSession for database operations

    Returns:
        Dictionary with aggregate names and their creation success status
    """
    from homepot.timescale import TimescaleDBManager

    ts_manager = TimescaleDBManager(session)

    # Check if TimescaleDB is available
    if not await ts_manager.is_timescaledb_available():
        logger.warning("TimescaleDB not available - skipping continuous aggregates")
        return {}

    results = {}

    # Create hourly device metrics aggregate
    logger.info("Creating hourly device metrics aggregate...")
    results["device_metrics_hourly"] = await create_hourly_device_metrics(ts_manager)

    # Create daily device metrics aggregate
    logger.info("Creating daily device metrics aggregate...")
    results["device_metrics_daily"] = await create_daily_device_metrics(ts_manager)

    # Create site-level hourly metrics aggregate
    logger.info("Creating site metrics hourly aggregate...")
    results["site_metrics_hourly"] = await create_site_metrics_hourly(ts_manager)

    # Log results
    successful = sum(1 for success in results.values() if success)
    logger.info(
        f"TimescaleDB aggregates setup complete: {successful}/{len(results)} successful"
    )

    return results
