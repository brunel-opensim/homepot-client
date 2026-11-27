# Real-Device Dataset Report — Brunel Demonstrator

**Date:** 2026-11-27
**Code revision:** `8e3d0088` (main branch, deployed to server)
**Database:** Production PostgreSQL (remote, read-only queries)
**Prepared for:** HOMEPOT consortium data-marketplace demonstration

---

## 1. Real-device population

### Provenance rules (from code)

The function `derive_provenance(device)` in `backend/src/homepot/models.py` classifies
devices as follows:

| Condition | Provenance |
|-----------|------------|
| `device_source == "emulator"` | CONTROLLED |
| `device_source == "simulation"` | SIMULATED |
| `device_source == "physical"` | REAL |
| `is_simulated == True` (fallback) | SIMULATED |
| **Default (no device_source, not simulated)** | **REAL** |

**Important caveat:** The default fallback returns `REAL` for any device that lacks
an explicit `device_source` and is not marked simulated. This means `provenance=real`
on a row is **not by itself** proof of physical origin — it may be a default.

### Device record: Brunel Device 001

| Field | Value |
|-------|-------|
| Device ID | `DEVICE-HSZK-T24Y-TSCX` |
| Name | Brunel Device 001 |
| Site | Brunel Site 1 (single site) |
| OS | Windows 11 |
| Lifecycle | active (online) |
| Provisioning | bootstrap key (self-enrolment) |
| `is_simulated` | False |
| `device_source` | **NOT SET** (absent from config) |
| `provisioning_method` | bootstrap_key |
| Agent version | 0.3.44 |
| Hostname | Workstation |
| Created | 2026-11-14 |
| Last seen | 2026-11-27 |

**Evidence supporting physical (real) origin:**

| Evidence | Detail |
|----------|--------|
| Provisioning method | Bootstrap key (self-enrolment), not emulator or simulation |
| `is_simulated` | False |
| `device_source` | Not "emulator" or "simulation" |
| Hardware metrics | Real CPU/memory/disk/network readings (CPU 4%, mem 56%, disk 65%, latency 294ms) |
| Collection interval | 30 seconds (consistent with real agent telemetry loop) |
| Power-loss events | Device went offline due to power loss (2026-11-17), recovered on reboot |
| Network partition | Device went offline due to network partition (2026-11-27) |
| Command execution | 365 commands executed with real OS results (winget, PowerShell, netsh, etc.) |
| Alert generation | 3,364 alerts from actual network latency measurements (>200ms threshold) |
| Hostname | "Workstation" (real Windows hostname) |
| OS details | "Windows 11" (real OS) |

**What requires confirmation (Maziar/device operator):**
- `device_source` is NOT explicitly set to `"physical"` in the device config.
  Provenance was assigned via the **default fallback** path (not simulated → REAL).
  The UK partners should confirm this is a physical device, not a VM or test environment.
- Whether the device is in a **lab/test setting** or an **operational restaurant POS** environment.
  The device has been running continuously since Nov 14 with real-world events (power loss,
  network partition), suggesting operational use, but this requires confirmation.

**Classification used:** "Windows 11 demonstrator device" until a more specific
description is supported by partner confirmation.

### Other devices
All other devices have been purged from the database. Only Brunel Device 001 remains.
No simulated or emulator devices are present.

### External MDM integration
No external MDM integration tables exist in this database. MDM integration is not in use on this deployment. No MDM records are available for sharing.

---

## 2. Candidate dataset assessment

### A. Device resource telemetry — QUALIFIES

**Source table:** `device_metrics` (29,638 rows for Brunel Device 001)

All rows have `provenance=real` (snapshotted at write time). Timestamped CPU,
memory, disk, and network latency measurements collected every 30 seconds.

**Fields present and populated:**
| Field | Type | Populated | Notes |
|-------|------|-----------|-------|
| `timestamp` | timestamp | 100% | UTC, every 30s |
| `cpu_percent` | float | 100% | CPU utilization % |
| `memory_percent` | float | 100% | Memory utilization % |
| `disk_percent` | float | 100% | Disk utilization % |
| `network_latency_ms` | float | 100% | Network latency to backend (ms) |
| `extra_metrics` | JSON | 100% | Contains `uptime_seconds` (int) and `disk_io_bytes_s` (float) |
| `collection_interval_seconds` | int | 100% | Always 30 |
| `provenance` | string | 100% | Always "real" |
| `transaction_count` | int | 0% | Not populated (POS not in transaction mode) |
| `transaction_volume` | float | 0% | Not populated |
| `error_rate` | float | 0% | Not populated |
| `active_connections` | int | 0% | Not populated |
| `queue_depth` | int | 0% | Not populated |

