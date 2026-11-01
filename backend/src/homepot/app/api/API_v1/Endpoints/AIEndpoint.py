"""AI Insights API Endpoints.

Provides REST API access to AI-powered analytics, predictions, and recommendations.
"""

import asyncio
from datetime import datetime, timezone
import logging
import os
import re
import sys
from typing import Any, Dict, List, Literal, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as SASession

from homepot.app.auth_utils import (  # noqa: E402
    get_accessible_site_ids,
    require_user,
    verify_device_belongs_to_user,
    verify_site_access_for_user,
)
from homepot.app.schemas.schemas import UserDict  # noqa: E402

# Add project root to path to allow importing 'ai' package
# Current file: backend/src/homepot/app/api/API_v1/Endpoints/AIEndpoint.py
# Root is 7 levels up
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../../../../")
)
if project_root not in sys.path:
    sys.path.append(project_root)

from ai.actions import all_reversible, max_risk_tier  # noqa: E402
from ai.agent import run_agent  # noqa: E402
from ai.analytics_service import AIAnalyticsService  # noqa: E402
from ai.anomaly_detection import AnomalyDetector  # noqa: E402
from ai.context_builder import ContextBuilder  # noqa: E402
from ai.device_memory import DeviceMemory, MemoryScope  # noqa: E402
from ai.device_resolver import DeviceResolver  # noqa: E402
from ai.doc_retriever import DocRetriever  # noqa: E402
from ai.failure_predictor import FailurePredictor  # noqa: E402
from ai.gates import (  # noqa: E402
    MODE_CAUTIONARY,
    MODE_STATUS_ONLY,
    GateContext,
    GateStatus,
    build_envelope_from_config,
)
from ai.gates import EnvelopeResult  # noqa: E402
from ai.job_scheduler import PredictiveJobScheduler  # noqa: E402
from ai.llm import LLMService  # noqa: E402
from ai.query_router import (  # noqa: E402
    MODE_KNOWLEDGE,
    resolve_query_mode,
    routing_enabled,
)
from ai.repo_tools import (  # noqa: E402
    REPO_TOOL_FUNCTIONS,
    code_access_enabled,
    get_repo_access,
    reset_repo_source_sink,
    set_repo_source_sink,
)
from ai.system_knowledge import SystemKnowledge  # noqa: E402

from homepot.app.models.AnalyticsModel import Alert  # noqa: E402
from homepot.app.models.AnalyticsModel import DeviceMetrics  # noqa: E402
from homepot.app.repositories.ai_action_repository import (  # noqa: E402
    AIActionRepository,
)
from homepot.app.utils import ai_cancel  # noqa: E402
from homepot.app.utils.ai_gate import (  # noqa: E402
    AIBusyError,
    AIConcurrencyGate,
)
from homepot.audit import AuditEventType, get_audit_logger  # noqa: E402
from homepot.database import get_database_service, get_db  # noqa: E402
from homepot.models import Device, HealthCheck, Site, User  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_user())])

# Tokens commonly used to break out of a prompt context and inject adversarial
# instructions. These are neutralized in any user-supplied text before it is
# placed into the LLM prompt (see _sanitize_ai_input).
_INJECTION_TOKENS = (
    "[INST]",
    "[/INST]",
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|assistant|>",
    "<|user|>",
    "### Instruction",
    "### System",
    "### Human:",
    "Ignore all previous instructions",
    "Ignore previous instructions",
    "Disregard all previous",
    "You are now",
    "You are a helpful",
)


def _sanitize_ai_input(text: Optional[str], label: str = "text") -> str:
    """Neutralize common prompt-injection tokens in user-supplied input.

    User-provided ``context``, ``role`` and chat ``history`` are placed into the
    LLM prompt, so they are a prompt-injection surface. This helper strips and
    flags any tokens that could be used to break out of the instruction context.
    """
    if not text:
        return ""
    sanitized = text
    flagged = 0
    for token in _INJECTION_TOKENS:
        if token.lower() in sanitized.lower():
            flagged += 1
            sanitized = sanitized.replace(token, "[neutralized]")
    if flagged:
        logger.warning(
            "Sanitized %d injection token(s) from AI %s input", flagged, label
        )
    # Limit length so a single field cannot blow out the bounded context.
    return sanitized[:4000]


# --- Device context helpers ---------------------------------------------------

# A device counts as online if it heartbeated recently (mirrors the site-status
# computation). The stored Device.status field is NOT used: it only flips to
# OFFLINE on explicit events and otherwise stays ONLINE even after a device
# stops heartbeating.
_HEARTBEAT_ONLINE_SECONDS = 120


def _device_is_online(device: Device) -> bool:
    """Return True if the device heartbeated within the online window."""
    heartbeat = device.last_heartbeat_at
    if not heartbeat:
        return False
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - heartbeat
    is_online: bool = delta.total_seconds() <= _HEARTBEAT_ONLINE_SECONDS
    return is_online


def _device_mode(device: Device) -> str:
    """Classify a device's data source: simulated, emulated or real."""
    config: dict = device.config if isinstance(device.config, dict) else {}
    if (
        device.enrollment_method == "emulated"
        or config.get("device_source") == "emulator"
    ):
        return "emulated"
    if device.is_simulated:
        return "simulated"
    return "real"


# Request/Response Models
class JobScheduleRequest(BaseModel):
    """Request model for job scheduling recommendation."""

    site_id: str = Field(..., description="Target site identifier")
    job_priority: str = Field(
        default="medium", description="Job priority: low, medium, high, critical"
    )
    earliest_start: Optional[str] = Field(
        None, description="Earliest acceptable start time (ISO format)"
    )


class SuccessProbabilityRequest(BaseModel):
    """Request model for success probability calculation."""

    site_id: str = Field(..., description="Target site identifier")
    device_id: str = Field(..., description="Target device identifier")
    scheduled_time: str = Field(..., description="Proposed execution time (ISO format)")


class ChatMessage(BaseModel):
    """Model for a single chat message."""

    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class AIQueryRequest(BaseModel):
    """Request model for AI query."""

    query: str = Field(..., description="The question or prompt for the AI")
    context: Optional[str] = Field(None, description="Optional context for the query")
    device_id: Optional[str] = Field(None, description="Optional device ID for context")
    role: Optional[str] = Field(None, description="User role of the requester")
    history: Optional[list[ChatMessage]] = Field(
        default_factory=list, description="Conversation history for short-term memory"
    )
    agentic: bool = Field(
        default=False,
        description="Enable agentic tool-calling mode for multi-step investigation",
    )
    mode: Literal["auto", "knowledge", "diagnostic"] = Field(
        default="auto",
        description=(
            "Query path: 'auto' classifies by intent (default), 'knowledge' "
            "answers from documentation without the device gates, 'diagnostic' "
            "forces the operational gated path."
        ),
    )
    session_id: Optional[str] = Field(
        None, description="Investigation session id for event streaming"
    )
    run_id: Optional[str] = Field(
        None, description="Investigation run id for event streaming"
    )
    query_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description=(
            "Client-generated id for this query. Post the same id to "
            "POST /ai/query/cancel to abandon the query (Stop/Esc); the server "
            "then discards the answer instead of remembering it."
        ),
    )


class AIQueryCancelRequest(BaseModel):
    """Request model for cancelling an in-flight AI query."""

    query_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="The query_id sent with the AI query to abandon",
    )


# ==================== LLM Provider Endpoints ====================


@router.get("/provider", tags=["AI Chat"])
async def get_llm_provider(
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Return the currently active LLM provider and available options."""
    from ai.provider import get_provider_info

    info = get_provider_info()
    # Check health of current provider
    try:
        llm, _, _ = get_ai_services()
        info["healthy"] = llm.check_health()
        info["model"] = llm.model
    except Exception:
        info["healthy"] = False
        info["model"] = "unknown"
    return {"status": "success", "data": info}


@router.put("/provider", tags=["AI Chat"])
async def set_llm_provider(
    provider: str,
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Switch the active LLM provider. Requires admin role."""
    from ai.provider import get_provider_info, set_provider

    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    if not set_provider(provider):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider: {provider}. Use: ollama, openai, anthropic",
        )

    # Reset the LLM service singleton so the new provider takes effect
    _ai_services["llm"] = None

    info = get_provider_info()
    try:
        llm, _, _ = get_ai_services()
        info["healthy"] = llm.check_health()
        info["model"] = llm.model
    except Exception:
        info["healthy"] = False
        info["model"] = "unknown"
    return {"status": "success", "message": f"Switched to {provider}", "data": info}


