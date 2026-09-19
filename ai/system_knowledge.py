"""System Knowledge Service - Provides self-awareness to the AI.

This module gathers static information about the system structure, codebase,
and documentation to give the AI context about "what it is" and "where it lives".
"""

import logging
import os

logger = logging.getLogger(__name__)


class SystemKnowledge:
    """Service for retrieving system architecture and codebase structure."""

    def __init__(self, root_path: str) -> None:
        """Initialize with the project root path."""
        self.root_path = root_path

    def get_system_overview(self) -> str:
        """Get a high-level overview of the system from README.md."""
        readme_path = os.path.join(self.root_path, "README.md")
        try:
            if os.path.exists(readme_path):
                with open(readme_path, "r") as f:
                    content = f.read()
                    # Extract the first 50 lines or until the first major section
                    lines = content.split("\n")
                    summary = []
                    for line in lines:
                        if line.startswith("## Project Structure"):
                            break
                        summary.append(line)
                    return "\n".join(summary)
            return "System overview not available."
        except Exception as e:
            logger.error(f"Failed to read README.md: {e}")
            return "Error reading system overview."

    def get_project_structure(self) -> str:
        """Scan the directory to generate a tree view of key components."""
        structure = ["Project Structure:"]

        # Define key directories to scan
        key_dirs = {
            "backend/src/homepot": "Backend Core",
            "frontend/src/pages": "Frontend Pages",
            "ai": "AI Services",
            "docs": "Documentation",
        }

        for rel_path, description in key_dirs.items():
            full_path = os.path.join(self.root_path, rel_path)
            if os.path.exists(full_path):
                structure.append(f"\n{description} ({rel_path}):")
                try:
                    # List files, excluding __pycache__ and hidden files
                    files = sorted(
                        [
                            f
                            for f in os.listdir(full_path)
                            if not f.startswith(".") and not f.startswith("__")
                        ]
                    )
                    # Limit to top 15 files to avoid context overflow
                    for f in files[:15]:
                        structure.append(f"  - {f}")
                    if len(files) > 15:
                        structure.append(f"  - ... ({len(files) - 15} more)")
                except Exception as e:
                    structure.append(f"  - Error scanning: {e}")

        return "\n".join(structure)

    def get_database_schema_info(self) -> str:
        """Extract database schema from SQLAlchemy models."""
        schema = ["Database Schema (derived from SQLAlchemy models):"]

        model_files = [
            "backend/src/homepot/models.py",
            "backend/src/homepot/app/models/AnalyticsModel.py",
        ]

        for rel_path in model_files:
            full_path = os.path.join(self.root_path, rel_path)
            if not os.path.exists(full_path):
                continue

            try:
                with open(full_path, "r") as f:
                    content = f.read()
                    lines = content.split("\n")

                    current_table = None
                    for line in lines:
                        line = line.strip()
                        if line.startswith("class ") and "(Base)" in line:
                            current_table = line.split("class ")[1].split("(")[0]
                            schema.append(f"\nTable: {current_table}")
                        elif current_table and " = Column(" in line:
                            # Extract column name and type roughly
                            col_name = line.split(" = ")[0]
                            col_def = line.split("Column(")[1].split(")")[0]
                            schema.append(f"  - {col_name}: {col_def}")
            except Exception as e:
                logger.error(f"Failed to parse model file {rel_path}: {e}")

        return "\n".join(schema)

    def get_full_system_context(self) -> str:
        """Combine overview, structure, and DB schema into a single context string."""
        return (
            f"SYSTEM IDENTITY:\n{self.get_system_overview()}\n\n"
            f"{self.get_database_schema_info()}\n\n"
            f"{self.get_project_structure()}"
        )

    def get_documentation_context(self, max_chars_per_doc: int = 500) -> str:
        """Read key documentation files and return token-efficient summaries.

        Provides the LLM with procedural knowledge from the project's docs
        so it can reference documented behaviors, thresholds, and workflows
        when answering diagnostics questions.

        Args:
            max_chars_per_doc: Maximum characters to extract from each doc.
        """
        doc_files = [
            "docs/ai-validation-gates.md",
            "docs/device-metrics-collection.md",
            "docs/ai-implementation.md",
            "docs/device-credentials-and-tokens.md",
            "docs/anomaly-detection.md",
        ]

        parts = ["[DOCUMENTATION]"]
        for rel_path in doc_files:
            full_path = os.path.join(self.root_path, rel_path)
            try:
                if os.path.exists(full_path):
                    with open(full_path, "r") as f:
                        content = f.read(max_chars_per_doc)
                    # Trim to last complete line within the limit
                    truncated = content.rfind("\n")
                    if truncated > 0:
                        content = content[:truncated]
                    parts.append(f"--- {rel_path} ---\n{content}")
            except Exception as e:
                logger.warning("Failed to read doc %s: %s", rel_path, e)

        if len(parts) == 1:
            return ""
        return "\n\n".join(parts)

    def get_command_payload_reference(self) -> str:
        """Return a structured reference of all command types and their payloads.

        Gives the LLM the schema knowledge needed to generate valid push
        notification payloads and device command JSON for technicians.
        """
        return _COMMAND_PAYLOAD_REFERENCE


