# Device Testing Template

This document provides a standardized testing template for verifying HOMEPOT
device management across platforms. Use this template when testing real devices
(Windows, macOS, Linux, Android) before User App testing.

## Test environment

| Field | Value |
|-------|-------|
| Device ID | `DEVICE-XXXX-XXXX-XXXX` |
| Device Name | |
| Site | |
| OS | Windows 10 / Windows 11 / macOS / Linux / Android |
| Agent Version | (check Device Details → Source) |
| Firmware Version | (check Device Details → Firmware) |
| Tester | |
| Date | |
| Dashboard URL | https://homepot.cabera.com |

## Prerequisites

- [ ] Device enrolled and showing as "online" in Dashboard
- [ ] Agent reports version (not "REAL") in Device Details → Source
- [ ] Firmware version populated in Device Details
- [ ] Peripherals (printers) listed if applicable
- [ ] "Manage device" permission granted (root_access)

---

## 1. Device Registration & Identity

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Device shows as "online" in Dashboard | Green indicator, last_seen recent | | |
| 1.2 | Device Details → Source shows agent version (not "REAL") | e.g. "0.3.26" | | |
| 1.3 | Device Details → Firmware shows BIOS version | e.g. "1.44.0" | | |
| 1.4 | Site Details → Associated Devices shows device with Source | Version displayed | | |
| 1.5 | Agents page shows device with Mode = version | Version displayed | | |
| 1.6 | Peripherals listed (printers, scanners) | At least printers shown | | |

## 2. Apply Configuration

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 2.1 | Apply Configuration with volume: 50, brightness: 50 | Status "completed", volume "applied" (verified: true) | | |
| 2.2 | Volume actually changes on device | Master volume slider moves to 50% | | |
| 2.3 | Brightness actually changes on device | Screen brightness changes | | |
| 2.4 | Result shows verification object | before/after/target/verified for both | | |
| 2.5 | Apply Configuration with volume: 0 | Volume muted | | |
| 2.6 | Apply Configuration with volume: 100 | Volume max | | |
| 2.7 | Apply Configuration with brightness: 0 | Screen very dark | | |
| 2.8 | Apply Configuration with brightness: 100 | Screen very bright | | |

## 3. Direct Connect (Remote Shell)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 3.1 | Direct Connect with simple command (e.g. `echo hello`) | Output shows "hello" | | |
| 3.2 | Direct Connect with system info command | Output shows system details | | |
| 3.3 | History shows "Remote Shell" as title | Title is "Remote Shell" | | |
| 3.4 | History shows correct prompt (`user@` or `root@`) | Prompt matches elevation | | |
| 3.5 | Command timeout (300s) works | Long-running command times out | | |

## 4. Compose Command (Push Review)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 4.1 | Push "Reboot System" command | Command queued, device reboots | | |
| 4.2 | Push "Shut Down System" command | Command queued, device shuts down | | |
| 4.3 | Push "Start Program" (default notepad.exe) | Notepad opens | | |
| 4.4 | Push "Stop Program" (default notepad.exe) | Notepad closes | | |
| 4.5 | Push "Install Program" (e.g. Git.Git) | Program installed | | |
| 4.6 | Push "Uninstall Program" | Program removed | | |
| 4.7 | Push "Update Program" | Program updated | | |
| 4.8 | Push "Upgrade All Programs" | All programs updated | | |
| 4.9 | Push "List Installed Programs" | Registry programs listed with locations | | |
| 4.10 | Push "Run Command" with custom script | Script executes, output shown | | |
| 4.11 | Push "Run Command (Unprivileged)" | Command runs as user | | |
| 4.12 | Push "Health Check" | CPU/mem/disk/network results shown | | |
| 4.13 | Push "Scan Filesystem" | File listing returned | | |
| 4.14 | Push "List Processes" | Process list returned | | |
| 4.15 | Push "List Connections" | Connection list returned | | |
| 4.16 | Final Payload Preview shows `{ command_type, payload }` | Preview matches queued command | | |
| 4.17 | Push History reuse derives correct template | Reused command has correct params | | |

## 5. Push History

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 5.1 | Push History shows command list | Commands listed with status | | |
| 5.2 | Click a command to see details | Result, stdout, stderr shown | | |
| 5.3 | Command result shows verification object | before/after/target/verified | | |
| 5.4 | Compose Command result shows per-key details | Status, message, verification per key | | |
| 5.5 | Reuse a command from history | Template derived correctly, shell command preserved | | |

## 6. Live Logs & Audit Trail

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 6.1 | Live Logs tab shows log entries | Status snapshots, command events | | |
| 6.2 | Task Health badges shown (heartbeat/telemetry/command_poll) | All show "OK" | | |
| 6.3 | Audit Trail shows agent_started event | Event with version number | | |
| 6.4 | Audit Trail shows command execution events | command_completed/failed events | | |
| 6.5 | Live Logs poll every 2s | New entries appear without refresh | | |

