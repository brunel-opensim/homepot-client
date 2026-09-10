#!/usr/bin/env bash
# Smoke-test the frozen agent + emulator binaries on the build OS.
#
# Runs from user_app/ (the workflow's working-directory). The frozen agent's
# entry point executes the full runtime loop, so "boots and stays alive" proves
# the PyInstaller bundle imports the complete module graph (agent_api router ->
# SQLAlchemy etc.) and finds its bundled data files without crashing. The
# emulator entry ends in argparse, so `--help` forces every bundled emulator
# module to load and exits cleanly.
set -euo pipefail

os="$1"

case "${os}" in
  windows-latest)
    agent="pyinstaller-dist/homepot-agent/homepot-agent.exe"
    emulator="pyinstaller-dist/homepot-emulator/homepot-emulator.exe"
    ;;
  *)
    agent="pyinstaller-dist/homepot-agent/homepot-agent"
    emulator="pyinstaller-dist/homepot-emulator/homepot-emulator"
    ;;
esac

"${agent}" >/tmp/homepot-agent-smoke.log 2>&1 &
agent_pid=$!
sleep 8
if kill -0 "${agent_pid}" 2>/dev/null; then
  kill "${agent_pid}" 2>/dev/null || true
  wait "${agent_pid}" 2>/dev/null || true
  echo "frozen homepot-agent smoke OK"
else
  wait "${agent_pid}" || true
  echo "frozen homepot-agent crashed during boot" >&2
  echo "--- homepot-agent log ---" >&2
  cat /tmp/homepot-agent-smoke.log >&2
  exit 1
fi

"${emulator}" --help >/dev/null
echo "frozen homepot-emulator smoke OK"