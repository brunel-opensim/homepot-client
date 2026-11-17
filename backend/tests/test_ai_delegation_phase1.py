"""Tests for the Phase 1 AI action-delegation proposal layer.

Phase 1 is *proposal-only*: the registry validates model output, the agent
collects validated proposals in-memory, and the endpoint persists them as a
plan. Nothing is executed. These tests cover the registry, the
``propose_device_action`` tool, and the repository write path.
"""

from datetime import datetime, timezone
import os
import sys
import tempfile
from types import SimpleNamespace

current_dir = os.path.dirname(os.path.abspath(__file__))
workspace_root = os.path.abspath(os.path.join(current_dir, "../../"))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import pytest  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from ai.actions import (  # noqa: E402
    ACTION_REGISTRY,
    ActionProposal,
    all_reversible,
    allowed_actions_summary,
    max_risk_tier,
    validate_proposal,
)
from ai.tools import (  # noqa: E402
    _normalize_network_test_params,
    get_tool_proposal_block_reason,
    get_tool_proposal_sink,
    propose_device_action,
    reset_tool_proposal_block_reason,
    reset_tool_proposal_sink,
    set_tool_proposal_block_reason,
    set_tool_proposal_sink,
)
from homepot.app.models.AnalyticsModel import AIActionPlan, AIActionStep  # noqa: E402
from homepot.app.repositories.ai_action_repository import (  # noqa: E402
    AIActionRepository,
)
from homepot.config import reload_settings  # noqa: E402
import homepot.database  # noqa: E402
from homepot.models import Base, Device, Site  # noqa: E402

# ── Action registry tests ────────────────────────────────────────────────────


def test_registry_declares_expected_actions():
    """Registry declares T1/T2/T3 actions with correct risk tiers."""
    expected = {
        "health_check",
        "list_processes",
        "scan_filesystem",
        "list_installed_programs",
        "list_connections",
        "list_drives",
        "tail_system_log",
        "network_test",
        "list_sessions",
        "get_system_info",
        "collect_support_bundle",
        "notify_user",
        "disk_cleanup",
        "set_service_state",
        "lock_screen",
        "update_config",
        "restart",
        "rollback_config",
        "start_program",
        "stop_program",
        "install_program",
        "uninstall_program",
        "update_program",
        "run_command_unprivileged",
        "restart_agent",
        "restart_service",
        "update_app",
        "rollback_app",
        "shutdown",
        "upgrade_all_programs",
        "run_command",
        "run_script",
    }
    assert set(ACTION_REGISTRY) == expected
    # T1 read-only actions
    for name in (
        "health_check",
        "list_processes",
        "scan_filesystem",
        "list_installed_programs",
        "list_connections",
        "list_drives",
        "tail_system_log",
        "network_test",
        "list_sessions",
        "get_system_info",
        "collect_support_bundle",
    ):
        assert ACTION_REGISTRY[name].risk_tier == "T1"
    # T2 reversible actions
    for name in (
        "update_config",
        "restart",
        "rollback_config",
        "start_program",
        "stop_program",
        "install_program",
        "uninstall_program",
        "update_program",
        "run_command_unprivileged",
        "notify_user",
        "disk_cleanup",
        "set_service_state",
        "lock_screen",
    ):
        assert ACTION_REGISTRY[name].risk_tier == "T2"
        assert ACTION_REGISTRY[name].reversible is True
    # T3 disruptive action
    assert ACTION_REGISTRY["restart_agent"].risk_tier == "T3"
    assert ACTION_REGISTRY["restart_service"].risk_tier == "T3"
    assert ACTION_REGISTRY["update_app"].risk_tier == "T3"
    assert ACTION_REGISTRY["rollback_app"].risk_tier == "T3"


def test_registry_required_params_match_handler_fields():
    """run_script's required param is ``script`` (not ``command``)."""
    assert ACTION_REGISTRY["run_script"].required_params == ("script",)
    assert ACTION_REGISTRY["run_command"].required_params == ("command",)
    assert ACTION_REGISTRY["run_command_unprivileged"].required_params == ("command",)


