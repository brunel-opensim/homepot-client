"""OS elevation layer for the real device agent.

The agent never receives blanket sudo. Managed ("root_access") elevation is
scoped to a single root-owned helper, ``homepot-ctl``, which can execute a
fixed allowlisted set of host operations as root and refuses anything else.

Lifecycle
---------
* **Install** (one-time, needs an OS admin prompt): the User App runs the
  bundled installer as root via ``osascript`` (macOS) or ``pkexec`` (Linux).
  It copies ``homepot-ctl`` into place and writes a NOPASSWD sudoers rule for
  the app user scoped **only** to that helper.
* **Provision/repair**: the agent re-runs ``sudo -n homepot-ctl
  ensure-allowlist`` whenever the grant is present. This can only repair the
  allowlist file; re-creating a removed sudoers drop-in requires the one-time
  installer because no rule exists any more.
* **Teardown (autonomous)**: when ``root_access`` is revoked the agent runs
  ``sudo -n homepot-ctl deprovision``, removing the drop-in and allowlist
  without any admin prompt. No lingering NOPASSWD rule survives a revoke.

All paths are redirected via ``HOMEPOT_ELEVATION_ROOT`` in tests so nothing
touches ``/etc`` on developer machines.
"""

import json
import logging
import os
import platform
import subprocess  # noqa: S404 - fixed argv list, no shell
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CTL_PATH_ENV = "HOMEPOT_CTL_PATH"
ELEVATION_ROOT_ENV = "HOMEPOT_ELEVATION_ROOT"

SUPPORTED_PLATFORMS = ("darwin", "linux")

# The only host operations the elevation helper may perform as root.
ALLOWED_OPS: tuple[str, ...] = ("restart", "shutdown")

FREE_FORM_COMMANDS = ("run_command", "run_script")

REFUSAL_MESSAGE = (
    "free-form command execution is not allowlisted on this device's OS; "
    "only predefined power operations (restart/shutdown) can be elevated"
)


def elevation_root() -> str:
    """Return the install root (redirectable for tests/packaging)."""
    return os.environ.get(ELEVATION_ROOT_ENV, "/usr/local/homepot")


def ctl_path() -> str:
    """Return the path to the ``homepot-ctl`` helper binary."""
    return os.environ.get(CTL_PATH_ENV) or os.path.join(elevation_root(), "homepot-ctl")


def dropin_path() -> str:
    """Return the path of the scoped sudoers drop-in file."""
    root = os.environ.get(ELEVATION_ROOT_ENV)
    if root:
        return os.path.join(root, "sudoers.d", "homepot")
    return "/etc/sudoers.d/homepot"


def allowlist_path() -> str:
    """Return the path of the root-owned allowlist file."""
    root = os.environ.get(ELEVATION_ROOT_ENV)
    if root:
        return os.path.join(root, "allowlist.json")
    return "/etc/homepot/allowlist.json"


def is_elevation_supported() -> bool:
    """Whether this platform can host the scoped elevation layer."""
    if os.name == "nt":
        return False
    return platform.system().lower() in SUPPORTED_PLATFORMS


def is_elevation_installed() -> bool:
    """Whether ``homepot-ctl`` is present on disk."""
    return os.path.isfile(ctl_path())


def is_provisioned() -> bool:
    """Whether the scoped sudoers drop-in currently exists."""
    return os.path.isfile(dropin_path())


def elevation_status() -> Dict[str, Any]:
    """Return the local elevation state as a status dict."""
    return {
        "supported": is_elevation_supported(),
        "installed": is_elevation_installed(),
        "provisioned": is_provisioned(),
        "ops": list(ALLOWED_OPS),
        "ctl_path": ctl_path(),
        "dropin_path": dropin_path(),
    }


def _run_ctl(argv: list[str]) -> Dict[str, Any]:
    """Run ``sudo -n homepot-ctl <...>`` and return a result dict."""
    cmd = ["sudo", "-n", ctl_path(), *argv]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv list, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def provision_elevation() -> Dict[str, Any]:
    """Repair the allowlist while a grant is present.

    Re-creating a missing sudoers drop-in is impossible without an admin
    prompt (there is no rule to go through ``sudo -n``), so when the drop-in
    is gone this returns ``reinstall_required`` for the User App to run the
    one-time installer. Returns ``{"provisioned": True}`` when the grant's OS
    state is in place.
    """
    if not is_elevation_supported():
        return {"provisioned": False, "reason": "os_unsupported"}
    if not is_elevation_installed():
        return {"provisioned": False, "reason": "not_installed"}
    if not is_provisioned():
        return {"provisioned": False, "reason": "reinstall_required"}
    outcome = _run_ctl(["ensure-allowlist"])
    return {
        "provisioned": bool(outcome["ok"]),
        "reason": (
            None
            if outcome["ok"]
            else f"ctl error: {outcome.get('stderr') or outcome.get('error')}"
        ),
    }


def deprovision_elevation() -> bool:
    """Autonomously remove the scoped elevation (no admin prompt needed).

    Uses the existing NOPASSWD rule for ``homepot-ctl`` to remove the drop-in
    and allowlist. Returns ``True`` when the OS no longer grants the helper
    (or never did).
    """
    if not is_elevation_supported():
        return True
    if not is_elevation_installed():
        return True
    outcome = _run_ctl(["deprovision"])
    if outcome["ok"] or not is_provisioned():
        return True
    logger.warning(
        "Deprovision failed: %s", outcome.get("stderr") or outcome.get("error")
    )
    return False


def sync_os_elevation(permissions: Optional[Dict[str, bool]]) -> None:
    """Reconcile the local OS elevation with the backend permission state.

    Best-effort and idempotent: while ``root_access`` is granted the allowlist
    is kept in place; once revoked the sudoers drop-in and allowlist are torn
    down autonomously. Failures shorten to a warning — the backend permission
    gate still blocks dispatch independently of the OS state.
    """
    if not is_elevation_supported():
        return
    granted = bool((permissions or {}).get("root_access", False))
    try:
        if granted:
            if not is_provisioned():
                logger.info(
                    "Elevation not provisioned while root_access granted; app must run installer"
                )
                return
            if not os.path.isfile(allowlist_path()):
                provision_elevation()
        elif is_provisioned():
            if deprovision_elevation():
                logger.info("Managed elevation deprovisioned (root_access revoked)")
            else:
                logger.warning("Failed to deprovision managed elevation")
    except Exception as exc:  # noqa: BLE001 - reconcile must never crash the loop
        logger.warning("Elevation reconcile failed: %s", exc)


def elevated_command_argv(command_type: str) -> Optional[list[str]]:
    """Return the argv used to elevate a fixed host operation.

    Returns ``None`` when elevation is not available on this platform, the
    helper is not installed, or the operation is not allowlisted.
    """
    if not is_elevation_supported():
        return None
    if command_type not in ALLOWED_OPS:
        return None
    if not is_elevation_installed():
        return None
    return ["sudo", "-n", ctl_path(), "run", command_type]


def allowlist_refusal(command_type: str) -> Optional[str]:
    """Return an error message when a command must be refused on this OS.

    Free-form ``run_command`` / ``run_script`` can no longer run arbitrary
    root commands on macOS/Linux real devices; the elevation helper only
    covers the fixed power operations. Returns ``None`` when the command is
    allowed to proceed.
    """
    if command_type not in FREE_FORM_COMMANDS:
        return None
    if not is_elevation_supported():
        return None
    return REFUSAL_MESSAGE


def parse_ctl_status(output: str) -> Dict[str, Any]:
    """Parse ``homepot-ctl status`` JSON output into a dict."""
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        pass
    return {}
