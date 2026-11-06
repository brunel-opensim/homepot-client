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
- [✓] Device enrolled and showing as "online" in Dashboard
- [✓] Agent reports version (not "REAL") in Device Details → Source
- [✓] Firmware version populated in Device Details
- [✓] Peripherals (printers) listed if applicable
- [✓] "Manage device" permission granted (root_access)
---
## 1. Device Registration & Identity
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 1.1 | Device shows as "online" in Dashboard | Green indicator, last_seen recent | **Pass** | Device shows online with a green indicator and recent timestamp. |
| 1.2 | Device Details → Source shows agent version (not "REAL") | 0.3.29 | **Pass** | Correctly displays version `0.3.29`. |
| 1.3 | Device Details → Firmware shows BIOS version | 1.39.0 | **Pass** | Correctly displays firmware version `1.39.0`. |
| 1.4 | Site Details → Associated Devices shows device with Source | Version displayed | **Pass** | Agent version is displayed correctly under Associated Devices. |
| 1.5 | Agents page shows device with Mode = version | Version displayed | **Pass** | Mode column displays the agent version correctly. |
| 1.6 | Peripherals listed (printers, scanners) | At least printers shown | **Pass** | Connected printers are listed accurately. |
---
## 2. Apply Configuration
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 2.1 | Apply Configuration with volume: 50, brightness: 50 | Status "completed", volume "applied" (verified: true) | **Fail** | Verification status did not return `verified: true` as expected. |
| 2.2 | Volume actually changes on device | Master volume slider moves to 50% | **Pass** | Device volume changed to 50% as expected. |
| 2.3 | Brightness actually changes on device | Screen brightness changes | **Pass** | Screen brightness changed to 50% as expected. |
| 2.4 | Result shows verification object | before/after/target/verified for both | **Fail** | The verification object is missing or incomplete in the result. |
| 2.5 | Apply Configuration with volume: 0 | Volume muted | **Pass** | Device volume was muted (0%) successfully. |
| 2.6 | Apply Configuration with volume: 100 | Volume max | **Pass** | Device volume was set to maximum (100%) successfully. |
| 2.7 | Apply Configuration with brightness: 0 | Screen very dark | **Fail** | Setting brightness to 0 did not dim the screen. |
| 2.8 | Apply Configuration with brightness: 100 | Screen very bright | **Fail** | Setting brightness to 100 did not set the screen to maximum brightness. |
---
## 3. Direct Connect (Remote Shell)
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 3.1 | Direct Connect with simple command (e.g. echo hello) | Output shows "hello" | **Pass** | Remote Shell opened and submitted the command to the Windows device, the PowerShell now returns "hello". |
| 3.2 | Direct Connect with system info command | Output shows system details | **Pass** | System details were returned and displayed as expected. |
| 3.3 | History shows "Remote Shell" as title | Title is "Remote Shell" | **Pass** | History entry displays "Remote Shell" as the title. |
| 3.4 | History shows correct prompt (user@ or root@) | Prompt matches elevation | **Pass** | The displayed prompt now matches the command elevation level. |
| 3.5 | Command timeout (310s) works | Long-running command times out | **Pass** | Long-running command timed-out after 300 seconds as expected. |
---
## 4. Compose Command (Push Review)
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 4.1 | Push "Reboot System" command | Command queued, device reboots | **Pass** | Command was queued and the device rebooted successfully. |
| 4.2 | Push "Shut Down System" command | Command queued, device shuts down | **Pass** | Command was queued and the device shut down successfully. |
| 4.3 | Push "Start Program" (default notepad.exe) | Notepad opens | **Pass** | Notepad opened on the device as expected. |
| 4.4 | Push "Stop Program" (default notepad.exe) | Notepad closes | **Pass** | The running Notepad process was stopped and closed successfully. |
| 4.5 | Push "Install Program" (e.g. Git.Git) | Program installed | **Pass** | Successfully installed `Notepad++.Notepad++` via the `INSTALL_PROGRAM` command and verified the installation. |
| 4.6 | Push "Uninstall Program" | Program removed | **Pass** | Successfully removed the selected application via the `UNINSTALL_PROGRAM` command. |
| 4.7 | Push "Update Program" | Program updated | **Pass** | Successfully updated the selected application via the `UPDATE_PROGRAM` command. |
| 4.8 | Push "Upgrade All Programs" | All programs updated | **Pass** | Successfully processed all available application updates via the `UPGRADE_ALL_PROGRAMS` command. |
| 4.9 | Push "List Installed Programs" | Registry programs listed with locations | **Pass** | Installed programs and their install locations were listed accurately. |
| 4.10 | Push "Run Command" with custom script | Script executes, output shown | **Pass** | Custom script executed and returned the expected output. |
| 4.11 | Push "Run Command (Unprivileged)" | Command runs as user | **Pass** | Command executed under the standard (unprivileged) user account. |
| 4.12 | Push "Health Check" | CPU/mem/disk/network results shown | **Pass** | Health check completed and returned CPU, memory, disk, and network metrics. |
| 4.13 | Push "Scan Filesystem" | File listing returned | **Pass** | Filesystem scan completed and returned the file listing. |
| 4.14 | Push "List Processes" | Process list returned | **Pass** | Active running processes were listed accurately. |
| 4.15 | Push "List Connections" | Connection list returned | **Pass** | Active network connections were listed accurately. |
| 4.16 | Final Payload Preview shows { command_type, payload } | Preview matches queued command | **Pass** | Payload preview matched the queued command parameters. |
| 4.17 | Push History reuse derives correct template | Reused command has correct params | **Pass** | Reusing the command populated the correct template and parameters. |
---
## 5. Push History
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 5.1 | Push History shows command list | Commands listed with status | **Pass** | Command history list displayed with accurate statuses. |
| 5.2 | Click a command to see details | Result, stdout, stderr shown | **Pass** | Clicking a command displayed its result, `stdout`, and `stderr` details. |
| 5.3 | Command result shows verification object | before/after/target/verified | **Pass** | Verification object (`before`/`after`/`target`/`verified`) was displayed. |
| 5.4 | Compose Command result shows per-key details | Status, message, verification per key | **Pass** | Per-key status, message, and verification details were displayed. |
| 5.5 | Reuse a command from history | Template derived correctly, shell command preserved | **Pass** | Command was reused from history with the template and shell command intact. |
---
## 6. Live Logs & Audit Trail
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 6.1 | Live Logs tab shows log entries | Status snapshots, command events | **Pass** | Live log entries and command events were visible. |
| 6.2 | Task Health badges shown (heartbeat/telemetry/command_poll) | All show "OK" | **Pass** | All task health badges displayed "OK". |
| 6.3 | Audit Trail shows agent_started event | Event with version number | **Pass** | `agent_started` event was logged with the correct version number. |
| 6.4 | Audit Trail shows command execution events | command_completed/failed events | **Pass** | Command execution (`command_completed` / `failed`) events were logged accurately. |
| 6.5 | Live Logs poll every 2s | New entries appear without refresh | **Pass** | New log entries appeared automatically every 2 seconds without refreshing. |
---
## 7. Device Health & Monitoring
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 7.1 | Device Details shows Agent Uptime | Formatted (e.g., "1h 23m") | **Pass** | Agent uptime is formatted and displayed clearly. |
| 7.2 | Device Details shows Agent Restarts | Number (0 on fresh start) | **Pass** | Agent restart count is displayed accurately. |
| 7.3 | Device Details shows Last Offline Reason | e.g. "network partition" or "N/A" | **Pass** | Last offline reason field is populated properly. |
| 7.4 | Telemetry charts show CPU/memory/disk | Charts populated | **Pass** | CPU, memory, and disk telemetry charts are populated with live data. |
| 7.5 | Health check passes | CPU/memory/disk/network all pass | **Pass** | All health check metrics passed. |
---
## 8. Offline & Resilience
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 8.1 | Disconnect network → device shows offline after ~2.5 min | Dashboard shows offline | **Pass** | Dashboard updated the device status to offline after disconnecting the network. |
| 8.2 | Reconnect network → device shows online | Dashboard shows online | **Pass** | Dashboard restored the device status to online after reconnecting the network. |
| 8.3 | Offline escalation alert created after 5 min | Warning alert in Alerts page | **Pass** | Warning alert was generated on the Alerts page after 5 minutes offline. |
| 8.4 | Device goes to sleep → wakes → reconnects | Heartbeat resumes | **Pass** | Agent resumed heartbeat and reconnected automatically after waking from sleep. |
| 8.5 | Force-kill agent → watchdog restarts (if configured) | Agent restarts, uptime resets | **Pass** | Watchdog automatically restarted the agent and reset the uptime. |
---
## 9. Auto-Update
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 9.1 | App checks for updates on launch (30s) | "Last checked" timestamp in Settings | **Pass** | "Last checked" timestamp updated in Settings after launch. |
| 9.2 | Update available notification shown | OS toast + tray tooltip | **Pass** | Update notification appeared via OS toast and system tray tooltip. |
| 9.3 | Download progress shown | Percentage in Settings | **Pass** | Download progress percentage was displayed in Settings. |
| 9.4 | "Restart to Install" installs update | App relaunches with new version | **Pass** | Immediate app restart did not apply the update at first; after restarting the device, the app launched with the new version. |
| 9.5 | Device Details → Source shows new version | Version updated | **Pass** | Device Details → Source updated to show the new agent version. |
---
## 10. Logs & File Locations
| # | Test | Expected | Pass/Fail | Notes |
|---|------|----------|-----------|-------|
| 10.1 | Logs in %PROGRAMDATA%\Homepot\logs\ | agent.log, agent-*.log present | **Pass** | Log files are present in `%PROGRAMDATA%\Homepot\logs\`. |
| 10.2 | No logs in app install directory | No resources\logs\ files | **Pass** | Verified no log files were created inside the application install directory. |
| 10.3 | Log rotation works (10 MiB, 5 backups) | .1, .2, ... files present after rotation | **Pass** | Log rotation works as expected with backup files generated. |
| 10.4 | Elevation marker exists | elevation_installed.marker in ProgramData\Homepot | **Pass** | `elevation_installed.marker` file is present in `%PROGRAMDATA%\Homepot`. |
| 10.5 | Scheduled task "HOMEPOT-Elevation" exists | Task shows in Task Scheduler | **Pass** | `HOMEPOT-Elevation` task is present in Windows Task Scheduler. |
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
