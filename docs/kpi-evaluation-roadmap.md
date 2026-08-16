# UK HOMEPOT Use Case Evaluation Roadmap

## 1. Purpose

This document is the working roadmap for completing the evaluation of the UK HOMEPOT use case with the HOMEPOT Client Demonstrator. It converts architecture claims and available telemetry into a repeatable evaluation programme and an auditable evidence package for D2.3.

The roadmap is complete when every in-scope claim has:

1. a named requirement and scenario;
2. a defined KPI, formula, time window, population, and acceptance threshold;
3. evidence produced by the demonstrator with source provenance;
4. a reproducible calculation or export;
5. a recorded result, limitation, and pass/fail decision.

This is an evaluation roadmap, not a statement that the UK requirements have already been validated. Architecture support, simulated demonstrations, and observations from real pilot devices are different evidence levels and must be reported separately.

## 2. Evaluation Question and Scope

**Primary question:** To what extent does the HOMEPOT Client Demonstrator provide reliable monitoring, management, and AI-assisted diagnosis for the devices used in the UK food-and-restaurant use case?

The initial demonstrator evaluation covers:

- enrolment and identification of POS terminals, tablets, and kitchen displays;
- authenticated telemetry collection and device-health monitoring;
- detection and presentation of connectivity or health incidents;
- remote configuration or command execution and outcome tracking;
- dashboard visibility for site operators;
- evidence quality and the trust status of AI-assisted analysis.

The following architecture requirements remain part of the UK use case but must not be claimed as demonstrator-validated until an executable workflow and an authoritative data source exist:

- **UK-F3:** menu and order synchronisation;
- **UK-F4:** new-order and kitchen-delay alerts;
- **UK-F5:** staff clock-in, clock-out, and scheduling;
- **UK-NF3:** offline completion and later synchronisation of critical operations;
- **UK-NF5:** multilingual staff journeys.

Phase 0 must either add concrete scenarios and instrumentation for these requirements or mark them out of scope for this evaluation cycle. “The schema/framework can support it” is not outcome evidence.

## 3. Evidence Principles

### 3.1 Provenance classes

Every device, metric row, result, chart, and export must carry or inherit one of these provenance classes:

| Class | Meaning | Permitted use |
| --- | --- | --- |
| `REAL` | Produced by a physical pilot device or an authoritative POS/application integration | May support a validated use-case claim |
| `CONTROLLED` | Produced by a deterministic emulator or injected fault under a recorded test protocol | May support functional and resilience claims, with the test conditions stated |
| `SIMULATED` | Random or seeded demonstration data | Pipeline rehearsal only; must not support a real-world performance claim |

`Device.is_simulated` and the configured `device_source` are combined by `derive_provenance()`, and the class is snapshotted onto each telemetry and event row at write time, so historical rows do not silently inherit a device’s later classification. See [Evidence Recording](provenance-and-outcomes.md).

### 3.2 Claim maturity

Use the following labels consistently in D2.3:

| Label | Minimum evidence |
| --- | --- |
| **Implemented** | Code path and automated tests exist |
| **Demonstrated** | Scenario completed with `CONTROLLED` evidence |
| **Pilot-observed** | Scenario or KPI observed on `REAL` devices, but the target sample or duration was not met |
| **Validated** | Pre-agreed threshold met using the required `REAL` sample, duration, and evidence-quality gates |
| **Not evaluated** | No adequate scenario, instrumentation, or evidence |

### 3.3 Reproducibility rules

- Store timestamps in UTC and record the reporting timezone.
- Freeze the evaluation window before calculating results.
- Record site IDs, device IDs, device types, software versions, and provenance.
- Define exclusions before the run; do not remove failed runs without recording a reason.
- Retain numerator, denominator, and excluded-row counts for every rate.
- Version the calculation code and record the Git commit in the evidence manifest.
- Do not combine `REAL`, `CONTROLLED`, and `SIMULATED` results in one headline value.

## 4. Current Evidence Baseline

