"""Real-time dashboard for HOMEPOT data collection."""

import asyncio
import os
from pathlib import Path
import sys
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlalchemy import text

from homepot.database import get_database_service

console = Console()


async def get_counts():
    """Fetch current record counts from the database."""
    try:
        db = await get_database_service()
        async with db.get_session() as session:
            metrics = await session.execute(text("SELECT COUNT(*) FROM device_metrics"))
            logs = await session.execute(text("SELECT COUNT(*) FROM api_request_logs"))
            errors = await session.execute(text("SELECT COUNT(*) FROM error_logs"))
            user_activity = await session.execute(
                text("SELECT COUNT(*) FROM user_activities")
            )
            job_outcomes = await session.execute(
                text("SELECT COUNT(*) FROM job_outcomes")
            )
            config_history = await session.execute(
                text("SELECT COUNT(*) FROM configuration_history")
            )

            return {
                "metrics": metrics.scalar(),
                "logs": logs.scalar(),
                "errors": errors.scalar(),
                "user_activity": user_activity.scalar(),
                "job_outcomes": job_outcomes.scalar(),
                "config_history": config_history.scalar(),
            }
    except Exception:
        return {
            "metrics": 0,
            "logs": 0,
            "errors": 0,
            "user_activity": 0,
            "job_outcomes": 0,
            "config_history": 0,
        }


def generate_layout(counts, start_time, log_line, initial_counts):
    """Generate the dashboard layout with current statistics."""
    elapsed = time.time() - start_time

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )

    # Header
    header_text = Text(
        f"HOMEPOT Data Collection Dashboard",
        style="bold white on blue",
        justify="center",
    )
    layout["header"].update(Panel(header_text, style="blue"))

    # Body - Stats Table
    table = Table(expand=True, border_style="dim")
    table.add_column("Metric", style="cyan")
    table.add_column("Total Count", style="magenta", justify="right")
    table.add_column("New (Session)", style="green", justify="right")
    table.add_column("Rate (per min)", style="yellow", justify="right")

    # Calculate deltas
    new_metrics = counts["metrics"] - initial_counts.get("metrics", 0)
    new_logs = counts["logs"] - initial_counts.get("logs", 0)
    new_errors = counts["errors"] - initial_counts.get("errors", 0)
    new_ua = counts["user_activity"] - initial_counts.get("user_activity", 0)
    new_jobs = counts["job_outcomes"] - initial_counts.get("job_outcomes", 0)
    new_config = counts["config_history"] - initial_counts.get("config_history", 0)

    mins = elapsed / 60 if elapsed > 0 else 1
    rate_metrics = int(new_metrics / mins)
    rate_logs = int(new_logs / mins)
    rate_errors = int(new_errors / mins)
    rate_ua = int(new_ua / mins)
    rate_jobs = int(new_jobs / mins)
    rate_config = int(new_config / mins)

    table.add_row(
        "Device Metrics", str(counts["metrics"]), f"+{new_metrics}", str(rate_metrics)
    )
    table.add_row(
        "API Request Logs", str(counts["logs"]), f"+{new_logs}", str(rate_logs)
    )
    table.add_row(
        "Error Logs", str(counts["errors"]), f"+{new_errors}", str(rate_errors)
    )
    table.add_row(
        "User Activity", str(counts["user_activity"]), f"+{new_ua}", str(rate_ua)
    )
    table.add_row(
        "Job Outcomes", str(counts["job_outcomes"]), f"+{new_jobs}", str(rate_jobs)
    )
    table.add_row(
        "Config History",
        str(counts["config_history"]),
        f"+{new_config}",
        str(rate_config),
    )

    layout["body"].update(Panel(table, title="Real-time Statistics"))

    # Footer - Latest Log
    # Clean log line of some common prefixes for better display
    clean_log = log_line
    if "INFO:" in clean_log:
        clean_log = clean_log.split("INFO:", 1)[1].strip()

    layout["footer"].update(
        Panel(
            Text(clean_log, style="italic grey70"), title="Latest Activity", style="dim"
        )
    )

    return layout


async def main():
    """Run the main dashboard loop."""
    start_time = time.time()
    log_file = Path("backend/homepot.log")

    # Get initial counts
    initial_counts = await get_counts()

    print("Starting dashboard...")

    with Live(refresh_per_second=2, screen=True) as live:
        while True:
            counts = await get_counts()

            last_line = "Waiting for logs... (CTRL+C to exit)"
            if log_file.exists():
                try:
                    # Read last few bytes to get the last line
                    file_size = os.path.getsize(log_file)
                    with open(log_file, "rb") as f:
                        if file_size > 200:
                            f.seek(-200, 2)
                            lines = f.readlines()
                            if len(lines) > 1:
                                last_line = (
                                    lines[-1].decode("utf-8", errors="ignore").strip()
                                )
                        else:
                            lines = f.readlines()
                            if lines:
                                last_line = (
                                    lines[-1].decode("utf-8", errors="ignore").strip()
                                )
                except Exception:
                    pass

            live.update(generate_layout(counts, start_time, last_line, initial_counts))
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
