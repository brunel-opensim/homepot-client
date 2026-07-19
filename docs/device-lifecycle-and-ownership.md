# Canonical Device Lifecycle and Ownership

## Purpose

This document defines the canonical device lifecycle and ownership contract for the HOMEPOT Dashboard/backend and HOMEPOT User App. It is the reference for API, database, user-interface, agent, simulation, and real-device development.

The contract separates four concepts that must not be represented by one overloaded status:

- **Identity:** which physical or virtual endpoint a record represents.
- **Ownership and assignment:** which HOMEPOT scope may manage it.
- **Lifecycle:** whether it is awaiting enrolment, managed, suspended, unpaired, or retired.
- **Connectivity:** whether the backend has heard from it recently.

This document defines the target contract. The implementation baseline distinguishes current behaviour from functionality that remains to be developed.

## Canonical terms

| Term            | Meaning                                                                                                                                                  |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Device          | A durable backend record representing one managed endpoint.                                                                                              |
| Device identity | A stable, non-secret identifier bound to the endpoint. A display name, address, push token, or API key is not device identity.                           |
| Site            | The operational scope to which a device is assigned.                                                                                                     |
| Principal       | An authenticated human user, service, or device identity.                                                                                                |
| Owner           | The tenant or organisation responsible for a site and its devices. Tenant ownership is a target capability and is not represented in the current schema. |
| Assignment      | The relationship between a device and a site. Assignment alone is not proof of authorisation.                                                            |
| Enrolment       | Establishing an authorised assignment and issuing device credentials.                                                                                    |
| Pairing         | The active management relationship created by successful enrolment.                                                                                      |
| Unpairing       | Revoking that relationship while retaining historical records.                                                                                           |
| Retirement      | A terminal administrative decision that prevents ordinary reactivation.                                                                                  |
| Lifecycle epoch | One enrolment-to-unpair-or-retire period. A new epoch requires new credentials and an auditable transition.                                              |

## Source of truth

The backend is authoritative for:

- device identity;
- ownership and site assignment;
- lifecycle state;
- credential issuance and revocation;
- authorisation decisions; and
- audit history.

The Dashboard and User App consume and request changes to that state. They must not independently declare a backend lifecycle transition successful.

| Component            | Responsibilities                                                                                                        | Must not be authoritative for                                                         |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Dashboard            | Create enrolment intents and pre-provisioned records, display state, and request authorised administrative transitions. | Ownership or device state inferred only from browser state.                           |
| Backend              | Authenticate principals, authorise scope, enforce transitions, issue and revoke credentials, and record audit events.   | Device-local facts not reported by an authenticated agent.                            |
| User App/agent       | Bootstrap enrolment, retain credentials securely, report device DNA, heartbeat and telemetry, and request unpairing.    | Ownership, assignment, or successful lifecycle transitions based only on local state. |
| Push provider or MDM | Deliver wake-up or management signals and report provider delivery status.                                              | HOMEPOT ownership, command completion, or lifecycle state.                            |

Removing credentials from a device does not prove that the backend revoked them. If the backend cannot confirm unpairing, the User App may perform a local safety reset but must report it as **local reset; server revocation pending**.

## Ownership model

The target ownership hierarchy is:

```text
Tenant / organisation
└── Site
    └── Device assignment
        └── Lifecycle epochs and retained operational history
```

### Ownership invariants

1. Every active device assignment belongs to exactly one active site and one tenant or organisation.
2. Human access is granted through tenant and site roles. Knowing a `site_id` or `device_id` does not grant access.
3. A device credential grants access only as that device.
4. A device cannot use its credentials to claim another device, change ownership, change site, or administer users.
5. A device cannot have two active assignments.
6. Transfer must be explicit, authorised, audited, and accompanied by credential rotation.
7. Provider identifiers, network addresses and observed hardware attributes are aliases or metadata, not ownership.
8. Historical telemetry and audit events retain the ownership scope and lifecycle epoch in which they were produced.
9. Secrets are returned only when issued or rotated and are stored server-side only as hashes or verifiers.
10. Enrolment tokens must be one-time, scoped, expiring, and consumed atomically.

## Canonical roles

Exact role names may evolve, but authorisation must support these capabilities:

| Principal              | Minimum permitted scope                                                                 |
| ---------------------- | --------------------------------------------------------------------------------------- |
| Platform administrator | Manage tenants and perform explicitly audited support operations.                       |
| Tenant administrator   | Manage sites, enrolment, assignments, commands and retirement within one tenant.        |
| Site operator          | View and operate authorised sites. Destructive transitions require explicit permission. |
| End user or installer  | Redeem an enrolment intent or request self-enrolment for an authorised site.            |
| Device                 | Report and retrieve data only for its own active identity.                              |

## Canonical lifecycle

Lifecycle, connectivity and health are independent dimensions.

### Lifecycle states

