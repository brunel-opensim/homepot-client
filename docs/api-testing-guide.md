# API Testing Guide

## Overview

This guide walks you through manually testing the HOMEPOT API endpoints to verify system functionality. This is different from automated unit testing - it's about validating the integration between components, testing real workflows, and verifying the system behaves correctly end-to-end.

## Prerequisites

Before starting API testing:

1. **Backend server running** on `http://localhost:8000`
   ```bash
   cd backend
   python -m homepot.main
   ```

2. **Required tools installed**:
   ```bash
   # jq for JSON formatting (highly recommended)
   sudo apt install jq  # Linux
   brew install jq      # macOS
   
   # curl (usually pre-installed)
   curl --version
   ```

3. **Database initialized** with seed data:
   ```bash
   cd backend
   python -m homepot.database
   ```

## Testing Approach

We'll test endpoints in this order:
1. **Health & Status** - Verify server is running
2. **Sites Management** - List and manage sites
3. **Agents** - Check POS simulators
4. **Devices** - Device health and management
5. **Jobs** - Job creation and tracking
6. **Audit** - Audit logging system
7. **Advanced Workflows** - Real-world scenarios

A `job` is a structured work order that tells devices:
- What to do (action + payload)
- Where to get the details (config_url)
- How urgent it is (priority)
- Who asked for it (created_by)
- What happened (status, result, timing)

## 1. Health & Status Endpoints

### Test Server Health

```bash
curl -s http://localhost:8000/health | jq .
```

**Expected Response:**
```json
{
  "status": "healthy",
  "client_connected": true,
  "version": "0.1.0",
  "timestamp": 12345.678
}
```

**Verify**: `status` is `"healthy"` and `client_connected` is `true`

### Check Client Status

```bash
curl -s http://localhost:8000/status | jq .
```

**Expected Response:**
```json
{
  "connected": true,
  "version": "0.1.0",
  "uptime": 123.45,
  "client_type": "HOMEPOT Client"
}
```

**Verify**: Server is connected and uptime is increasing

### Get Version

```bash
curl -s http://localhost:8000/version | jq .
```

**Expected Response:**
```json
{
  "version": "0.1.0"
}
```

## 2. Sites Management

### List All Sites

```bash
curl -s http://localhost:8000/sites | jq .
```

**Expected Response:**
```json
{
  "sites": [
    {
      "site_id": "site-001",
      "name": "Main Store - Downtown",
      "description": "Primary retail location with 5 POS terminals",
      "location": "123 Main St, Downtown",
      "created_at": "2025-10-24T19:25:30.084710"
    },
    {
      "site_id": "site-002",
      "name": "West Branch",
      "description": "Secondary location with 3 POS terminals",
      "location": "456 West Ave, West Side",
      "created_at": "2025-10-24T19:25:30.098584"
    }
  ]
}
```

**Verify**: At least 2 sites returned from seed data

### Get Specific Site

```bash
curl -s http://localhost:8000/sites/site-001 | jq .
```

**Expected Response:**
```json
{
  "site_id": "site-001",
  "name": "Main Store - Downtown",
  "description": "Primary retail location with 5 POS terminals",
  "location": "123 Main St, Downtown",
  "is_active": true,
  "created_at": "2025-10-24T19:25:30.084710",
  "updated_at": "2025-10-24T19:25:30.084714"
}
```

**Verify**: Site details match expected values

### Create New Site

```bash
curl -s -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-test-001",
    "name": "Test Branch API",
    "description": "Created via API testing",
    "location": "789 Test Street"
  }' | jq .
```

**Expected Response:**
```json
{
  "message": "Site site-test-001 created successfully",
  "site_id": "site-test-001",
  "name": "Test Branch API"
}
```

**Verify**: Site created successfully, returns new site_id

### Check Site Health

```bash
curl -s http://localhost:8000/sites/site-001/health | jq .
```

**Expected Response:**
```json
{
  "site_id": "site-001",
  "total_devices": 5,
  "healthy_devices": 5,
  "offline_devices": 0,
  "error_devices": 0,
  "health_percentage": 100.0,
  "status_summary": "5/5 terminals healthy",
  "devices": [
    {
      "device_id": "pos-terminal-001",
      "name": "POS Terminal 1",
      "type": "pos_terminal",
      "status": "online",
      "ip_address": "192.168.1.11",
      "last_seen": null
    }
    // ... more devices
  ],
  "last_updated": "2025-11-04T00:10:47.570383"
}
```

