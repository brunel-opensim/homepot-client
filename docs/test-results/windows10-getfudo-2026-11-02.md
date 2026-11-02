# Device Testing Results — GetFudo Device 001

Standardized device management testing report for HOMEPOT across platforms.

## Test environment

| Field | Value |
|---|---|
| **Device ID** | `DEVICE-UDWE-YNA6-QTM6` |
| **Device Name** | GetFudo Device 001 |
| **Site** | `SITE-GS2F-NBJ8` |
| **OS & Architecture** | Windows 10 Pro 64-bit |
| **Agent Version** | `v0.3.29` |
| **Firmware Version** | `1.39.0` |
| **Tester Name** | Robin |
| **Testing Date** | 2026-11-02 |
| **Dashboard URL** | https://homepot.cabera.com |

---

## Prerequisites

- [✔️] Device enrolled and showing as "online" in Dashboard
- [✔️] Agent reports version (not "REAL") in Device Details → Source
- [✔️] Firmware version populated in Device Details
- [✔️] Peripherals (printers) listed if applicable
- [✔️] "Manage device" permission granted (root_access)

---

## 1. Device Registration & Identity

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Device shows as "online" in Dashboard | Green indicator, last_seen recent | **Pass** | Verified |
| 1.2 | Device Details → Source shows agent version (not "REAL") | 0.3.29 | **Pass** | Displays 0.3.29 |
| 1.3 | Device Details → Firmware shows BIOS version | 1.39.0 | **Pass** | Displays 1.39.0 |
| 1.4 | Site Details → Associated Devices shows device with Source | Version displayed | **Pass** | Version displayed correctly |
| 1.5 | Agents page shows device with Mode = version | Version displayed | **Pass** | Mode shows version |
| 1.6 | Peripherals listed (printers, scanners) | At least printers shown | **Pass** | Printers listed |

---

## 2. Apply Configuration

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 2.1 | Apply Configuration with volume: 50, brightness: 50 | Status "completed", volume "applied" (verified: true) | **Fail** | Verification status not returning expected true |
| 2.2 | Volume actually changes on device | Master volume slider moves to 50% | **Pass** | Hardware volume changed |
| 2.3 | Brightness actually changes on device | Screen brightness changes | **Pass** | Display brightness changed |
| 2.4 | Result shows verification object | before/after/target/verified for both | **Fail** | Verification object missing or incomplete |
| 2.5 | Apply Configuration with volume: 0 | Volume muted | **Pass** | Volume muted successfully |
| 2.6 | Apply Configuration with volume: 100 | Volume max | **Pass** | Volume maximized successfully |
| 2.7 | Apply Configuration with brightness: 0 | Screen very dark | **Fail** | Brightness 0 not setting screen dark |
| 2.8 | Apply Configuration with brightness: 100 | Screen very bright | **Fail** | Brightness 100 not setting screen bright |

---

## 3. Direct Connect (Remote Shell)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 3.1 | Direct Connect with simple command (e.g. echo hello) | Output shows "hello" | **Fail** | Remote Shell successfully opened and the command was submitted to the Windows device. However, the entered command Hello returned a PowerShell error: command not recognized. The expected output was not received. |
| 3.2 | Direct Connect with system info command | Output shows system details | **Pass** | System details output was received |
| 3.3 | History shows "Remote Shell" as title | Title is "Remote Shell" | **Pass** | Remote Shell history display the expected title. |
| 3.4 | History shows correct prompt (user@ or root@) | Prompt matches elevation | **Fail** | Prompt did not match elevation level |
| 3.5 | Command timeout (300s) works | Long-running command times out | **Fail** | Command timeout behaviour was not as expected. |

---

## 4. Compose Command (Push Review)

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 4.1 | Push "Reboot System" command | Command queued, device reboots | **Pass** | Device rebooted |
| 4.2 | Push "Shut Down System" command | Command queued, device shuts down | **Pass** | Device shut down |
| 4.3 | Push "Start Program" (default notepad.exe) | Notepad opens | **Pass** | Notepad opened |
| 4.4 | Push "Stop Program" (default notepad.exe) | Notepad closes | **Pass** | Only started program has been stopped |
| 4.5 | Push "Install Program" (e.g. Git.Git) | Program installed | **Pass** | Successfully executed the INSTALL_PROGRAM command on Dealdio Device 001 using the Notepad++.Notepad++ package. The application installation was completed and verified successfully. |
| 4.6 | Push "Uninstall Program" | Program removed | **Pass** | Successfully executed the UNINSTALL_PROGRAM command. The selected application was removed successfully from the Windows device. |
| 4.7 | Push "Update Program" | Program updated | **Pass** | Successfully executed the UPDATE_PROGRAM command. The application update was completed successfully. |
| 4.8 | Push "Upgrade All Programs" | All programs updated | **Pass** | Successfully executed the UPGRADE_ALL_PROGRAMS command. The available application updates were processed successfully. |
| 4.9 | Push "List Installed Programs" | Registry programs listed with locations | **Pass** | Registry programs listed with locations |
| 4.10 | Push "Run Command" with custom script | Script executes, output shown | **Pass** | Script executed successfully |
| 4.11 | Push "Run Command (Unprivileged)" | Command runs as user | **Pass** | Executed under standard user |
| 4.12 | Push "Health Check" | CPU/mem/disk/network results shown | **Pass** | Health check returned metrics |
| 4.13 | Push "Scan Filesystem" | File listing returned | **Pass** | File listing returned |
| 4.14 | Push "List Processes" | Process list returned | **Pass** | Process list returned |
| 4.15 | Push "List Connections" | Connection list returned | **Pass** | Connection list returned |
| 4.16 | Final Payload Preview shows { command_type, payload } | Preview matches queued command | **Pass** | Preview verified |
| 4.17 | Push History reuse derives correct template | Reused command has correct params | **Pass** | Template derived correctly |

