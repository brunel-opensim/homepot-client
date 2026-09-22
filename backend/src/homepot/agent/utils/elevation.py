"""OS elevation layer for the real device agent.

The agent never receives blanket sudo. Managed ("root_access") elevation is
scoped to a single root-owned helper, ``homepot-ctl``, which executes a fixed
allowlisted set of host operations as root (``restart``/``shutdown``) plus the
owner-authorized free-form ``exec`` op (a script read from stdin and run via
the shell). Everything else is refused.

Lifecycle
---------
* **Install** (one-time, needs an OS admin prompt): the User App runs the
  bundled installer as root via ``osascript`` (macOS), ``pkexec`` (Linux), or
  a UAC-elevated PowerShell command (Windows). It copies ``homepot-ctl`` into
  place and writes a NOPASSWD sudoers rule for the app user scoped **only**
  to that helper. On Windows, the helper is registered as a scheduled task
  that runs with SYSTEM privileges.
* **Provision/repair**: the agent re-runs ``sudo -n homepot-ctl
  ensure-allowlist`` (POSIX) or verifies the scheduled task exists (Windows)
  whenever the grant is present. This can only repair the allowlist file;
  re-creating a removed sudoers drop-in requires the one-time installer
  because no rule exists any more.
* **Teardown (autonomous)**: when ``root_access`` is revoked the agent runs
  ``sudo -n homepot-ctl deprovision`` (POSIX) or removes the scheduled task
  (Windows), removing the drop-in and allowlist without any admin prompt. No
  lingering NOPASSWD rule survives a revoke.

Consent model: the owner's ``root_access`` grant is the one authorization —
operators who reach this layer through the backend permission gate may run
power ops and free-form shell commands, and every command is audited. Revoking
the grant tears the layer down. All paths are redirected via
``HOMEPOT_ELEVATION_ROOT`` in tests so nothing touches ``/etc`` on developer
machines.
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

SUPPORTED_PLATFORMS = ("darwin", "linux", "windows")

# The only host operations the elevation helper may perform as root.
ALLOWED_OPS: tuple[str, ...] = ("restart", "shutdown", "exec")

# Helper op that carries free-form shell execution (script read from stdin).
EXEC_OP = "exec"

# Dispatch command types served by the free-form ``exec`` op.
FREE_FORM_COMMANDS = ("run_command", "run_script")

# Windows scheduled task name for the elevation helper.
WINDOWS_TASK_NAME = "HOMEPOT-Elevation"


def elevation_root() -> str:
    """Return the install root (redirectable for tests/packaging)."""
    env_root = os.environ.get(ELEVATION_ROOT_ENV)
    if env_root:
        return env_root
    if os.name == "nt":
        # On Windows, use ProgramData (typically C:\\ProgramData)
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        return os.path.join(program_data, "Homepot")
    return "/usr/local/homepot"


def ctl_path() -> str:
    """Return the path to the ``homepot-ctl`` helper binary."""
    env_path = os.environ.get(CTL_PATH_ENV)
    if env_path:
        return env_path
    root = elevation_root()
    if os.name == "nt":
        return os.path.join(root, "homepot-ctl.ps1")
    return os.path.join(root, "homepot-ctl")


def dropin_path() -> str:
    """Return the path of the scoped sudoers drop-in file (POSIX) or task marker (Windows)."""
    root = os.environ.get(ELEVATION_ROOT_ENV)
    if os.name == "nt":
        if root:
            return os.path.join(root, "elevation_installed.marker")
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        return os.path.join(program_data, "Homepot", "elevation_installed.marker")
    if root:
        return os.path.join(root, "sudoers.d", "homepot")
    return "/etc/sudoers.d/homepot"


def allowlist_path() -> str:
    """Return the path of the root-owned allowlist file."""
    root = os.environ.get(ELEVATION_ROOT_ENV)
    if os.name == "nt":
        if root:
            return os.path.join(root, "allowlist.json")
        program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
        return os.path.join(program_data, "Homepot", "allowlist.json")
    if root:
        return os.path.join(root, "allowlist.json")
    return "/etc/homepot/allowlist.json"


def is_elevation_supported() -> bool:
    """Whether this platform can host the scoped elevation layer."""
    return platform.system().lower() in SUPPORTED_PLATFORMS


def is_elevation_installed() -> bool:
    """Whether ``homepot-ctl`` is present on disk."""
    return os.path.isfile(ctl_path())


def is_provisioned() -> bool:
    """Whether the scoped sudoers drop-in or scheduled task marker exists."""
    if os.name == "nt":
        # On Windows, check for the scheduled task or marker file
        try:
            result = subprocess.run(  # noqa: S603, S607
                ["schtasks", "/query", "/tn", WINDOWS_TASK_NAME],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
        return os.path.isfile(dropin_path())
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
    """Run ``sudo -n homepot-ctl <...>`` (POSIX) or ``powershell <script>`` (Windows)."""
    if os.name == "nt":
        # On Windows, execute the PowerShell helper directly
        ctl = ctl_path()
        if not os.path.isfile(ctl):
            return {"ok": False, "error": f"Helper not found: {ctl}"}
        # Build PowerShell command: & 'C:\...\homepot-ctl.ps1' <args>
        ps_args = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ctl,
        ] + argv
        try:
            completed = subprocess.run(  # noqa: S603
                ps_args,
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
    # POSIX: use sudo
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
    if os.name == "nt":
        # On Windows, provision is a no-op if the task exists; just ensure
        # the allowlist file is in place.
        _ensure_windows_allowlist()
        return {"provisioned": True, "reason": None}
    outcome = _run_ctl(["ensure-allowlist"])
    return {
        "provisioned": bool(outcome["ok"]),
        "reason": (
            None
            if outcome["ok"]
            else f"ctl error: {outcome.get('stderr') or outcome.get('error')}"
        ),
    }


def _ensure_windows_allowlist() -> None:
    """Write the allowlist file on Windows."""
    allowlist = allowlist_path()
    os.makedirs(os.path.dirname(allowlist), exist_ok=True)
    with open(allowlist, "w") as f:
        f.write("op:restart\nop:shutdown\nop:exec\n")


def deprovision_elevation() -> bool:
    """Autonomously remove the scoped elevation (no admin prompt needed).

    Uses the existing NOPASSWD rule for ``homepot-ctl`` to remove the drop-in
    and allowlist. On Windows, removes the scheduled task and marker file.
    Returns ``True`` when the OS no longer grants the helper (or never did).
    """
    if not is_elevation_supported():
        return True
    if not is_elevation_installed():
        return True
    if os.name == "nt":
        # On Windows, remove the scheduled task and marker file
        try:
            subprocess.run(  # noqa: S603, S607
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_NAME, "/f"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        # Remove marker and allowlist
        marker = dropin_path()
        allowlist = allowlist_path()
        for path in (marker, allowlist):
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
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
    if os.name == "nt":
        # On Windows, execute the PowerShell helper directly (it runs via
        # the scheduled task or the elevated service context).
        return [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ctl_path(),
            "run",
            command_type,
        ]
    return ["sudo", "-n", ctl_path(), "run", command_type]


def elevated_exec_argv() -> Optional[list[str]]:
    """Return the argv used to elevate a free-form shell command.

    Free-form ``run_command`` / ``run_script`` on macOS/Linux real devices run
    through the same scoped helper (``homepot-ctl run exec``); the command or
    script text is piped on stdin and the helper runs it via the shell as
    root. On Windows, the PowerShell helper reads from stdin and executes via
    PowerShell. Returns ``None`` when elevation is not available on this
    platform or the helper is not installed.
    """
    if not is_elevation_supported():
        return None
    if not is_elevation_installed():
        return None
    if os.name == "nt":
        return [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            ctl_path(),
            "run",
            EXEC_OP,
        ]
    return ["sudo", "-n", ctl_path(), "run", EXEC_OP]


def parse_ctl_status(output: str) -> Dict[str, Any]:
    """Parse ``homepot-ctl status`` JSON output into a dict."""
    try:
        parsed = json.loads(output)
        if isinstance(parsed, dict):
            return parsed
    except (ValueError, TypeError):
        pass
    return {}