## 7. Device Health & Monitoring

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 7.1 | Device Details shows Agent Uptime | Formatted (e.g., "1h 23m") | | |
| 7.2 | Device Details shows Agent Restarts | Number (0 on fresh start) | | |
| 7.3 | Device Details shows Last Offline Reason | e.g. "network partition" or "N/A" | | |
| 7.4 | Telemetry charts show CPU/memory/disk | Charts populated | | |
| 7.5 | Health check passes | CPU/memory/disk/network all pass | | |

## 8. Offline & Resilience

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 8.1 | Disconnect network → device shows offline after ~2.5 min | Dashboard shows offline | | |
| 8.2 | Reconnect network → device shows online | Dashboard shows online | | |
| 8.3 | Offline escalation alert created after 5 min | Warning alert in Alerts page | | |
| 8.4 | Device goes to sleep → wakes → reconnects | Heartbeat resumes | | |
| 8.5 | Force-kill agent → watchdog restarts (if configured) | Agent restarts, uptime resets | | |

## 9. Auto-Update

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 9.1 | App checks for updates on launch (30s) | "Last checked" timestamp in Settings | | |
| 9.2 | Update available notification shown | OS toast + tray tooltip | | |
| 9.3 | Download progress shown | Percentage in Settings | | |
| 9.4 | "Restart to Install" installs update | App relaunches with new version | | |
| 9.5 | Device Details → Source shows new version | Version updated | | |

## 10. Logs & File Locations

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 10.1 | Logs in `%PROGRAMDATA%\Homepot\logs\` | agent.log, agent-*.log present | | |
| 10.2 | No logs in app install directory | No `resources\logs\` files | | |
| 10.3 | Log rotation works (10 MiB, 5 backups) | .1, .2, ... files present after rotation | | |
| 10.4 | Elevation marker exists | `elevation_installed.marker` in ProgramData\Homepot | | |
| 10.5 | Scheduled task "HOMEPOT-Elevation" exists | Task shows in Task Scheduler | | |

---

## Platform-specific notes

### Windows 10
- Brightness: WMI SetBrightness only (dxva2 may not work)
- Volume: Core Audio ctypes (CoInitialize required)
- Elevation: Scheduled task with SYSTEM principal

### Windows 11
- Brightness: WMI SetBrightness (dxva2 may return success but not work)
- Volume: Core Audio ctypes
- Elevation: Scheduled task with SYSTEM principal

### macOS (future)
- Brightness: `brightness` helper (brew install brightness)
- Volume: `osascript set volume`
- Elevation: pkexec / osascript

### Linux (future)
- Brightness: `brightnessctl set`
- Volume: `amixer set Master`
- Elevation: sudo / pkexec

### Android (future)
- Brightness: Android API
- Volume: Android AudioManager
- Elevation: root access (rooted devices)

---

## How to submit test results

Test engineers should submit completed test results via pull request for review.

### Step 1: Copy the template

```bash
cp docs/device-testing-template.md docs/test-results/<platform>-<device-slug>-<date>.md
```

Naming convention: `<platform>-<device-slug>-<date>.md`
- Platform: `windows10`, `windows11`, `macos`, `linux`, `android`
- Device slug: lowercase device name (e.g., `brunel`, `getfudo`, `dealdio`)
- Date: `YYYY-MM-DD`

Examples:
- `docs/test-results/windows11-brunel-2026-10-29.md`
- `docs/test-results/windows10-getfudo-2026-10-29.md`
- `docs/test-results/macos-brunel-2026-11-05.md`

### Step 2: Fill in the template

1. Fill in the **Test environment** table (Device ID, name, site, OS, agent version, etc.)
2. For each test case, mark **Pass**, **Fail**, or **Blocked** in the Pass/Fail column
3. Add notes for any failures or observations
4. Fill in the **Test result summary** table at the end

### Step 3: Submit via PR

```bash
git checkout -b test-results/<platform>-<device-slug>-<date>
git add docs/test-results/<platform>-<device-slug>-<date>.md
git commit -m "test: <Platform> <Device> device testing results"
git push -u origin HEAD
gh pr create --title "test: <Platform> <Device> device testing results" --body "..."
```

Or use the GitHub web UI:
1. Navigate to the file in the repo
2. Click "Edit" (pencil icon)
3. Fill in the template
4. Click "Commit changes" → "Create a new branch" → "Propose changes"
5. Create the pull request

### Step 4: Review process

- Reviewers will comment on specific failed tests
- Failed tests should include details: what was expected vs. what happened
- Blocked tests should include the reason (e.g., "requires physical access")
- PR is merged when testing is complete

### PR template

A PR template is available at `.github/PULL_REQUEST_TEMPLATE/test-result.md` for structured submissions.

## Test result summary

| Section | Total | Pass | Fail | Blocked |
|---------|-------|------|------|---------|
| 1. Registration | 6 | | | |
| 2. Apply Configuration | 8 | | | |
| 3. Direct Connect | 5 | | | |
| 4. Compose Command | 17 | | | |
| 5. Push History | 5 | | | |
| 6. Live Logs & Audit | 5 | | | |
| 7. Device Health | 5 | | | |
| 8. Offline & Resilience | 5 | | | |
| 9. Auto-Update | 5 | | | |
| 10. Logs & Files | 5 | | | |
| **Total** | **66** | | | |
EOF
echo "done"