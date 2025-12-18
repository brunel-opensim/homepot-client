# Analytics Data Collection

This document explains what data HOMEPOT collects for AI integration and where it's stored.

## Overview

HOMEPOT Client automatically collects operational data to enable AI-powered insights and recommendations. The system uses 8 PostgreSQL tables to store different types of analytics data:

- **5 operational analytics tables**: API requests, device states, job outcomes, errors, user activities
- **3 AI-focused tables**: Device metrics, configuration history, site schedules

- **5 Core Analytics Tables:** API requests, device states, job outcomes, errors, user activities
- **3 AI-Focused Tables:** Device performance metrics, configuration history, site schedules

**Current Status:** (Verified Dec 18, 2025)
- Database tables created (all 8 tables, verified in PostgreSQL)
- API request logging (automatic via middleware, **123 rows actively collecting**)
- Frontend user activity tracking (fully implemented in 6+ pages with analytics.js)
- Analytics API endpoints (10 endpoints ready and tested)
- Device performance metrics collection (needs periodic background task)
- Configuration change tracking (needs integration in config endpoints)
- Site operating schedules (needs admin interface or manual setup)
- Device state tracking (needs integration in device management)
- Job outcome tracking (needs integration in job execution)
- Error logging (frontend integrated, needs backend exception handlers)

---

## 1. API Request Logs

**Table:** `api_request_logs`  
**Collection Status:** Automatic (AnalyticsMiddleware active)

### What It Stores

Every API request made to the backend is automatically logged with:

- `timestamp`: When the API was called
- `endpoint`: API path (e.g., `/api/v1/devices`, `/api/v1/sites`)
- `method`: HTTP method (GET, POST, PUT, DELETE)
- `status_code`: Response code (200, 404, 500, etc.)
- `response_time_ms`: How long the request took
- `user_id`: Who made the request
- `ip_address`: Client IP address
- `user_agent`: Browser/client information
- `error_message`: Error details if request failed
- `request_size_bytes`: Request payload size
- `response_size_bytes`: Response payload size

### Example Data

```
timestamp           | endpoint          | method | status | time  | user_id
--------------------|-------------------|--------|--------|-------|----------
2025-12-05 13:45:23 | /api/v1/devices   | GET    | 200    | 45ms  | user123
2025-12-05 13:46:10 | /api/v1/sites     | GET    | 200    | 32ms  | user123
2025-12-05 13:47:05 | /api/v1/devices/1 | PUT    | 200    | 89ms  | user456
2025-12-05 13:48:00 | /api/v1/auth      | POST   | 401    | 12ms  | null
```

### Use Cases for AI

- Identify most-used endpoints
- Detect performance bottlenecks
- Pattern recognition for user workflows
- Predict API failures

---

## 2. Device State History

**Table:** `device_state_history`  
**Collection Status:** Needs manual logging in backend code

### What It Stores

Tracks every device state change with:

- `timestamp`: When the state changed
- `device_id`: Device identifier
- `previous_state`: State before change (e.g., "online", "offline")
- `new_state`: State after change
- `changed_by`: User ID or "system"
- `reason`: Why the change happened
- `extra_data`: Additional JSON context

### Example Data

```
timestamp           | device_id | previous | new     | changed_by | reason
--------------------|-----------|----------|---------|------------|------------------
2025-12-05 14:00:00 | dev_001   | online   | offline | user123    | Maintenance
2025-12-05 14:15:00 | dev_001   | offline  | online  | system     | Auto-recovery
2025-12-05 14:30:00 | dev_002   | idle     | active  | user456    | Manual trigger
```

### Use Cases for AI

- Predict device failures
- Identify maintenance patterns
- Recommend optimal maintenance schedules
- Detect anomalous state transitions

### Implementation Required

Add logging calls in your device management code:

```python
from homepot.app.models.AnalyticsModel import DeviceStateHistory

# When device state changes
db.add(DeviceStateHistory(
    device_id=device.device_id,
    previous_state="online",
    new_state="offline",
    changed_by=current_user.id,
    reason="User-initiated maintenance"
))
db.commit()
```

---

## 3. Job Outcomes

**Table:** `job_outcomes`  
**Collection Status:** Needs manual logging in job execution code

### What It Stores

