# Tools

Manual command-line tools for device management and soak testing. These are
run by an operator on a workstation/laptop — they are **not** unit tests and
are **never** executed by CI (pytest is scoped to `backend/tests/`).

| Script | Purpose |
|--------|---------|
| `compose-soak-test.py` | Sends each compose command to a device via the command API and reports pass/fail. Run sequentially with generous timeouts. |
| `ai-soak-test.py` | *(planned)* AI-delegation soak test (propose → approve → execute → verify). |

## Filenames

Use hyphens, not underscores, to match the repo convention (e.g.
`compose-soak-test.py`, not `compose_soak_test.py`). These are standalone
scripts run directly (`python tools/compose-soak-test.py`), never imported as
modules.
