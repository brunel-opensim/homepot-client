# Access Roles: Admin, Technician and Guest — Design Proposal

**Status:** Draft for team review
**Scope:** the role model (Admin / Technician / Guest) and reviewer access to the dashboard
**Reviewed:** 2026-10-14
**Related:** `docs/rbac-hardening-plan.md`

---

## 1. Why this document

We want to invite a small number of external reviewers and colleagues to log into
the dashboard, exercise it, and give feedback. At the same time, real partner
engineers are joining to add and integrate devices. Both need access that is
*deliberately different* from each other and from the system owner.

This document defines the three access roles — **Admin**, **Technician** and
**Guest** — and proposes how each behaves, including a **stage-aware** Guest that
is read-only once real devices arrive but may operate devices during development.

It is a **design proposal for discussion**. Nothing here is implemented. It is
deliberately paired with `docs/rbac-hardening-plan.md`, because these roles rest
on the same role model and inherit some of the same gaps.

Evidence is cited as `file:line` so each claim can be checked directly.

---

## 2. Requirements and constraints

- **Admin, Technician and Guest** must be clearly distinct in what they can do.
- Guests see the **main Dashboard** and can **communicate with the AI** for
  recommendations and device-related activity.
- At this **development stage the devices are demo devices** — they are not real
  customer devices — so the risk of granting reviewers *more* is low. We would
  like reviewers to be able to **operate** devices now, then tighten to
  **read-only** once real devices are in play.
- Technicians at this stage are the **test engineers from Dealdio and Getfudo**
  who help add real devices and integrate them.
- **No simulation or emulation data may be written to the production database.**
  Fake devices must not pollute real-device visibility. Guests look at real,
  scoped data — not a sandbox populated with fake rows.
- **No role may ever grant itself more access than it was given** (see
  `docs/rbac-hardening-plan.md:142-158`).

---

## 3. The three roles

The roles differ along **three independent axes** plus a **data-sensitivity
floor** — not along a single ladder:

- **Administration** — who runs the *system and the people*: user accounts, roles,
  tenants, memberships.
- **Operation** — who runs *devices and sites*: add/integrate, edit, enrol,
  commands, suspend/resume/retire.
- **Scope** — *whose* devices a person can touch: the whole fleet, or only the
  sites they are granted.
- **Floor** — a set of things **nobody below Admin may ever do or see** (§3.4).

### 3.1 What each role is

- **Admin** — the system owner. Full **administration** (users, roles, tenants,
  memberships) **and** full operation, across **all** devices and sites. This is
  the smallest set of accounts; in the pilot it is the project owner.
- **Technician** — an **operator**, scoped. Adds, integrates and operates devices
  and sites **within the sites they are granted**, but cannot manage users, roles
  or tenants, and cannot reach beyond their scope. At this stage the Technicians
  are the **Dealdio and Getfudo test engineers**.
- **Guest** — a **reviewer/observer**, scoped. Sees the Dashboard and the AI. At
  this stage a Guest may be granted **operation** (§3.3) but is **never** an
  administrator and **never** sees secrets.

In one line each:

> **Admin** runs the system *and the people*. **Technician** runs *devices,
> scoped*. **Guest** *observes* (or, in development, *operates scoped devices*),
> but never administers and never sees secrets.

### 3.2 Capability matrix

| Capability | Admin | Technician | Guest (prod) | Guest (dev) |
|---|---|---|---|---|
| Dashboard + AI | ✓ | ✓ | ✓ | ✓ |
| View devices & sites | ✓ all | ✓ scoped | ✓ scoped | ✓ scoped |
| Add / integrate / edit devices & sites | ✓ | ✓ scoped | ✗ | ✓ scoped |
| Device commands, monitor, suspend/resume/retire | ✓ | ✓ scoped | ✗ | ✓ scoped |
| Delete / purge (irreversible) | ✓ | see §12 | ✗ | ✗ |
| View device credentials / tokens / bootstrap keys | ✓ | ✓ | ✗ | ✗ **floor** |
| Jobs & push notifications | ✓ | ✓ | ✗ | ✓ scoped |
| **Manage users & assign roles** | ✓ | ✗ | ✗ | ✗ **floor** |
| **Manage tenants & memberships** | ✓ | ✗ | ✗ | ✗ **floor** |

The **floor** (bold) does not move with the stage: **no role below Admin ever
gains administration or device secrets.**