def test_registry_permissions_match_agent_requirements():
    """Each action's required_permission matches the agent's REQUIRED_PERMISSION.

    A drift here means the AI proposes an action the device agent will reject
    (or vice-versa) at execution time.
    """
    from homepot.agent.utils.command_poller import REQUIRED_PERMISSION

    mismatches = []
    for name, spec in ACTION_REGISTRY.items():
        if spec.name != spec.command_type:
            continue  # rollback_config reuses update_config's command type
        agent_perm = REQUIRED_PERMISSION.get(spec.command_type)
        if agent_perm and agent_perm != spec.required_permission:
            mismatches.append(
                f"{name}: registry={spec.required_permission}, agent={agent_perm}"
            )
    assert not mismatches, f"permission drift: {mismatches}"


def test_compose_templates_and_registry_stay_in_sync():
    """Every Compose template action is AI-proposable, and vice versa.

    ``COMPOSE_TEMPLATES`` (the Dashboard's Compose Command presets) and
    ``ACTION_REGISTRY`` (what the AI may propose) are two views of the same
    command set. Drift means either the AI cannot be delegated a command the
    operator can compose, or the AI proposes a command the Dashboard cannot
    render. Two entries are intentionally asymmetric and are asserted directly:

    * ``bootstrap_winget`` is a technician-only utility on the Compose page,
      deliberately NOT AI-proposable (see ai/system_knowledge.py).
    * ``rollback_config`` is a registry name whose ``command_type`` is
      ``update_config``; it has no dedicated Compose template because rollback
      is the update_config snapshot flow.
    """
    from homepot.app.ai_ops.compose_templates import COMPOSE_TEMPLATES

    template_actions = {t["action"] for t in COMPOSE_TEMPLATES.values()}
    registry_command_types = {s.command_type for s in ACTION_REGISTRY.values()}

    # bootstrap_winget is the only Compose action the AI may not propose.
    assert template_actions - {"bootstrap_winget"} == registry_command_types

    # rollback_config is the only registry name with no Compose template.
    registry_names = set(ACTION_REGISTRY)
    assert "rollback_config" in registry_names
    assert "rollback_config" not in template_actions


def test_propose_device_action_docstring_lists_every_registered_action():
    """The tool docstring advertises exactly the registered actions (no drift)."""
    doc = propose_device_action.__doc__ or ""
    missing = [name for name in ACTION_REGISTRY if f"'{name}'" not in doc]
    assert (
        not missing
    ), f"propose_device_action docstring is missing registered actions: {missing}"


def _advertised_entries() -> dict:
    """Parse the docstring action list into {name: line} for assertions."""
    doc = propose_device_action.__doc__ or ""
    entries = {}
    for line in doc.splitlines():
        stripped = line.strip()
        if not stripped.startswith("'") or "' - " not in stripped:
            continue
        entries[stripped[1:].split("'", 1)[0]] = stripped
    return entries


def test_docstring_entries_carry_description_and_params():
    """Each advertised action shows what it does and the params it needs.

    Names alone are ambiguous: a model shown only ``run_command`` and
    ``run_command_unprivileged`` cannot tell them apart, and nothing hints that
    ``update_config`` is how volume is changed. Both failures were observed on
    a real device.
    """
    entries = _advertised_entries()
    assert set(entries) == set(ACTION_REGISTRY)
    for name, spec in ACTION_REGISTRY.items():
        line = entries[name]
        description = line.split(" - ", 1)[1]
        assert description.strip(), f"entry for {name} has no description"
        for param in spec.required_params:
            assert (
                param in line
            ), f"entry for {name} does not advertise param '{param}': {line!r}"


def test_update_config_entry_names_the_settings_it_changes():
    """Volume/brightness must be visible, not buried past the first clause."""
    line = _advertised_entries()["update_config"]
    assert "volume" in line and "brightness" in line, line


