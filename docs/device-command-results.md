# Device Command Results: Feedback & Validation

Commands run on the device (Windows/macOS/Linux), but they only add value when
the raw output — stdout, stderr, exit code and the error message — comes back to
the people and systems that need it. This document is the reference for **how
command results flow back to the Dashboard and the AI**, and the checks to run
when re-validating that feedback path against later changes.

## Why this matters

A technician diagnosing a failed install needs the *error*, not just a red exit
code. The AI answering "why did this fail, and what should I do next?" needs the
same error plus the command that actually ran. Before PR #941 and PR #942, the
error was often hidden in the Dashboard, and the AI only saw a 150-character
JSON prefix of the result — so follow-ups were unreliable. This document
captures the corrected design so it can be re-validated.

## Result shape (device side)

Each command handler in `backend/src/homepot/agent/utils/command_poller.py`
returns `{status, result}`. The result dict is stored whole in
`device_commands.result` (JSON). Conventions:

| Field | Meaning |
|-------|---------|
| `error` | Human-readable failure reason (failure results). |
| `exit_code` | Process exit code (`0` = success), when applicable. |
| `stdout` / `stderr` | Captured output, clipped to the last 64 KB (`MAX_COMMAND_OUTPUT`). |
| `truncated` | True when stdout/stderr exceeded 64 KB. winget, bootstrap and program listing set this consistently. |
| `message` | Short human summary for some successes (e.g. winget bootstrap). |
| `results` | Per-key outcome for `update_config` / `health_check` (status/value/error per key). |
| `command_executed` | The literal OS command that ran, added by `process_command` via `_describe_executed_command` (e.g. `winget install -e --id 'Notepad++.Notepad++' --silent --accept-package-agreements --accept-source-agreements --scope machine`). |

Winget failure results also append an actionable hint ("winget is not installed
… run the `bootstrap_winget` command") when the cause is a missing App Installer.

## Flow

```mermaid
graph LR
    D[Device agent] -->|PUT /devices/{id}/status| B[Backend]
    B --> DB[(device_commands.result, JSON)]
    DB --> H[History list endpoint<br/>compact summary]
    DB --> X[Detail endpoint<br/>full result]
    H --> UI[Dashboard Device History]
    X --> UI
    DB --> CB[AI Context Builder<br/>summarize_command_result]
    DB --> T[AI get_command tool<br/>full result]
    V[Verifier] -->|step.error| P[Plan status]
```

## Dashboard feedback (PR #941)

- **List endpoint** `GET /devices/device/{device_id}/commands` honours `limit`
  (1–200, default 50) and `offset`, and returns a **compact result summary** per
  row: `error`, `message`, `exit_code`, `truncated`, `command_executed`, each
  string capped at 500 chars. stdout/stderr are *omitted* from the list so a
  5-second poll no longer ships megabytes of output.
- **Detail endpoint** `GET /devices/device/{device_id}/commands/{command_id}`
  returns the full result on demand. The Details modal fetches it when opened.
- **Rendering** (`frontend/src/pages/Device/DeviceHistory.jsx`): the error is
  shown prominently (not hidden behind stdout), nested `results` expose
  `value`/`error` with correct pass/fail colours, CRLF is normalised, and a
  "Load older commands" button pages past the first 50.

## AI feedback (PR #942)

- `ContextBuilder.get_command_context` emits an error-first **bounded summary**
  via `summarize_command_result` in `ai/context_builder.py`: `error`/`message`/
  exit code/`truncated`/`command_executed`, stdout/stderr tail-clipped (500
  chars), per-key `results`, and data-list results reduced to counts (e.g.
  `processes=42`).
- A **`get_command(device_id, command_id)` tool** (`ai/tools.py`) returns one
  command's full result (larger caps, 2000 chars) so the assistant can inspect a
  specific failure on demand.
- The **verifier** (`ai_ops/verifier.py`) records the device-reported reason on
  `step.error` for failed/expired/cancelled commands, so plan status
  (`get_action_plan_status`) and follow-ups carry the real reason instead of the
  generic `"step failed"`.

Note: the enriched context is still capped by `context_budget` (default 1000
chars) and the command blocks sit near the end of the block list, so under a
tight budget the summaries can be trimmed. The `get_command` tool is the
reliable path to full detail.

## Validation checklist

For each command type exercised on a real device, confirm:

1. A failed winget install shows its `error` (and exit code) in the Dashboard
   Details modal — not only stdout.
2. `GET /devices/device/{device_id}/commands?limit=…` returns at most that many
   rows, each with the compact summary (no stdout/stderr); the detail endpoint
   returns the full stdout/stderr.
3. Oversized winget/bootstrap/listing output sets `truncated`, and the Dashboard
   shows the truncation hint.
4. `command_executed` is the literal command (`winget install -e --id '…' …`),
   and `restart_service` reflects the device OS, not the server OS.
5. The AI can answer "why did install X fail?" and propose the correct follow-up
   (e.g. `bootstrap_winget`), via the summary and/or `get_command`.
6. A failed action plan's step error is the device-reported reason (or exit
   code), not `"step failed"`.

## Related

- [AI Context Builder](ai-context-builder.md)
- [Adding a Device Command](adding-a-device-command.md)
- [AI command payload and execution transparency](ai-command-payload-transparency.md)
