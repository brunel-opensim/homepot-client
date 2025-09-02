# Audit & Compliance Guide

HOMEPOT provides enterprise-grade audit logging with comprehensive event tracking for compliance and security monitoring.

## Overview

The audit system tracks **20+ event types** across all system operations, providing a complete trail for compliance, security analysis, and operational monitoring.

## Audit Event Categories

### Security Events
- Login attempts and authentication
- API access and authorization
- Unauthorized access attempts
- Security policy violations
- Certificate and encryption events

### User Actions
- User login/logout events
- Profile changes and updates
- Administrative actions
- Permission changes
- Account creation/deletion

### Site Management
- Site creation and updates
- Site configuration changes
- Site deletion and archiving
- Location updates
- Site health status changes

### Device Management
- Device registration and removal
- Device status changes
- Health check results
- Configuration updates
- Firmware/software updates

### Job Management
- Job creation and scheduling
- Job execution progress
- Job completion/failure
- Queue management
- Priority changes

### System Events
- System startup/shutdown
- Service restarts
- Database operations
- Backup operations
- Error conditions

## Viewing Audit Events

### Recent Events

```bash
# Get recent audit events (default: last 100)
curl http://localhost:8000/audit/events

# Get events with pagination
curl "http://localhost:8000/audit/events?limit=50&offset=0"

# Filter by category
curl "http://localhost:8000/audit/events?category=security"

# Filter by event type
curl "http://localhost:8000/audit/events?event_type=device_registered"
```

### Example Audit Event

```json
{
  "id": 1247,
  "event_type": "device_registered",
  "category": "device_management",
  "description": "Device POS_TERMINAL_001 registered at RESTAURANT_001",
  "metadata": {
    "site_id": "RESTAURANT_001",
    "device_id": "POS_TERMINAL_001",
    "device_type": "pos_terminal",
    "operator_id": "admin",
    "location": "Counter 1"
  },
  "timestamp": "2025-09-01T15:30:45.123456",
  "ip_address": "192.168.1.100",
  "user_agent": "curl/7.68.0",
  "session_id": "sess_abc123",
  "severity": "info"
}
```

### Audit Statistics

```bash
# Get overall audit statistics
curl http://localhost:8000/audit/statistics

# Response:
# {
#   "total_events": 15247,
#   "events_by_category": {
#     "system_events": 3421,
#     "device_management": 4523,
#     "user_actions": 2134,
#     "security_events": 1876,
#     "site_management": 1987,
#     "job_management": 1306
#   },
#   "events_by_severity": {
#     "info": 12456,
#     "warning": 2134,
#     "error": 456,
#     "critical": 201
#   },
#   "recent_activity": {
#     "last_hour": 45,
#     "last_24_hours": 1247,
#     "last_week": 8765
#   }
# }
```

## Event Types Reference

### Security Events

| Event Type | Description | Severity |
|------------|-------------|----------|
| `login_attempt` | User login attempt | info |
| `login_success` | Successful login | info |
| `login_failed` | Failed login attempt | warning |
| `unauthorized_access` | Unauthorized access attempt | critical |
| `api_access` | API endpoint access | info |
| `permission_denied` | Access denied | warning |

### Device Management Events

| Event Type | Description | Severity |
|------------|-------------|----------|
| `device_registered` | New device registration | info |
| `device_updated` | Device configuration update | info |
| `device_health_check` | Health check performed | info |
| `device_offline` | Device went offline | warning |
| `device_error` | Device error occurred | error |
| `device_restart` | Device restart initiated | info |

### Job Management Events

| Event Type | Description | Severity |
|------------|-------------|----------|
| `job_created` | New job created | info |
| `job_started` | Job execution started | info |
| `job_completed` | Job completed successfully | info |
| `job_failed` | Job execution failed | error |
| `job_cancelled` | Job was cancelled | warning |
| `job_timeout` | Job timed out | error |

## Compliance Features

### Regulatory Compliance

HOMEPOT audit logging supports various compliance frameworks:

- **PCI DSS**: Payment card industry compliance
- **SOX**: Sarbanes-Oxley financial reporting
- **GDPR**: General Data Protection Regulation
- **HIPAA**: Health information privacy (if applicable)
- **SOC 2**: Service organization controls

### Data Retention

```bash
# Configure retention policies
curl -X POST http://localhost:8000/audit/retention \
  -H "Content-Type: application/json" \
  -d '{
    "retention_days": 2555,  // 7 years for financial compliance
    "archive_after_days": 365,
    "compress_archives": true,
    "encryption_required": true
  }'
```

