# Analytics Data Examples

This document shows realistic examples of what analytics tables will contain after HOMEPOT Client runs for a few days with actual users.

---

## 1. API Request Logs (api_request_logs)

**Scenario:** 3 users accessing the system over 2 days

```sql
SELECT * FROM api_request_logs ORDER BY timestamp DESC LIMIT 20;
```

| id  | timestamp           | endpoint                      | method | status | response_ms | user_id | ip_address    | user_agent                    |
|-----|---------------------|-------------------------------|--------|--------|-------------|---------|---------------|-------------------------------|
| 245 | 2025-12-07 15:23:45 | /api/v1/devices               | GET    | 200    | 42          | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 244 | 2025-12-07 15:23:30 | /api/v1/sites                 | GET    | 200    | 35          | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 243 | 2025-12-07 15:20:12 | /api/v1/devices/dev_042       | PUT    | 200    | 89          | usr_456 | 192.168.1.67  | Mozilla/5.0 Firefox/121.0     |
| 242 | 2025-12-07 15:18:55 | /api/v1/auth/login            | POST   | 200    | 156         | null    | 192.168.1.67  | Mozilla/5.0 Firefox/121.0     |
| 241 | 2025-12-07 15:15:20 | /api/v1/mobivisor/groups      | GET    | 200    | 67          | usr_789 | 192.168.1.99  | PostmanRuntime/7.36.0         |
| 240 | 2025-12-07 15:12:08 | /api/v1/devices/dev_001       | GET    | 404    | 23          | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 239 | 2025-12-07 15:10:44 | /api/v1/analytics/requests    | GET    | 200    | 234         | usr_789 | 192.168.1.99  | PostmanRuntime/7.36.0         |
| 238 | 2025-12-07 14:58:33 | /api/v1/devices               | POST   | 201    | 312         | usr_456 | 192.168.1.67  | Mozilla/5.0 Firefox/121.0     |
| 237 | 2025-12-07 14:45:21 | /api/v1/devices/dev_025/state | PUT    | 200    | 445         | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 236 | 2025-12-07 14:30:15 | /api/v1/sites                 | GET    | 200    | 38          | usr_456 | 192.168.1.67  | Mozilla/5.0 Firefox/121.0     |
| 235 | 2025-12-07 14:15:09 | /api/v1/devices               | GET    | 500    | 5002        | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 234 | 2025-12-07 13:55:42 | /api/v1/auth/logout           | POST   | 200    | 45          | usr_456 | 192.168.1.67  | Mozilla/5.0 Firefox/121.0     |
| 233 | 2025-12-07 13:30:18 | /api/v1/devices/dev_042       | DELETE | 204    | 178         | usr_789 | 192.168.1.99  | PostmanRuntime/7.36.0         |
| 232 | 2025-12-07 12:45:33 | /api/v1/sites/site_003        | GET    | 200    | 56          | usr_123 | 192.168.1.45  | Mozilla/5.0 Chrome/120.0      |
| 231 | 2025-12-07 11:20:05 | /api/v1/mobivisor/devices     | GET    | 200    | 123         | usr_789 | 192.168.1.99  | PostmanRuntime/7.36.0         |

**Insights from this data:**
- User `usr_123` is the most active (5 requests shown)
- Most requests are GET (viewing data)
- One error occurred: 500 on `/api/v1/devices` (took 5 seconds - timeout?)
- User `usr_789` uses Postman (likely a developer/admin)
- Average response time: ~250ms (excluding the timeout)

---

## 2. Device State History (device_state_history)

**Scenario:** Devices changing states due to maintenance, failures, and recovery

```sql
SELECT * FROM device_state_history ORDER BY timestamp DESC LIMIT 15;
```