The repository has useful evaluation infrastructure, but most KPI claims are not yet reproducible from real pilot evidence.

| Capability | Current status | Evaluation consequence |
| --- | --- | --- |
| API request timing and status logging | Implemented | Can support API latency and failure calculations after aggregation and test-traffic filtering are added |
| Basic dashboard counts | Implemented | Supports live status display, not a time-bounded KPI result |
| Device metrics schema | Implemented | CPU, memory, and disk are available; several operational fields remain unpopulated by the real agent |
| Real device telemetry | Implemented | Real agent collects network latency, uptime, and collection metadata; POS signals remain config-gated |
| Error analytics | Implemented | Frontend and backend aligned on `error_message`/`context` with a contract test |
| Device state history | Implemented | Standardised on `extra_data` with an end-to-end contract test |
| Configuration history | Implemented | Before/after performance, success, and rollback outcome fields captured; closed-loop evidence for MW-03 to MW-05 |
| Real/simulated distinction | Implemented | Provenance snapshotted on telemetry and event rows via `derive_provenance()` |
| KPI aggregation | Implemented | EQ-01, MW-01 to MW-05, and PF-LAT computed by the export; freshness, connectivity, and health KPIs remain future work |
| KPI dashboard/export | Implemented | Versioned, filtered export with manifest, provenance scopes, raw evidence, REST API, and CLI |
| Validation gates for AI context | Implemented | Gates A-C can report contract, data-integrity, and context-readiness status for AI queries |
| Real pilot evidence | Not established | A controlled pilot run and signed run log are still required |

Relevant baselines are documented in [Architecture Compliance Matrix](architecture-compliance-matrix.md), [Database Metrics Validation](database-metrics-validation.md), [Real Device Integration Readiness](real-device-readiness-tasks.md), and [AI Validation Gates](ai-validation-gates.md). Some older documents describe simulated rows as “verified”; this roadmap uses the stricter provenance and claim-maturity definitions above.

## 5. KPI Register

Thresholds must be agreed with the UK use-case owner before the formal run. Values marked **TBD** are deliberately not invented after observing results. Baseline values may be collected during the rehearsal, but acceptance targets must then be frozen before the pilot evaluation.

**Implemented calculations:** EQ-01, MW-01 to MW-05, and PF-LAT are computed by the versioned export. See [KPI Export](kpi-export.md) for their stable definitions, formulas, units, manifest contract, and limitations. The remaining register items below are defined but not yet computed.

### 5.1 Evidence-quality KPIs

| ID | KPI and calculation | Population/window | Proposed acceptance rule | Required source |
| --- | --- | --- | --- | --- |
| EQ-01 | **Provenance coverage** = rows with valid provenance / eligible rows × 100 | All exported KPI input rows | 100% | Device identity plus immutable metric/event provenance |
| EQ-02 | **Telemetry completeness** = received expected samples / expected samples × 100 | Per real device and reporting window | TBD | Device metrics and configured collection interval |
| EQ-03 | **Telemetry freshness** = evaluation time − latest accepted sample time | Per real device, reported as p50/p95/max | TBD, tied to collection interval | Device metrics timestamps |
| EQ-04 | **Continuity** = intervals without a gap above the agreed limit / all expected intervals × 100 | Per real device | TBD | Gate B results or equivalent gap calculation |
| EQ-05 | **Valid record rate** = records passing schema/range checks / received records × 100 | Per source and run | TBD | Gate A/B check results and ingestion logs |

No operational KPI can receive a **Validated** label when its underlying evidence fails the agreed EQ-01 to EQ-05 gates.

### 5.2 Platform and device KPIs