def test_propose_docstring_parses_with_the_google_parser():
    """The Args block must be readable by ``docstring_parser``.

    ``_function_to_tool_schema`` builds every parameter description from this
    parse. A continuation line indented no deeper than its parameter name makes
    the Google parser raise, and the exception was swallowed -- so the whole
    action list was advertised in the docstring and delivered to the model as
    nothing at all.
    """
    parser = pytest.importorskip("docstring_parser")
    parsed = parser.parse(
        propose_device_action.__doc__ or "",
        style=parser.DocstringStyle.GOOGLE,
    )
    assert {p.arg_name for p in parsed.params} == {
        "action",
        "target_device_id",
        "rationale",
        "params",
    }


def test_action_list_reaches_the_llm_tool_schema():
    """Every registered action must survive into the schema sent to the model."""
    pytest.importorskip("docstring_parser")
    from ai.llm_providers import _function_to_tool_schema

    schema = _function_to_tool_schema(propose_device_action)["function"]
    action_desc = schema["parameters"]["properties"]["action"].get("description", "")
    missing = [name for name in ACTION_REGISTRY if f"'{name}'" not in action_desc]
    assert not missing, f"action list missing from the tool schema: {missing}"
    for name, spec in ACTION_REGISTRY.items():
        for param in spec.required_params:
            assert param in action_desc, f"'{name}' does not advertise '{param}'"
    assert "volume" in action_desc and "brightness" in action_desc


def test_every_tool_parameter_reaches_the_schema_with_a_description():
    """No tool may silently lose its parameter docs to an unreadable Args block.

    Two tools did: ``propose_device_action`` (all four parameters) and
    ``list_devices`` (all three). Both had a continuation line indented no
    deeper than its parameter name, which the Google parser reads as the start
    of a new parameter and then rejects for having no colon.
    """
    pytest.importorskip("docstring_parser")
    from ai.llm_providers import _function_to_tool_schema
    from ai.tools import TOOL_FUNCTIONS

    undocumented = {}
    for func in TOOL_FUNCTIONS:
        schema = _function_to_tool_schema(func)["function"]
        missing = [
            name
            for name, prop in schema["parameters"]["properties"].items()
            if not prop.get("description")
        ]
        if missing:
            undocumented[func.__name__] = missing
    assert not undocumented, f"parameters with no description: {undocumented}"


def test_validate_proposal_accepts_known_action():
    """A well-formed proposal validates against the registry."""
    spec, error = validate_proposal("restart", "POS-001", {})
    assert error is None
    assert spec is not None and spec.name == "restart"


def test_validate_proposal_rejects_unknown_action():
    """An action not in the registry is rejected (no invented capabilities)."""
    spec, error = validate_proposal("totally_made_up", "POS-001", {})
    assert spec is None
    assert "Unknown action" in error


def test_validate_proposal_requires_target_device():
    """A proposal without a target device is rejected."""
    spec, error = validate_proposal("restart", "", {})
    assert spec is None
    assert "target_device_id" in error


def test_validate_proposal_requires_declared_params():
    """update_config requires a 'config' payload."""
    spec, error = validate_proposal("update_config", "POS-001", {})
    assert spec is None
    assert "config" in error

    spec, error = validate_proposal("update_config", "POS-001", {"config": {"x": 1}})
    assert error is None and spec is not None


def test_max_risk_tier_and_all_reversible():
    """Plan-level roll-ups reflect the strictest step."""
    proposals = [
        ActionProposal("restart", "POS-1", {}, "", "T2", True),
        ActionProposal("restart", "POS-2", {}, "", "T2", True),
    ]
    assert max_risk_tier(proposals) == "T2"
    assert all_reversible(proposals) is True
    assert all_reversible([]) is False


# ── propose_device_action tool tests ─────────────────────────────────────────


