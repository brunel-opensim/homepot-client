# AI query suggestions (design note)

This document captures a design discussion for providing curated query
suggestions in the HOMEPOT AI Ask interface. The goal is to help technicians
learn effective query phrasings by example, without crowding the UI.

## Concept

Instead of recording the coding assistant's queries in the dashboard (which
raises privacy and complexity concerns), provide **curated example queries**
directly in the Ask Question interface. When a technician types a trigger
character (e.g. `/`), a suggestion list appears with common, proven queries
they can pick from or adapt.

## How it would work

1. **Trigger:** Typing `/` in the AskAI input opens a suggestion panel.
   Alternatively, a small "💡" icon next to the input opens it.
2. **Suggestions:** A list of pre-defined query templates, optionally filtered
   by context (device page vs. dashboard).
3. **Selection:** Clicking a suggestion fills the input (or sends it
   directly). The technician sees the exact phrasing that works.
4. **Categories:** Group by scenario (diagnostics, configuration, fleet, etc.).

## Example suggestions

| Category | Query template | Triggers proposal? |
|----------|---------------|-------------------|
| Diagnostics | "Run a health check on {device}." | ✅ Yes |
| Diagnostics | "Check the health of {device} and report its status." | ❌ No (answers directly) |
| Diagnostics | "Scan the filesystem of {device}." | ✅ Yes |
| Diagnostics | "List installed programs on {device}." | ✅ Yes |
| Diagnostics | "List processes on {device}." | ✅ Yes |
| Diagnostics | "Run a list of network connections on {device}." | ✅ Yes |
| Diagnostics | "List network connections on {device}." | ❌ No (answers directly) |
| Configuration | "Apply configuration to set volume to 50 on {device}." | ✅ Yes |
| Configuration | "Set brightness to 30 on {device}." | ❌ No (AI refuses) |
| Troubleshooting | "Restart the print spooler on {device}." | ✅ Yes |
| Delegation | "Run a health check on {device} and tell me whether it worked." | ✅ Yes |
| Fleet | "Run a health check on all devices at {site}." | ✅ Yes |

**Tip:** Action-oriented verbs ("Run", "Scan", "Apply") trigger proposals more
reliably than informational verbs ("Check", "List", "Set"). When in doubt, use
"Run a ..." phrasing. For guaranteed results, use explicit tool-call phrasing
(see `docs/ai-command-payload-transparency.md`).

## Explicit tool-call phrasing

When natural-language phrasing doesn't trigger the right action, technicians
can use **explicit tool-call phrasing** to force a specific proposal. The AI
recognizes these patterns and calls the corresponding tool directly.

### Format

```
Call propose_device_action with action=<action>, target_device_id=<device_id>,
params=<json>, rationale='<reason>'.
```

For fleet-wide actions:

```
Call propose_fleet_action with action=<action>, site_id=<site_id>,
rationale='<reason>'.
```

### Tested examples (Brunel Device 001)

| Phrasing | Result |
|----------|--------|
| `Call propose_device_action with action=update_config, target_device_id=DEVICE-MRUU-AUCA-8TJB, params={"config": {"brightness": 30}}, rationale='test brightness control'.` | Proposed `update_config` with brightness=30 |
| `Call propose_device_action with action=update_config, target_device_id=DEVICE-MRUU-AUCA-8TJB, params={"config": {"volume": 75}}, rationale='test volume control'.` | Proposed `update_config` with volume=75 |
| `Call propose_fleet_action with action=health_check, site_id=SITE-W545-2BK3, rationale='fleet health check'.` | Proposed `health_check` (1 step for 1 active device) |

### When to use explicit phrasing

- The AI refuses a natural-language request ("brightness is not configurable").
- You need a specific config key that the AI doesn't associate with
  `update_config`.
- You want to propose an action the AI wouldn't normally suggest.
- Fleet operations where you want to ensure all devices are covered.

### Tips

- Always include `target_device_id` (business ID, not the friendly name).
- `params` must be valid JSON with the correct structure for the action.
- For `update_config`, wrap settings under `{"config": {...}}`.
- For `restart_service`, include `{"service_name": "..."}`.
- For `run_command`, include `{"command": "..."}`.

## Where suggestions come from

- **Soak test scenarios** (S1–S8 in `docs/real-device-ai-soak-test.md`) are
  already proven queries that work.
- **Reliability metrics** can surface the most successful query patterns per
  action type.
- **Memory** (ChromaDB) could store and retrieve effective queries over time.
- **Manual curation** by admins/technicians who find useful phrasings.

## UI design — keeping it clean

The main concern is **not crowding the dashboard**. The AskAI widget is
already compact. Here's how to integrate suggestions without clutter:

### Option 1 — Inline trigger (recommended)

- A small **"?"** or **lightbulb icon** sits inside or next to the input
  field (same line, not a new row).
- Clicking it (or typing `/`) opens a **floating popover** anchored to the
  input — not a modal, not a new panel.
- The popover is narrow (max 320px), scrollable if needed, and dismisses on
  click-outside or Escape.
- Suggestions are grouped by category with collapsible headers.
- On a device detail page, `{device}` is pre-filled with the device ID; on the
  dashboard, `{device}` and `{site}` are left as placeholders the technician
  fills in.

### Option 2 — Empty-state hint

- When the input is empty and focused, show a single line below:
  "Tip: type `/` for query suggestions."
- No icon, no button — just a subtle hint that disappears on typing.
- The `/` trigger still opens the popover.

### Option 3 — Contextual (post-result)

- After the AI returns a result, show a small "Try next:" line with 1–2
  related suggestions (e.g., after a health check: "Try: 'Run a health check
  on all devices at this site'").
- This is contextual and doesn't crowd the input area at all.

### What NOT to do

- Do not add a permanent sidebar or panel of suggestions — it competes with
  the answer area.
- Do not show suggestions on every keystroke — only on `/` or explicit click.
- Do not show more than ~8 suggestions at once — use categories and scroll.
- Do not auto-send — always let the technician review and edit before sending.

## Implementation sketch (when ready)

- **Frontend:** Add a `QuerySuggestions` component to `AskAIWidget` that
  activates on `/` and shows a filtered list. Clicking fills the input.
- **Backend (optional):** `GET /ai/query-suggestions?device_id=...` returning
  context-aware suggestions. Could be static JSON or derived from reliability
  data.
- **Config:** A `ai/query_suggestions.yaml` file listing templates with
  placeholders, similar to command templates.

## Pros and cons

### Pros
- Low implementation effort (frontend-only if static; small endpoint if dynamic).
- No backend persistence or privacy concerns.
- Technicians learn by seeing proven phrasings.
- The `/` trigger is a familiar UX pattern.

### Cons
- Suggestions can become stale if the device capabilities change.
- Static suggestions don't adapt to per-site context unless the backend is involved.
- Requires curation effort to keep the list relevant.

## Status

**Concept only.** No code written. Tracked for future implementation when the
soak test produces a stable set of proven queries.
PYEOF
echo written