| ID | KPI and calculation | Population/window | Threshold | Required evidence |
| --- | --- | --- | --- | --- |
| PF-01 | **Telemetry ingestion success** = accepted submissions / attempted submissions × 100 | Real devices; full pilot | TBD | Agent submission log joined to backend ingestion log |
| PF-02 | **End-to-end telemetry latency** = dashboard/backend availability time − device sample time | Real devices; p50/p95/max | TBD | Device timestamp and server receipt timestamp |
| PF-03 | **Connectivity rate** = time classified online / eligible monitored time × 100 | Per device and site | TBD | Heartbeats/state history with documented timeout rule |
| PF-04 | **Device uptime** = agent or OS active time / eligible pilot time × 100 | Per real device | TBD | Real agent uptime and restart records |
| PF-05 | **Health compliance** = healthy observations / valid health observations × 100 | Per device type/site | TBD | Health checks with a frozen healthy definition |
| PF-06 | **API failure rate** = requests with agreed failure status / eligible requests × 100 | Demonstrator API; exclude health/docs and identified test traffic | TBD | API request logs |
| PF-07 | **API response time** | Eligible requests grouped by endpoint; p50/p95/max | TBD | API request logs |

### 5.3 Management-workflow KPIs

| ID | KPI and calculation | Population/window | Threshold | Required evidence |
| --- | --- | --- | --- | --- |
| MW-01 | **Command completion rate** = completed commands / terminal commands × 100 | Commands sent to real pilot devices (only command types the owner granted) | TBD | Queue, agent execution, and status history |
| MW-02 | **Command round-trip time** = terminal status time − queue time | By command type; p50/p95/max (only granted command types) | TBD | Command audit timestamps |
| MW-03 | **Configuration-change success** = successful changes / attempted changes × 100 | Real devices and approved config scenarios | TBD | Configuration history with `was_successful` |
| MW-04 | **Verified improvement rate** = successful changes meeting the defined post-change health target / successful changes × 100 | Changes with valid before/after windows | TBD | `performance_before`, `performance_after`, health checks |
| MW-05 | **Rollback effectiveness** = rollbacks restoring the baseline health target / attempted rollbacks × 100 | Injected failed-change scenarios | TBD | Config history, rollback result, post-rollback health |
| MW-06 | **Detection time** = first demonstrator alert/state change − injected or observed incident start | Controlled incidents and real incidents separately | TBD | Fault log, state history, alerts |
| MW-07 | **Recovery time** = restored healthy state − incident start | Controlled incidents and real incidents separately | TBD | Incident run log and health/state history |

### 5.4 AI-assistance KPIs

| ID | KPI and calculation | Population/window | Threshold | Required evidence |
| --- | --- | --- | --- | --- |
| AI-01 | **Audit-ready query rate** = queries passing required validation gates / eligible AI queries × 100 | Scripted diagnostic query set | Report, then set target | Returned trust envelope |
| AI-02 | **Incident detection precision** = true-positive alerts / reviewed positive alerts | Labelled controlled fault set | TBD | Ground-truth fault log and anomaly output |
| AI-03 | **Incident detection recall** = detected ground-truth incidents / all ground-truth incidents | Labelled controlled fault set | TBD | Ground-truth fault log and anomaly output |
| AI-04 | **Unsupported-claim rate** = responses containing a claim not supported by supplied evidence / reviewed responses × 100 | Blinded expert review of scripted queries | TBD | Prompt/context snapshot, response, reviewer rubric |

AI narrative quality must not substitute for platform outcome evidence. Report the deterministic detector/gate result separately from any LLM-generated explanation.

## 6. Evaluation Scenarios

Each formal run uses a scenario ID, preconditions, operator, start/end timestamps, expected events, and links to raw evidence.