### 3.3 The stage model

The Guest role is **stage-aware**, so it tightens automatically when real devices
arrive without a code change or a rewrite:

| Stage | Devices | Guest capability |
|---|---|---|
| **dev** | demo/test devices (today) | **operate**, scoped (like a Technician) |
| **prod** | real customer devices | **view-only**, redacted (§7.2) |

A single, explicitly named switch selects the stage (for example
`HOMEPOT_ACCESS_STAGE=dev|prod`), rather than the blunt
`HOMEPOT_DEV_UNIFIED_ACCESS` — see §7.1 for why that switch is the wrong tool for
this.

### 3.4 The floor

At **every** stage, a Guest (and in fact any non-Admin) must not be able to:

- create, delete or re-role users; manage tenants or memberships;
- read device credentials, tokens, or provisioning/bootstrap keys;
- perform fleet-wide irreversible operations.

This floor is the difference that makes "Guest" meaningful even when it can
operate devices: a Guest is *an operator without any administrative reach and
without secrets*, not *a Technician with a different label*.

### 3.5 Partners are scope, not a role

Dealdio's engineers and Getfudo's engineers are **both `Technician`**. They are
separated by **tenant/site membership**, not by different roles. This keeps the
role enum small and makes the access model match the real multi-tenant one:
**role = what you may do; membership = which sites you may do it to.**

---

## 4. What already exists

The current state matters because the login page *looks* like it already offers a
choice, and it does not.

- **Only two roles exist:** `Admin` and `Technician`
  (`backend/src/homepot/app/roles.py:22-25`). Every legacy name — `client`,
  `user`, `engineer`, **`viewer`**, `member` — normalises to `Technician`
  (`roles.py:30-41`). There is no way to express "Guest" today.
- **The `Engineer` / `Client` tabs on the login page are cosmetic.** Both call
  the same `POST /auth/login` endpoint. The only difference is a client-side check
  that the `Engineer` tab requires `is_admin` (`frontend/src/pages/Login.jsx:54-72`,
  `frontend/src/components/Auth/RoleTabs.jsx:3-17`).
- **Privilege is a boolean, not a role.** `User.is_admin` is the real switch
  (`backend/src/homepot/models.py:272`); `User.role` is free text. In the default
  configuration `HOMEPOT_DEV_UNIFIED_ACCESS` is **on**, which makes every role
  admin-equivalent (`backend/src/homepot/app/roles.py:51-79`).
- **Site/tenant scoping exists but is unused in practice.** `get_accessible_site_ids`
  (`backend/src/homepot/app/auth_utils.py:683-730`) scopes list queries, but it
  needs a membership row and is bypassed entirely in unified mode (§6).
- **Backend enforcement is coarse.** Most endpoints require only *any*
  authenticated user; device **read** is allowed at viewer level and device
  **write** at operator level (`DevicesEndpoints.py`, e.g. list `:319-348`,
  detail `:404-486`, update `:610-633`, delete `:685-725`).
- **The frontend has effectively no role gating.** `ProtectedRoute` checks only
  `isAuthenticated` (`frontend/src/routes/ProtectedRoute.jsx:5-26`); the sidebar
  always renders Sites, Devices, "Add Site" and "Register Device"
  (`frontend/src/layouts/Sidebar.jsx:34-43`).
- There is **no guest, reviewer or read-only role** anywhere in the codebase.

---

## 5. The core conflict: the Dashboard renders from the device list

The single most important finding for the *read-only* case: **the current
Dashboard cannot render without the device-management endpoint.**

`frontend/src/pages/Dashboard.jsx` makes five read calls (plus one AI call on
submit):

| # | Caller | Endpoint |
|---|---|---|
| 1 | `Dashboard.jsx:40` (polled 1s) | `GET /health/system-pulse` |
| 2 | `Dashboard.jsx:70` | `GET /dashboard/summary` |
| 3 | `Dashboard.jsx:78` | `GET /sites/` |
| 4 | `Dashboard.jsx:84` | `GET /devices/device` ← device management list |
| 5 | `Dashboard.jsx:94` (polled 30s) | `GET /ai/anomalies` |
| 6 | `AskAIWidget.jsx:340` (on submit) | `POST /ai/query` |

Call 4 is the same endpoint that powers the Devices management page, and its
response includes `ip_address` and `credential_status`
(`DevicesEndpoints.py:356-393`). The Dashboard discards those fields for display,
but a reviewer reading the raw response — or prompting the AI — is not limited to
what the UI renders.