_COMMAND_PAYLOAD_REFERENCE = """[COMMAND PAYLOAD REFERENCE]
The system supports these device command types. Each command is sent
via POST /api/v1/devices/{device_id}/commands as JSON.
The push notification payload wraps these commands for delivery over
FCM, APNs, Web Push, MQTT, or WNS.

COMMAND TYPES AND PAYLOADS:

1. ping — Lightweight connectivity check. No payload needed.
   {"command_type": "ping"}
   Permission: none

2. health_check — Run device health diagnostics.
   {"command_type": "health_check", "payload": {"data": {"tests": ["network", "storage", "memory", "cpu"]}}}
   Permission: command_execution

3. update_config — Push new configuration to the device.
   {"command_type": "update_config", "payload": {"data": {"config_url": "https://...", "config_version": "v2.1.0", "brightness": 75, "volume": 50}}}
   Permission: root_access

4. restart — Restart the device agent. No payload needed.
   {"command_type": "restart"}
   Permission: root_access

5. shutdown — Shut down the device agent. No payload needed.
   {"command_type": "shutdown"}
   Permission: root_access

6. run_command — Execute a shell command on the device.
   {"command_type": "run_command", "payload": {"data": {"command": "ls -la /tmp", "timeout_seconds": 30}}}
   Permission: root_access

7. run_script — Execute a script on the device.
   {"command_type": "run_script", "payload": {"data": {"script": "#!/bin/bash\\necho hello", "timeout_seconds": 30}}}
   Permission: root_access

8. status_request — Request current device status. No payload needed.
   {"command_type": "status_request"}
   Permission: none

9. list_processes — List running processes.
   {"command_type": "list_processes", "payload": {"data": {"sort_by": "cpu", "max_results": 50, "include_memory": true}}}
   Permission: process_monitoring

10. list_connections — List network connections.
    {"command_type": "list_connections", "payload": {"data": {"filter_state": "ESTABLISHED", "limit": 100}}}
    Permission: network_monitoring

11. scan_filesystem — Scan filesystem for files.
    {"command_type": "scan_filesystem", "payload": {"data": {"path": "/tmp", "max_depth": 2, "include_sizes": true}}}
    Permission: root_access

12. request_permission — Agent requests a permission grant. No payload needed.
    {"command_type": "request_permission"}
    Permission: none

PUSH NOTIFICATION PAYLOAD WRAPPER:
When a command is delivered via push notification, the wire format is:
{
  "title": "Notification title",
  "body": "Notification body",
  "data": { ... command payload fields ... },
  "priority": "low|normal|high|critical",
  "ttl_seconds": 300,
  "collapse_key": "grouping-key-or-null"
}

The "data" field carries the command-specific payload. The agent reads
"data.action" to determine the command type, and "data" for the rest.

PLATFORM-SPECIFIC WIRE FORMATS:

MQTT: {"title": "...", "body": "...", "data": {...}, "priority": "high", "ttl": 300, "message_id": "uuid"}
Web Push: {"notification": {"title": "...", "body": "...", "data": {...}, "requireInteraction": true, "tag": "..."}}
FCM: Uses the standard PushNotificationPayload fields directly.

DEVICE PERMISSIONS (device_permissions JSON on Device model):
Keys match the REQUIRED_PERMISSION map above. A device must have the
matching permission key set to true for the command to execute.
Example: {"root_access": true, "command_execution": true, "process_monitoring": false}

COMMAND STATUS LIFECYCLE:
pending -> sent -> completed | failed | expired | cancelled
"""
