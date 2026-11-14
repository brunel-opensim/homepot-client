"""Tests for isolation of the cached application settings."""

from conftest import isolate_settings
import pytest

from homepot.config import get_settings, reload_settings


def test_settings_restored_after_environment_patch(monkeypatch: pytest.MonkeyPatch):
    """Reloaded settings do not leak after a test's environment is restored."""
    monkeypatch.setenv("DATABASE__URL", "sqlite:///original.db")
    original = reload_settings()

    with pytest.MonkeyPatch.context() as patch:
        isolate_settings.__wrapped__(patch)
        patch.setenv("DATABASE__URL", "sqlite:///temporary.db")
        assert reload_settings().database.url == "sqlite:///temporary.db"

    assert get_settings() is original
    assert get_settings().database.url == "sqlite:///original.db"
