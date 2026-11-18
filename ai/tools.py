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
from ai.context_builder import (
    COMMAND_HISTORY_FRESH_WINDOW_MINUTES,
    ContextBuilder,
    command_age_seconds,
    format_command_age,
    summarize_command_result,
)
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
# Compose-template grounding — per-run ContextVar
# ---------------------------------------------------------------------------
#
# Imperative requests must be mapped onto a registry-backed Compose Command
# template before a proposal tool can be used. Without this, the model can
# invent a plausible-sounding action or stuff a bespoke shell command into
# ``run_command``. The agent marks grounding as required for action runs;
# ``list_compose_templates`` marks it satisfied, and the proposal tools refuse
# until then. Direct tool tests that call ``propose_device_action`` outside an
# agent run are unaffected because grounding is only required when the agent
# explicitly asks for it.

_TEMPLATE_GROUNDING_STATE: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tool_template_grounding_state", default="not_required"
)


def set_tool_template_grounding(required: bool) -> contextvars.Token:
    """Require (or waive) a Compose template lookup for this run."""
    return _TEMPLATE_GROUNDING_STATE.set("required" if required else "not_required")


def reset_tool_template_grounding(token: contextvars.Token) -> None:
    """Restore the previous template-grounding state using ``set_...`` token."""
    _TEMPLATE_GROUNDING_STATE.reset(token)


def mark_compose_templates_loaded() -> None:
    """Record that the registry-backed template list was read this run."""
    _TEMPLATE_GROUNDING_STATE.set("loaded")


def compose_templates_required() -> bool:
    """Return True when this run requires a template lookup before proposing."""
    return _TEMPLATE_GROUNDING_STATE.get() == "required"


def compose_templates_loaded() -> bool:
    """Return True when this run has already read the template registry."""
    return _TEMPLATE_GROUNDING_STATE.get() == "loaded"


