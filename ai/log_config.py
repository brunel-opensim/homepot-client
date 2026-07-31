"""Centralized logging configuration for the AI package.

Adds a rotating file handler to the ``ai`` logger tree. Console output is
handled by the backend's root-logger handlers (via propagation), avoiding
duplicate stdout lines.

Mirrors the backend's approach (``backend/src/homepot/agent/utils/log_setup.py``).
Idempotent — only the first call applies config.
"""

import logging
import logging.handlers
import os
import tempfile

_LOG_CONFIGURED = False


def configure_ai_logging(
    log_dir: str | None = None,
    log_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Set up rotating file logging for the ``ai`` logger tree.

    Call once at import time from ``ai/__init__.py``. Subsequent calls are
    no-ops.  Console output is inherited through the root logger — we do not
    add a ``StreamHandler`` here to avoid double-printing.

    If the configured ``log_dir`` is not writable (e.g. inside a Docker
    container running as a non-root user), falls back to a temp directory.
    If that also fails, file logging is skipped entirely — logs still reach
    the console via root-logger propagation.
    """
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return
    _LOG_CONFIGURED = True

    if log_dir is None:
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))

    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_dir = os.path.join(tempfile.gettempdir(), "homepot-ai-logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            return  # cannot write anywhere — skip file logging

    log_file = os.path.join(log_dir, "ai.log")
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError:
        return  # cannot open log file — skip file logging

    file_handler.setFormatter(fmt)
    file_handler.setLevel(log_level)

    ai_logger = logging.getLogger("ai")
    ai_logger.setLevel(log_level)
    ai_logger.addHandler(file_handler)
