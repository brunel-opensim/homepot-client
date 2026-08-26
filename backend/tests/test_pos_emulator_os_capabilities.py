"""Tests for POS emulator OS identity and derived permissions.

The POS emulators are thin wrappers around the shared parameterized engine in
``emulators/pos_engine.py``; each OS only overrides identity defaults
(``os_details``, mock MAC/hostname). This test suite verifies that the engine
carries the OS identity through **both** the CLI-only and ``--config`` paths so
that OS-specific capability maps are honoured (e.g. Android must not report
``root_access``).

Covered:
- derive_os_capabilities() for Linux, Android, Windows, iOS
- derive_push_channel() for FCM/WNS/APNs and polling-only OSes
- push registration hooks (channel + token) on the engine and status report
- CLI-only launch defaulting from an emulator's identity defaults (Android)
- CLI-only launch without defaults (plain Linux defaults)
- --config path honouring the config's os_details
- --os-details CLI override taking precedence over the config value
"""

from pathlib import Path
import sys

import pytest

EMULATORS_DIR = Path(__file__).resolve().parents[2] / "emulators"
sys.path.insert(0, str(EMULATORS_DIR))

import android_pos_emulator  # noqa: E402
import ios_pos_emulator  # noqa: E402
import macos_pos_emulator  # noqa: E402
import pos_engine as emu  # noqa: E402
import windows_pos_emulator  # noqa: E402


def test_command_wakeup_sets_wake_event():
    """A command_wakeup push makes the command loop poll immediately."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg.os_details = "Android 14"
    eng = emu.POSEmulator(cfg)
    eng._device_id = "device-test-001"
    eng._api_key = "api-key-test"

    async def deliver():
        eng._http = AsyncMock()
        eng._http.post.return_value = SimpleNamespace(status_code=200)
        eng._report_push_log = AsyncMock()
        await eng._deliver_push(
            {
                "message_id": "m1",
                "payload": {
                    "title": "",
                    "body": "",
                    "data": {"type": "command_wakeup", "device_id": "d"},
                },
            }
        )
        return eng._command_wake_event.is_set()

    assert asyncio.run(deliver())


def test_regular_push_does_not_wake_command_loop():
    """A non-wake-up push leaves the command loop on its own interval."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg.os_details = "Android 14"
    eng = emu.POSEmulator(cfg)
    eng._device_id = "device-test-001"
    eng._api_key = "api-key-test"

    async def deliver():
        eng._http = AsyncMock()
        eng._http.post.return_value = SimpleNamespace(status_code=200)
        eng._report_push_log = AsyncMock()
        await eng._deliver_push(
            {"message_id": "m2", "payload": {"title": "Hello", "body": "World"}}
        )
        return eng._command_wake_event.is_set()

    assert not asyncio.run(deliver())


