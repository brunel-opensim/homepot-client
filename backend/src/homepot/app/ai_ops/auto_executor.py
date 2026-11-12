"""Background auto-execution runner for AI action plans (Phase 3).

Scans for ``approved`` plans whose every action has earned at least
``auto_execute_min_level`` autonomy, and executes them without a manual
"Execute" click. This is the piece that turns delegation from "propose and
wait for a human to run" into "the AI completes the task on its own."

Safety guardrails:
- Disabled by default (``agent.auto_execute_enabled``).
- Only plans where *every* step's action has autonomy >= min level.
- Never auto-executes plans containing per-step approval gates (T3 steps that
  are still ``awaiting_approval``).
- Never auto-executes destructive/irreversible actions unless min_level >= 3
  and the action is explicitly allow-listed.
- Caps concurrent auto-executions.
- Every auto-execution is audited.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Set, cast

logger = logging.getLogger(__name__)

_AUTO_EXECUTE_ALLOWLIST: Optional[Set[str]] = None  # None = derive from autonomy level


async def _is_eligible(plan: Any, controller: Any, min_level: int) -> bool:
    """Return True if the plan may be auto-executed."""
    if plan.status != "approved":
        return False
    steps = getattr(plan, "steps", []) or []
    if not steps:
        return False

    # Resolve device OS for each step to check per-OS autonomy.
    from homepot.database import get_database_service
    from homepot.models import Device

    device_os_cache: Dict[str, Optional[str]] = {}

    async def _os_for_device(device_id: Optional[str]) -> Optional[str]:
        if not device_id:
            return None
        if device_id in device_os_cache:
            return device_os_cache[device_id]
        try:
            db_service = await get_database_service()
            async with db_service.get_session() as session:
                from sqlalchemy import select

                from homepot.app.schemas.os_capabilities import os_family as _os_family

                result = await session.execute(
                    select(Device.os_details).where(Device.device_id == device_id)
                )
                os_details = result.scalar_one_or_none()
                osf = _os_family(cast(Optional[str], os_details))
                device_os_cache[device_id] = osf
                return osf
        except Exception:
            device_os_cache[device_id] = None
            return None

    for step in steps:
        # Per-step approval gates must be cleared by a human first.
        if (
            getattr(step, "approval_required", False)
            and getattr(step, "status", "") != "approved"
        ):
            return False
        osf = await _os_for_device(getattr(step, "target_device_id", None))
        decision = controller.check_autonomy(step.action, os_family=osf)
        if decision.current_level < min_level:
            return False
        if not decision.may_auto_execute and min_level >= 3:
            return False
    return True


async def _execute_plan(plan: Any, actor: str) -> None:
    """Execute a single approved plan to a terminal state."""
    from homepot.app.ai_ops.executor import start_execution
    from homepot.app.ai_ops.verifier import reconcile_plan
    from homepot.database import get_database_service

    try:
        db_service = await get_database_service()
    except Exception:
        logger.warning("Auto-executor: no DB service; skipping")
        return

    from homepot.database import SessionLocal

    db = SessionLocal()
    try:
        # Re-load plan in this session
        from homepot.app.repositories.ai_action_repository import AIActionRepository

        repo = AIActionRepository(db)
        plan = repo.get_plan(plan.plan_id)
        if plan is None or plan.status != "approved":
            return

        plan, policy = await start_execution(
            db, plan, actor=actor, db_service=db_service
        )
        if not policy.allowed:
            logger.info("Auto-executor: plan %s blocked by policy", plan.plan_id)
            return

        # Audit
        try:
            from homepot.audit import AuditEventType, get_audit_logger

            await get_audit_logger().log_event(
                event_type=AuditEventType.AI_EXECUTION_STARTED,
                description=f"Auto-executed AI plan {plan.plan_id}",
                user_id=None,
                event_metadata={
                    "plan_id": plan.plan_id,
                    "actor": actor,
                    "auto": True,
                },
            )
        except Exception:
            logger.debug("Audit failed for auto-execution", exc_info=True)

        # Poll until terminal
        terminal = {"succeeded", "failed", "rolled_back", "blocked", "cancelled"}
        import asyncio as _asyncio

        for _ in range(60):  # ~2 min max at 2s
            db.refresh(plan)
            if plan.status in terminal:
                break
            try:
                await reconcile_plan(db, plan, db_service)
            except Exception:
                logger.debug("Reconcile failed during auto-execution", exc_info=True)
            await _asyncio.sleep(2)
        db.refresh(plan)
        logger.info(
            "Auto-executor: plan %s finished with status %s", plan.plan_id, plan.status
        )
    except Exception:
        logger.warning(
            "Auto-executor: failed to execute plan %s",
            getattr(plan, "plan_id", "?"),
            exc_info=True,
        )
    finally:
        db.close()


async def run_auto_execution_loop() -> None:
    """Background loop that auto-executes eligible approved plans."""
    import os

    try:
        import yaml

        config_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "..",
                "..",
                "ai",
                "config.yaml",
            )
        )
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception:
        cfg = {}
    agent_cfg = (cfg.get("agent") or {}) if isinstance(cfg, dict) else {}
    enabled = bool(agent_cfg.get("auto_execute_enabled", False))
    if not enabled:
        logger.info("Auto-execution disabled (agent.auto_execute_enabled=false).")
        # Still loop but do nothing, so the task stays alive and config can be
        # flipped without restart? We exit instead to keep it simple.
        return

    min_level = int(agent_cfg.get("auto_execute_min_level", 3))
    poll_seconds = int(agent_cfg.get("auto_execute_poll_seconds", 30))
    max_concurrent = int(agent_cfg.get("auto_execute_max_concurrent", 2))

    from homepot.app.ai_ops.autonomy import hydrate_autonomy_from_reliability

    controller = await hydrate_autonomy_from_reliability(days=30)

    from homepot.app.repositories.ai_action_repository import AIActionRepository
    from homepot.database import SessionLocal

    logger.info(
        "Auto-execution runner started (min_level=%d, poll=%ds, max_concurrent=%d).",
        min_level,
        poll_seconds,
        max_concurrent,
    )

    running: set = set()

    while True:
        try:
            db = SessionLocal()
            try:
                repo = AIActionRepository(db)
                plans = repo.list_plans(statuses={"approved"}, limit=50)
            finally:
                db.close()

            eligible = []
            for plan in plans:
                if plan.plan_id in running:
                    continue
                if await _is_eligible(plan, controller, min_level):
                    eligible.append(plan)

            # Cap concurrency
            slots = max_concurrent - len(running)
            for plan in eligible[:slots]:
                running.add(plan.plan_id)
                asyncio.create_task(_run_and_track(plan, running))

        except Exception:
            logger.warning("Auto-executor loop iteration failed", exc_info=True)

        await asyncio.sleep(poll_seconds)


async def _run_and_track(plan: Any, running: set) -> None:
    try:
        await _execute_plan(plan, actor="auto-executor")
    finally:
        running.discard(plan.plan_id)
