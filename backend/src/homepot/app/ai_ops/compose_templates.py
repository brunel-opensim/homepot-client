# flake8: noqa: E501
"""Compose Command templates shared between the Dashboard and the AI.

The Dashboard's Compose Command page (frontend/src/pages/Device/PushReview.jsx)
used to hard-code these presets. They now live here so the backend, the AI
system prompt, and the Dashboard all read from one source of truth. The
Dashboard fetches them via GET /api/v1/ai/compose-templates; the AI gets them
injected into its system prompt (see homepot.ai.system_knowledge).

Each template mirrors the shape consumed by PushReview:
    {
      "label": str,
      "action": str,           # ACTION_REGISTRY key
      "permission": str,
      "defaultData": dict,
      "defaultDataByOS": {os: dict},   # optional
      "description": str,
    }
"""

from typing import Any, Dict

COMPOSE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "RUN_COMMAND": {
        "label": "Run Command",
        "action": "run_command",
        "group": "Run Commands",
        "permission": "root_access",
        "defaultData": {"command": "uname -a", "timeout_seconds": 30},
        "defaultDataByOS": {
            "windows": {"command": "systeminfo"},
            "macos": {"command": "sw_vers"},
        },
        "description": "Run a command with elevated privileges using the target device's shell (PowerShell on Windows, sh on macOS/Linux).",
    },
    "RUN_SCRIPT": {
        "label": "Run Script",
        "action": "run_script",
        "group": "Run Commands",
        "permission": "root_access",
        "defaultData": {"script": "#!/bin/sh\nid", "timeout_seconds": 30},
        "defaultDataByOS": {
            "windows": {"script": "Get-Process | Select-Object -First 5 Name, Id, CPU"}
        },
        "description": "Run a script with elevated privileges using the target device's shell (PowerShell on Windows, POSIX sh on macOS/Linux).",
    },
    "RUN_COMMAND_UNPRIVILEGED": {
        "label": "Run Command (Unprivileged)",
        "action": "run_command_unprivileged",
        "group": "Run Commands",
        "permission": "command_execution",
        "defaultData": {"command": "ipconfig", "timeout_seconds": 30},
        "defaultDataByOS": {
            "windows": {"command": "ipconfig"},
            "linux": {"command": "uname -a"},
            "macos": {"command": "sw_vers"},
        },
        "description": "Run a command as the unprivileged device user (no elevation, PowerShell on Windows, sh on macOS/Linux).",
    },
    "APPLY_CONFIG": {
        "label": "Apply Configuration",
        "action": "update_config",
        "group": "Configuration",
        "permission": "root_access",
        "defaultData": {"volume": 50, "brightness": 75},
        "description": "Update system settings with root privileges. Volume uses the Windows legacy audio API (may not move the modern master slider on all systems); brightness uses DDC/CI with a WMI fallback and reports failure when the panel does not support software control.",
    },
    "REBOOT_SYSTEM": {
        "label": "Reboot System",
        "action": "restart",
        "group": "System",
        "permission": "root_access",
        "defaultData": {},
        "description": "Reboot the system the User App runs on. The reboot begins immediately.",
    },
    "RESTART_AGENT": {
        "label": "Restart Agent",
        "action": "restart_agent",
        "group": "Services & Agent",
        "permission": "root_access",
        "defaultData": {},
        "description": "Restart the agent process itself. The User App supervisor respawns it, briefly interrupting heartbeat and telemetry. Use for an online-but-misbehaving agent.",
    },
    "UPDATE_APP": {
        "label": "Update User App",
        "action": "update_app",
        "group": "Services & Agent",
        "permission": "root_access",
        "defaultData": {},
        "description": "Update the HOMEPOT User App to the latest published release. The app checks the server-hosted feed, downloads, and restarts to install in one action. Briefly interrupts telemetry during the restart.",
    },
    "ROLLBACK_APP": {
        "label": "Roll Back User App",
        "action": "rollback_app",
        "group": "Services & Agent",
        "permission": "root_access",
        "defaultData": {},
        "description": "Roll the HOMEPOT User App back to the previously served release. The app checks the server-hosted previous channel, downloads, and restarts to install the older version in one action. Use only when a newly installed release is broken.",
    },
    "UPDATE_FIRMWARE": {
        "label": "Update Firmware",
        "action": "update_config",
        "group": "Configuration",
        "permission": "root_access",
        "defaultData": {
            "version": "2.4.0",
            "url": "https://homepot.cabera.com/firmware/demo-firmware-2.4.0.bin",
            "checksum": "sha256:a079d6bb4d884cc7571769ad5f6a79164324f93e894a68cfec88ae2ed6bf043e",
        },
        "description": "Download and verify the HomePot demo firmware artifact (hosted on the demo server). The artifact is staged and discarded; nothing is flashed. Replace the URL and checksum with a vendor artifact for real updates.",
    },
    "START_PROGRAM": {
        "label": "Start Program",
        "action": "start_program",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"path": "notepad.exe", "args": []},
        "description": "Launch a program on the device in the background. Provide an absolute path (or a name on PATH) and optional arguments.",
    },
    "STOP_PROGRAM": {
        "label": "Stop Program",
        "action": "stop_program",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"name": "notepad.exe", "force": False},
        "description": "Stop a running process by name or PID. Set force to terminate immediately. Critical system processes are never stopped.",
    },
    "BOOTSTRAP_WINGET": {
        "label": "Bootstrap Winget (App Installer)",
        "action": "bootstrap_winget",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"timeout_seconds": 300},
        "description": "Ensure winget (App Installer) is installed on the Windows device. Run once per device before using Install/Update/Uninstall Program on Windows 10 builds where App Installer is missing.",
    },
    "INSTALL_PROGRAM": {
        "label": "Install Program",
        "action": "install_program",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
        "description": "Install a program on the Windows device via winget (silent, machine-wide).",
    },
    "UNINSTALL_PROGRAM": {
        "label": "Uninstall Program",
        "action": "uninstall_program",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
        "description": "Uninstall a program from the Windows device via winget (silent).",
    },
    "LIST_INSTALLED_PROGRAMS": {
        "label": "List Installed Programs",
        "action": "list_installed_programs",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {},
        "description": "List the programs installed on the Windows device with their install locations (from the registry). Use the location to find executables for Start/Stop Program.",
    },
    "UPDATE_PROGRAM": {
        "label": "Update Program",
        "action": "update_program",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"package": "Notepad++.Notepad++", "timeout_seconds": 300},
        "description": "Update a program on the Windows device via winget (silent).",
    },
    "UPGRADE_ALL_PROGRAMS": {
        "label": "Upgrade All Programs",
        "action": "upgrade_all_programs",
        "group": "Programs",
        "permission": "root_access",
        "defaultData": {"timeout_seconds": 600},
        "description": "Upgrade all installed programs on the Windows device via winget (silent).",
    },
    "HEALTH_CHECK": {
        "label": "Health Check",
        "action": "health_check",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {"tests": ["network", "storage", "memory"]},
        "description": "Execute self-tests (network/storage/memory) and report pass/fail.",
    },
    "LIST_PROCESSES": {
        "label": "List Processes",
        "action": "list_processes",
        "group": "Diagnostics",
        "permission": "process_monitoring",
        "defaultData": {"max_results": 50, "sort_by": "cpu", "include_memory": True},
        "description": "List the running processes on the device.",
    },
    "LIST_CONNECTIONS": {
        "label": "List Network Connections",
        "action": "list_connections",
        "group": "Diagnostics",
        "permission": "network_monitoring",
        "defaultData": {"filter_state": "ESTABLISHED", "limit": 100},
        "description": "List the device's active network connections.",
    },
    "LIST_DRIVES": {
        "label": "List Drives",
        "action": "list_drives",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {},
        "description": "List mounted drives/volumes and their free space.",
    },
    "TAIL_SYSTEM_LOG": {
        "label": "Tail System Log",
        "action": "tail_system_log",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {"lines": 50},
        "description": "Read the most recent OS error/warning events (Windows Event Log, journalctl, or macOS unified log).",
    },
    "NETWORK_TEST": {
        "label": "Network Test",
        "action": "network_test",
        "group": "Diagnostics",
        "permission": "network_monitoring",
        "defaultData": {"host": "example.com", "timeout_seconds": 10},
        "description": "Probe a host's connectivity (DNS, ping, optional TCP port).",
    },
    "LIST_SESSIONS": {
        "label": "List Sessions",
        "action": "list_sessions",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {},
        "description": "List users currently logged into the device.",
    },
    "GET_SYSTEM_INFO": {
        "label": "Get System Info",
        "action": "get_system_info",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {},
        "description": "Return a hardware/OS inventory snapshot (CPU, RAM, OS build, and on Windows serial/model/GPU).",
    },
    "COLLECT_SUPPORT_BUNDLE": {
        "label": "Collect Support Bundle",
        "action": "collect_support_bundle",
        "group": "Diagnostics",
        "permission": "command_execution",
        "defaultData": {},
        "description": "Bundle hardware/OS, disk, process, and metrics snapshots into a single zip support artifact.",
    },
    "SCAN_FILESYSTEM": {
        "label": "Scan Filesystem",
        "action": "scan_filesystem",
        "group": "Diagnostics",
        "permission": "root_access",
        "defaultData": {"path": "/var/homepot", "max_depth": 3, "include_sizes": True},
        "defaultDataByOS": {"windows": {"path": "C:\\ProgramData\\Homepot"}},
        "description": "Scan the system filesystem for files with elevated privileges.",
    },
    "SHUT_DOWN": {
        "label": "Shut Down System",
        "action": "shutdown",
        "group": "System",
        "permission": "root_access",
        "defaultData": {},
        "description": "Shut down the system the User App runs on. The shutdown begins immediately.",
    },
    "DISK_CLEANUP": {
        "label": "Disk Cleanup",
        "action": "disk_cleanup",
        "group": "System",
        "permission": "command_execution",
        "defaultData": {"max_age_days": 7},
        "description": "Clear old temp files and caches from the system temp directory to reclaim disk space.",
    },
    "LOCK_SCREEN": {
        "label": "Lock Screen",
        "action": "lock_screen",
        "group": "System",
        "permission": "command_execution",
        "defaultData": {},
        "description": "Lock the terminal's screen (session lock). The person at the device unlocks it with their credentials.",
    },
    "RESTART_SERVICE": {
        "label": "Restart Service",
        "action": "restart_service",
        "group": "Services & Agent",
        "permission": "root_access",
        "defaultData": {"service_name": "Spooler"},
        "defaultDataByOS": {
            "linux": {"service_name": "cron"},
            "macos": {"service_name": "com.apple.mDNSResponder"},
        },
        "description": "Restart a named OS service (Windows service, systemd unit, or launchd label) with root privileges.",
    },
    "SET_SERVICE_STATE": {
        "label": "Set Service State",
        "action": "set_service_state",
        "group": "Services & Agent",
        "permission": "root_access",
        "defaultData": {"service_name": "Spooler", "action": "start"},
        "description": "Enable, disable, start, or stop a named OS service (Windows service, systemd unit, or launchd label) with root privileges.",
    },
    "NOTIFY_USER": {
        "label": "Notify User",
        "action": "notify_user",
        "group": "Services & Agent",
        "permission": "command_execution",
        "defaultData": {"title": "HOMEPOT", "message": "Please reboot the terminal."},
        "description": "Show a message to the person at the device (operator-to-user channel).",
    },
}


def compose_templates_reference() -> str:
    """Render the templates as a human-readable reference for the AI system prompt."""
    lines = [
        "[COMPOSE COMMAND TEMPLATES]",
        "The Dashboard's Compose Command page offers these presets. When a technician asks for a payload, reference the matching template (label + default params) or provide the raw JSON.",
        "",
    ]
    for key, t in COMPOSE_TEMPLATES.items():
        lines.append(f"- {t['label']} ({key}) -> action: {t['action']}")
        lines.append(f"  default params: {t['defaultData']}")
        if t.get("defaultDataByOS"):
            lines.append(f"  OS overrides: {t['defaultDataByOS']}")
        lines.append(f"  {t['description']}")
        lines.append("")
    return "\n".join(lines)
