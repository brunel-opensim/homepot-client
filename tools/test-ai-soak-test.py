"""Tests for tools/ai-soak-test.py.

The tool is a hyphenated script, not an importable module, so it is loaded by
path. Everything here is hermetic: the device, the AI and the API are fakes,
because a soak run must never be able to touch real hardware or the LLM from a
test suite.

These pin the behaviours that are easy to get wrong: gate failures must be
reported as BLOCKED (not FAIL), a wrong action must not be scored as a pass and
its persisted plan must be rejected, and a plan that reached ``succeeded``
without a verified outcome must not count.
"""

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

TOOL = Path(__file__).with_name("ai-soak-test.py")
NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def soak():
    """Load the AI soak script as a module."""
    spec = importlib.util.spec_from_file_location("ai_soak_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ai_soak_test"] = module
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


def test_readiness_missing_grants_are_named(soak):
    """Each missing grant is reported so the fix is obvious."""
    device = dict(
        DEVICE_OK,
        device_permissions={"root_access": False, "command_execution": True},
    )
    ready, problems, _ = soak.evaluate_readiness(device, soak.SOAK_COMMANDS)
    assert not ready
    assert any("root_access" in problem for problem in problems)


# --- Proposal parsing --------------------------------------------------------


def test_proposed_actions_extracts_step_actions(soak):
    """Distinct step actions are returned in order."""
    proposal = {
        "plan_id": "p1",
        "steps": [
            {"seq": 1, "action": "list_processes"},
            {"seq": 2, "action": "list_processes"},
        ],
    }
    assert soak.proposed_actions(proposal) == ["list_processes", "list_processes"]


def test_proposed_actions_ignores_malformed_steps(soak):
    """Non-dict steps and steps without an action are skipped."""
    proposal = {"steps": [None, {"seq": 1}, {"seq": 2, "action": "health_check"}]}
    assert soak.proposed_actions(proposal) == ["health_check"]


def test_proposal_from_response_missing(soak):
    """An absent proposal key yields an empty dict."""
    assert soak.proposal_from_response({}) == {}


# --- query_proposal ----------------------------------------------------------


def make_record(soak, action="list_processes"):
    """Build a minimal record the query path can mutate."""
    return soak.new_record(1, action, "List Processes", "List processes on {device}.")


class QueryClient:
    """Fake client serving only the AI query endpoint."""

    def __init__(self, payload):
        """Record the canned query response."""
        self.payload = payload

    def post(self, url, json=None, timeout=None):
        """Return the canned query response."""
        return FakeResponse(self.payload)


def test_query_proposal_gate_failure_is_blocked(soak):
    """A non-actionable query is a BLOCKED outcome with the gate named."""
    client = QueryClient({"trust": {"actionable": False, "failed_gate": "B"}})
    record = make_record(soak)
    proposal = soak.query_proposal(client, "http://x", "D", "q", record, 5, 0.0)
    assert proposal == {}
    assert record["outcome"] == soak.OUTCOME_BLOCKED
    assert record["gate_failure"] == "B"
    assert not record["checks"]["proposed"]


def test_query_proposal_no_proposal_is_failed(soak):
    """An actionable query that yields no proposal is a FAIL."""
    client = QueryClient(
        {"trust": {"actionable": True, "failed_gate": None}, "response": "nothing"}
    )
    record = make_record(soak)
    proposal = soak.query_proposal(client, "http://x", "D", "q", record, 5, 0.0)
    assert proposal == {}
    assert record["outcome"] == soak.OUTCOME_FAIL
    assert not record["checks"]["proposed"]


def test_query_proposal_records_action(soak):
    """A valid proposal marks the proposed check and returns the proposal."""
    proposal = {
        "plan_id": "p1",
        "steps": [{"seq": 1, "action": "list_processes"}],
    }
    client = QueryClient({"trust": {"actionable": True}, "proposal": proposal})
    record = make_record(soak)
    result = soak.query_proposal(client, "http://x", "D", "q", record, 5, 0.0)
    assert result == proposal
    assert record["checks"]["proposed"]
    assert record["proposed_actions"] == ["list_processes"]


