# Pilot Operator Protocol

## 1. Purpose

This document turns the [evaluation roadmap](kpi-evaluation-roadmap.md) Phase 0
outputs into a concrete, operator-facing protocol. It fixes the definitions,
units, owners, evidence bundle, reviewer rubric, and limitations that the
demonstrator operator and the evidence reviewer must follow during a formal UK
pilot run. Decisions recorded here are frozen before the pilot and are not
changed while results are being produced.

## 2. Roles and owners

| Role | Responsibility | Named owner |
| --- | --- | --- |
| UK use-case owner | Approves scope, thresholds, and exclusions | TBD (Phase 0) |
| Demonstrator operator | Executes scenarios, records interventions | TBD (Phase 0) |
| Data analyst | Runs exports and calculations | TBD (Phase 0) |
| Evidence reviewer | Independent second-person review and sign-off | TBD (Phase 0) |
| D2.3 author | Reports results with claim-maturity labels | TBD (Phase 0) |

Names are recorded in `manifest.json` (operator/reviewer identities) and in the
bundle's `protocol.md` before the run starts.

## 3. Phase 0 decisions to freeze

The following decisions are made and signed before any formal run. "TBD" values
are a deliberate gap, not a post-hoc choice.

| Decision | Value | Owner |
| --- | --- | --- |
| Requirement-to-scenario scope mapping and explicit exclusions | TBD | UK use-case owner |
| KPI acceptance thresholds (from roadmap §5) | TBD | UK use-case owner |
| Pilot duration and reporting window | TBD | UK use-case owner |
| Number and types of pilot devices | TBD | Demonstrator operator |
| Telemetry collection interval | TBD (real agent default 30 s) | Demonstrator operator |
| Reporting timezone | `UTC` (fixed) | Data analyst |
| Exclusions and their reasons | TBD (recorded before the run) | Data analyst |
| Scenario scripts and fault catalogue | Frozen | Demonstrator operator |
| Endpoint eligibility rules | Frozen | Data analyst |
| Reviewer rubric | Frozen | Evidence reviewer |

**Exit gate:** no KPI remains ambiguous about formula, population, window,
provenance, or acceptance rule (roadmap §7 Phase 0).

## 4. Operational protocol

### 4.1 Before each run

1. Confirm the frozen decisions in §3 are signed and unchanged.
2. Deploy versioned agent and demonstrator builds; record deployment versions
   in `environment.json`.
3. Seed only setup data, labelled `SIMULATED` (roadmap §3.1).
4. Verify clocks (device vs server), IDs, and expected sample counts.
5. Freeze the reporting window; record `start`/`end` in `manifest.json`.

### 4.2 During each run

1. Execute scenarios exactly as approved (UK-E01 to UK-E07, roadmap §6).
2. Record planned downtime and every operator intervention in the scenario log.
3. Monitor evidence quality (EQ-01 coverage) **without changing thresholds**.
4. Preserve raw logs and exports read-only at the end of each run.

### 4.3 After each run

1. Generate exports with the [KPI export](kpi-export.md) (API or
   `./scripts/kpi-export.sh`); do not transform results in spreadsheets.
2. Record exclusions and their reasons; never delete raw evidence.
3. Assemble the evidence bundle (§5) with the generated manifest.
4. Request the independent evidence review (§7) before reporting.

## 5. Evidence bundle

One immutable bundle is stored per formal run (roadmap §8):

```text
kpi-evidence/<run-id>/
├── kpi-export.json
├── manifest.json
├── protocol.md
├── environment.json
├── scenario-log.csv
├── raw/
├── calculations/
├── screenshots/
├── reviewer-signoff.md
└── limitations.md
```

| Item | Contents |
| --- | --- |
| `manifest.json` | Run ID, protocol version, Git commit, deployment versions, window, timezone, sites, devices, provenance, scenario IDs, file hashes, exclusions, operator/reviewer identities |
| `protocol.md` | The frozen §3 decisions and §4 procedure for this run |
| `environment.json` | Deployment versions, database snapshot identifier, device types/OS, network conditions |
| `scenario-log.csv` | Scenario ID, preconditions, operator, start/end, expected events, result, interventions |
| `raw/` | Raw evidence rows (metrics, state history, config history, commands) — read-only |
| `kpi-export.json` | Versioned KPI export bundle and its `kpi-summary.csv` companion from the KPI export |
| `calculations/` | Calculation code revision (Git commit) and generated manifests |
| `screenshots/` | Illustrative dashboard captures (do not replace machine-readable evidence) |
| `reviewer-signoff.md` | Second-person review outcome (§7) and audit log of discrepancies |
| `limitations.md` | Limitations, exclusions, and missing UK workflows (§8) |

## 6. Data-quality gates

An export is only accepted when its underlying evidence passes the gates:

| Gate | Rule | Status today |
| --- | --- | --- |
| EQ-01 | Provenance coverage = rows with valid provenance / eligible rows × 100 | **Computed in every export**; acceptance 100% |
| EQ-02 | Telemetry completeness | Defined; not yet computed; threshold TBD |
| EQ-03 | Telemetry freshness | Defined; not yet computed; threshold TBD |
| EQ-04 | Continuity | Defined; not yet computed; threshold TBD |
| EQ-05 | Valid record rate | Defined; not yet computed; threshold TBD |

No operational KPI receives a **Validated** label when its evidence fails the
EQ-01 to EQ-05 gates. See [KPI export](kpi-export.md) §9 for the gate
definition and current coverage.

## 7. Reviewer rubric

Apply the claim-maturity labels from roadmap §3.2 when deciding whether a claim
is reportable:

| Label | Minimum evidence |
| --- | --- |
| **Implemented** | Code path and automated tests exist |
| **Demonstrated** | Scenario completed with `CONTROLLED` evidence |
| **Pilot-observed** | Scenario or KPI observed on `REAL` devices, but the target sample or duration was not met |
| **Validated** | Pre-agreed threshold met using the required `REAL` sample, duration, and evidence-quality gates |
| **Not evaluated** | No adequate scenario, instrumentation, or evidence |

The reviewer:

1. regenerates every headline value from the export bundle and the manifest;
2. triples-checks numerator, denominator, exclusions, and sample counts;
3. triangulates results with the scenario log and operator observations;
4. resolves every discrepancy in the audit log and records it in
   `reviewer-signoff.md`.

## 8. Limitations template

Every report must state, at minimum:

- which KPIs rely on **REAL** evidence and which are **CONTROLLED** or
  **SIMULATED** rehearsal output;
- any threshold still marked **TBD** (i.e. not frozen in Phase 0);
- the evidence-quality gates that were **not** met and their effect on each
  affected KPI;
- excluded rows, their reasons, and any scenarios that could not be executed;
- provenance caveats (for example command KPIs whose provenance is derived at
  export time rather than snapshotted);
- command-permission coverage (command KPIs describe only the command types
  each device owner has granted — devices granting no permissions contribute no
  command evidence, and un-granted types such as `restart`/`shutdown`
  (`root_access`) or `update_config` (`filesystem_access`) are absent from
  MW-01/MW-02);
- whether any **REAL** and **CONTROLLED**/**SIMULATED** values were combined in
  a headline number (which is prohibited by roadmap §3.3).

## 9. Final exit gate

Every reported number must resolve to a manifest entry, raw evidence,
calculation version, and review decision. Only then is the bundle eligible for
the UK D2.3 section (roadmap §7 Phase 5).