@router.put("/provider/key", tags=["AI Chat"])
async def set_llm_api_key(
    provider: str,
    api_key: str,
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Store an API key for an LLM provider. Requires admin role."""
    from ai.provider import get_provider, get_provider_info, set_api_key

    if current_user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    if provider not in ("openai", "anthropic"):
        raise HTTPException(
            status_code=400, detail="Provider must be openai or anthropic"
        )

    if not set_api_key(provider, api_key):
        raise HTTPException(status_code=500, detail="Failed to store API key")

    # If this is the active provider, reset the singleton
    if get_provider() == provider:
        _ai_services["llm"] = None

    info = get_provider_info()
    try:
        llm, _, _ = get_ai_services()
        info["healthy"] = llm.check_health()
        info["model"] = llm.model
    except Exception:
        info["healthy"] = False
        info["model"] = "unknown"
    return {
        "status": "success",
        "message": f"API key stored for {provider}",
        "data": info,
    }


# ==================== Analytics Endpoints ====================


@router.get("/anomalies", tags=["AI Insights"])
async def get_system_anomalies() -> Dict[str, Any]:
    """Detect system-wide anomalies using AI heuristics."""
    try:
        detector = AnomalyDetector()
        anomalies = []

        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # 1. Get active devices for mapping (only live, non-archived devices)
            all_devices_result = await session.execute(
                select(Device).where(Device.is_active.is_(True))
            )
            all_devices = all_devices_result.scalars().all()
            device_map = {d.device_id: d.name for d in all_devices}

            # 2. Fetch Active Alerts from Database (Persistent Context) FIRST
            # We want to prioritize persistent alerts which have IDs.
            alerts_result = await session.execute(
                select(Alert).where(Alert.status == "active")
            )
            active_alerts = alerts_result.scalars().all()

            # Track which devices have active alerts to avoid duplication
            alerted_devices = set()

            for alert in active_alerts:
                alerted_devices.add(alert.device_id)
                anomalies.append(
                    {
                        "id": alert.id,
                        "device_id": alert.device_id,
                        "device_name": device_map.get(
                            alert.device_id, "Unknown Device"
                        ),
                        "score": round(alert.ai_confidence or 0.8, 2),
                        "reasons": [alert.title, alert.description],
                        "severity": alert.severity,
                        "metrics": {
                            "source": "persistent_alert",
                            "category": alert.category,
                        },
                        "timestamp": (
                            alert.timestamp.isoformat()
                            if alert.timestamp
                            else datetime.utcnow().isoformat()
                        ),
                    }
                )

            # Filter for monitored devices to run active detection
            monitored_devices = [d for d in all_devices if d.is_monitored]
            devices_to_check = [
                d for d in monitored_devices if d.device_id not in alerted_devices
            ]
            device_ids_to_check = [d.id for d in devices_to_check]

            # Batch query DeviceMetrics and HealthCheck to eliminate N+1 queries
            latest_metrics_by_device: Dict[Any, Any] = {}
            health_checks_by_device: Dict[Any, Any] = {}

            if device_ids_to_check:
                from sqlalchemy.orm import aliased

                # 1. Batch fetch latest metrics
                metrics_subq = (
                    select(
                        DeviceMetrics,
                        func.row_number()
                        .over(
                            partition_by=DeviceMetrics.device_id,
                            order_by=DeviceMetrics.timestamp.desc(),
                        )
                        .label("rn"),
                    )
                    .where(DeviceMetrics.device_id.in_(device_ids_to_check))
                    .subquery()
                )
                metrics_alias = aliased(DeviceMetrics, metrics_subq)
                metrics_result = await session.execute(
                    select(metrics_alias).where(metrics_subq.c.rn == 1)
                )
                for metric in metrics_result.scalars().all():
                    latest_metrics_by_device[metric.device_id] = metric

                # 2. Batch fetch last 5 health checks
                health_subq = (
                    select(
                        HealthCheck,
                        func.row_number()
                        .over(
                            partition_by=HealthCheck.device_id,
                            order_by=HealthCheck.timestamp.desc(),
                        )
                        .label("rn"),
                    )
                    .where(HealthCheck.device_id.in_(device_ids_to_check))
                    .subquery()
                )
                health_alias = aliased(HealthCheck, health_subq)
                health_result = await session.execute(
                    select(health_alias).where(health_subq.c.rn <= 5)
                )
                for hc in health_result.scalars().all():
                    health_checks_by_device.setdefault(hc.device_id, []).append(hc)

                # Ensure order is sorted by timestamp descending
                for dev_id, checks in health_checks_by_device.items():
                    checks.sort(key=lambda x: x.timestamp, reverse=True)

            devices_status_updated = False
            for device in devices_to_check:
                device_metrics: Dict[str, Any] = {}

                # 3. Get latest metrics from pre-fetched dict
                latest_metric = latest_metrics_by_device.get(device.id)
                if latest_metric:
                    device_metrics.update(
                        {
                            "cpu_percent": latest_metric.cpu_percent,
                            "memory_percent": latest_metric.memory_percent,
                            "disk_percent": latest_metric.disk_percent,
                            "network_latency_ms": latest_metric.network_latency_ms,
                            "error_rate": latest_metric.error_rate,
                        }
                    )

                # 4. Get Flapping Count (last 1 hour)
                device_metrics["flapping_count"] = 0.0

                # 5. Get Consecutive Failures from pre-fetched dict
                checks = health_checks_by_device.get(device.id, [])
                consecutive_failures = 0
                for check in checks:
                    if not check.is_healthy:
                        consecutive_failures += 1
                    else:
                        break
                device_metrics["consecutive_failures"] = float(consecutive_failures)

                # Sync Device Status with Health & Generate Offline Alert
                try:
                    status_changed = False
                    if consecutive_failures >= 3:
                        if device.status != "offline":
                            device.status = "offline"  # type: ignore
                            status_changed = True

                    elif consecutive_failures == 0 and device.status == "offline":
                        # Recover from offline
                        device.status = "online"  # type: ignore
                        status_changed = True

                    if status_changed:
                        session.add(device)
                        devices_status_updated = True
                except Exception as e:
                    logger.error(f"Failed to sync device status: {e}")

                # 6. Run Detection
                score, reasons = detector.check_anomaly(device_metrics)

                if score > 0:
                    anomalies.append(
                        {
                            "device_id": device.device_id,
                            "device_name": device.name,
                            "score": round(score, 2),
                            "reasons": reasons,
                            "severity": "critical" if score >= 0.8 else "warning",
                            "metrics": device_metrics,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            if devices_status_updated:
                try:
                    await session.commit()
                except Exception as e:
                    logger.error(f"Failed to commit device status changes: {e}")

        # Sort by score descending
        anomalies.sort(key=lambda x: float(str(x["score"])), reverse=True)

        # Limit to top 5 anomalies
        anomalies = anomalies[:5]

        return {"count": len(anomalies), "anomalies": anomalies}

    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Anomaly detection failed")


@router.put("/alerts/{alert_id}/resolve", tags=["AI Insights"])
async def resolve_alert(
    alert_id: int,
    user_id: Optional[str] = Query(None, description="User resolving the alert"),
    notes: Optional[str] = Query(None, description="Resolution notes"),
) -> Dict[str, Any]:
    """Resolve a system alert manually."""
    try:
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalars().first()

            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")

            alert.status = "resolved"  # type: ignore
            alert.resolved_at = datetime.utcnow()  # type: ignore
            alert.resolved_by = user_id or "manual_resolution"  # type: ignore
            alert.resolution_notes = notes  # type: ignore

            await session.commit()

            return {
                "status": "success",
                "message": f"Alert {alert_id} resolved",
                "alert": {
                    "id": alert.id,
                    "status": alert.status,
                    "resolved_at": alert.resolved_at,
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


# Helper for Singleton services to avoid re-initialization overhead
_ai_services: Dict[str, Any] = {"llm": None, "knowledge": None, "memory": None}


def get_ai_services() -> Any:
    """Get singleton instances of AI services."""
    if _ai_services["llm"] is None:
        _ai_services["llm"] = LLMService()
    if _ai_services["knowledge"] is None:
        _ai_services["knowledge"] = SystemKnowledge(project_root)
    if _ai_services["memory"] is None:
        _ai_services["memory"] = DeviceMemory()
    return _ai_services["llm"], _ai_services["knowledge"], _ai_services["memory"]


# Process-wide gate that caps concurrent generations (see utils/ai_gate.py).
# Built lazily from the LLM config on first use so tests that patch
# get_ai_services still control it.
# Per-provider gates so Ollama (single slot) and cloud (several slots) do not
# share one semaphore sized for the weakest provider. Built lazily per provider.
_ai_gates: dict[str, AIConcurrencyGate] = {}


async def _publish_investigation_event(
    request: AIQueryRequest, event: str, data: Optional[dict] = None
) -> None:
    """Best-effort publish to the investigation event bus.

    No-op when the request is not tied to an investigation session/run, so
    existing callers (and tests) are unaffected.
    """
    if not request.session_id or not request.run_id:
        return
    try:
        from homepot.app.events.investigation_events import get_event_bus

        await get_event_bus().publish(
            session_id=request.session_id,
            run_id=request.run_id,
            event=event,
            data=data or {},
        )
    except Exception:
        pass


def get_ai_gate(llm: Any) -> AIConcurrencyGate:
    """Return the AI concurrency gate for the active provider."""
    llm_cfg = (getattr(llm, "config", {}) or {}).get("llm", {}) or {}
    provider = llm_cfg.get("provider") or "ollama"
    if provider not in _ai_gates:
        ext_cfg = (llm_cfg.get("external") or {}).get(provider, {}) or {}
        max_concurrent = ext_cfg.get("max_concurrent", llm_cfg.get("max_concurrent", 1))
        queue_timeout = ext_cfg.get(
            "queue_timeout_seconds", llm_cfg.get("queue_timeout_seconds")
        )
        _ai_gates[provider] = AIConcurrencyGate(
            max_concurrent=max_concurrent,
            queue_timeout_seconds=queue_timeout,
        )
    return _ai_gates[provider]


# Documentation retriever for the knowledge path (Tier C grounding). Built
# lazily and kept separate from `_ai_services` so the long-standing
# `get_ai_services()` 3-tuple contract (and the tests that patch it) is
# unchanged. Tests patch this to avoid indexing the real corpus.
_doc_retriever: Optional[DocRetriever] = None


def get_doc_retriever() -> DocRetriever:
    """Return the shared documentation retriever (Tier C grounding)."""
    global _doc_retriever
    if _doc_retriever is None:
        _doc_retriever = DocRetriever(docs_dir=os.path.join(project_root, "docs"))
    return _doc_retriever


def _ai_busy_http_exception(gate: AIConcurrencyGate) -> HTTPException:
    """Build the 503 returned when every AI slot is busy."""
    logger.warning(
        "AI request rejected: all %d slot(s) busy",
        gate.max_concurrent,
    )
    return HTTPException(
        status_code=503,
        detail=(
            "The assistant is busy handling other requests. "
            "Please try again in a few seconds."
        ),
        headers={"Retry-After": "5"},
    )


def _build_proposal_info(
    proposals: List[Any], plan: Optional[Any] = None
) -> Dict[str, Any]:
    """Serialize an agent run's proposals for the AI query response (Phase 1).

    Mirrors the persisted plan when available, or falls back to the in-memory
    proposals if persistence failed, so the technician still sees the intent.
    Nothing here executes an action.
    """
    if plan is not None:
        return {
            "plan_id": plan.plan_id,
            "persisted": True,
            "status": plan.status,
            "risk_tier": plan.risk_tier,
            "reversible": plan.reversible,
            "rationale": plan.rationale,
            "steps": [
                {
                    "seq": step.seq,
                    "action": step.action,
                    "target_device_id": step.target_device_id,
                    "params": step.params,
                    "status": step.status,
                }
                for step in plan.steps
            ],
        }

    return {
        "plan_id": None,
        "persisted": False,
        "status": "proposed",
        "risk_tier": max_risk_tier(proposals),
        "reversible": all_reversible(proposals),
        "rationale": "\n".join(p.rationale for p in proposals if p.rationale) or None,
        "steps": [
            {
                "seq": seq,
                "action": p.action,
                "target_device_id": p.target_device_id,
                "params": p.params,
                "status": "proposed",
            }
            for seq, p in enumerate(proposals)
        ],
    }


async def _generate_direct(
    llm: Any,
    query: str,
    context: str,
    system_prompt_text: str,
    gate: AIConcurrencyGate,
) -> str:
    """Run a single direct generation, through the concurrency gate.

    The Ollama client is synchronous, so it runs in a worker thread; the gate
    caps how many generations run at once and bounds the wait, so a burst gets
    an explicit "busy" (``AIBusyError`` → HTTP 503) instead of queueing
    invisibly inside Ollama (see utils/ai_gate.py and docs/ai-concurrency.md).
    """
    try:
        return await asyncio.to_thread(
            gate.run,
            llm.generate_response,
            prompt=query,
            context=context,
            system_prompt=system_prompt_text,
        )
    except AIBusyError:
        raise _ai_busy_http_exception(gate)


async def _client_disconnected(http_request: Optional[Request]) -> bool:
    """Report whether the caller has gone away (technician pressed Stop/Esc).

    Best-effort only. Starlette's ``is_disconnected`` does not block, so it is
    cheap enough to check before and after a generation, but it is *not* the
    mechanism this deployment relies on: ``AnalyticsMiddleware``
    (a ``BaseHTTPMiddleware``) re-wraps the ASGI ``receive`` callable and the
    check then never reports a disconnect, and Apache does not forward a browser
    abort to the backend either. Explicit cancellation via
    ``POST /ai/query/cancel`` is what actually works - see
    ``homepot.app.utils.ai_cancel`` and docs/ai-concurrency.md.
    """
    if http_request is None:
        # Called directly (tests) rather than through an ASGI request.
        return False
    try:
        return await http_request.is_disconnected()
    except Exception:  # pragma: no cover - never fail a query over this
        return False


async def _abandon_reason(
    http_request: Optional[Request],
    cancel_token: Optional[ai_cancel.AICancelToken],
) -> Optional[str]:
    """Why the caller abandoned this query, or ``None`` if they have not.

    The explicit token is checked first: it is the signal that works through the
    analytics middleware and Apache. The disconnect check is kept as a
    best-effort extra for callers that do not use the cancel endpoint.
    """
    if cancel_token is not None and cancel_token.cancelled:
        return "explicit_cancel"
    if await _client_disconnected(http_request):
        return "client_disconnect"
    return None


async def _audit_cancelled_query(
    request: AIQueryRequest,
    current_user: UserDict,
    *,
    mode: str,
    stage: str,
    source: str,
    routing_info: Optional[Dict[str, Any]] = None,
) -> None:
    """Record an abandoned query so cancellations are visible in the audit log."""
    logger.info(
        "AI query cancelled by client | mode=%s | stage=%s | source=%s | user=%s",
        mode,
        stage,
        source,
        current_user.get("email"),
    )
    metadata: Dict[str, Any] = {
        "query_length": len(request.query),
        "cancelled": True,
        "cancel_stage": stage,
        "cancel_source": source,
        "trust_mode": mode,
        "actionable": False,
    }
    if routing_info:
        metadata["routing_mode"] = routing_info.get("resolved")
        metadata["routing_reason"] = routing_info.get("reason")
    try:
        await get_audit_logger().log_event(
            event_type=AuditEventType.AI_QUERY,
            description=(
                f"AI query cancelled | mode={mode} | stage={stage} | "
                f"device={request.device_id or 'N/A'}"
            ),
            user_id=current_user.get("user_id"),
            event_metadata=metadata,
        )
    except Exception:
        logger.warning("Failed to persist cancelled AI audit event", exc_info=True)


def _cancelled_response(
    routing_info: Dict[str, Any], trust: Dict[str, Any]
) -> Dict[str, Any]:
    """Response body for a query the caller abandoned.

    The client has already disconnected, so nothing reads this; it exists so the
    early return is explicit and testable rather than a bare ``None``.
    """
    return {
        "response": "",
        "cancelled": True,
        "timestamp": datetime.utcnow().isoformat(),
        "trust": trust,
        "routing": routing_info,
    }


# Leading "[ANSWER]" tag the small model sometimes emits by mimicking the
# bracketed context blocks it is given ([RELEVANT DOCUMENTATION], etc.).
_LEADING_ANSWER_TAG_RE = re.compile(r"^(?:\s*\[ANSWER\]\s*:?\s*)+", re.IGNORECASE)
# A trailing "Source:"/"Sources:" attribution line. Sources are returned
# separately in the response's ``sources`` field, so these are redundant.
_SOURCE_LINE_RE = re.compile(r"^\s*Sources?:", re.IGNORECASE)


def _strip_answer_markup(text: str) -> str:
    """Remove internal format artifacts a small model sometimes emits.

    The AI context is built from bracketed blocks ([RELEVANT DOCUMENTATION],
    [RELEVANT MEMORIES], ...), and the model occasionally mimics that style by
    wrapping its reply in a leading ``[ANSWER]`` tag and/or appending a trailing
    ``Source: [RELEVANT DOCUMENTATION]`` line. Neither belongs in the
    user-facing answer -- the cited files are returned separately in the
    response's ``sources`` field. The system prompt also asks for plain text,
    but the model is stochastic, so strip defensively as well.
    """
    if not text:
        return text
    cleaned = _LEADING_ANSWER_TAG_RE.sub("", text, count=1)
    lines = cleaned.split("\n")
    # Drop trailing blank lines and redundant source-attribution lines, stopping
    # at the first line of real content.
    while lines:
        last = lines[-1].strip()
        if last == "" or _SOURCE_LINE_RE.match(last):
            lines.pop()
        else:
            break
    return "\n".join(lines).strip()


def _informational_trust() -> Dict[str, Any]:
    """Build the trust object for a knowledge query: informational, non-actionable.

    No device data was validated (none was needed), so there is no gate result,
    score or failed gate. The shape mirrors ``EnvelopeResult.to_dict()`` so the
    UI can render both uniformly.
    """
    return {
        "trust_mode": "informational",
        "trust_mode_label": "Informational",
        "trust_score": None,
        "actionable": False,
        "passed_gates": [],
        "failed_gate": None,
        "gates": [],
        "summary": (
            "Knowledge answer grounded in documentation; no device data was "
            "validated (none was needed)."
        ),
    }


def _format_retrieved_docs(chunks: List[Dict[str, Any]]) -> str:
    """Render retrieved doc chunks as a citable ``[RELEVANT DOCUMENTATION]`` block.

    Each chunk is labelled with its real repo-relative path (and section
    heading) so the model can cite sources that actually exist, and the API can
    return the same paths in the response's ``sources`` list.
    """
    if not chunks:
        return ""
    lines = ["[RELEVANT DOCUMENTATION]"]
    for chunk in chunks:
        source = chunk.get("source") or "docs/unknown.md"
        heading = chunk.get("heading") or ""
        label = f"{source} — {heading}" if heading else source
        lines.append(f"--- {label} ---")
        lines.append(str(chunk.get("content", "")).strip())
    return "\n".join(lines)


async def _answer_knowledge(
    *,
    request: AIQueryRequest,
    current_user: UserDict,
    llm: Any,
    knowledge: Any,
    short_term_context: str,
    memory_scope: MemoryScope,
    routing_info: Dict[str, Any],
    http_request: Optional[Request] = None,
    cancel_token: Optional[ai_cancel.AICancelToken] = None,
) -> Dict[str, Any]:
    """Answer a knowledge-mode query from documentation only.

    Skips the fleet/device DB scans, the validation gates (A-E) and the AI
    insights entirely (see docs/ai-query-routing.md section 7): a how-to answer
    does not need live device state. The response carries an informational trust
    object and can never produce a proposal.
    """
    parts: List[str] = [
        "[MODE]\nknowledge (documentation-only; no live device data)",
    ]
    if request.context:
        parts.append(
            "[USER CONTEXT]\n" + _sanitize_ai_input(request.context, "context")
        )
    if request.role:
        parts.append("[REQUESTER ROLE]\n" + _sanitize_ai_input(request.role, "role"))

    # Tier C grounding: retrieve the most relevant documentation chunks for this
    # query and inject them with their real file paths so the model cites actual
    # sources instead of inventing them (see docs/ai-query-routing.md 8.1).
    sources: List[str] = []
    doc_block = ""
    try:
        retriever = get_doc_retriever()
        chunks = retriever.retrieve(request.query)
        if chunks:
            doc_block = _format_retrieved_docs(chunks)
            sources = DocRetriever.unique_sources(chunks)
    except Exception:
        logger.warning("Documentation retrieval failed", exc_info=True)

    if doc_block:
        parts.append(doc_block)
    else:
        # No retrieval hit (or retriever unavailable): fall back to the fixed
        # doc excerpts so the answer is not left with no context at all.
        fallback = knowledge.get_documentation_context()
        if fallback:
            parts.append(fallback)

    # Long-term memory is deliberately NOT included here: a knowledge answer is
    # grounded in documentation only, never in the model's own past output
    # (see docs/ai-memory.md).
    if short_term_context:
        parts.append(short_term_context)
    knowledge_context = "\n".join(parts)

    gate = get_ai_gate(llm)

    # Cancel check (1/2): if the technician pressed Stop while the documentation
    # was being retrieved, skip the generation instead of burning CPU on an
    # answer nobody will read.
    abandon_reason = await _abandon_reason(http_request, cancel_token)
    if abandon_reason:
        await _publish_investigation_event(
            request,
            "cancelled",
            {"reason": abandon_reason, "stage": "before_generation"},
        )
        await _audit_cancelled_query(
            request,
            current_user,
            mode=MODE_KNOWLEDGE,
            stage="before_generation",
            source=abandon_reason,
            routing_info=routing_info,
        )
        return _cancelled_response(routing_info, _informational_trust())

    # Tier B (Tier C + on-demand repo tools): when read-only repository access
    # is enabled, let the model consult documentation and code via a bounded,
    # read-only tool loop. The proposal tool is never offered here, so the
    # knowledge path still cannot emit a plan, and the trust object stays
    # informational. Files it reads are surfaced as extra sources.
    if code_access_enabled():
        access = get_repo_access()
        system_prompt_text = knowledge.get_knowledge_prompt(include_repo_tools=True)
        repo_sources: List[str] = []
        sink_token = set_repo_source_sink(repo_sources)
        try:
            try:
                agent_result = await run_agent(
                    query=request.query,
                    context=knowledge_context,
                    llm=llm,
                    tools=list(REPO_TOOL_FUNCTIONS),
                    system_prompt=system_prompt_text,
                    gate=gate,
                    memory_scope=memory_scope,
                    max_iterations=access.max_tool_calls,
                    max_tool_bytes=access.max_tool_bytes,
                )
            except AIBusyError:
                raise _ai_busy_http_exception(gate)
        finally:
            reset_repo_source_sink(sink_token)

        if agent_result.response and not agent_result.fell_back_to_direct:
            response = agent_result.response
        else:
            # Loop produced no usable answer: answer directly with the context.
            logger.warning(
                "Knowledge tool loop produced no answer; falling back to direct"
            )
            response = await _generate_direct(
                llm, request.query, knowledge_context, system_prompt_text, gate
            )
        for path in repo_sources:
            if path not in sources:
                sources.append(path)
    else:
        system_prompt_text = knowledge.get_knowledge_prompt()
        response = await _generate_direct(
            llm,
            request.query,
            knowledge_context,
            system_prompt_text,
            gate,
        )

    # Strip internal format artifacts (leading [ANSWER] tag / trailing
    # "Source:" line) so a stochastic emission never leaks markup to the user.
    # Covers both the Tier B agent branch and the direct-generation branch.
    response = _strip_answer_markup(response)

    # Cancel check (2/2): the answer was abandoned, so do not record it as a
    # delivered query. Knowledge answers are never written to memory anyway (see
    # docs/ai-memory.md), so this only suppresses the success audit entry.
    abandon_reason = await _abandon_reason(http_request, cancel_token)
    if abandon_reason:
        await _publish_investigation_event(
            request,
            "cancelled",
            {"reason": abandon_reason, "stage": "before_generation"},
        )
        await _audit_cancelled_query(
            request,
            current_user,
            mode=MODE_KNOWLEDGE,
            stage="after_generation",
            source=abandon_reason,
            routing_info=routing_info,
        )
        return _cancelled_response(routing_info, _informational_trust())

    logger.info(
        "AI query done | mode=knowledge | reason=%s",
        routing_info.get("reason"),
    )

    # Knowledge answers are intentionally NOT written to long-term memory. They
    # are informational (never gate-validated) and derived from docs, so
    # persisting them only stores the model's own output; recalling it later
    # would let a wrong answer reinforce itself with no ground truth to correct
    # it. See docs/ai-memory.md.

    try:
        await get_audit_logger().log_event(
            event_type=AuditEventType.AI_QUERY,
            description=(
                f"AI query | mode=knowledge | " f"device={request.device_id or 'N/A'}"
            ),
            user_id=current_user.get("user_id"),
            event_metadata={
                "query_length": len(request.query),
                "trust_mode": "informational",
                "actionable": False,
                "routing_mode": MODE_KNOWLEDGE,
                "routing_reason": routing_info.get("reason"),
            },
        )
    except Exception:
        logger.warning("Failed to persist AI audit event", exc_info=True)

    logger.info(
        "AI query done | device_id=%s | mode=knowledge | actionable=False",
        request.device_id or "N/A",
    )

    return {
        "response": response,
        "timestamp": datetime.utcnow().isoformat(),
        "trust": _informational_trust(),
        "routing": routing_info,
        "sources": sources,
    }


@router.post("/query/cancel", tags=["AI Chat"])
async def cancel_query(
    request: AIQueryCancelRequest,
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Abandon an in-flight AI query (technician pressed Stop/Esc).

    The widget posts back the ``query_id`` it sent with the question. The
    matching query stops at its next cancel check: no memory write, no proposal,
    and an audit entry tagged as cancelled. This request is deliberately tiny
    and does not touch the generation gate, so it is answered while a generation
    is still running.

    ``cancelled: false`` means there was nothing to cancel: the query had
    already finished, or the id is unknown (which includes another user's query,
    so the endpoint cannot be used to probe for live queries).
    """
    matched = ai_cancel.cancel_query(request.query_id, current_user.get("user_id"))
    logger.info(
        "AI query cancel requested | query_id=%s | matched=%s | user=%s",
        request.query_id,
        matched,
        current_user.get("email"),
    )
    return {"cancelled": matched}


@router.post("/query", tags=["AI Chat"])
async def query_ai(
    request: AIQueryRequest,
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
    # Injected from the ASGI scope by FastAPI. It defaults to None only so
    # handlers can still be called directly in tests; see _client_disconnected.
    http_request: Request = None,  # type: ignore[assignment]
) -> Dict[str, Any]:
    """Query the AI assistant.

    Registers the query's cancellation token for the duration of the request, so
    a technician pressing Stop/Esc can abandon it explicitly. See
    ``homepot.app.utils.ai_cancel`` and docs/ai-concurrency.md.
    """
    cancel_token = (
        ai_cancel.register_query(request.query_id, current_user.get("user_id"))
        if request.query_id
        else None
    )
    try:
        return await _query_ai_impl(
            request, current_user, db, http_request, cancel_token
        )
    finally:
        if cancel_token is not None:
            ai_cancel.release_query(cancel_token)


async def _query_ai_impl(
    request: AIQueryRequest,
    current_user: UserDict,
    db: SASession,
    http_request: Optional[Request] = None,
    cancel_token: Optional[ai_cancel.AICancelToken] = None,
) -> Dict[str, Any]:
    """Query the AI assistant."""
    logger.info(
        "AI query | device_id=%s | query_len=%d | user=%s",
        request.device_id or "N/A",
        len(request.query),
        current_user.get("email"),
    )
    try:
        # Use singletons for heavy services
        llm, knowledge, memory = get_ai_services()
        # ContextBuilder is lightweight
        context_builder = ContextBuilder()

        await _publish_investigation_event(
            request, "run_started", {"query": request.query}
        )

        # 1. Build Short-Term Context (Conversation History)
        short_term_context = ""
        if request.history:
            short_term_context = "\n[CONVERSATION HISTORY]\n"
            short_term_context += "\n".join(
                [
                    f"{_sanitize_ai_input(msg.role, 'history-role')}: "
                    f"{_sanitize_ai_input(msg.content, 'history')}"
                    for msg in request.history[-5:]
                ]
            )

        # 2. Determine the caller's long-term memory scope (RBAC-aware) and
        # recall scoped memories. Admins recall across all memories; everyone
        # else is limited to their sites, and to a single device when the query
        # is device-focused.
        is_admin = current_user.get("role") == "Admin"
        site_scope: Optional[list] = None
        if not is_admin:
            try:
                db_user = (
                    db.query(User)
                    .filter(User.email == current_user.get("email"))
                    .first()
                )
                if db_user is not None:
                    accessible = get_accessible_site_ids(db_user, db)
                    site_scope = list(accessible) if accessible is not None else None
            except Exception as e:
                logger.warning("Failed to resolve memory scope: %s", e)
        memory_scope = MemoryScope(
            user_id=current_user.get("user_id"),
            site_ids=site_scope,
            device_id=request.device_id,
            is_admin=is_admin,
        )

        # 2b. Resolve the query's intent BEFORE building long-term memory, so a
        # knowledge (how-to/definition) answer can stay documentation-only. The
        # long-term store holds the model's own past answers; feeding them back
        # on a path with no live ground truth lets it repeat stale or wrong output
        # instead of consulting the docs (see docs/ai-memory.md).
        routing = resolve_query_mode(
            request.query,
            requested=request.mode,
            device_id=request.device_id,
            history=request.history,
            enabled=routing_enabled(),
        )
        routing_info = {
            "requested": routing.requested,
            "resolved": routing.resolved,
            "reason": routing.reason,
        }
        logger.info(
            "AI query routing | requested=%s | resolved=%s | reason=%s",
            routing.requested,
            routing.resolved,
            routing.reason,
        )

        # 2c. Build Long-Term Context (Vector Memory). Only the device-backed
        # diagnostic path recalls memory; knowledge answers skip it entirely so
        # they can never echo the model's own past output.
        long_term_context = ""
        if routing.resolved != MODE_KNOWLEDGE:
            try:
                # Get Memory Stats (Self-Awareness)
                mem_stats = memory.get_memory_stats()
                long_term_context = (
                    f"\n[MEMORY SYSTEM STATUS]\n"
                    f"Total Memories Stored: {mem_stats['total_memories']}\n"
                )

                # Get Similar Memories (scope-filtered + relevance-thresholded)
                # Per-provider recall depth (see ai/provider.py). Falls back to
                # the shared `memory.n_results` when no override is set.
                from ai.provider import get_llm_setting

                _n_results = get_llm_setting("memory_n_results", None)
                if _n_results is None:
                    _n_results = get_llm_setting("n_results", 3)
                similar_memories = memory.query_similar(
                    request.query, scope=memory_scope, n_results=int(_n_results)
                )
                if similar_memories:
                    long_term_context += "\n[RELEVANT MEMORIES]\n"
                    long_term_context += "\n".join(
                        [f"- {m['content']}" for m in similar_memories]
                    )
            except Exception as e:
                logger.warning(f"Failed to query vector memory: {e}")

        if routing.resolved == MODE_KNOWLEDGE:
            return await _answer_knowledge(
                request=request,
                current_user=current_user,
                llm=llm,
                knowledge=knowledge,
                short_term_context=short_term_context,
                memory_scope=memory_scope,
                routing_info=routing_info,
                http_request=http_request,
                cancel_token=cancel_token,
            )

        # 3. Build Real-Time System Context
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            # Get Sites with active Devices only (archived/unpaired/retired
            # devices must not be visible to the AI).
            result = await session.execute(
                select(Site).where(Site.is_active.is_(True)).limit(10)
            )
            sites = result.scalars().all()
            site_ids = [s.id for s in sites]
            devices_by_site: dict = {}
            all_active_devices: list = []
            if site_ids:
                dev_result = await session.execute(
                    select(Device).where(
                        Device.site_id.in_(site_ids),
                        Device.is_active.is_(True),
                    )
                )
                for dev in dev_result.scalars().all():
                    devices_by_site.setdefault(dev.site_id, []).append(dev)
                    all_active_devices.append(dev)

            # Fleet summary: connectivity (heartbeat-based), health and mode.
            online_count = sum(1 for d in all_active_devices if _device_is_online(d))
            healthy_count = sum(
                1 for d in all_active_devices if d.health_state == "healthy"
            )
            mode_counts: dict = {"simulated": 0, "emulated": 0, "real": 0}
            for d in all_active_devices:
                mode_counts[_device_mode(d)] += 1

            site_context = "[CURRENT SYSTEM STATUS]\n"
            site_context += f"Total Sites: {len(sites)}\n"
            site_context += f"Total Active Devices: {len(all_active_devices)}\n"
            site_context += f"Online Devices: {online_count}\n"
            site_context += f"Healthy Devices: {healthy_count}\n"
            site_context += (
                f"Devices by Mode: {mode_counts['simulated']} simulated, "
                f"{mode_counts['emulated']} emulated, {mode_counts['real']} real\n"
            )
            for site in sites:
                site_context += f"- Site: {site.name} (ID: {site.site_id}), Location: {site.location}\n"
                site_devices = devices_by_site.get(site.id, [])[:10]
                if site_devices:
                    site_context += "  Devices:\n"
                    for d in site_devices:
                        site_context += (
                            f"    * Name: {d.name}\n"
                            f"      ID: {d.device_id}\n"
                            f"      Type: {d.device_type}\n"
                            f"      Status: "
                            f"{'online' if _device_is_online(d) else 'offline'}\n"
                            f"      Health: {d.health_state or 'unknown'}\n"
                            f"      Mode: {_device_mode(d)}\n"
                            f"      IP: {d.ip_address or 'N/A'}\n"
                        )

            # Get Push Notification Stats via ContextBuilder
            push_context = await context_builder.get_push_context(session=session)
            site_context += f"\n{push_context}\n"

            # Get Active Alerts for AI Context (only for active devices)
            # Keep inline: active_alerts is reused below for known_alert_ids.
            active_device_ids = select(Device.device_id).where(
                Device.is_active.is_(True)
            )
            alerts_result = await session.execute(
                select(Alert)
                .where(
                    Alert.status == "active",
                    Alert.device_id.in_(active_device_ids),
                )
                .limit(10)
            )
            active_alerts = alerts_result.scalars().all()

            site_context += "\n[ACTIVE SYSTEM ALERTS]\n"
            if active_alerts:
                for alert in active_alerts:
                    site_context += (
                        f"- **ALERT RECORD**:\n"
                        f"  ID: #{alert.id}\n"
                        f"  Severity: {alert.severity}\n"
                        f"  Device: {alert.device_id}\n"
                        f"  Title: {alert.title}\n"
                        f"  Description: {alert.description}\n\n"
                    )
            else:
                site_context += "No active alerts.\n"

            # Get Job Context if relevant
            job_context = await context_builder.get_job_context(session=session)

            # 4. Assemble Final Context
            full_context = f"{site_context}\n{job_context}\n{long_term_context}\n{short_term_context}"

            if request.context:
                sanitized_context = _sanitize_ai_input(request.context, "context")
                full_context += f"\n[USER CONTEXT]\n{sanitized_context}"

            if request.role:
                sanitized_role = _sanitize_ai_input(request.role, "role")
                full_context += f"\n[REQUESTER ROLE]\n{sanitized_role}"

            if request.device_id:
                full_context += f"\n[FOCUS DEVICE]\nID: {request.device_id}"

            # NOTE: the static [SYSTEM ROLES DEFINITIONS] block now lives in the
            # cached system prompt (SystemKnowledge.get_system_prompt) so it is
            # not re-evaluated by the CPU on every request.

            # Resolve device integer ID early so enriched context and gates
            # can both use it.
            device_int_id = None
            if request.device_id:
                device_int_id = await DeviceResolver(session).resolve(request.device_id)

            # Enriched diagnostic context: gather all ContextBuilder sources
            # in parallel so total latency = slowest single query, not the sum.
            # The fleet summary (above) stays inline because it includes the
            # site/device listing that ContextBuilder doesn't replicate.
            enriched = ""
            try:
                enriched = await ContextBuilder.build_enriched_context(
                    device_id=request.device_id,
                    device_int_id=device_int_id,
                    user_id=(
                        str(current_user.get("user_id"))
                        if current_user.get("user_id") is not None
                        else None
                    ),
                    session=session,
                )
                if enriched:
                    # Cap the enriched context to a configurable budget so
                    # small-window models (Ollama, num_ctx=8192) are not
                    # overwhelmed. Cloud models can raise `context_budget`
                    # in ai/config.yaml to receive the full detail.
                    _llm_cfg = getattr(llm, "config", None)
                    if isinstance(_llm_cfg, dict):
                        _llm = _llm_cfg.get("llm") or {}
                        _provider = _llm.get("provider") or "ollama"
                        _ext = (_llm.get("external") or {}).get(_provider, {}) or {}
                        if "context_budget" in _ext:
                            budget = int(_ext["context_budget"])
                        else:
                            budget = int(_llm.get("context_budget", 2000))
                    else:
                        budget = 2000
                    if budget > 0 and len(enriched) > budget:
                        enriched = (
                            enriched[:budget].rsplit("\n", 1)[0]
                            + "\n… (trimmed to context budget)"
                        )
                    full_context += f"\n{enriched}"
            except Exception as e:
                logger.warning("Failed to build enriched context: %s", e)

            await _publish_investigation_event(
                request, "context_ready", {"context_len": len(full_context)}
            )

            # 5. Validation-First Gates: Gate A -> B -> C (see ai/gates)
            # AI inference is a downstream consumer of the operational data
            # (paper Sec. 4). Gates no longer block inference outright --
            # instead they determine how much trust is attached to the
            # resulting recommendation (see [VALIDATION TRUST STATUS] below
            # and the `trust` field always returned to the caller), so a
            # technician can see, per-recommendation, how much confidence to
            # place in it. Gates run BEFORE the AI Insights below because
            # Gate B's result gates whether those insights are computed at
            # all (see next step).
            known_alert_ids = [alert.id for alert in active_alerts]
            gate_context = GateContext(
                session=session,
                device_id=request.device_id,
                device_int_id=device_int_id,
                assembled_context=full_context,
                known_alert_ids=known_alert_ids,
            )
            # ------------------------------------------------------------------
            # ZERO-FLEET REFUSAL (Mode 1 boundary, live). When the fleet is
            # empty, the validation gates have NO fleet data to validate:
            # Gate A (schema/DB) and Gate B (data integrity) are
            # infrastructure checks that PASS on an empty DB, so running the
            # envelope here would produce a confident-looking ~0.24 'trust'
            # with zero real devices behind it -- a fabricated grounding
            # signal. So on zero_fleet we create NO trust at all (no gates
            # activated, status-only, trust_score 0.0, not actionable) and
            # inject a refusal mandate into the context so the LLM states
            # plainly that there are 0 devices and that it will NOT provide a
            # suggestion -- while still reporting non-fleet system facts
            # (sites, alerts, push stats, memory) as observable status, never
            # as a recommendation.
            zero_fleet = not all_active_devices
            if zero_fleet:
                trust = EnvelopeResult(
                    gate_results=[],
                    trust_mode=MODE_STATUS_ONLY,
                    trust_score=0.0,
                    failed_gate_id=None,
                )
            else:
                envelope = build_envelope_from_config()
                trust = await envelope.run(gate_context)

            await _publish_investigation_event(
                request,
                "gates_complete",
                {
                    "trust_mode": getattr(trust, "trust_mode", None),
                    "trust_score": getattr(trust, "trust_score", None),
                    "failed_gate": getattr(trust, "failed_gate", None),
                    "actionable": getattr(trust, "actionable", None),
                },
            )

            # 6. AI Insights: surface the SAME anomaly/failure signals a
            # technician would see elsewhere in the product, so the LLM's
            # answer is grounded in all information available, not just raw
            # metrics/alerts. Gated on Gate B (data integrity) having PASSED:
            # anomaly detection and failure prediction are themselves derived
            # from the same telemetry Gate B validates, so computing and
            # presenting them when that data has already failed integrity
            # checks would hand the LLM a confident-looking conclusion
            # ("Risk Level: CRITICAL") built on data we've just determined is
            # NOT trustworthy -- undermining the trust signal below. This
            # also avoids the extra anomaly-scan/failure-prediction DB
            # queries on every chat turn once the data is already known to
            # be stale/incomplete/invalid. Best-effort: a failure here must
            # not break chat.
            data_integrity_passed = any(
                g.gate_id == "B" and g.status == GateStatus.PASS
                for g in trust.gate_results
            )
            if data_integrity_passed:
                full_context += "\n[AI INSIGHTS: SYSTEM ANOMALIES]\n"
                try:
                    anomalies_payload = await get_system_anomalies()
                    detected = anomalies_payload.get("anomalies") or []
                    if detected:
                        for a in detected:
                            full_context += (
                                f"- Device: {a.get('device_name')} ({a.get('device_id')}), "
                                f"Severity: {a.get('severity')}, Score: {a.get('score')}, "
                                f"Reasons: {', '.join(a.get('reasons') or [])}\n"
                            )
                    else:
                        full_context += "No active anomalies detected.\n"
                except Exception as e:
                    logger.warning(
                        f"Failed to gather anomaly insights for AI context: {e}"
                    )
                    full_context += "Anomaly insights unavailable.\n"

                if request.device_id:
                    try:
                        prediction = await FailurePredictor().predict_device_failure(
                            request.device_id
                        )
                        risk_factor_names = [
                            f.get("name", "Unknown")
                            for f in prediction.get("risk_factors", [])
                        ]
                        full_context += (
                            "\n[AI INSIGHTS: FAILURE PREDICTION]\n"
                            f"Device: {request.device_id}\n"
                            f"Risk Level: {prediction.get('risk_level', 'UNKNOWN')}\n"
                            f"Failure Probability: {prediction.get('failure_probability', 0.0)}\n"
                            f"Risk Factors: {', '.join(risk_factor_names)}\n"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to gather failure prediction for AI context: {e}"
                        )
                        full_context += (
                            "\n[AI INSIGHTS: FAILURE PREDICTION]\nUnavailable.\n"
                        )
            else:
                full_context += (
                    "\n[AI INSIGHTS]\n"
                    "Skipped: Gate B (data integrity) did not pass; analytics "
                    "withheld.\n"
                )

            # 7. Re-validate Gate C against the FINAL context (base context +
            # AI Insights appended above). Appending the insights blocks can
            # grow the prompt past Gate C's bounded-context threshold, or in
            # principle disturb its stable-block/ID-rule checks -- Gate C's
            # whole purpose is "is the context about to be sent to the LLM
            # fit for ingestion" (paper Sec. 4.3), so that question has to be
            # re-asked against what's *actually* being sent, not just the
            # pre-insight draft. We re-run the SAME Gate C instance used
            # above (same overrides/thresholds) rather than introducing a
            # new gate, since this is the same concern (context readiness),
            # just re-checked at the point the context is complete. Only
            # meaningful when the first pass was fully actionable -- if it
            # already failed, trust is already capped and the insights
            # section above was replaced with a short skip note that can't
            # newly violate Gate C.
            if trust.is_actionable:
                gate_c = next(g for g in envelope.gates if g.gate_id == "C")
                post_insight_result = await gate_c.run(
                    GateContext(
                        session=session,
                        device_id=request.device_id,
                        device_int_id=device_int_id,
                        assembled_context=full_context,
                        known_alert_ids=known_alert_ids,
                    )
                )
                trust.gate_results.append(post_insight_result)
                if post_insight_result.status != GateStatus.PASS:
                    trust = EnvelopeResult(
                        gate_results=trust.gate_results,
                        trust_mode=MODE_CAUTIONARY,
                        trust_score=min(
                            trust.trust_score, MODE_CAUTIONARY.trust_ceiling
                        ),
                        failed_gate_id="C (post-insight)",
                    )

        # Surface the trust envelope directly in the context so the LLM can
        # see -- and is instructed (below) to reflect in its answer -- exactly
        # how much confidence to attach to what follows. The LLM always runs;
        # gates condition its instructions rather than gating inference itself.
        full_context += (
            "\n[VALIDATION TRUST STATUS]\n"
            f"{trust.label()}\n"
            f"Trust score: {trust.trust_score:.2f} (0.0 = no trust, 1.0 = fully grounded)\n"
            f"Actionable: {'yes' if trust.is_actionable else 'no'}\n"
        )
        if zero_fleet:
            full_context += (
                "\n[REFUSAL MANDATE]\n"
                "Fleet EMPTY (0 devices). Answer in at most 3 short sentences: "
                "state that no devices are connected and no validation gates ran; "
                "do NOT dump per-statistic zeros or give any suggestion or "
                "recommendation. Non-fleet facts (sites, alerts, push, memory) only "
                "as brief status.\n"
            )
        if not trust.is_actionable:
            full_context += (
                f"Failed gate: {trust.failed_gate_id} "
                f"({trust.trust_mode.description})\n"
            )
            # Surface a SHORT, plain-English reason so the LLM can be
            # specific ("telemetry is 340s stale") instead of just naming
            # the failed gate -- without dumping the full per-check
            # evidence tree (row counts, thresholds, timestamps) into the
            # prompt. That full detail is reserved for the dashboard's
            # expandable trust banner; the LLM only gets a 1-2 line digest
            # so its answer -- and a technician reading it -- isn't
            # overwhelmed with raw validation data.
            failing_gate = trust.gate_results[-1] if trust.gate_results else None
            failing_reasons = [
                c.message
                for c in (failing_gate.checks if failing_gate else [])
                if not c.passed and c.message
            ]
            if failing_reasons:
                full_context += f"Reason: {' '.join(failing_reasons[:2])}\n"

        # 5b. Per-device trust digest (surfaces merged #464's Gate B digest so
        # statements can be grounded PER DEVICE rather than fleet-wide-only).
        # The fleet envelope's trust mode/score/actionability and the #463
        # zero-fleet refusal are decided ABOVE and are untouched here -- this
        # block only walks the SAME per-device EvidenceRefs Gate B already
        # emitted (info-only; device_id keyed) so the LLM grounds statements
        # on the SPECIFIC device the evidence covers:
        #   * a digest PASS for device H  => H-only statements allowed;
        #   * a digest FAIL for device X  => no statements from/about X, and
        #     no cross-device statement involving X is ever permitted;
        #   * fleet semantics, trust mode, envelope actionability are NEVER
        #     changed by this render (it is purely informational evidence).
        digest_rows = [
            (ev.device_id, c.check_id, c.passed)
            for gate_result in (trust.gate_results or [])
            for c in (gate_result.checks or [])
            for ev in (c.evidence or [])
            if getattr(ev, "device_id", None)
        ]
        if digest_rows:
            digest_lines = [
                f"- device {device_id}: {check_id} " f"{'PASS' if passed else 'FAIL'}"
                for device_id, check_id, passed in digest_rows
            ]
            full_context += (
                "\n[PER-DEVICE TRUST DIGEST]\n"
                + "\n".join(digest_lines)
                + "\nStatements may be grounded ONLY on the device whose "
                "digest passes; a FAILed digest forbids conclusions from or "
                "about that device and any cross-device statement involving "
                "it. Never borrow one device's grounding for another.\n"
                "[END PER-DEVICE TRUST DIGEST]\n"
            )

        # Protect the fleet summary against context truncation in small-window
        # models (e.g. Ollama, num_ctx=8192). The full [CURRENT SYSTEM
        # STATUS] block sits at the top of the context and can be dropped when
        # the assembled prompt exceeds the window; restate the headline counts
        # here, at the very end (adjacent to the question), so at least one
        # copy survives regardless of truncation direction. See
        # docs/ai-llm-providers.md for the provider-specific context limits.
        full_context += (
            "\n[CURRENT SYSTEM STATUS — SUMMARY (report these exact numbers)]\n"
            f"Total Sites: {len(sites)}\n"
            f"Total Active Devices: {len(all_active_devices)}\n"
            f"Online Devices: {online_count}\n"
            f"Healthy Devices: {healthy_count}\n"
            "Do not contradict these counts. If they say 3 sites and 3 devices, "
            "report 3 sites and 3 devices.\n"
        )

        # Per-request size diagnostic. Every token in this dynamic context is
        # re-evaluated by the CPU on each query (~22 tok/s), unlike the cached
        # system prompt, so this breakdown is what guides trimming.
        logger.info(
            "AI context parts | full=%d site=%d job=%d memory=%d short=%d "
            "enriched=%d other=%d",
            len(full_context),
            len(site_context),
            len(job_context),
            len(long_term_context),
            len(short_term_context),
            len(enriched),
            len(full_context)
            - len(site_context)
            - len(job_context)
            - len(long_term_context)
            - len(short_term_context)
            - len(enriched),
        )

        # Static system prompt. Built by SystemKnowledge so the startup warm-up
        # can prime Ollama's KV cache with the exact same prefix (see main.py).
        system_prompt_text = knowledge.get_system_prompt()

        # Cancel check (1/2): the technician may have pressed Stop/Esc while the
        # context was being assembled. Nothing has been generated yet, so skip
        # the (expensive) inference entirely.
        abandon_reason = await _abandon_reason(http_request, cancel_token)
        if abandon_reason:
            await _audit_cancelled_query(
                request,
                current_user,
                mode=trust.trust_mode.label,
                stage="before_generation",
                source=abandon_reason,
                routing_info=routing_info,
            )
            return _cancelled_response(routing_info, trust.to_dict())

        if request.agentic:
            # Agentic mode: multi-step tool-calling investigation. Each LLM
            # call is routed through the same concurrency gate as a direct
            # query, and the caller's memory scope is passed in so memory-reading
            # tools only recall what this user may see.
            gate = get_ai_gate(llm)
            await _publish_investigation_event(
                request, "llm_started", {"mode": "agentic"}
            )
            try:
                agent_result = await run_agent(
                    query=request.query,
                    context=full_context,
                    llm=llm,
                    device_id=request.device_id,
                    gate=gate,
                    memory_scope=memory_scope,
                    include_repo_tools=code_access_enabled(),
                )
            except AIBusyError:
                raise _ai_busy_http_exception(gate)

            if agent_result.fell_back_to_direct:
                # Documented graceful degradation: the loop could not produce an
                # answer (LLM/tool failure or budget exhausted with no output),
                # so answer directly with the context we already assembled.
                logger.warning(
                    "Agent loop produced no answer; falling back to direct generation"
                )
                response = await _generate_direct(
                    llm, request.query, full_context, system_prompt_text, gate
                )
            else:
                response = agent_result.response

            agentic_info = {
                "iterations": agent_result.iterations,
                "tools_called": [
                    {"tool": tc.tool_name, "iteration": tc.iteration}
                    for tc in agent_result.tools_called
                ],
                "total_duration_ms": agent_result.total_duration_ms,
                "fell_back_to_direct": agent_result.fell_back_to_direct,
            }
        else:
            # Direct mode: single LLM call (existing behavior).
            await _publish_investigation_event(
                request, "llm_started", {"mode": "direct"}
            )
            response = await _generate_direct(
                llm,
                request.query,
                full_context,
                system_prompt_text,
                get_ai_gate(llm),
            )
            agentic_info = None

        # Strip internal format artifacts (leading [ANSWER] tag / trailing
        # "Source:" line), mirroring the knowledge path, so markup never
        # reaches the user.
        response = _strip_answer_markup(response)

        await _publish_investigation_event(
            request, "llm_complete", {"response_len": len(response or "")}
        )

        # Cancel check (2/2): the answer was abandoned, so it must not become
        # remembered truth. Skipping this leaves no memory record, and no
        # proposal, for a query the technician rejected. The generation itself
        # cannot be interrupted (worker thread), so this is the point where an
        # "esc" stops having side effects.
        abandon_reason = await _abandon_reason(http_request, cancel_token)
        if abandon_reason:
            await _publish_investigation_event(
                request, "cancelled", {"reason": abandon_reason}
            )
            await _audit_cancelled_query(
                request,
                current_user,
                mode=trust.trust_mode.label,
                stage="after_generation",
                source=abandon_reason,
                routing_info=routing_info,
            )
            return _cancelled_response(routing_info, trust.to_dict())

        # 5a. Capture AI-proposed actions (Phase 1: proposal-only / dry-run).
        # A proposal is only surfaced when the trust envelope deems the answer
        # actionable AND the agent completed normally (not a direct fallback):
        # we never present an action as approvable off the back of a degraded
        # run. Nothing is executed here -- the plan is recorded with status
        # "proposed" for a technician to review (Phase 2). See
        # docs/ai-delegation-plan.md.
        proposal_info = None
        if agentic_info is not None and agent_result.proposals:
            if trust.is_actionable and not agent_result.fell_back_to_direct:
                plan = None
                try:
                    repo = AIActionRepository(db)
                    plan = repo.create_plan(
                        agent_result.proposals,
                        risk_tier=max_risk_tier(agent_result.proposals),
                        reversible=all_reversible(agent_result.proposals),
                        trust=trust,
                        created_by=current_user.get("email"),
                        # The trust envelope already vetted the answer, so the
                        # plan is promoted straight to awaiting a technician
                        # (Phase 2). See docs/ai-delegation-plan.md section 6.
                        status="pending_approval",
                    )
                except Exception:
                    logger.warning(
                        "Failed to persist AI action proposal", exc_info=True
                    )
                proposal_info = _build_proposal_info(agent_result.proposals, plan)
                if plan is not None:
                    try:
                        await get_audit_logger().log_event(
                            event_type=AuditEventType.AI_PROPOSAL_CREATED,
                            description=(
                                f"AI proposal created | plan={plan.plan_id} | "
                                f"risk={plan.risk_tier}"
                            ),
                            user_id=current_user.get("user_id"),
                            event_metadata={
                                "plan_id": plan.plan_id,
                                "risk_tier": plan.risk_tier,
                                "reversible": plan.reversible,
                                "target_devices": [
                                    step.target_device_id
                                    for step in plan.steps
                                    if step.target_device_id
                                ],
                            },
                        )
                    except Exception:
                        logger.warning(
                            "Failed to audit AI proposal creation", exc_info=True
                        )
            else:
                logger.info(
                    "AI produced %d proposal(s) but they were not surfaced "
                    "(actionable=%s, fell_back=%s)",
                    len(agent_result.proposals),
                    trust.is_actionable,
                    agent_result.fell_back_to_direct,
                )

        # 5b. Persist a compact, scoped long-term memory of this answer so later
        # queries can recall it. Best-effort: a storage failure must never break
        # a query, and we skip the Ollama-unreachable fallback string.
        try:
            if (
                getattr(memory, "write_on_query", True)
                and response
                and "unable to connect to my AI brain" not in response
            ):
                digest_chars = getattr(memory, "answer_digest_chars", 500)
                if not isinstance(digest_chars, int) or digest_chars <= 0:
                    digest_chars = 500
                memory.remember(
                    f"Q: {request.query}\nA: {response[:digest_chars]}",
                    scope=memory_scope,
                    extra_metadata={
                        "source": "ai_query",
                        "trust_score": round(float(trust.trust_score), 3),
                        "is_actionable": bool(trust.is_actionable),
                    },
                )
                await _publish_investigation_event(
                    request, "memory_written", {"digest_chars": digest_chars}
                )
        except Exception:
            logger.warning("Failed to persist AI memory", exc_info=True)

        logger.info(
            "AI query done | device_id=%s | mode=%s | score=%.2f | actionable=%s",
            request.device_id or "N/A",
            trust.trust_mode.label,
            trust.trust_score,
            trust.is_actionable,
        )

        try:
            audit = get_audit_logger()
            await audit.log_event(
                event_type=AuditEventType.AI_QUERY,
                description=(
                    f"AI query | device={request.device_id or 'N/A'} | "
                    f"mode={trust.trust_mode.label} | score={trust.trust_score:.2f}"
                ),
                user_id=current_user.get("user_id"),
                event_metadata={
                    "query_length": len(request.query),
                    "trust_mode": trust.trust_mode.label,
                    "trust_score": trust.trust_score,
                    "actionable": trust.is_actionable,
                    "failed_gate": trust.failed_gate_id,
                    "agentic": request.agentic,
                    "routing_mode": routing_info["resolved"],
                    "routing_requested": routing_info["requested"],
                    "routing_reason": routing_info["reason"],
                },
            )
            if not trust.is_actionable:
                await audit.log_event(
                    event_type=AuditEventType.AI_GATE_FAILURE,
                    description=(
                        f"Gate {trust.failed_gate_id} failed | device={request.device_id or 'N/A'}"
                    ),
                    user_id=current_user.get("user_id"),
                    event_metadata={
                        "trust_score": trust.trust_score,
                        "failed_gate": trust.failed_gate_id,
                    },
                )
        except Exception:
            logger.warning("Failed to persist AI audit event", exc_info=True)

        await _publish_investigation_event(
            request,
            "completed",
            {
                "response": response,
                "trust_mode": getattr(trust, "trust_mode", None),
                "trust_score": getattr(trust, "trust_score", None),
                "routing": routing_info,
            },
        )

        return {
            "response": response,
            "timestamp": datetime.utcnow().isoformat(),
            "trust": trust.to_dict(),
            "routing": routing_info,
            **({"agentic": agentic_info} if agentic_info else {}),
            **({"proposal": proposal_info} if proposal_info else {}),
        }
    except HTTPException:
        # Preserve deliberate status codes (e.g. 503 when the AI gate is full).
        await _publish_investigation_event(
            request, "failed", {"reason": "http_exception"}
        )
        raise
    except Exception as e:
        logger.error(f"AI query failed: {e}", exc_info=True)
        await _publish_investigation_event(request, "failed", {"reason": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/push-notifications", tags=["AI Insights"])
async def get_push_insights(
    device_id: Optional[str] = Query(
        None, description="Optional device ID to filter by"
    ),
    days: int = Query(default=7, ge=1, le=90, description="Analysis period in days"),
) -> Dict[str, Any]:
    """Get AI analytics for push notification delivery."""
    try:
        analytics = AIAnalyticsService()
        analytics_result = await analytics.get_push_notification_analytics(
            device_id, days
        )

        # If the analytics service indicates an error, raise a generic HTTP error
        if (
            isinstance(analytics_result, dict)
            and analytics_result.get("status") == "error"
        ):
            logger.error(
                "Push notification analytics service reported an error: %s",
                analytics_result.get("message"),
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze push notifications",
            )

        return analytics_result
    except HTTPException:
        # Re-raise HTTPException without modification
        raise
    except Exception as e:
        logger.error(f"Failed to get push insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to analyze push notifications"
        )


@router.get("/insights/device/{device_id}", tags=["AI Insights"])
async def get_device_insights(
    device_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Analysis period in days"),
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive AI insights for a device.

    Includes performance trends, health score, and predictive analysis.
    Restricted to users with access to the device's site.
    """
    try:
        analytics = AIAnalyticsService()

        # Archived/unpaired/retired devices must not be visible to the AI.
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            device_result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = device_result.scalar_one_or_none()
        if not device or not device.is_active:
            raise HTTPException(
                status_code=404,
                detail=f"Device '{device_id}' not found or not active",
            )

        # Scope to the caller's site/tenant access.
        db_user = cast(
            "User",
            db.query(User).filter(User.email == current_user["email"]).first(),
        )
        verify_device_belongs_to_user(db_user, device, db, minimum_role="viewer")

        # Get performance trends
        performance = await analytics.get_device_performance_trends(device_id, days)

        # Get error analysis
        errors = await analytics.get_error_frequency_analysis(
            device_id, days=min(days, 7)
        )

        # Get failure prediction
        predictor = FailurePredictor()
        failure_prediction = await predictor.predict_device_failure(device_id)

        return {
            "device_id": device_id,
            "analysis_period_days": days,
            "performance": performance,
            "errors": errors,
            "failure_prediction": failure_prediction,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get device insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate device insights due to an internal error.",
        )


@router.get("/insights/site/{site_id}", tags=["AI Insights"])
async def get_site_insights(
    site_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Analysis period in days"),
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive AI insights for a site.

    Includes job patterns, optimal scheduling windows, and site-level analytics.
    Restricted to users with access to the site.
    """
    try:
        analytics = AIAnalyticsService()

        # Archived sites must not be visible to the AI.
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            site_result = await session.execute(
                select(Site).where(Site.site_id == site_id)
            )
            site = site_result.scalar_one_or_none()
        if not site or not site.is_active:
            raise HTTPException(
                status_code=404,
                detail=f"Site '{site_id}' not found or not active",
            )

        # Scope to the caller's site/tenant access.
        db_user = cast(
            "User",
            db.query(User).filter(User.email == current_user["email"]).first(),
        )
        verify_site_access_for_user(db_user, site_id, db, minimum_role="viewer")

        # Get job outcome patterns
        job_patterns = await analytics.get_job_outcome_patterns(site_id, days)

        # Get optimal scheduling windows
        scheduling = await analytics.get_optimal_scheduling_windows(site_id)

        # Get configuration change impact
        config_impact = await analytics.get_configuration_impact_analysis(
            site_id, days=min(days, 14)
        )

        return {
            "site_id": site_id,
            "analysis_period_days": days,
            "job_patterns": job_patterns,
            "scheduling_windows": scheduling,
            "configuration_impact": config_impact,
            "generated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get site insights: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate site insights due to an internal error.",
        )


# ==================== Prediction Endpoints ====================


@router.get("/predictions/failure/{device_id}", tags=["AI Predictions"])
async def predict_device_failure(
    device_id: str,
    window_hours: int = Query(
        default=24, ge=1, le=168, description="Prediction window in hours (max 7 days)"
    ),
    current_user: UserDict = Depends(require_user()),
    db: SASession = Depends(get_db),
) -> Dict[str, Any]:
    """Predict likelihood of device failure in the next N hours.

    Returns probability, risk level, contributing factors, and recommendations.
    Restricted to users with access to the device's site.
    """
    try:
        # Archived/unpaired/retired devices must not be visible to the AI.
        db_service = await get_database_service()
        async with db_service.get_session() as session:
            device_result = await session.execute(
                select(Device).where(Device.device_id == device_id)
            )
            device = device_result.scalar_one_or_none()
        if not device or not device.is_active:
            raise HTTPException(
                status_code=404,
                detail=f"Device '{device_id}' not found or not active",
            )

        # Scope to the caller's site/tenant access.
        db_user = cast(
            "User",
            db.query(User).filter(User.email == current_user["email"]).first(),
        )
        verify_device_belongs_to_user(db_user, device, db, minimum_role="viewer")

        predictor = FailurePredictor()
        prediction = await predictor.predict_device_failure(device_id, window_hours)

        return prediction

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to predict device failure: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to predict device failure due to an internal error.",
        )


@router.get("/predictions/at-risk-devices", tags=["AI Predictions"])
async def get_at_risk_devices(
    site_id: Optional[str] = Query(None, description="Optional site filter"),
    min_risk_level: str = Query(
        default="medium",
        pattern="^(low|medium|high|critical)$",
        description="Minimum risk level to include",
    ),
) -> Dict[str, Any]:
    """Identify all devices currently at risk of failure.

    Returns prioritized list with risk levels and recommendations.
    """
    try:
        predictor = FailurePredictor()
        at_risk = await predictor.identify_at_risk_devices(site_id, min_risk_level)

        return at_risk

    except Exception as e:
        logger.error(f"Failed to identify at-risk devices: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to identify at-risk devices due to an internal error.",
        )


# ==================== Recommendation Endpoints ====================


@router.post("/recommendations/schedule-job", tags=["AI Recommendations"])
async def recommend_job_schedule(request: JobScheduleRequest) -> Dict[str, Any]:
    """Get AI recommendation for optimal job execution time.

    Considers site schedules, historical success rates, and current conditions.
    """
    try:
        scheduler = PredictiveJobScheduler()

        # Parse earliest_start if provided
        earliest_start = None
        if request.earliest_start:
            try:
                earliest_start = datetime.fromisoformat(request.earliest_start)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid earliest_start format. Use ISO 8601 format.",
                )

        recommendation = await scheduler.recommend_execution_time(
            site_id=request.site_id,
            job_priority=request.job_priority,
            earliest_start=earliest_start,
        )

        return recommendation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recommend job schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate scheduling recommendation due to an internal error.",
        )


@router.post("/recommendations/success-probability", tags=["AI Recommendations"])
async def calculate_success_probability(
    request: SuccessProbabilityRequest,
) -> Dict[str, Any]:
    """Calculate probability of job success at a specific time.

    Analyzes device health, historical patterns, and site conditions.
    """
    try:
        scheduler = PredictiveJobScheduler()

        # Parse scheduled_time
        try:
            scheduled_time = datetime.fromisoformat(request.scheduled_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid scheduled_time format. Use ISO 8601 format.",
            )

        probability = await scheduler.calculate_success_probability(
            site_id=request.site_id,
            device_id=request.device_id,
            scheduled_time=scheduled_time,
        )

        return probability

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to calculate success probability: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate success probability due to an internal error.",
        )