| State       | Meaning                                                                                    | Credentials                                                           | Device operations                         |
| ----------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- | ----------------------------------------- |
| `pending`   | An enrolment intent or pre-provisioned slot exists, but no endpoint has proved possession. | None                                                                  | Rejected                                  |
| `active`    | Enrolment is complete and the management relationship is valid.                            | Valid                                                                 | Allowed when authenticated and authorised |
| `suspended` | Management is temporarily disabled by an authorised operator or policy.                    | Retained or rotated according to policy, but rejected while suspended | Rejected                                  |
| `unpaired`  | The management relationship has ended, while records are retained for audit and analytics. | Revoked                                                               | Rejected                                  |
| `retired`   | Terminal state for that lifecycle epoch. Ordinary claim or reactivation is forbidden.      | Revoked                                                               | Rejected                                  |

`is_active` may remain as a compatibility field, but it must not form a second lifecycle model. Its mapping to canonical lifecycle states must be defined once and used consistently.

### Connectivity states

| State     | Meaning                                                                     |
| --------- | --------------------------------------------------------------------------- |
| `unknown` | No trustworthy heartbeat has been observed.                                 |
| `online`  | The most recent authenticated heartbeat is within the configured threshold. |
| `offline` | The device is active, but its heartbeat is absent or stale.                 |

Connectivity must be computed from authenticated heartbeat information.

`maintenance` and `error` are operational or health conditions. They are not connectivity, lifecycle, or ownership states.

An unpaired device is not merely offline: it no longer has an active management relationship.

## Allowed transitions

| From                                | Event                         | To                                     | Required authority and effects                                                                                                   |
| ----------------------------------- | ----------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `none`                              | Create pre-provisioned intent | `pending`                              | Tenant or site administrator; bind owner and site; issue one-time claim token.                                                   |
| `none`                              | Authorised self-enrolment     | `active`                               | Authenticated installer authorised for the target site; atomically create identity, assignment, lifecycle epoch and credentials. |
| `pending`                           | Claim                         | `active`                               | Verify and consume the token and device proof; issue credentials; audit actor and device.                                        |
| `active`                            | Suspend                       | `suspended`                            | Authorised operator or policy; reject device operations and record the reason.                                                   |
| `suspended`                         | Resume                        | `active`                               | Authorised operator or policy; rotate credentials if compromise is possible.                                                     |
| `active` or `suspended`             | Unpair                        | `unpaired`                             | Authorised user or device flow; revoke credentials and provider channels; retain history.                                        |
| `active`, `suspended` or `unpaired` | Retire                        | `retired`                              | Tenant administrator; revoke credentials and prevent ordinary reactivation.                                                      |
| `unpaired`                          | Re-enrol                      | `active` in a new epoch                | Repeat authorisation and device proof; retain the old epoch and issue new credentials.                                           |
| `active` or `suspended`             | Transfer                      | `active` in a new assignment and epoch | Authorised at source and destination; revoke old credentials and retain historical ownership.                                    |

Transitions must be idempotent or accept an idempotency key. Concurrent claim, unpair, transfer and credential-rotation operations must be transactionally serialised.

## Enrolment paths

### Pre-provisioned enrolment

1. An authorised administrator creates a pending device record or enrolment intent for a tenant and site.
2. The backend issues a short-lived, one-time claim token.
3. The claim token is separate from the eventual device API credential.
4. The User App or agent submits the claim token and stable device evidence.
5. The backend verifies scope, token validity and identity uniqueness.
6. The backend consumes the token atomically, starts the lifecycle epoch, and returns one-time credentials.
7. The device stores those credentials using platform-secure storage and registers its device DNA.

### Self-enrolment

1. The user authenticates.
2. The backend verifies that the user may enrol devices into the selected site.
3. The backend atomically creates the device, assignment and lifecycle epoch.
4. The backend returns one-time device credentials.
5. The agent stores the credentials securely and reports its device DNA.

A raw site ID and caller-provided `user_identity` are metadata, not proof of authorisation.

## Unpairing and local reset

Canonical unpairing is a backend lifecycle transition. It is not merely an HTTP `DELETE` convention or removal of browser storage.

The target API should provide an explicit operation such as:

```bash
POST /devices/{device_id}/unpair
```

The request must include authentication, authorisation, an optional reason, and an idempotency key.

### Successful unpairing requirements

1. verify that the caller may unpair the device in its current ownership scope;
2. mark the lifecycle epoch as unpaired and inactive;
3. revoke API credentials, bootstrap tokens, push channels and active sessions;
4. expire or cancel outstanding command leases;
5. reject subsequent heartbeat, telemetry, command polling and command-result writes;
6. retain the device record, assignment history, telemetry, outcomes and audit records;
7. record the actor, reason, previous state, new state, timestamp and correlation ID; and
8. return a structured result before the User App clears local credentials.

Hard deletion is a separate data-governance operation and is outside ordinary device unpairing.

## API representation

Device responses should expose the independent state dimensions:

```json
{
  "device_id": "device-stable-id",
  "tenant_id": "tenant-123",
  "site_id": "site-123",
  "lifecycle_state": "active",
  "connectivity_state": "online",
  "health_state": "healthy",
  "enrollment_method": "self-enrolled",
  "lifecycle_epoch_id": "epoch-456",
  "last_heartbeat_at": "2026-07-19T10:30:00Z"
}
```

### Transition events

Transition events should include:

- event ID and type;
- device and lifecycle epoch IDs;
- tenant and site scope;
- authenticated actor;
- source component;
- previous and new states;
- reason;
- correlation or idempotency key; and
- UTC timestamp.

Events must never include plaintext API keys, enrolment tokens, or provider secrets.

## Implementation baseline

At the time this document was introduced, the repository implements only part of the contract.

### Implemented

- Device has a globally unique `device_id`.
- Every device has a required site foreign key.
- The model includes `is_active`, `status`, `enrollment_method`, and a hashed API key.
- Provisioning creates a device, returns a one-time plaintext API key, and stores its hash.
- Device DNA, heartbeat, telemetry and pending-command reads authenticate using `X-Device-ID` and `X-API-Key`.
- Database unpairing sets `is_active` to `false`.
- Database unpairing sets `status` to `unpaired`.
- Database unpairing removes the API-key hash while retaining the site relationship.
- Database unpairing creates a `device_unpaired` audit row.
- Normal site listings exclude inactive devices and may optionally include unpaired records.

## Known gaps

- There is no tenant or organisation entity.
- There is no user-to-site membership or site-role model.
- There is no explicit device owner, assignment history, or lifecycle epoch.
- `status` mixes connectivity, lifecycle and health conditions.
- Provisioning accepts `site_id` and caller-provided `user_identity` without user authentication or site authorisation.
- General device administration and command queueing do not consistently require an authenticated, site-authorised user.
- A matching `device_id` is currently enough to enter the pre-provisioned claim path.
- Claim-token validation, expiry and atomic consumption are not enforced.
- Provisioning does not consistently persist self-enrolled or an explicit lifecycle state.
- The User App stores its API key in `sessionStorage`; real-device implementations require OS-protected storage.
- The User App stores a device ID under the misleading key `homepot_token`.
- The User App calls an unauthenticated `DELETE` operation during unpairing.
- It does not reject unsuccessful HTTP responses and clears local state after network failure.
- Unpairing does not yet revoke push-provider channels or expire outstanding commands and sessions.
- Re-enrolment, transfer, suspension, retirement and concurrency rules are not represented.
- Command-result ownership is checked after the update has been committed; ownership must be enforced before mutation.

## Canonical state model
PR 1: Separate lifecycle, connectivity, and health
**Backend:**
- Add explicit enums/fields:
  - lifecycle_state: pending, active, suspended, unpaired, retired
  - connectivity_state: computed as unknown, online, or offline
  - health_state: for conditions such as healthy, warning, error, maintenance
- Stop using the existing status field for all three dimensions.
- Define a temporary migration mapping from existing values.
- Centralise state transitions in a lifecycle service.
- Prevent arbitrary endpoint code from changing lifecycle state directly.
**Dashboard:**
- Display lifecycle, connectivity, and health separately.
- Exclude unpaired and retired devices from active fleet counts.
- Do not describe an unpaired device as merely offline.
**User App:**
- Read the backend lifecycle state rather than inferring it from local storage.
- Disable device operations when suspended, unpaired, or retired.
**Tests:**
- Database migration tests.
- Allowed and rejected transition tests.
- Dashboard/API representation tests.
This should be the first code PR because every later security and real-device flow depends on these meanings.

PR 2: Introduce tenant and site membership
**Backend:**
- Add Tenant or Organisation.
- Assign every site to one tenant.
- Add user-to-tenant/site membership and roles.
- Migrate existing sites into a default tenant.
- Define permissions for administrators, operators, installers, and devices.

PR 3: Enforce ownership at API boundaries
**Secure:**
- device creation and listing;
- device update and unpairing;
- provisioning;
- command creation;
- site statistics;
- telemetry and configuration access.
Knowing a Site ID must not be sufficient to enrol or administer a device.
**Important acceptance tests:**
- User from tenant A cannot view or modify tenant B.
- Site operator cannot act outside assigned sites.
- Device credentials only operate on that same device.
- Unauthenticated provisioning and unpairing are rejected.

PR 5: Implement pre-provisioned claiming
**Dashboard:**
- Administrator creates a pending device/enrolment intent.
- Display claim status and expiry.
- Allow token revocation and regeneration.
**User App:**
- Accept the claim token.
- Present stable device evidence.
- Securely receive and store credentials.
Backend:
- Validate token hash, scope, expiry, and unused state.
- Consume the token atomically.
- Create the lifecycle epoch.
- Issue the API key only once.
- Reject duplicate and concurrent claims.




