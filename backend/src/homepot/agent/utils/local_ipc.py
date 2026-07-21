"""Local IPC server helpers used by the real device agent."""

import threading
from typing import Any, Dict, List, Optional, cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


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


def create_local_ipc_app(initial_state: LocalAgentState) -> FastAPI:
    """Create a lightweight localhost FastAPI app for local agent status and command IPC."""
    app = FastAPI(title="Homepot Local Agent IPC", version="0.1.0")
    app.state.agent_state = initial_state
    app.state.state_lock = threading.Lock()
    app.state.pending_commands = []  # type: ignore[assignment]
    app.state.command_results = {}  # type: ignore[assignment]

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

    # ------------------------------------------------------------------
    # Command IPC endpoints — allow the real device to pick up and
    # report results for commands received from the backend.
    # ------------------------------------------------------------------

    @app.get("/ipc/commands/pending")
    def get_pending_commands_ipc() -> List[Dict[str, Any]]:
        """Return commands waiting for execution by the real device.

        The real device should poll this endpoint, execute the command,
        and submit the result via ``POST /ipc/commands/{command_id}/result``.
        """
        with app.state.state_lock:
            return list(app.state.pending_commands)

    @app.post("/ipc/commands/{command_id}/result")
    def submit_command_result(
        command_id: str, body: CommandResultSubmission
    ) -> Dict[str, str]:
        """Accept the execution result of a command from the real device.

        The agent's result loop picks up this result and forwards it to the
        backend via ``PUT /api/v1/devices/{command_id}/status``.
        """
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
    def collect_command_results() -> Dict[str, Dict[str, Any]]:
        """Return collected command results (agent uses this to forward to backend)."""
        with app.state.state_lock:
            return dict(app.state.command_results)

    @app.delete("/ipc/commands/results/{command_id}")
    def clear_command_result(command_id: str) -> Dict[str, str]:
        """Remove a processed result from the results dict."""
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
