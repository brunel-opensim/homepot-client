"""Regression tests for settings isolation between tests."""

from pathlib import Path

import pytest

pytest_plugins = ("pytester",)


@pytest.mark.parametrize(
    "database_url",
    ["sqlite+aiosqlite:///:memory:", "postgresql+asyncpg://localhost/homepot_test"],
)
def test_settings_restored_after_monkeypatch(pytester, monkeypatch, database_url):
    """Settings are reloaded only after fixture environment patches are undone."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE__URL", database_url)
    conftest = Path(__file__).with_name("conftest.py")
    pytester.makeconftest(
        f"import runpy\nrestore_settings = runpy.run_path({str(conftest)!r})"
        "['restore_settings']\n"
    )
    pytester.makepyfile(
        """
        import os
        import pytest
        from homepot.config import Settings, get_settings, reload_settings

        @pytest.fixture
        def temporary_database(monkeypatch):
            monkeypatch.setenv("DATABASE__URL", "sqlite:///temporary.db")
            reload_settings()
            yield
            assert get_settings().database.url == "sqlite:///temporary.db"

        def test_temporary_settings(temporary_database):
            assert get_settings().database.url == "sqlite:///temporary.db"

        def test_restored_settings():
            assert get_settings().database.url == Settings().database.url
            assert get_settings().database.url == os.environ["DATABASE__URL"]
        """
    )
    result = pytester.runpytest_subprocess("-q", "-p", "no:cacheprovider", "--no-cov")
    result.assert_outcomes(passed=2)
