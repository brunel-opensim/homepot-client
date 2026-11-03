# 2. Data Overview

## 2.1 Data Sources and Acquisition Methods

### 2.1.5 United Kingdom, Food Technology

**Scope and evidence baseline:** The UK Food Technology demonstrator is led by Brunel University of London with Dealdio and GetFudo. Its purpose is to support reliable operation and maintenance of heterogeneous restaurant and POS endpoints through the HOMEPOT Dashboard and a device-side User App/agent. The User App provides the bridge to devices, with user permission governing monitoring and management. Windows 10 and Windows 11 form the initial testing scope; macOS, Android and Linux are planned extensions. Mobivisor integration is implemented in the codebase (proxy endpoints for device, group and app management), but its role in the UK demonstrator specifically remains a project decision.

The technical description in this contribution is based on a targeted documentation and source-code review of main at commit 048c889f9ddd6ebf75016085160e2f0dca706cba, reviewed on 31 October 2026 [UK-R1]. This fixes the implementation reference, rather than establishing the deployed server version or the date of an operational measurement campaign. The codebase has continued to evolve since this commit (PRs #703–#747), including per-provider LLM tuning, investigation sessions with SSE streaming, and an embedded AI workspace. Findings referencing configuration values should be verified against the current revision before final publication.

**Sources and acquisition:** Device agents submit periodic resource and health telemetry to backend services. Backend middleware and application services also generate API-request records, state transitions, errors, task outcomes, configuration changes and user/action activity. These complementary sources support correlation of endpoint condition with management activity through device identifiers, site identifiers and timestamps. Access to the analysis data is through authorised backend queries and exports.

**Evidence populations:** Real-device, controlled-test and simulated records must be identified separately in the selected analysis population. Selected tables retain provenance and collection-interval metadata when records are written; command-derived exports use the device provenance available at export time. This difference must be recorded when interpreting historical command evidence.

[UK evidence to add: reporting interval in UTC, extraction date, deployed backend/App versions, sites and devices by OS, row counts by source and provenance, actual collection intervals, access authorisation and deviations from D4.1.]

## 2.2 Data Characteristics and Structure

### 2.2.5 United Kingdom, Food Technology

**Structure and attributes: **The backend provides structured relational records through SQLAlchemy models, with JSON or structured metadata where appropriate. Device metrics include CPU, memory, disk and network-latency information. Related records describe device states, API requests, errors, jobs, configuration history, user activity and action outcomes. Device, site and time fields provide the principal relationships for longitudinal and site-specific analysis.

The analysis distinguishes observations, derived scores and management outcomes. Resource measurements and recorded command states are observations; anomaly, risk and scheduling scores are algorithm outputs. An approved action, a completed command and an improved device condition represent different events and must not be counted as equivalent outcomes. Units, timestamp conventions and denominator populations must accompany each exported measure.

**Data sensitivity:** The schemas support user identifiers, IP addresses, user activity and free-text metadata. The wider demonstrator also handles customer/order information, but the fields actually included in the D4.3 analytical extraction have not yet been confirmed. The UK dataset therefore cannot be described categorically as containing no personal identifiers. The extraction must document included fields, exclusions or pseudonymisation, access controls and any external AI-service recipients. Schema availability does not establish that a field is populated or used in analysis.

[UK evidence to add: selected tables and fields, verified units, dataset size and period, non-null coverage and the approved data-minimisation/de-identification policy. Device numbers and data volumes remain unconfirmed.]

## 2.3 Preprocessing and Quality Assessment

### 2.3.5 United Kingdom, Food Technology

**Implemented preparation:** The analytics service aggregates device metrics and operational events over defined time windows. Diagnostic context is assembled from scoped device/site information and bounded history. Documentation questions follow a separate retrieval path. These implemented preparations do not establish that a complete dataset-wide cleaning, deduplication, resampling or time-alignment campaign has been performed.

**Runtime quality assessment:** Diagnostic requests pass through a validation envelope. Its data-integrity stage checks completeness, freshness, continuity and validity before context is considered ready for actionable interpretation. At the reviewed revision, checked-in settings include freshness of 300 seconds, continuity of 1,800 seconds, a maximum null ratio of 0.01 and a sustained-gap threshold of 3,600 seconds. The continuity (1,800 s) and null-ratio (0.01) settings are relaxed development settings; the stricter values described elsewhere are continuity ≤ 60 s and null ratio = 0. The configuration actually used must accompany each result.

**Missingness and coverage:** Some resource averages currently treat absent values as zero, which can depress estimated utilisation. A low mean must therefore be interpreted with its non-null coverage and collection interval. Runtime readiness scores describe the implemented checks; they are not measured diagnostic accuracy or a substitute for a dataset-quality report.

[UK evidence to add: missing/invalid values by field, duplicates, timestamp and gap summaries, coverage by device/site/provenance, cleaning decisions and the thresholds used for the selected reporting interval.]

# 3. Methodology

## 3.1 AI-Based Approaches and Service Architecture

### 3.1.5 United Kingdom, Food Technology

**Analytical approach:** The UK implementation combines operational-data aggregation, deterministic anomaly rules, heuristic risk and scheduling indicators, and retrieval-grounded interaction with a pretrained language model [UK-R1]. The inspected anomaly detector and failure predictor are not locally trained classifiers. No local LLM training or fine-tuning is established by the reviewed evidence.

**Service sequence:** A request entering the backend is first classified by a deterministic router. Knowledge questions retrieve documentation passages with source paths and do not require live-fleet validation. This route deliberately excludes previous-answer memory. Diagnostic questions assemble current device/fleet context and relevant scoped history, then apply validation stages for infrastructure contracts, data integrity, context readiness, permissions/capabilities and lifecycle. Language-model output interprets this context for the operator.

The validation envelope stops at the first failing stage and constrains actionability. A failed check can still result in cautionary explanatory text. Its readiness/trust score is not empirically calibrated and does not certify that a generated diagnosis is correct. Historical answers retrieved from memory are also not independent incident ground truth.

**Management sequence:** Proposed actions are recorded as plans. Approval and execution are separate operations, with scope and membership checks in the backend and device-side permission boundaries in the User App workflow. Human approval authorises an operation; it does not validate the diagnosis or establish that the operation succeeded. Operational outcomes must be measured separately.

The architecture supports local Ollama inference and external-provider adapters. The active deployment, enabled functions and external data flows must be confirmed before this implementation description is treated as the configuration of an evaluated service.

## 3.2 Feature Engineering, Knowledge Base Design, and System Configuration

### 3.2.5 United Kingdom, Food Technology

**Operational features:** The anomaly detector uses seven threshold signals: CPU, memory and disk utilisation above 90%; error-rate ratio above 0.05; network latency above 200 ms; more than five state changes; and at least three consecutive failures. Fixed contributions are summed, capped and scaled by sensitivity. The checked-in sensitivity is 0.8, giving a maximum current-default score of 0.8. This score is not a calibrated anomaly probability.

The prototype failure indicator assigns weights of 0.35 to resource patterns, 0.30 to error patterns, 0.20 to state stability and 0.15 to health trend. The latter two factors currently return zero, limiting the implemented score to 0.65. Its nominal prediction horizon and factor-based confidence do not establish calibrated failure forecasting. Scheduling recommendations combine health, historical outcomes, operating schedules and errors through rules; their success scores likewise require empirical validation.

**Knowledge and memory:** The documentation retriever indexes top-level docs/*.md files using heading-aware chunks. Checked-in settings select three chunks of 600 characters with 150-character overlap and a maximum cosine distance of 0.9. Diagnostic memory is a separate ChromaDB resource scoped by user, site and device, with a configured 90-day retention. These settings describe retrieval behaviour, rather than measured retrieval quality.

**Inference configuration:** Repository defaults select Ollama/llama3.2, temperature 0.7, an 8,192-token context, a 120-token output cap and one concurrent generation. Per-provider overrides exist for Ollama, OpenAI and Anthropic (e.g. num_predict raised to 512 and max_concurrent to 4 for cloud providers), so effective values may differ from base defaults. Provider/model selection and environment overrides can change the running configuration. The diagnostic context budget defaults to 1,000 characters (reduced from 4,000 to reduce model confusion), with per-provider overrides up to 6,000 for cloud providers. Read-only repository access is implemented but disabled by default.

**Reproducibility:** Each experiment requires its code revision, configuration, model identifier/digest, dependency versions, hardware, knowledge-corpus snapshot, input population and random seed where applicable. Rules and pretrained inference do not require an invented local training split. Independent labelled cases and untouched evaluation periods are still needed to assess diagnostic correctness and operational benefit.

[UK evidence to add: deployed overrides and enabled flags, model/digest and quantisation, machine specifications, dependency versions, corpus snapshot and the original configurations of the uncertainty studies.]

## 3.3 Evaluation Framework and Performance Metrics

For the UK use case, computational sensitivity/scenario studies, runtime readiness checks and operational KPI measurements are distinct evidence classes. Anomaly and risk scores are not calibrated probabilities. Diagnostic assessment should use independently labelled cases or an explicit assessor rubric, while service evaluation uses dated exports and request-level timings. Real-device, controlled and simulated populations must remain distinguishable, with denominators, exclusions and null results disclosed. No diagnostic-accuracy or KPI-achievement value is inferred from implementation tests alone.

# 4. Analysis and Service Results

## 4.1 Country-specific Use Case Findings

### 4.1.5 United Kingdom, Food Technology

**Status and scope:** The repository contains three computational uncertainty studies, with scripts, reports and tracked figures [UK-R2]. They provide preliminary analysis of scoring behaviour and model assumptions. The reviewed evidence does not establish restaurant-pilot diagnostic accuracy or measured improvement across physical devices.

**Anomaly sensitivity:** The first study applies second-order polynomial-chaos expansion to seven assumed input distributions, with 2,187 model evaluations and Sobol sensitivity analysis. These are evaluations of sampled computational states, rather than observations from 2,187 endpoints. Interpretation depends on the selected ranges, distributions and detector configuration.

**Scenario boundaries:** The second study evaluates six controlled input scenarios using 2,700 Saltelli samples per scenario, or 16,200 evaluations. The wrapper calls the detector on sampled scenario inputs. The reported healthy and high-CPU cases illustrate how fixed weights and the selected alert threshold can suppress single-signal alerts. These findings require their original run configuration and are not field false-positive or missed-detection rates.

**Configuration reconciliation:** Some reported scores in the first two studies exceed the current-default bound of 0.8. A focused source-level check confirmed a maximum of 0.8 with current defaults and 1.0 with sensitivity explicitly set to 1.0. Original run manifests or reproducible reruns are needed to reconcile the historical results before carrying their numerical summaries into the final report.

**Push model:** The third study uses 20,000 main samples and 12,000 prior-sensitivity samples in an analytical expected-value model. It assumes a Beta(19,1) delivery probability and uniformly sampled campaign sizes from 1 to 50. Expected failures are n(1-p), the failure fraction is 1-p, and campaign time is prescribed as 100+400n/(n+1) ms. These relationships support analysis of assumptions and sensitivity; they do not measure real command delivery or server latency.

**Implementation findings:** The review also identifies limits relevant to interpretation: incomplete factors cap the failure indicator at 0.65; configuration-impact analysis returns a neutral placeholder; and some resource aggregation treats missing values as zero. These findings inform the next evaluation and must not be presented as completed predictive or causal analyses.

[UK evidence to add: original campaign outputs/configurations or reconciled reruns, figure provenance, and any independently labelled diagnostic or completed physical-device test results. No TRL level or operational success rate is established by the repository review alone.]

## 4.2 Service Performance Results

### 4.2.5 United Kingdom, Food Technology

**Available measurement capability:** The backend implements an evidence export for provenance coverage (EQ-01), command completion (MW-01), command turnaround (MW-02), configuration-change success (MW-03), an implemented health/non-regression criterion (MW-04), rollback effectiveness (MW-05), and device-reported network latency (PF-LAT) [UK-R3]. This capability enables measurement but does not itself provide a measured result.

**Definitions and denominators:** MW-01 uses completed commands divided by terminal commands and excludes pending/sent commands. MW-02 measures creation-to-terminal time, including queue time, and reports p50, p95 and maximum by command type. PF-LAT concerns device-reported network latency, not language-model response time. MW-04 accepts a healthy after-state or non-regressed response time under its implemented rule; this does not establish causal performance improvement. Empty denominators produce null results and must not be reported as success.

**Reporting status:** A dated, frozen server export has not been supplied for this contribution. Generated evidence is intentionally excluded from Git, so its absence from the tracked repository does not show that server measurements do not exist. The reviewed documentation also contains machine-specific inference timing observations, but their different models, workloads and configurations do not constitute a comparable deployed-service benchmark.

The service evaluation should report the observation interval, sample counts, provenance, exclusions, command types, device/OS/site distribution, software/model configuration, hardware and load. Each measured KPI requires its approved baseline, target and mapping to FPP/D2.3. Diagnostic correctness requires independently assessed cases; AI-response latency requires request-level timing under a stated workload. Runtime quality gates do not substitute for these evaluations.

[UK evidence to add: approved reporting interval and KPI export/manifest, baseline and target values, completed device-test records, diagnostic assessment if performed, and representative service timing/availability/resource measurements. Until then, KPI achievement and field accuracy remain pending.]

## 4.3 Comparative Analysis of AI Approaches and Service Outcomes

**UK comparison contribution.** The UK combines explainable operational rules and heuristic indicators with pretrained language-model interpretation. Its computational sensitivity studies assess scoring behaviour under assumed inputs, whereas its planned operational evaluation concerns command outcomes, device condition and service performance. These outputs cannot be ranked directly against forecasting errors or classification accuracy from other use cases. A shared contribution is the traceability of inputs, configuration and outcomes; evidence of comparative operational benefit remains pending.

# 5. Discussion

## 5.1 Key Findings and Insights

**UK contribution.** The implementation provides a traceable sequence from endpoint and backend observations through scoped analysis, operator interpretation and separately approved actions. The principal lesson is to distinguish data readiness, diagnostic correctness, authorised execution and observed device outcomes. This distinction supports evidence collection for later verification and evaluation without treating implemented controls as proof of field performance.

## 5.2 Challenges and Limitations

**UK limitations and mitigation.** The reviewed revision is not yet tied to a frozen deployed dataset or service-measurement bundle. Historical uncertainty-study scores require reconciliation with current sensitivity scaling, some risk factors and impact-analysis functions are incomplete, and missing-value treatment can affect resource averages. Ground-truth diagnostic cases, confirmed analytical privacy scope and representative physical-device results remain necessary. Mitigation is to freeze code/configuration and dataset manifests, recover or rerun the computational campaigns, disclose incomplete factors and missingness, and collect dated KPI/device-test evidence. Current development quality thresholds must be reported explicitly rather than replaced by stricter design thresholds.

# References

[\[UK-R1\]](https://github.com/brunel-opensim/homepot-client/tree/048c889f9ddd6ebf75016085160e2f0dca706cba) Brunel University of London, HOMEPOT Client repository, implementation snapshot 048c889f9ddd6ebf75016085160e2f0dca706cba, reviewed 31 October 2026. Source documentation and code underpin Sections 2.1.5 to 3.2.5; this reference is not a deployed-run manifest.

[\[UK-R2\]](https://github.com/brunel-opensim/homepot-client/tree/048c889f9ddd6ebf75016085160e2f0dca706cba/docs/uq) HOMEPOT Client, uncertainty studies and runners: uq/study1_anomaly, uq/study2_simulator and uq/study3_push; reports in docs/uq. Same repository snapshot as [UK-R1]. Historical numerical outputs require their original campaign configuration or reconciled reruns.

[\[UK-R3\]](https://github.com/brunel-opensim/homepot-client/tree/048c889f9ddd6ebf75016085160e2f0dca706cba/backend/src/homepot/kpi) HOMEPOT Client, operational KPI calculator/export and kpi-evidence guidance. Same repository snapshot as [UK-R1]. Generated evidence bundles are excluded from version control and must be supplied separately for measured results.