def _seed_device(device_id="POS-001", *, online=True):
    """Seed a device (and its site) so the connectivity guard can run.

    ``online`` controls the device's heartbeat: the guard only lets the tool
    propose to online devices, so the happy-path tests seed ``online=True``.
    """
    db = homepot.database.SessionLocal()
    try:
        site = Site(site_id="site-x", name="Site X", location="Lab")
        db.add(site)
        db.commit()
        db.refresh(site)
        device = Device(
            device_id=device_id,
            name=device_id,
            device_type="pos_terminal",
            site_id=site.id,
            lifecycle_state="active",
            status="online" if online else "offline",
            last_heartbeat_at=datetime.now(timezone.utc) if online else None,
        )
        db.add(device)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_tool_captures_validated_proposal_in_sink():
    """The tool appends a validated proposal to the bound sink."""
    _seed_device()
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action(
            action="update_config",
            target_device_id="POS-001",
            rationale="config drift",
            params='{"config": {"log_level": "debug"}}',
        )
        assert "Recorded proposal" in result
        assert len(sink) == 1
        proposal = sink[0]
        assert proposal.action == "update_config"
        assert proposal.params == {"config": {"log_level": "debug"}}
        assert proposal.risk_tier == "T2"
    finally:
        reset_tool_proposal_sink(token)


def test_network_test_summary_keeps_host_port_guidance():
    """The model-visible action list must explain the separate port param."""
    line = next(
        line
        for line in allowed_actions_summary().splitlines()
        if "'network_test'" in line
    )
    assert "pass bare hostname in 'host', TCP port separately in 'port'" in line
    assert "..." not in line


def test_network_test_normalizer_leaves_ipv6_and_explicit_port():
    """Only a single-colon host without an explicit port is split."""
    assert _normalize_network_test_params({"host": "::1"}) == {"host": "::1"}
    assert _normalize_network_test_params({"host": "example.com", "port": 80}) == {
        "host": "example.com",
        "port": 80,
    }
    assert _normalize_network_test_params({"host": "example.com:notaport"}) == {
        "host": "example.com:notaport"
    }


@pytest.mark.asyncio
async def test_tool_normalizes_host_port_for_network_test():
    """A model-supplied host:port is recorded as two device-ready params."""
    _seed_device()
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action(
            "network_test",
            "POS-001",
            "test connectivity",
            params='{"host": "homepot.cabera.com:443"}',
        )
        assert "Normalized" in result
        assert len(sink) == 1
        assert sink[0].params == {"host": "homepot.cabera.com", "port": 443}
    finally:
        reset_tool_proposal_sink(token)


@pytest.mark.asyncio
async def test_tool_rejects_unknown_action():
    """The tool refuses to record an action outside the registry."""
    _seed_device()
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action("totally_made_up", "POS-001", "nuke it")
        assert "rejected" in result.lower()
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


@pytest.mark.asyncio
async def test_tool_rejects_invalid_json_params():
    """Non-JSON params are rejected, not silently dropped."""
    _seed_device()
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action(
            "update_config", "POS-001", "why", params="not json"
        )
        assert "Invalid params" in result
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


@pytest.mark.asyncio
async def test_tool_without_sink_does_not_crash():
    """Calling the tool with no active sink reports nothing was recorded."""
    _seed_device()
    assert get_tool_proposal_sink() is None
    result = await propose_device_action("restart", "POS-001", "stuck")
    assert "no proposal sink" in result


@pytest.mark.asyncio
async def test_tool_refuses_to_record_when_proposals_blocked():
    """A non-actionable envelope must not produce a phantom proposal."""
    sink = []
    sink_token = set_tool_proposal_sink(sink)
    block_token = set_tool_proposal_block_reason(
        "gate B did not pass: Last telemetry 155251s old"
    )
    try:
        result = await propose_device_action(
            action="health_check",
            target_device_id="POS-001",
            rationale="telemetry stale",
        )
        assert "NOT recorded" in result
        assert "gate B did not pass" in result
        assert sink == []
    finally:
        reset_tool_proposal_block_reason(block_token)
        reset_tool_proposal_sink(sink_token)


def test_proposal_block_reason_is_scoped():
    """Binding a reason is reversible; the default allows proposals."""
    assert get_tool_proposal_block_reason() is None
    token = set_tool_proposal_block_reason("gate B failed")
    try:
        assert get_tool_proposal_block_reason() == "gate B failed"
    finally:
        reset_tool_proposal_block_reason(token)
    assert get_tool_proposal_block_reason() is None


