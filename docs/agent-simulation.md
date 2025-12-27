# Agent Simulation Guide

Learn how HOMEPOT's realistic POS agent simulators work and how to manage them effectively.

## Overview

HOMEPOT includes **23+ realistic POS agent simulators** that behave like real payment terminals, providing a comprehensive testing and demonstration environment.

## Agent State Machine

Each agent follows a realistic lifecycle with the following states:

```
    ┌─────────┐    Update     ┌─────────────┐
    │  IDLE   │  Available    │ DOWNLOADING │
    │ (Ready) │──────────────▶│  (Busy)     │
    └─────────┘               └─────────────┘
         ▲                           │
         │                           ▼
    ┌─────────────┐              ┌─────────┐
    │ HEALTH_CHECK│              │UPDATING │
    │  (Testing)  │◀─────────────│(Installing)
    └─────────────┘              └─────────┘
         ▲                           │
         │                           ▼
    ┌─────────────┐              ┌─────────────┐
    │   READY     │              │ RESTARTING  │
    │ (Complete)  │◀─────────────│ (Rebooting) │
    └─────────────┘              └─────────────┘
```

### State Descriptions

- **IDLE**: Ready for transactions and new jobs
- **DOWNLOADING**: Receiving software updates or configuration
- **UPDATING**: Installing new software or applying configuration
- **RESTARTING**: Rebooting after updates
- **HEALTH_CHECK**: Performing system diagnostics
- **READY**: Operational and healthy

## Realistic Data Simulation

The simulation engine (`POSAgentSimulator`) has been enhanced to provide **stateful, cumulative data generation**, ensuring that metrics behave realistically over time rather than being random snapshots.

### Key Features

1.  **Cumulative Metrics**:
    *   **Transactions Today**: Increments steadily throughout the day.
    *   **Transaction Volume**: Grows cumulatively based on transaction count.
    *   **Uptime**: Increments by the check interval (2 seconds) on every heartbeat.

2.  **High-Frequency Updates**:
    *   Agents perform health checks every **2 seconds** (previously 5s).
    *   This ensures the frontend dashboard (`/data-collection`) feels alive and responsive.

3.  **Simulated Characteristics**:
    *   **Network Latency**: Varies between 10ms and 150ms.
    *   **Error Rate**: Simulates occasional spikes (0.0% - 2.0%).
    *   **Resource Usage**: CPU, Memory, and Disk usage fluctuate within realistic bounds.

## Managing Agents

### Viewing All Agents

```bash
# List all active agents
curl http://localhost:8000/agents

# Response: Array of agent objects
# [
#   {
#     "device_id": "POS_TERMINAL_001",
#     "site_id": "RESTAURANT_001",
#     "status": "idle",
#     "state": "ready",
#     "last_heartbeat": "2025-09-01T15:45:30"
#   },
#   ...
# ]
```

### Agent Details

```bash
# Get specific agent information
curl http://localhost:8000/agents/POS_TERMINAL_001

# Detailed response:
# {
#   "device_id": "POS_TERMINAL_001",
#   "site_id": "RESTAURANT_001",
#   "device_type": "pos_terminal",
#   "status": "idle",
#   "state": "ready",
#   "version": "2.1.3",
#   "last_heartbeat": "2025-09-01T15:45:30",
#   "health_metrics": {
#     "cpu_usage": 15.2,
#     "memory_usage": 42.8,
#     "disk_usage": 68.5,
#     "temperature": 45.0,
#     "uptime": 86400
#   },
#   "configuration": {
#     "payment_timeout": 30,
#     "receipt_printer": true,
#     "card_reader_enabled": true
#   }
# }
```

## Agent Communication

### Push Notifications

Send real-time notifications to agents:

```bash
# Send configuration update notification
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Configuration update available",
    "priority": "high",
    "action": "update_config",
    "config_version": "2.1.4"
  }'

# Send maintenance notification
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Scheduled maintenance in 30 minutes",
    "priority": "medium",
    "action": "prepare_maintenance"
  }'
```

### Health Monitoring

```bash
# Get current health status
curl http://localhost:8000/devices/POS_TERMINAL_001/health

# Force health check
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/health \
  -H "Content-Type: application/json" \
  -d '{
    "force_check": true
  }'
```

## Agent Behaviors

### Realistic Simulation Features

1. **Variable Processing Times**: Updates take realistic time (5-15 minutes)
2. **Health Fluctuations**: CPU, memory, and disk usage vary naturally
3. **Occasional Failures**: Simulated network timeouts and errors
4. **Recovery Procedures**: Automatic restart and recovery attempts
5. **State Persistence**: Agents remember their state across restarts

