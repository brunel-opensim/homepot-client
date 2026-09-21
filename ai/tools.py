"""Agentic AI Tool Definitions.

Tool functions for the ReAct agent loop. Each tool is a Python function with
type hints and docstrings — the Ollama SDK auto-generates JSON schema from
them. Tools wrap existing ContextBuilder methods and database queries.

See docs/ai-agentic.md for the full architecture.
"""

import json
import logging
from typing import Optional

from ai.context_builder import ContextBuilder
from ai.device_memory import DeviceMemory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper to resolve device_id → device_int_id (integer PK)
# ---------------------------------------------------------------------------


async def _resolve_device_int_id(
    session: AsyncSession, device_id: str
) -> Optional[int]:
    """Resolve a device_id string to its integer primary key."""
    from homepot.models import Device

    stmt = select(Device.id).where(Device.device_id == device_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Tool 1: get_device_status
# ---------------------------------------------------------------------------


async def get_device_status(device_id: str) -> str:
    """Check the current status and health of a specific device.

    Args:
        device_id: The device identifier (e.g., 'POS-001', 'EMU-002')

    Returns:
        A summary of the device's status including name, type, online/offline
        state, health state, lifecycle state, firmware, OS, and IP address.
    """
    try:
        context = await ContextBuilder.get_metadata_context(device_id=device_id)
        if not context:
            return f"No device found with ID '{device_id}'."
        return context
    except Exception as e:
        logger.error("get_device_status failed for %s: %s", device_id, e)
        return f"Error retrieving status for {device_id}: {e}"


# ---------------------------------------------------------------------------
# Tool 2: get_device_metrics
# ---------------------------------------------------------------------------


async def get_device_metrics(device_id: str, metric: Optional[str] = None) -> str:
    """Retrieve recent device performance metrics (CPU, memory, disk, etc.).

    Args:
        device_id: The device identifier to fetch metrics for.
        metric: Optional specific metric to focus on (e.g., 'cpu', 'memory',
                'disk', 'latency', 'error_rate'). If None, returns all metrics.

    Returns:
        Recent metric readings for the device including timestamps and values.
    """
    try:
        context = await ContextBuilder.get_metrics_context(device_id=device_id)
        if not context:
            return f"No metrics available for device '{device_id}'."

        if metric:
            # Filter to requested metric
            lines = context.split("\n")
            filtered = [lines[0]]  # Keep header
            metric_lower = metric.lower()
            for line in lines[1:]:
                if metric_lower in line.lower():
                    filtered.append(line)
            if len(filtered) > 1:
                return "\n".join(filtered)
            return (
                f"Metric '{metric}' not found in recent data for {device_id}."
                f" Available metrics:\n{context}"
            )

        return context
    except Exception as e:
        logger.error("get_device_metrics failed for %s: %s", device_id, e)
        return f"Error retrieving metrics for {device_id}: {e}"


# ---------------------------------------------------------------------------
# Tool 3: get_error_logs
# ---------------------------------------------------------------------------


async def get_error_logs(device_id: str, limit: int = 10) -> str:
    """Retrieve recent error logs for a device.

    Args:
        device_id: The device identifier to fetch errors for.
        limit: Maximum number of error entries to return (default 10).

    Returns:
        Recent error log entries with timestamps, error types, and messages.
    """
    try:
        context = await ContextBuilder.get_error_context(device_id=device_id)
        if not context:
            return f"No error logs found for device '{device_id}'."

        # Truncate to requested limit
        lines = context.split("\n")
        if len(lines) > limit + 1:  # +1 for header
            return (
                "\n".join(lines[: limit + 1])
                + f"\n... ({len(lines) - limit - 1} more entries)"
            )

        return context
    except Exception as e:
        logger.error("get_error_logs failed for %s: %s", device_id, e)
        return f"Error retrieving error logs for {device_id}: {e}"


# ---------------------------------------------------------------------------
# Tool 4: get_command_history
# ---------------------------------------------------------------------------


async def get_command_history(device_id: str) -> str:
    """Retrieve recent commands sent to a device, including payloads and results.

    Args:
        device_id: The device identifier to fetch command history for.

    Returns:
        Recent commands with their types, statuses, payloads, and results.
    """
    try:
        context = await ContextBuilder.get_command_context(device_id=device_id)
        if not context:
            return f"No command history found for device '{device_id}'."
        return context
    except Exception as e:
        logger.error("get_command_history failed for %s: %s", device_id, e)
        return f"Error retrieving command history for {device_id}: {e}"


# ---------------------------------------------------------------------------
# Tool 5: get_config_history
# ---------------------------------------------------------------------------


async def get_config_history(device_id: str) -> str:
    """Retrieve recent configuration changes for a device.

    Args:
        device_id: The device identifier to fetch config history for.

    Returns:
        Recent configuration change entries with timestamps and old/new values.
    """
    try:
        context = await ContextBuilder.get_config_context(device_id=device_id)
        if not context:
            return f"No configuration history found for device '{device_id}'."
        return context
    except Exception as e:
        logger.error("get_config_history failed for %s: %s", device_id, e)
        return f"Error retrieving config history for {device_id}: {e}"


# ---------------------------------------------------------------------------
# Tool 6: search_similar_incidents
# ---------------------------------------------------------------------------


def search_similar_incidents(query: str) -> str:
    """Search for similar past incidents and their resolutions using vector similarity.

    Args:
        query: A description of the issue to search for (e.g., 'POS device
               intermittent connectivity drops after config update').

    Returns:
        A list of similar past incidents with their content, metadata, and
        similarity scores.
    """
    try:
        device_memory = DeviceMemory()
        results = device_memory.query_similar(query, n_results=5)

        if not results:
            return "No similar incidents found in memory."

        parts = ["[SIMILAR PAST INCIDENTS]"]
        for i, mem in enumerate(results, 1):
            content = mem.get("content", "")[:300]
            metadata = mem.get("metadata", {})
            distance = mem.get("distance", 0)
            parts.append(f"{i}. (similarity={1 - distance:.2f}) {content}")
            if metadata:
                parts.append(f"   Metadata: {json.dumps(metadata, default=str)}")
        return "\n".join(parts)
    except Exception as e:
        logger.error("search_similar_incidents failed: %s", e)
        return f"Error searching similar incidents: {e}"


# ---------------------------------------------------------------------------
# Tool 7: get_fleet_summary
# ---------------------------------------------------------------------------


async def get_fleet_summary() -> str:
    """Get a high-level summary of the entire device fleet.

    Returns:
        Fleet-wide statistics including total sites, total active devices,
        online/offline counts, healthy/unhealthy counts, and devices by mode
        (simulated/emulated/real).
    """
    try:
        from homepot.database import get_database_service
        from homepot.models import Device, Site

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # Site count
            site_stmt = select(Site).where(Site.is_archived.is_(False))
            site_result = await session.execute(site_stmt)
            sites = site_result.scalars().all()
            total_sites = len(sites)

            # Device count
            dev_stmt = select(Device).where(Device.is_archived.is_(False))
            dev_result = await session.execute(dev_stmt)
            devices = dev_result.scalars().all()
            total_devices = len(devices)

            online = sum(
                1
                for d in devices
                if d.last_heartbeat and hasattr(d.last_heartbeat, "timestamp")
            )
            healthy = sum(1 for d in devices if d.health_state == "healthy")

            modes = {}
            for d in devices:
                mode = getattr(d, "mode", "unknown") or "unknown"
                modes[mode] = modes.get(mode, 0) + 1

            parts = [
                "[FLEET SUMMARY]",
                f"Total Sites: {total_sites}",
                f"Total Active Devices: {total_devices}",
                f"Online: {online}",
                f"Healthy: {healthy}",
                f"Unhealthy: {total_devices - healthy}",
            ]
            for mode, count in sorted(modes.items()):
                parts.append(f"  {mode}: {count}")
            return "\n".join(parts)
    except Exception as e:
        logger.error("get_fleet_summary failed: %s", e)
        return f"Error retrieving fleet summary: {e}"


# ---------------------------------------------------------------------------
# Tool 8: get_alerts
# ---------------------------------------------------------------------------


async def get_alerts(severity: Optional[str] = None) -> str:
    """Retrieve active system alerts, optionally filtered by severity.

    Args:
        severity: Optional severity filter ('critical', 'warning', 'info').
                  If None, returns all active alerts.

    Returns:
        Active alerts with their severity, device, title, and description.
    """
    try:
        from homepot.database import get_database_service
        from homepot.models import Alert

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            stmt = select(Alert).where(Alert.status == "active")
            if severity:
                stmt = stmt.where(Alert.severity == severity.lower())
            stmt = stmt.order_by(Alert.created_at.desc()).limit(20)

            result = await session.execute(stmt)
            alerts = result.scalars().all()

            if not alerts:
                filter_text = f" with severity '{severity}'" if severity else ""
                return f"No active alerts{filter_text}."

            parts = ["[ACTIVE ALERTS]"]
            for alert in alerts:
                parts.append(
                    f"- [{alert.severity.upper()}] {alert.title}"
                    f" (Device: {getattr(alert, 'device_id', 'N/A')})"
                    f"\n  {alert.description}"
                )
            return "\n".join(parts)
    except Exception as e:
        logger.error("get_alerts failed: %s", e)
        return f"Error retrieving alerts: {e}"


# ---------------------------------------------------------------------------
# Tool registry for the agent loop
# ---------------------------------------------------------------------------

# Map of tool name → (function, is_async)
TOOL_REGISTRY = {
    "get_device_status": (get_device_status, True),
    "get_device_metrics": (get_device_metrics, True),
    "get_error_logs": (get_error_logs, True),
    "get_command_history": (get_command_history, True),
    "get_config_history": (get_config_history, True),
    "search_similar_incidents": (search_similar_incidents, False),
    "get_fleet_summary": (get_fleet_summary, True),
    "get_alerts": (get_alerts, True),
}

# Tool functions list for Ollama SDK (auto-generates JSON schema)
TOOL_FUNCTIONS = [
    get_device_status,
    get_device_metrics,
    get_error_logs,
    get_command_history,
    get_config_history,
    search_similar_incidents,
    get_fleet_summary,
    get_alerts,
]