### Audit Reports

```bash
# Generate compliance report
curl -X POST http://localhost:8000/audit/reports \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "compliance",
    "period": {
      "start": "2025-01-01T00:00:00Z",
      "end": "2025-09-01T23:59:59Z"
    },
    "categories": ["security_events", "user_actions"],
    "format": "json"
  }'
```

## Real-time Monitoring

### Event Streaming

Monitor audit events in real-time:

```bash
# Stream recent events (requires WebSocket or SSE client)
curl -N -H "Accept: text/event-stream" \
  http://localhost:8000/audit/events/stream
```

### Alert Configuration

```bash
# Set up security alerts
curl -X POST http://localhost:8000/audit/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "security_breach",
    "event_types": ["unauthorized_access", "login_failed"],
    "threshold": 5,
    "time_window": 300,  // 5 minutes
    "notification": {
      "email": "security@company.com",
      "webhook": "https://alerts.company.com/webhook"
    }
  }'
```

## Audit Query Examples

### Security Analysis

```bash
# Find failed login attempts in the last 24 hours
curl "http://localhost:8000/audit/events?event_type=login_failed&since=24h"

# Look for unauthorized access attempts
curl "http://localhost:8000/audit/events?category=security&severity=critical"

# Check API access patterns
curl "http://localhost:8000/audit/events?event_type=api_access&limit=1000"
```

### Operational Analysis

```bash
# Device performance issues
curl "http://localhost:8000/audit/events?category=device_management&severity=error"

# Job failure analysis
curl "http://localhost:8000/audit/events?event_type=job_failed&since=7d"

# System stability monitoring
curl "http://localhost:8000/audit/events?category=system_events&since=24h"
```

### User Activity Tracking

```bash
# Track user actions for specific user
curl "http://localhost:8000/audit/events?category=user_actions&metadata.user_id=admin"

# Monitor administrative actions
curl "http://localhost:8000/audit/events?event_type=admin_action&since=30d"

# Review configuration changes
curl "http://localhost:8000/audit/events?event_type=config_updated&since=7d"
```

## Advanced Audit Features

### Custom Event Types

```bash
# Log custom business events
curl -X POST http://localhost:8000/audit/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "transaction_processed",
    "category": "business_events",
    "description": "Payment transaction completed",
    "metadata": {
      "transaction_id": "txn_12345",
      "amount": 45.67,
      "payment_method": "credit_card",
      "merchant_id": "RESTAURANT_001"
    },
    "severity": "info"
  }'
```

### Audit Data Export

```bash
# Export audit data for external analysis
curl -X POST http://localhost:8000/audit/export \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "period": {
      "start": "2025-08-01T00:00:00Z",
      "end": "2025-09-01T23:59:59Z"
    },
    "categories": ["all"],
    "include_metadata": true,
    "compress": true
  }'
```

### Integration with SIEM

```bash
# Configure SIEM integration
curl -X POST http://localhost:8000/audit/integrations \
  -H "Content-Type: application/json" \
  -d '{
    "type": "syslog",
    "destination": "siem.company.com:514",
    "format": "CEF",
    "filter": {
      "severities": ["warning", "error", "critical"],
      "categories": ["security_events", "system_events"]
    }
  }'
```

## Best Practices

### Audit Strategy

- Enable comprehensive logging for all critical operations
- Set appropriate retention periods based on compliance requirements
- Regular review of audit logs for security analysis
- Implement automated alerting for critical events
- Maintain audit log integrity and tamper protection

### Performance Considerations

- Monitor audit log storage growth
- Implement log rotation and archiving
- Use efficient queries for large datasets
- Consider audit log database optimization
- Balance detail level with performance impact

### Security Measures

- Protect audit logs from unauthorized access
- Implement audit log encryption
- Regular backup of audit data
- Monitor audit system health
- Secure audit data transmission

## Troubleshooting

### Missing Events

```bash
# Check audit service status
curl http://localhost:8000/audit/status

# Verify event logging configuration
curl http://localhost:8000/audit/config

# Test event logging
curl -X POST http://localhost:8000/audit/test \
  -H "Content-Type: application/json" \
  -d '{"test_event": true}'
```

### Performance Issues

```bash
# Check audit database performance
curl http://localhost:8000/audit/performance

# View audit log statistics
curl http://localhost:8000/audit/statistics/detailed

# Optimize audit queries
curl http://localhost:8000/audit/optimize
```

---

*Next: Learn about [Development Guide](development-guide.md) for testing, code quality, and contributing to HOMEPOT.*
