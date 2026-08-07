# Device Credentials & Tokens

This guide defines the distinct secrets and identifiers involved in device
provisioning, authentication, and push notification delivery in HOMEPOT. Device
emulators model these identities so that simulated devices behave like real
hardware.

The four terms are **not interchangeable**. In short:

| Term | Scope | Purpose | Who generates | Reusable across devices? |
|------|-------|---------|---------------|--------------------------|
| `bootstrap_key`   | site | one-time invitation used to *create* devices on a site | Technician (Dashboard) | **Yes** (many devices per key) |
| `api_key`         | device | authenticates the *device* to the backend after provisioning | Backend at provision | no (one per device) |
| `device_token`   | device | legacy alias of `api_key` **or** a push-registration identifier | Backend / OS | one per device |
| `push_channel`   | device/OS | kind of push transport (`fcm` / `wns` / `apns` / `None`) | derived from OS | n/a |

---

## `bootstrap_key` — the site invitation secret

- **What it is:** a secret key generated once **per site** and shared with the
  User App install to enrol devices on that site.
- **Flow (Dashboard technician → User):**
  1. Technician generates a key for the site:
     `POST /api/v1/sites/{site_id}/bootstrap-key`
     (backed by `SitesBootstrapKeyEndpoint.generate_bootstrap_key`; the hash is
     stored at `site.bootstrap_key_hash`). The plaintext is shown **only once**.
  2. The key is sent out-of-band to the user.
  3. A device uses it to provision itself:
     `POST /api/v1/devices/bootstrap-provision`
     (`DeviceBootstrapProvisionEndpoint` → `verify_bootstrap_key`).
- **Reusable:** Yes. `verify_bootstrap_key` (`auth_utils.py`) only compares the
  submitted key against the site's stored hash; it is not rotated or invalidated
  after one use. The same key can add many devices to the same site.
- **Revocation:** Technician calls
  `DELETE /api/v1/sites/{site_id}/bootstrap-key` to invalidate it
  (`SitesBootstrapKeyEndpoint.revoke_bootstrap_key`).
- **Dev key:** in non-production, a well-known dev key may be accepted
  (`is_dev_bootstrap_key`, `allow_dev_key=True`) for simulated/emulator
  enrolment. It is never valid against a real deployment.
- **Important:** the `bootstrap_key` is the *enrolment* secret. It is **not**
  the authentication the device uses once provisioned.

---

## `api_key` — the device authentication secret

- **What it is used for:** after provisioning, every authenticated request the
  *device* makes (heartbeats, telemetry, command ACKs, DNA updates) is signed
  with this key. It is sent on the `X-API-Key` header alongside `X-Device-ID`.
- **How it is created:** generated fresh per device at provisioning time
  (`secrets.token_urlsafe(32)` in `agent_service.py`). Only the hash
  (`api_key_hash`) is stored server-side; the plaintext is returned once to the
  device at provision.
- **Scoped:** one per device. Rotating or revoking it affects only that device
  (see `DeviceCredential` / `api_key_hash` handling).

---

## `device_token` — two distinct meanings

The term `device_token` is overloaded and currently used for **two unrelated
things**. This ambiguity is a source of confusion and a known discrepancy; see
the open question at the end.

### Meaning 1 — legacy alias of `api_key`

In the self-enrolment / SSO provisioning flow, the provision response exposes a
`device_token` field as a backward-compatible alias alongside `api_key`
(see `DeviceProvisionResponse` in `schemas/provision.py`). Here
`device_token` ≈ `api_key`; it is **not** a separate secret.

### Meaning 2 — push transport registration identifier

A push-*registration* identifier the OS/device registers with the backend so the
server can push (not poll) for commands:

| OS    | Channel (`push_channel`) | Example `device_token` shape |
|-------|--------------------------|------------------------------|
| Android | `fcm` | `fcm:emulator:<hex>` |
| Windows | `wns` | `https://wns.notify.windows.com/?token=emulator:<hex>` |
| iOS / iPadOS | `apns` | `apns://emulator:<hex>` |
| Linux / macOS | `None` | polling only (no push token) |

In the real agent this is what `send_registration` forwards as `device_token`
for push delivery (e.g. a WNS channel URI). The emulators derive a synthetic
token from `derive_push_channel(os_details)` (`emulators/pos_engine.py`).

> ⚠️ **Discrepancy:** The emulator currently sends this push token in
> `device-dna` registration, but the `AgentRegisterRequest` schema does **not**
> accept a `device_token` field, so the backend drops it and `device_token` is
> stored as `None` for emulator-provisioned devices. Resolving whether `device_token`
> should model the push-transport identifier server-side, and on which endpoint
> (DNA registration vs. a dedicated push-registration call), is an open task.

---

## `push_channel` — the platform's push transport

- What push transport the device's OS uses. Derived from `os_details` by
  `derive_push_channel()` (`emulators/pos_engine.py`).
- Not itself a secret — it is metadata that `device_token` (meaning 2) belongs
  to.

---

## Summary of a device lifetime (emulator)

1. **Enrolment** — the emulator calls bootstrap-provision with the site
   `bootstrap_key`. The backend creates the device and returns `device_id` +
   `api_key`.
2. **Registration** — the emulator registers its DNA (`POST /devices/device-dna`),
   including `os_details` and (in the emulator) its push `device_token`.
3. **Authentication** — subsequent heartbeats, telemetry, and command handling
   use `X-Device-ID` + `X-API-Key` derived from the `api_key`.
4. **Command delivery** — push-capable OSes may rely on the `device_token`
   (meaning 2) / `push_channel`; others poll `/devices/pending`.

See also: [`docs/device-registration.md`](device-registration.md),
[`docs/device-emulators.md`](device-emulators.md).