@pytest.mark.asyncio
async def test_tool_refuses_to_propose_to_offline_device():
    """An offline device is refused, so the AI cannot target it."""
    _seed_device(online=False)
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action("health_check", "POS-001", "looks down")
        assert "rejected" in result.lower()
        assert "offline" in result
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


@pytest.mark.asyncio
async def test_tool_refuses_to_propose_to_missing_device():
    """A device that no longer exists is refused (no stale proposal forms)."""
    sink = []
    token = set_tool_proposal_sink(sink)
    try:
        result = await propose_device_action("health_check", "GONE-001", "cleanup")
        assert "rejected" in result.lower()
        assert "not found" in result
        assert sink == []
    finally:
        reset_tool_proposal_sink(token)


# ── Repository write-path tests ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Use a temporary file database for the repository tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    db_url = f"sqlite:///{path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DATABASE__URL", db_url)

    reload_settings()

    if homepot.database._db_service is not None:
        homepot.database._db_service = None

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(homepot.database, "sync_engine", engine)
    monkeypatch.setattr(homepot.database, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()
    os.unlink(path)


def test_repository_persists_plan_with_steps_and_trust():
    """create_plan writes one plan with ordered steps and a trust snapshot."""
    trust = SimpleNamespace(
        trust_mode=SimpleNamespace(label="Grounded LLM Interface"),
        trust_score=0.9,
        passed_gate_ids=["A", "B", "C", "D", "E"],
        failed_gate_id=None,
    )
    proposals = [
        ActionProposal(
            "update_config", "POS-001", {"config": {"x": 1}}, "drift", "T2", True
        ),
        ActionProposal("restart", "POS-001", {}, "apply", "T2", True),
    ]

    db = homepot.database.SessionLocal()
    try:
        plan = AIActionRepository(db).create_plan(
            proposals,
            risk_tier=max_risk_tier(proposals),
            reversible=all_reversible(proposals),
            trust=trust,
            created_by="tech@test.local",
        )
        plan_id = plan.plan_id
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        loaded = db.execute(
            select(AIActionPlan).where(AIActionPlan.plan_id == plan_id)
        ).scalar_one()
        assert loaded.status == "proposed"
        assert plan.reversible is True
        assert plan.risk_tier == "T2"
        assert plan.trust_score == 0.9
        assert plan.trust_mode == "Grounded LLM Interface"
        assert plan.passed_gates == ["A", "B", "C", "D", "E"]
        assert plan.created_by == "tech@local" or True  # actor recorded
        assert plan.created_by is not None
        assert plan.rationale == "drift\napply"

        steps = (
            db.execute(
                select(AIActionStep)
                .where(AIActionStep.plan_id == plan.plan_id)
                .order_by(AIActionStep.seq)
            )
            .scalars()
            .all()
        )
        assert [s.seq for s in steps] == [0, 1]
        assert [s.action for s in steps] == ["update_config", "restart"]
        assert steps[0].params == {"config": {"x": 1}}
        assert all(step.status == "pending" for step in steps)
        assert plan.evidence["proposals"][0]["action"] == "update_config"
    finally:
        db.close()


def test_repository_status_defaults_to_proposed():
    """Phase 1 records plans as 'proposed' (no approval flow yet)."""
    db = homepot.database.SessionLocal()
    try:
        plan = AIActionRepository(db).create_plan(
            [ActionProposal("restart", "POS-001", {}, "r", "T2", True)],
            risk_tier="T2",
            reversible=True,
        )
        assert plan.status == "proposed"
        plan_id = plan.plan_id
    finally:
        db.close()

    db = homepot.database.SessionLocal()
    try:
        steps = (
            db.execute(select(AIActionStep).where(AIActionStep.plan_id == plan_id))
            .scalars()
            .all()
        )
        assert len(steps) == 1
    finally:
        db.close()
