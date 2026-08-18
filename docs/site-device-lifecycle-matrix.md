# Site & Device Lifecycle Matrix

> Reference for the **combined** site × device lifecycle state space. The
> device-only transitions are documented in
> [device-lifecycle-and-ownership.md](device-lifecycle-and-ownership.md). This
> document focuses on how **site-level** and **device-level** actions interact,
> and on every reachable combination of states — including the archive/purge/
> restore behaviour (Model B) and the suspended/unpaired device restore flow.

## States

### Site states

| State       | `is_active` | Meaning                                                            |
| ----------- | ----------- | ------------------------------------------------------------------ |
| `active`    | `true`      | Site is visible on the Dashboard and manages its devices normally. |
| `archived`  | `false`     | Site is hidden; data retained; recoverable via restore.            |

A **purged** site is not a state — the row (and all its data) is deleted and
cannot be restored.

### Device states

| State       | `is_active` | Meaning                                                                               |
| ----------- | ----------- | ------------------------------------------------------------------------------------- |
| `pending`   | `true`*     | Enrolment intent / pre-provisioned slot exists but no endpoint has claimed it.        |
| `active`    | `true`      | Enrolment complete; the management relationship is valid.                             |
| `suspended` | `false`*    | Management temporarily disabled by an operator/policy, or by its site being archived. |
| `unpaired`  | `false`     | Management relationship ended; records retained for audit/analytics.                  |

> `retired` was folded into `unpaired` — both revoke credentials and hide the
> device, and permanent removal is provided by **purge**. The `/retire` endpoint
> is retained for API compatibility but performs an unpair.

\* `pending` and `suspended` devices are normally `is_active=false` after any
archive/unpair/retire action; a brand-new `pending` intent starts `is_active=true`.

`is_active` is a **compatibility/visibility** field, not a second lifecycle
model. Its mapping to lifecycle state is defined once and used consistently.

## Site × Device reachable combinations

A device's lifecycle is independent of its site's lifecycle, so the two
dimensions cross-product. The following table lists every *reachable*
combination (rows marked with the actions that produce them).

| Site       | Device     | `site.is_active` | `device.is_active` | Meaning / how to reach                                              | Visible on Dashboard? | Restorable?              |
| ---------- | ---------- | ---------------- | ------------------ | ------------------------------------------------------------------- | --------------------- | ------------------------ |
| `active`   | `pending`  | true             | true               | A site is active; a device slot awaits claim.                       | Device yes            | n/a (claims to active)   |
| `active`   | `active`   | true             | true               | Normal operating pair.                                              | Yes                   | n/a (already active)     |
| `active`   | `suspended`| true             | false              | Device suspended directly (`suspend`), or site was archived then restored (Model B). | No (device hidden) | Yes — resume → `active` |
| `active`   | `unpaired` | true             | false              | Device unpaired directly (`unpair`/`archive`/`retire`).             | No (device hidden)    | Yes — resume → `active`  |
| `archived` | `suspended`| false            | false              | **Archive site**: active/pending/suspended devices → `suspended`.   | No (site hidden)      | Yes — restore site, then resume device |
| `archived` | `unpaired` | false            | false              | Archive site over an independently-unpaired device.                 | No (site hidden)      | Yes — restore site, then resume device |

> Not reachable: `archived` site with an `active`/`pending` device (archive
> forces them to `suspended`), and `active` site with `is_active=false` device
> (that is exactly the suspended/unpaired rows above).

## Action matrix

How each action changes **both** the site and its devices. Read a row as the
net effect of one user action.

