"""Local IPC server helpers used by the real device agent."""

import threading
from typing import Any, Dict, Optional, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class LocalAgentState(BaseModel):
    """In-memory state model exposed to local UI consumers."""

    device_id: str
    status: str
    last_heartbeat: Optional[str] = None
    last_telemetry: Optional[Dict[str, Any]] = None


def create_local_ipc_app(initial_state: LocalAgentState) -> FastAPI:
    """Create a lightweight localhost FastAPI app for local agent status."""
    app = FastAPI(title="Homepot Local Agent IPC", version="0.1.0")
    app.state.agent_state = initial_state
    app.state.state_lock = threading.Lock()

    # Allow Electron/React UI apps to call localhost IPC from any origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/status")
    def get_status() -> Dict[str, Any]:
        """Return current agent runtime status."""
        with app.state.state_lock:
            return cast(Dict[str, Any], app.state.agent_state.model_dump())

    @app.get("/ipc/status")
    def get_status_alias() -> Dict[str, Any]:
        """Alias endpoint for UI clients that namespace IPC routes."""
        with app.state.state_lock:
            return cast(Dict[str, Any], app.state.agent_state.model_dump())

    @app.get("/health")
    def health() -> Dict[str, str]:
        """Return basic health status for local IPC consumers."""
        return {"status": "ok"}

    @app.get("/last-telemetry")
    def get_last_telemetry() -> Dict[str, Any]:
        """Return the most recent telemetry snapshot."""
        with app.state.state_lock:
            return {"data": app.state.agent_state.last_telemetry}

    @app.get("/ipc/last-telemetry")
    def get_last_telemetry_alias() -> Dict[str, Any]:
        """Alias endpoint for UI clients that namespace IPC routes."""
        with app.state.state_lock:
            return {"data": app.state.agent_state.last_telemetry}

    return app


def update_local_agent_state(
    app: FastAPI,
    *,
    status: Optional[str] = None,
    last_heartbeat: Optional[str] = None,
    last_telemetry: Optional[Dict[str, Any]] = None,
) -> None:
    """Update local IPC state values exposed to UI clients."""
    with app.state.state_lock:
        state: LocalAgentState = app.state.agent_state
        if status is not None:
            state.status = status
        if last_heartbeat is not None:
            state.last_heartbeat = last_heartbeat
        if last_telemetry is not None:
            state.last_telemetry = last_telemetry