**Verify**: Health percentage and device counts are accurate

## 3. Agent Simulators

The system includes 8 POS terminal agent simulators that mimic real devices.

### List All Agents

```bash
curl -s http://localhost:8000/agents | jq .
```

**Expected Response:**
```json
{
  "agents": [
    {
      "device_id": "pos-terminal-001",
      "state": "health_check",
      "config_version": "1.0.0",
      "last_health_check": {
        "status": "healthy",
        "config_version": "1.0.0",
        "last_restart": "2025-11-03T11:08:25.126111",
        "response_time_ms": 339,
        "device_info": {
          "model": "POS-Terminal-X1",
          "firmware": "2.4.1",
          "os": "Linux ARM",
          "memory_mb": 2048,
          "storage_gb": 16,
          "uptime_hours": 668
        },
        "services": {
          "pos_app": "running",
          "payment_gateway": "connected",
          "database": "online",
          "network": "connected"
        },
        "metrics": {
          "cpu_usage_percent": 14,
          "memory_usage_percent": 32,
          "disk_usage_percent": 26,
          "transactions_today": 235,
          "uptime_seconds": 202971
        }
      },
      "uptime": "running"
    }
    // ... 7 more agents
  ]
}
```

**Verify**: 
- All 8 agents (pos-terminal-001 through pos-terminal-008) are present
- Most agents show `"status": "healthy"`
- Agents have realistic metrics (CPU, memory, transactions)
- One agent (pos-terminal-006) may show `"status": "unhealthy"` by design

### Get Specific Agent

```bash
curl -s http://localhost:8000/agents/pos-terminal-001 | jq .
```

**Expected Response:**
```json
{
  "device_id": "pos-terminal-001",
  "state": "health_check",
  "config_version": "1.0.0",
  "last_health_check": {
    "status": "healthy",
    // ... full health data
  },
  "uptime": "running"
}
```

**Verify**: Agent returns detailed health information

## 4. Device Management

### Get Device Health

```bash
curl -s http://localhost:8000/devices/pos-terminal-001/health | jq .
```

**Expected Response:**
```json
{
  "device_id": "pos-terminal-001",
  "health": {
    "status": "healthy",
    "config_version": "1.0.0",
    "device_info": {
      "model": "POS-Terminal-X1",
      "firmware": "2.4.1",
      "os": "Linux ARM"
    },
    "services": {
      "pos_app": "running",
      "payment_gateway": "connected",
      "database": "online",
      "network": "connected"
    }
  },
  "agent_state": "health_check",
  "last_updated": "2025-11-04T00:10:53.530022"
}
```

**Verify**: All services are running/connected

### Test Unhealthy Device

Check the health of `pos-terminal-006` (intentionally unhealthy by design):

```bash
curl -s http://localhost:8000/devices/pos-terminal-006/health | jq .
```

**Expected Response:**
```json
{
  "device_id": "pos-terminal-006",
  "health": {
    "status": "unhealthy",
    "services": {
      "pos_app": "error",
      "payment_gateway": "disconnected",
      "database": "offline",
      "network": "connected"
    },
    "error": "Payment gateway timeout"
  }
}
```

**Verify**: Device shows unhealthy status with error message

### Restart Unhealthy Device

```bash
curl -s -X POST http://localhost:8000/devices/pos-terminal-006/restart \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Testing restart functionality"
  }' | jq .
```

**Expected Response:**
```json
{
  "message": "Restart request sent to pos-terminal-006",
  "device_id": "pos-terminal-006",
  "response": {
    "status": "success",
    "message": "Application restarted successfully",
    "device_id": "pos-terminal-006",
    "health_check": {
      "status": "healthy",
      "services": {
        "pos_app": "running",
        "payment_gateway": "connected",
        "database": "online",
        "network": "connected"
      }
    }
  }
}
```

**Verify**: 
- Restart successful
- Device is now healthy
- All services are running

### Verify Device is Healthy After Restart

```bash
curl -s http://localhost:8000/devices/pos-terminal-006/health | jq '.health.status'
```

**Expected Output:**
```
"healthy"
```

**Verify**: Status changed from `"unhealthy"` to `"healthy"`

### Create New Device