| Action (endpoint)                          | Site effect                              | Device effect                                                                                                        | Reversible?                              |
| ------------------------------------------ | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **Archive site** `DELETE /sites/{id}?mode=archive` | → `archived`, `is_active=false`          | active/pending/suspended → **suspended**, `is_active=false`, `status=offline`; unpaired/retired → `is_active=false` only | Yes — via **restore site** + resume devices |
| **Restore site** `POST /sites/{id}/restore` (Model B) | → `active`, `is_active=true`             | **No change** — devices stay suspended/unpaired with `is_active=false` until individually resumed                    | Yes — archive again                     |
| **Purge site** `DELETE /sites/{id}?mode=purge&confirm=true` | **Deleted** (row + all data)             | **Deleted** with the site                                                                                            | No (permanent)                          |
| **Suspend device** `POST /devices/device/{id}/suspend` | none                                     | `active` → `suspended`                                                                                               | Yes — resume                            |
| **Resume/restore device** `POST /devices/device/{id}/resume` | none                                     | `suspended` or `unpaired` → **active**, `is_active=true`, `status=online`                                            | Yes — suspend/unpair again              |
| **Unpair/archive device** `DELETE /devices/device/{id}?mode=archive` | none                                     | `active`/`suspended` → `unpaired`, `is_active=false`, credentials revoked                                            | Yes — resume (re-activate)              |
| **Purge device** `DELETE /devices/device/{id}?mode=purge&confirm=true` | none                                     | **Deleted** (row + all data)                                                                                         | No (permanent)                          |
| **Retire device** `POST /devices/device/{id}/retire` (alias → unpair) | none                                     | `active`/`suspended`/`unpaired` → `unpaired` (credentials revoked, epoch closed)                                     | Yes — resume                             |
| **Transfer device** `POST /devices/device/{id}/transfer` | none                                     | `active`/`suspended` → `active` in the target site, new epoch, credentials rotated                                  | n/a (new epoch)                          |

### How a technician restores an archived site

Because **restoring a site does not restore its devices** (Model B), the full
recovery of an archived site requires two steps:

1. **Restore the site** — Archived tab → Restore (site becomes `active`).
2. **Restore each device** — open the site, then in *Associated Devices* press
   the restore icon on each grayed-out `suspended`/`unpaired` row.

Purged sites/devices cannot be restored (their data no longer exists).

## Data collection & lifecycle

**Data collection only happens for `active` (or `pending`) devices.** Every
device-authenticated ingestion path — heartbeat, telemetry, command polling,
error/log submission, jobs, alerts — is gated by `get_current_device`
(`backend/src/homepot/app/auth_utils.py`), which rejects authentication with
`403` for any device whose `lifecycle_state` is not `active`/`pending`. So a
`suspended` or `unpaired` device cannot send data.

This applies **uniformly** to real devices, emulated devices, and the in-process
simulated agents — they all authenticate through the same dependency, so there
is one code path and no per-source exceptions.

### Expected behaviour

| Action                      | Device state | Ingested data | Notes                                                         |
| --------------------------- | ------------ | ------------- | ------------------------------------------------------------- |
| Site is active              | `active`     | ✅ collected  | Heartbeats, telemetry, commands, logs all accepted.           |
| **Archive site**            | `suspended`  | ❌ **stopped**| Emulator/agent requests return `403`; no new rows written.    |
| **Restore site + resume dev**| `active`     | ✅ **resumed**| Requests accepted again; data collection picks up where it left off. |
| **Unpair / retire device**  | `unpaired`   | ❌ **stopped**| Same `403` gate; device must be resumed to collect again.     |

### Verifying it on a live system

Observe the device's own collection loop (e.g. an emulator log or the simulated
agent log). When the site is archived you should see the requests start to fail:

```
[heartbeat] error: 403 {"detail":"Device lifecycle state is 'suspended'; only 'active' or 'pending' devices may authenticate"}
[telemetry] error: 403 {"detail":"Device lifecycle state is 'suspended'; only 'active' or 'pending' devices may authenticate"}
```

After restoring the site and resuming the device, the same loop returns to:

```
[heartbeat] OK
[telemetry] OK
```

You can also confirm at the database level: the row count of an ingested table
(e.g. `health_checks`) for the affected device stays flat while suspended and
grows again once the device is resumed.

> A device that is `unpaired` has its API key revoked, so it cannot even
> authenticate. A `suspended` device keeps its key but is still rejected by the
> lifecycle check. In both cases the practical effect is identical: no data
> collection until the device is restored to `active`.

## Design notes / open questions

- `active` site + `suspended` device can arise either from a direct device
  suspend **or** from archiving-then-restoring a site. These look identical and
  both recover via `resume` — there is no separate "archived by site" vs
  "suspended directly" distinction at the device level today.
- Consider a **"Restore all devices"** button on a restored site so technicians
  do not have to restore devices one-by-one.
- Consider whether `resume` should also set a fresh connectivity/health state or
  leave the device `offline` until the agent next heartbeats. Currently resume
  sets `status=online` optimistically.