**Consequence:** the *prod* (read-only) Guest cannot be implemented by hiding UI
alone. It needs a redacted projection of the dashboard data, and the management
list must be denied. In *dev* (operate) mode these calls are permitted, but the
**floor** (§3.4) still applies.

---

## 6. Current data-scope gaps

Three of the Dashboard's read endpoints are **not scoped to the caller's tenant or
sites**, and two health endpoints have **no authentication at all**. These are
pre-existing and affect more than the Guest role, but the Guest role cannot be
safe without addressing them.

| Endpoint | Scope today | Evidence |
|---|---|---|
| `GET /dashboard/summary` | **Global** — counts across all tenants | `DashboardEndpoint.py:22-34`; query has no tenant/site predicate `database.py:1488-1609` |
| `GET /ai/anomalies` | **Global** — all tenants' devices/alerts | `AIEndpoint.py:188-379` (`:198-209` loads all active devices/alerts) |
| `POST /ai/query` | **Global** — LLM grounded on every tenant's device names, IDs, IPs, site names/locations, alerts | `AIEndpoint.py:436-...` (`:491-540`) |
| `GET /devices/device` | Scoped via `get_accessible_site_ids` | `DevicesEndpoints.py:344`; `auth_utils.py:683-730` |
| `GET /sites/` | Scoped via `get_accessible_site_ids` | `SitesEndpoint.py:213` |
| `GET /sites/{id}/dashboard` | Scoped via `verify_site_access_for_user` | `DashboardEndpoint.py:62` |
| `GET /health/system-pulse` | **No auth, no scope** | `HealthEndpoint.py:189-190` |
| `GET /health/sites/{id}/health` | **No auth, no scope** — returns per-device name, id, type, status, IP for any site id | `HealthEndpoint.py:348-351`, `:397-411` |

Two further facts make scoping unreliable:

- `get_accessible_site_ids()` returns `None` (= all sites) for admins, and a
  non-admin without a `TenantMembership`/`SiteMembership` row gets an empty set
  (`auth_utils.py:683-730`). Signup assigns a `tenant_id` but **no membership**,
  so tenant scoping depends on data that is often absent.
- In unified development mode every account is issued `is_admin=True`
  (`UserRegisterEndpoint.py:98,163`; `roles.py:70-79`), which makes
  `get_accessible_site_ids()` return **all** sites for everyone. **Tenant scoping
  is effectively disabled until `HOMEPOT_DEV_UNIFIED_ACCESS=false`.**

---

## 7. Proposed design

### 7.1 Role model and capability config

- Add a canonical role **`Guest`** to `roles.py:22-25`, outside the privileged
  set. `is_privileged("Guest")` must be `False` at every stage.
- Add `guest` / `reviewer` aliases mapping to `Guest`. **Do not** repurpose the
  existing `viewer` alias — it currently maps to `Technician` and silently
  reassigning it would change behaviour for existing rows.
- Sort out scope: prove **role = capability, membership = scope**, and make
  scoping real (create memberships; turn unified access off — §9).
- **Replace reliance on `HOMEPOT_DEV_UNIFIED_ACCESS`** with a small capability
  matrix keyed by stage. The unified switch grants *everything, including
  administration*, to every account — the wrong granularity for guest (we want
  *operation without administration*). See §3.3.
- Provisioning must understand the role: `scripts/add-user.sh` (validates against
  `LEGACY_ROLE_ALIASES`, `:165-173`) and `scripts/seed-users.sh` (`:261-272`)
  must accept `Guest` and must **not** collapse it to `Technician`.

### 7.2 Guest redaction and floor

In **prod**, a Guest sees device **names, status, health and alerts**, and **AI
recommendations**; it does **not** see **IP addresses, credentials, tokens, or
provisioning keys**, and cannot mutate anything. In **dev**, the same secrets and
administration remain hidden, but device/site operation is allowed.

| Data | Guest (prod) | Guest (dev) |
|---|---|---|
| Aggregate counts, device name, status, health | Visible | Visible |
| Active alerts (title/severity/message) | Visible | Visible |
| AI query / recommendations | Visible, scoped + redacted (§7.5) | Visible, scoped + redacted |
| Device IP address | Hidden | Hidden |
| Device credentials / tokens / bootstrap keys | **Hidden (floor)** | **Hidden (floor)** |
| Create / edit / commands / suspend / resume / retire | Blocked | Allowed, scoped |
| Users, roles, tenants, memberships | Blocked (floor) | Blocked (floor) |