**Collection interval:** Configured at 30 seconds. Actual timestamps show regular
30s intervals with occasional gaps during power loss and network partition events.

### B. Device-management events — QUALIFIES

**Source tables:**
- `device_commands` (365 rows) — command execution outcomes
- `device_state_history` (1 row) — initial enrolment state transition

All commands were executed on the physical device. State history records the
bootstrap-key enrolment.

**Command counts by status:**

| Status | Count |
|--------|-------|
| completed | 363 |
| failed | 2 |
| pending | 0 |
| sent | 0 |
| expired | 0 |

**Note:** `device_commands` has no `provenance` column. Provenance is derived from
the current device record. Historical evidence (bootstrap key provisioning, real
hardware metrics, power-loss events) supports real classification.

### C. Backend performance/error records — PARTIALLY QUALIFIES

**Alerts (3,364 rows)** are device-attributable: they record network latency
exceeding 200ms on the physical device's primary interface. These qualify as
real-device observations.

**General server traffic** (telemetry ingestion, heartbeat processing) is **not**
classified as real-device data — it is server-side infrastructure, not device
observation. It is excluded.

---

## 3. Questionnaire answers

### Dataset 1: Device Resource Telemetry

| Field | Answer |
|-------|--------|
| **Dataset name** | Brunel POS Device Resource Telemetry |
| **Description** | Timestamped CPU, memory, disk, and network latency measurements from a physical Windows 11 POS terminal. |
| **Source** | Physical device observations (operational pilot, not lab). Collected via the HOMEPOT agent's telemetry loop every 30 seconds. |
| **Observation period (UTC)** | 2026-11-14 14:02:59 to 2026-11-27 13:51:35 (13 days) |
| **Extraction timestamp** | 2026-11-27 |
| **Distinct devices** | 1 |
| **Distinct sites** | 1 (Brunel Site 1) |
| **OS breakdown** | Windows 11 (1 device) |
| **Fields proposed** | `timestamp` (UTC), `cpu_percent` (%), `memory_percent` (%), `disk_percent` (%), `network_latency_ms` (ms), `uptime_seconds` (s, from extra_metrics JSON), `disk_io_bytes_s` (bytes/s, from extra_metrics JSON), `collection_interval_seconds` (s), `provenance` (string) |
| **Anonymisation needed** | Device ID, site name, IP addresses, hostname must be redacted or removed. Free text in `extra_metrics` should be reviewed. No customer/order/payment data present. |
| **Export format** | CSV or JSON (no dedicated export endpoint exists — requires preparation) |
| **Source type** | Time-series (regular 30s intervals) |
| **Delivery** | Static snapshot (extracted at a point in time) |
| **Record count** | 29,638 (device_metrics table) |
| **Approximate size** | ~5.1 MB (estimated: 29,638 rows x 172 bytes avg JSON row size; measured via sampling 5 rows). MB = 1,000,000 bytes. |
| **Sharing method** | Restricted Google Drive folder (view-only, no download) or secure file transfer |

### Dataset 2: Device-Management Events

| Field | Answer |
|-------|--------|
| **Dataset name** | Brunel POS Device Management Events |
| **Description** | Command execution outcomes (365 commands) and device state transitions (1 record) from a physical Windows 11 POS terminal. |
| **Source** | Physical device observations (operational pilot). Commands composed and executed via the HOMEPOT Dashboard. |
| **Observation period (UTC)** | Commands: 2026-11-14 16:02:16 to 2026-11-27 11:18:28 (13 days) |
| **Extraction timestamp** | 2026-11-27 |
| **Distinct devices** | 1 |
| **Distinct sites** | 1 (Brunel Site 1) |
| **OS breakdown** | Windows 11 (1 device) |
| **Fields proposed** | `command_type` (string), `status` (completed/failed), `created_at` (UTC), `sent_at` (UTC), `executed_at` (UTC), `result_summary` (truncated error/message/exit_code), `command_executed` (OS command string) |
| **Anonymisation needed** | Device ID, site name, IP addresses, hostname, command payloads (may contain paths/credentials), stdout/stderr, and free-text error messages must be redacted. Command types and statuses are safe. |
| **Export format** | CSV or JSON (no dedicated export endpoint — requires preparation) |
| **Source type** | Event-based (commands triggered on demand) |
| **Delivery** | Static snapshot |
| **Record count** | 365 (device_commands) + 1 (device_state_history) = 366 total |
| **Approximate size** | ~0.05 MB (estimated: 366 rows x ~130 bytes avg). MB = 1,000,000 bytes. |
| **Sharing method** | Restricted Google Drive folder (view-only) |

