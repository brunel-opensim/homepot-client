"""Host firmware/version helpers shared by the agent runtime."""

from functools import lru_cache
import platform
import subprocess  # noqa: S404

# ``devices.firmware_version`` is VARCHAR(50); keep the reported value inside
# the column even when an OEM returns an unusually long SMBIOS string.
_FIRMWARE_VERSION_MAX_LENGTH = 50
_WINDOWS_BIOS_TIMEOUT_SECONDS = 5


def _bios_version_from_windows() -> str:
    """Return the SMBIOS/BIOS version reported by Windows, or an empty string."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance -ClassName Win32_BIOS).SMBIOSBIOSVersion",
            ],
            capture_output=True,
            text=True,
            timeout=_WINDOWS_BIOS_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception:  # noqa: BLE001 - best-effort host detail
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        version = line.strip()
        if version:
            return version[:_FIRMWARE_VERSION_MAX_LENGTH]
    return ""


def _os_version_fallback() -> str:
    """Return the OS build/kernel version as a portable fallback."""
    try:
        version = platform.version()
        if version and version.strip():
            return version.strip()
    except Exception:  # noqa: BLE001 - best-effort host detail
        pass
    return f"{platform.system()} {platform.release()}".strip()


@lru_cache(maxsize=1)
def get_firmware_version() -> str:
    """Return a best-effort firmware version for the host.

    On Windows this is the platform firmware (BIOS/UEFI) version reported by
    ``Win32_BIOS.SMBIOSBIOSVersion``. A general-purpose OS has no single
    firmware value on other platforms, so the OS build/kernel version is used
    as the closest portable proxy.
    """
    if platform.system() == "Windows":
        bios_version = _bios_version_from_windows()
        if bios_version:
            return bios_version
    return _os_version_fallback()