```bash
curl -s -X POST http://localhost:8000/sites/site-test-001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pos-test-001",
    "name": "Test POS Terminal",
    "type": "pos_terminal",
    "ip_address": "192.168.1.100",
    "os_type": "Linux",
    "os_version": "Ubuntu 22.04"
  }' | jq .
```

**Expected Response:**
```json
{
  "message": "Device pos-test-001 created successfully",
  "device_id": "pos-test-001",
  "site_id": "site-test-001"
}
```

**Verify**: Device created and associated with site

## 5. Job Management

### Create a Job

Jobs are tasks sent to devices at a specific site.

```bash
curl -s -X POST http://localhost:8000/sites/site-001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "action": "Update POS configuration",
    "description": "Test job creation via API",
    "priority": "high"
  }' | jq .
```

**Expected Response:**
```json
{
  "message": "Job created successfully for site site-001",
  "job_id": "job-a42da035",
  "site_id": "site-001",
  "action": "Update POS configuration",
  "status": "queued"
}
```

**Verify**: 
- Job created with unique job_id
- Initial status is `"queued"`
- Save the `job_id` for next step

### Check Job Status

```bash
# Replace job-a42da035 with your job_id from previous step
curl -s http://localhost:8000/jobs/job-a42da035 | jq .
```

**Expected Response:**
```json
{
  "job_id": "job-a42da035",
  "action": "Update POS configuration",
  "status": "sent",
  "priority": "high",
  "site_id": "site-001",
  "segment": "pos-terminals",
  "config_url": "https://config.homepot.local/site-001/pos/v20251104-001115.json",
  "config_version": "v20251104-001115",
  "created_at": "2025-11-04T00:11:15.564427",
  "started_at": "2025-11-04T00:11:15.582761",
  "completed_at": null,
  "result": null,
  "error_message": null
}
```

**Verify**:
- Status progressed from `"queued"` to `"sent"`
- Has `started_at` timestamp
- Job orchestrator processed the job

### Check Job Status Again After Delay

```bash
# Wait a few seconds and check again
sleep 3
curl -s http://localhost:8000/jobs/job-a42da035 | jq '.status, .completed_at'
```

**Verify**: Job may progress to `"completed"` status

## 6. Audit System

### List Recent Audit Events

```bash
curl -s http://localhost:8000/audit/events | jq '.events[:3]'
```

**Expected Response:**
```json
[
  {
    "id": 5,
    "event_type": "job_created",
    "description": "Job job-a42da035 created for site site-001",
    "user_id": null,
    "job_id": "job-a42da035",
    "device_id": null,
    "site_id": "site-001",
    "event_metadata": {
      "action": "Update POS configuration",
      "priority": "high"
    },
    "created_at": "2025-11-04T00:11:15.564427"
  },
  {
    "id": 3,
    "event_type": "system_startup",
    "description": "HOMEPOT Client application started successfully",
    "event_metadata": {
      "version": "1.0.0",
      "components": ["database", "orchestrator", "agent_manager", "client"]
    },
    "created_at": "2025-11-04T00:07:55.383765"
  }
]
```

**Verify**: 
- Events are logged chronologically
- Job creation events appear
- System startup/shutdown events logged

### Get Audit Statistics

```bash
curl -s http://localhost:8000/audit/statistics | jq .
```

**Expected Response:**
```json
{
  "statistics": {
    "total_events": 5,
    "events_by_type": {
      "system_startup": 2,
      "system_shutdown": 1,
      "job_created": 2
    },
    "api_access_count": 0,
    "time_period_hours": 24,
    "since": "2025-11-03T00:11:08.129672"
  },
  "generated_at": "2025-11-04T00:11:08.139045"
}
```

**Verify**: Statistics accurately reflect recent activity

## 7. Push Notifications

### Send Test Notification

```bash
curl -s -X POST http://localhost:8000/agents/pos-terminal-001/push \
  -H "Content-Type: application/json" \
  -d '{
    "title": "System Alert",
    "body": "This is a test push notification",
    "data": {
      "priority": "high",
      "action": "display"
    }
  }' | jq .
```

**Expected Response:**
```json
{
  "message": "Push notification sent to pos-terminal-001",
  "device_id": "pos-terminal-001",
  "response": {
    "status": "success",
    "message": "Push notification received",
    "device_id": "pos-terminal-001",
    "timestamp": "2025-11-04T00:11:39.265180"
  }
}
```

**Verify**: 
- Notification sent successfully
- Agent acknowledged receipt

