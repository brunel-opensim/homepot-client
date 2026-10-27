"""Tests for the host firmware/version helpers."""

import subprocess  # noqa: S404 - exercises the helper's subprocess call
from typing import Iterator
from unittest.mock import patch

import pytest

from homepot.agent.utils import host_info


@pytest.fixture(autouse=True)
def _clear_firmware_cache() -> Iterator[None]:
    """Keep the cached host value from leaking between tests."""
    host_info.get_firmware_version.cache_clear()
    yield
    host_info.get_firmware_version.cache_clear()


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["powershell"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_windows_uses_bios_version(monkeypatch) -> None:
    """Windows reports the SMBIOS/BIOS version, not the OS build."""
    monkeypatch.setattr(host_info.platform, "system", lambda: "Windows")
    monkeypatch.setattr(host_info.platform, "version", lambda: "10.0.26100")
    with patch.object(
        host_info.subprocess, "run", return_value=_completed("1.14.0\r\n")
    ) as run:
        assert host_info.get_firmware_version() == "1.14.0"
    query = " ".join(run.call_args.args[0])
    assert "Win32_BIOS" in query
    assert "SMBIOSBIOSVersion" in query


def test_windows_falls_back_when_bios_query_fails(monkeypatch) -> None:
    """A failed PowerShell query falls back to the OS build."""
    monkeypatch.setattr(host_info.platform, "system", lambda: "Windows")
    monkeypatch.setattr(host_info.platform, "version", lambda: "10.0.26100")
    with patch.object(
        host_info.subprocess, "run", return_value=_completed("", returncode=1)
    ):
        assert host_info.get_firmware_version() == "10.0.26100"


def test_windows_falls_back_when_powershell_is_unavailable(monkeypatch) -> None:
    """A missing PowerShell binary does not break registration."""
    monkeypatch.setattr(host_info.platform, "system", lambda: "Windows")
    monkeypatch.setattr(host_info.platform, "version", lambda: "10.0.26100")
    with patch.object(host_info.subprocess, "run", side_effect=OSError("missing")):
        assert host_info.get_firmware_version() == "10.0.26100"


def test_non_windows_does_not_shell_out(monkeypatch) -> None:
    """Other platforms use the OS build without spawning PowerShell."""
    monkeypatch.setattr(host_info.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(host_info.platform, "version", lambda: "24.6.0")
    with patch.object(host_info.subprocess, "run") as run:
        assert host_info.get_firmware_version() == "24.6.0"
    run.assert_not_called()


def test_windows_bios_version_is_capped_for_the_db_column(monkeypatch) -> None:
    """Overlong OEM strings are truncated to the VARCHAR(50) column size."""
    monkeypatch.setattr(host_info.platform, "system", lambda: "Windows")
    with patch.object(host_info.subprocess, "run", return_value=_completed("A" * 80)):
        assert host_info.get_firmware_version() == "A" * 50