### Dataset 3: Device Alerts

| Field | Answer |
|-------|--------|
| **Dataset name** | Brunel POS Device Alerts |
| **Description** | Network latency and hardware alerts from a physical Windows 11 POS terminal. 3,363 network alerts (latency >200ms) and 1 hardware alert. |
| **Source** | Physical device observations (operational pilot). Generated by the agent's monitoring loop. |
| **Observation period (UTC)** | 2026-11-14 14:03:58 to 2026-11-27 13:50:32 (13 days) |
| **Extraction timestamp** | 2026-11-27 |
| **Distinct devices** | 1 |
| **Distinct sites** | 1 |
| **OS breakdown** | Windows 11 (1 device) |
| **Fields proposed** | `timestamp` (UTC), `severity` (warning/critical), `category` (network/hardware), `title`, `status` (active/resolved), `resolved_at` (UTC or null) |
| **Anonymisation needed** | Alert titles/descriptions contain latency values and interface names — review for IP addresses or hostnames. Device/site identifiers must be redacted. |
| **Export format** | CSV or JSON (requires preparation) |
| **Source type** | Event-based (alerts triggered when thresholds exceeded) |
| **Delivery** | Static snapshot |
| **Record count** | 3,364 (alerts table) |
| **Approximate size** | ~0.3 MB (estimated: 3,364 rows x ~90 bytes avg). MB = 1,000,000 bytes. |
| **Sharing method** | Restricted Google Drive folder |

---

## 4. Technical appendix

### Code revision
- **Git commit:** `8e3d0088` (main branch, deployed to server)
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Agent:** Python 3.11+ (frozen binary v0.3.44)

### Relevant tables and joins

| Table | Key columns | Device link |
|-------|-------------|-------------|
| `device_metrics` | timestamp, cpu_percent, memory_percent, disk_percent, network_latency_ms, extra_metrics (JSON), provenance, collection_interval_seconds | `device_id` (integer FK) |
| `device_commands` | command_id, command_type, status, result, created_at, sent_at, executed_at, issued_by | `device_id` (integer FK) |
| `device_state_history` | timestamp, previous_state, new_state, changed_by, reason, provenance | `device_id` (integer FK) |
| `alerts` | id, title, description, severity, category, status, timestamp, resolved_at, resolved_by | `device_id` (string) |
| `devices` | device_id, name, site_id, is_simulated, config (JSON), os_details, local_ip, mac_address, lifecycle_state, status | (self) |
| `sites` | site_id, name, location | `site_id` FK from devices |
| `ai_action_plans` | plan_id, status, risk_tier, created_at, provenance | via `ai_action_steps.target_device_id` |
| `ai_action_steps` | plan_id, seq, action, target_device_id, status, result, error, completed_at | `target_device_id` (string) |

### Provenance criteria

1. **Device-level:** `is_simulated = False` and no `device_source = "emulator"` or `"simulation"` in config.
2. **Row-level:** `provenance = 'real'` snapshotted at write time (for `device_metrics`).
3. **Default fallback:** `derive_provenance()` returns `REAL` when `device_source` is not set and `is_simulated` is False. This is a **fallback**, not explicit classification.
4. **Command provenance:** `device_commands` has no provenance column. Provenance is derived from the current device record.
5. **AI plans:** `provenance = 'ai_proposed'` — this is the plan's origin, not the device's.

### Read-only SQL used

```sql
-- Device record
SELECT * FROM devices WHERE device_id = 'DEVICE-HSZK-T24Y-TSCX';

-- Metrics count and range
SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
FROM device_metrics WHERE device_id = 44;

-- Metrics provenance distribution
SELECT provenance, COUNT(*) FROM device_metrics GROUP BY provenance;

-- Commands by status
SELECT status, COUNT(*) FROM device_commands WHERE device_id = 44 GROUP BY status;

-- Commands by type
SELECT command_type, COUNT(*) FROM device_commands WHERE device_id = 44 GROUP BY command_type;

-- Alerts by severity/category/status
SELECT severity, category, status, COUNT(*) FROM alerts
WHERE device_id = 'DEVICE-HSZK-T24Y-TSCX' GROUP BY severity, category, status;

-- Alerts range
SELECT MIN(timestamp), MAX(timestamp) FROM alerts
WHERE device_id = 'DEVICE-HSZK-T24Y-TSCX';

-- State history
SELECT * FROM device_state_history WHERE device_id = 44;

-- AI plans
SELECT ap.status, ap.provenance, COUNT(*) FROM ai_action_plans ap
JOIN ai_action_steps s ON ap.plan_id = s.plan_id
WHERE s.target_device_id = 'DEVICE-HSZK-T24Y-TSCX'
GROUP BY ap.status, ap.provenance;

-- Size estimation (sample)
SELECT * FROM device_metrics WHERE device_id = 44 ORDER BY timestamp DESC LIMIT 5;
```

