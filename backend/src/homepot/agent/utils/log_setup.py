"""Centralised logging setup with log rotation for the real device agent.

On Windows, supports optional Windows EventLog integration via
``pywin32`` (``servicemanager.LogMsg``).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Any, Dict, Optional

_LOG_CONFIGURED = False

_DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
_DEFAULT_BACKUP_COUNT = 5


def configure_agent_logging(
    *,
    log_file: Optional[str] = None,
    log_level: int = logging.INFO,
    log_format: str = _DEFAULT_FORMAT,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
    use_eventlog: bool = False,
) -> None:
    """Configure the root logger with a rotating file handler and a stream handler.

    On Windows, when *use_eventlog* is ``True`` and ``pywin32`` is available,
    a ``NTEventLogHandler`` is added so log records are visible in the Windows
    Event Viewer.

    This function is idempotent — only the first call configures the logger.
    """
    global _LOG_CONFIGURED
    if _LOG_CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(log_level)

    formatter = logging.Formatter(log_format)

    # Always add a stream handler (stdout / journald)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    # Optional rotating file handler
    if log_file:
        path = Path(log_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                str(path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            logging.getLogger(__name__).warning(
                "Failed to configure log file %s: %s", log_file, exc
            )

    # Optional Windows EventLog handler
    if use_eventlog and sys.platform == "win32":
        _add_eventlog_handler(root, formatter)

    _LOG_CONFIGURED = True
    logging.getLogger(__name__).info(
        "Logging configured (level=%s, file=%s, max_bytes=%s, backup_count=%s, eventlog=%s)",
        logging.getLevelName(log_level),
        log_file or "(none)",
        max_bytes,
        backup_count,
        use_eventlog,
    )


def _add_eventlog_handler(root: logging.Logger, formatter: logging.Formatter) -> None:
    """Add a ``NTEventLogHandler`` to the root logger.

    Falls back silently if pywin32 is not installed.
    """
    try:
        from logging.handlers import NTEventLogHandler

        eventlog_handler = NTEventLogHandler(
            "HOMEPOT Agent",
            logtype="Application",
        )
        eventlog_handler.setFormatter(formatter)
        root.addHandler(eventlog_handler)
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to add EventLog handler: %s", exc)


def logging_config_from_config(
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract logging-related configuration values from agent config.

    Reads the following optional keys:

    * ``log_file`` — path to the rotating log file (default: ``None``)
    * ``log_level`` — string log level name (default: ``"INFO"``)
    * ``log_max_bytes`` — max size per log file before rotation (default: 10 MiB)
    * ``log_backup_count`` — number of rotated log files to keep (default: 5)
    * ``use_eventlog`` — enable Windows EventLog output (default: ``False``)
    """
    return {
        "log_file": config.get("log_file"),
        "log_level": _parse_log_level(config.get("log_level", "INFO")),
        "log_format": config.get("log_format", _DEFAULT_FORMAT),
        "max_bytes": int(config.get("log_max_bytes", _DEFAULT_MAX_BYTES)),
        "backup_count": int(config.get("log_backup_count", _DEFAULT_BACKUP_COUNT)),
        "use_eventlog": bool(config.get("use_eventlog", False)),
    }


def _parse_log_level(name: str) -> int:
    """Convert a log level name to its numeric value, defaulting to INFO."""
    level = getattr(logging, name.upper(), None)
    if isinstance(level, int):
        return level
    return logging.INFO


def reset_logging_config() -> None:
    """Allow re-configuration in tests.  Not intended for production use."""
    global _LOG_CONFIGURED
    _LOG_CONFIGURED = False
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
