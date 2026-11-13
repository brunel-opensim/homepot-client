"""Agentic AI Tool Definitions.

Tool functions for the ReAct agent loop. Each tool is a Python function with
type hints and docstrings — the Ollama SDK auto-generates JSON schema from
them. Tools wrap existing ContextBuilder methods and database queries.

See docs/ai-agentic.md for the full architecture.
"""

import contextvars
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.actions import ActionProposal, allowed_actions_summary, validate_proposal
from ai.context_builder import ContextBuilder
from ai.device_memory import DeviceMemory, MemoryScope

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-request tool scope
# ---------------------------------------------------------------------------
#
# Tool functions must keep simple, schema-friendly signatures (Ollama derives
# the JSON schema from the type hints), so the caller's access scope cannot be a
# normal parameter. Instead the agent sets it in a ContextVar for the duration
# of a run and the tools that read user data consult it. This keeps agentic
# recall scoped exactly like the direct path, without leaking scope into the
# model-visible tool schema.

_tool_memory_scope: contextvars.ContextVar[Optional[MemoryScope]] = (
    contextvars.ContextVar("tool_memory_scope", default=None)
)


def set_tool_memory_scope(scope: Optional[MemoryScope]) -> contextvars.Token:
    """Bind the caller's memory scope for the current run; returns a token."""
    return _tool_memory_scope.set(scope)


def reset_tool_memory_scope(token: contextvars.Token) -> None:
    """Restore the previous memory scope using the token from ``set_...``."""
    _tool_memory_scope.reset(token)


def get_tool_memory_scope() -> Optional[MemoryScope]:
    """Return the memory scope bound to the current run (or ``None``)."""
    return _tool_memory_scope.get()


# ---------------------------------------------------------------------------
# Per-request proposal sink
# ---------------------------------------------------------------------------
#
# Like the memory scope, the proposal collector is a ContextVar so tools keep
# schema-friendly signatures. When the agent starts a run it binds an empty list
# here; ``propose_device_action`` appends validated proposals to it, and the
# endpoint reads the list once the run finishes (see docs/ai-delegation-plan.md,
# Phase 1). Nothing is executed — this is a dry-run capture only.

_tool_proposal_sink: contextvars.ContextVar[Optional[List[ActionProposal]]] = (
    contextvars.ContextVar("tool_proposal_sink", default=None)
)


def set_tool_proposal_sink(sink: Optional[List[ActionProposal]]) -> contextvars.Token:
    """Bind the proposal collector for the current run; returns a token."""
    return _tool_proposal_sink.set(sink)


def reset_tool_proposal_sink(token: contextvars.Token) -> None:
    """Restore the previous proposal collector using the token from ``set_...``."""
    _tool_proposal_sink.reset(token)


def get_tool_proposal_sink() -> Optional[List[ActionProposal]]:
    """Return the proposal collector bound to the current run (or ``None``)."""
    return _tool_proposal_sink.get()


# ---------------------------------------------------------------------------
# Per-request proposal gating
# ---------------------------------------------------------------------------
#
# The validation envelope decides whether an answer is actionable *before* the
# agent runs. When it is not (e.g. Gate B failed on stale telemetry) the
# endpoint deliberately drops any captured proposals rather than surfacing
# them. Without telling the tools, though, ``propose_device_action`` would
# still report "Recorded proposal" to the model, which then tells the
# technician a proposal exists even though nothing was persisted (observed on
# Brunel Device 001, 2026-11). This ContextVar carries the block reason
# (``None`` = proposals allowed) so the tools refuse honestly instead.

_tool_proposal_block_reason: contextvars.ContextVar[Optional[str]] = (
    contextvars.ContextVar("tool_proposal_block_reason", default=None)
)


def set_tool_proposal_block_reason(reason: Optional[str]) -> contextvars.Token:
    """Bind a reason that forbids proposals for this run; returns a token."""
    return _tool_proposal_block_reason.set(reason)


def reset_tool_proposal_block_reason(token: contextvars.Token) -> None:
    """Restore the previous proposal-block reason using a token."""
    _tool_proposal_block_reason.reset(token)


def get_tool_proposal_block_reason() -> Optional[str]:
    """Return the reason proposals are blocked for this run, or ``None``."""
    return _tool_proposal_block_reason.get()


