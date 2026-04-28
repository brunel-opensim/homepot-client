# User App — Page Wireframes
# Branch: feature/user-app-frontend-scaffold (PR #149)
# Author: Radhakrishnan (kasi.v@redblox.io)
# Date: 2026-04-28

---

## Overview

4-page layout for the HOMEPOT User App.
Single card/window layout with a tab bar for navigation (Pages 2–4).
Page 1 is first-run only.

---

## Navigation Flow

```
[First Launch]
      │
      ▼
┌─────────────┐     Provisioning done
│  Page 1     │ ──────────────────────►  ┌─────────────┐
│  Setup /    │                          │  Page 2     │
│  Wizard     │                          │  Home /     │◄── Default view
└─────────────┘                          │  Dashboard  │
                                         └──────┬──────┘
                                                │  Tab bar
                                    ┌───────────┼───────────┐
                                    ▼                       ▼
                             ┌────────────┐         ┌────────────┐
                             │  Page 3    │         │  Page 4    │
                             │ Permissions│         │Device Info │
                             └────────────┘         └────────────┘
```

---

## Page 1 — Setup / Provisioning Wizard (First Run Only)

```
┌─────────────────────────────────┐
│         HOMEPOT Agent           │
│                                 │
│   ●━━━━━○━━━━━○   Step 1 of 3  │
│                                 │
│   Welcome! Let's set up         │
│   your device.                  │
│                                 │
│   Site ID *                     │
│   ┌─────────────────────────┐   │
│   │  Enter your Site ID     │   │
│   └─────────────────────────┘   │
│                                 │
│   Device Name (optional)        │
│   ┌─────────────────────────┐   │
│   │  e.g. radha-Laptop      |   │
│   └─────────────────────────┘   │
│                                 │
│   ┌─────────────────────────┐   │
│   │   🔐  Login with SSO    │   │
│   └─────────────────────────┘   │
│                                 │
│             [ Next → ]          │
└─────────────────────────────────┘
```

**Purpose:** Register the device with the backend via /provision API.
**Elements:**
- Step progress indicator (3 steps)
- Site ID input (required)
- Device Name input (optional)
- SSO / Auth login button
- Next button → transitions to Page 2 on completion
- Saves auth token securely on device

---

## Page 2 — Home / Status Dashboard (Default View)

```
┌─────────────────────────────────┐
│  HOMEPOT Agent       Radha  👤  │
│ ─────────────────────────────── │
│  ┌──────────────────────────┐   │
│  │  ●  SECURE — ONLINE      │   │  ← green
│  │     Last sync: 2 min ago │   │
│  └──────────────────────────┘   │
│                                 │
│   CPU        MEM       DISK     │
│   (◕)        (◑)       (◔)      │
│   42%        61%       28%      │
│                                 │
│  ┌──────────────────────────┐   │
│  │ ❤  Heartbeat: 13:52:01  │    │
│  └──────────────────────────┘   │
│                                 │
│ ┌──────┬───────────┬─────────┐  │
│ │ Home │   Perms   │Settings │  │
│ └──────┴───────────┴─────────┘  │
└─────────────────────────────────┘
```

**Purpose:** At-a-glance confirmation the agent is running and transmitting telemetry.
**Elements:**
- Status badge: SECURE / ONLINE (green) or OFFLINE (red)
- Last sync timestamp
- 3 gauge rings: CPU, Memory, Disk — data from local IPC /last-telemetry endpoint
- Heartbeat timestamp
- Tab bar navigation (Home | Perms | Settings)

**Note:** Gauge ring data depends on /last-telemetry IPC from Dealdio Python agent (Phase 3).

---

## Page 3 — Permissions & Access Control

```
┌─────────────────────────────────┐
│  HOMEPOT Agent     Permissions  │
│ ─────────────────────────────── │
│                                 │
│  Control what the Admin         │
│  Dashboard can access.          │
│                                 │
│  Root / Full Access             │
│  Allows full system scan   [ON] │
│  ─────────────────────────────  │
│                                 │
│  Process Monitoring             │
│  View running processes   [ON]  │
│  ─────────────────────────────  │
│                                 │
│  File System Access             │
│  Scan files & folders    [OFF]  │
│  ─────────────────────────────  │
│                                 │
│  Network Monitoring             │
│  Track connections        [ON]  │
│  ─────────────────────────────  │
│                                 │
│  ⚠  Changes apply immediately   │
│                                 │
│ ┌──────┬───────────┬─────────┐  │
│ │ Home │   Perms   │Settings │  │
│ └──────┴───────────┴─────────┘  │
└─────────────────────────────────┘
```

**Purpose:** Let the employee explicitly grant or revoke access levels to the Admin Dashboard.
**Elements:**
- Toggle list for rule-based security parameters
- Root / Full Access toggle
- Process Monitoring toggle
- File System Access toggle
- Network Monitoring toggle
- Warning label: changes apply immediately
- Tab bar navigation

**Note:** Toggle state persistence needs a decision — local storage or backend sync?

---

## Page 4 — Device Info & Settings

```
┌─────────────────────────────────┐
│  HOMEPOT Agent    Device Info   │
│ ─────────────────────────────── │
│                                 │
│  Device DNA                     │
│  ┌──────────────────────────┐   │
│  │ Hostname   │ Radha-Laptop |  │
│  │ MAC Addr   │ A1:B2:C3... │   │
│  │ Local IP   │ 192.168.1.x │   │
│  │ OS         │ Ubuntu 22   │   │
│  │ Agent Ver  │ v0.1.0      │   │
│  └──────────────────────────┘   │
│                                 │
│  ┌──────────────────────────┐   │
│  │  ↺  Check for Updates    │   │
│  └──────────────────────────┘   │
│                                 │
│  ┌──────────────────────────┐   │
│  │  🔌  Disconnect & Unpair │   │  ← red / danger
│  └──────────────────────────┘   │
│  Removes token, resets app      │
│                                 │
│ ┌──────┬───────────┬─────────┐  │
│ │ Home │   Perms   │Settings │  │
│ └──────┴───────────┴─────────┘  │
└─────────────────────────────────┘
```

**Purpose:** Troubleshooting, maintenance, and device unpairing.
**Elements:**
- Device DNA table: Hostname, MAC Address, Local IP, OS Details, Agent Version
- Check for Updates button
- Disconnect & Unpair button (danger — red styling)
  - Wipes local credentials and resets app back to Page 1 (Setup Wizard)
- Tab bar navigation

---

## General UX Notes

- No heavy navigation bars — simple tab/pill selector at bottom
- Use Radix UI + Tailwind primitives only — no external charting libraries
- Keep bundle size small (target: under 300KB JS)
- Card dimensions suit both desktop window (Electron) and mobile screen (Capacitor)
- Top tab bar for desktop (Electron), bottom tab bar for mobile (Capacitor) — decide early
