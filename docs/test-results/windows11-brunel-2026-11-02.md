# Device Testing — Brunel Device 001 (v0.3.29)

Standardized test record for the Brunel Windows 11 device, filled in as a
sample for other engineers to follow. Server-side items are pre-filled from
live Dashboard/API checks on 2026-11-02; on-device items must be verified by
the tester and recorded below.

## Test environment

| Field | Value |
|-------|-------|
| Device ID | `DEVICE-MRUU-AUCA-8TJB` |
| Device Name | Brunel Device 001 |
| Site | Brunel Site 1 (`SITE-W545-2BK3`) |
| OS | Windows 11 |
| Agent Version | (not reported — older agent → shows "REAL" in UI) |
| Firmware Version | (check Device Details → Firmware) |
| Tester | Maziar Ghorbani |
| Date | 2026-11-02 |
| Dashboard URL | https://homepot.cabera.com |
| Server commit | c762a4d (main) |

## Prerequisites

- [x] Device enrolled and showing as "online" in Dashboard
- [ ] Agent reports version (not "REAL") in Device Details → Source
- [ ] Firmware version populated in Device Details
- [ ] Peripherals (printers) listed if applicable
- [ ] "Manage device" permission granted (root_access)

---

## 1. Device Registration & Identity

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Device shows as "online" in Dashboard | Green indicator, last_seen recent | Pass | Verified via API: connectivity=online, last_seen 2026-11-02 |
| 1.2 | Device Details → Source shows agent version (not "REAL") | e.g. "0.3.29" | Fail | Older agent; reports "REAL" (expected for pre-v0.3.29 agent) |
| 1.3 | Device Details → Firmware shows BIOS version | e.g. "1.44.0" | | Needs on-device check |
| 1.4 | Site Details → Associated Devices shows device with Source | Version displayed | | Needs on-device check |
| 1.5 | Agents page shows device with Mode = version | Version displayed | | Needs on-device check |
| 1.6 | Peripherals listed (printers, scanners) | At least printers shown | | Needs on-device check |

## 2. Apply Configuration

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 2.1 | Apply Configuration with volume: 50, brightness: 50 | Status "completed", volume "applied" (verified: true) | | Needs on-device test |
| 2.2 | Volume actually changes on device | Master volume slider moves to 50% | | Needs on-device test |
| 2.3 | Brightness actually changes on device | Screen brightness changes | Pass (prior) | Verified on v0.3.24: 75→30 via WMI |
| 2.4 | Result shows verification object | before/after/target/verified for both | | Needs on-device test |
| 2.5 | Apply Configuration with volume: 0 | Volume muted | | Needs on-device test |
| 2.6 | Apply Configuration with volume: 100 | Volume max | | Needs on-device test |
| 2.7 | Apply Configuration with brightness: 0 | Screen very dark | | Needs on-device test |
| 2.8 | Apply Configuration with brightness: 100 | Screen very bright | | Needs on-device test |

## 3. Direct Connect (Remote Shell)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 3.1 | Direct Connect with simple command (e.g. `echo hello`) | Output shows "hello" | | Needs on-device test |
| 3.2 | Direct Connect with system info command | Output shows system details | | Needs on-device test |
| 3.3 | History shows "Remote Shell" as title | Title is "Remote Shell" | | Needs on-device test |
| 3.4 | History shows correct prompt (`user@` or `root@`) | Prompt matches elevation | | Needs on-device test |
| 3.5 | Command timeout (300s) works | Long-running command times out | | Needs on-device test |

## 4. Compose Command (Push Review)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 4.1 | Push "Reboot System" command | Command queued, device reboots | | Needs on-device test |
| 4.2 | Push "Shut Down System" command | Command queued, device shuts down | | Needs on-device test |
| 4.3 | Push "Start Program" (default notepad.exe) | Notepad opens | | Needs on-device test |
| 4.4 | Push "Stop Program" (default notepad.exe) | Notepad closes | | Needs on-device test |
| 4.5 | Push "Install Program" (e.g. Git.Git) | Program installed | | Needs on-device test |
| 4.6 | Push "Uninstall Program" | Program removed | | Needs on-device test |
| 4.7 | Push "Update Program" | Program updated | | Needs on-device test |
| 4.8 | Push "Upgrade All Programs" | All programs updated | | Needs on-device test |
| 4.9 | Push "List Installed Programs" | Registry programs listed with locations | | Needs on-device test |
| 4.10 | Push "Run Command" with custom script | Script executes, output shown | | Needs on-device test |
| 4.11 | Push "Run Command (Unprivileged)" | Command runs as user | | Needs on-device test |
| 4.12 | Push "Health Check" | CPU/mem/disk/network results shown | | Needs on-device test |
| 4.13 | Push "Scan Filesystem" | File listing returned | | Needs on-device test |
| 4.14 | Push "List Processes" | Process list returned | | Needs on-device test |
| 4.15 | Push "List Connections" | Connection list returned | | Needs on-device test |
| 4.16 | Final Payload Preview shows `{ command_type, payload }` | Preview matches queued command | | Needs on-device test |
| 4.17 | Push History reuse derives correct template | Reused command has correct params | | Needs on-device test |