Tracks execution results of jobs (firmware updates, config changes, etc.):

- `timestamp`: When the job completed
- `job_id`: Unique job identifier
- `job_type`: Type of job (e.g., "firmware_update", "restart")
- `device_id`: Target device
- `status`: success, failed, timeout, cancelled
- `duration_ms`: How long the job took
- `error_code`: Error code if failed
- `error_message`: Error details
- `retry_count`: Number of retry attempts
- `initiated_by`: User who started the job
- `extra_data`: Additional JSON context

### Example Data

```
timestamp           | job_id  | job_type        | device  | status  | duration | error
--------------------|---------|-----------------|---------|---------|----------|-------
2025-12-05 14:15:00 | job_456 | firmware_update | dev_001 | success | 3500ms   | null
2025-12-05 14:20:00 | job_457 | restart         | dev_002 | success | 1200ms   | null
2025-12-05 14:25:00 | job_458 | config_change   | dev_003 | failed  | 5000ms   | E_TIMEOUT
```

### Use Cases for AI

- Predict job success rates
- Identify failure patterns
- Recommend optimal job scheduling
- Estimate job completion times

### Implementation Required

Add logging in your job execution logic:

```python
from homepot.app.models.AnalyticsModel import JobOutcome

# After job completion
db.add(JobOutcome(
    job_id=job.id,
    job_type="firmware_update",
    device_id=device.id,
    status="success",
    duration_ms=duration,
    initiated_by=current_user.id
))
db.commit()
```

---

## 4. Error Logs

**Table:** `error_logs`  
**Collection Status:** Needs manual logging when errors occur

### What It Stores

Categorized error tracking for system health:

- `timestamp`: When the error occurred
- `category`: api, database, external_service, validation
- `severity`: critical, error, warning, info
- `error_code`: Error code (e.g., "E_DB_TIMEOUT")
- `error_message`: Human-readable error description
- `stack_trace`: Full stack trace for debugging
- `endpoint`: API endpoint if applicable
- `user_id`: User affected by error
- `device_id`: Device related to error
- `context`: Additional JSON context
- `resolved`: Whether error is resolved
- `resolved_at`: Resolution timestamp

### Example Data

```
timestamp           | category | severity | error_code    | message              | resolved
--------------------|----------|----------|---------------|----------------------|----------
2025-12-05 14:30:00 | database | error    | E_DB_TIMEOUT  | Connection timeout   | false
2025-12-05 14:35:00 | api      | warning  | E_RATE_LIMIT  | Rate limit exceeded  | true
2025-12-05 14:40:00 | external | critical | E_MQTT_DOWN   | MQTT broker offline  | false
```

### Use Cases for AI

- Predict system failures
- Identify recurring error patterns
- Recommend preventive actions
- Prioritize critical issues

### Implementation Required

Add error logging in exception handlers:

```python
from homepot.app.models.AnalyticsModel import ErrorLog

try:
    # Your code
    pass
except Exception as e:
    db.add(ErrorLog(
        category="database",
        severity="error",
        error_code="E_DB_TIMEOUT",
        error_message=str(e),
        stack_trace=traceback.format_exc(),
        endpoint=request.url.path,
        user_id=current_user.id if current_user else None
    ))
    db.commit()
    raise
```

---

## 5. User Activities

**Table:** `user_activities`  
**Collection Status:** Needs frontend implementation

### What It Stores

Tracks user interactions in the frontend:

- `timestamp`: When the activity occurred
- `user_id`: User identifier
- `session_id`: Browser session ID
- `activity_type`: page_view, click, search, form_submit, etc.
- `page_url`: Current page URL
- `element_id`: HTML element ID clicked
- `search_query`: Search terms entered
- `extra_data`: Additional JSON context
- `duration_ms`: Time spent on page/activity

### Example Data

```
timestamp           | user_id | activity    | page_url  | element_id         | search_query
--------------------|---------|-------------|-----------|--------------------|--------------
2025-12-05 14:45:00 | user123 | page_view   | /devices  | null               | null
2025-12-05 14:45:15 | user123 | click       | /devices  | add-device-button  | null
2025-12-05 14:46:00 | user123 | search      | /devices  | device-search      | temperature
2025-12-05 14:47:00 | user123 | form_submit | /devices  | device-form        | null
```

