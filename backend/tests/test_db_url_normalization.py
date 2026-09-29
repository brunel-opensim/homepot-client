"""Tests for database URL dialect normalisation.

Background
----------
HOMEPOT uses two engines over one configured URL:

* the async engine, driven by the FastAPI application
* a synchronous engine, used by Alembic and the backup/utility scripts

Deployment and CI both configure the bare ``postgresql://`` form. That leaves
the dialect to SQLAlchemy, and the two engines need *different* drivers. If the
dialect is left unnamed, SQLAlchemy 2.1 resolves a bare ``postgresql://`` to
psycopg 3 and the sync engine dies with ``No module named 'psycopg'`` even
though psycopg2 is installed.

These tests pin the normalisation that keeps each engine on a driver this
project actually declares.
"""

import pytest

from homepot.database import (
    ASYNC_PG_DIALECT,
    SYNC_PG_DIALECT,
    to_async_db_url,
    to_sync_db_url,
)

PG = "postgresql://homepot_user:secret@postgres:5432/homepot_db"
CRED = "homepot_user:secret@postgres:5432/homepot_db"


class TestToAsyncDbUrl:
    """The async engine cannot use a synchronous driver."""

    def test_bare_postgres_uses_asyncpg(self):
        """A bare postgresql:// must not reach create_async_engine unnamed."""
        assert to_async_db_url(PG) == f"{ASYNC_PG_DIALECT}://{CRED}"

    def test_asyncpg_is_idempotent(self):
        """Asyncpg is idempotent."""
        url = f"{ASYNC_PG_DIALECT}://{CRED}"
        assert to_async_db_url(url) == url

    def test_sqlite_becomes_aiosqlite(self):
        """The async engine needs the aiosqlite driver for SQLite."""
        assert to_async_db_url("sqlite:///./test.db") == "sqlite+aiosqlite:///./test.db"

    def test_aiosqlite_is_unchanged(self):
        """An already-correct async SQLite URL is left alone."""
        url = "sqlite+aiosqlite:///./test.db"
        assert to_async_db_url(url) == url

    def test_never_leaves_bare_postgres(self):
        """Regression guard: the async engine must never get a bare dialect."""
        assert not to_async_db_url(PG).startswith("postgresql://")


class TestToSyncDbUrl:
    """The sync engine must not pick a driver that is not installed."""

    def test_bare_postgres_uses_psycopg2(self):
        """This is the exact failure seen in the Docker CI job.

        Without this, ``_db_url`` fell through to ``create_engine`` as a bare
        ``postgresql://`` and SQLAlchemy 2.1 imported psycopg 3.
        """
        assert to_sync_db_url(PG) == f"{SYNC_PG_DIALECT}://{CRED}"

    def test_asyncpg_is_downgraded_to_psycopg2(self):
        """The sync layer cannot use asyncpg, so it is swapped for psycopg2."""
        url = f"{ASYNC_PG_DIALECT}://{CRED}"
        assert to_sync_db_url(url) == f"{SYNC_PG_DIALECT}://{CRED}"

    def test_explicit_psycopg2_is_unchanged(self):
        """An explicit psycopg2 URL is already valid for the sync engine."""
        url = f"{SYNC_PG_DIALECT}://{CRED}"
        assert to_sync_db_url(url) == url

    def test_aiosqlite_becomes_sqlite(self):
        """Aiosqlite becomes sqlite."""
        url = "sqlite+aiosqlite:///./test.db"
        assert to_sync_db_url(url) == "sqlite:///./test.db"

    def test_plain_sqlite_is_unchanged(self):
        """Plain SQLite is already valid for the sync engine."""
        url = "sqlite:///./test.db"
        assert to_sync_db_url(url) == url

    def test_never_leaves_bare_postgres(self):
        """Regression guard: the sync engine must always name its driver."""
        assert not to_sync_db_url(PG).startswith("postgresql://")


class TestDriverIsDeclared:
    """The driver named by each normaliser must be a declared dependency."""

    @pytest.mark.parametrize(
        "dialect,distribution",
        [
            (ASYNC_PG_DIALECT, "asyncpg"),
            (SYNC_PG_DIALECT, "psycopg2-binary"),
        ],
    )
    def test_dialect_driver_is_in_pyproject(self, dialect, distribution):
        """Each dialect we name must have a driver actually declared."""
        from pathlib import Path

        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
        assert f'"{distribution}>=' in pyproject, (
            f"{dialect} requires the {distribution} driver, which pyproject.toml "
            f"does not declare"
        )


class TestBothEnginesFromOneUrl:
    """One configured URL must produce two compatible, distinct drivers."""

    def test_default_url_splits_into_async_and_sync(self):
        """Default url splits into async and sync."""
        assert to_async_db_url(PG) == f"{ASYNC_PG_DIALECT}://{CRED}"
        assert to_sync_db_url(PG) == f"{SYNC_PG_DIALECT}://{CRED}"

    def test_async_url_also_resolves_for_sync_layer(self):
        """Alembic reads the same DATABASE__URL, so async URLs must convert."""
        """Alembic reads DATABASE__URL too, so an async URL must still work."""
        assert to_sync_db_url(to_async_db_url(PG)) == f"{SYNC_PG_DIALECT}://{CRED}"
