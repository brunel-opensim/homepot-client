"""Tests for the canonical operator role vocabulary."""

import pytest

from homepot.app import roles


@pytest.mark.parametrize("spelling", ["Admin", "admin", "ADMIN", "administrator"])
def test_normalize_role_admin_spellings(spelling):
    """Admin spellings, including case variants, resolve to Admin."""
    assert roles.normalize_role(spelling) == roles.ADMIN


@pytest.mark.parametrize(
    "spelling", ["Technician", "technician", "Client", "Engineer", "user", "User"]
)
def test_normalize_role_non_admin_spellings(spelling):
    """Legacy Client/Engineer/User spellings resolve to Technician."""
    assert roles.normalize_role(spelling) == roles.TECHNICIAN


def test_normalize_role_is_idempotent():
    """Normalising an already-canonical role is a no-op."""
    assert roles.normalize_role(roles.normalize_role("Client")) == roles.TECHNICIAN


@pytest.mark.parametrize("value", [None, 42, "", "   ", "wizard", ["Admin"]])
def test_normalize_role_unknown_values_fall_back_to_least_privilege(value):
    """Unknown, empty or non-string roles fall back to Technician."""
    # An unrecognised role must never resolve to Admin.
    assert roles.normalize_role(value) == roles.TECHNICIAN


def test_normalize_role_tolerates_surrounding_whitespace():
    """Surrounding whitespace does not defeat normalisation."""
    assert roles.normalize_role("  Admin  ") == roles.ADMIN


def test_development_default_unifies_admin_and_technician():
    """In development mode both operator roles are privileged."""
    # Dev mode: both roles get admin-equivalent access, by explicit request.
    assert roles.is_privileged(roles.ADMIN) is True
    assert roles.is_privileged(roles.TECHNICIAN) is True


def test_with_unified_access_off_only_admin_is_privileged():
    """With unified access off, Technician loses admin access."""
    assert roles.is_privileged(roles.ADMIN, dev_unified_access=False) is True
    assert roles.is_privileged(roles.TECHNICIAN, dev_unified_access=False) is False


def test_with_unified_access_off_legacy_spellings_still_resolve():
    """Legacy spellings still privilege correctly with unified access off."""
    assert roles.is_privileged("Engineer", dev_unified_access=False) is False
    assert roles.is_privileged("administrator", dev_unified_access=False) is True


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
def test_dev_flag_truthy_values(monkeypatch, raw):
    """Truthy HOMEPOT_DEV_UNIFIED_ACCESS values enable unified access."""
    monkeypatch.setenv("HOMEPOT_DEV_UNIFIED_ACCESS", raw)
    assert roles._env_flag("HOMEPOT_DEV_UNIFIED_ACCESS", default=False) is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", "banana"])
def test_dev_flag_falsy_values(monkeypatch, raw):
    """Falsy or unparseable values disable unified access."""
    monkeypatch.setenv("HOMEPOT_DEV_UNIFIED_ACCESS", raw)
    assert roles._env_flag("HOMEPOT_DEV_UNIFIED_ACCESS", default=True) is False


def test_dev_flag_unset_uses_default(monkeypatch):
    """An unset flag falls back to the supplied default."""
    monkeypatch.delenv("HOMEPOT_DEV_UNIFIED_ACCESS", raising=False)
    assert roles._env_flag("HOMEPOT_DEV_UNIFIED_ACCESS", default=True) is True
    assert roles._env_flag("HOMEPOT_DEV_UNIFIED_ACCESS", default=False) is False


def test_development_mode_is_the_shipped_default():
    """Development mode is on unless explicitly disabled."""
    # Guard against accidentally disabling the dev-mode unification.
    assert roles.DEV_UNIFIED_ACCESS is True