### Use Cases for AI

- Understand user behavior patterns
- Identify unused features
- Recommend UI improvements
- Personalize user experience

### Implementation Required

Frontend developers need to add tracking calls. See [Frontend Analytics Integration](frontend-analytics-integration.md) for details.

---

## 6. Device Performance Metrics

**Table:** `device_metrics`  
**Collection Status:** Needs periodic collection (recommended: every 5 minutes)

### What It Stores

Tracks device performance metrics over time for predictive maintenance and optimization:

- `timestamp`: When metrics were collected
- `device_id`: Device identifier
- `cpu_percent`: CPU usage percentage
- `memory_percent`: Memory usage percentage
- `disk_percent`: Disk usage percentage
- `network_latency_ms`: Network latency in milliseconds
- `transaction_count`: Number of transactions processed
- `transaction_volume`: Dollar amount of transactions
- `error_rate`: Error rate percentage
- `active_connections`: Number of active connections
- `queue_depth`: Number of queued items
- `extra_metrics`: Additional JSON metrics

### Example Data

```
timestamp           | device_id | cpu% | mem% | disk% | trans | error_rate
--------------------|-----------|------|------|-------|-------|------------
2025-12-11 14:00:00 | dev_001   | 45.2 | 62.8 | 38.5  | 156   | 0.64
2025-12-11 14:05:00 | dev_001   | 48.1 | 65.2 | 38.6  | 162   | 0.71
2025-12-11 14:10:00 | dev_001   | 52.3 | 68.5 | 38.7  | 178   | 0.85
```

### Use Cases for AI

- Predict device performance degradation
- Identify resource bottlenecks before they cause issues
- Recommend hardware upgrades based on usage patterns
- Correlate performance with transaction volume
- Detect anomalous behavior patterns

### Implementation Required

Add periodic metrics collection (e.g., in a background task):

```python
from homepot.app.models.AnalyticsModel import DeviceMetrics

# Every 5 minutes
async def collect_device_metrics(device_id: str):
    metrics = await get_device_performance(device_id)
    
    db.add(DeviceMetrics(
        device_id=device_id,
        cpu_percent=metrics.cpu,
        memory_percent=metrics.memory,
        disk_percent=metrics.disk,
        network_latency_ms=metrics.latency,
        transaction_count=metrics.transactions,
        transaction_volume=metrics.volume,
        error_rate=metrics.error_rate
    ))
    await db.commit()
```

---

## 7. Configuration History

**Table:** `configuration_history`  
**Collection Status:** Needs logging on all config changes

### What It Stores

Tracks configuration changes and their impact for AI learning:

- `timestamp`: When configuration was changed
- `entity_type`: Type of entity (device, site, system)
- `entity_id`: Identifier of the entity
- `parameter_name`: Name of the parameter changed
- `old_value`: Previous value (JSON)
- `new_value`: New value (JSON)
- `changed_by`: User who made the change
- `change_reason`: Why the change was made
- `change_type`: manual, automated, ai_recommended
- `performance_before`: Performance metrics before change (JSON)
- `performance_after`: Performance metrics after change (JSON)
- `was_successful`: Whether change achieved desired result
- `was_rolled_back`: Whether change was reverted
- `rollback_reason`: Why it was rolled back

### Example Data

```
timestamp           | entity  | entity_id | parameter       | old   | new   | success | rolled_back
--------------------|---------|-----------|-----------------|-------|-------|---------|-------------
2025-12-11 14:00:00 | device  | dev_001   | max_connections | 10    | 15    | true    | false
2025-12-11 14:30:00 | device  | dev_002   | timeout_ms      | 5000  | 10000 | false   | true
2025-12-11 15:00:00 | site    | site_001  | peak_hours      | 12-14 | 11-15 | true    | false
```

### Use Cases for AI

- Learn which configuration changes improve performance
- Recommend optimal settings based on historical data
- Identify failed configuration patterns to avoid
- Predict impact of configuration changes before applying
- Automatically suggest rollback for degraded performance

### Implementation Required

Add logging whenever configuration is changed:

