# AI command payload and execution transparency (design note)

This document captures a design discussion about the mismatch between the JSON
payloads the AI proposes and the mixed Python/PowerShell execution that happens
on the device. It is a design note only — no code changes.

## The observation

Not all HOMEPOT commands are pure JSON. The command flow has two layers:

1. **AI proposal layer** (`ai/actions.py`, `ai/tools.py`): the AI proposes a
   structured JSON payload, e.g. `{"config": {"brightness": 30}}` or
   `{"command": "ipconfig"}`. This is what gets stored in `ai_action_step.params`
   and shown in the Final Payload Preview.

2. **Device execution layer** (`command_poller.py`): the device agent receives the
   JSON payload and translates it into an actual OS operation — a PowerShell
   script for brightness, a ctypes Core Audio call for volume, a subprocess for
   `run_command`, a winget invocation for `install_program`, etc.

So the AI's JSON payload is **not the final command**. It is a *parameter
specification* that the device agent expands into a platform-specific
implementation. The actual executed command (the PowerShell script, the
subprocess argv) is generated on the device at execution time and is never seen
by the AI or the technician in the proposal.

## Why this is problematic

### 1. Transparency gap

A technician reviewing an AI proposal sees:

```
Action: update_config
Params: {"config": {"brightness": 30}}
```

But what actually runs on the device is a 40-line PowerShell script (dxva2 +
WMI fallback). The technician cannot verify from the proposal alone what OS
command will execute. The dry-run preview (`POST /ai/action-plans/{id}/dry-run`)
shows "predicted_change: {config_keys: [brightness], values: {brightness: 30}}"
but not the generated script.

### 2. Auditability

The command result (stored in `device_commands.result`) contains the stdout/stderr
of the actual OS command. So the *result* is auditable, but the *command* that
produced it is not stored as a single string — it is reconstructed by the device
agent from the payload at execution time. If the agent version changes, the same
payload might produce a different OS command.

### 3. Injection risk

For `run_command` and `run_script`, the AI specifies `{"command": "..."}` and
the device agent passes it to a shell. The executor and policy engine validate
the action (risk tier, permissions) but do not sanitize the command string.
A malicious or confused AI could propose a command that does more than intended.

### 4. Reuse mismatch

The "Reuse Command" feature in push history reuses `payload.data` (the JSON
params). For AI-created commands, this is the params dict, not the full OS
command. Reusing an AI health_check command sends `{"data": {}}` which is fine
(no params needed). But reusing an AI `run_command` sends `{"data": {"command":
"ipconfig"}}` which works because the device agent reads `data.command`. So
reuse works, but the technician is reusing the *params*, not the *executed
command*.

## What the AI can and cannot see

| Layer | AI sees? | Technician sees (proposal)? | Technician sees (result)? |
|-------|----------|----------------------------|---------------------------|
| Action name (e.g. `update_config`) | ✅ | ✅ | ✅ |
| JSON params (e.g. `{"brightness": 30}`) | ✅ | ✅ | ✅ |
| Device command type (e.g. `update_config`) | ❌ (indirect) | ❌ | ✅ (in command history) |
| OS command / script (e.g. PowerShell) | ❌ | ❌ | ✅ (in result stdout/stderr) |
| Final payload (title + data) | ❌ | ❌ | ✅ (in command history) |

## Options

### Option A — Keep the two-layer model (current)

The AI proposes parameters; the device agent expands them. The technician
reviews the *intent* (action + params) and the *result* (stdout/stderr), but not
the intermediate OS command.

**Pros:** Clean separation of concerns. The AI never needs to know OS-specific
implementation details. Adding a new OS platform doesn't require AI changes.

**Cons:** Transparency gap. Technicians can't fully verify what will run from
the proposal alone. Injection risk for `run_command`/`run_script`.

### Option B — AI proposes the full command string

Extend the AI action registry so `run_command` and `run_script` accept a
command string that is shown verbatim in the proposal and dry-run preview.
The device agent executes it as-is (no expansion).

**Pros:** Full transparency — what the AI proposes is what runs. Reuse is
exact.

**Cons:** The AI would need to know OS-specific command syntax (PowerShell vs
bash). This pushes platform knowledge into the LLM, increasing error rates.
Higher injection risk if the AI generates unsafe commands.

### Option C — Store the generated OS command in the result

Keep the two-layer model, but have the device agent include the exact command
it executed in the result payload (e.g. `{"command_executed": "powershell -c ...",
"status": "applied"}`). The technician can then see what ran after the fact.

**Pros:** No change to the proposal flow. Full auditability of what actually
ran. Reuse still works on params.

**Cons:** Post-hoc only — the technician can't preview the OS command before
approval.

### Option D — Hybrid: show generated command in dry-run

Extend the dry-run endpoint to call a "preview" function on the device agent
(or simulate it server-side) that returns the OS command that *would* be
executed, without running it. The technician sees both the params and the
generated command before approving.

**Pros:** Best of both — transparency before approval, no AI knowledge of OS
details.

**Cons:** Requires a preview capability in the device agent (or a server-side
template engine that mirrors the agent's logic). Significant effort.

## Recommendation

**Short term (demo):** Option A is fine. The device agent already logs the
full stdout/stderr in the result, so what ran is visible after the fact. The
dry-run shows the intent. This is acceptable for a demo where technicians
understand the two-layer model.

**Medium term:** Option C (store the generated command in the result) is cheap
and high-value. Add a `command_executed` field to the result payload so the
push history shows exactly what ran. This requires a small change to
`command_poller.py` (each applier returns the command it ran) and to the
result serialization.

**Long term:** Option D (dry-run shows the generated command) is the
production-grade solution. It requires either a preview endpoint on the device
agent or a server-side template engine that mirrors the agent's applier logic.

## Action items (when ready)

1. **Option C (quick win):** Modify `command_poller.py` appliers to include
   `command_executed` in their result dict. Update `DeviceHistory.jsx` to
   display it in the details modal.
2. **Option D (production):** Design a preview endpoint that returns the OS
   command without executing it. Wire it into the dry-run flow.
3. **Security:** Add command-string sanitization for `run_command`/`run_script`
   (reject shell metacharacters, allow-list known commands).

## Status

**Design only.** No code changes. The two-layer model (Option A) remains in
effect.
PYEOF
echo written