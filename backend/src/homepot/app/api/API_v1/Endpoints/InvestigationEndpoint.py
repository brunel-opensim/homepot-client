"""Investigation session endpoints (backend-owned AI investigations).

Stage 2 of the investigation workflow: persistent sessions, messages and runs
with owner + site/device scoping and per-operation authorisation.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SASession
from typing import AsyncGenerator

from homepot.app.auth_utils import get_accessible_site_ids, require_user
from homepot.app.schemas.schemas import UserDict
from homepot.database import get_db
from homepot.models import (
    InvestigationMessage,
    InvestigationRun,
    InvestigationSession,
    User,
)
from homepot.app.api.API_v1.Endpoints.AIActionEndpoint import _get_db_user

router = APIRouter(dependencies=[Depends(require_user())])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _authorize_session(
    db: SASession, db_user: User, session: InvestigationSession
) -> None:
    """Verify the caller may access *session*; raise HTTPException otherwise."""
    if db_user.is_admin:
        return
    if session.owner_user_id != db_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the session owner"
        )
    # Site scope re-check.
    if session.site_id is not None:
        accessible = get_accessible_site_ids(db_user, db)
        if accessible is not None and session.site_id not in accessible:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No access to this site"
            )


def _get_session(db: SASession, session_id: str) -> InvestigationSession:
    sess = (
        db.query(InvestigationSession)
        .filter(InvestigationSession.session_id == session_id)
        .first()
    )
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return sess


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    """Request body for creating an investigation session."""

    title: Optional[str] = None
    site_id: Optional[int] = None
    device_id: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    """Request body for updating an investigation session."""

    title: Optional[str] = None
    status: Optional[str] = None  # "active" | "archived"


class AddMessageRequest(BaseModel):
    """Request body for adding a message to an investigation session."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)
    trust: Optional[dict] = None
    routing: Optional[dict] = None
    sources: Optional[list] = None


class CreateRunRequest(BaseModel):
    """Request body for creating a run in an investigation session."""

    message_id: Optional[str] = None
    status: str = "pending"


class UpdateRunRequest(BaseModel):
    """Request body for updating a run in an investigation session."""

    status: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", tags=["Investigations"])