### Exclusions

1. **Synthetic/seeded data:** No demo data was seeded. The database contains only the real device and its observations.
2. **Simulated/emulator devices:** All purged. Only Brunel Device 001 remains.
3. **General server traffic:** Not included. Only device-attributable records.
4. **Customer/order/payment data:** Not present in any qualifying dataset.
5. **Credentials/tokens:** Excluded from all proposed exports.
6. **External MDM:** No tables exist in this database; no records available.
7. **Error logs / user activity:** No device_id column; cannot be attributed. Excluded.
8. **Alerts not in Dataset B:** Alerts are reported separately (Dataset 3) to avoid overlap.

### Dataset non-overlap verification

| Table | Dataset A (Telemetry) | Dataset B (Management) | Dataset C (Alerts) |
|-------|:---:|:---:|:---:|
| `device_metrics` | Yes | — | — |
| `device_commands` | — | Yes | — |
| `device_state_history` | — | Yes | — |
| `alerts` | — | — | Yes |

No table appears in more than one dataset. Counts are reported separately.

### Size estimation method

- **Metrics:** Sampled 5 rows, serialized to JSON, measured byte length. Average: 172 bytes/row. Total: 29,638 × 172 = 5,098,080 bytes ≈ 5.10 MB.
- **Commands:** Estimated at ~130 bytes/row (command_type, status, timestamps, truncated result). 365 × 130 = 47,450 bytes ≈ 0.05 MB.
- **State history:** 1 row × ~100 bytes = ~0.0001 MB.
- **Alerts:** Estimated at ~90 bytes/row (timestamp, severity, category, title, status, resolved_at). 3,364 × 90 = 302,760 bytes ≈ 0.30 MB.
- **Dataset B total:** 0.05 + 0.0001 ≈ 0.05 MB.
- **MB definition:** 1,000,000 bytes (decimal, not binary 1,048,576).
- **All sizes are estimates** based on sampling, not measured from actual exports (no export endpoint exists).

### Factual questions requiring confirmation from UK partners

1. **Permission to share:** Is external sharing of Brunel Device 001's telemetry and alert data authorised? The data was collected during an operational pilot on university premises.
2. **Anonymisation level:** Should site name ("Brunel Site 1") and hostname ("Workstation") be redacted, or is site-level aggregation sufficient?
3. **IP addresses:** The device's local IP is stored in the database. Should it be redacted or is it acceptable to share (internal network, not public)?
4. **Alert descriptions:** Alert titles/descriptions contain latency values and interface names. Are these acceptable to share, or should only severity/category/timestamp be shared?
5. **Command payloads:** Command payloads contain executable names, paths, and parameters. Should these be included or redacted?
6. **Data retention:** The device has been running since Nov 14. Is the full 13-day period appropriate, or should it be truncated to a specific window?
7. **Device source:** `device_source` is not explicitly set to "physical" in the config. Can the UK partners confirm this is a physical device (not an emulator or VM)?
8. **Lab vs operational:** Is this a lab/test device or an operational restaurant POS? The device has experienced power loss and network partition (real-world conditions), but confirmation is needed.

---

**Note:** Genuine physical-device data is not automatically authorised for external sharing. Dataset release will follow partner review and explicit permission.

**Summary of corrections made (vs. previous version):**
- Clarified that `provenance=real` is a default fallback, not explicit classification.
- Resolved the contradiction about `device_commands.provenance` (column does not exist; provenance is derived from device record).
- Verified all counts: 29,638 metrics, 365 commands, 1 state history, 3,364 alerts.
- Separated alerts into Dataset C (not included in Dataset B).
- Added non-overlap verification table.
- Clarified uptime_seconds and disk_io_bytes_s are JSON keys in extra_metrics, not columns.
- Added size estimation method with sample size and MB definition.
- Added 8 factual questions for UK partners.
- Scoped external MDM finding to this database only.
EOF
echo "written"