```python
from homepot.app.models.AnalyticsModel import ConfigurationHistory

# Before change
before_metrics = await measure_performance(device_id)

# Apply change
await update_device_config(device_id, "max_connections", 15)

# After change (wait a bit for metrics)
await asyncio.sleep(60)
after_metrics = await measure_performance(device_id)

# Log the change
db.add(ConfigurationHistory(
    entity_type="device",
    entity_id=device_id,
    parameter_name="max_connections",
    old_value={"value": 10},
    new_value={"value": 15},
    changed_by=current_user.id,
    change_reason="Increased load during peak hours",
    change_type="manual",
    performance_before={"avg_response_time": 145, "error_rate": 1.2},
    performance_after={"avg_response_time": 98, "error_rate": 0.3},
    was_successful=True
))
await db.commit()
```

---

## 8. Site Operating Schedules

**Table:** `site_operating_schedules`  
**Collection Status:** Needs manual configuration per site

### What It Stores

Defines site operating hours and maintenance windows for intelligent job scheduling:

- `site_id`: Site identifier
- `day_of_week`: Day (0=Monday, 6=Sunday)
- `open_time`: Store opening time
- `close_time`: Store closing time
- `is_closed`: Whether site is closed (holiday, etc.)
- `is_maintenance_window`: Whether maintenance is preferred
- `expected_transaction_volume`: Expected number of transactions
- `peak_hours_start`: Peak period start time
- `peak_hours_end`: Peak period end time
- `notes`: Additional notes
- `special_considerations`: JSON with special rules

### Example Data

```
site_id  | day | open_time | close_time | maintenance | peak_start | peak_end | trans_volume
---------|-----|-----------|------------|-------------|------------|----------|-------------
site_001 | 0   | 08:00:00  | 22:00:00   | false       | 12:00:00   | 14:00:00 | 500
site_001 | 1   | 08:00:00  | 22:00:00   | false       | 12:00:00   | 14:00:00 | 550
site_001 | 6   | 10:00:00  | 18:00:00   | true        | 13:00:00   | 15:00:00 | 200
```

### Use Cases for AI

- Schedule maintenance jobs during low-traffic periods
- Avoid disrupting operations during peak hours
- Predict optimal times for firmware updates
- Recommend maintenance windows based on traffic patterns
- Alert when maintenance is overdue

### Implementation Required

Configure schedules through admin interface or API:

```python
from homepot.app.models.AnalyticsModel import SiteOperatingSchedule
from datetime import time

# Monday schedule
db.add(SiteOperatingSchedule(
    site_id="site_001",
    day_of_week=0,  # Monday
    open_time=time(8, 0),
    close_time=time(22, 0),
    is_maintenance_window=False,
    expected_transaction_volume=500,
    peak_hours_start=time(12, 0),
    peak_hours_end=time(14, 0),
    notes="Regular business day"
))

# Sunday - preferred maintenance
db.add(SiteOperatingSchedule(
    site_id="site_001",
    day_of_week=6,  # Sunday
    open_time=time(10, 0),
    close_time=time(18, 0),
    is_maintenance_window=True,
    expected_transaction_volume=200,
    peak_hours_start=time(13, 0),
    peak_hours_end=time(15, 0),
    notes="Preferred maintenance window: 6am-9am"
))
await db.commit()
```

---

## Query Endpoints

The backend provides API endpoints to query collected analytics data:

- `GET /api/v1/analytics/requests` - Query API request logs
- `GET /api/v1/analytics/device-states` - Query device state history
- `GET /api/v1/analytics/jobs` - Query job outcomes
- `GET /api/v1/analytics/errors` - Query error logs
- `GET /api/v1/analytics/user-activities` - Query user activities
- `GET /api/v1/analytics/device-metrics` - Query device performance metrics
- `GET /api/v1/analytics/config-history` - Query configuration changes
- `GET /api/v1/analytics/site-schedules` - Query site operating schedules

All endpoints support filtering by:
- `start_date` / `end_date`: Time range
- Additional filters specific to each endpoint

Example:
```bash
curl "http://localhost:8000/api/v1/analytics/requests?start_date=2025-12-01&end_date=2025-12-05"
curl "http://localhost:8000/api/v1/analytics/device-metrics?device_id=dev_001&start_date=2025-12-11"
```

## Command-Line Query Tool

Use the query-db.sh script to inspect analytics data:

