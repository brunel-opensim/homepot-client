"""Tests for tools/compose-soak-test.py.

The tool is a hyphenated script, not an importable module, so it is loaded by
path. Everything here is hermetic: the device and the API are fakes, because a
soak run must never be able to touch real hardware from a test suite.

These exist because the first real run produced a misleading report twice over:
every command was flagged for "new errors" that were really its own completion
line and a heartbeat, and the agent-restart probe claimed a restart after 0.1s
while the restart counter had not moved.
"""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types

import httpx
import pytest

TOOL = Path(__file__).with_name("compose-soak-test.py")
NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def soak():
    """Load the soak script as a module."""
    spec = importlib.util.spec_from_file_location("compose_soak_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["compose_soak_test"] = module
    spec.loader.exec_module(module)
    return module


def iso(moment):
    """Format a datetime the way the API does."""
    return moment.isoformat()


class FakeResponse:
    """Minimal httpx.Response stand-in."""

    def __init__(self, payload, status_code=200):
        """Store the canned body and status."""
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        """Return the canned body."""
        return self._payload

    def raise_for_status(self):
        """Never raise: callers decide based on status_code."""
        return None


DEVICE_OK = {
    "name": "Brunel Device 001",
    "lifecycle_state": "active",
    "last_seen": iso(NOW),
    "agent_restart_count": 3,
    "device_permissions": {
        "root_access": True,
        "command_execution": True,
        "process_monitoring": True,
        "network_monitoring": True,
        "filesystem_access": True,
    },
}


# --- Readiness ---------------------------------------------------------------


def test_readiness_ready_device(soak):
    """An active device with every grant is ready and quiet."""
    ready, problems, warnings = soak.evaluate_readiness(DEVICE_OK, soak.SOAK_COMMANDS)
    assert ready
    assert problems == []
    assert warnings == []


def test_readiness_suspended_device_is_not_ready(soak):
    """A suspended device stops the run before anything is queued."""
    device = dict(DEVICE_OK, lifecycle_state="suspended")
    ready, problems, _ = soak.evaluate_readiness(device, soak.SOAK_COMMANDS)
    assert not ready
    assert "suspended" in problems[0]


def test_readiness_missing_grants_are_named(soak):
    """Each missing grant is reported so the fix is obvious."""
    device = dict(
        DEVICE_OK,
        device_permissions={"root_access": False, "command_execution": True},
    )
    ready, problems, _ = soak.evaluate_readiness(device, soak.SOAK_COMMANDS)
    assert not ready
    assert any("root_access" in problem for problem in problems)
    assert sum(1 for p in problems if "missing grant" in p) == 3


def test_readiness_stale_last_seen_warns_but_continues(soak):
    """A stale heartbeat is a warning, not a blocker: agents poll slowly."""
    device = dict(DEVICE_OK, last_seen=iso(NOW - timedelta(minutes=30)))
    ready, _, warnings = soak.evaluate_readiness(device, soak.SOAK_COMMANDS)
    assert ready
    assert warnings


# --- History and audit -------------------------------------------------------


def test_verify_history_accepts_recorded_command(soak):
    """A command with a stored result counts as recorded."""
    history = [{"command_id": "c1", "status": "completed", "result": {"count": 1}}]
    assert soak.verify_history(history, "c1", "completed")["ok"]


def test_verify_history_rejects_status_mismatch(soak):
    """History must agree with the status the device reported."""
    history = [{"command_id": "c1", "status": "completed", "result": {}}]
    assert not soak.verify_history(history, "c1", "failed")["ok"]


def test_verify_history_rejects_missing_row(soak):
    """A command the server did not record is a failure, not a note."""
    assert not soak.verify_history([], "c1", "completed")["ok"]


def audit_events(command_type="list_processes", command_id="c1"):
    """Build the three audit rows a healthy command produces."""
    return [
        {
            "event_type": "command_queued",
            "description": f"User 'admin' queued {command_type} command for device 'D'",
            "created_at": iso(NOW),
        },
        {
            "event_type": "command_sent",
            "description": f"Device 'D' acknowledged command '{command_id}'",
            "created_at": iso(NOW),
        },
        {
            "event_type": "command_completed",
            "description": f"Device 'D' reported command '{command_id}' as completed",
            "created_at": iso(NOW),
        },
    ]


def test_verify_audit_full_trail(soak):
    """Accept a complete queued + sent + completed trail."""
    result = soak.verify_audit(
        audit_events(),
        "c1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert result["ok"]
    assert result["queued"] and result["sent"] and result["terminal"]


def test_verify_audit_missing_queued(soak):
    """A missing queued event fails the trail."""
    result = soak.verify_audit(
        audit_events()[1:],
        "c1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert not result["ok"]
    assert not result["queued"]


def test_verify_audit_missing_terminal_event(soak):
    """A trail that stops at 'sent' is incomplete."""
    result = soak.verify_audit(
        audit_events()[:1],
        "c1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert not result["ok"]
    assert result["queued"]
    assert not result["sent"]
    assert not result["terminal"]


# --- Result shape and verdicts ----------------------------------------------


def test_result_shape_accepts_expected_keys(soak):
    """A healthy payload has no complaints."""
    assert (
        soak.result_shape_problems("list_processes", {"processes": [], "count": 0})
        == []
    )


def test_result_shape_names_missing_key(soak):
    """A missing key is reported by name."""
    assert soak.result_shape_problems("list_processes", {"count": 0}) == [
        "result is missing 'processes'"
    ]


def test_result_shape_reports_agent_error(soak):
    """An agent-side error is surfaced before the shape problems."""
    problems = soak.result_shape_problems("run_command", {"error": "boom"})
    assert problems[0] == "agent reported error: boom"
    assert "result is missing 'exit_code'" in problems


def test_result_shape_missing_result(soak):
    """No result at all is a single clear problem."""
    assert soak.result_shape_problems("run_command", None) == ["result is missing"]


def test_subtests_verdict_pass(soak):
    """Every sub-test passing yields a pass verdict."""
    verdict, subtests = soak.subtests_of(
        "health_check", {"results": {"memory": {"status": "pass"}}}
    )
    assert verdict == "pass"
    assert subtests


def test_subtests_verdict_fail(soak):
    """One failing sub-test fails the verdict."""
    verdict, _ = soak.subtests_of(
        "health_check",
        {"results": {"memory": {"status": "fail"}, "network": {"status": "pass"}}},
    )
    assert verdict == "fail"


def test_subtests_absent_for_plain_actions(soak):
    """Actions without sub-tests report no verdict."""
    assert soak.subtests_of("list_drives", {"drives": []}) == (None, {})


def make_record(soak, action, checks=None, status="completed", verdict=None, errors=()):
    """Build the parts of a record that classify_outcome reads."""
    names = ("accepted", "delivered", "executed", "result_shape", "history", "audit")
    wanted = names if checks is None else checks
    return {
        "action": action,
        "status": status,
        "verdict": verdict,
        "new_errors": list(errors),
        "checks": {name: name in wanted for name in names},
    }


@pytest.mark.parametrize(
    "kwargs, timed_out, expected",
    [
        ({}, False, "PASS"),
        ({}, True, "TIMEOUT"),
        ({"checks": ("accepted", "delivered")}, False, "FAIL"),
        ({"action": "health_check", "verdict": "pass"}, False, "PASS"),
        ({"action": "health_check", "verdict": "fail"}, False, "PASS_NOTE"),
        ({"status": "failed"}, False, "FAIL"),
        ({"errors": ("2026-11-15T15:00:00|E1|boom",)}, False, "PASS_NOTE"),
    ],
)
def test_classify_outcome(soak, kwargs, timed_out, expected):
    """Outcomes map to the documented categories."""
    kwargs.setdefault("action", "run_command")
    record = make_record(soak, **kwargs)
    assert soak.classify_outcome(record, timed_out) == expected


# --- Device log filtering ----------------------------------------------------


def test_log_filter_drops_heartbeats_and_completion_lines(soak):
    """Bookkeeping rows are not errors, however alarming they look.

    The first run counted these and flagged all 24 commands.
    """
    rows = [
        {
            "timestamp": "2026-11-15T15:09:18",
            "severity": "info",
            "category": "status",
            "error_code": None,
            "error_message": "Status report: ONLINE | uptime 409813s | cpu 6.1%",
        },
        {
            "timestamp": "2026-11-15T15:09:29",
            "severity": "info",
            "category": "command",
            "error_code": None,
            "error_message": "Command completed: list_processes (2555f7d0)",
        },
    ]
    client = types.SimpleNamespace(get=lambda url, params=None: FakeResponse(rows))
    assert soak.error_fingerprints(client, "http://x", "D") == []


def test_log_filter_keeps_real_errors(soak):
    """A genuine device error still registers."""
    rows = [
        {
            "timestamp": "2026-11-15T15:20:00",
            "severity": "error",
            "category": "agent",
            "error_code": "AGENT-500",
            "error_message": "unhandled exception in command worker",
        }
    ]
    client = types.SimpleNamespace(get=lambda url, params=None: FakeResponse(rows))
    found = soak.error_fingerprints(client, "http://x", "D")
    assert len(found) == 1
    assert "AGENT-500" in found[0]


def test_log_filter_keeps_error_code_without_severity(soak):
    """An error code alone is enough to count."""
    rows = [
        {
            "timestamp": "2026-11-15T15:20:01",
            "severity": None,
            "category": None,
            "error_code": "SVC-101",
            "error_message": "spooler unreachable",
        }
    ]
    client = types.SimpleNamespace(get=lambda url, params=None: FakeResponse(rows))
    assert len(soak.error_fingerprints(client, "http://x", "D")) == 1


def test_log_filter_keeps_warnings(soak):
    """Warnings are worth a look, so they count."""
    rows = [{"severity": "warning", "category": "device", "error_message": "disk 91%"}]
    client = types.SimpleNamespace(get=lambda url, params=None: FakeResponse(rows))
    assert len(soak.error_fingerprints(client, "http://x", "D")) == 1


def test_log_filter_survives_fetch_failure(soak):
    """A log fetch failure disables the comparison instead of ending the run."""

    def boom(url, params=None):
        raise httpx.ConnectError("offline")

    client = types.SimpleNamespace(get=boom)
    assert soak.error_fingerprints(client, "http://x", "D") == []


# --- Agent restart probe -----------------------------------------------------


def device_state(count, uptime, seen=None):
    """Build a device payload carrying the two restart signals."""
    return {
        "agent_restart_count": count,
        "agent_uptime_seconds": uptime,
        "last_seen": seen or iso(NOW),
    }


def run_probe(soak, snapshots, baseline, timeout=1):
    """Run the probe over a scripted sequence of device snapshots."""
    calls = {"n": 0}

    def get(url):
        index = min(calls["n"], len(snapshots) - 1)
        calls["n"] += 1
        return FakeResponse(snapshots[index])

    client = types.SimpleNamespace(get=get)
    return soak.wait_for_agent_recovery(client, "http://x", "D", baseline, timeout)


def test_probe_requires_proof_not_last_seen(soak, monkeypatch):
    """An unchanged counter with old uptime is not a restart.

    This is the exact false positive the first run reported as "back after 0.1s".
    """
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    baseline = {"agent_restart_count": 25, "agent_uptime_seconds": 410000}
    result = run_probe(soak, [device_state(25, 410010)], baseline)
    assert result["recovered"] is False
    assert result["verified"] is True
    assert result["proof"] is None


def test_probe_accepts_counter_increment(soak):
    """Counter 25 -> 26 proves the restart, as seen on real hardware."""
    baseline = {"agent_restart_count": 25, "agent_uptime_seconds": 410000}
    result = run_probe(soak, [device_state(26, 135)], baseline)
    assert result["recovered"] is True
    assert result["proof"] == "restart_count"


def test_probe_accepts_uptime_reset_without_counter(soak):
    """An uptime reset is proof when the counter is unavailable."""
    baseline = {"agent_restart_count": None, "agent_uptime_seconds": 410000}
    result = run_probe(soak, [device_state(None, 12)], baseline)
    assert result["recovered"] is True
    assert result["proof"] == "uptime_reset"


def test_probe_accepts_fresh_process_without_baseline(soak):
    """A few seconds of uptime is a new process even if the baseline was missed."""
    result = run_probe(soak, [device_state(None, 8)], {})
    assert result["recovered"] is True
    assert result["proof"] == "fresh"


def test_probe_reports_unverified_without_signals(soak, monkeypatch):
    """With nothing to compare the probe must not guess either way."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    result = run_probe(soak, [device_state(None, None)], {})
    assert result["recovered"] is False
    assert result["verified"] is False


def test_probe_not_fooled_by_old_agent_heartbeats(soak, monkeypatch):
    """A failed restart keeps heartbeating; that is still not a restart."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    baseline = {"agent_restart_count": 25, "agent_uptime_seconds": 410000}
    snapshots = [device_state(25, 410000 + i * 10) for i in range(30)]
    result = run_probe(soak, snapshots, baseline)
    assert result["recovered"] is False
    assert result["verified"] is True


# --- One command end to end --------------------------------------------------


class FakeClient:
    """API double covering queue, poll, history, audit and logs."""

    def __init__(self, mode="ok"):
        """Record the mode and start with an empty request log."""
        self.mode = mode
        self.posts = []

    def post(self, url, json=None):
        """Accept the command, unless the mode says it is rejected."""
        self.posts.append((url, json))
        if self.mode == "blocked":
            request = httpx.Request("POST", url)
            response = httpx.Response(
                403,
                request=request,
                json={"detail": {"missing_permissions": ["root_access"]}},
            )
            raise httpx.HTTPStatusError("forbidden", request=request, response=response)
        return FakeResponse({"command_id": "cmd-1", "status": "pending"})

    def get(self, url, params=None):
        """Serve the endpoints run_one uses."""
        if url.endswith("/error-logs"):
            return FakeResponse([])
        if url.endswith("/audit-logs"):
            action = (
                self.posts[-1][1].get("command_type")
                if self.posts
                else "list_processes"
            )
            return FakeResponse(audit_events(command_type=action, command_id="cmd-1"))
        if "/commands/cmd-1" in url:
            return FakeResponse(
                {
                    "command_id": "cmd-1",
                    "status": "completed",
                    "sent_at": iso(NOW),
                    "executed_at": iso(NOW + timedelta(seconds=1)),
                    "result": {"pid": 4242, "message": "program started"},
                }
            )
        if url.endswith("/commands"):
            return FakeResponse(
                [
                    {
                        "command_id": "cmd-1",
                        "status": "completed",
                        "result": {"pid": 4242},
                    }
                ]
            )
        raise AssertionError(f"unexpected GET {url}")


SOAK_ARGS = types.SimpleNamespace(poll_interval=0)


def test_run_one_happy_path_captures_pid(soak):
    """A completed command passes every check and records its pid."""
    state = {}
    spec = {
        "action": "start_program",
        "label": "Start Program",
        "payload": {"path": "ping.exe", "args": ["-n", "300", "127.0.0.1"]},
        "timeout": 2,
    }
    record = soak.run_one(FakeClient(), "http://x", "D", 1, spec, state, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_PASS
    assert record["checks"]["accepted"]
    assert record["checks"]["history"]
    assert record["checks"]["audit"]
    assert state["last_started_pid"] == 4242


def test_run_one_substitutes_captured_pid(soak):
    """stop_program targets the pid start_program returned, never a stray one."""
    client = FakeClient()
    spec = {
        "action": "stop_program",
        "label": "Stop",
        "payload": {"pid": "$PID", "force": False},
        "timeout": 2,
    }
    soak.run_one(
        client, "http://x", "D", 2, spec, {"last_started_pid": 4242}, SOAK_ARGS
    )
    assert client.posts[0][1]["payload"]["pid"] == 4242


def test_run_one_rejected_command_is_blocked(soak):
    """A 403 is a policy result with the reason kept for the report."""
    record = soak.run_one(
        FakeClient("blocked"),
        "http://x",
        "D",
        3,
        {
            "action": "install_program",
            "label": "Install",
            "payload": {"package": "X"},
            "timeout": 2,
        },
        {},
        SOAK_ARGS,
    )
    assert record["outcome"] == soak.OUTCOME_BLOCKED
    assert record["http_status"] == 403
    assert record["detail"] == {"missing_permissions": ["root_access"]}


def test_run_one_missing_pid_is_skipped(soak):
    """Without a captured pid the stop step is skipped, not guessed."""
    record = soak.run_one(
        FakeClient(),
        "http://x",
        "D",
        4,
        {
            "action": "stop_program",
            "label": "Stop",
            "payload": {"pid": "$PID"},
            "timeout": 2,
        },
        {},
        SOAK_ARGS,
    )
    assert record["outcome"] == soak.OUTCOME_SKIPPED


# --- Reporting ---------------------------------------------------------------


def test_new_record_has_every_field_the_report_reads(soak):
    """The record shape is shared by the run and skip paths.

    Both used to build this literal separately, so a field added to one was
    silently missing from the other.
    """
    record = soak.new_record(1, "list_drives", "List Drives", {})
    for key in (
        "index",
        "action",
        "label",
        "payload",
        "command_id",
        "status",
        "outcome",
        "checks",
        "verdict",
        "subtests",
        "timings",
        "new_errors",
        "notes",
        "result",
        "window",
    ):
        assert key in record
    assert set(record["checks"]) == {
        "accepted",
        "delivered",
        "executed",
        "result_shape",
        "history",
        "audit",
    }


def test_report_renders_without_records(soak, capsys):
    """An empty run prints the summary and says there is nothing to look at."""
    soak.print_report([], "D", 0.0)
    out = capsys.readouterr().out
    assert "COMPOSE SOAK TEST" in out
    assert "No failures to investigate" in out


def test_report_renders_a_skipped_command(soak, capsys):
    """A skipped command is listed, and not counted as a failure."""
    record = soak.new_record(1, "run_command", "Run Command", {"command": "whoami"})
    record["outcome"] = soak.OUTCOME_SKIPPED
    record["notes"].append("not run: agent did not come back")
    soak.print_report([record], "D", 1.0)
    out = capsys.readouterr().out
    assert "SKIPPED" in out
    assert "No failures to investigate" in out
