r"""Platform-aware proxy configuration for the HOMEPOT agent.

Reads system proxy settings and returns a configuration suitable for
``httpx.AsyncClient(proxy=...)``.

**Cross-platform (env vars):**
    Respects ``HTTP_PROXY``, ``HTTPS_PROXY``, ``NO_PROXY`` environment
    variables on all platforms.

**Windows IE proxy:**
    Reads Internet Explorer / system proxy settings from the Windows
    registry (``HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings``).
    This is the same source that ``WinHttpGetIEProxyConfigForCurrentUser``
    and most Windows applications use.

**Linux/macOS:**
    Only environment variables are consulted.  Desktop environments
    (GNOME, KDE) may set ``HTTP_PROXY``/``HTTPS_PROXY`` automatically.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Environment-variable lookup (all platforms)
# ---------------------------------------------------------------------------


def _env_proxy() -> Dict[str, Optional[str]]:
    """Read proxy settings from environment variables.

    Returns
    -------
    dict with keys ``http``, ``https``, ``no_proxy``.
    Values are ``None`` when the respective variable is not set.
    """
    return {
        "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
        "no_proxy": os.environ.get("NO_PROXY") or os.environ.get("no_proxy"),
    }


# ---------------------------------------------------------------------------
# Windows IE/System proxy (registry)
# ---------------------------------------------------------------------------


def _windows_ie_proxy() -> Dict[str, Optional[str]]:
    r"""Read Internet Explorer / system proxy from the Windows registry.

    Reads ``HKCU\Software\Microsoft\Windows\CurrentVersion\Internet
    Settings``.

    Returns
    -------
    dict with keys ``http``, ``https``, ``no_proxy``.
    All values are ``None`` if the registry key does not exist or
    proxy is disabled.
    """
    result: Dict[str, Optional[str]] = {
        "http": None,
        "https": None,
        "no_proxy": None,
    }

    winreg: Any
    try:
        import winreg as winreg  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        logger.debug("winreg not available (not Windows)")
        return result

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ
        ) as key:
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not proxy_enable:
                return result

            proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if not proxy_server:
                return result

            proxy_override, _ = winreg.QueryValueEx(key, "ProxyOverride")
            if proxy_override:
                result["no_proxy"] = proxy_override

            proxy_server = proxy_server.strip()

            if "=" not in proxy_server and ";" not in proxy_server:
                result["http"] = proxy_server
                result["https"] = proxy_server
            else:
                parts = proxy_server.replace(";", " ").split()
                for part in parts:
                    if "=" in part:
                        protocol, server = part.split("=", 1)
                        protocol = protocol.strip().lower()
                        server = server.strip()
                        if protocol == "http":
                            result["http"] = server
                        elif protocol == "https":
                            result["https"] = server
                        elif protocol == "socks":
                            result["http"] = server
                            result["https"] = server
    except (OSError, FileNotFoundError) as exc:
        logger.debug("Failed to read Windows IE proxy: %s", exc)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_proxy_settings() -> Dict[str, Optional[str]]:
    """Return the best available proxy configuration for the current platform.

    Priority:
    1. Environment variables ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``NO_PROXY``.
    2. Windows IE / system proxy (registry on Windows only).

    Returns
    -------
    dict with keys ``http``, ``https``, ``no_proxy``.
    """
    settings = _env_proxy()

    if any(settings.values()):
        logger.debug(
            "Using proxy from environment: http=%s https=%s",
            settings["http"],
            settings["https"],
        )
        return settings

    if sys.platform == "win32":
        ie_settings = _windows_ie_proxy()
        if any(ie_settings.values()):
            logger.debug(
                "Using proxy from Windows IE settings: http=%s https=%s",
                ie_settings["http"],
                ie_settings["https"],
            )
            return ie_settings

    return settings


def build_httpx_proxy_kwargs(
    settings: Optional[Dict[str, Optional[str]]] = None,
) -> Dict[str, Any]:
    """Build ``**kwargs`` for ``httpx.AsyncClient`` from proxy settings.

    Parameters
    ----------
    settings:
        Proxy settings dict as returned by ``get_proxy_settings()``.
        If ``None``, settings are auto-detected.

    Returns
    -------
    A dict suitable for ``httpx.AsyncClient(**build_httpx_proxy_kwargs())``.
    If no proxy is configured, returns an empty dict.
    """
    if settings is None:
        settings = get_proxy_settings()

    https_proxy = settings.get("https")
    if https_proxy:
        return {"proxy": https_proxy}

    http_proxy = settings.get("http")
    if http_proxy:
        return {"proxy": http_proxy}

    return {}