```bash
# Show counts for all tables
./scripts/query-db.sh count

# Query specific analytics tables
./scripts/query-db.sh api_request_logs
./scripts/query-db.sh device_state_history
./scripts/query-db.sh job_outcomes
./scripts/query-db.sh error_logs
./scripts/query-db.sh user_activities

# Query AI-focused tables
./scripts/query-db.sh device_metrics
./scripts/query-db.sh configuration_history
./scripts/query-db.sh site_operating_schedules
```

---

## Database Setup

All analytics tables are created automatically when you initialize the database:

```bash
./scripts/init-postgresql.sh
```

This creates:
- 6 core tables (sites, devices, users, jobs, health_checks, audit_logs)
- 5 analytics tables (api_request_logs, user_activities, device_state_history, job_outcomes, error_logs)
- 3 AI-focused tables (device_metrics, configuration_history, site_operating_schedules)

**Total: 14 tables** with sample data for each.

The script is idempotent - safe to run multiple times.

---

## Testing the System

Validate that analytics collection is working:

```bash
python backend/utils/demo_analytics.py
```

This will:
1. Check that backend is running
2. Generate test API calls
3. Query analytics endpoints
4. Display collected data summary

---

## Data Collection Timeline

**Phase 1 (COMPLETE - Dec 18, 2025):**
- API request logging (automatic, 123+ requests logged)
- Database tables created (all 14 tables)
- Sample data populated
- Frontend analytics integrated (trackActivity, trackSearch, trackError)
- Analytics API endpoints (10 endpoints ready)

**Phase 2:**
- Add device performance metrics collection (periodic background task)
- Add configuration change logging to all config update endpoints
- Add site operating schedules through admin interface
- Add device state logging to backend device management
- Add job outcome logging to backend job execution
- Add error logging to backend exception handlers
- Generate real user activity through application usage

**Phase 3:**
- Let system run for 3-5 days
- Collect real usage patterns (target: 1000+ rows per table)
- Validate data quality for all 8 analytics tables
- Prepare for AI integration (Phase 3 of roadmap)

---

## Privacy & Security

- All sensitive data (passwords, tokens) is excluded from logging
- User IDs are anonymized for AI training
- Data retention: 90 days (configurable)
- Access restricted to admin users only

---

## Next Steps

### Phase 2: Data Collection Implementation (In Progress)

**Completed:**
1. **Device Metrics Collection** (Implemented: Dec 18, 2025)
   - Added automatic collection in agents.py _run_health_check()
   - Collects CPU, memory, disk usage, and transaction counts
   - Runs every 30 seconds for all 12 POS agents
   - Stores in device_metrics table with proper TimescaleDB compatibility
   - Verified: All 12 devices saving metrics successfully

2. **Job Outcomes Logging** (Implemented: Dec 18, 2025)
   - Added logging in orchestrator.py at all job completion points
   - Captures job duration, status (success/failed/completed), and error messages
   - Logs device counts, push notification results, and execution metadata
   - Fixed site_id resolution for string-based security identifiers
   - Verified: Successfully logging all 4 outcome scenarios (success, failed, exception, no devices)

**Remaining Tasks:**
3. **Device State History**
   - Add hooks in DeviceEndpoint.py to log state transitions
   - Estimated time: 2-3 hours

4. **Error Logging**
   - Add backend exception handlers to log errors
   - Estimated time: 3 hours

5. **Configuration History**
   - Add hooks in config endpoints to track changes
   - Estimated time: 3 hours

### Original Next Steps

1. **Backend Team:** 
   - ~~Add periodic device metrics collection (every 5 minutes)~~ DONE (every 30s)
   - Add configuration history logging to all config changes
   - Add logging for device states, job outcomes, and errors
   
2. **Admin Team:**
   - Configure site operating schedules for all locations
   - Define maintenance windows
   
3. **Frontend Team:** 
   - Implement user activity tracking
   
4. **DevOps:** 
   - Run system for 3-5 days to collect real data
   - Monitor database growth and performance
   
5. **AI Team:** 
   - Review collected data from all 8 analytics tables
   - Define training requirements
   - Develop initial predictive models

For implementation guides, see:
- [Frontend Analytics Integration](frontend-analytics-integration.md)
- [Backend Analytics Guide](backend-analytics.md)
- [Fresh Database Setup](fresh-database-setup.md)
