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
