"""Local IPC server helpers used by the real device agent."""

import secrets
import threading
from typing import Any, Dict, List, Optional, cast

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

AUTH_HEADER = "X-Agent-Token"


class LocalAgentState(BaseModel):
    """In-memory state model exposed to local UI consumers."""

    device_id: str
    status: str
    last_heartbeat: Optional[str] = None
    last_telemetry: Optional[Dict[str, Any]] = None


class PendingCommand(BaseModel):
    """A command awaiting execution by the real device."""

    command_id: str
    command_type: str
    payload: Optional[Dict[str, Any]] = None


class CommandResultSubmission(BaseModel):
    """Result sent back by the real device after executing a command."""

    status: str
    result: Optional[Dict[str, Any]] = None


def _authenticate(token: Optional[str], expected_token: Optional[str]) -> None:
    """Reject the request when the token is missing or does not match.

    When ``expected_token`` is ``None`` (auth disabled) the check passes.
    """
    if expected_token is None:
        return
    if not token or not secrets.compare_digest(token, expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def create_local_ipc_app(
    initial_state: LocalAgentState, token: Optional[str] = None
) -> FastAPI:
    """Create a lightweight localhost FastAPI app for local agent status and command IPC.

    Parameters
    ----------
    token:
        Optional bearer token. When set, every endpoint requires it via the
        ``X-Agent-Token`` header. When ``None``, authentication is disabled
        (default, matching legacy behaviour).
    """
    app = FastAPI(title="Homepot Local Agent IPC", version="0.1.0")
    app.state.agent_state = initial_state
    app.state.state_lock = threading.Lock()
    app.state.pending_commands = []  # type: ignore[assignment]
    app.state.command_results = {}  # type: ignore[assignment]
    app.state.auth_token = token

    # The IPC server is localhost-only. CORS is applied for the Electron
    # renderer, but when auth is enabled the token protects the endpoints
    # regardless of origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", AUTH_HEADER],
    )

    @app.get("/status")
    def get_status(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        """Return current agent runtime status."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return cast(Dict[str, Any], app.state.agent_state.model_dump())

    @app.get("/ipc/status")
    def get_status_alias(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        """Alias endpoint for UI clients that namespace IPC routes."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return cast(Dict[str, Any], app.state.agent_state.model_dump())

    @app.get("/health")
    def health() -> Dict[str, str]:
        """Return basic health status for local IPC consumers."""
        return {"status": "ok"}

    @app.get("/last-telemetry")
    def get_last_telemetry(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        """Return the most recent telemetry snapshot."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return {"data": app.state.agent_state.last_telemetry}

    @app.get("/ipc/last-telemetry")
    def get_last_telemetry_alias(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        """Alias endpoint for UI clients that namespace IPC routes."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return {"data": app.state.agent_state.last_telemetry}

    # ------------------------------------------------------------------
    # Command IPC endpoints — allow the real device to pick up and
    # report results for commands received from the backend.
    # ------------------------------------------------------------------

    @app.get("/ipc/commands/pending")
    def get_pending_commands_ipc(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> List[Dict[str, Any]]:
        """Return commands waiting for execution by the real device.

        The real device should poll this endpoint, execute the command,
        and submit the result via ``POST /ipc/commands/{command_id}/result``.
        """
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return list(app.state.pending_commands)

    @app.post("/ipc/commands/{command_id}/result")
    def submit_command_result(
        command_id: str,
        body: CommandResultSubmission,
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, str]:
        """Accept the execution result of a command from the real device.

        The agent's result loop picks up this result and forwards it to the
        backend via ``PUT /api/v1/devices/commands/{command_id}/status``.
        """
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            original = next(
                (
                    c
                    for c in app.state.pending_commands
                    if c.get("command_id") == command_id
                ),
                None,
            )
            if original is None:
                raise HTTPException(
                    status_code=404, detail="Command not found in pending list"
                )

            app.state.command_results[command_id] = {
                "status": body.status,
                "result": body.result,
            }
            app.state.pending_commands = [
                c
                for c in app.state.pending_commands
                if c.get("command_id") != command_id
            ]

        return {"status": "accepted"}

    @app.get("/ipc/commands/results")
    def collect_command_results(
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, Dict[str, Any]]:
        """Return collected command results (agent uses this to forward to backend)."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            return dict(app.state.command_results)

    @app.delete("/ipc/commands/results/{command_id}")
    def clear_command_result(
        command_id: str,
        x_agent_token: Optional[str] = Header(default=None),
    ) -> Dict[str, str]:
        """Remove a processed result from the results dict."""
        _authenticate(x_agent_token, app.state.auth_token)
        with app.state.state_lock:
            app.state.command_results.pop(command_id, None)
        return {"status": "cleared"}

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


def push_pending_command(app: FastAPI, command: Dict[str, Any]) -> None:
    """Add a command to the IPC pending list for the real device to pick up."""
    with app.state.state_lock:
        app.state.pending_commands.append(command)


def pop_command_result(app: FastAPI, command_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and remove a command result submitted by the real device."""
    with app.state.state_lock:
        result = cast(
            Optional[Dict[str, Any]], app.state.command_results.pop(command_id, None)
        )
    return result