def test_query_proposal_captures_provider_and_diagnostics(soak):
    """The provider, response text and tool calls are kept for diagnosis.

    These are what turn a "no proposal" failure into an explainable one: the
    tools_called list shows whether propose_device_action was attempted, and
    the response shows what the AI said instead.
    """
    proposal = {"plan_id": "p1", "steps": [{"seq": 1, "action": "list_processes"}]}
    resp = {
        "trust": {"actionable": True},
        "proposal": proposal,
        "provider": "anthropic",
        "response": "I recorded a proposal to list processes.",
        "agentic": {
            "tools_called": [{"tool": "propose_device_action", "iteration": 1}]
        },
    }
    client = QueryClient(resp)
    record = make_record(soak)
    soak.query_proposal(client, "http://x", "D", "q", record, 5, 0.0)
    assert record["provider"] == "anthropic"
    assert record["response"] == "I recorded a proposal to list processes."
    assert record["tools_called"] == [{"tool": "propose_device_action", "iteration": 1}]


# --- Outcome classification --------------------------------------------------


def make_classify_record(
    soak, action="list_processes", checks=None, plan_status="succeeded", errors=()
):
    """Build the parts of a record that classify_outcome reads."""
    names = (
        "proposed",
        "action_match",
        "persisted",
        "approved",
        "executed",
        "verified",
        "history",
        "audit",
    )
    wanted = names if checks is None else checks
    return {
        "action": action,
        "plan_status": plan_status,
        "new_errors": list(errors),
        "checks": {name: name in wanted for name in names},
    }


@pytest.mark.parametrize(
    "kwargs, timed_out, expected",
    [
        ({}, False, "PASS"),
        ({}, True, "TIMEOUT"),
        ({"checks": ("proposed",)}, False, "FAIL"),
        (
            {
                "checks": ("proposed", "action_match", "persisted", "approved"),
                "plan_status": "blocked",
            },
            False,
            "BLOCKED",
        ),
        (
            {
                "checks": (
                    "proposed",
                    "action_match",
                    "persisted",
                    "approved",
                    "executed",
                ),
                "plan_status": "failed",
            },
            False,
            "FAIL",
        ),
        ({"errors": ("2026-11-15T15:00:00|E1|boom",)}, False, "PASS_NOTE"),
    ],
)
def test_classify_outcome(soak, kwargs, timed_out, expected):
    """Outcomes map to the documented categories."""
    kwargs.setdefault("action", "list_processes")
    record = make_classify_record(soak, **kwargs)
    assert soak.classify_outcome(record, timed_out) == expected


# --- One command end to end --------------------------------------------------


def terminal_plan():
    """Build a serialized plan that has succeeded and verified."""
    return {
        "plan_id": "p1",
        "status": "succeeded",
        "steps": [
            {
                "step_id": "s1",
                "seq": 1,
                "action": "list_processes",
                "target_device_id": "D",
                "status": "done",
                "approval_required": False,
                "command_id": "cmd-1",
            }
        ],
        "outcome": {"verified": True, "rolled_back": False},
    }


