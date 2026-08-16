# Device Emulators

This directory contains realistic **POS/IoT device emulators** for end-to-end
testing of the full device lifecycle (device DNA, heartbeat, telemetry, command
polling) against the HOMEPOT backend without physical hardware.

| Emulator | Description |
|----------|-------------|
| `linux_pos_emulator.py`  | Linux point-of-sale terminal emulator |
| `android_pos_emulator.py`| Android POS terminal emulator |
| `macos_pos_emulator.py`  | macOS POS terminal emulator |
| `windows_pos_emulator.py`| Windows POS terminal emulator |
| `ios_pos_emulator.py`    | iOS tablet/terminal emulator |
| `pos_engine.py`          | Shared emulator engine (health, telemetry, heartbeat, command handling) |
| `*.json`                 | Default per-OS emulator configuration |

Emulation is one of the **three test integration modes** (Simulation, Emulation,
Real Devices).

> ⚠️ **Disable the in-process agent simulator first.** Keep
> `ENABLE_AGENT_SIMULATION=false` in the environment (or `backend/.env`) when
> running an emulator, otherwise the backend's built-in simulator writes fake
> telemetry into the emulated device — and into any `real` device — corrupting
> the `real`/`controlled`/`simulated` provenance used by the KPI export.

## Quick start

```bash
./scripts/start-emulator.sh                    # default (Linux) emulator
./scripts/start-emulator.sh --emulator android # Android emulator
./scripts/start-emulator.sh --site-id <site> --bootstrap-key <key> --device-name demo-pos-1
```

Full usage and configuration details: [docs/device-emulators.md](../docs/device-emulators.md).