def template_grounding_error() -> Optional[str]:
    """Return a tool-level refusal when a required template lookup was skipped."""
    if compose_templates_required() and not compose_templates_loaded():
        return (
            "Proposal NOT recorded: call list_compose_templates first. Match the "
            "request to a registry-backed Compose Command template and use only "
            "that action name and parameter keys; do not invent an action or a "
            "raw run_command string for a named capability."
        )
    return None


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
    role_rank = {"viewer": 0, "manager": 1, "admin": 2}
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
    """Check the status HOMEPOT last recorded for a device (cached telemetry).

    A summary of the agent's latest status report, not a live query of the
    machine. For a live OS and hardware inventory, propose the get_system_info
    action.

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
    """Retrieve HOMEPOT-recorded device events, not the device's own OS log.

    Returns the status reports and command events the platform recorded for the
    device. For the machine's own log, propose the tail_system_log action.

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

    Command records are historical audit evidence, not live readings. Only
    results from the last 30 minutes are included; older commands keep their
    metadata and payload but have their result removed.

    Args:
        device_id: The device identifier to fetch command history for.

    Returns:
        Recent commands with types, statuses, ages and fresh result payloads.
    """
    try:
        context = await ContextBuilder.get_command_context(device_id=device_id)
        if not context:
            return f"No command history found for device '{device_id}'."
        return context
    except Exception as e:
        logger.error("get_command_history failed for %s: %s", device_id, e)
        return f"Error retrieving command history for {device_id}: {e}"


async def get_command(device_id: str, command_id: str) -> str:
    """Fetch one command's full result (stdout/stderr/error/exit code).

    Unlike ``get_command_history`` (a compact list), this returns the detailed
    result for a specific command so the assistant can explain a failure and
    suggest the correct follow-up.

    Args:
        device_id: Device identifier the command was sent to.
        command_id: The command identifier (from history or a queued action).

    Returns:
        A string with the command's metadata, payload, and full result.
    """
    try:
        from homepot.database import get_database_service

        db = await get_database_service()
        command = await db.get_command(command_id)
        if command is None:
            return f"Command '{command_id}' not found."

        if device_id:
            device = await db.get_device_by_device_id(device_id)
            if device is None:
                return f"Device '{device_id}' not found."
            if command.device_id != device.id:
                return (
                    f"Command '{command_id}' does not belong to device '{device_id}'."
                )

        age = command_age_seconds(command.executed_at or command.created_at)
        lines = [
            f"command_id={command.command_id}",
            f"type={command.command_type}",
            f"status={command.status}",
            f"created={command.created_at.isoformat() if command.created_at else None}",
            f"executed_at={command.executed_at.isoformat() if command.executed_at else None}",
            f"issued_by={command.issued_by}",
            "note=This is a past command record from "
            f"{format_command_age(age)}, not a live reading; propose a fresh "
            "action for current device state."
            + (
                f" Older than the {COMMAND_HISTORY_FRESH_WINDOW_MINUTES}-minute "
                "fresh window, so get_command_history omits its result."
                if age is not None and age > COMMAND_HISTORY_FRESH_WINDOW_MINUTES * 60
                else ""
            ),
        ]
        if command.payload:
            payload = json.dumps(command.payload, default=str)
            if len(payload) > 1000:
                payload = payload[:1000] + "..."
            lines.append(f"payload={payload}")
        result = summarize_command_result(command.result, field_max=2000, tail_max=2000)
        if result:
            lines.append(f"result={result}")
        return "\n".join(lines)
    except Exception as e:
        logger.error("get_command failed for %s/%s: %s", device_id, command_id, e)
        return f"Error retrieving command '{command_id}': {e}"


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


def _tool_connectivity(device: Any) -> str:
    """Compute online/offline/unknown for a device (mirrors the dashboard)."""
    try:
        from datetime import datetime, timezone

        if getattr(device, "lifecycle_state", None) != "active":
            return "offline"
        status = getattr(device, "status", None)
        if status == "offline":
            return "offline"
        hb = getattr(device, "last_heartbeat_at", None)
        if not hb:
            return "unknown"
        if getattr(hb, "tzinfo", None) is None:
            hb = hb.replace(tzinfo=timezone.utc)
        from homepot.config import get_settings

        threshold = getattr(get_settings().devices, "device_offline_threshold", 300)
        delta = (datetime.now(timezone.utc) - hb).total_seconds()
        return "online" if delta <= threshold else "offline"
    except Exception:
        return "unknown"


def _device_online_gate(device_id: str) -> Optional[str]:
    """Return an error string when a device is missing or not online.

    A proposal targets a real, currently-online device, so the model cannot
    suggest an action the device would never receive (offline) or a device that
    no longer exists. Returns ``None`` when the device is online. Uses the same
    ``compute_connectivity`` the Dashboard does, so the AI never disagrees with
    the UI on online/offline. Failures fail closed (no proposal) rather than
    allow an action on an unverifiable device.
    """
    try:
        from homepot.database import SessionLocal
        from homepot.models import (
            ConnectivityState,
        )
        from homepot.models import (
            compute_connectivity,
        )
        from homepot.models import Device as DeviceModel

        db = SessionLocal()
        try:
            device = (
                db.query(DeviceModel).filter(DeviceModel.device_id == device_id).first()
            )
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 - fail closed, do not propose
        return f"could not verify device connectivity: {exc}"

    if device is None:
        return f"target device '{device_id}' not found"

    connectivity = compute_connectivity(device)
    if connectivity != ConnectivityState.ONLINE.value:
        return f"target device '{device_id}' is {connectivity}"

    return None


# ---------------------------------------------------------------------------
# Tool 6c: list_devices (full device list at a site or across the fleet)
# ---------------------------------------------------------------------------


async def list_devices(
    site_id: str = "all",
    status_filter: str = "active",
    limit: int = 50,
) -> str:
    """List devices at a site (or across the fleet) in a compact form.

    Use this when the user asks which devices are at a site, or when you need
    the full device_id list for a site (the ambient system status only shows
    the first 25 devices per site). Returns a compact one-line row per device.

    Args:
        site_id: Business site id to filter by, or "all" (default) for every
            site.
        status_filter: One of "active" (default, non-suspended paired devices),
            "suspended", "unpaired", or "all" (every paired device). "active"
            excludes suspended/unpaired; "all" includes suspended.
            status_filter values are case-insensitive.
        limit: Maximum rows to return (default 50, max 200).

    Returns:
        A compact list of devices, or "No devices found" if none match.
    """
    try:
        scope = get_tool_user_scope()
        from homepot.database import get_database_service
        from homepot.models import PAIRED_LIFECYCLE_STATES, Device, Site

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            stmt = select(Device, Site).join(
                Site, Device.site_id == Site.id, isouter=True
            )

            # Site filter
            if site_id and site_id.strip().lower() not in ("", "all", "*"):
                site = (
                    await session.execute(
                        select(Site).where(Site.site_id == site_id.strip())
                    )
                ).scalar_one_or_none()
                if site is None:
                    return f"Site not found: {site_id!r}."
                stmt = stmt.where(Device.site_id == site.id)

            # Status filter
            sf = (status_filter or "active").strip().lower()
            if sf == "active":
                stmt = stmt.where(Device.is_active.is_(True))
            elif sf == "suspended":
                stmt = stmt.where(Device.lifecycle_state == "suspended")
            elif sf == "unpaired":
                stmt = stmt.where(Device.lifecycle_state == "unpaired")
            elif sf == "all":
                stmt = stmt.where(Device.lifecycle_state.in_(PAIRED_LIFECYCLE_STATES))
            else:
                return (
                    f"Unknown status_filter {status_filter!r}; use one of "
                    "'active', 'suspended', 'unpaired', 'all'."
                )

            stmt = stmt.order_by(Device.name, Device.device_id).limit(
                min(max(int(limit or 50), 1), 200)
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
                matches.append((dev, site))

        if not matches:
            return "No devices found."

        lines = [f"Found {len(matches)} device(s):"]
        for dev, site in matches:
            site_name = site.name if site else "?"
            lines.append(
                f"  - {dev.name} ({dev.device_id}) | site={site_name} | "
                f"{dev.device_type} | "
                f"{'online' if _tool_connectivity(dev) == 'online' else 'offline'} | "
                f"{dev.health_state or 'unknown'} | {dev.lifecycle_state}"
            )
        lines.append(
            "Use the device_id value with other device tools (e.g. "
            "get_device_status)."
        )
        return "\n".join(lines)
    except Exception as e:
        logger.error("list_devices failed: %s", e, exc_info=True)
        return f"Error listing devices: {e}"


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
# Tool 8b: list_compose_templates
# ---------------------------------------------------------------------------


def list_compose_templates(action: str = "") -> str:
    """List registry-backed Compose Command templates before proposing an action.

    Call this tool FIRST for every imperative device request, before
    ``propose_device_action`` or ``propose_fleet_action``. The compact list maps
    the request to a template key and registered action. Call it again with an
    ``action`` value to see that template's full default parameters, then use
    only that action name and those parameter keys in the proposal. Never
    invent a new action or a bespoke ``run_command`` string for a named
    capability such as setting volume or restarting a service.

    Args:
        action: Optional registered action name to show full template details.
            Leave empty to list every template compactly.

    Returns:
        The matching Compose Command template(s) from the shared backend registry.
    """
    try:
        from homepot.app.ai_ops.compose_templates import COMPOSE_TEMPLATES
    except Exception as e:
        logger.error("list_compose_templates failed: %s", e)
        return f"Error loading Compose Command templates: {e}"

    wanted = (action or "").strip()
    entries = [
        (key, template)
        for key, template in COMPOSE_TEMPLATES.items()
        if not wanted or str(template.get("action", "")) == wanted
    ]
    if not entries:
        return f"No Compose Command template found for action '{wanted}'."

    mark_compose_templates_loaded()
    if wanted:
        payload = {
            key: {
                "label": template.get("label"),
                "action": template.get("action"),
                "group": template.get("group"),
                "permission": template.get("permission"),
                "defaultData": template.get("defaultData"),
                "defaultDataByOS": template.get("defaultDataByOS", {}),
                "description": template.get("description"),
            }
            for key, template in entries
        }
        return json.dumps(payload, default=str)

    lines = [
        "REGISTRY-BACKED COMPOSE COMMAND TEMPLATES",
        "Call list_compose_templates(action=...) for one template's full defaults.",
    ]
    for key, template in entries:
        params = ", ".join(sorted((template.get("defaultData") or {}).keys())) or "-"
        lines.append(
            f"- {key}: {template.get('label')} -> {template.get('action')} "
            f"[{params}]"
        )
    return "\n".join(lines)


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
FIRST call list_compose_templates and choose a registry-backed template; use
only its action and parameter keys. Never invent an action or a bespoke
run_command string for a named capability such as setting volume.
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


def _normalize_network_test_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Split a ``host:port`` value into separate ``host`` and ``port`` params.

    The device probes DNS and ICMP with ``host`` as given, so a port appended
    to the hostname makes both checks fail. IPv6 literals (multiple colons)
    and explicitly supplied ports are left alone.

    Args:
        params: Parsed proposal parameters.

    Returns:
        The original parameters or a copy with the port separated out.
    """
    host = params.get("host")
    if not isinstance(host, str) or host.count(":") != 1:
        return params
    name, _, value = host.rpartition(":")
    if not name or not value.isdigit() or params.get("port") is not None:
        return params
    normalized = dict(params)
    normalized["host"] = name
    normalized["port"] = int(value)
    return normalized


