"""Guard the agent <-> Electron-supervisor marker/exit-code contract.

The device agent (Python) and the Electron supervisor (TypeScript) coordinate
``update_app``/``rollback_app``/unpair/restart through reserved stdout markers
and exit codes. Those literals are duplicated in
``backend/src/homepot/agent/utils/command_poller.py`` and
``user_app/electron/main.ts``, with only comments tying them together. This test
reads both and fails loudly if either side drifts.
"""

import os
import re

from homepot.agent.utils.command_poller import (
    RESTART_AGENT_EXIT_CODE,
    ROLLBACK_APP_MARKER,
    UNPAIRED_EXIT_CODE,
    UNPAIRED_MARKER,
    UPDATE_APP_MARKER,
)

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_CURRENT_DIR, "..", ".."))
_MAIN_TS = os.path.join(_WORKSPACE_ROOT, "user_app", "electron", "main.ts")


def _read_main_ts() -> str:
    with open(_MAIN_TS, encoding="utf-8") as fh:
        return fh.read()


def _ts_string_constant(source: str, name: str) -> str:
    """Extract a ``const NAME = '...'`` string literal from the TS source."""
    match = re.search(rf"const {name} = '([^']+)'", source)
    assert match, f"{name} not found in {_MAIN_TS}"
    return match.group(1)


def _ts_int_constant(source: str, name: str) -> int:
    """Extract a ``const NAME = <int>`` literal from the TS source."""
    match = re.search(rf"const {name} = (\d+)", source)
    assert match, f"{name} not found in {_MAIN_TS}"
    return int(match.group(1))


def test_supervisor_markers_match_agent():
    """Every stdout marker literal in main.ts matches the Python constant."""
    source = _read_main_ts()
    assert _ts_string_constant(source, "UPDATE_APP_MARKER") == UPDATE_APP_MARKER
    assert _ts_string_constant(source, "ROLLBACK_APP_MARKER") == ROLLBACK_APP_MARKER
    assert _ts_string_constant(source, "UNPAIRED_MARKER") == UNPAIRED_MARKER


def test_supervisor_exit_codes_match_agent():
    """Every reserved exit code in main.ts matches the Python constant."""
    source = _read_main_ts()
    assert (
        _ts_int_constant(source, "RESTART_AGENT_EXIT_CODE") == RESTART_AGENT_EXIT_CODE
    )
    assert _ts_int_constant(source, "UNPAIRED_EXIT_CODE") == UNPAIRED_EXIT_CODE
