"""Command Line Interface for HOMEPOT Client.

This module provides the main entry point for the HOMEPOT Client CLI.
"""

import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
import typer

from homepot import __version__
from homepot.database import get_database_service
from homepot.kpi.export import compute_kpi_bundle, render_csv_summary
from homepot.kpi.models import PROVENANCE_CLASSES, ExportFilters, KPIExportBundle

app = typer.Typer(
    name="homepot-client",
    help="HOMEPOT Client - Homogenous Cyber Management of End-Points and OT",
    add_completion=False,
)
console = Console()

# Alias for test compatibility
cli = app


@app.command()
def version() -> None:
    """Show the HOMEPOT Client version."""
    console.print(
        Panel(
            f"[bold blue]HOMEPOT Client[/bold blue]\n"
            f"Version: [green]{__version__}[/green]\n"
            f"A consortium project for unified device management",
            title="Version Information",
            border_style="blue",
        )
    )


@app.command()
def info() -> None:
    """Show information about the HOMEPOT Client."""
    console.print(
        Panel(
            "[bold blue]HOMEPOT Client[/bold blue]\n\n"
            "[yellow]HOMEPOT[/yellow] stands for [italic]Homogenous Cyber "
            "Management of End-Points and Operational Technology[/italic].\n\n"
            "[bold]Key Features:[/bold]\n"
            "• Unified device management across multiple ecosystems\n"
            "• Secure communication with distributed devices\n"
            "• Cross-platform compatibility\n"
            "• Consortium collaboration support\n\n"
            "[bold]Use Cases:[/bold]\n"
            "• Retail operations\n"
            "• Hospitality management\n"
            "• Industrial control systems\n\n"
            "[dim]Copyright 2025 HOMEPOT Consortium[/dim]",
            title="HOMEPOT Client Information",
            border_style="green",
        )
    )


def main() -> None:
    """Entry point for the CLI."""
    app()


@app.command()
def kpi_export(
    start: str = typer.Option(..., help="Window start, ISO-8601 UTC"),
    end: str = typer.Option(..., help="Window end, ISO-8601 UTC"),
    site_id: Optional[str] = typer.Option(None, help="Restrict to a site"),
    device_id: Optional[str] = typer.Option(None, help="Restrict to a device"),
    device_type: Optional[str] = typer.Option(None, help="Restrict to a device type"),
    provenance: Optional[str] = typer.Option(
        None, help="Restrict to a provenance class (real/controlled/simulated)"
    ),
    run_id: Optional[str] = typer.Option(
        None, help="Run ID (default: UTC timestamp, e.g. 20260816T220500Z)"
    ),
    out_dir: Optional[str] = typer.Option(
        None,
        help="Directory to write the export into (default: kpi-evidence/<run-id>)",
    ),
) -> None:
    """Export a versioned, filtered UK demonstrator KPI calculation.

    Writes both ``kpi-export.json`` (manifest + KPI summary + raw evidence)
    and ``kpi-summary.csv`` (machine-readable KPI summary) into ``--out-dir``
    (default ``kpi-evidence/<run-id>``).
    """
    if provenance is not None and provenance not in PROVENANCE_CLASSES:
        raise typer.BadParameter(
            f"provenance must be one of: {', '.join(PROVENANCE_CLASSES)}"
        )

    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid timestamp: {exc}")

    filters = ExportFilters(
        start=start_dt,
        end=end_dt,
        site_id=site_id,
        device_id=device_id,
        device_type=device_type,
        provenance=provenance,
    )

    async def _run() -> KPIExportBundle:
        db_service = await get_database_service()
        try:
            async with db_service.get_session() as session:
                return await compute_kpi_bundle(session, filters, run_id=run_id)
        finally:
            await db_service.close()

    bundle = asyncio.run(_run())

    run_id_used = bundle.manifest["run_id"]
    if out_dir is None:
        out_dir = f"kpi-evidence/{run_id_used}"

    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    json_path = target / "kpi-export.json"
    json_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    csv_path = target / "kpi-summary.csv"
    csv_path.write_text(render_csv_summary(bundle), encoding="utf-8")

    console.print(
        Panel(
            f"Exported {len(bundle.kpis)} KPI results to:\n"
            f"  [green]{json_path}[/green]\n"
            f"  [green]{csv_path}[/green]\n"
            f"run_id: {bundle.manifest.get('run_id')}\n"
            f"calculation_version: {bundle.manifest.get('calculation_version')}\n"
            f"git_commit: {bundle.manifest.get('git_commit')}",
            title="KPI Export",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