## 8. Advanced Testing Workflows

### Scenario 1: Complete Site Setup

Test the full workflow of setting up a new site with devices:

```bash
# 1. Create site
curl -s -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-new-001",
    "name": "New Retail Location",
    "description": "Complete setup test",
    "location": "100 Commerce St"
  }' | jq .

# 2. Add first device
curl -s -X POST http://localhost:8000/sites/site-new-001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pos-new-001",
    "name": "New POS Terminal 1",
    "type": "pos_terminal",
    "ip_address": "192.168.2.10",
    "os_type": "Linux",
    "os_version": "Ubuntu 22.04"
  }' | jq .

# 3. Add second device
curl -s -X POST http://localhost:8000/sites/site-new-001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pos-new-002",
    "name": "New POS Terminal 2",
    "type": "pos_terminal",
    "ip_address": "192.168.2.11",
    "os_type": "Linux",
    "os_version": "Ubuntu 22.04"
  }' | jq .

# 4. Check site health
curl -s http://localhost:8000/sites/site-new-001/health | jq .

# 5. Create deployment job for new site
curl -s -X POST http://localhost:8000/sites/site-new-001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "action": "Initial configuration deployment",
    "description": "Deploy base configuration to new site",
    "priority": "high"
  }' | jq .
```

**Verify**:
- Site created successfully
- Both devices added
- Site health shows 2 devices
- Job created for the site

### Scenario 2: Monitor Agent Health Degradation

Test the system's ability to detect and respond to health issues:

```bash
# 1. Check initial health
curl -s http://localhost:8000/devices/pos-terminal-006/health | jq '.health.status'

# 2. If unhealthy, restart it
curl -s -X POST http://localhost:8000/devices/pos-terminal-006/restart \
  -H "Content-Type: application/json" \
  -d '{"reason": "Health check failed"}' | jq .

# 3. Verify recovery
curl -s http://localhost:8000/devices/pos-terminal-006/health | jq '.health.status'

# 4. Check audit trail
curl -s http://localhost:8000/audit/events | jq '.events[] | select(.device_id == "pos-terminal-006")'
```

**Verify**:
- Unhealthy device detected
- Restart successful
- Health restored
- Actions logged in audit

### Scenario 3: Bulk Operations

Test multiple operations in sequence:

```bash
# Create multiple jobs
for i in {1..3}; do
  curl -s -X POST http://localhost:8000/sites/site-001/jobs \
    -H "Content-Type: application/json" \
    -d "{
      \"action\": \"Bulk test job $i\",
      \"description\": \"Testing bulk job creation\",
      \"priority\": \"medium\"
    }" | jq -c '{job_id, status}'
  sleep 1
done

# Check all jobs in audit
curl -s http://localhost:8000/audit/events | \
  jq '.events[] | select(.event_type == "job_created") | {job_id, created_at}'
```

**Verify**:
- All jobs created successfully
- Jobs processed by orchestrator
- Audit trail complete

## 9. API Documentation

### Access Interactive API Docs

FastAPI provides automatic interactive documentation:

```bash
# Open in browser
open http://localhost:8000/docs

# Or with xdg-open on Linux
xdg-open http://localhost:8000/docs
```

The `/docs` endpoint provides:
- Complete API schema
- Interactive "Try it out" functionality
- Request/response examples
- Parameter descriptions

### Alternative ReDoc Interface

```bash
open http://localhost:8000/redoc
```

ReDoc provides a cleaner, more documentation-focused interface.

## 10. Common Testing Patterns

### Pretty Print JSON Responses

```bash
# Use jq for formatted output
curl -s http://localhost:8000/sites | jq .

# Extract specific fields
curl -s http://localhost:8000/sites | jq '.sites[].name'

# Filter results
curl -s http://localhost:8000/agents | jq '.agents[] | select(.last_health_check.status == "unhealthy")'
```

### Save Responses for Analysis

```bash
# Save response to file
curl -s http://localhost:8000/agents > agents-snapshot.json

# Compare snapshots
diff agents-snapshot-1.json agents-snapshot-2.json
```

### Test Response Times

```bash
# Measure response time
curl -s -w "\nTime: %{time_total}s\n" http://localhost:8000/agents | jq '.agents | length'

# Test multiple endpoints
for endpoint in health status sites agents; do
  echo -n "$endpoint: "
  curl -s -w "%{time_total}s\n" -o /dev/null http://localhost:8000/$endpoint
done
```

