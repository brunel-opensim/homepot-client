"""Command Line Interface for HOMEPOT Client.

This module provides the main entry point for the HOMEPOT Client CLI.
"""

import typer
from rich.console import Console
from rich.panel import Panel

from homepot_client import __version__

app = typer.Typer(
    name="homepot-client",
    help="HOMEPOT Client - Homogenous Cyber Management of End-Points and OT",
    add_completion=False,
)
console = Console()


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


if __name__ == "__main__":
    main()