| Scenario | Demonstrator action | Principal KPIs | Evidence class |
| --- | --- | --- | --- |
| UK-E01 Enrol and observe | Enrol each supported pilot device type, authenticate it, and verify identity, telemetry, and dashboard status | EQ-01–05, PF-01–05 | `REAL` |
| UK-E02 Connectivity interruption | Disconnect a controlled pilot device, observe detection, reconnect it, and verify recovery and queued-data behaviour | PF-03, MW-06, MW-07 | `CONTROLLED` on real hardware |
| UK-E03 Remote command | Queue approved non-destructive commands, execute them on the agent, and verify terminal status on the dashboard | MW-01, MW-02 | `REAL` |
| UK-E04 Configuration change | Apply a safe configuration change and verify before/after health and success status | MW-03, MW-04 | `REAL` |
| UK-E05 Failed change and rollback | Inject an invalid but safe change, observe failure, roll back, and verify restored health | MW-05–07 | `CONTROLLED` on real hardware |
| UK-E06 API workload | Replay a versioned representative dashboard/operator workload | PF-06, PF-07 | `CONTROLLED` |
| UK-E07 AI-assisted diagnosis | Run a frozen query set for healthy, stale, incomplete, disconnected, and degraded-device conditions | AI-01–04 | Mixed; reported by provenance |
| UK-E08 Restaurant workflow | Exercise menu/order sync, kitchen alerts, or shift management using an authoritative UK integration | To be defined in Phase 0 | `REAL` or `CONTROLLED` |

UK-E08 is blocked until the UK partner confirms the external system, event contract, ground truth, and success criteria. Without those inputs, UK-F3 to UK-F5 remain **Not evaluated**.

## 7. Delivery Roadmap

### Phase 0 — Freeze the Evaluation Protocol

#### Outputs

- Signed scope mapping each UK requirement to a scenario or an explicit exclusion.
- Agreed KPI thresholds, pilot duration, number and types of devices, collection interval, and reporting timezone.
- Data-protection review covering transaction, staff, user-activity, and device identifiers.
- Frozen scenario scripts, fault catalogue, endpoint eligibility rules, and reviewer rubric.
- Named owners: UK use-case owner, demonstrator operator, data analyst, evidence reviewer, and D2.3 author.

**Exit gate:** No KPI remains ambiguous about formula, population, window, provenance, or acceptance rule.

### Phase 1 — Make Instrumentation Trustworthy

| Priority | Work package | Status | Acceptance evidence |
| --- | --- | --- | --- |
| P0 | Align frontend error payload with backend `error_message` and `context` fields | Done | Frontend/backend contract test proves message and context persistence |
| P0 | Standardise device-state history on `extra_data` | Done | Endpoint test proves request-to-database-to-response round trip |
| P0 | Preserve real/controlled/simulated provenance on telemetry and events | Done | Exported rows retain source classification independently of later device changes |
| P1 | Add real-agent network latency, uptime, sample timestamp, and submission-attempt telemetry | Done | Known-value tests plus observations from each pilot OS/device type |
| P1 | Integrate permitted real POS/application signals | Config-gated | Data-source agreement and side-by-side source validation; otherwise exclude operational POS KPIs |
| P1 | Complete post-change and rollback outcome capture | Done | Integration test populates before/after health, success, and rollback fields |
| P1 | Record command attempt and terminal outcome timestamps | Done | Full queue-to-agent-to-dashboard integration test |

**Exit gate:** A 24-hour rehearsal produces traceable, non-null inputs for all in-scope KPI calculations.

### Phase 2 — Build Reproducible KPI Calculations

Delivered as `GET /api/v1/kpi/export` and `./scripts/kpi-export.sh`. The
versioned export supports:

- `start`, `end`, `site_id`, `device_id`, `device_type`, and provenance filters;
- numerator, denominator, exclusions, and sample count;
- p50, p95, and maximum where latency is reported;
- raw CSV/JSON plus a machine-readable KPI summary;
- calculation version, Git commit, units, timezone, and generation timestamp;
- separate results for `REAL`, `CONTROLLED`, and `SIMULATED` evidence.

Automated tests cover empty windows, boundary timestamps, mixed provenance,
missing samples, percentile calculations, failed requests, and site/device
isolation. See [KPI Export](kpi-export.md) for the full contract.

**Exit gate:** A reviewer can regenerate every KPI value from a clean database snapshot and the evidence manifest.

### Phase 3 — Rehearse with Controlled Evidence