async def create_session(
    body: CreateSessionRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    # Validate site access if a site is given.
    if body.site_id is not None and not db_user.is_admin:
        accessible = get_accessible_site_ids(db_user, db)
        if accessible is not None and body.site_id not in accessible:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No access to this site"
            )
    sess = InvestigationSession(
        session_id=str(uuid.uuid4()),
        owner_user_id=db_user.id,
        site_id=body.site_id,
        device_id=body.device_id,
        title=body.title,
        status="active",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    try:
        from homepot.app.events.investigation_events import get_event_bus

        await get_event_bus().publish(
            session_id=str(sess.session_id),
            run_id=str(sess.session_id),
            event="session_created",
            data={
                "owner_user_id": sess.owner_user_id,
                "site_id": sess.site_id,
                "device_id": sess.device_id,
            },
        )
    except Exception:
        pass

    return {"status": "success", "data": _serialize_session(sess)}


@router.get("", tags=["Investigations"])
async def list_sessions(
    include_archived: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    q = db.query(InvestigationSession)
    if not db_user.is_admin:
        q = q.filter(InvestigationSession.owner_user_id == db_user.id)
    if not include_archived:
        q = q.filter(InvestigationSession.status == "active")
    q = q.order_by(InvestigationSession.updated_at.desc()).offset(offset).limit(limit)
    sessions = q.all()
    return {
        "status": "success",
        "data": {"sessions": [_serialize_session(s) for s in sessions]},
    }


@router.get("/{session_id}", tags=["Investigations"])
async def get_session(
    session_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    messages = (
        db.query(InvestigationMessage)
        .filter(InvestigationMessage.session_id == sess.id)
        .order_by(InvestigationMessage.sequence)
        .all()
    )
    runs = (
        db.query(InvestigationRun)
        .filter(InvestigationRun.session_id == sess.id)
        .order_by(InvestigationRun.started_at)
        .all()
    )
    return {
        "status": "success",
        "data": {
            "session": _serialize_session(sess),
            "messages": [_serialize_message(m) for m in messages],
            "runs": [_serialize_run(r) for r in runs],
        },
    }


@router.patch("/{session_id}", tags=["Investigations"])
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    if body.title is not None:
        sess.title = body.title  # type: ignore[assignment]
    if body.status is not None:
        if body.status not in ("active", "archived"):
            raise HTTPException(status_code=400, detail="Invalid status")
        sess.status = body.status  # type: ignore[assignment]
    sess.updated_at = _utc_now()  # type: ignore[assignment]
    db.commit()
    db.refresh(sess)
    return {"status": "success", "data": _serialize_session(sess)}


@router.post("/{session_id}/resume", tags=["Investigations"])
async def resume_session(
    session_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    # Re-check site access on resume (already done in _authorize_session).
    messages = (
        db.query(InvestigationMessage)
        .filter(InvestigationMessage.session_id == sess.id)
        .order_by(InvestigationMessage.sequence)
        .all()
    )
    sess.last_message_at = sess.last_message_at or _utc_now()  # type: ignore[assignment]
    db.commit()
    return {
        "status": "success",
        "data": {
            "session": _serialize_session(sess),
            "messages": [_serialize_message(m) for m in messages],
        },
    }


@router.post("/{session_id}/messages", tags=["Investigations"])
async def add_message(
    session_id: str,
    body: AddMessageRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    # Next sequence number
    last = (
        db.query(InvestigationMessage)
        .filter(InvestigationMessage.session_id == sess.id)
        .order_by(InvestigationMessage.sequence.desc())
        .first()
    )
    seq = (last.sequence + 1) if last else 1
    msg = InvestigationMessage(
        message_id=str(uuid.uuid4()),
        session_id=sess.id,
        role=body.role,
        content=body.content,
        sequence=seq,
        trust=body.trust,
        routing=body.routing,
        sources=body.sources,
        created_at=_utc_now(),
    )
    db.add(msg)
    sess.last_message_at = _utc_now()  # type: ignore[assignment]
    sess.updated_at = _utc_now()  # type: ignore[assignment]
    db.commit()
    db.refresh(msg)

    try:
        from homepot.app.events.investigation_events import get_event_bus

        await get_event_bus().publish(
            session_id=str(sess.session_id),
            run_id=str(msg.message_id),
            event="message_added",
            data={"role": msg.role, "sequence": msg.sequence},
        )
    except Exception:
        pass

    return {"status": "success", "data": _serialize_message(msg)}


@router.get("/{session_id}/messages", tags=["Investigations"])
async def list_messages(
    session_id: str,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    messages = (
        db.query(InvestigationMessage)
        .filter(InvestigationMessage.session_id == sess.id)
        .order_by(InvestigationMessage.sequence)
        .all()
    )
    return {
        "status": "success",
        "data": {"messages": [_serialize_message(m) for m in messages]},
    }


@router.post("/{session_id}/runs", tags=["Investigations"])
async def create_run(
    session_id: str,
    body: CreateRunRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    msg = None
    if body.message_id:
        msg = (
            db.query(InvestigationMessage)
            .filter(
                InvestigationMessage.message_id == body.message_id,
                InvestigationMessage.session_id == sess.id,
            )
            .first()
        )
        if msg is None:
            raise HTTPException(status_code=404, detail="Message not found in session")
    run = InvestigationRun(
        run_id=str(uuid.uuid4()),
        session_id=sess.id,
        message_id=msg.id if msg else None,
        status=body.status or "pending",
        started_at=_utc_now() if body.status == "running" else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Publish a run-lifecycle event for SSE subscribers.
    try:
        from homepot.app.events.investigation_events import get_event_bus

        await get_event_bus().publish(
            session_id=str(sess.session_id),
            run_id=str(run.run_id),
            event="run_queued" if run.status == "pending" else "run_started",
            data={"status": run.status},
        )
    except Exception:
        pass

    return {"status": "success", "data": _serialize_run(run)}


@router.patch("/{session_id}/runs/{run_id}", tags=["Investigations"])
async def update_run(
    session_id: str,
    run_id: str,
    body: UpdateRunRequest,
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> Dict[str, Any]:
    """Investigation session operation."""
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    run = (
        db.query(InvestigationRun)
        .filter(
            InvestigationRun.run_id == run_id, InvestigationRun.session_id == sess.id
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if body.status is not None:
        if body.status not in (
            "pending",
            "running",
            "completed",
            "cancelled",
            "failed",
        ):
            raise HTTPException(status_code=400, detail="Invalid run status")
        run.status = body.status  # type: ignore[assignment]
        if body.status in ("completed", "cancelled", "failed"):
            run.completed_at = _utc_now()  # type: ignore[assignment]
        if body.status == "running" and run.started_at is None:
            run.started_at = _utc_now()  # type: ignore[assignment]
    if body.error is not None:
        run.error = body.error  # type: ignore[assignment]
    db.commit()
    db.refresh(run)

    # Publish a terminal or progress event for SSE subscribers.
    try:
        from homepot.app.events.investigation_events import get_event_bus

        if body.status in ("completed", "cancelled", "failed"):
            event_name = (
                "completed"
                if body.status == "completed"
                else "cancelled" if body.status == "cancelled" else "failed"
            )
            await get_event_bus().publish(
                session_id=str(sess.session_id),
                run_id=str(run.run_id),
                event=event_name,
                data={"status": run.status, "error": run.error},
            )
        elif body.status in ("running",):
            await get_event_bus().publish(
                session_id=str(sess.session_id),
                run_id=str(run.run_id),
                event="run_started",
                data={"status": run.status},
            )
    except Exception:
        pass

    return {"status": "success", "data": _serialize_run(run)}


@router.get("/{session_id}/runs/{run_id}/events", tags=["Investigations"])
async def stream_run_events(
    session_id: str,
    run_id: str,
    last_event_id: Optional[int] = Header(None, alias="Last-Event-ID"),
    db: SASession = Depends(get_db),
    current_user: UserDict = Depends(require_user()),
) -> StreamingResponse:
    """Stream a run's activity over Server-Sent Events.

    Reconnection is supported via the standard ``Last-Event-ID`` header: missed
    events are replayed from the in-memory buffer before live streaming
    resumes. Events are identified by (session, run, sequence) so a reconnect
    never duplicates a message.

    Requires viewer-level access on the session (owner or admin).
    """
    db_user = _get_db_user(db, current_user)
    sess = _get_session(db, session_id)
    _authorize_session(db, db_user, sess)
    run = (
        db.query(InvestigationRun)
        .filter(
            InvestigationRun.run_id == run_id,
            InvestigationRun.session_id == sess.id,
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    from homepot.app.events.investigation_events import get_event_bus

    bus = get_event_bus()

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in bus.subscribe(session_id, run_id, last_event_id):
                yield chunk
        except Exception as e:  # pragma: no cover - defensive
            yield f'event: error\ndata: {{"error": "{str(e)}"}}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_session(sess: InvestigationSession) -> dict:
    return {
        "session_id": sess.session_id,
        "owner_user_id": sess.owner_user_id,
        "site_id": sess.site_id,
        "device_id": sess.device_id,
        "title": sess.title,
        "status": sess.status,
        "created_at": sess.created_at.isoformat() if sess.created_at else None,
        "updated_at": sess.updated_at.isoformat() if sess.updated_at else None,
        "last_message_at": (
            sess.last_message_at.isoformat() if sess.last_message_at else None
        ),
    }


def _serialize_message(msg: InvestigationMessage) -> dict:
    return {
        "message_id": msg.message_id,
        "session_id": msg.session_id and str(msg.session_id),
        "role": msg.role,
        "content": msg.content,
        "sequence": msg.sequence,
        "trust": msg.trust,
        "routing": msg.routing,
        "sources": msg.sources,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _serialize_run(run: InvestigationRun) -> dict:
    return {
        "run_id": run.run_id,
        "session_id": run.session_id,
        "message_id": run.message_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error": run.error,
    }
