"""Command-line interface for the HOMEPOT Agent.

Provides commands for running the agent, managing device identity,
inspecting status, and viewing configuration.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

import typer

from homepot.agent.credential_storage import (
    LinuxFileStorage,
    create_credential_storage,
)
from homepot.agent.identity import (
    get_device_id,
    get_or_create_device_id,
    identity_dir,
    identity_path,
    reset_device_id,
)
from homepot.agent.real_device_agent import load_agent_config, run_agent

app = typer.Typer(
    name="homepot-agent",
    help="HOMEPOT Device Agent - managed endpoint runtime",
    add_completion=False,
)

logger = logging.getLogger(__name__)


@app.callback()
def _main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to agent configuration JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Configure global agent options."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    if config:
        os.environ["HOMEPOT_AGENT_CONFIG"] = str(config.resolve())


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@app.command()
def run(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to agent configuration JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Run the agent runtime (registration, heartbeat, telemetry).

    This is the main entry point used by the systemd service.
    """
    if config:
        os.environ["HOMEPOT_AGENT_CONFIG"] = str(config.resolve())
    ensure_identity()
    asyncio.run(run_agent())


def ensure_identity() -> str:
    """Ensure a persistent device identity exists and log it."""
    device_id = get_or_create_device_id()
    logger.info("Device identity: %s", device_id)
    logger.info("Identity file: %s", identity_path())
    return device_id


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------


@app.command()
def identity() -> None:
    """Show the current device identity or generate one."""
    device_id = get_or_create_device_id()
    path = identity_path()
    dir_path = identity_dir()

    typer.echo(f"Device ID:   {device_id}")
    typer.echo(f"Identity:    {path}")
    typer.echo(f"Storage:     {dir_path}")
    typer.echo(f"Provisioned: {is_provisioned_str()}")

    cred = create_credential_storage()
    if cred.is_provisioned():
        typer.echo(f"API Key:     {mask_key(cred.get_api_key() or '')}")


@app.command()
def reset_identity() -> None:
    """Remove the stored device identity (does not affect machine-id)."""
    current = get_device_id()
    if current:
        typer.echo(f"Removing identity: {current}")
        reset_device_id()
        typer.echo(
            "Identity removed.  Run 'homepot-agent identity' to generate a new one."
        )
    else:
        typer.echo("No identity to remove.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status() -> None:
    """Show the current agent status."""
    cred = create_credential_storage()
    is_prov = cred.is_provisioned()
    device_id = get_device_id() or "(not set)"

    typer.echo(f"Device ID:    {device_id}")
    typer.echo(f"Provisioned:  {yes_no(is_prov)}")
    if is_prov:
        typer.echo(f"Device Name:  {cred.get_metadata('device_name') or '(not set)'}")
        typer.echo(f"Site ID:      {cred.get_metadata('site_id') or '(not set)'}")

    identity_path_val = identity_path()
    typer.echo(f"Identity:     {identity_path_val}")
    typer.echo(f"  Exists:     {yes_no(identity_path_val.exists())}")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


@app.command()
def show_config(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to agent configuration JSON file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Show the effective agent configuration."""
    if config:
        os.environ["HOMEPOT_AGENT_CONFIG"] = str(config.resolve())
    try:
        cfg = load_agent_config()
        typer.echo(json.dumps(cfg, indent=2))
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error loading config: {exc}", err=True)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------


@app.command()
def credentials() -> None:
    """Show credential storage status and metadata."""
    cred = create_credential_storage()
    if not cred.is_provisioned():
        typer.echo("No credentials stored.")
        raise typer.Exit(code=0)

    device_id = cred.get_device_id()
    api_key = cred.get_api_key()
    backend_url = cred.get_backend_url()

    typer.echo(f"Device ID:    {device_id}")
    typer.echo(f"API Key:      {mask_key(api_key or '')}")
    typer.echo(f"Backend URL:  {backend_url or '(not set)'}")
    typer.echo(f"TLS Verify:   {cred.get_tls_verify()}")
    typer.echo(f"Storage:      {type(cred).__name__}")

    if isinstance(cred, LinuxFileStorage):
        typer.echo(f"File:         {cred._file_path}")

    for meta_key in ("device_name", "site_id", "device_type", "enrollment_method"):
        val = cred.get_metadata(meta_key)
        if val:
            typer.echo(f"{meta_key}: {val}")

    ca_cert = cred.get_tls_ca_cert()
    client_cert = cred.get_tls_client_cert()
    if ca_cert:
        typer.echo(f"TLS CA Cert:  {ca_cert}")
    if client_cert:
        typer.echo(f"TLS Client Cert: {client_cert}")


@app.command()
def clear_credentials() -> None:
    """Remove all stored credentials (local unpair)."""
    cred = create_credential_storage()
    if cred.is_provisioned():
        cred.clear()
        typer.echo("Credentials cleared.")
    else:
        typer.echo("No credentials to clear.")


# ---------------------------------------------------------------------------
# backend-url
# ---------------------------------------------------------------------------


@app.command()
def set_backend_url(
    url: str = typer.Argument(
        ..., help="Backend URL (e.g. https://api.homepot.example.com)"
    ),
) -> None:
    """Set the backend URL for the agent to connect to."""
    cred = create_credential_storage()
    cred.set_backend_url(url)
    typer.echo(f"Backend URL set to: {url}")


# ---------------------------------------------------------------------------
# tls
# ---------------------------------------------------------------------------


@app.command()
def set_tls(
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Enable/disable TLS verification"
    ),
    ca_cert: Optional[str] = typer.Option(
        None, "--ca-cert", help="Path to CA certificate file or PEM content"
    ),
    client_cert: Optional[str] = typer.Option(
        None, "--client-cert", help="Path to client certificate file or PEM content"
    ),
    client_key: Optional[str] = typer.Option(
        None,
        "--client-key",
        help="Path to client private key file or PEM content",
    ),
) -> None:
    """Set TLS configuration for backend communication."""
    cred = create_credential_storage()
    cred.set_tls_config(
        verify=verify,
        ca_cert=ca_cert,
        client_cert=client_cert,
        client_key=client_key,
    )
    typer.echo("TLS configuration updated.")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def is_provisioned_str() -> str:
    """Return 'yes' or 'no' indicating whether credentials exist."""
    cred = create_credential_storage()
    return yes_no(cred.is_provisioned())


def yes_no(val: bool) -> str:
    """Return 'yes' for True, 'no' for False."""
    return "yes" if val else "no"


def mask_key(key: str) -> str:
    """Mask all but the first and last 4 characters of an API key."""
    if len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def main() -> None:
    """Entry point for the homepot-agent console script."""
    app()


if __name__ == "__main__":
    main()
