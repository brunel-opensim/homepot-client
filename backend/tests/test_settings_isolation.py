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


def test_class_database_fixture_restores_environment(pytester, monkeypatch):
    """The class-scoped POS fixture restores its previous database URL."""
    database_url = "sqlite+aiosqlite:///:memory:"
    monkeypatch.setenv("DATABASE__URL", database_url)
    test_dir = Path(__file__).parent
    pytester.makeconftest(
        f"import runpy\nrestore_settings = runpy.run_path({str(test_dir / 'conftest.py')!r})"
        "['restore_settings']\n"
    )
    pytester.makepyfile(
        f"""
        import importlib
        import os
        import runpy
        import homepot.config

        class TestTemporaryDatabase:
            temp_db = runpy.run_path({str(test_dir / 'test_pos_dummy.py')!r})['TestPOSDummy'].temp_db

            def test_temporary_settings(self, temp_db):
                importlib.reload(homepot.config)
                assert homepot.config.get_settings().database.url == f"sqlite:///{{temp_db}}"

        def test_restored_settings():
            assert os.environ["DATABASE__URL"] == {database_url!r}
            assert homepot.config.get_settings().database.url == {database_url!r}
        """
    )
    result = pytester.runpytest_subprocess("-q", "-p", "no:cacheprovider", "--no-cov")
    result.assert_outcomes(passed=2)