1. Seed only the data required for setup, labelled `SIMULATED`.
2. Execute UK-E01 to UK-E07 using deterministic inputs and controlled faults.
3. Verify clocks, IDs, expected sample counts, exclusions, and export completeness.
4. Record failed or ambiguous steps as issues; do not edit raw evidence.
5. Fix instrumentation and repeat until all evidence-quality gates pass.

**Exit gate:** One complete rehearsal evidence bundle is reproducible, with no simulated result presented as a pilot result.

### Phase 4 — Execute the Real Pilot

The minimum pilot profile must be agreed in Phase 0. The current readiness roadmap proposes 3–5 physical devices running for at least one full day; this is a useful engineering smoke test, not automatically a statistically adequate evaluation sample.

During the frozen pilot window:

- deploy versioned agent and demonstrator builds;
- record planned downtime and operator interventions;
- execute scenarios exactly as approved;
- monitor evidence quality without changing thresholds;
- preserve raw logs and exports read-only at the end of each run;
- document safety constraints and any scenario that could not be executed.

**Exit gate:** Required sample and duration are met, or the result is explicitly downgraded to **Pilot-observed**.

### Phase 5 — Analyse, Review, and Report

1. Generate KPI summaries without manual spreadsheet-only transformations.
2. Compare results with frozen thresholds and report confidence/dispersion where appropriate.
3. Triangulate KPI output with scenario logs and operator observations.
4. Conduct a second-person evidence review and resolve every discrepancy in an audit log.
5. Assign claim-maturity labels and document limitations, exclusions, and missing UK workflows.
6. Produce the UK D2.3 section from the reviewed evidence bundle.

**Final exit gate:** Every reported number resolves to a manifest entry, raw evidence, calculation version, and review decision.

## 8. Evidence Bundle

Store one immutable bundle per formal run:

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

The manifest should include the run ID, protocol version, Git commit, deployment versions, window, timezone, sites, devices, provenance, scenario IDs, file hashes, exclusions, and operator/reviewer identities. Screenshots illustrate a result but do not replace machine-readable evidence. See [Pilot Operator Protocol](operator-protocol.md) for the contents of each item and the operator procedure.

## 9. Completion Checklist

- [ ] UK requirement scope and exclusions approved.
- [ ] KPI formulas, thresholds, sample, duration, and owners frozen.
- [ ] Privacy and operational-safety review completed.
- [x] Frontend/backend analytics contracts fixed and tested.
- [x] Real-agent telemetry and immutable provenance complete.
- [x] Command and configuration outcomes close the loop.
- [x] KPI export and reproducible calculations implemented and tested.
- [ ] Controlled rehearsal passes evidence-quality gates.
- [ ] Real pilot meets the agreed sample and duration.
- [ ] UK-E01 to UK-E07 completed; UK-E08 completed or explicitly excluded.
- [ ] Independent evidence review completed.
- [ ] D2.3 claims use the agreed maturity labels and cite evidence-bundle IDs.

## 10. Immediate PR Sequence

| Order | Proposed PR | Status | Outcome |
| --- | --- | --- | --- |
| 1 | `fix: align analytics event contracts end to end` | Merged | Reliable error and state-history records with contract tests |
| 2 | `feat: preserve telemetry provenance and collection metadata` | Merged | Real, controlled, and simulated evidence cannot be mixed silently |
| 3 | `feat: capture real-agent latency uptime and operational signals` | Merged | Real inputs for PF-02, PF-04, and agreed POS KPIs |
| 4 | `feat: close configuration and command outcome tracking` | Merged | Reproducible MW-01 to MW-05 evidence |
| 5 | `feat: add UK demonstrator KPI calculations and export` | Merged | Time-bounded, filtered, versioned evidence output |
| 6 | `test: add KPI data-quality and scenario integration coverage` | Merged | Automated protection for formulas and end-to-end evidence flow |
| 7 | `docs: align analytics telemetry and pilot documentation` | This PR | Stable definitions, units, limitations, and operator protocol |

Phase 0 protocol decisions can proceed in parallel with PRs 1–2. The formal pilot must wait for PRs 1–6 and a successful controlled rehearsal.
