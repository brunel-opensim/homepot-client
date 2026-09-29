# Role-Based Access Control — Readiness Review and Hardening Plan

**Status:** Draft for team review
**Scope:** readiness of the centralized dashboard for multiple concurrent technicians
**Reviewed:** 2026-09-29

---

## 1. Why this document

We are standing up a **single HOMEPOT dashboard** as the central entry point for
field technicians, reachable over HTTPS. That changes the threat model in one
specific way: it is no longer a single-operator tool on a single operator's
machine. Several technicians will hold valid sessions at the same time, and
technicians change — they join, they move between sites, and they leave.

Two questions follow, and this document answers both:

1. **Concurrency** — can the system serve several technicians at once?
2. **Access control** — can it correctly say what each of them may do?

Short answer: **concurrency is largely fine; access control is not ready.**

---

## 2. What was examined

- The authentication stack: login, token issuance, refresh, logout, SSO
- The user model and every role vocabulary in use
- The authorization helpers and which endpoints actually use them
- A route-by-route inventory of auth dependencies
- The audit trail and what it records
- Database concurrency, pooling, and the real-time transport

Evidence is cited as `file:line` throughout so each claim can be checked
directly.

---

## 3. Verdict at a glance

| Area | State | Blocking? |
|---|---|---|
| Database / concurrency | Sound | No |
| Session isolation | No per-connection state to conflict | No |
| Connection pool ceiling | ~15 concurrent; adequate for a small team | Watch |
| Concurrent edit safety | None — silent last-write-wins | Watch |
| Role model | Four conflicting vocabularies; privilege is a boolean | **Yes** |
| Role enforcement | Main admin gate trusts a stale token claim | **Yes** |
| Account creation | Can grant administrative privilege | **Yes — highest severity** |
| Auth coverage | Inconsistent across endpoints | **Yes** |
| Session revocation | None; tokens valid ~10 years | **Yes** |
| Audit / accountability | Records *what*, rarely *who* | Yes |

---

## 4. What already exists — keep and build on this

The foundation is better than a rewrite would suggest:

- **Site and tenant membership** with a role hierarchy of
  `admin > operator > installer > viewer` (`backend/src/homepot/app/auth_utils.py:580-585`).
- **`require_site_access(site_id, min_role)`** and **`require_tenant_role()`**,
  both of which read from the database.
- **`get_accessible_site_ids()`**, which correctly scopes list queries to what a
  given user may see.
- **Device permission tiers** (`root_access` = Manage, monitoring keys = Monitor)
  in `backend/src/homepot/app/permissions.py:31-55`. This is a separate,
  device-owned consent system and is orthogonal to operator roles. It is the
  strongest part of the authorization story and should not be disturbed by the
  work below.
- **Correctly protected surfaces:** the sites, devices, jobs, agent, and
  device-command routers, and the AI/analytics/KPI routers, all carry
  dependencies. The device plane authenticates every request with a device
  identity and enforces ownership.

---

## 5. Gaps

### 5.1 Privilege is a boolean, not a role

`User.is_admin` is the real privilege switch. `User.role` is free text and is
decorative. Worse, **four** role vocabularies coexist:

| Source | Values |
|---|---|
| `User.role` (free text) | whatever was supplied at signup: `Client`, `Engineer`, `Admin`, … |
| `TokenData.role` | only `Admin` or `User`, derived from `is_admin`, never from the DB |
| `TenantMembership.role` | `admin, operator, installer, member` |
| `SiteMembership.role` | `admin, operator, installer, viewer` |

Two problems follow. `member` and `Client` score **0** in the hierarchy, i.e.
*below* `viewer` — so a tenant member ranks lower than a site viewer. And the
hierarchy is duplicated in two places, which will drift.

**Fix:** one enum, one hierarchy, one source of truth (the database).

### 5.2 The main admin gate trusts a stale token

`require_role()` compares against the role derived from the JWT claim and never
queries the database. The result: **demoting a user does not take effect** until
their token expires — and tokens are long-lived (§5.6). A demoted user stays an
admin.

The fix is small, because the correct helper already exists: `require_user()`
does re-read the database. `require_role()` should delegate to it.

Related: `is_active` exists on the user model but is **never checked** at login
or during authorization, so a deactivated account still authenticates.

### 5.3 Account creation can grant administrative privilege — highest severity

`POST /api/v1/auth/signup` has **no authentication dependency**, and it derives
the administrative flag from a role value supplied in the request body
(`backend/src/homepot/app/api/API_v1/Endpoints/UserRegisterEndpoint.py:65-67`
and the `is_admin` derivation at line 91). The public sign-up page is wired to
request exactly that role.

**Anyone who can reach the dashboard can create an administrative account.**

This blocks the rest of the programme: role-based access control is not a
meaningful control while a caller can simply mint the highest role. Exact
request detail is deliberately kept out of this public document — see §10.

### 5.4 Auth coverage is inconsistent

A route inventory found a substantial number of endpoints carrying no auth
dependency. Some are intentionally open (device bootstrap, health probes); others
are operational endpoints that should not be, including parts of the
notification/publish plane, device telemetry ingestion, and device inventory
listings. Telemetry ingestion in particular allows fleet health data to be
altered by an unauthenticated caller.

There is also **no test that fails when a new endpoint ships without an auth
dependency** — which is how the drift accumulated.

Note on scope: a second, older application entrypoint in this repository carries
a larger set of unprotected routes. The deployed service does **not** run that
entrypoint, so those are not currently exposed. Worth removing or isolating so a
future deployment cannot pick it up by accident.

### 5.5 No session revocation