### 7.3 Backend enforcement

Enforcement must be server-side; the UI is not a control.

- Introduce a **capability gate** so every device/site/user endpoint declares the
  capability it needs, and Guest/prod fails with `403`. This is stronger than the
  current operator-level site check (`DevicesEndpoints.py:156-163`, `:633`,
  `:725`; `SitesEndpoint.py:414`, `:726`, `:795`), which a Guest holding a site
  membership would otherwise pass.
- In **prod**, the Guest allowlist is:

  ```
  GET  /auth/me
  POST /auth/logout
  GET  /dashboard/summary      (tenant-scoped + redacted)
  GET  /health/system-pulse
  GET  /ai/anomalies           (tenant-scoped + redacted)
  POST /ai/query               (tenant-scoped + redacted)
  GET  /dashboard/guest        (new; see §7.4)
  ```

- In **dev**, a Guest additionally gets the scoped operational device/site
  endpoints — **never** `/auth/users/*`, `/tenants/*`, credentials/token endpoints,
  bootstrap keys, or `/client/*`.

### 7.4 Redacted dashboard projection

For the read-only (prod) case, add a **redacted projection** the Dashboard can
consume — e.g. `GET /dashboard/guest` returning, per visible device, only `name`,
status, health and alert summary, with **no** `ip_address`, `credential_status` or
credential fields. The Dashboard selects this instead of `GET /devices/device`
(`Dashboard.jsx:84`) when the caller is a read-only Guest.

### 7.5 AI scoping and redaction

`POST /ai/query` and `GET /ai/anomalies` must be **tenant-scoped** and their
**context redacted** (no IPs or credentials) before grounding the model — in both
stages. Without this, a Guest can prompt the assistant into a cross-tenant
device/IP dump (`AIEndpoint.py:491-540`).

### 7.6 Frontend gating

- Make `ProtectedRoute` role-aware (`frontend/src/routes/ProtectedRoute.jsx:5-26`)
  and redirect read-only Guests away from `/device*`, `/sites*`, `/useractivity`,
  `/agents`. In dev, allow device/site pages but hide administrative and secret UI.
- Hide "Add Site"/"Register Device" and administrative links when not permitted
  (`frontend/src/layouts/Sidebar.jsx:34-43`).
- Add role helpers on `AuthContext` (e.g. `role`, `isGuest`, `canManage`,
  `canAdminister`) and stop the display logic rewriting a Guest to `Admin`
  (`AuthContext.jsx:31-35, 87-93`).

### 7.7 Login entry and provisioning

- Add a clearly labelled **Guest / Reviewer** login entry rather than overloading
  the `Client` tab (which today means "non-admin customer/operator").
- Ensure `POST /auth/signup` cannot create a Guest (or any role) anonymously
  (`rbac-hardening-plan.md:142-158`). Guest accounts are created by an Admin.

---

## 8. Technician scope during development

**The question:** the Technicians are Dealdio/Getfudo test engineers; if an Admin
grants them access only to *their own sites*, does that limit their testing?

**Answer: it limits *visibility of other partners' devices*, not their ability to
do their job.** Their core task — add a device, integrate it, operate it — happens
on *their* sites and is unaffected. In fact, starting scoped is the right call,
because:

- It **exercises the real isolation model now**, so you find scoping bugs before
  real devices arrive, rather than after.
- Partners generally **should not see each other's fleet** even in development.
  Giving Dealdio access to Getfudo's devices would be the wrong default.

Where scoping genuinely gets in the way, the fix is **not** to widen the
`Technician` role. It is one of:

1. **Give the specific person a broader grant** (membership to more sites, or an
   Admin account) if they need fleet-wide end-to-end testing.
2. **Use a temporary dev-only scope switch** (like the Guest stage model) so that
   during development named accounts can see all sites, and it flips off with the
   stage.

**Prerequisites to make this real:** membership must actually be provisioned
(signup creates a `tenant_id` but **no membership** — `auth_utils.py:704-713`), and
`HOMEPOT_DEV_UNIFIED_ACCESS` must be off, or "scoped to their sites" is a no-op
today (§6).

