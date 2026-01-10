# Real-time Dashboard Guide

Learn how to use HOMEPOT's real-time monitoring dashboard with WebSocket updates and live data visualization.

## Dashboard Overview

Access the dashboard at **[http://localhost:8000](http://localhost:8000)** to monitor your entire POS ecosystem in real-time.

### Key Features

- **Live Status Indicators**: Real-time site health with color-coded status
- **Health Metrics**: Site health percentages updating every few seconds
- **WebSocket Updates**: Instant updates without page refresh
- **Quick Actions**: Direct links to site details and management
- **Agent Monitoring**: Live view of all active POS terminals

## Dashboard Components

### Site Health Overview

The main dashboard displays:

```
┌─────────────────────────────────────────┐
│ HOMEPOT POS Management Dashboard        │
├─────────────────────────────────────────┤
│ ● RESTAURANT_001    [████████░░] 85%    │
│ ● STARBUCKS_001     [██████████] 100%   │
│ ● BESTBUY_001       [██████░░░░] 62%    │
│ ● WALMART_001       [████████░░] 78%    │
└─────────────────────────────────────────┘
```

### Status Color Codes

- **Green**: Healthy (80-100% health)
- **Yellow**: Warning (50-79% health)
- **Red**: Critical (0-49% health)
- **Gray**: Offline or no data

## WebSocket Integration

### Real-time Updates

The dashboard automatically connects to WebSocket endpoints for live updates:

```javascript
// Automatic WebSocket connection (built into dashboard)
const ws = new WebSocket('ws://localhost:8000/ws/status');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    updateDashboard(data);
};
```

### Update Frequency

- **Site Health**: Updates every 30 seconds
- **Agent Status**: Updates every 10 seconds
- **Job Progress**: Updates every 5 seconds
- **Audit Events**: Real-time as they occur

## Monitoring Endpoints

### System Health

```bash
# Overall system health
curl http://localhost:8000/health

# Response:
# {
#   "status": "healthy",
#   "client_connected": true,
#   "active_agents": 23,
#   "total_sites": 14,
#   "healthy_sites": 12,
#   "version": "0.1.0"
# }
```

### Site Monitoring

```bash
# Get all sites with health status
curl http://localhost:8000/sites

# Get specific site health
curl http://localhost:8000/sites/RESTAURANT_001/health

# Response:
# {
#   "site_id": "RESTAURANT_001",
#   "status": "healthy",
#   "devices_total": 3,
#   "devices_healthy": 3,
#   "health_percentage": 100.0,
#   "last_heartbeat": "2025-09-01T15:45:30",
#   "uptime": 86400
# }
```

### Agent Monitoring

```bash
# List all active agents
curl http://localhost:8000/agents

# Get specific agent details
curl http://localhost:8000/agents/POS_TERMINAL_001

# Response:
# {
#   "device_id": "POS_TERMINAL_001",
#   "site_id": "RESTAURANT_001",
#   "status": "idle",
#   "state": "ready",
#   "last_heartbeat": "2025-09-01T15:45:30",
#   "health_metrics": {
#     "cpu_usage": 15.2,
#     "memory_usage": 42.8,
#     "disk_usage": 68.5,
#     "temperature": 45.0
#   }
# }
```

## Dashboard Features

### Interactive Elements

1. **Site Cards**: Click to view detailed site information
2. **Health Bars**: Hover for detailed metrics tooltip
3. **Status Indicators**: Click for recent events and actions
4. **Agent List**: Expandable view of all POS terminals

### Active Alerts Ticker

A real-time ticker at the top of the dashboard displaying critical system alerts.

- **Auto-Rotation**: Cycles through active alerts automatically.
- **Interaction**:
    - **Pause**: Hovering over the ticker pauses rotation.
    - **Dismiss**: Users can dismiss specific alerts. Dismissed alerts are persisted in local storage and won't reappear.
    - **View All**: A "View All" button opens a dialog showing all active alerts in a list.
    - **Navigation**: Clicking an alert card navigates to the specific device or site details.

### Navigation

- **Dashboard Home**: Overview of all sites and agents
- **Site Details**: Drill down into specific site information
- **Agent Management**: Individual agent monitoring and control
- **Job Queue**: Active and completed job monitoring
- **Audit Trail**: Real-time event logging

### Quick Actions

Available directly from the dashboard:

```bash
# Restart an agent from the dashboard
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/restart

# Trigger health check
curl -X POST http://localhost:8000/devices/POS_TERMINAL_001/health

# Send push notification
curl -X POST http://localhost:8000/agents/POS_TERMINAL_001/push \
  -H "Content-Type: application/json" \
  -d '{
    "message": "System maintenance in 30 minutes",
    "priority": "high"
  }'
```

## Advanced Features

### Custom Dashboard Views

The dashboard supports filtered views:

- **By Site Type**: Restaurants, retail stores, etc.
- **By Health Status**: Healthy, warning, critical
- **By Agent State**: Idle, busy, updating, offline
- **By Job Status**: Running, completed, failed

### Alerts and Notifications

Configure real-time alerts:

```javascript
// Dashboard alert configuration
const alertConfig = {
    healthThreshold: 50,  // Alert if health drops below 50%
    offlineTimeout: 300,  // Alert if offline for 5 minutes
    jobFailures: true,    // Alert on job failures
    securityEvents: true  // Alert on security events
};
```

### Historical Data

Access historical monitoring data:

```bash
# Get historical health data
curl "http://localhost:8000/sites/RESTAURANT_001/health?period=24h"

# Get agent performance history
curl "http://localhost:8000/agents/POS_TERMINAL_001/metrics?period=1d"
```

## Dashboard Customization

### Layout Options

- **Grid View**: Card-based layout for site overview
- **List View**: Detailed tabular view with metrics
- **Compact View**: Dense view for large deployments
- **Map View**: Geographic visualization (if location data available)

### Refresh Settings

```javascript
// Configure update intervals
const dashboardConfig = {
    siteHealthInterval: 30000,    // 30 seconds
    agentStatusInterval: 10000,   // 10 seconds
    jobProgressInterval: 5000,    // 5 seconds
    auditEventStream: true        // Real-time
};
```

## Troubleshooting Dashboard Issues

### WebSocket Connection Problems

```bash
# Check WebSocket endpoint
curl -H "Upgrade: websocket" \
     -H "Connection: Upgrade" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8000/ws/status
```

### Dashboard Not Loading

```bash
# Verify server is running
curl http://localhost:8000/health

# Check browser console for JavaScript errors
# Open browser DevTools (F12) and check Console tab
```

### Data Not Updating

```bash
# Verify WebSocket connection in browser DevTools
# Network tab should show WebSocket connection as "101 Switching Protocols"

# Check server logs for WebSocket events
tail -f logs/backend.out | grep -i websocket
```

## Performance Optimization

### Large Deployments

For deployments with 100+ sites:

- Enable pagination in site views
- Use data aggregation for overview metrics
- Implement client-side caching
- Consider WebSocket message throttling

### Network Considerations

- Dashboard works over LAN and WAN
- WebSocket fallback to polling for restrictive networks
- Configurable update intervals to reduce bandwidth
- Compression for large data sets

---

*Next: Learn about [Agent Simulation](agent-simulation.md) to understand how POS terminals behave in the system.*
