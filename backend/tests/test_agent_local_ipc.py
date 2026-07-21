"""Tests for the local IPC server — command queuing and result reporting."""

from homepot.agent.utils.local_ipc import (
    LocalAgentState,
    create_local_ipc_app,
    pop_command_result,
    push_pending_command,
)


class TestLocalAgentState:
    """Tests for ``LocalAgentState`` model."""

    def test_default_fields(self):
        """State initialises with provided fields."""
        state = LocalAgentState(device_id="dev-1", status="ONLINE")
        assert state.device_id == "dev-1"
        assert state.status == "ONLINE"
        assert state.last_heartbeat is None
        assert state.last_telemetry is None

    def test_with_optional_fields(self):
        """Optional fields can be set."""
        state = LocalAgentState(
            device_id="dev-1",
            status="ONLINE",
            last_heartbeat="2026-01-01T00:00:00",
            last_telemetry={"cpu": 50.0},
        )
        assert state.last_heartbeat == "2026-01-01T00:00:00"
        assert state.last_telemetry == {"cpu": 50.0}


class TestIpcCommandEndpoints:
    """Tests for the IPC command management endpoints."""

    def test_pending_commands_starts_empty(self):
        """Pending commands list is empty initially."""
        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        with app.state.state_lock:
            assert app.state.pending_commands == []

    def test_push_pending_command_adds_item(self):
        """push_pending_command adds a command to the pending list."""
        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        cmd = {"command_id": "c1", "command_type": "ping"}
        push_pending_command(app, cmd)
        with app.state.state_lock:
            assert len(app.state.pending_commands) == 1
            assert app.state.pending_commands[0]["command_id"] == "c1"

    def test_push_multiple_commands(self):
        """Multiple commands can be pushed to the pending list."""
        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        push_pending_command(app, {"command_id": "c2", "command_type": "restart"})
        with app.state.state_lock:
            assert len(app.state.pending_commands) == 2

    def test_pop_command_result_returns_none_for_missing(self):
        """pop_command_result returns None for unknown command_id."""
        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        result = pop_command_result(app, "nonexistent")
        assert result is None

    def test_pop_command_result_returns_stored_result(self):
        """pop_command_result returns the stored result and removes it."""
        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        with app.state.state_lock:
            app.state.command_results["c1"] = {
                "status": "completed",
                "result": {"message": "pong"},
            }
        result = pop_command_result(app, "c1")
        assert result is not None
        assert result["status"] == "completed"
        assert result["result"] == {"message": "pong"}
        # Should be removed
        result2 = pop_command_result(app, "c1")
        assert result2 is None


class TestIpcHttpEndpoints:
    """Tests for HTTP endpoints exposed by the IPC app (using TestClient)."""

    def test_health_returns_ok(self):
        """GET /health returns ok status."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_status_returns_device_id(self):
        """GET /status returns agent state."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(LocalAgentState(device_id="dev-42", status="ONLINE"))
        client = TestClient(app)
        response = client.get("/status")
        data = response.json()
        assert data["device_id"] == "dev-42"
        assert data["status"] == "ONLINE"

    def test_get_pending_commands_empty(self):
        """GET /ipc/commands/pending returns empty list initially."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        client = TestClient(app)
        response = client.get("/ipc/commands/pending")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_pending_commands_with_items(self):
        """GET /ipc/commands/pending returns pushed commands."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        client = TestClient(app)
        response = client.get("/ipc/commands/pending")
        data = response.json()
        assert len(data) == 1
        assert data[0]["command_id"] == "c1"

    def test_submit_command_result(self):
        """POST /ipc/commands/{id}/result stores the result."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        client = TestClient(app)
        response = client.post(
            "/ipc/commands/c1/result",
            json={"status": "completed", "result": {"message": "pong"}},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}
        with app.state.state_lock:
            assert app.state.command_results["c1"]["status"] == "completed"

    def test_submit_result_for_unknown_command(self):
        """POST /ipc/commands/{id}/result returns 404 for unknown command."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        client = TestClient(app)
        response = client.post(
            "/ipc/commands/nonexistent/result",
            json={"status": "completed"},
        )
        assert response.status_code == 404

    def test_collect_command_results(self):
        """GET /ipc/commands/results returns all stored results."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        client = TestClient(app)
        client.post(
            "/ipc/commands/c1/result",
            json={"status": "completed", "result": {"msg": "ok"}},
        )
        response = client.get("/ipc/commands/results")
        data = response.json()
        assert "c1" in data
        assert data["c1"]["status"] == "completed"

    def test_clear_command_result(self):
        """DELETE /ipc/commands/results/{id} removes a result."""
        from fastapi.testclient import TestClient

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        push_pending_command(app, {"command_id": "c1", "command_type": "ping"})
        client = TestClient(app)
        client.post(
            "/ipc/commands/c1/result",
            json={"status": "completed"},
        )
        delete_resp = client.delete("/ipc/commands/results/c1")
        assert delete_resp.status_code == 200
        assert delete_resp.json() == {"status": "cleared"}
        # Verify it's gone
        get_resp = client.get("/ipc/commands/results")
        assert "c1" not in get_resp.json()


class TestPopNextResult:
    """Tests for ``_pop_next_result`` (used in command_result_loop)."""

    def test_empty_when_no_results(self):
        """Returns (None, None) when no results are available."""
        from homepot.agent.real_device_agent import _pop_next_result

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        cid, result = _pop_next_result(app)
        assert cid is None
        assert result is None

    def test_pops_first_result(self):
        """Pops the first available result."""
        from homepot.agent.real_device_agent import _pop_next_result

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        with app.state.state_lock:
            app.state.command_results["c1"] = {"status": "completed", "result": {}}
            app.state.command_results["c2"] = {"status": "failed", "result": {}}
        cid, result = _pop_next_result(app)
        assert cid is not None
        assert result is not None
        assert result["status"] in ("completed", "failed")
        # Only one result should be removed
        with app.state.state_lock:
            assert len(app.state.command_results) == 1

    def test_multiple_calls_eventually_empty(self):
        """Multiple pop calls eventually empty the results dict."""
        from homepot.agent.real_device_agent import _pop_next_result

        app = create_local_ipc_app(
            LocalAgentState(device_id="dev-1", status="STARTING")
        )
        with app.state.state_lock:
            app.state.command_results["c1"] = {"status": "completed"}
            app.state.command_results["c2"] = {"status": "completed"}
        _pop_next_result(app)
        _pop_next_result(app)
        cid, result = _pop_next_result(app)
        assert cid is None