- Tokens are issued with a ~10-year lifetime. The source comment describes this
  as deliberate (`backend/src/homepot/app/auth_utils.py:52-53`).
- Logout deletes cookies only. There is **no revocation mechanism of any kind**:
  no token identifier, no denylist, no token-version column.
- Deleting a user does not terminate their sessions.

For a workforce that changes, this means: **you cannot reliably remove someone's
access.** A departing technician's token keeps working for years.

### 5.6 Accountability is mostly missing

An audit log exists with an appropriate schema, but:

- The actor is recorded in only a small minority of call sites. Site, device,
  tenant and job events record *what* changed with no *who*.
- Authentication events are declared but never emitted — **logins, failed
  logins, signups and logouts are not recorded at all.**
- Administrative actions (role changes, user deletion) are untracked.
- Denied access attempts leave no trace.
- The audit read endpoints are themselves unauthenticated.

So after an incident you could not determine which technician did what — which
is precisely the question a shared multi-technician dashboard exists to answer.

---

## 6. Concurrency and multi-user readiness

Separate from access control, and largely in good shape:

- **Database.** PostgreSQL, with a session per request and `pool_pre_ping`
  enabled so the application survives database restarts.
- **Pool ceiling.** `pool_size=5`, `max_overflow=10` — roughly 15 concurrent
  connections (`backend/src/homepot/config.py:21-22`,
  `backend/src/homepot/database.py:1629`). Adequate for a small technician
  team. Raise deliberately if headcount grows.
- **No shared per-connection state.** There are no WebSocket endpoints in the
  deployed application, so there is no per-browser state that could interfere
  between technicians.
- **No optimistic locking.** If two technicians edit the same site or device,
  the second write silently overwrites the first. There is no version column, no
  conflict detection, and no "someone else changed this" prompt. Worth adding
  before concurrent editing becomes routine.

### 6.1 Real-time updates: aspirational, not active

There is exactly one WebSocket endpoint in the repository, intended to push job
status and site health to the dashboard. It is **not part of the deployed
application**, no frontend code connects to it, and its configuration settings
are never read.

If it is enabled later, note two design problems: it re-queries the database once
per connected browser every five seconds (so N browsers means N times the
database load, against a small pool), and it accepts connections without
authenticating them. The right shape is a single broadcaster fanning out to
subscribers, with the existing session token verified at connect time.

The dashboard's current real-time behaviour is ordinary HTTP polling, plus MQTT
for device-originated push. That is fine.

---

## 7. Definition of done

Role-based access control can be called real when all of the following hold:

- [ ] One role enum, one hierarchy, one source of truth (the database)
- [ ] Every mutating endpoint declares the minimum role it requires
- [ ] A role change or account deactivation takes effect immediately
- [ ] No code path allows a caller to grant themselves a role
- [ ] Sessions can be revoked server-side; token lifetime is sane
- [ ] Deactivated accounts cannot authenticate
- [ ] Every privileged action records its actor
- [ ] Authentication events are recorded
- [ ] A test fails when an endpoint is added without an auth dependency

---

## 8. Sequenced plan

The order matters: the first item is what makes the rest safe to build and test.

| # | Scope | Why here |
|---|---|---|
| **1** | Close open administrative signup; add authentication to the unprotected operational endpoints; disable agent simulation in production; enforce secure cookies; resolve the split secret-key configuration | Nothing else is safe to test until this lands. **Highest severity.** |
| **2** | Make `require_role()` consult the database; check `is_active` at login; repair the role-update path so the stored role and the admin flag agree; add session revocation and a sane token lifetime | Turns "admin or not" into real enforcement |
| **3** | Unify the four role vocabularies into one enum and hierarchy and migrate existing rows; record the actor on privileged actions; emit authentication events; protect audit reads | Makes the model coherent and accountable |
| **4** | *Optional:* optimistic locking for concurrent edits, pool sizing for larger teams, an authenticated real-time broadcaster if live updates are wanted | Only matters once technicians actually collide |

Item 1 is independent of items 2–4 and also protects the deployment that is
already live. Items 2 and 3 can follow once item 1 is merged.

**Sizing is deliberately not estimated here.** Item 2 touches login and
authorization, which warrants genuine test coverage rather than a fast patch. A
reasonable estimate needs input on how much regression testing the authentication
paths should carry.

---

## 9. Open questions for review

These change the shape of the work and should be settled before item 2 starts.

1. **Who are the users?** All technicians equivalent operators, or does access
   differ by site, region, or role?
2. **Is the dashboard internet-facing or behind VPN / IP allow-listing?** This
   changes the urgency of item 1 substantially. It is currently reachable over
   public HTTPS.
3. **Sign-up policy:** open self-service, invite-only, or bootstrap-first-admin
   with no public registration? For an internal operational tool, invite-only is
   usually the right answer.
4. **Do we need tenant isolation now,** or is a single organisation with
   site-scoped roles sufficient? The membership models already exist, so this is
   a configuration decision more than a build.
5. **Is a real-time dashboard actually required?** If not, item 4's broadcaster
   can be dropped.

---

## 10. Note on disclosure

This repository is **public** and the dashboard is **live and internet-facing**.
Findings in §5.3, §5.4 and §5.5 describe unauthenticated or
privilege-escalation-capable paths against a running system. Publishing exact
request shapes would amount to publishing working attack instructions.

Accordingly:

- This document carries the architecture, the gaps, and the plan.
- **Endpoint-level exploit detail is tracked in a private GitHub security
  advisory**, not in this repository, and is not reproduced in comments, issues
  or chat.
- Findings already posted publicly should be reviewed and redacted where they
  name specific unprotected endpoints on the live host.

Nobody outside the team needs the detail in order to act on this plan.