# ---------------------------------------------------------------------------
# User scope (RBAC) — per-run ContextVar
# ---------------------------------------------------------------------------
# Tracks the authenticated user's accessible device IDs and minimum role for
# the current agent run.  Tools use this to enforce per-device RBAC instead
# of accepting any device_id blindly.

_tool_user_scope: contextvars.ContextVar[Optional[Dict[str, Any]]] = (
    contextvars.ContextVar("tool_user_scope", default=None)
)


def set_tool_user_scope(scope: Optional[Dict[str, Any]]) -> contextvars.Token:
    """Bind the caller's user scope for the current agent run."""
    return _tool_user_scope.set(scope)


def reset_tool_user_scope(token: contextvars.Token) -> None:
    """Reset the user scope ContextVar."""
    _tool_user_scope.reset(token)


def get_tool_user_scope() -> Optional[Dict[str, Any]]:
    """Return the active user scope, or ``None`` if not bound."""
    return _tool_user_scope.get()


async def _check_device_access(
    device_id: str, minimum_role: str = "viewer"
) -> Optional[str]:
    """Verify the caller has access to ``device_id``.

    Returns ``None`` if access is granted, or an error message string if denied.
    When no user scope is bound (e.g. tests, direct calls), access is allowed
    for backward compatibility.
    """
    scope = get_tool_user_scope()
    if scope is None:
        return None  # no scope bound → allow (backward compat)

    accessible = scope.get("accessible_device_ids")
    accessible_sites = scope.get("accessible_site_ids")
    if accessible is not None and device_id not in accessible:
        # Fall back to site-level check
        if accessible_sites is not None:
            try:
                from homepot.database import SessionLocal
                from homepot.models import Device as DeviceModel

                db = SessionLocal()
                try:
                    device = (
                        db.query(DeviceModel)
                        .filter(DeviceModel.device_id == device_id)
                        .first()
                    )
                    if device is not None and device.site_id not in accessible_sites:
                        return f"Access denied: device '{device_id}' is outside your scope."
                finally:
                    db.close()
            except Exception:
                pass  # On error, fall through
        else:
            return f"Access denied: device '{device_id}' is outside your scope."

    # Role check
    user_role = scope.get("role", "viewer")
    role_rank = {"viewer": 0, "operator": 1, "admin": 2}
    if role_rank.get(user_role, 0) < role_rank.get(minimum_role, 0):
        return (
            f"Access denied: '{minimum_role}' role required for device "
            f"'{device_id}', you have '{user_role}'."
        )
    return None


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


async def _gate_b_note(device_id: str) -> str:
    """Run a lightweight Gate B freshness check on a device's telemetry.

    Returns a short annotation the tool output carries so the LLM (and the
    operator) can see whether the underlying data is fresh enough to trust.
    """
    try:
        from datetime import datetime

        from homepot.app.models.AnalyticsModel import DeviceMetrics
        from homepot.database import get_database_service

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            int_id = await _resolve_device_int_id(session, device_id)
            if int_id is None:
                return "[Gate B: device not found]"
            from sqlalchemy import func as _func

            stmt = select(_func.max(DeviceMetrics.timestamp)).where(
                DeviceMetrics.device_id == int_id
            )
            result = await session.execute(stmt)
            latest = result.scalar_one_or_none()
            if latest is None:
                return "[Gate B: no telemetry recorded - treat with caution]"
            age = (datetime.utcnow() - latest).total_seconds()
            if age > 300:
                return (
                    f"[Gate B: stale telemetry (last sample {int(age)}s ago) - "
                    "treat with caution]"
                )
            return "[Gate B: telemetry fresh]"
    except Exception as e:
        logger.debug("Gate B note failed for %s: %s", device_id, e)
        return "[Gate B: unavailable]"


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
        access_error = await _check_device_access(device_id, "viewer")
        if access_error:
            return access_error
        context = await ContextBuilder.get_metadata_context(device_id=device_id)
        if not context:
            return f"No device found with ID '{device_id}'."
        note = await _gate_b_note(device_id)
        return f"{context}\n{note}"
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
        access_error = await _check_device_access(device_id, "viewer")
        if access_error:
            return access_error
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
                note = await _gate_b_note(device_id)
                return "\n".join(filtered) + "\n" + note
            return (
                f"Metric '{metric}' not found in recent data for {device_id}."
                f" Available metrics:\n{context}"
            )

        note = await _gate_b_note(device_id)
        return f"{context}\n{note}"
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
        results = device_memory.query_similar(
            query, n_results=5, scope=get_tool_memory_scope()
        )

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
# Tool 6b: find_device (resolve a name or partial ID to a device)
# ---------------------------------------------------------------------------


