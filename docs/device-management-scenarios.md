# Managing multiple devices under one site

This document describes the recommended workflows when an engineer wants to keep
an existing device enrolled while enrolling additional devices under the same
site. The bootstrap key is shared across all devices in a site, so multiple
devices can be enrolled without re-provisioning the key.

## Background

- One site has **one bootstrap key** used by all devices in that site.
- Each enrolled device gets its **own unique device ID and API key** — devices
  are independent after enrolment.
- **Device names must be unique within a site** (case-insensitive). A name can
  only be reused after the device is **purged** (hard-deleted) from the database.
  Unpairing (soft-delete) does **not** free the name.
- There is **no limit** on how many devices can be enrolled per site, and
  **no "primary device"** concept — all devices are peers.

## Scenario 1 — Keep both devices running

**Use when:** You want both the old and new device active simultaneously (e.g.,
a laptop and a desktop both managed under the same site).

### Steps

1. Enrol the new device using the **same Site ID and Bootstrap Key** via the
   User App (or the dashboard bootstrap-provision endpoint).
2. Choose a **different device name** (e.g., "GetFudo Device 002" alongside
   "GetFudo Device 001"). The name check will reject duplicates.
3. Both devices appear under **Associated Devices** on the site dashboard.
4. Both devices send heartbeats independently and show as online.

### What happens

- No change to the existing device. It keeps running, sending heartbeats, and
  receiving commands.
- The new device is created with its own device ID, credentials, and lifecycle
  state (starts as `pending`, transitions to `active`).
- Both devices are independently manageable (commands, config, Direct Connect).

### Considerations

- Both devices consume server resources (heartbeats, metrics, commands).
- Commands sent to one device do not affect the other.
- If you want to target a specific device, use its device ID in the command or
  AI query.

---

## Scenario 2 — Suspend one device temporarily

**Use when:** You want to keep a device enrolled but temporarily take it out
of service (e.g., maintenance, troubleshooting, or switching to a replacement
while keeping the option to return).

### Steps

1. On the dashboard, open the device you want to suspend.
2. Click **Suspend** (or call `POST /api/v1/devices/{device_id}/suspend`).
3. The device's lifecycle state becomes `suspended`, `is_active = False`.
4. The device stops accepting commands and shows as offline in the dashboard.

### What happens

- The device row remains in the database (not purged). Its name is **not**
  freed — you cannot enrol a new device with the same name while it is suspended.
- The User App on the device, if still running, will receive a 403 on its
  next poll and should stop sending heartbeats.
- The device's historical data (metrics, commands, logs) is preserved.

### To return to the device later

1. Open the device on the dashboard.
2. Click **Resume** (or call the resume endpoint).
3. Lifecycle state returns to `active`, `is_active = True`.
4. The User App resumes normal operation (if still installed) or you can
   re-launch it.

### Considerations

- Suspended devices are hidden from the default "Associated Devices" view? No —
  they appear with `is_active = False` and a grayed-out row. Use
  `include_unpaired` is not needed; suspended devices are still listed.
- Suspending does not revoke the device's credentials — they remain valid for
  when the device is resumed.
- AI proposals can still target suspended devices, but commands will be
  rejected (lifecycle gate).

---

## Scenario 3 — Unpair / disconnect a device

**Use when:** You want to permanently remove a device from the site's active
management, but keep its historical data (metrics, commands, logs) for audit.
The device's name is **not** freed — only a purge frees the name.

### Steps (from the User App)

1. On the device, open the User App.
2. Click **Disconnect & Unpair Device**.
3. Confirm the unpair prompt.
4. The User App stops the agent, revokes local credentials, and notifies the
   backend.

### Steps (from the dashboard)

1. Open the device on the dashboard.
2. Click **Unpair** (or call `POST /api/v1/devices/{device_id}/unpair`).
3. The device's lifecycle state becomes `unpaired`, `is_active = False`.
4. Credentials are revoked.

### What happens

- The device row remains in the database (soft delete). Its name is **not**
  freed (per the name-uniqueness policy).
- The device disappears from the default "Associated Devices" view (use
  `include_unpaired=true` to see it).
- Historical data (metrics, commands, logs, lifecycle events) is preserved.
- The device can be **re-enrolled** (same device_id, if credentials are
  restored) but cannot be re-enrolled with a different name unless purged.

### To fully remove (purge)

1. On the dashboard, open the unpaired device.
2. Click **Purge** (or call `POST /api/v1/devices/{device_id}/purge` with
   `confirm: true`).
3. The device and all its associated data are **permanently deleted**.
4. The device name is now free for reuse.

### Considerations

- Purge is irreversible. Only use after confirming the device is no longer
  needed.
- After purge, a new device can be enrolled with the same name.
- Unpaired devices still appear in `include_unpaired=true` queries for audit.

---

## Scenario comparison

| Aspect | Keep both | Suspend | Unpair | Purge |
|--------|-----------|---------|--------|-------|
| Device row in DB | Yes | Yes | Yes (soft delete) | No (hard delete) |
| Name reusable | No | No | No | Yes |
| Historical data | Preserved | Preserved | Preserved | Deleted |
| Credentials valid | Yes | Yes | Revoked | N/A |
| Shows in dashboard (default) | Yes | Yes (grayed) | No | No |
| Shows with `include_unpaired=true` | Yes | Yes | Yes | No |
| AI can target it | Yes | No (commands rejected) | No | No |
| Reversible | N/A | Yes (resume) | Yes (re-enroll) | No |

## Enrollment flow (new device, same site)

1. Open the User App on the new device.
2. Enter the **Site ID** and **Bootstrap Key** (same as existing devices).
3. The User App calls `check-name` to verify the chosen name is available.
4. If available → proceed with provisioning. The new device is created with
   a unique device ID and its own API key.
5. If not available → the User App reports "Device name already in use" and
   the user must choose a different name.

### Important notes for engineers

- **Bootstrap key is shared** across all devices in a site. Do not treat it
  as a per-device secret.
- **Device names must be unique within a site** (case-insensitive). Plan
  names ahead: "GetFudo Device 001", "GetFudo Device 002", etc.
- **Unpairing does not free the name.** If you unpair a device and want to
  reuse its name, you must purge it first.
- **Multiple devices can be online simultaneously.** There is no "primary
  device" or "one device per site" constraint.
- **The old device going offline after enrolling a new one** is not an
  automatic backend action. It means the old device stopped sending
  heartbeats (moved, uninstalled, or network issue). Check `last_heartbeat_at`
  and the old device's User App logs.
PYEOF
echo written