# Data Collection Guide for Developers

## Purpose

Collect 3-5 days of analytics data to train AI models for:
- Predictive job scheduling
- Device failure prediction  
- Performance optimization
- Intelligent resource allocation

## Prerequisites

1. **PostgreSQL 16** with TimescaleDB installed
2. **Python 3.12+**
3. **Virtual environment** set up
4. **.env file** configured with database credentials

## Quick Start (One Command)

```bash
./scripts/start-data-collection.sh
```

Once running, the backend automatically:

- Spawns 10+ simulated POS agents at startup
- Collects device metrics every **2 seconds** (high-frequency mode)
- Records job outcomes and state transitions
- Logs errors and configuration changes

**Just leave it running for 3-5 days!**

## Validation (Check Progress Anytime)

Run this command to see what data has been collected:

```bash
source .venv/bin/activate
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py
```

The validation script now checks for a comprehensive set of metrics:
- **System**: CPU, Memory, Disk Usage
- **Business**: Transaction Count, Transaction Volume
- **Network**: Latency, Active Connections
- **Reliability**: Error Rates, Uptime

**Note:** The `-W ignore::DeprecationWarning` flag suppresses datetime warnings (database uses timezone-naive timestamps for compatibility).

### Validation Options

**Check with minimum days requirement:**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --min-days 3
```

**Export validation report to JSON:**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --report collection_report.json
```

**Quick check (0 days minimum):**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --min-days 0
```

### Sample Output:

```
======================================================================
HOMEPOT Data Collection Validation
======================================================================
Minimum data requirement: 3 days

✓ Database Connectivity: Connected
✓ Agent Activity: 12 devices active
✓ Device Metrics: 45620 records (2.7 days)
⚠ Job Outcomes: Only 1.2/3.0 days
✓ Device State History: 234 records (2.7 days)
✓ Error Logs: 48 records (2.7 days)
✓ Configuration History: 15 records (2.7 days)
✓ Site Operating Schedules: 7 schedules configured

Data Quality Checks:
  ✓ All data within expected ranges

Collection Continuity:
  ✓ Continuous data collection confirmed

======================================================================
Validation Summary
======================================================================
Total Checks: 9
  ✓ Passed: 8
  ⚠ Warnings: 1
  ✗ Failed: 0

⚠ Overall Status: WARNING
Some warnings detected. Review recommendations below.

Recommendations:
  1. Continue running for 1-2 more days to reach minimum threshold
```

## What's Being Collected

The system automatically collects data across **8 analytics tables**:

| Table | Collection Rate | Purpose |
|-------|----------------|---------|
| **device_metrics** | Every 5 seconds | CPU, memory, disk, network latency |
| **job_outcomes** | Per job | Success/failure patterns, execution time |
| **device_state_history** | On state change | ONLINE ↔ OFFLINE ↔ ERROR transitions |
| **error_logs** | Real-time | Categorized errors with severity levels |
| **configuration_history** | On config change | Track config update impacts |
| **site_operating_schedules** | Static config | Operating hours, peak times, maintenance |
| **site_analytics** | Daily aggregation | Site-level performance summaries |
| **device_analytics** | Daily aggregation | Device-level statistics |

## Manual Setup (If Needed)

### 1. Setup Database

```bash
python scripts/setup_database.py
```

### 2. Configure Site Schedules

```bash
python backend/utils/populate_schedules.py
```

### 3. Start Backend

```bash
source .venv/bin/activate
uvicorn homepot.main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting

### No Data Being Collected

**Check 1: Is the backend running?**
```bash
curl http://localhost:8000/health
```

**Check 2: Are agents active?**
```bash
curl http://localhost:8000/agents | jq
```

Expected: 10-12 active agents

**Check 3: Database connectivity**
```bash
./scripts/query-db.sh
```

This command provides an interface to query the PostgreSQL database. Available commands include:

```bash
Usage: ./scripts/query-db.sh [command]

(e.g., ./scripts/query-db.sh schema health_checks)

Available commands:
  tables              - List all tables
  users               - Show all users
  sites               - Show all sites
  devices             - Show all devices
  jobs                - Show all jobs
  health_checks       - Show recent health checks
  audit_logs          - Show recent audit logs
  api_request_logs    - Show recent API requests
  user_activities     - Show recent user activities
  device_state_history - Show device state changes
  device_metrics      - Show device performance metrics
  configuration_history - Show configuration changes
  site_operating_schedules - Show site schedules
  job_outcomes        - Show job execution outcomes
  error_logs          - Show recent errors
  count               - Count rows in all tables
  schema [table]      - Show table structure
  where               - Show where PostgreSQL stores data
  sql 'query'         - Run custom SQL query

Examples:
  ./scripts/query-db.sh count
  ./scripts/query-db.sh jobs
  ./scripts/query-db.sh audit_logs
  ./scripts/query-db.sh schema health_checks
  ./scripts/query-db.sh sql 'SELECT * FROM sites LIMIT 1;'
```

### Backend Crashes

**Check logs:**
```bash
tail -f backend/backend.log
```

**Common issues:**
- Database credentials incorrect (check `.env`)
- Port 8000 already in use (kill existing process)
- Missing dependencies (run `pip install -r requirements.txt`)

### Validation Fails

**Run with verbose output:**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --min-days 5
```

**Save report for analysis:**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --report collection_report.json
```

## When You're Done (After 3-5 Days)

1. **Stop the backend** (Ctrl+C)

2. **Run final validation:**
```bash
python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py --min-days 3 --report final_report.json
```

3. **Check you have:**
   - All 8 tables with data
   - 3+ days of continuous collection
   - No critical errors
   - <5% collection gaps

4. **Report to team lead:**
   - Share `final_report.json`
   - Mention any warnings/issues
   - Note total collection days

## Understanding the Data

### Device Metrics Example:
```json
{
  "device_id": "pos-terminal-001",
  "cpu_percent": 45.2,
  "memory_percent": 62.8,
  "disk_percent": 38.5,
  "network_latency_ms": 12.3,
  "timestamp": "2025-12-18T10:15:30Z"
}
```

### Job Outcome Example:
```json
{
  "job_id": "job-12345",
  "site_id": "site-001",
  "status": "completed",
  "started_at": "2025-12-18T09:00:00Z",
  "completed_at": "2025-12-18T09:05:30Z",
  "duration_seconds": 330,
  "devices_updated": 5
}
```

### Why This Data Matters:

The AI uses this data to:
- **Predict failures**: "Device X has 85% chance of failure in next 24h"
- **Optimize scheduling**: "Deploy at 9 AM (85% success rate) instead of 6 PM (45% success)"
- **Recommend actions**: "High CPU + frequent errors → restart recommended"

## Support

**Issues?** Contact the backend team or check:
- Backend logs: `backend/backend.log`
- Database logs: `docker logs postgres` (if using Docker)
- Validation report: `python -W ignore::DeprecationWarning backend/utils/validate_data_collection.py`

## Success Criteria

You're done when validation shows:

```
✓ Overall Status: PASSED
All checks passed! Data collection is healthy.
```

**Expected timeline:** 3-5 days of continuous running
**Storage needed:** ~500MB per day (varies by activity)
**CPU usage:** 5-10% (background collection)

If you hit any roadblocks, please reach out for assistance or preferably create a GitHub Issue!