async def find_device(query: str) -> str:
    """Find devices whose name or ID matches a search term.

    Use this when the user refers to a device by name (e.g. "Brunel Device 001")
    or a partial ID, and you need the business device_id to call other tools.
    Returns a list of matching devices with their device_id, name, site and status.

    Args:
        query: A device name, partial name, site name, or partial device ID.

    Returns:
        A list of matching devices, or "No devices found" if none match.
    """
    try:
        scope = get_tool_user_scope()
        from homepot.database import get_database_service
        from homepot.models import Device, Site

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            term = f"%{query.strip()}%"
            stmt = (
                select(Device, Site)
                .join(Site, Device.site_id == Site.id, isouter=True)
                .where(
                    (Device.device_id.ilike(term))
                    | (Device.name.ilike(term))
                    | (Site.name.ilike(term))
                )
                .limit(20)
            )
            rows = (await session.execute(stmt)).all()

            # RBAC: filter to accessible devices/sites if scope is bound.
            accessible = None
            accessible_sites = None
            if scope is not None:
                accessible = scope.get("accessible_device_ids")
                accessible_sites = scope.get("accessible_site_ids")

            matches = []
            for dev, site in rows:
                if accessible is not None and dev.device_id not in accessible:
                    if accessible_sites is not None and (
                        site is None or site.id not in accessible_sites
                    ):
                        continue
                matches.append(
                    {
                        "device_id": dev.device_id,
                        "name": getattr(dev, "name", None),
                        "site": getattr(site, "name", None) if site else None,
                        "status": getattr(dev, "health_state", None)
                        or getattr(dev, "lifecycle_state", None),
                    }
                )

        if not matches:
            return f"No devices found matching '{query}'."

        lines = [f"Found {len(matches)} device(s) matching '{query}':"]
        for m in matches:
            lines.append(
                f"  - {m['device_id']} | {m['name']} | site={m['site']} | "
                f"status={m['status']}"
            )
        lines.append(
            "Use the device_id value (e.g. DEVICE-XXXX-XXXX-XXXX) with other "
            "device tools."
        )
        return "\n".join(lines)
    except Exception as e:
        logger.error("find_device failed for %r: %s", query, e)
        return f"Error searching devices: {e}"


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
            site_stmt = select(Site).where(Site.is_active.is_(True))
            site_result = await session.execute(site_stmt)
            sites = site_result.scalars().all()
            total_sites = len(sites)

            # Device count
            dev_stmt = select(Device).where(Device.is_active.is_(True))
            dev_result = await session.execute(dev_stmt)
            devices = dev_result.scalars().all()
            total_devices = len(devices)

            from homepot.models import compute_connectivity as _cc

            online = sum(1 for d in devices if _cc(d) == "online")
            healthy = sum(1 for d in devices if d.health_state == "healthy")

            modes: dict[str, int] = {}
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
        from homepot.app.models.AnalyticsModel import Alert
        from homepot.database import get_database_service

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            stmt = select(Alert).where(Alert.status == "active")
            if severity:
                stmt = stmt.where(Alert.severity == severity.lower())
            stmt = stmt.order_by(Alert.timestamp.desc()).limit(20)

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
# Tool 9: propose_device_action
# ---------------------------------------------------------------------------

# The full tool docstring is built once from the action registry so the
# advertised action list can never drift from ACTION_REGISTRY.
_PROPOSE_DEVICE_ACTION_DOC = f"""Propose a device-management action for technician
approval (does NOT execute).

ALWAYS use this when the user asks you to DO something on a device, even
if you already have the data in context. Keywords that imply an action:
"run", "list", "scan", "check", "start", "stop", "install", "execute",
"show me processes", "show me connections", "what programs are installed".
This records a *proposal* only: a technician must review and approve
before anything runs. Never claim an action was performed — always tell
the user it is pending approval.

Do NOT use this for purely informational questions ("what is the status",
"how is it performing", "explain", "summarize") — answer those directly.
But "list processes" is an ACTION (propose it), while "what is the CPU
usage" is informational (answer directly).

Args:
    action: The proposed action. Must be one of the registered actions:
        {allowed_actions_summary()}
    target_device_id: The device identifier the action applies to. If you only
    have a device name, call find_device first to resolve the business ID.
    rationale: Why the action is recommended, citing the evidence you
            observed (metrics, errors, config history).
    params: Optional JSON object string of action parameters, e.g.
            '{{"config": {{"log_level": "debug"}}}}'. Omit for actions such as
            'restart' that take no parameters.

Returns:
    A confirmation that the proposal was recorded (not executed), or an
    error explaining why it was rejected.
"""


