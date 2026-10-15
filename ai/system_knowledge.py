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

    def get_system_overview(self, max_chars: int = 1800) -> str:
        """Get a high-level overview of the system from README.md.

        Capped at ``max_chars`` (trimmed to a line boundary). The README intro
        is only background, and the LLM prompt is evaluated on every request, so
        keeping this small keeps answers fast on CPU-only hosts.
        """
        readme_path = os.path.join(self.root_path, "README.md")
        try:
            if os.path.exists(readme_path):
                with open(readme_path, "r") as f:
                    content = f.read()
                # Read until the first major section, then cap to a bound.
                lines = content.split("\n")
                summary = []
                for line in lines:
                    if line.startswith("## Project Structure"):
                        break
                    summary.append(line)
                text = "\n".join(summary)
                if len(text) > max_chars:
                    text = text[:max_chars].rsplit("\n", 1)[0] + "\n  ... (truncated)"
                return text
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

    def get_database_schema_info(
        self, max_cols_per_table: int = 15, max_chars: int = 4500
    ) -> str:
        """Extract a compact database schema from the SQLAlchemy models.

        Lists table names with their first ``max_cols_per_table`` columns and
        caps the whole block at ``max_chars``. The full column-by-column dump is
        ~12k chars and dominated the prompt, slowing every request on CPU hosts;
        this keeps the useful shape (tables + key columns) at a fraction of the
        size.
        """
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
                    col_count = 0
                    for line in lines:
                        line = line.strip()
                        if line.startswith("class ") and "(Base)" in line:
                            current_table = line.split("class ")[1].split("(")[0]
                            col_count = 0
                            schema.append(f"\nTable: {current_table}")
                        elif current_table and " = Column(" in line:
                            if col_count >= max_cols_per_table:
                                continue
                            col_count += 1
                            # Extract column name and type roughly
                            col_name = line.split(" = ")[0]
                            col_def = line.split("Column(")[1].split(")")[0]
                            schema.append(f"  - {col_name}: {col_def}")
            except Exception as e:
                logger.error(f"Failed to parse model file {rel_path}: {e}")

        text = "\n".join(schema)
        if len(text) > max_chars:
            text = text[:max_chars].rsplit("\n", 1)[0] + "\n  ... (truncated)"
        return text

    def get_full_system_context(self) -> str:
        """Combine overview, structure, and DB schema into a single context string."""
        return (
            f"SYSTEM IDENTITY:\n{self.get_system_overview()}\n\n"
            f"{self.get_database_schema_info()}\n\n"
            f"{self.get_project_structure()}"
        )

    def get_system_prompt(self) -> str:
        """Build the full static system prompt sent to the LLM.

        Centralised here so the startup warm-up (see
        ``backend/src/homepot/app/main.py``) can prime Ollama's KV cache with
        the *exact* same prefix the request path uses -- otherwise the first
        real query pays the whole prompt-eval cost (tens of seconds on CPU).
        """
        system_knowledge = self.get_full_system_context()
        doc_context = self.get_documentation_context()
        if doc_context:
            system_knowledge += f"\n\n{doc_context}"
        cmd_ref = self.get_command_payload_reference()
        if cmd_ref:
            system_knowledge += f"\n\n{cmd_ref}"

        return (
            "IDENTITY:\n"
            "You are the HOMEPOT System Diagnostics AI, an advanced operational "
            "assistant for the HOMEPOT Client ecosystem.\n"
            "Your goal is to monitor, diagnose, and explain the behavior of "
            "IoT devices, sites, and the platform itself.\n\n"
            "CAPABILITIES & DATA SOURCES:\n"
            "1. Real-Time Database (PostgreSQL): You have access to live device "
            "metrics, site status, and push notification stats.\n"
            "2. Long-Term Memory (ChromaDB): You can recall past anomalies, "
            "error patterns, and resolutions to identify recurring issues.\n"
            "3. System Knowledge: You are self-aware of the codebase structure, "
            "file locations, and documentation.\n"
            "4. Short-Term Memory: You maintain context of the current conversation.\n"
            "5. AI Insights: anomaly detection and failure-prediction signals are "
            "provided in [AI INSIGHTS: ...] blocks.\n\n"
            "SYSTEM CONTEXT:\n"
            f"{system_knowledge}\n\n"
            "INSTRUCTIONS:\n"
            "- Scope your answers to the HOMEPOT system. Do not answer unrelated "
            "general knowledge questions.\n"
            "- Use the provided [CURRENT SYSTEM STATUS], [AI INSIGHTS: ...], and "
            "[RELEVANT MEMORIES] blocks to ground your answers in facts.\n"
            "- If you don't know something, admit it. Do not hallucinate system details.\n"
            "- When listing alerts, use the explicit 'ID' field provided in "
            "the [ACTIVE SYSTEM ALERTS] section. Format as '#ID'. Do not guess IDs.\n"
            "- Uncertainty protocol: if telemetry or context evidence is incomplete, "
            "state the gap explicitly instead of extrapolating an unsupported system state.\n"
            "- Trust protocol: your context includes a [VALIDATION TRUST STATUS] block. "
            "If 'Actionable' is 'no', you MUST explicitly tell the user their data could "
            "not be fully validated (name the failed gate and trust score) and limit your "
            "answer to cautionary, non-actionable observations -- never phrase a low-trust "
            "answer as a confirmed diagnosis or a directive to act. If a 'Reason' line is "
            "present, weave it in as ONE short supporting sentence (e.g. 'because telemetry "
            "is 340s stale') -- do not list every validation check or invent additional "
            "statistics beyond what's given.\n"
            "- Be concise: aim for at most ~150 words unless the user asks for more; do "
            "not restate the question or pad with pleasantries. Be professional and technical."
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
                    with open(full_path, "r", encoding="utf-8") as f:
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
   {"command_type": "update_config", "payload":
   {"data": {"config_url": "https://...", "config_version": "v2.1.0", "brightness": 75, "volume": 50}}}
   Permission: root_access

4. restart — Restart the device agent. No payload needed.
   {"command_type": "restart"}
   Permission: root_access

5. shutdown — Shut down the device agent. No payload needed.
   {"command_type": "shutdown"}
   Permission: root_access

6. run_command — Execute a shell command on the device.
   {"command_type": "run_command", "payload":
   {"data": {"command": "ls -la /tmp", "timeout_seconds": 30}}}
   Permission: root_access

7. run_script — Execute a script on the device.
   {"command_type": "run_script", "payload":
    {"data": {"script": "#!/bin/bash\\necho hello", "timeout_seconds": 30}
    }
   }
   Permission: root_access

8. status_request — Request current device status. No payload needed.
   {"command_type": "status_request"}
   Permission: none

9. list_processes — List running processes.
   {"command_type": "list_processes", "payload":
   {"data": {"sort_by": "cpu", "max_results": 50, "include_memory": true}}}
   Permission: process_monitoring

10. list_connections — List network connections.
    {"command_type": "list_connections", "payload": {"data": {"filter_state": "ESTABLISHED", "limit": 100}}}
    Permission: network_monitoring

11. scan_filesystem — Scan filesystem for files.
    {"command_type": "scan_filesystem", "payload":
    {"data": {"path": "/tmp", "max_depth": 2, "include_sizes": true}}}
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
Web Push: {"notification":
Example: {"root_access": true, "command_execution": true, "process_monitoring": false}

COMMAND STATUS LIFECYCLE:
pending -> sent -> completed | failed | expired | cancelled
"""
