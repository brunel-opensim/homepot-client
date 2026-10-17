"""Background reconcile loop for AI action execution (Phase 3).

Execution is asynchronous: the executor queues device commands and the device
reports back later, so a background loop must advance ``executing`` /
``rolling_back`` plans to a terminal state once their commands finish.

This loop must be started by the process that actually serves the API
(``homepot.app.main``). It previously lived only in the legacy ``homepot.main``
module, which the deployed service never imports, so the verifier never ran in
production and plans stayed stuck in ``executing``.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

#: How often (seconds) to scan for plans that need reconciling.
AI_EXECUTION_RECONCILE_SECONDS = 10


async def run_ai_execution_reconcile_loop() -> None:
    """Advance AI action plans that are mid-execution.

    Runs forever; callers own the task lifecycle and should cancel it on
    shutdown.
    """
    from homepot.app.ai_ops.verifier import reconcile_plan
    from homepot.app.repositories.ai_action_repository import AIActionRepository
    from homepot.database import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                repo = AIActionRepository(db)
                plans = repo.list_plans(
                    statuses={"executing", "rolling_back"}, limit=100
                )
                for plan in plans:
                    try:
                        await reconcile_plan(db, plan)
                    except Exception:
                        logger.warning(
                            "Failed to reconcile AI plan %s",
                            plan.plan_id,
                            exc_info=True,
                        )
            finally:
                db.close()
        except Exception:
            logger.warning("AI execution reconcile loop failed", exc_info=True)
        await asyncio.sleep(AI_EXECUTION_RECONCILE_SECONDS)