async def propose_device_action(
    action: str,
    target_device_id: str,
    rationale: str,
    params: Optional[str] = None,
) -> str:
    """Propose a device-management action for technician approval."""
    block_reason = get_tool_proposal_block_reason()
    if block_reason is not None:
        return (
            "Proposal NOT recorded: the validation envelope is not actionable "
            f"({block_reason}). Do NOT tell the technician a proposal was "
            "created or is pending approval. In your final answer, explain that "
            "no proposal could be created, cite the reason above, and state "
            "what must be fixed before retrying."
        )

    # RBAC: verify the caller has access to the target device.
    access_error = await _check_device_access(target_device_id, "operator")
    if access_error:
        return access_error

    parsed: dict = {}
    if params:
        try:
            parsed = json.loads(params)
        except (TypeError, ValueError):
            return (
                f"Invalid params for '{action}': expected a JSON object string, "
                f"got {params!r}."
            )
        if not isinstance(parsed, dict):
            return f"Invalid params for '{action}': expected a JSON object."

    spec, error = validate_proposal(action, target_device_id, parsed)
    if error or spec is None:
        return f"Proposal rejected: {error}"

    proposal = ActionProposal(
        action=spec.name,
        target_device_id=str(target_device_id).strip(),
        params=parsed,
        rationale=rationale or "",
        risk_tier=spec.risk_tier,
        reversible=spec.reversible,
    )

    sink = get_tool_proposal_sink()
    if sink is None:
        return (
            f"Proposal validated ({spec.name} on {target_device_id}) but no "
            "proposal sink is active; nothing was recorded."
        )
    sink.append(proposal)

    return (
        f"Recorded proposal: {spec.name} on {target_device_id} "
        f"(risk {spec.risk_tier}, reversible={spec.reversible}). "
        "This is a PROPOSAL only — it has NOT been executed and requires "
        "technician approval. In your final answer, state clearly that the "
        "action is pending approval and must not be assumed to have happened. "
        "The technician can later ask whether it succeeded; use "
        "get_action_plan_status with the plan_id from the proposal metadata."
    )


propose_device_action.__doc__ = _PROPOSE_DEVICE_ACTION_DOC


# ---------------------------------------------------------------------------
# Tool 9b: propose_fleet_action (B5)
# ---------------------------------------------------------------------------


