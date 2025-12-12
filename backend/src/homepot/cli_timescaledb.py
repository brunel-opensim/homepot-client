"""CLI command for TimescaleDB setup and migration.

This script provides commands to:
- Set up TimescaleDB extension
- Create hypertables
- Create continuous aggregates
- Check TimescaleDB status
"""

import asyncio
import logging
import sys
from typing import Optional

import click

from homepot.database import get_database_service
from homepot.migrations.timescaledb_aggregates import setup_timescaledb_aggregates
from homepot.timescale import TimescaleDBManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def timescaledb() -> None:
    """TimescaleDB management commands."""
    pass


@timescaledb.command()
def status() -> None:
    """Check TimescaleDB availability and status."""

    async def check_status() -> None:
        db_service = await get_database_service()

        async with db_service.get_session() as session:
            ts_manager = TimescaleDBManager(session)

            # Check availability
            is_available = await ts_manager.is_timescaledb_available()

            if not is_available:
                click.echo("TimescaleDB: Not available")
                click.echo(
                    "\nTo install TimescaleDB, follow: https://docs.timescale.com/install/latest/"
                )
                return

            click.echo("TimescaleDB: Available")

            # Get hypertable stats
            stats = await ts_manager.get_hypertable_stats("health_checks")
            if stats:
                click.echo("\nHypertable: health_checks")
                click.echo(f"  Schema: {stats.get('hypertable_schema')}")
                click.echo(f"  Chunks: {stats.get('num_chunks', 'N/A')}")
                click.echo(f"  Compression: {stats.get('compression_enabled', False)}")

                # Get chunk stats
                chunks = await ts_manager.get_chunk_stats("health_checks")
                if chunks:
                    click.echo(f"\n  Recent chunks:")
                    for chunk in chunks[:3]:  # Show 3 most recent
                        click.echo(
                            f"    - {chunk.get('chunk_name')}: "
                            f"{chunk.get('range_start')} to {chunk.get('range_end')}"
                        )
            else:
                click.echo("\n  health_checks is not a hypertable")

        await db_service.close()

    asyncio.run(check_status())


@timescaledb.command()
@click.option(
    "--force",
    is_flag=True,
    help="Force recreation of hypertables (destructive)",
)
def setup(force: bool) -> None:
    """Set up TimescaleDB extension and hypertables."""

    async def run_setup() -> int:
        db_service = await get_database_service()

        async with db_service.get_session() as session:
            ts_manager = TimescaleDBManager(session)

            # Check availability
            if not await ts_manager.is_timescaledb_available():
                click.echo("TimescaleDB extension not available")
                click.echo(
                    "Please install TimescaleDB: https://docs.timescale.com/install/latest/"
                )
                return 1

            click.echo("TimescaleDB extension is available")

            # Enable extension
            click.echo("\nEnabling TimescaleDB extension...")
            if await ts_manager.enable_extension():
                click.echo("TimescaleDB extension enabled")
            else:
                click.echo("Failed to enable TimescaleDB extension")
                return 1

            # Create hypertable
            click.echo("\nCreating hypertable: health_checks...")
            success = await ts_manager.create_hypertable(
                table_name="health_checks",
                time_column="timestamp",
                chunk_time_interval="1 week",
                if_not_exists=not force,
            )

            if success:
                click.echo("Hypertable created: health_checks")

                # Add compression
                click.echo("\n  Adding compression policy...")
                if await ts_manager.add_compression_policy(
                    hypertable="health_checks",
                    compress_after="7 days",
                    if_not_exists=True,
                ):
                    click.echo("Compression policy added (compress after 7 days)")

                # Add retention
                click.echo("\n  Adding retention policy...")
                if await ts_manager.add_retention_policy(
                    hypertable="health_checks",
                    retention_period="90 days",
                    if_not_exists=True,
                ):
                    click.echo("Retention policy added (keep 90 days)")

                click.echo("\nTimescaleDB setup completed successfully!")
                return 0
            else:
                click.echo("Failed to create hypertable")
                return 1

        await db_service.close()

    sys.exit(asyncio.run(run_setup()))


@timescaledb.command()
def create_aggregates() -> None:
    """Create continuous aggregates for pre-computed metrics."""

    async def run_aggregates() -> int:
        db_service = await get_database_service()

        async with db_service.get_session() as session:
            ts_manager = TimescaleDBManager(session)

            # Check availability
            if not await ts_manager.is_timescaledb_available():
                click.echo("TimescaleDB not available")
                return 1

            click.echo("Creating continuous aggregates...")
            results = await setup_timescaledb_aggregates(session)

            if not results:
                click.echo("No aggregates created")
                return 1

            # Display results
            click.echo("\nResults:")
            for name, success in results.items():
                status = "✓" if success else "✗"
                click.echo(f"  {status} {name}")

            successful = sum(1 for s in results.values() if s)
            total = len(results)

            if successful == total:
                click.echo(f"\nAll {total} aggregates created successfully!")
                return 0
            else:
                click.echo(f"\nCreated {successful}/{total} aggregates")
                return 1

        await db_service.close()

    sys.exit(asyncio.run(run_aggregates()))


@timescaledb.command()
@click.argument("hypertable", default="health_checks")
def chunks(hypertable: str) -> None:
    """List chunks for a hypertable."""

    async def list_chunks() -> None:
        db_service = await get_database_service()

        async with db_service.get_session() as session:
            ts_manager = TimescaleDBManager(session)

            if not await ts_manager.is_timescaledb_available():
                click.echo("TimescaleDB not available")
                return

            chunks = await ts_manager.get_chunk_stats(hypertable)

            if not chunks:
                click.echo(f"No chunks found for hypertable: {hypertable}")
                return

            click.echo(f"\nChunks for {hypertable}:\n")
            for i, chunk in enumerate(chunks, 1):
                click.echo(f"{i}. {chunk.get('chunk_name')}")
                click.echo(
                    f"   Range: {chunk.get('range_start')} to {chunk.get('range_end')}"
                )
                click.echo(f"   Rows: {chunk.get('num_rows', 'N/A')}")
                click.echo(f"   Compressed: {chunk.get('is_compressed', False)}")
                click.echo()

        await db_service.close()

    asyncio.run(list_chunks())


if __name__ == "__main__":
    timescaledb()