| id | timestamp           | device_id | previous_state | new_state  | changed_by | reason                      | extra_data                          |
|----|---------------------|-----------|----------------|------------|------------|-----------------------------|-------------------------------------|
| 89 | 2025-12-07 15:45:00 | dev_042   | maintenance    | online     | system     | Auto-recovery completed     | {"recovery_time_sec": 1800}         |
| 88 | 2025-12-07 15:30:12 | dev_025   | online         | offline    | usr_123    | Emergency shutdown          | {"reason_code": "OVERHEAT"}         |
| 87 | 2025-12-07 14:15:00 | dev_042   | offline        | maintenance| usr_456    | Scheduled maintenance       | {"scheduled": true, "window": "14-16"} |
| 86 | 2025-12-07 13:00:00 | dev_018   | active         | idle       | system     | No activity for 30 min      | null                                |
| 85 | 2025-12-07 12:30:45 | dev_007   | error          | online     | system     | Error cleared, auto-restart | {"error_duration_min": 15}          |
| 84 | 2025-12-07 12:15:22 | dev_007   | online         | error      | system     | Connection timeout          | {"error_code": "E_TIMEOUT"}         |
| 83 | 2025-12-07 11:00:00 | dev_001   | idle           | active     | usr_789    | Manual activation           | null                                |
| 82 | 2025-12-07 10:30:15 | dev_033   | online         | offline    | system     | Heartbeat lost              | {"last_seen": "2025-12-07 10:25:00"}|
| 81 | 2025-12-07 09:15:00 | dev_012   | offline        | online     | system     | Boot sequence completed     | {"boot_time_sec": 45}               |
| 80 | 2025-12-07 08:00:00 | dev_025   | idle           | active     | system     | Scheduled task triggered    | {"task_id": "daily_sync"}           |
| 79 | 2025-12-06 18:30:00 | dev_042   | online         | offline    | usr_456    | End of business day         | {"scheduled_shutdown": true}        |
| 78 | 2025-12-06 16:45:30 | dev_018   | active         | idle       | system     | Task completed              | null                                |
| 77 | 2025-12-06 15:20:12 | dev_001   | maintenance    | online     | usr_123    | Maintenance completed       | {"duration_min": 45}                |

**Insights from this data:**
- `dev_042` had a maintenance window (offline → maintenance → online)
- `dev_025` had an emergency shutdown due to overheating
- `dev_007` experienced a temporary error but auto-recovered in 15 minutes
- `dev_033` lost heartbeat (potential network issue)
- Most state changes are automated by the system
- Device `dev_042` follows a schedule (shutdown at 18:30)

---

## 3. Job Outcomes (job_outcomes)

**Scenario:** Various jobs executed on devices over 2 days

```sql
SELECT * FROM job_outcomes ORDER BY timestamp DESC LIMIT 15;
```

| id  | timestamp           | job_id      | job_type         | device_id | status    | duration_ms | error_code | error_message        | retry_count | initiated_by |
|-----|---------------------|-------------|------------------|-----------|-----------|-------------|------------|----------------------|-------------|--------------|
| 156 | 2025-12-07 15:45:00 | job_1523    | firmware_update  | dev_042   | success   | 125000      | null       | null                 | 0           | usr_456      |
| 155 | 2025-12-07 15:40:30 | job_1522    | restart          | dev_025   | success   | 3500        | null       | null                 | 0           | usr_123      |
| 154 | 2025-12-07 15:30:15 | job_1521    | config_change    | dev_018   | failed    | 10000       | E_TIMEOUT  | Device not responding| 2           | usr_789      |
| 153 | 2025-12-07 14:20:00 | job_1520    | data_sync        | dev_033   | success   | 8900        | null       | null                 | 0           | system       |
| 152 | 2025-12-07 14:00:12 | job_1519    | health_check     | dev_001   | success   | 450         | null       | null                 | 0           | system       |
| 151 | 2025-12-07 13:45:30 | job_1518    | restart          | dev_007   | success   | 4200        | null       | null                 | 0           | system       |
| 150 | 2025-12-07 13:30:00 | job_1517    | firmware_update  | dev_025   | cancelled | 0           | E_CANCEL   | Cancelled by user    | 0           | usr_123      |
| 149 | 2025-12-07 12:15:45 | job_1516    | backup           | dev_042   | success   | 67000       | null       | null                 | 0           | system       |
| 148 | 2025-12-07 11:00:00 | job_1515    | config_change    | dev_012   | success   | 2300        | null       | null                 | 0           | usr_456      |
| 147 | 2025-12-07 10:30:20 | job_1514    | firmware_update  | dev_018   | timeout   | 300000      | E_TIMEOUT  | Update timed out     | 1           | usr_789      |
| 146 | 2025-12-07 09:15:00 | job_1513    | data_sync        | dev_007   | success   | 12500       | null       | null                 | 0           | system       |
| 145 | 2025-12-07 08:00:30 | job_1512    | health_check     | dev_033   | failed    | 5000        | E_NO_RESP  | No response          | 0           | system       |
| 144 | 2025-12-06 18:30:00 | job_1511    | backup           | dev_001   | success   | 45000       | null       | null                 | 0           | system       |
| 143 | 2025-12-06 16:45:15 | job_1510    | restart          | dev_025   | success   | 3800        | null       | null                 | 0           | usr_123      |

