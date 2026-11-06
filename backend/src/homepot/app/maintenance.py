"""Background maintenance loops for the API process.

These are long-running tasks started (and cancelled) by ``homepot.app.main``.
They must run in the process that actually serves the API — the same reason the
AI reconcile loop lives in :mod:`homepot.app.ai_ops.reconcile` rather than the
legacy ``homepot.main`` module.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

#: How often (seconds) to attempt trimming old ``api_request_logs`` rows.
API_REQUEST_LOG_RETENTION_INTERVAL_SECONDS = 6 * 60 * 60  # every 6 hours


#: How often (seconds) to attempt trimming old ``error_logs`` rows.
ERROR_LOG_RETENTION_INTERVAL_SECONDS = 6 * 60 * 60  # every 6 hours


async def run_error_log_retention_loop() -> None:
    """Trim ``error_logs`` past the configured retention window.

    ``error_logs`` stores device status reports (every 30 s) and is
    high-volume; the User App only surfaces the latest few entries. This
    loop trims rows older than the configured retention (default 7 days) in
    bounded batches. A retention setting of 0 disables trimming.
    """
    from homepot.config import get_settings
    from homepot.database import get_database_service

    while True:
        try:
            retention_days = get_settings().database.error_log_retention_days
            if retention_days and retention_days > 0:
                db = await get_database_service()
                deleted = await db.delete_old_error_logs(retention_days=retention_days)
                if deleted:
                    logger.info(
                        "Trimmed %d stale error_logs row(s) (retention=%d days)",
                        deleted,
                        retention_days,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Error log retention pass failed: %s", e)
        await asyncio.sleep(ERROR_LOG_RETENTION_INTERVAL_SECONDS)


#: How often (seconds) to attempt trimming old ``device_metrics`` rows.
DEVICE_METRICS_RETENTION_INTERVAL_SECONDS = 6 * 60 * 60  # every 6 hours


async def run_device_metrics_retention_loop() -> None:
    """Trim ``device_metrics`` past the configured retention window.

    Runs forever; callers own the task lifecycle and should cancel it on
    shutdown. Each pass deletes only rows older than the configured retention
    (default 30 days), in bounded batches, so it never blocks request traffic.
    A retention setting of 0 disables trimming.
    """
    from homepot.config import get_settings
    from homepot.database import get_database_service

    while True:
        try:
            retention_days = get_settings().database.device_metrics_retention_days
            if retention_days and retention_days > 0:
                db = await get_database_service()
                deleted = await db.delete_old_device_metrics(
                    retention_days=retention_days
                )
                if deleted:
                    logger.info(
                        "Trimmed %d stale device_metrics row(s) (retention=%d days)",
                        deleted,
                        retention_days,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Device metrics retention pass failed: %s", e)
        await asyncio.sleep(DEVICE_METRICS_RETENTION_INTERVAL_SECONDS)


async def run_api_request_log_retention_loop() -> None:
    """Trim ``api_request_logs`` past the configured retention window.

    Runs forever; callers own the task lifecycle and should cancel it on
    shutdown. Each pass deletes only rows older than the configured retention
    (default 30 days), in bounded batches, so it never blocks request traffic.
    A retention setting of 0 disables trimming.
    """
    from homepot.config import get_settings
    from homepot.database import get_database_service

    while True:
        try:
            retention_days = get_settings().database.api_request_log_retention_days
            if retention_days and retention_days > 0:
                db = await get_database_service()
                deleted = await db.delete_old_api_request_logs(
                    retention_days=retention_days
                )
                if deleted:
                    logger.info(
                        "Trimmed %d stale api_request_logs row(s) (retention=%d days)",
                        deleted,
                        retention_days,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("API request log retention pass failed: %s", e)
        await asyncio.sleep(API_REQUEST_LOG_RETENTION_INTERVAL_SECONDS)


#: How often (seconds) to attempt archiving old AI action plans.
AI_PLAN_RETENTION_INTERVAL_SECONDS = 24 * 60 * 60  # every 24 hours


async def run_ai_plan_retention_loop() -> None:
    """Soft-archive AI action plans past the configured retention window.

    Terminal plans (succeeded, failed, rolled_back, cancelled, rejected,
    blocked, expired) older than the configured retention (default 90 days)
    are soft-archived (archived_at set) so they stay in the DB for
    reliability metrics but are hidden from the default list/summary. A
    retention setting of 0 disables archiving.

    Runs forever; callers own the task lifecycle and should cancel on
    shutdown.
    """
    import asyncio as _asyncio

    from homepot.config import get_settings
    from homepot.database import SessionLocal

    while True:
        try:
            retention_days = getattr(
                get_settings().database, "ai_plan_retention_days", 90
            )
            if retention_days and retention_days > 0:
                db = SessionLocal()
                try:
                    from homepot.app.repositories.ai_action_repository import (
                        AIActionRepository,
                    )

                    repo = AIActionRepository(db)
                    archived = repo.archive_old_plans(days=retention_days)
                    if archived:
                        logger.info(
                            "Archived %d old AI action plan(s) (retention=%d days)",
                            archived,
                            retention_days,
                        )
                finally:
                    db.close()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("AI plan retention pass failed: %s", e)
        await _asyncio.sleep(AI_PLAN_RETENTION_INTERVAL_SECONDS)
