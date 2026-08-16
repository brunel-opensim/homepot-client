"""Export metadata: calculation version, Git commit, and generation stamp."""

from datetime import datetime, timezone
import logging
import subprocess  # noqa: S404 - fixed argv; reads a local Git revision only

from homepot.kpi.models import ExportFilters

logger = logging.getLogger(__name__)

KPI_CALCULATION_VERSION = "1.0.0"
REPORT_TIMEZONE = "UTC"

KPI_UNITS = {
    "EQ-01": "%",
    "MW-01": "%",
    "MW-02": "seconds",
    "MW-03": "%",
    "MW-04": "%",
    "MW-05": "%",
    "PF-LAT": "ms",
}


def get_git_commit() -> str:
    """Return the short Git commit of the running tree, or ``"unknown"``.

    Used so a reviewer can pin every exported KPI value to a specific
    calculation code revision (roadmap §3.3).
    """
    try:
        result = subprocess.run(  # noqa: S603, S607 - fixed argv, no shell
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not read Git commit: %s", exc)
    return "unknown"


def build_manifest(filters: ExportFilters, provenance_scopes: list[str]) -> dict:
    """Build the export manifest dict.

    Includes the window, filters, timezone, calculation version, Git commit,
    and generation timestamp so every value resolves to a reproducible run.
    """
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": REPORT_TIMEZONE,
        "calculation_version": KPI_CALCULATION_VERSION,
        "git_commit": get_git_commit(),
        "units": KPI_UNITS,
        "provenance_scopes": provenance_scopes,
        "filters": {
            "start": filters.start.isoformat(),
            "end": filters.end.isoformat(),
            "site_id": filters.site_id,
            "device_id": filters.device_id,
            "device_type": filters.device_type,
            "provenance": filters.provenance,
        },
    }
