# Analytics Data Collection

This document explains what data HOMEPOT collects for AI integration and where it's stored.

## Overview

HOMEPOT Client automatically collects operational data to enable AI-powered insights and recommendations. The system uses 5 PostgreSQL tables to store different types of analytics data.

**Current Status:**
- Database tables created
- API request logging (automatic via middleware)
- Device state tracking (needs implementation)
- Job outcome tracking (needs implementation)
- Error logging (needs implementation)
- Frontend user activity (needs implementation)

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

## Query Endpoints

The backend provides API endpoints to query collected analytics data:

- `GET /api/v1/analytics/requests` - Query API request logs
- `GET /api/v1/analytics/device-states` - Query device state history
- `GET /api/v1/analytics/jobs` - Query job outcomes
- `GET /api/v1/analytics/errors` - Query error logs
- `GET /api/v1/analytics/user-activities` - Query user activities

All endpoints support filtering by:
- `start_date` / `end_date`: Time range
- Additional filters specific to each endpoint

Example:
```bash
curl "http://localhost:8000/api/v1/analytics/requests?start_date=2025-12-01&end_date=2025-12-05"
```

---

## Database Setup

Create the analytics tables by running:

```bash
python backend/utils/create_analytics_tables.py
```

This script is idempotent - safe to run multiple times.

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

**Phase 1 (Current):**
- API request logging (automatic)

**Phase 2 (This Week):**
- Add device state logging to backend
- Add job outcome logging to backend
- Add error logging to exception handlers
- Frontend implements user activity tracking

**Phase 3 (Next Week):**
- Let system run for 3-5 days
- Collect real usage patterns
- Validate data quality
- Prepare for AI integration

---

## Privacy & Security

- All sensitive data (passwords, tokens) is excluded from logging
- User IDs are anonymized for AI training
- Data retention: 90 days (configurable)
- Access restricted to admin users only

---

## Next Steps

1. **Backend Team:** Add logging for device states, job outcomes, and errors
2. **Frontend Team:** Implement user activity tracking
3. **DevOps:** Run system for 3-5 days to collect real data
4. **AI Team:** Review collected data and define training requirements

For implementation guides, see:
- [Frontend Analytics Integration](frontend-analytics-integration.md)
- [Backend Analytics Guide](backend-analytics.md)