def test_final_offline_heartbeat_sends_online_false():
    """The shutdown heartbeat marks the device OFFLINE on the backend."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg.os_details = "Android 14"
    eng = emu.POSEmulator(cfg)
    eng._device_id = "device-test-001"
    eng._api_key = "api-key-test"

    async def send():
        eng._http = AsyncMock()
        eng._http.post.return_value = SimpleNamespace(status_code=200)
        await eng._send_final_offline_heartbeat()
        return eng._http.post.await_args

    call = asyncio.run(send())
    assert call.args[0].endswith("/agent/heartbeat")
    assert call.kwargs["json"]["online"] is False
    assert call.kwargs["json"]["device_id"] == "device-test-001"


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
def test_derive_os_capabilities(
    os_details, expected_root_access, expected_network_monitoring
):
    """Every supported OS maps to the right root-access and monitoring flags."""
    caps = emu.derive_os_capabilities(os_details)
    assert caps["root_access"] is expected_root_access
    assert caps["network_monitoring"] is expected_network_monitoring


@pytest.mark.parametrize(
    ("os_details", "expected_push_channel"),
    [
        ("Android 14", "fcm"),
        ("Windows 11", "wns"),
        ("iOS 17", "apns"),
        ("iPadOS 17", "apns"),
        ("Linux 6.8.0 (Debian 12)", None),
        ("macOS 14", None),
        ("", None),
    ],
)
def test_derive_push_channel(os_details, expected_push_channel):
    """Push-capable OSes pick FCM/WNS/APNs; desktop runtimes stay polling-only."""
    assert emu.derive_push_channel(os_details) is expected_push_channel


@pytest.mark.parametrize(
    ("os_details", "expected_channel"),
    [
        ("Android 14", "fcm"),
        ("Windows 11", "wns"),
        ("iOS 26", "apns"),
        ("Linux 6.8.0 (Debian 12)", None),
    ],
)
def test_derive_push_channel_and_token_for_os(os_details, expected_channel):
    """The engine hooks expose a synthetic token only for push-capable OSes."""
    if expected_channel is None:
        cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
        cfg.os_details = os_details
        eng = emu.POSEmulator(cfg)
        assert eng.push_channel is None
        assert eng.push_token is None
        assert eng._push_delivery_note("restart") is None
        return
    cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg.os_details = os_details
    eng = emu.POSEmulator(cfg)
    assert eng.push_channel is expected_channel
    assert eng.push_token is not None
    if expected_channel == "wns":
        assert "://" in eng.push_token
        host = eng.push_token.split("://")[1]
        assert host.startswith("wns.")
    else:
        assert eng.push_token.startswith(expected_channel)
    note = eng._push_delivery_note("restart")
    assert note is not None
    assert expected_channel in note.lower()


def test_push_token_stability_within_engine():
    """Re-instantiating for the same OS regenerates a fresh token."""
    cfg = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg.os_details = "Android 14"
    token_a = emu.POSEmulator(cfg).push_token
    cfg2 = emu.build_config(emu.parse_args([], defaults=None), defaults=None)
    cfg2.os_details = "Android 14"
    token_b = emu.POSEmulator(cfg2).push_token
    assert token_a != token_b


def test_android_cli_only_defaults_to_android_os():
    """The pure-CLI path must pick up an emulator's Android identity defaults."""
    cfg = emu.build_config(
        emu.parse_args([], defaults=android_pos_emulator.ANDROID_DEFAULTS),
        defaults=android_pos_emulator.ANDROID_DEFAULTS,
    )
    assert cfg.os_details == "Android 14"
    caps = emu.derive_os_capabilities(cfg.os_details)
    assert caps["root_access"] is False
    assert caps["process_monitoring"] is True


def test_cli_only_defaults_to_linux_when_no_defaults_provided():
    """Without an emulator's defaults, the engine keeps its Linux baseline."""
    cfg = emu.build_config(emu.parse_args([]), defaults=None)
    assert cfg.os_details == "Linux 6.8.0 (Debian 12)"
    assert emu.derive_os_capabilities(cfg.os_details)["root_access"] is True


@pytest.mark.parametrize(
    ("module", "defaults_name", "expected_os", "expected_type", "expected_root"),
    [
        (android_pos_emulator, "ANDROID_DEFAULTS", "Android 14", "pos_terminal", False),
        (windows_pos_emulator, "WINDOWS_DEFAULTS", "Windows 11", "pos_terminal", False),
        (macos_pos_emulator, "MACOS_DEFAULTS", "macOS 14", "pos_terminal", True),
        (ios_pos_emulator, "IOS_DEFAULTS", "iOS 17", "tablet", False),
    ],
)
def test_os_wrapper_identity_defaults(
    module, defaults_name, expected_os, expected_type, expected_root
):
    """Each OS wrapper's CLI-only path carries its identity and capability map."""
    defaults = getattr(module, defaults_name)
    cfg = emu.build_config(emu.parse_args([], defaults=defaults), defaults=defaults)
    assert cfg.os_details == expected_os
    assert cfg.device_type == expected_type
    caps = emu.derive_os_capabilities(cfg.os_details)
    assert caps["root_access"] is expected_root

    # iOS is the most restricted: network monitoring only.
    if defaults_name == "IOS_DEFAULTS":
        assert caps["process_monitoring"] is False
        assert caps["filesystem_access"] is False
        assert caps["network_monitoring"] is True
    elif defaults_name in ("ANDROID_DEFAULTS", "WINDOWS_DEFAULTS", "MACOS_DEFAULTS"):
        assert caps["process_monitoring"] is True
        assert caps["filesystem_access"] is True


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