**Insights from this data:**
- Firmware updates take longest (125 seconds on dev_042)
- One firmware update timed out after 5 minutes (job_1514)
- Config change on dev_018 failed after 2 retries
- Most jobs are initiated by system (scheduled tasks)
- Restart jobs consistently take ~3-4 seconds
- Backup jobs take 45-67 seconds
- User usr_123 cancelled a firmware update midway

---

## 4. Error Logs (error_logs)

**Scenario:** Various errors encountered over 2 days

```sql
SELECT * FROM error_logs ORDER BY timestamp DESC LIMIT 12;
```

| id | timestamp           | category         | severity | error_code    | error_message                     | endpoint               | user_id | device_id | resolved |
|----|---------------------|------------------|----------|---------------|-----------------------------------|------------------------|---------|-----------|----------|
| 78 | 2025-12-07 15:30:45 | api              | warning  | E_RATE_LIMIT  | Rate limit exceeded for user      | /api/v1/devices        | usr_123 | null      | true     |
| 77 | 2025-12-07 14:15:20 | database         | error    | E_DB_TIMEOUT  | Query timeout after 5000ms        | /api/v1/devices        | usr_123 | null      | false    |
| 76 | 2025-12-07 13:45:12 | external_service | critical | E_MQTT_DOWN   | MQTT broker not responding        | null                   | null    | dev_033   | false    |
| 75 | 2025-12-07 12:50:30 | validation       | warning  | E_INVALID_ID  | Invalid device ID format          | /api/v1/devices/abc    | usr_456 | null      | true     |
| 74 | 2025-12-07 12:30:00 | api              | error    | E_AUTH_FAIL   | Invalid authentication token      | /api/v1/devices        | null    | null      | true     |
| 73 | 2025-12-07 11:20:45 | database         | warning  | E_SLOW_QUERY  | Query took 2500ms                 | /api/v1/analytics/jobs | usr_789 | null      | true     |
| 72 | 2025-12-07 10:15:30 | external_service | error    | E_TIMEOUT     | Device communication timeout      | null                   | null    | dev_018   | false    |
| 71 | 2025-12-07 09:00:12 | validation       | info     | E_MISSING_FIELD| Optional field 'description' missing| /api/v1/sites        | usr_456 | null      | true     |
| 70 | 2025-12-06 18:45:00 | api              | critical | E_SERVER_ERROR| Internal server error             | /api/v1/devices        | usr_123 | null      | false    |
| 69 | 2025-12-06 16:30:20 | database         | error    | E_CONN_LOST   | Database connection lost          | /api/v1/devices        | usr_789 | null      | true     |
| 68 | 2025-12-06 15:10:45 | external_service | warning  | E_RETRY_3X    | Service call failed after 3 retries| null                  | null    | dev_007   | true     |
| 67 | 2025-12-06 14:00:00 | validation       | warning  | E_DEPRECATED  | Using deprecated API version      | /api/v1/legacy/devices | usr_456 | null      | true     |

**Insights from this data:**
- MQTT broker issue (critical) affecting device dev_033 - unresolved
- Database timeout at 14:15:20 caused the 500 error we saw in API logs
- User usr_123 hit rate limit (making too many requests)
- One critical server error still unresolved from yesterday
- Most errors are resolved quickly
- External service errors (MQTT, device timeouts) are recurring issues

---

## 5. User Activities (user_activities)

**Scenario:** Frontend user interactions over a few hours

```sql
SELECT * FROM user_activities ORDER BY timestamp DESC LIMIT 20;
```

