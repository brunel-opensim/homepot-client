# POS Management Guide

This guide covers managing sites, devices, and `job(s)` in your HOMEPOT POS ecosystem.

1. Job (The Goal): "Update all 50 devices at Site A."
2. Orchestrator (The Manager): Breaks the job down and finds the 50 target devices.
3. Push Notification (The Message): A specific signal sent to one specific Agent.
4. Agent (The Worker): Receives the notification, wakes up, and executes the task.

## Site Management

HOMEPOT comes pre-configured with **14 diverse sites** representing real-world scenarios:

### Viewing Sites

```bash
# List all sites
curl http://localhost:8000/sites

# Get specific site details
curl http://localhost:8000/sites/RESTAURANT_001

# Check site health
curl http://localhost:8000/sites/RESTAURANT_001/health
```

### Sample Pre-configured Sites

The system includes realistic sites like:
- McDonald's Downtown
- Starbucks Coffee #1
- Best Buy Electronics
- Walmart Supercenter
- Target Store #101
- Demo Restaurant

### Creating New Sites

```bash
# Create a new restaurant site
curl -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "PIZZA_HUT_001", 
    "name": "Pizza Hut Downtown",
    "location": "123 Main St, Downtown",
    "type": "restaurant"
  }'
```

### Site Health Monitoring

```bash
# Get detailed site health metrics
curl http://localhost:8000/sites/RESTAURANT_001/health

# Example response:
# {
#   "site_id": "RESTAURANT_001",
#   "status": "healthy",
#   "devices_total": 3,
#   "devices_healthy": 3,
#   "health_percentage": 100.0,
#   "last_updated": "2025-09-01T15:30:45.123456"
# }
```

## Device Management

Each site can have multiple POS devices (terminals, card readers, receipt printers).

### Device Registration

```bash
# Register a new POS terminal
curl -X POST http://localhost:8000/sites/RESTAURANT_001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "TERMINAL_001",
    "device_type": "pos_terminal",
    "location": "Counter 1"
  }'

# Register a card reader
curl -X POST http://localhost:8000/sites/RESTAURANT_001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "CARD_READER_001",
    "device_type": "card_reader",
    "location": "Counter 1"
  }'
```

### Device Health Monitoring

```bash
# Check device health
curl http://localhost:8000/devices/TERMINAL_001/health

# Submit health check results
curl -X POST http://localhost:8000/devices/TERMINAL_001/health \
  -H "Content-Type: application/json" \
  -d '{
    "status": "healthy",
    "cpu_usage": 15.2,
    "memory_usage": 42.8,
    "disk_usage": 68.5,
    "uptime": 86400
  }'
```

### Device Actions

```bash
# Restart a device remotely
curl -X POST http://localhost:8000/devices/TERMINAL_001/restart

# Response: {"message": "Restart command sent", "device_id": "TERMINAL_001"}
```

### Device Management Interface

The **Device Detail** page provides a comprehensive dashboard for managing individual devices.

#### Dashboard Features
- **Real-time Status**: Visual indicators for online/offline status and health metrics.
- **System Stats**: Live monitoring of CPU, Memory, and Disk usage.
- **Device Information**: Detailed view of IP address, MAC address, firmware version, and last seen timestamp.

#### Direct Connect (Remote Shell)
Establish a secure, simulated remote shell session directly from the browser:
- **Access**: Click the "Direct Connect" widget to open the terminal.
- **Capabilities**: Execute commands like `status`, `reboot`, `logs`, and `help`.
- **Security**: Simulated TLS 1.3 secure channel.

#### Device Actions
Perform critical maintenance tasks with immediate feedback via toast notifications:
- **Refresh Kiosk**: Reload the kiosk application.
- **Update Configurations**: Push the latest settings to the device.
- **Request Status**: Force a status update.
- **Fetch Apps**: Retrieve installed application list.

#### Audit & History
- **Command History**: Track all administrative actions performed on the device.
- **Audit Log**: View detailed system events and configuration changes.
- **Logs**: Access recent device logs for troubleshooting.

## Job Management

Deploy configuration updates and maintenance tasks across your POS network.

### Creating Jobs

```bash
# Create a software update job
curl -X POST http://localhost:8000/sites/RESTAURANT_001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "software_update",
    "priority": "high",
    "config": {
      "update_version": "2.1.4",
      "restart_required": true
    }
  }'

# Create a configuration update job
curl -X POST http://localhost:8000/sites/RESTAURANT_001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "config_update",
    "priority": "medium",
    "config": {
      "payment_timeout": 30,
      "receipt_printer": true
    }
  }'
```

### Monitoring Job Progress

```bash
# Get job status
curl http://localhost:8000/jobs/{job_id}

# Example response:
# {
#   "job_id": "job_12345",
#   "site_id": "RESTAURANT_001",
#   "job_type": "software_update",
#   "status": "running",
#   "progress": 75,
#   "created_at": "2025-09-01T15:00:00",
#   "estimated_completion": "2025-09-01T16:00:00"
# }
```

### Job Types

| Job Type | Description | Typical Duration |
|----------|-------------|------------------|
| `software_update` | Update POS terminal software | 10-15 minutes |
| `config_update` | Update device configuration | 2-5 minutes |
| `health_check` | Perform comprehensive health check | 1-2 minutes |
| `restart` | Restart device or system | 1-3 minutes |
| `maintenance` | Scheduled maintenance tasks | Variable |

## Common Workflows

### Adding a New Store Location

```bash
# 1. Create the site
curl -X POST http://localhost:8000/sites \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "STORE_NEW_001",
    "name": "New Store Location",
    "location": "456 Commerce St",
    "type": "retail"
  }'

# 2. Register POS terminals
curl -X POST http://localhost:8000/sites/STORE_NEW_001/devices \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "TERMINAL_NEW_001",
    "device_type": "pos_terminal",
    "location": "Checkout 1"
  }'

# 3. Deploy initial configuration
curl -X POST http://localhost:8000/sites/STORE_NEW_001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "config_update",
    "priority": "high",
    "config": {
      "store_id": "STORE_NEW_001",
      "tax_rate": 0.08,
      "receipt_footer": "Thank you for shopping!"
    }
  }'
```

### Rolling Update Across Sites

```bash
# Deploy update to multiple sites
for site in RESTAURANT_001 RESTAURANT_002 STORE_001; do
  curl -X POST http://localhost:8000/sites/$site/jobs \
    -H "Content-Type: application/json" \
    -d '{
      "job_type": "software_update",
      "priority": "high",
      "config": {
        "update_version": "2.1.4",
        "restart_required": true
      }
    }'
done
```

## Best Practices

### Site Organization
- Use clear, descriptive site IDs (e.g., `RESTAURANT_DOWNTOWN_001`)
- Include location information in site names
- Group sites by type for easier management

### Device Naming
- Follow consistent naming conventions (e.g., `TERMINAL_001`, `CARD_READER_001`)
- Include location context for larger sites
- Use device type prefixes for clarity

### Job Scheduling
- Schedule maintenance during off-peak hours
- Use appropriate priority levels
- Monitor job progress and handle failures
- Test updates in development environments first

### Health Monitoring
- Set up regular health checks
- Monitor key metrics (CPU, memory, disk usage)
- Set up alerts for critical issues
- Maintain historical health data

---

*Next: Learn about [Real-time Dashboard](real-time-dashboard.md) features for monitoring your POS ecosystem.*
