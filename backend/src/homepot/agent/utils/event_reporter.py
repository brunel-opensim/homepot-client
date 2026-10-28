"""Structured event reporting for the real device agent.

The agent already reports status snapshots to the Live Logs endpoint and
audit events to the Audit Trail endpoint.  This module provides convenience
helpers that emit *structured* events (lifecycle, connectivity, permission,
resource, command) so the Dashboard can surface them in the "Live Logs" and
"Audit Trail" tabs without the technician having to read raw log files.

All helpers are fire-and-forget: they catch and log exceptions internally so
they never crash the calling loop.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from homepot.agent.utils.errors import classify_status

logger = logging.getLogger(__name__)


async def emit_log_event(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    *,
    level: str = "info",
    category: str = "device",
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Send a structured log event to ``POST /api/v1/agent/logs``.

    Fire-and-forget: exceptions are caught and logged, never propagated.
    """
    url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/logs"
    payload: Dict[str, Any] = {
        "device_id": config["device_id"],
        "level": level,
        "category": category,
        "message": message,
        "timestamp": None,
    }
    if context is not None:
        payload["context"] = context
    try:
        from datetime import datetime, timezone

        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        headers = {
            "X-Device-ID": str(config["device_id"]),
            "X-API-Key": str(config.get("api_key", "")),
        }
        response = await client.post(url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        err = classify_status(url, e.response.status_code)
        if err is not None:
            logger.error("Permanent failure reporting log event: %s", err)
        else:
            logger.warning(
                "Log event post failed url=%s status=%s", url, e.response.status_code
            )
    except Exception as e:
        logger.warning("Log event post failed url=%s error=%s", url, e)


async def emit_audit_event(
    client: httpx.AsyncClient,
    config: Dict[str, Any],
    *,
    event_type: str,
    description: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Send a structured audit event to ``POST /api/v1/agent/audit``.

    Fire-and-forget: exceptions are caught and logged, never propagated.
    """
    url = f"{config['backend_url'].rstrip('/')}/api/v1/agent/audit"
    payload: Dict[str, Any] = {
        "device_id": config["device_id"],
        "event_type": event_type,
        "description": description,
    }
    if metadata is not None:
        payload["metadata"] = metadata
    try:
        from datetime import datetime, timezone

        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        headers = {
            "X-Device-ID": str(config["device_id"]),
            "X-API-Key": str(config.get("api_key", "")),
        }
        response = await client.post(url, json=payload, headers=headers, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        err = classify_status(url, e.response.status_code)
        if err is not None:
            logger.error("Permanent failure reporting audit event: %s", err)
        else:
            logger.warning(
                "Audit event post failed url=%s status=%s", url, e.response.status_code
            )
    except Exception as e:
        logger.warning("Audit event post failed url=%s error=%s", url, e)