### Automated Testing Script

Create a test script `test-api.sh`:

```bash
#!/bin/bash
set -e

echo "🧪 HOMEPOT API Testing Suite"
echo "=============================="
echo

# Test 1: Health check
echo "✓ Testing health endpoint..."
STATUS=$(curl -s http://localhost:8000/health | jq -r '.status')
if [ "$STATUS" != "healthy" ]; then
  echo "❌ Health check failed!"
  exit 1
fi
echo "Health check passed"

# Test 2: Sites
echo "✓ Testing sites endpoint..."
SITE_COUNT=$(curl -s http://localhost:8000/sites | jq '.sites | length')
if [ "$SITE_COUNT" -lt 2 ]; then
  echo "❌ Expected at least 2 sites!"
  exit 1
fi
echo "Found $SITE_COUNT sites"

# Test 3: Agents
echo "✓ Testing agents endpoint..."
AGENT_COUNT=$(curl -s http://localhost:8000/agents | jq '.agents | length')
if [ "$AGENT_COUNT" -ne 8 ]; then
  echo "❌ Expected 8 agents, found $AGENT_COUNT!"
  exit 1
fi
echo "All 8 agents running"

# Test 4: Create and check job
echo "✓ Testing job creation..."
JOB_ID=$(curl -s -X POST http://localhost:8000/sites/site-001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "action": "Test job",
    "description": "Automated test",
    "priority": "low"
  }' | jq -r '.job_id')

if [ -z "$JOB_ID" ]; then
  echo "❌ Job creation failed!"
  exit 1
fi

JOB_STATUS=$(curl -s http://localhost:8000/jobs/$JOB_ID | jq -r '.status')
echo "Job created: $JOB_ID (status: $JOB_STATUS)"

echo
echo "🎉 All tests passed!"
```

Make it executable and run:

```bash
chmod +x test-api.sh
./test-api.sh
```

## Troubleshooting

### Server Not Responding

```bash
# Check if server is running
curl -v http://localhost:8000/health

# Check process
ps aux | grep homepot

# Check port
lsof -i :8000
```

### Connection Refused

```bash
# Verify server is listening on correct port
netstat -tulpn | grep 8000

# Check firewall (if applicable)
sudo ufw status

# Try different host
curl http://127.0.0.1:8000/health
```

### Unexpected Responses

```bash
# Check server logs
tail -f backend/logs/homepot.log

# Increase curl verbosity
curl -v http://localhost:8000/sites

# Test with minimal request
curl -X GET http://localhost:8000/health
```

### Agent Simulators Not Working

```bash
# Check agent manager started
curl -s http://localhost:8000/agents | jq '.agents | length'

# Verify database has devices
sqlite3 backend/data/homepot.db "SELECT COUNT(*) FROM devices;"

# Check server startup logs for agent initialization
```

## Best Practices

### 1. Test in Order
Start with basic endpoints (health, status) before testing complex workflows.

### 2. Save Job IDs
When creating jobs, save the `job_id` to track status later.

### 3. Use Variables
```bash
SITE_ID="site-001"
curl -s http://localhost:8000/sites/$SITE_ID | jq .
```

### 4. Check Audit Trail
After operations, verify they're logged in audit events.

### 5. Test Error Cases
Try invalid requests to verify error handling:
```bash
# Missing required field
curl -s -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -d '{"name": "Missing site_id"}' | jq .

# Non-existent resource
curl -s http://localhost:8000/sites/invalid-id | jq .
```

## Next Steps

After completing API testing:

1. **Review Unit Tests**: See [Testing Guide](testing-guide.md) for automated tests
2. **Integration Testing**: Test with real push notification services
3. **Load Testing**: Use tools like Locust or Apache Bench
4. **Frontend Integration**: Connect React frontend to API
5. **Real Device Testing**: Deploy to actual POS terminals

## Related Documentation

- [Running Locally Guide](running-locally.md) - Initial setup
- [Testing Guide](testing-guide.md) - Unit testing with pytest
- [Development Guide](development-guide.md) - Development workflow
- [Database Guide](database-guide.md) - Database schema and queries
- [Agent Simulation](agent-simulation.md) - POS agent simulator details

## Questions or Issues?

If you encounter problems during API testing:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review server logs for errors
3. Verify database is initialized
4. Check [GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)
5. Ask the team for help

---

**Happy Testing!**
