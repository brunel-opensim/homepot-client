"""Append-only submission-attempt log for the real device agent.

Each backend submission attempt is recorded as one JSON line so the
PF-01 telemetry-ingestion KPI can be computed by joining this log to the
backend ingestion log (attempted vs accepted submissions).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from homepot.agent.identity import identity_dir


def _default_log_path() -> Path:
    """Return the default submission log path inside the identity directory."""
    return identity_dir() / ".agent_submissions.jsonl"


class SubmissionLog:
    """Append-only JSONL log of agent submission attempts.

    Each record carries the submission timestamp, endpoint path, the
    payload's device sample timestamp (when present), the HTTP status, and
    whether the backend accepted the submission.
    """

    def __init__(self, log_path: Optional[Path] = None) -> None:
        """Initialize the log.

        Parameters
        ----------
        log_path:
            Path to the JSONL file.  Defaults to
            ``<identity_dir>/.agent_submissions.jsonl``.
        """
        self.path = log_path or _default_log_path()

    def append(
        self,
        *,
        endpoint: str,
        status_code: Optional[int],
        payload_timestamp: Optional[str] = None,
        accepted: Optional[bool] = None,
        retry_count: int = 0,
    ) -> None:
        """Record one submission attempt as a JSON line."""
        if accepted is None:
            accepted = bool(status_code is not None and 200 <= int(status_code) < 300)
        record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "payload_timestamp": payload_timestamp,
            "status_code": status_code,
            "accepted": accepted,
            "retry_count": retry_count,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def read_all(self) -> List[Dict[str, Any]]:
        """Read every recorded submission attempt."""
        if not self.path.exists():
            return []
        records: List[Dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return records

    def clear(self) -> None:
        """Remove the log file, dropping all recorded attempts."""
        if self.path.exists():
            self.path.unlink()
