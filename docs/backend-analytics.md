# Backend Analytics Infrastructure

## Overview

This analytics infrastructure provides comprehensive data collection and querying capabilities to support AI development and operational insights.

## Components

### 1. Data Models (`AnalyticsModel.py`)

**APIRequestLog**: Tracks all API requests
- Endpoint, method, status code
- Response time, user, IP address
- Request/response sizes
- Error messages

**DeviceStateHistory**: Tracks device state changes
- Device ID, previous/new state
- Changed by (user or system)
- Reason and metadata

**JobOutcome**: Tracks job execution results
- Job type, device, status
- Duration, error codes
- Retry count, metadata

**ErrorLog**: Categorized error tracking
- Category (api, database, external_service, validation)
- Severity (critical, error, warning, info)
- Stack trace, context
- Resolution status

**UserActivity**: Tracks user behavior (frontend integration)
- Activity type (page_view, click, search, interaction)
- Page URL, element ID
- Search queries
- Session tracking

### 2. API Endpoints (`AnalyticsEndpoint.py`)

#### Data Collection Endpoints

**POST `/api/v1/analytics/user-activity`** - Log user activity
- Requires authentication
- Used by frontend to track user behavior

**POST `/api/v1/analytics/error`** - Log errors
- Can be called from frontend or backend
- Categorizes and tracks errors

### 3. Smart Data Filtering

To prevent database overload from high-frequency device metrics, the system implements a **Smart Data Filtering** mechanism (`SmartDataFilter`).

**Logic:**
1.  **Snapshot Interval**: A full snapshot of device metrics is stored every 5 minutes (configurable) regardless of changes, ensuring a heartbeat.
2.  **Significant Change**: Metrics are stored immediately if they deviate by more than 5% (configurable) from the last stored value.
3.  **First Contact**: The first data point received from a device (after system restart) is always stored.

This ensures that the database only grows with meaningful data while maintaining high-resolution visibility during active state changes.

**POST `/api/v1/analytics/device-state-change`** - Log device state changes
- Called when device state changes
- Tracks who/what triggered the change

**POST `/api/v1/analytics/job-outcome`** - Log job results
- Called after job execution
- Tracks success/failure patterns

#### Query Endpoints (Admin/Authenticated)

**GET `/api/v1/metrics/api-performance`** - API performance metrics
- Query params: `hours` (1-168), `endpoint` (optional)
- Returns request counts, avg/min/max response times

**GET `/api/v1/metrics/job-outcomes`** - Job execution statistics
- Query params: `hours` (1-168), `job_type` (optional)
- Returns success rates, avg duration

**GET `/api/v1/metrics/error-trends`** - Error trend analysis
- Query params: `hours` (1-168), `category` (optional)
- Returns error counts by category/severity

**GET `/api/v1/metrics/device-state-history/{device_id}`** - Device history
- Query params: `hours` (1-720)
- Returns state change timeline

### 3. Middleware (`analytics.py`)

