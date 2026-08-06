"""Tests for POS emulator OS identity and derived permissions.

The POS emulators are thin wrappers around the shared parameterized engine in
``emulators/linux_pos_emulator.py``; each OS only overrides identity defaults
(``os_details``, mock MAC/hostname). This test suite verifies that the engine
carries the OS identity through **both** the CLI-only and ``--config`` paths so
that OS-specific capability maps are honoured (e.g. Android must not report
``root_access``).

Covered:
- derive_os_capabilities() for Linux, Android, Windows, iOS
- CLI-only launch defaulting from an emulator's identity defaults (Android)
- CLI-only launch without defaults (plain Linux defaults)
- --config path honouring the config's os_details
- --os-details CLI override taking precedence over the config value
"""

import sys
from pathlib import Path

import pytest

EMULATORS_DIR = Path(__file__).resolve().parents[2] / "emulators"
sys.path.insert(0, str(EMULATORS_DIR))

import android_pos_emulator  # noqa: E402
import linux_pos_emulator as emu  # noqa: E402


@pytest.mark.parametrize(
    ("os_details", "expected_root_access", "expected_network_monitoring"),
    [
        ("Linux 6.8.0 (Debian 12)", True, True),
        ("Android 14", False, True),
        ("Windows 11", False, True),
        ("iOS", False, True),
        ("", False, False),
    ],
)
def test_derive_os_capabilities(os_details, expected_root_access, expected_network_monitoring):
    """Every supported OS maps to the right root-access and monitoring flags."""
    caps = emu.derive_os_capabilities(os_details)
    assert caps["root_access"] is expected_root_access
    assert caps["network_monitoring"] is expected_network_monitoring


def test_android_cli_only_defaults_to_android_os():
    """The pure-CLI path must pick up an emulator's Android identity defaults."""
    cfg = emu.build_config(emu.parse_args([], defaults=android_pos_emulator.ANDROID_DEFAULTS), defaults=android_pos_emulator.ANDROID_DEFAULTS)
    assert cfg.os_details == "Android 14"
    caps = emu.derive_os_capabilities(cfg.os_details)
    assert caps["root_access"] is False
    assert caps["process_monitoring"] is True


def test_cli_only_defaults_to_linux_when_no_defaults_provided():
    """Without an emulator's defaults, the engine keeps its Linux baseline."""
    cfg = emu.build_config(emu.parse_args([]), defaults=None)
    assert cfg.os_details == "Linux 6.8.0 (Debian 12)"
    assert emu.derive_os_capabilities(cfg.os_details)["root_access"] is True


def test_config_file_honours_android_os_details(tmp_path):
    """The --config path must carry the config's os_details into capabilities."""
    config_file = tmp_path / "android.json"
    config_file.write_text(
        '{"site_id": "site-1", "bootstrap_key": "k", '
        '"device_name": "android-pos-emulator-1", "os_details": "Android 14"}'
    )
    cfg = emu.build_config(
        emu.parse_args(["--config", str(config_file)]),
        defaults=android_pos_emulator.ANDROID_DEFAULTS,
    )
    assert cfg.os_details == "Android 14"
    assert emu.derive_os_capabilities(cfg.os_details)["root_access"] is False


def test_os_details_cli_flag_overrides_config(tmp_path):
    """--os-details on the CLI must override the config-file value."""
    config_file = tmp_path / "linux.json"
    config_file.write_text(
        '{"site_id": "site-1", "bootstrap_key": "k", '
        '"device_name": "device-1", "os_details": "Linux 6.8.0 (Debian 12)"}'
    )
    cfg = emu.build_config(
        emu.parse_args(["--config", str(config_file), "--os-details", "Android 14"]),
        defaults=None,
    )
    assert cfg.os_details == "Android 14"
    assert emu.derive_os_capabilities(cfg.os_details)["root_access"] is False