"""Alembic environment configuration for Homepot migrations."""

from __future__ import annotations

from logging.config import fileConfig
import os
from pathlib import Path
import sys
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text

# Ensure "src" is importable when running Alembic from backend root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from homepot.config import get_settings  # noqa: E402
from homepot.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """Resolve migration DB URL from env var or application settings."""
    env_db_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE__URL")
    if env_db_url:
        return env_db_url
    return get_settings().database.url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _prepare_alembic_version_table(engine: Any) -> None:
    """Ensure ``alembic_version.version_num`` can hold long revision ids.

    Alembic creates the version table with a ``VARCHAR(32)`` column, but
    several revision ids in this chain exceed 32 characters (e.g.
    ``20260720_add_device_assignments_events``).  PostgreSQL enforces the
    length limit, so widen (or pre-create) the column before migrations run.
    SQLite ignores ``VARCHAR`` lengths and needs no adjustment.
    """
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        if inspect(engine).has_table("alembic_version"):
            conn.execute(
                text(
                    "ALTER TABLE alembic_version "
                    "ALTER COLUMN version_num TYPE VARCHAR(64)"
                )
            )
            return

        conn.execute(
            text(
                "CREATE TABLE alembic_version ("
                "version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
            )
        )


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    cfg_section = config.get_section(config.config_ini_section, {})
    cfg_section["sqlalchemy.url"] = _resolve_database_url()

    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    _prepare_alembic_version_table(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