---

## 5. Push History

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 5.1 | Push History shows command list | Commands listed with status | **Pass** | Command list displayed |
| 5.2 | Click a command to see details | Result, stdout, stderr shown | **Pass** | Details shown |
| 5.3 | Command result shows verification object | before/after/target/verified | **Pass** | Verification object shown |
| 5.4 | Compose Command result shows per-key details | Status, message, verification per key | **Pass** | Per-key details verified |
| 5.5 | Reuse a command from history | Template derived correctly, shell command preserved | **Pass** | Command reuse verified |

---

## 6. Live Logs & Audit Trail

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 6.1 | Live Logs tab shows log entries | Status snapshots, command events | **Pass** | Logs visible |
| 6.2 | Task Health badges shown (heartbeat/telemetry/command_poll) | All show "OK" | **Pass** | Badges show OK |
| 6.3 | Audit Trail shows agent_started event | Event with version number | **Pass** | Version event verified |
| 6.4 | Audit Trail shows command execution events | command_completed/failed events | **Pass** | Events logged |
| 6.5 | Live Logs poll every 2s | New entries appear without refresh | **Pass** | Polling every 2s verified |

---

## 7. Device Health & Monitoring

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 7.1 | Device Details shows Agent Uptime | Formatted (e.g., "1h 23m") | **Pass** | Uptime formatted correctly |
| 7.2 | Device Details shows Agent Restarts | Number (0 on fresh start) | **Pass** | Restarts count displayed |
| 7.3 | Device Details shows Last Offline Reason | e.g. "network partition" or "N/A" | **Pass** | Reason populated |
| 7.4 | Telemetry charts show CPU/memory/disk | Charts populated | **Pass** | Charts populated |
| 7.5 | Health check passes | CPU/memory/disk/network all pass | **Pass** | All checks pass |

---

## 8. Offline & Resilience

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 8.1 | Disconnect network → device shows offline after ~2.5 min | Dashboard shows offline | **Pass** | Offline state detected |
| 8.2 | Reconnect network → device shows online | Dashboard shows online | **Pass** | Online state restored |
| 8.3 | Offline escalation alert created after 5 min | Warning alert in Alerts page | **Pass** | Alert created |
| 8.4 | Device goes to sleep → wakes → reconnects | Heartbeat resumes | **Pass** | Reconnected after wake |
| 8.5 | Force-kill agent → watchdog restarts (if configured) | Agent restarts, uptime resets | **Pass** | Watchdog restarted agent |

---

## 9. Auto-Update

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 9.1 | App checks for updates on launch (30s) | "Last checked" timestamp in Settings | **Pass** | Timestamp verified |
| 9.2 | Update available notification shown | OS toast + tray tooltip | **Pass** | Notification displayed |
| 9.3 | Download progress shown | Percentage in Settings | **Pass** | Progress shown |
| 9.4 | "Restart to Install" installs update | App relaunches with new version | **Pass** | Same time not work, I have restart the device then App relaunches with new version |
| 9.5 | Device Details → Source shows new version | Version updated | **Pass** | New version updated |

---

## 10. Logs & File Locations

| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 10.1 | Logs in %PROGRAMDATA%\Homepot\logs\ | agent.log, agent-*.log present | **Pass** | Log files present |
| 10.2 | No logs in app install directory | No resources\logs\ files | **Pass** | Clean install dir |
| 10.3 | Log rotation works (10 MiB, 5 backups) | .1, .2, ... files present after rotation | **Pass** | Rotation working |
| 10.4 | Elevation marker exists | elevation_installed.marker in ProgramData\Homepot | **Pass** | Marker exists |
| 10.5 | Scheduled task "HOMEPOT-Elevation" exists | Task shows in Task Scheduler | **Pass** | Task present in Task Scheduler |

---

## Test result summary

| Section | Total | Pass | Fail | Blocked |
|---|---|---|---|---|
| 1. Registration & Identity | 6 | 6 | 0 | 0 |
| 2. Apply Configuration | 8 | 4 | 4 | 0 |
| 3. Direct Connect (Remote Shell) | 5 | 2 | 3 | 0 |
| 4. Compose Command (Push Review) | 17 | 17 | 0 | 0 |
| 5. Push History | 5 | 5 | 0 | 0 |
| 6. Live Logs & Audit Trail | 5 | 5 | 0 | 0 |
| 7. Device Health & Monitoring | 5 | 5 | 0 | 0 |
| 8. Offline & Resilience | 5 | 5 | 0 | 0 |
| 9. Auto-Update | 5 | 5 | 0 | 0 |
| 10. Logs & File Locations | 5 | 5 | 0 | 0 |
| **TOTAL SCORE** | **66** | **59** | **7** | **0** |
