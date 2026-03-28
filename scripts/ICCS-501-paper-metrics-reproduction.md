# ICCS Paper 501: Metrics Reproduction Guide
**Paper Title:** Trustworthy Data Foundations for AI-Driven Analytics in Distributed IoT: A Validation-First Methodology  
**Submission:** 501 (TAMCS Workshop at ICCS)

This guide documents how to reproduce the quantitative metrics, trace volume indicators, and data integrity guarantees reported in the evaluation section of the paper.

## Prerequisites

1. **Database Access:** A PostgreSQL / TimescaleDB instance hosting the HOMEPOT telemetry schema.
   _Note: Setting up the complete platform (including the database, backend, and frontend) can be automated using the shell scripts provided in this repository. For comprehensive installation instructions, please refer to the main `README.md` and the "Getting Started" guide within the project's documentation._
2. **Required Tables:**
   - `device_metrics`
   - `health_checks`
   - `error_logs`
   - `api_request_logs`
   - `device_state_history`
3. **Data Availability:** To replicate the exact numbers in the paper, the underlying trace represents a 10-device simulation executed over a 10-day evaluation window.

## Execution

The exact SQL queries (Q1--Q8) referenced in the paper are bundled in `ICCS-501-paper-metrics.sql`.

To execute the script against your database:
```bash
psql -h <host> -U <user> -d <database> -f ICCS-501-paper-metrics.sql
```

## Query Mapping (Q1--Q8)

- **Volume and Coverage:**
  - **Q1:** Record counts over a fixed window (e.g., last 10 days) across all core operating tables.
  - **Q2:** Evaluates the number of distinct devices contributing to the trace.
- **Completeness and Validity (Gate B):**
  - **Q3:** Assesses field-level non-null completeness for `cpu`, `memory`, `disk`, and `latency` attributes.
  - **Q4:** Detects validity violations (e.g., ensuring percentage values strictly adhere to the $0 \le x \le 100$ constraint).
- **Temporal Continuity (Gate B):**
  - **Q5:** Calculates the absolute maximum inter-arrival gap over the continuity window (e.g., last 7 days).
  - **Q6:** Measures the maximum inter-arrival gap partitioned by individual device.
  - **Q7:** Counts sustained continuity dropouts (e.g., gaps exceeding 60 minutes) proving absence of long-term failure over the trace.
- **Collection-Rate Alignment:**
  - **Q8:** Verifies the smart-filtering baseline by computing sample arrivals per device per day, ensuring it meets or exceeds the heartbeat baseline.

## Customising Evaluation Windows
The SQL script by default uses `NOW() - INTERVAL '10 days'`. If your captured simulation trace occurred in the past, replace `NOW()` with your specific anchor timestamp or alter the interval directly in the `.sql` wrapper.