## 5. Push History

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 5.1 | Push History shows command list | Commands listed with status | Pass | 14 commands in history, all completed |
| 5.2 | Click a command to see details | Result, stdout, stderr shown | | Needs on-device test |
| 5.3 | Command result shows verification object | before/after/target/verified | | Needs on-device test |
| 5.4 | Compose Command result shows per-key details | Status, message, verification per key | | Needs on-device test |
| 5.5 | Reuse a command from history | Template derived correctly, shell command preserved | | Needs on-device test |

## 6. Live Logs & Audit Trail

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 6.1 | Live Logs tab shows log entries | Status snapshots, command events | | Needs on-device test |
| 6.2 | Task Health badges shown (heartbeat/telemetry/command_poll) | All show "OK" | | Needs on-device test |
| 6.3 | Audit Trail shows agent_started event | Event with version number | | Needs on-device test |
| 6.4 | Audit Trail shows command execution events | command_completed/failed events | | Pass (server) | Command history shows 14 completed commands with attribution |
| 6.5 | Live Logs poll every 2s | New entries appear without refresh | | Needs on-device test |

## 7. Device Health & Monitoring

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 7.1 | Device Details shows Agent Uptime | Formatted (e.g., "1h 23m") | | Needs on-device test |
| 7.2 | Device Details shows Agent Restarts | Number (0 on fresh start) | | Needs on-device test |
| 7.3 | Device Details shows Last Offline Reason | e.g. "network partition" or "N/A" | | Needs on-device test |
| 7.4 | Telemetry charts show CPU/memory/disk | Charts populated | | Needs on-device test |
| 7.5 | Health check passes | CPU/memory/disk/network all pass | | Needs on-device test |

## 8. Offline & Resilience

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 8.1 | Disconnect network → device shows offline after ~2.5 min | Dashboard shows offline | | Needs on-device test |
| 8.2 | Reconnect network → device shows online | Dashboard shows online | | Needs on-device test |
| 8.3 | Offline escalation alert created after 5 min | Warning alert in Alerts page | | Needs on-device test |
| 8.4 | Device goes to sleep → wakes → reconnects | Heartbeat resumes | | Needs on-device test |
| 8.5 | Force-kill agent → watchdog restarts (if configured) | Agent restarts, uptime resets | | Needs on-device test |

## 9. Auto-Update

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 9.1 | App checks for updates on launch (30s) | "Last checked" timestamp in Settings | | Needs on-device test |
| 9.2 | Update available notification shown | OS toast + tray tooltip | | Needs on-device test |
| 9.3 | Download progress shown | Percentage in Settings | | Needs on-device test |
| 9.4 | "Restart to Install" installs update | App relaunches with new version | | Needs on-device test |
| 9.5 | Device Details → Source shows new version | Version updated | | Needs on-device test |

## 10. Logs & File Locations

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 10.1 | Logs in `%PROGRAMDATA%\Homepot\logs\` | agent.log, agent-*.log present | | Needs on-device test |
| 10.2 | No logs in app install directory | No `resources\logs\` files | | Needs on-device test |
| 10.3 | Log rotation works (10 MiB, 5 backups) | .1, .2, ... files present after rotation | | Needs on-device test |
| 10.4 | Elevation marker exists | `elevation_installed.marker` in ProgramData\Homepot | | Needs on-device test |
| 10.5 | Scheduled task "HOMEPOT-Elevation" exists | Task shows in Task Scheduler | | Needs on-device test |

---

## Platform-specific notes

### Windows 11 (Brunel)
- Brightness: WMI SetBrightness (dxva2 returns rc=3 on this device)
- Volume: Core Audio ctypes (CoInitialize required)
- Elevation: Scheduled task with SYSTEM principal
- Prior verification: brightness 75→30 (WMI), volume unmute verified

---

## Test result summary

| Section | Total | Pass | Fail | Blocked |
|---------|-------|------|------|---------|
| 1. Registration | 6 | 1 | 1 | 0 |
| 2. Apply Configuration | 8 | 1 | 0 | 7 |
| 3. Direct Connect | 5 | 0 | 0 | 5 |
| 4. Compose Command | 17 | 0 | 0 | 17 |
| 5. Push History | 5 | 1 | 0 | 4 |
| 6. Live Logs & Audit | 5 | 1 | 0 | 4 |
| 7. Device Health | 5 | 0 | 0 | 5 |
| 8. Offline & Resilience | 5 | 0 | 0 | 5 |
| 9. Auto-Update | 5 | 0 | 0 | 5 |
| 10. Logs & Files | 5 | 0 | 0 | 5 |
| **Total** | **66** | **4** | **1** | **61** |

---

## Known limitations / blockers

- Agent on this device is pre-v0.3.29 (shows "REAL" instead of version). Update to v0.3.29 to verify agent_version reporting (tests 1.2, 1.4, 1.5, 9.5).
- GetFudo device is on v0.3.24 and needs an update before validation.
- Dealdio device was previously unresponsive (stale last_seen) but is now online.

---

## Sign-off

| Role | Name | Date |
|------|------|------|
| Tester | Maziar Ghorbani | 2026-11-02 |
| Reviewer | | |
EOF
echo "done"