**AnalyticsMiddleware**: Automatic API request logging
- Captures all API requests automatically
- Non-blocking (doesn't slow down requests)
- Configurable (can be disabled)
- Skips health checks and metrics endpoints

## Setup

### 1. Database Migration

Create the analytics tables:

```bash
cd backend
# Add AnalyticsModel to your database initialization
# Tables will be created automatically on first run
```

### 2. Enable Middleware

Add to `main.py`:

```python
from homepot.app.middleware.analytics import AnalyticsMiddleware

app.add_middleware(AnalyticsMiddleware, enable_logging=True)
```

### 3. Register Analytics Router

Add to `Api.py`:

```python
from homepot.app.api.API_v1.Endpoints import AnalyticsEndpoint

app.include_router(
    AnalyticsEndpoint.router,
    prefix="/api/v1",
    tags=["Analytics"]
)
```

## Usage Examples

### Backend Integration

#### Log Device State Change

```python
from homepot.app.models.AnalyticsModel import DeviceStateHistory
from datetime import datetime, timezone

# When device state changes
state_change = DeviceStateHistory(
    device_id="device-123",
    previous_state="online",
    new_state="offline",
    changed_by="system",
    reason="Network timeout",
    extra_data={"last_seen": "2025-12-01T10:00:00Z"},
    timestamp=datetime.now(timezone.utc)
)
db.add(state_change)
db.commit()
```

#### Log Job Outcome

```python
from homepot.app.models.AnalyticsModel import JobOutcome

# After job execution
outcome = JobOutcome(
    job_id="job-456",
    job_type="device_restart",
    device_id="device-123",
    status="success",
    duration_ms=5000,
    initiated_by="user@example.com",
    timestamp=datetime.now(timezone.utc)
)
db.add(outcome)
db.commit()
```

### Frontend Integration

#### Log User Activity

```javascript
// Example: Track page view
await fetch('/api/v1/analytics/user-activity', {
  method: 'POST',
  credentials: 'include', // Include httpOnly cookie
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    activity_type: 'page_view',
    page_url: window.location.pathname,
    session_id: sessionStorage.getItem('session_id'),
    duration_ms: 1500
  })
});

// Example: Track search
await fetch('/api/v1/analytics/user-activity', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    activity_type: 'search',
    page_url: '/dashboard',
    search_query: 'device status',
    extra_data: { results_count: 5 }
  })
});
```

#### Log Frontend Errors

```javascript
// Example: Log error in error boundary
window.addEventListener('error', async (event) => {
  await fetch('/api/v1/analytics/error', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      category: 'frontend',
      severity: 'error',
      error_message: event.message,
      stack_trace: event.error?.stack,
      context: {
        url: window.location.href,
        user_agent: navigator.userAgent
      }
    })
  });
});
```

### Query Analytics Data

```python
# Get API performance for last 24 hours
response = await client.get("/api/v1/metrics/api-performance?hours=24")

# Get job outcomes for specific job type
response = await client.get("/api/v1/metrics/job-outcomes?hours=168&job_type=restart")

# Get error trends
response = await client.get("/api/v1/metrics/error-trends?hours=24&category=api")

# Get device state history
response = await client.get("/api/v1/metrics/device-state-history/device-123?hours=720")
```

## Configuration

### Environment Variables

```bash
# Enable/disable analytics logging
ANALYTICS_ENABLED=true

# Retention period (days) for analytics data
ANALYTICS_RETENTION_DAYS=90
```

### Middleware Configuration

```python
# Disable analytics logging (e.g., for testing)
app.add_middleware(AnalyticsMiddleware, enable_logging=False)
```

## Data Retention

Implement a cleanup job to remove old analytics data:

```python
# Run daily/weekly to clean up old data
from datetime import datetime, timedelta, timezone

retention_days = 90
cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

db.query(APIRequestLog).filter(APIRequestLog.timestamp < cutoff_date).delete()
db.query(DeviceStateHistory).filter(DeviceStateHistory.timestamp < cutoff_date).delete()
# ... repeat for other tables

db.commit()
```

## Performance Considerations

1. **Indexes**: All timestamp and frequently queried fields are indexed
2. **Async Logging**: Middleware logs asynchronously to avoid blocking requests
3. **Selective Logging**: Health checks and metrics endpoints are skipped
4. **Batch Queries**: Use time-based queries with limits to avoid large result sets

## Future Enhancements

1. **Real-time Dashboard**: Connect to analytics endpoints for live monitoring
2. **Alerting**: Set up alerts based on error rates, response times
3. **Data Export**: Export analytics data for external analysis
4. **AI Integration**: Use collected data to train recommendation models
5. **Aggregation Tables**: Create pre-computed hourly/daily aggregates for faster queries

## Testing

```bash
# Run analytics tests
pytest tests/test_analytics.py -v

# Test with coverage
pytest tests/test_analytics.py --cov=homepot.app --cov-report=html
```

## Dependencies

Required packages (already in requirements.txt):
- FastAPI
- SQLAlchemy
- Python 3.10+

## Support

For questions or issues:
1. Check the API documentation: `/docs` endpoint
2. Review error logs in the database
3. Check middleware logs for debugging