def audit_events(command_type="list_processes", command_id="cmd-1"):
    """Build the full audit trail an AI-dispatched command now writes."""
    return [
        {
            "event_type": "command_queued",
            "description": (
                f"AI plan 'p-1' queued {command_type} command '{command_id}' "
                "for device 'D'"
            ),
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


def test_verify_audit_ok_with_full_lifecycle(soak):
    """Queued, sent and terminal events all verify the AI command path."""
    result = soak.verify_audit(
        audit_events(),
        "cmd-1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert result["ok"]
    assert result["queued"] and result["sent"] and result["terminal"]


def test_verify_audit_requires_queued_event(soak):
    """A missing command_queued event is no longer accepted."""
    result = soak.verify_audit(
        audit_events()[1:],
        "cmd-1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert not result["ok"]
    assert not result["queued"]
    assert result["sent"] and result["terminal"]


def test_verify_audit_requires_terminal_event(soak):
    """A trail that stops at 'sent' is incomplete."""
    result = soak.verify_audit(
        audit_events()[:2],
        "cmd-1",
        "list_processes",
        NOW,
        NOW + timedelta(seconds=5),
        True,
        True,
    )
    assert not result["ok"]
    assert result["queued"] and result["sent"]
    assert not result["terminal"]


class ProviderClient:
    """Fake client serving the /ai/provider GET and PUT endpoints."""

    def __init__(self, current="ollama", model="llama3.2"):
        """Record the current provider/model and any switch request."""
        self.current = current
        self.model = model
        self.switched = None

    def get(self, url, params=None):
        """Return the current provider info."""
        return FakeResponse(
            {
                "status": "success",
                "data": {"current": self.current, "model": self.model},
            }
        )

    def put(self, url, params=None):
        """Record the switch and return the updated provider info."""
        self.switched = (params or {}).get("provider")
        self.current = self.switched or self.current
        if self.switched == "anthropic":
            self.model = "claude-haiku-4-5"
        return FakeResponse(
            {
                "status": "success",
                "data": {"current": self.current, "model": self.model},
            }
        )


def test_resolve_provider_switches_when_requested(soak):
    """A --provider that differs switches the server and reports the new model."""
    client = ProviderClient(current="ollama")
    provider, model = soak.resolve_provider(client, "http://x", "anthropic")
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5"
    assert client.switched == "anthropic"


def test_resolve_provider_records_without_switch(soak):
    """Omitting --provider records the active provider without a switch."""
    client = ProviderClient(current="anthropic", model="claude-haiku-4-5")
    provider, model = soak.resolve_provider(client, "http://x", None)
    assert provider == "anthropic"
    assert model == "claude-haiku-4-5"
    assert client.switched is None


class FakeClient:
    """API double covering query, plan, reject, approve, execute and verification."""

    def __init__(self, query=None, plan_status="pending_approval", reject_error=None):
        """Record the query response, first plan status and reject failure."""
        self.query = query or {
            "trust": {"actionable": True},
            "proposal": {
                "plan_id": "p1",
                "steps": [{"seq": 1, "action": "list_processes"}],
            },
        }
        self.plan_status = plan_status
        self.reject_error = reject_error
        self.plan_gets = 0
        self.posts = []

    def post(self, url, json=None, timeout=None):
        """Serve the AI query, decision, step-approve and execute endpoints."""
        self.posts.append((url, json))
        if url.endswith("/ai/query"):
            return FakeResponse(self.query)
        if url.endswith("/reject") and self.reject_error is not None:
            raise self.reject_error
        return FakeResponse({})

    def get(self, url, params=None):
        """Serve plan polling and the verification endpoints."""
        if url.endswith("/error-logs"):
            return FakeResponse([])
        if url.endswith("/audit-logs"):
            return FakeResponse(audit_events(command_id="cmd-1"))
        if url.endswith("/commands"):
            return FakeResponse(
                [{"command_id": "cmd-1", "status": "completed", "result": {"count": 1}}]
            )
        if "/ai/action-plans/" in url:
            self.plan_gets += 1
            if self.plan_gets == 1 and self.plan_status != "succeeded":
                return FakeResponse(
                    {
                        "plan_id": "p1",
                        "status": self.plan_status,
                        "steps": [
                            {
                                "step_id": "s1",
                                "seq": 1,
                                "action": "list_processes",
                                "approval_required": False,
                                "status": "pending",
                            }
                        ],
                    }
                )
            return FakeResponse(terminal_plan())
        raise AssertionError(f"unexpected GET {url}")


SOAK_ARGS = types.SimpleNamespace(poll_interval=0, query_timeout=5)


def test_run_one_happy_path(soak):
    """A full propose -> approve -> execute -> verify loop passes every check."""
    client = FakeClient()
    spec = {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 2,
    }
    record = soak.run_one(client, "http://x", "D", 1, spec, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_PASS
    assert record["plan_id"] == "p1"
    assert record["checks"]["proposed"]
    assert record["checks"]["action_match"]
    assert record["checks"]["verified"]
    assert record["checks"]["history"]
    assert record["checks"]["audit"]


def test_run_one_gate_blocked(soak):
    """A non-actionable query stops the run with BLOCKED, not a device failure."""
    client = FakeClient(query={"trust": {"actionable": False, "failed_gate": "B"}})
    spec = {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 2,
    }
    record = soak.run_one(client, "http://x", "D", 1, spec, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_BLOCKED
    assert record["gate_failure"] == "B"


def test_run_one_wrong_action_is_failed_and_rejected(soak):
    """A wrong action is a FAIL and its persisted plan is rejected, not executed."""
    client = FakeClient(
        query={
            "trust": {"actionable": True},
            "proposal": {
                "plan_id": "p1",
                "steps": [{"seq": 1, "action": "run_command"}],
            },
        }
    )
    spec = {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 2,
    }
    record = soak.run_one(client, "http://x", "D", 1, spec, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_FAIL
    assert not record["checks"]["action_match"]
    assert record["plan_id"] == "p1"
    assert record["checks"]["persisted"]
    assert record["rejected_plan"]["ok"] is True
    assert "run_command" in record["rejected_plan"]["reason"]

    reject_posts = [post for post in client.posts if post[0].endswith("/reject")]
    assert len(reject_posts) == 1
    assert reject_posts[0][0].endswith("/ai/action-plans/p1/reject")
    assert "run_command" in reject_posts[0][1]["reason"]
    assert not any("/approve" in url or "/execute" in url for url, _ in client.posts)


def test_run_one_wrong_action_reject_failure_is_recorded(soak):
    """A failed reject call is recorded but never turns the command into a pass."""
    client = FakeClient(
        query={
            "trust": {"actionable": True},
            "proposal": {
                "plan_id": "p1",
                "steps": [{"seq": 1, "action": "run_command"}],
            },
        },
        reject_error=RuntimeError("reject unavailable"),
    )
    spec = {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 2,
    }
    record = soak.run_one(client, "http://x", "D", 1, spec, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_FAIL
    assert record["rejected_plan"]["ok"] is False
    assert "reject unavailable" in record["rejected_plan"]["error"]
    assert any("could not reject mismatched plan" in note for note in record["notes"])
    assert not record["checks"]["approved"]


def test_run_one_missing_plan_id_is_failed(soak):
    """A proposal with no plan_id cannot proceed and is reported."""
    client = FakeClient(
        query={
            "trust": {"actionable": True},
            "proposal": {
                "plan_id": None,
                "steps": [{"seq": 1, "action": "list_processes"}],
            },
        }
    )
    spec = {
        "action": "list_processes",
        "label": "List Processes",
        "prompt": "List the running processes on the device {device}.",
        "timeout": 2,
    }
    record = soak.run_one(client, "http://x", "D", 1, spec, SOAK_ARGS)
    assert record["outcome"] == soak.OUTCOME_FAIL
    assert not record["checks"]["persisted"]
    assert record["rejected_plan"] is None
    assert not any(url.endswith("/reject") for url, _ in client.posts)


# --- Reporting ---------------------------------------------------------------


def test_new_record_has_every_field_the_report_reads(soak):
    """The record shape is shared by the run and skip paths."""
    record = soak.new_record(1, "list_processes", "List Processes", "prompt")
    for key in (
        "index",
        "action",
        "label",
        "prompt",
        "plan_id",
        "plan_status",
        "rejected_plan",
        "outcome",
        "checks",
        "proposed_actions",
        "trust",
        "gate_failure",
        "provider",
        "response",
        "tools_called",
        "step_approvals",
        "steps",
        "outcome_detail",
        "command_id",
        "timings",
        "new_errors",
        "notes",
        "window",
    ):
        assert key in record
    assert set(record["checks"]) == {
        "proposed",
        "action_match",
        "persisted",
        "approved",
        "executed",
        "verified",
        "history",
        "audit",
    }


def test_report_renders_without_records(soak, capsys):
    """An empty run prints the summary and says there is nothing to look at."""
    soak.print_report([], "D", 0.0)
    out = capsys.readouterr().out
    assert "AI DELEGATION SOAK TEST" in out
    assert "No failures to investigate" in out


def test_report_renders_a_skipped_command(soak, capsys):
    """A skipped command is listed, and not counted as a failure."""
    record = soak.new_record(1, "list_processes", "List Processes", "prompt")
    record["outcome"] = soak.OUTCOME_SKIPPED
    record["notes"].append("not run: agent did not come back")
    soak.print_report([record], "D", 1.0)
    out = capsys.readouterr().out
    assert "SKIPPED" in out
    assert "No failures to investigate" in out