**Net:** scoping does not block the technicians' testing; and if it ever does, the
correct answer is a scope grant or an Admin account for that person — not a change
to the role itself.

---

## 9. Non-negotiable prerequisites

These are already-known gaps that the role model makes more important. They must
land first, or the roles are decorative:

1. **Replace `HOMEPOT_DEV_UNIFIED_ACCESS` with a stage-aware capability config,
   and set the stage to `prod` for real deployments.** Otherwise every account —
   Guest included — is admin-equivalent and scoping is bypassed (`roles.py:70-79`;
   `auth_utils.py:692-693`).
2. **Make membership real.** Provision `TenantMembership`/`SiteMembership` rows so
   "scoped to their sites" actually means something (`auth_utils.py:683-730`).
3. **Enforce `is_active` at login and authorization** — it is never checked today
   (`models.py:271`; `rbac-hardening-plan.md:139-140`).
4. **Close anonymous signup / privilege-granting** (`rbac-hardening-plan.md:142-158`).
5. **Scope and/or redact the globally-scoped read endpoints** in §6.
6. **Fix the unauthenticated per-site health endpoint** in §6 (independent of
   roles).

---

## 10. Phased plan

| # | Scope | Why here |
|---|---|---|
| **0** | Prerequisites in §9: capability config; real memberships; enforce `is_active`; close anonymous signup; fix the unauthenticated health endpoint | The roles are meaningless without these |
| **1** | Add the `Guest` role and the capability gate; make provisioning scripts accept it | Establishes the role and blocks administrative/secret surfaces |
| **2** | Tenant-scope `/dashboard/summary` and both `/ai/*`; add the redacted projection | Enables the read-only (prod) Guest without the management list or cross-tenant data |
| **3** | Frontend gating: role-aware routes, sidebar, stage-aware Dashboard | Completes the experience |
| **4** | Guest login entry; scope the Technicians; docs; verification | Ships it to reviewers and partners |

Phases 0–2 are backend and security-sensitive; they warrant real test coverage
before reviewer or partner accounts exist.

---

## 11. Definition of done

- [ ] `Guest` is a canonical role; `is_privileged("Guest")` is always false
- [ ] A stage switch (`dev`/`prod`) drives Guest capability; no reliance on
      `HOMEPOT_DEV_UNIFIED_ACCESS`
- [ ] An Admin can create a Guest and scope a Technician; signup can do neither
- [ ] Deactivated accounts cannot authenticate
- [ ] A Guest receives `403` on every administrative and secret endpoint, verified
      by test
- [ ] In **prod**, the Dashboard renders for a Guest from a redacted projection
      with **no** IPs, credentials or management identifiers
- [ ] In **dev**, a Guest can operate only the devices within its scope
- [ ] `/ai/query` and `/ai/anomalies` are tenant-scoped and credential-free in both
      stages
- [ ] Technicians are confined to their granted sites (membership enforced)
- [ ] No simulation/emulation data is written to the production database
- [ ] A test fails if a new endpoint is added without declaring its capability

---

## 12. Open questions for review

These change the shape of the work; settle them before Phase 1.

1. **Dev-stage Guest operation.** Confirm reviewers should operate devices now
   (demo devices) and flip to read-only later — and that this is a stage switch,
   not a permanent widening of the role.
2. **Irreversible operations.** Should `Technician` retain delete/purge, or should
   irreversible fleet operations be **Admin-only**? (Currently operator-level.)
3. **Redaction level.** In prod, do reviewers see device **names**, or should
   identities be anonymised (`Device A`, `Device B`)? Meaningful AI feedback
   probably needs names.
4. **Cross-tenant visibility for reviewers.** Do reviewers belong to one tenant
   (e.g. the project owner's), or should aggregate data span partners? Today the
   summary and AI endpoints are global.
5. **Reviewer/partner account lifecycle.** Who owns the accounts, how many, and
   how are they revoked? Note tokens are long-lived and there is no revocation
   (`rbac-hardening-plan.md:177-186`).

---

## 13. Note on disclosure

This repository is **public** and the dashboard is **live and internet-facing**.
Section 6 names endpoints that are currently unscoped or unauthenticated against a
running system. As with `docs/rbac-hardening-plan.md`, this document carries the
architecture, the gaps and the plan; **step-by-step exploit detail is deliberately
omitted** and should be tracked privately rather than in issues or chat. Section 6
should be reviewed, and redacted where necessary, before this document is merged.