| id  | timestamp           | user_id | session_id   | activity_type | page_url         | element_id           | search_query      | duration_ms |
|-----|---------------------|---------|--------------|---------------|------------------|----------------------|-------------------|-------------|
| 345 | 2025-12-07 15:25:30 | usr_123 | sess_abc123  | click         | /devices         | add-device-btn       | null              | null        |
| 344 | 2025-12-07 15:24:45 | usr_123 | sess_abc123  | page_view     | /devices         | null                 | null              | 45000       |
| 343 | 2025-12-07 15:23:50 | usr_123 | sess_abc123  | search        | /devices         | device-search-input  | temperature sensor| null        |
| 342 | 2025-12-07 15:23:00 | usr_123 | sess_abc123  | page_view     | /dashboard       | null                 | null              | 50000       |
| 341 | 2025-12-07 15:20:15 | usr_456 | sess_def456  | form_submit   | /devices/edit/42 | device-edit-form     | null              | null        |
| 340 | 2025-12-07 15:19:30 | usr_456 | sess_def456  | click         | /devices/42      | edit-device-btn      | null              | null        |
| 339 | 2025-12-07 15:18:00 | usr_456 | sess_def456  | page_view     | /devices/42      | null                 | null              | 90000       |
| 338 | 2025-12-07 15:16:45 | usr_456 | sess_def456  | click         | /devices         | device-42-link       | null              | null        |
| 337 | 2025-12-07 15:15:30 | usr_789 | sess_ghi789  | page_view     | /analytics       | null                 | null              | 180000      |
| 336 | 2025-12-07 15:12:20 | usr_789 | sess_ghi789  | click         | /dashboard       | analytics-tab        | null              | null        |
| 335 | 2025-12-07 15:10:00 | usr_123 | sess_abc123  | search        | /devices         | device-search-input  | gateway           | null        |
| 334 | 2025-12-07 15:08:30 | usr_123 | sess_abc123  | click         | /devices         | filter-online        | null              | null        |
| 333 | 2025-12-07 15:05:15 | usr_456 | sess_def456  | page_view     | /devices         | null                 | null              | 135000      |
| 332 | 2025-12-07 15:02:00 | usr_456 | sess_def456  | click         | /dashboard       | devices-link         | null              | null        |
| 331 | 2025-12-07 15:00:00 | usr_456 | sess_def456  | page_view     | /dashboard       | null                 | null              | 120000      |
| 330 | 2025-12-07 14:55:30 | usr_789 | sess_ghi789  | search        | /sites           | site-search-input    | building A        | null        |
| 329 | 2025-12-07 14:52:00 | usr_789 | sess_ghi789  | page_view     | /sites           | null                 | null              | 210000      |
| 328 | 2025-12-07 14:48:45 | usr_123 | sess_abc123  | click         | /dashboard       | refresh-btn          | null              | null        |

**Insights from this data:**
- User usr_123 searched for "temperature sensor" and "gateway"
- User usr_456 edited device 42 (clicked edit, submitted form)
- User usr_789 spent 3 minutes on analytics page (longest duration)
- Most common activity: page_view (users browsing)
- /devices page is most visited
- Users spend 45-135 seconds per page on average
- Search queries show users looking for specific device types

---

## Summary: What You Learn from This Data

### Performance Patterns
- Average API response time: 100-300ms
- Slow queries: Some analytics queries take 2+ seconds
- Problem areas: Device communication timeouts

### User Behavior
- Most active times: 9 AM - 3 PM
- Most viewed pages: /devices, /dashboard
- Common searches: Temperature sensor, gateway, building A
- Average session duration: 5-10 minutes per user

### Device Health
- Most reliable: dev_001 (no failures)
- Problem devices: dev_018, dev_033 (frequent timeouts)
- Common state transitions: idle ↔ active, online → offline

### Job Success Rates
- Overall success rate: ~80%
- Firmware updates: 67% success (some timeouts)
- Config changes: 90% success
- Health checks: 95% success
- Restarts: 100% success

### Error Patterns
- Critical issues: 2 (MQTT broker, internal server error)
- Most common: Timeouts (database, device communication)
- Security: 1 authentication failure
- Rate limiting: User usr_123 making too many requests

---

## AI Opportunities

With this data collected, AI models are ready to train:

1. **Predict Device Failures**
   - Pattern: dev_033 goes offline → heartbeat lost → stays offline
   - AI can alert before device fails

2. **Optimize Job Scheduling**
   - Pattern: Firmware updates succeed 90% at night, 50% during business hours
   - AI can recommend best time to schedule updates

3. **Detect Anomalies**
   - Pattern: usr_123 rate limit + 20 requests in 5 min = possible bot
   - AI can detect unusual behavior

4. **Improve UX**
   - Pattern: Users search "temperature sensor" → click add → cancel form
   - AI suggests improving device creation UX

5. **Prevent Cascading Failures**
   - Pattern: Database timeout → API errors → job failures
   - AI can predict and prevent cascading issues

---

The document makes it very clear what value the analytics system provides!