@router.get("/recommendations/optimal-windows/{site_id}", tags=["AI Recommendations"])
async def get_optimal_windows(
    site_id: str,
    day_of_week: Optional[int] = Query(
        None, ge=0, le=6, description="Optional day filter (0=Monday, 6=Sunday)"
    ),
) -> Dict[str, Any]:
    """Get optimal scheduling windows for a site.

    Returns recommended time windows that avoid peak hours and maintenance periods.
    """
    try:
        analytics = AIAnalyticsService()
        windows = await analytics.get_optimal_scheduling_windows(site_id, day_of_week)

        return windows

    except Exception as e:
        logger.error(f"Failed to get optimal windows: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to get optimal scheduling windows due to an internal error.",
        )


# ==================== Health Forecast Endpoint ====================


@router.get("/health-forecast", tags=["AI Insights"])
async def get_health_forecast(
    site_id: Optional[str] = Query(None, description="Optional site filter"),
    forecast_hours: int = Query(
        default=24, ge=1, le=168, description="Forecast period in hours"
    ),
) -> Dict[str, Any]:
    """Get health forecast for site or all devices.

    Provides predictive view of system health in the forecast window.
    """
    try:
        predictor = FailurePredictor()

        # Get all at-risk devices
        at_risk = await predictor.identify_at_risk_devices(
            site_id, min_risk_level="low"
        )

        # Analyze overall health trend
        total_devices = at_risk.get("total_devices_analyzed", 0)
        at_risk_count = at_risk.get("at_risk_count", 0)
        risk_dist = at_risk.get("risk_distribution", {})

        # Calculate overall health score
        if total_devices > 0:
            health_percentage = ((total_devices - at_risk_count) / total_devices) * 100
        else:
            health_percentage = 100.0

        # Determine forecast status
        if risk_dist.get("critical", 0) > 0:
            forecast_status = "critical"
            forecast_message = "Critical issues require immediate attention"
        elif risk_dist.get("high", 0) > 0:
            forecast_status = "warning"
            forecast_message = "High-risk devices need attention soon"
        elif at_risk_count > 0:
            forecast_status = "moderate"
            forecast_message = "Some devices show elevated risk"
        else:
            forecast_status = "healthy"
            forecast_message = "All systems operating normally"

        return {
            "site_id": site_id,
            "forecast_hours": forecast_hours,
            "overall_health_score": round(health_percentage, 2),
            "forecast_status": forecast_status,
            "forecast_message": forecast_message,
            "total_devices": total_devices,
            "healthy_devices": total_devices - at_risk_count,
            "at_risk_devices": at_risk_count,
            "risk_distribution": risk_dist,
            "top_concerns": at_risk.get("at_risk_devices", [])[:5],  # Top 5
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to generate health forecast: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate health forecast due to an internal error.",
        )


# ==================== System Status ====================


@router.get("/status", tags=["AI Insights"])
async def get_ai_system_status() -> Dict[str, Any]:
    """Get AI system status and capabilities."""
    return {
        "status": "operational",
        "version": "1.0.0",
        "capabilities": {
            "device_insights": True,
            "site_insights": True,
            "failure_prediction": True,
            "at_risk_detection": True,
            "job_scheduling": True,
            "success_probability": True,
            "health_forecast": True,
        },
        "data_sources": {
            "device_metrics": "real-time (5s intervals)",
            "job_outcomes": "historical",
            "device_state_history": "real-time",
            "error_logs": "real-time",
            "configuration_history": "real-time",
            "site_analytics": "aggregated",
            "device_analytics": "aggregated",
            "site_operating_schedules": "configured",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