### Health Metrics Simulation

Agents simulate realistic hardware metrics:

```json
{
  "health_metrics": {
    "cpu_usage": 15.2,        // 0-100%, varies with load
    "memory_usage": 42.8,     // 0-100%, gradually increases
    "disk_usage": 68.5,       // 0-100%, slowly increases over time
    "temperature": 45.0,      // Celsius, varies with usage
    "uptime": 86400,          // Seconds since last restart
    "network_latency": 23.4,  // Milliseconds to server
    "transaction_count": 1247 // Daily transaction counter
  }
}
```

### Configuration Updates

Agents can receive various configuration types:

```bash
# Payment configuration
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "payment_timeout": 45,
      "max_transaction_amount": 10000,
      "tip_enabled": true,
      "receipt_options": ["email", "sms", "print"]
    }
  }'

# Display configuration
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "display_brightness": 80,
      "screensaver_timeout": 300,
      "welcome_message": "Welcome to HOMEPOT Store!",
      "language": "en-US"
    }
  }'
```

## Agent Types

### POS Terminals

Primary payment processing devices:

- **Transaction Processing**: Simulates payment transactions
- **Card Reader Integration**: Chip, PIN, and contactless payments
- **Receipt Printing**: Configurable receipt options
- **Display Management**: Customer-facing display simulation

### Card Readers

Dedicated payment processing devices:

- **EMV Chip Processing**: Secure chip card transactions
- **Contactless Payments**: NFC and mobile payment simulation
- **PIN Entry**: Secure PIN verification simulation
- **Magnetic Stripe**: Legacy card support

### Receipt Printers

Dedicated printing devices:

- **Receipt Formatting**: Customizable receipt templates
- **Paper Management**: Paper level monitoring simulation
- **Print Quality**: Simulated print quality issues
- **Connectivity**: USB, Ethernet, and wireless connections

## Troubleshooting Agents

### Common Agent Issues

```bash
# Agent not responding
curl http://localhost:8000/agents/POS_TERMINAL_001

# If no response, check if agent is registered
curl http://localhost:8000/sites/RESTAURANT_001/devices

# Restart unresponsive agent
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/restart
```

### Agent Recovery

```bash
# Force agent restart
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/restart

# Reset agent configuration
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reset_config",
    "force": true
  }'

# Reinitialize agent
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reinitialize",
    "backup_data": true
  }'
```

### Health Diagnostics

```bash
# Run comprehensive diagnostics
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/health \
  -H "Content-Type: application/json" \
  -d '{
    "diagnostic_mode": "comprehensive",
    "include_logs": true,
    "test_components": ["payment", "printer", "display", "network"]
  }'
```

## Advanced Agent Features

### Batch Operations

```bash
# Update multiple agents at once
for device_id in POS_TERMINAL_001 POS_TERMINAL_002 CARD_READER_001; do
  curl -X POST http://localhost:8000/agents/$device_id/push \
    -H "Content-Type: application/json" \
    -d '{
      "message": "Security update available",
      "priority": "critical",
      "config_version": "2.1.5"
    }'
done
```

### Agent Groups

Organize agents for easier management:

```bash
# Get agents by site
curl "http://localhost:8000/agents?site_id=RESTAURANT_001"

# Get agents by type
curl "http://localhost:8000/agents?device_type=pos_terminal"

# Get agents by status
curl "http://localhost:8000/agents?status=idle"
```

### Performance Monitoring

```bash
# Get agent performance metrics
curl "http://localhost:8000/agents/POS_TERMINAL_001/metrics?period=24h"

# Monitor transaction throughput
curl "http://localhost:8000/agents/POS_TERMINAL_001/transactions?period=1d"

# Check error rates
curl "http://localhost:8000/agents/POS_TERMINAL_001/errors?period=7d"
```

## Best Practices

### Agent Management

- Monitor agent health regularly
- Schedule updates during off-peak hours
- Use staged rollouts for critical updates
- Maintain agent configuration backups
- Set up automated health check alerts

### Performance Optimization

- Balance load across multiple agents
- Monitor resource usage trends
- Plan capacity based on transaction volume
- Optimize configuration for hardware capabilities
- Regular maintenance and updates

### Security Considerations

- Use secure communication channels
- Regularly update agent software
- Monitor for unauthorized access attempts
- Implement proper authentication
- Log all administrative actions

---

*Next: Learn about [Audit & Compliance](audit-compliance.md) features for enterprise logging and reporting.*