async def propose_device_action(
    action: str,
    target_device_id: str,
    rationale: str,
    params: Optional[str] = None,
) -> str:
    """Propose a device-management action for technician approval."""
    grounding_error = template_grounding_error()
    if grounding_error is not None:
        return grounding_error

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
    access_error = await _check_device_access(target_device_id, "manager")
    if access_error:
        return access_error

    # The target must be online: the model must not propose an action the
    # device would never receive (offline/unknown) or a device that no longer
    # exists (a stale proposal that cannot be executed).
    online_error = _device_online_gate(target_device_id)
    if online_error:
        return f"Proposal rejected: {online_error}"

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

    normalization_note = ""
    if action == "network_test":
        normalized = _normalize_network_test_params(parsed)
        if normalized != parsed:
            normalization_note = (
                " Normalized 'host:port' into separate 'host' and 'port' params."
            )
        parsed = normalized

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
        f"(risk {spec.risk_tier}, reversible={spec.reversible})."
        f"{normalization_note} "
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
    grounding_error = template_grounding_error()
    if grounding_error is not None:
        return grounding_error.replace(
            "Proposal NOT recorded", "Proposals NOT recorded"
        )

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
            err = await _check_device_access(str(d.device_id), "manager")
            if err:
                denied.append(str(d.device_id))
        if denied:
            return (
                "Access denied for device(s): "
                + ", ".join(denied)
                + ". Fleet proposal aborted."
            )

        from ai.actions import validate_proposal
        from homepot.models import ConnectivityState, compute_connectivity

        sink = get_tool_proposal_sink()
        if sink is None:
            return (
                f"Validated scope ({len(devices)} device(s)) but no proposal sink "
                "is active; nothing was recorded."
            )

        recorded = 0
        rejected: list[str] = []
        for d in devices:
            connectivity = compute_connectivity(d)
            if connectivity != ConnectivityState.ONLINE.value:
                rejected.append(f"{d.device_id}: device is {connectivity}")
                continue
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
    "get_command": (get_command, True),
    "get_config_history": (get_config_history, True),
    "search_similar_incidents": (search_similar_incidents, False),
    "get_fleet_summary": (get_fleet_summary, True),
    "find_device": (find_device, True),
    "list_devices": (list_devices, True),
    "get_alerts": (get_alerts, True),
    "list_compose_templates": (list_compose_templates, False),
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
    get_command,
    get_config_history,
    search_similar_incidents,
    get_fleet_summary,
    find_device,
    list_devices,
    get_alerts,
    list_compose_templates,
    propose_device_action,
    propose_fleet_action,
    get_action_plan_status,
]