async def propose_fleet_action(
    action: str,
    site_id: str = "all",
    rationale: str = "",
    params: Optional[str] = None,
) -> str:
    """Propose the same device action across a fleet of devices at once.

    Expands into one per-device proposal (each still requires its own
    technician approval). Use this instead of calling propose_device_action
    repeatedly when the user asks for an action on a site or the whole fleet.

    Args:
        action: The proposed action (same allowed set as propose_device_action).
        site_id: Business site id to target, or "all" (default) for every
            active device.
        rationale: Why the action is recommended.
        params: Optional JSON object string of action parameters.

    Returns:
        A summary of how many proposals were recorded, or an error.
    """
    block_reason = get_tool_proposal_block_reason()
    if block_reason is not None:
        return (
            "Proposals NOT recorded: the validation envelope is not actionable "
            f"({block_reason}). Do NOT tell the technician any proposal was "
            "created or is pending approval. In your final answer, explain that "
            "no proposals could be created, cite the reason above, and state "
            "what must be fixed before retrying."
        )

    try:
        from homepot.database import get_database_service
        from homepot.models import Device, Site

        parsed: dict = {}
        if params:
            try:
                parsed = json.loads(params)
            except (TypeError, ValueError):
                return (
                    f"Invalid params for '{action}': expected a JSON object string, "
                    f"got {params!r}."
                )
            if not isinstance(parsed, dict):
                return f"Invalid params for '{action}': expected a JSON object."

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            if site_id and site_id.strip().lower() not in ("", "all", "*"):
                site = (
                    await session.execute(
                        select(Site).where(Site.site_id == site_id.strip())
                    )
                ).scalar_one_or_none()
                if site is None:
                    return f"Site not found: {site_id!r}."
                devices = (
                    (
                        await session.execute(
                            select(Device).where(
                                Device.site_id == site.id, Device.is_active.is_(True)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
            else:
                devices = (
                    (
                        await session.execute(
                            select(Device).where(Device.is_active.is_(True))
                        )
                    )
                    .scalars()
                    .all()
                )

        if not devices:
            return "No active devices matched the requested scope."

        # RBAC: caller must have operator access to every target device.
        denied: list[str] = []
        for d in devices:
            err = await _check_device_access(str(d.device_id), "operator")
            if err:
                denied.append(str(d.device_id))
        if denied:
            return (
                "Access denied for device(s): "
                + ", ".join(denied)
                + ". Fleet proposal aborted."
            )

        from ai.actions import validate_proposal

        sink = get_tool_proposal_sink()
        if sink is None:
            return (
                f"Validated scope ({len(devices)} device(s)) but no proposal sink "
                "is active; nothing was recorded."
            )

        recorded = 0
        rejected: list[str] = []
        for d in devices:
            spec, error = validate_proposal(action, str(d.device_id), parsed)
            if error or spec is None:
                rejected.append(f"{d.device_id}: {error}")
                continue
            proposal = ActionProposal(
                action=spec.name,
                target_device_id=str(d.device_id).strip(),
                params=parsed,
                rationale=rationale or "",
                risk_tier=spec.risk_tier,
                reversible=spec.reversible,
            )
            sink.append(proposal)
            recorded += 1

        parts = [
            f"Recorded {recorded} fleet proposal(s) for '{action}' "
            f"across {len(devices)} device(s).",
        ]
        if rejected:
            parts.append("Rejected: " + "; ".join(rejected))
        parts.append(
            "These are PROPOSALS only — they have NOT been executed and require "
            "technician approval."
        )
        return " ".join(parts)
    except Exception as e:
        logger.error("propose_fleet_action failed: %s", e)
        return f"Error proposing fleet action '{action}': {e}"


# ---------------------------------------------------------------------------
# Tool 10: get_action_plan_status
# ---------------------------------------------------------------------------


async def get_action_plan_status(plan_id: str) -> str:
    """Query the status and outcome of an AI action plan.

    Use this to check whether a previously proposed action has been approved,
    executed, succeeded, failed, or rolled back. Returns the plan's current
    status, step-level details, and outcome (if terminal).

    Args:
        plan_id: The plan identifier (UUID) returned when the proposal was
                 recorded.

    Returns:
        A JSON string with the plan status, steps, and outcome.
    """
    try:
        from homepot.app.repositories.ai_action_repository import AIActionRepository
        from homepot.database import SessionLocal

        db = SessionLocal()
        try:
            repo = AIActionRepository(db)
            plan = repo.get_plan(plan_id)
            if plan is None:
                return f"Plan '{plan_id}' not found."

            steps_info = []
            for step in plan.steps:
                steps_info.append(
                    {
                        "seq": step.seq,
                        "action": step.action,
                        "target_device_id": step.target_device_id,
                        "status": step.status,
                        "error": getattr(step, "error", None),
                    }
                )

            outcome_info = None
            if plan.outcome is not None:
                outcome_info = {
                    "verified": plan.outcome.verified,
                    "rolled_back": plan.outcome.rolled_back,
                    "error": plan.outcome.error,
                }

            result = {
                "plan_id": plan.plan_id,
                "status": plan.status,
                "risk_tier": plan.risk_tier,
                "steps": steps_info,
                "outcome": outcome_info,
            }
            return json.dumps(result, default=str)
        finally:
            db.close()
    except Exception as e:
        logger.error("get_action_plan_status failed for %s: %s", plan_id, e)
        return f"Error querying plan '{plan_id}': {e}"


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
    "find_device": (find_device, True),
    "get_alerts": (get_alerts, True),
    "propose_device_action": (propose_device_action, True),
    "propose_fleet_action": (propose_fleet_action, True),
    "get_action_plan_status": (get_action_plan_status, True),
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
    find_device,
    get_alerts,
    propose_device_action,
    propose_fleet_action,
    get_action_plan_status,
]
