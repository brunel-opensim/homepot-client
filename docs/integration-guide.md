# HOMEPOT Client - Complete Integration Guide

> **A comprehensive guide to the HOMEPOT Client application - Backend-Frontend integration with multi-platform push notifications**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Getting Started](#getting-started)
4. [Development Guide](#development-guide)
5. [API Reference](#api-reference)
6. [Frontend Guide](#frontend-guide)
7. [Push Notifications](#push-notifications)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### What is HOMEPOT Client?

HOMEPOT Client is a modern, full-stack web application for managing IoT devices across multiple sites with comprehensive push notification support. It enables organizations to:

- **Manage Sites & Devices** - Organize IoT devices across multiple physical locations
- **Schedule Jobs** - Automate device tasks and monitor execution
- **Send Notifications** - Push notifications across 5 platforms (FCM, WNS, APNs, Web Push, MQTT)
- **Monitor Health** - Real-time device status and health metrics
- **Simulate Agents** - Test device behaviors without physical hardware
- **Analyze Data** - Insights through dashboards and reports

### Technology Stack

**Backend:**
- **Framework:** FastAPI 0.104+ (Python 3.12+)
- **Database:** SQLite (development) / PostgreSQL (production)
- **ORM:** SQLAlchemy 2.0+
- **Authentication:** JWT (JSON Web Tokens)
- **Real-time:** WebSocket support
- **Testing:** pytest with 85%+ coverage

**Frontend:**
- **Framework:** React 19.1.1
- **Build Tool:** Vite 5.0.3
- **Styling:** Tailwind CSS 3.4+
- **UI Components:** shadcn/ui
- **HTTP Client:** Axios
- **State Management:** Context API (Zustand recommended for scaling)
- **Testing:** Vitest + Playwright

**Push Notification Platforms:**
1. **FCM** (Firebase Cloud Messaging) - Android, iOS, Web
2. **WNS** (Windows Notification Service) - Windows devices
3. **APNs** (Apple Push Notification service) - iOS, macOS
4. **Web Push** - Browser notifications with VAPID
5. **MQTT** - IoT device messaging

### Project Structure

```
homepot-client/
├── backend/                    # FastAPI backend
│   ├── homepot/
│   │   ├── app/
│   │   │   ├── api/           # API endpoints
│   │   │   │   └── API_v1/
│   │   │   │       ├── Api.py                    # Router configuration
│   │   │   │       └── Endpoints/
│   │   │   │           ├── PushNotificationEndpoint.py
│   │   │   │           ├── SitesEndpoint.py
│   │   │   │           ├── DevicesEndpoint.py
│   │   │   │           ├── JobsEndpoint.py
│   │   │   │           └── ...
│   │   │   └── services/      # Business logic
│   │   │       └── push_notifications/
│   │   │           ├── factory.py
│   │   │           ├── fcm_linux.py
│   │   │           ├── apns_apple.py
│   │   │           ├── web_push.py
│   │   │           └── ...
│   │   ├── config.py          # Configuration (Pydantic)
│   │   ├── database.py        # Database setup
│   │   ├── models.py          # SQLAlchemy models
│   │   └── main.py            # Application entry point
│   ├── tests/                 # Backend tests
│   ├── requirements.txt       # Python dependencies
│   └── pyproject.toml         # Project metadata
│
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── services/
│   │   │   ├── api.js                    # Axios API client
│   │   │   └── pushNotifications.js      # Push manager
│   │   ├── components/
│   │   │   └── NotificationSettings.jsx  # Push settings UI
│   │   ├── pages/             # Page components (to be added)
│   │   ├── layouts/           # Layout components (to be added)
│   │   └── App.jsx            # Main app component
│   ├── public/
│   │   └── sw.js             # Service Worker for Web Push
│   ├── tests/                # Frontend tests
│   ├── package.json          # Node dependencies
│   └── vite.config.js        # Vite configuration
│
├── scripts/
│   ├── test-integration.sh   # ONE-COMMAND setup script
│   └── README.md             # Scripts documentation
│
├── docs/                      # Documentation
│   ├── engineering-todo.md   # Engineering task list
│   ├── api-reference.md      # API documentation
│   └── ...
│
├── data/                      # SQLite database & backups
├── docker-compose.yml        # Docker orchestration
└── README.md                 # Project README
```

---

## Architecture

### System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         HOMEPOT Client                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌───────────────────┐              ┌───────────────────┐      │
│  │   React Frontend  │◄────────────►│  FastAPI Backend  │      │
│  │                   │   REST API   │                   │      │
│  │  - Pages & UI     │   WebSocket  │  - Endpoints      │      │
│  │  - State Mgmt     │              │  - Business Logic │      │
│  │  - API Client     │              │  - Database       │      │
│  │  - Push Manager   │              │  - Auth (JWT)     │      │
│  └───────────────────┘              └───────────────────┘      │
│           │                                   │                │
│           │ Service Worker                    │ Push Factory   │
│           ▼                                   ▼                │
│  ┌───────────────────┐              ┌───────────────────┐      │
│  │   Web Push API    │              │ Push Platforms    │      │
│  │   (Browser)       │              │ - FCM             │      │
│  └───────────────────┘              │ - WNS             │      │
│                                     │ - APNs            │      │
│                                     │ - Web Push        │      │
│                                     │ - MQTT            │      │
│                                     └───────────────────┘      │
│                                               │                │
└───────────────────────────────────────────────┼────────────────┘
                                                │
                                                ▼
                                      ┌───────────────────┐
                                      │  External Services│
                                      │  - Firebase       │
                                      │  - Apple APNs     │
                                      │  - MQTT Broker    │
                                      └───────────────────┘
```

### Data Flow

**1. User Authentication:**
```
Frontend → POST /api/v1/auth/login → Backend validates → Returns JWT token
Frontend stores token → Includes in all subsequent requests
```

**2. Device Management:**
```
User creates device → POST /api/v1/devices → Backend saves to DB
Backend subscribes to push platform → Returns device info
Frontend displays device → WebSocket updates status in real-time
```

**3. Push Notification Flow:**
```
User composes notification → Frontend sends to /api/v1/push/send
Backend validates → Determines platform (FCM/WNS/APNs/WebPush/MQTT)
Platform-specific service formats message → Sends to platform API
Platform delivers to device → Audit log created
```

**4. Real-time Updates:**
```
Backend detects device status change → Emits WebSocket event
Frontend WebSocket listener receives → Updates UI state
User sees updated status without refresh
```

### Database Schema

**Core Tables:**

```sql
-- Users (authentication)
users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE,
  username VARCHAR UNIQUE,
  hashed_password VARCHAR,
  is_active BOOLEAN,
  created_at TIMESTAMP
)

-- Sites (physical locations)
sites (
  id UUID PRIMARY KEY,
  name VARCHAR,
  location VARCHAR,
  description TEXT,
  created_at TIMESTAMP
)

-- Devices (IoT devices)
devices (
  id UUID PRIMARY KEY,
  site_id UUID FOREIGN KEY,
  name VARCHAR,
  device_type VARCHAR,
  status VARCHAR,  -- online, offline, warning
  push_platform VARCHAR,  -- fcm, wns, apns, webpush, mqtt
  push_token TEXT,
  last_seen TIMESTAMP,
  created_at TIMESTAMP
)

-- Jobs (scheduled tasks)
jobs (
  id UUID PRIMARY KEY,
  device_id UUID FOREIGN KEY,
  name VARCHAR,
  status VARCHAR,  -- pending, running, completed, failed
  scheduled_at TIMESTAMP,
  completed_at TIMESTAMP,
  result TEXT
)

-- Push Subscriptions (Web Push specific)
push_subscriptions (
  id UUID PRIMARY KEY,
  device_id UUID FOREIGN KEY,
  endpoint VARCHAR UNIQUE,
  p256dh_key VARCHAR,
  auth_key VARCHAR,
  created_at TIMESTAMP
)

-- Audit Logs (tracking all actions)
audit_logs (
  id UUID PRIMARY KEY,
  action VARCHAR,
  user_id UUID,
  resource_type VARCHAR,
  resource_id UUID,
  details JSON,
  timestamp TIMESTAMP
)
```

---

## Getting Started

### Prerequisites

**Required:**
- Python 3.12 or higher
- Node.js 20 or higher
- npm (comes with Node.js)
- Git

**Optional (for production):**
- Docker & Docker Compose
- PostgreSQL 14+
- Redis 7+

### Installation

#### Option 1: One-Command Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# Run the integration script
chmod +x scripts/test-integration.sh
./scripts/test-integration.sh
```

This script automatically:
- ✓ Checks prerequisites
- ✓ Sets up Python virtual environment
- ✓ Installs backend dependencies
- ✓ Installs frontend dependencies
- ✓ Generates VAPID keys for Web Push
- ✓ Creates environment configuration files
- ✓ Initializes SQLite database
- ✓ Starts backend server (http://localhost:8000)
- ✓ Starts frontend server (http://localhost:5173)
- ✓ Opens browser automatically

**Access Points:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Option 2: Manual Setup

**Backend:**
```bash
# Create virtual environment
cd backend
python3 -m venv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file (see Configuration section)
cp .env.example .env
# Edit .env with your settings

# Run database migrations (if applicable)
# alembic upgrade head

# Start server
uvicorn homepot.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
# Install dependencies
cd frontend
npm install

# Create .env file
cp .env.example .env.local
# Edit .env.local with your settings

# Start development server
npm run dev
```

### Configuration

#### Backend Configuration (`.env`)

The backend uses **Pydantic V2** with nested settings. Environment variables use the `__` delimiter for nesting.

```bash
# backend/.env

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=true
ENVIRONMENT=development

# Database Configuration (nested with DATABASE__)
DATABASE__URL=sqlite:///../data/homepot.db
DATABASE__ECHO_SQL=false

# Authentication Settings (nested with AUTH__)
AUTH__SECRET_KEY=your-secret-key-here-change-in-production
AUTH__ALGORITHM=HS256
AUTH__ACCESS_TOKEN_EXPIRE_MINUTES=30
AUTH__API_KEY_HEADER=X-API-Key

# Redis Settings (nested with REDIS__)
REDIS__URL=redis://localhost:6379/0

# Push Notification Settings (nested with PUSH__)
PUSH__ENABLED=true
PUSH__DEFAULT_TTL=300

# Web Push VAPID (auto-generated by script)
PUSH__WEB_PUSH__VAPID_PRIVATE_KEY=your-vapid-private-key
PUSH__WEB_PUSH__VAPID_PUBLIC_KEY=your-vapid-public-key
PUSH__WEB_PUSH__VAPID_SUBJECT=mailto:admin@example.com

# WebSocket Settings (nested with WEBSOCKET__)
WEBSOCKET__ENABLED=true
WEBSOCKET__PING_INTERVAL=20
WEBSOCKET__PING_TIMEOUT=10

# Logging Settings (nested with LOGGING__)
LOGGING__LEVEL=INFO

# Device Settings (nested with DEVICES__)
DEVICES__HEALTH_CHECK_INTERVAL=60
DEVICES__HEALTH_CHECK_TIMEOUT=10
DEVICES__DEVICE_OFFLINE_THRESHOLD=300
DEVICES__MAX_CONCURRENT_JOBS=10

# Agent Simulation
PUSH__ENABLE_AGENT_SIMULATION=false
```

#### Frontend Configuration (`.env.local`)

```bash
# frontend/.env.local

# API Base URL (backend)
VITE_API_BASE_URL=http://localhost:8000

# App Configuration
VITE_APP_NAME=HOMEPOT Client
VITE_APP_VERSION=1.0.0

# Feature Flags
VITE_ENABLE_PUSH_NOTIFICATIONS=true
VITE_ENABLE_WEBSOCKET=true
VITE_ENABLE_ANALYTICS=false
```

### Verification

After setup, verify everything is working:

**1. Check Backend Health:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","timestamp":"...","version":"..."}
```

**2. Check API Documentation:**
Open http://localhost:8000/docs in your browser - you should see Swagger UI with all endpoints.

**3. Check Frontend:**
Open http://localhost:5173 - you should see the HOMEPOT Client application.

**4. Test Push Notification Setup:**
```bash
# Get VAPID public key
curl http://localhost:8000/api/v1/push/vapid-public-key
# Expected: {"public_key":"..."}
```

---

## Development Guide

### Development Workflow

**Starting Development:**
```bash
# Option 1: Use integration script (recommended)
./scripts/test-integration.sh

# Option 2: Quick start (skips dependency installation)
./scripts/test-integration.sh --quick

# Option 3: Manual start
# Terminal 1 - Backend
cd backend && source .venv/bin/activate
uvicorn homepot.main:app --reload

# Terminal 2 - Frontend
cd frontend && npm run dev
```

**Making Changes:**

Both backend and frontend have **hot reload** enabled:
- **Backend:** Edit Python files, server restarts automatically
- **Frontend:** Edit React files, browser updates instantly

### Adding a New Feature

**Example: Adding a new "Alerts" feature**

**1. Backend - Create Endpoint:**

```python
# backend/src/homepot/app/api/API_v1/Endpoints/AlertsEndpoint.py

from fastapi import APIRouter, Depends
from typing import List
from homepot.models import Alert
from homepot.database import get_db

router = APIRouter()

@router.get("/alerts", response_model=List[Alert])
async def get_alerts(db=Depends(get_db)):
    """Get all alerts"""
    alerts = db.query(Alert).all()
    return alerts

@router.post("/alerts", response_model=Alert)
async def create_alert(alert: Alert, db=Depends(get_db)):
    """Create new alert"""
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
```

**2. Register Router:**

```python
# backend/src/homepot/app/api/API_v1/Api.py

from .Endpoints import AlertsEndpoint

api_v1_router.include_router(
    AlertsEndpoint.router,
    prefix="/alerts",
    tags=["Alerts"]
)
```

**3. Frontend - Add API Method:**

```javascript
// frontend/src/services/api.js

export const api = {
  // ... existing methods
  
  alerts: {
    getAll: async () => {
      const response = await client.get('/alerts')
      return response.data
    },
    
    create: async (alertData) => {
      const response = await client.post('/alerts', alertData)
      return response.data
    }
  }
}
```

**4. Frontend - Create Component:**

```jsx
// frontend/src/pages/Alerts/AlertsList.jsx

import { useEffect, useState } from 'react'
import { api } from '../../services/api'

export default function AlertsList() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    loadAlerts()
  }, [])
  
  const loadAlerts = async () => {
    try {
      const data = await api.alerts.getAll()
      setAlerts(data)
    } catch (error) {
      console.error('Failed to load alerts:', error)
    } finally {
      setLoading(false)
    }
  }
  
  if (loading) return <div>Loading...</div>
  
  return (
    <div>
      <h1>Alerts</h1>
      {alerts.map(alert => (
        <div key={alert.id}>{alert.message}</div>
      ))}
    </div>
  )
}
```

**5. Add Route:**

```jsx
// frontend/src/App.jsx (or routes/index.jsx when implemented)

import AlertsList from './pages/Alerts/AlertsList'

// In your router configuration:
<Route path="/alerts" element={<AlertsList />} />
```

**6. Test:**

Visit http://localhost:5173/alerts and test the new feature!

### Code Style & Standards

**Backend (Python):**
- Follow PEP 8 style guide
- Use type hints for all functions
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes

```python
def send_notification(
    device_id: str,
    message: str,
    platform: str = "fcm"
) -> dict:
    """
    Send push notification to device.
    
    Args:
        device_id: Unique device identifier
        message: Notification message content
        platform: Push platform (fcm, wns, apns, webpush, mqtt)
        
    Returns:
        dict: Notification send result with status
        
    Raises:
        ValueError: If platform is not supported
    """
    pass
```

**Frontend (JavaScript/React):**
- Use functional components with hooks
- Use descriptive variable/function names
- Maximum line length: 100 characters
- One component per file

```jsx
// Good
function DeviceCard({ device, onDelete }) {
  const [isDeleting, setIsDeleting] = useState(false)
  
  const handleDelete = async () => {
    setIsDeleting(true)
    await onDelete(device.id)
    setIsDeleting(false)
  }
  
  return (
    <div className="device-card">
      <h3>{device.name}</h3>
      <button onClick={handleDelete} disabled={isDeleting}>
        {isDeleting ? 'Deleting...' : 'Delete'}
      </button>
    </div>
  )
}
```

### Git Workflow

**Branch Naming:**
```
feature/feature-name    # New features
fix/bug-description     # Bug fixes
docs/documentation-update
refactor/code-improvement
```

**Commit Messages:**
```
feat: add alert management feature
fix: resolve push notification token validation
docs: update API documentation
refactor: simplify device status logic
test: add tests for notifications service
```

**Pull Request Process:**
1. Create feature branch from `main`
2. Make changes and commit
3. Write/update tests
4. Ensure all tests pass
5. Update documentation
6. Push branch and create PR
7. Request review from team
8. Address review comments
9. Merge after approval

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1
```

### Authentication

**All protected endpoints require JWT authentication.**

**Header:**
```
Authorization: Bearer <your-jwt-token>
```

**Get Token:**
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "yourpassword"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Core Endpoints

#### Health Check
```bash
GET /health
# Check system health

Response: 200 OK
{
  "status": "healthy",
  "timestamp": "2025-10-24T10:30:00Z",
  "version": "1.0.0"
}
```

#### Sites

```bash
# List all sites
GET /api/v1/sites
Response: 200 OK
[
  {
    "id": "uuid",
    "name": "Main Office",
    "location": "New York, NY",
    "description": "Headquarters",
    "created_at": "2025-10-24T10:00:00Z"
  }
]

# Get site details
GET /api/v1/sites/{site_id}
Response: 200 OK
{
  "id": "uuid",
  "name": "Main Office",
  "location": "New York, NY",
  "devices_count": 15,
  "active_devices": 12
}

# Create site
POST /api/v1/sites
Content-Type: application/json
{
  "name": "Branch Office",
  "location": "Boston, MA",
  "description": "East Coast Branch"
}
Response: 201 Created

# Update site
PUT /api/v1/sites/{site_id}
Content-Type: application/json
{
  "name": "Updated Name",
  "location": "Updated Location"
}
Response: 200 OK

# Delete site
DELETE /api/v1/sites/{site_id}
Response: 204 No Content
```

#### Devices

```bash
# List all devices
GET /api/v1/devices
Query parameters:
  - site_id (optional): Filter by site
  - status (optional): Filter by status (online, offline, warning)
  - limit (optional): Max results (default: 100)
  - offset (optional): Pagination offset

Response: 200 OK
[
  {
    "id": "uuid",
    "site_id": "uuid",
    "name": "Sensor #1",
    "device_type": "temperature_sensor",
    "status": "online",
    "push_platform": "fcm",
    "last_seen": "2025-10-24T10:25:00Z"
  }
]

# Get device details
GET /api/v1/devices/{device_id}
Response: 200 OK
{
  "id": "uuid",
  "name": "Sensor #1",
  "status": "online",
  "push_subscription": {
    "platform": "fcm",
    "token": "...",
    "endpoint": "..."
  },
  "jobs": [...]
}

# Create device
POST /api/v1/devices
Content-Type: application/json
{
  "site_id": "uuid",
  "name": "New Device",
  "device_type": "actuator",
  "push_platform": "fcm",
  "push_token": "device-fcm-token"
}
Response: 201 Created

# Update device
PUT /api/v1/devices/{device_id}
Response: 200 OK

# Delete device
DELETE /api/v1/devices/{device_id}
Response: 204 No Content
```

#### Push Notifications

```bash
# Get VAPID public key (Web Push)
GET /api/v1/push/vapid-public-key
Response: 200 OK
{
  "public_key": "BNJ..."
}

# Subscribe device to push notifications
POST /api/v1/push/subscribe
Content-Type: application/json
{
  "device_id": "uuid",
  "platform": "webpush",
  "subscription": {
    "endpoint": "https://...",
    "keys": {
      "p256dh": "...",
      "auth": "..."
    }
  }
}
Response: 201 Created

# Send notification
POST /api/v1/push/send
Content-Type: application/json
{
  "device_id": "uuid",
  "title": "Alert",
  "body": "Device offline",
  "data": {
    "priority": "high"
  }
}
Response: 200 OK
{
  "success": true,
  "message_id": "..."
}

# Send bulk notification
POST /api/v1/push/send-bulk
Content-Type: application/json
{
  "device_ids": ["uuid1", "uuid2", "uuid3"],
  "title": "System Update",
  "body": "Maintenance scheduled"
}
Response: 200 OK
{
  "success_count": 3,
  "failure_count": 0,
  "results": [...]
}

# Publish MQTT message
POST /api/v1/push/mqtt/publish
Content-Type: application/json
{
  "topic": "devices/alerts",
  "payload": {"message": "Alert!"},
  "qos": 1
}
Response: 200 OK

# Get available platforms
GET /api/v1/push/platforms
Response: 200 OK
[
  {
    "name": "fcm",
    "display_name": "Firebase Cloud Messaging",
    "enabled": true,
    "supports_devices": ["android", "ios", "web"]
  },
  {
    "name": "webpush",
    "display_name": "Web Push",
    "enabled": true,
    "requires_subscription": true
  }
]

# Get platform details
GET /api/v1/push/platforms/{platform_name}/info
Response: 200 OK
{
  "name": "fcm",
  "enabled": true,
  "configuration": {...},
  "statistics": {
    "total_sent": 1234,
    "success_rate": 98.5
  }
}

# Send test notification
POST /api/v1/push/test
Content-Type: application/json
{
  "device_id": "uuid",
  "platform": "webpush"
}
Response: 200 OK
{
  "success": true,
  "test_message": "Test notification sent!"
}
```

#### Jobs

```bash
# List jobs
GET /api/v1/jobs
Query parameters:
  - device_id (optional)
  - status (optional): pending, running, completed, failed
  - limit, offset

Response: 200 OK
[
  {
    "id": "uuid",
    "device_id": "uuid",
    "name": "Temperature Reading",
    "status": "completed",
    "scheduled_at": "2025-10-24T10:00:00Z",
    "completed_at": "2025-10-24T10:01:23Z",
    "result": "23.5°C"
  }
]

# Create job
POST /api/v1/jobs
Content-Type: application/json
{
  "device_id": "uuid",
  "name": "Firmware Update",
  "scheduled_at": "2025-10-25T02:00:00Z",
  "parameters": {
    "version": "2.1.0"
  }
}
Response: 201 Created

# Get job details
GET /api/v1/jobs/{job_id}
Response: 200 OK

# Update job
PUT /api/v1/jobs/{job_id}
Response: 200 OK

# Cancel job
DELETE /api/v1/jobs/{job_id}
Response: 204 No Content
```

### Error Responses

All endpoints may return standard HTTP error codes:

```bash
400 Bad Request
{
  "detail": "Invalid request data",
  "errors": {
    "field_name": ["Error message"]
  }
}

401 Unauthorized
{
  "detail": "Not authenticated"
}

403 Forbidden
{
  "detail": "Not enough permissions"
}

404 Not Found
{
  "detail": "Resource not found"
}

422 Unprocessable Entity
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}

500 Internal Server Error
{
  "detail": "Internal server error"
}
```

---

## Frontend Guide

### Services

#### API Client (`services/api.js`)

Complete axios-based client for all backend endpoints.

```javascript
import { api } from './services/api'

// Authentication
const loginResponse = await api.login({ username, password })
const token = loginResponse.access_token

// Sites
const sites = await api.sites.getAll()
const site = await api.sites.getById(siteId)
await api.sites.create({ name, location })
await api.sites.update(siteId, { name })
await api.sites.delete(siteId)

// Devices
const devices = await api.devices.getAll({ site_id: siteId })
const device = await api.devices.getById(deviceId)
await api.devices.create({ site_id, name, device_type })

// Push Notifications
const vapidKey = await api.push.getVapidPublicKey()
await api.push.subscribe(deviceId, subscription)
await api.push.send(deviceId, { title, body, data })
await api.push.sendBulk(deviceIds, { title, body })

// Jobs
const jobs = await api.jobs.getAll({ device_id })
await api.jobs.create({ device_id, name, scheduled_at })

// Health
const health = await api.health.check()
```

#### Push Notification Manager (`services/pushNotifications.js`)

Singleton service for managing Web Push subscriptions.

```javascript
import pushManager from './services/pushNotifications'

// Initialize (call once on app load)
await pushManager.initialize()

// Check permission
const permission = pushManager.getPermission()
// 'granted', 'denied', or 'default'

// Request permission
const granted = await pushManager.requestPermission()

// Subscribe to push notifications
const subscription = await pushManager.subscribe()
// subscription object sent to backend

// Check subscription status
const isSubscribed = await pushManager.isSubscribed()

// Unsubscribe
await pushManager.unsubscribe()

// Send test notification (local)
await pushManager.showNotification({
  title: 'Test',
  body: 'This is a test notification',
  icon: '/icon.png'
})

// Send test via backend
await pushManager.sendTestNotification()
```

### Components

#### NotificationSettings Component

Ready-to-use component for push notification preferences.

```jsx
import NotificationSettings from './components/NotificationSettings'

function SettingsPage() {
  return (
    <div>
      <h1>Settings</h1>
      <NotificationSettings />
    </div>
  )
}
```

**Features:**
- Permission status display
- Subscribe/unsubscribe buttons
- Test notification button
- Subscription info display
- Platform availability list
- Error handling

### State Management

Currently using React Context and useState. For scaling, consider:

**Zustand (Recommended):**
```javascript
// store/authStore.js
import create from 'zustand'

const useAuthStore = create((set) => ({
  user: null,
  token: null,
  login: (user, token) => set({ user, token }),
  logout: () => set({ user: null, token: null }),
}))

// Usage in component
function Header() {
  const { user, logout } = useAuthStore()
  
  return (
    <div>
      <span>Hello, {user?.name}</span>
      <button onClick={logout}>Logout</button>
    </div>
  )
}
```

**React Query (for server state):**
```javascript
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from './services/api'

function DevicesList() {
  // Fetch devices with automatic caching and refetching
  const { data: devices, isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: api.devices.getAll
  })
  
  // Mutation for creating device
  const createDevice = useMutation({
    mutationFn: api.devices.create,
    onSuccess: () => {
      queryClient.invalidateQueries(['devices'])
    }
  })
  
  if (isLoading) return <div>Loading...</div>
  
  return (
    <div>
      {devices.map(device => (
        <div key={device.id}>{device.name}</div>
      ))}
    </div>
  )
}
```

---

## Push Notifications

### Web Push (VAPID)

**Browser Support:** Chrome, Firefox, Edge, Safari 16+

**Setup (already done by script):**
1. VAPID keys generated automatically
2. Service Worker registered (`/sw.js`)
3. Push manager initialized

**Usage:**

```javascript
// Frontend: Request permission and subscribe
import pushManager from './services/pushNotifications'

// Initialize on app load
await pushManager.initialize()

// Request permission (user action required)
const granted = await pushManager.requestPermission()

if (granted) {
  // Subscribe
  const subscription = await pushManager.subscribe()
  // Backend receives and stores subscription
}

// Backend: Send notification
POST /api/v1/push/send
{
  "device_id": "uuid",
  "title": "New Message",
  "body": "You have a new notification",
  "data": {
    "url": "/notifications"
  }
}
```

**Service Worker (`public/sw.js`):**

Handles:
- Push event reception
- Notification display
- Click handling
- Cache management

```javascript
// Service worker automatically:
self.addEventListener('push', (event) => {
  const data = event.data.json()
  self.registration.showNotification(data.title, {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    data: data.data
  })
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  // Open app or navigate to URL
  clients.openWindow(event.notification.data.url)
})
```

### FCM (Firebase Cloud Messaging)

**Platform Support:** Android, iOS, Web

**Setup:**
1. Create Firebase project
2. Get Server Key and Sender ID
3. Add to backend configuration

```bash
# backend/.env
PUSH__FCM__SERVER_KEY=your-fcm-server-key
PUSH__FCM__SENDER_ID=your-sender-id
```

**Usage:**

```python
# Backend sends notification
from homepot.services.push_notifications import PushNotificationFactory

factory = PushNotificationFactory()
fcm_service = factory.get_service('fcm')

result = await fcm_service.send_notification(
    token="device-fcm-token",
    title="Alert",
    body="Device status changed",
    data={"device_id": "123"}
)
```

### APNs (Apple Push Notification service)

**Platform Support:** iOS, macOS

**Setup:**
1. Get APNs certificate or auth key from Apple Developer
2. Configure in backend

```bash
# backend/.env
PUSH__APNS__KEY_ID=your-key-id
PUSH__APNS__TEAM_ID=your-team-id
PUSH__APNS__AUTH_KEY=your-auth-key
PUSH__APNS__USE_SANDBOX=true  # Set false for production
```

### WNS (Windows Notification Service)

**Platform Support:** Windows devices

**Setup:**
1. Register app in Microsoft Partner Center
2. Get Package SID and Client Secret

```bash
# backend/.env
PUSH__WNS__PACKAGE_SID=your-package-sid
PUSH__WNS__CLIENT_SECRET=your-client-secret
```

### MQTT

**Platform Support:** IoT devices

**Setup:**
1. Configure MQTT broker connection

```bash
# backend/.env
PUSH__MQTT__BROKER_HOST=broker.example.com
PUSH__MQTT__BROKER_PORT=1883
PUSH__MQTT__USERNAME=user
PUSH__MQTT__PASSWORD=pass
PUSH__MQTT__USE_TLS=true
```

**Usage:**

```bash
# Publish to topic
POST /api/v1/push/mqtt/publish
{
  "topic": "devices/alerts",
  "payload": {
    "message": "Temperature high",
    "device_id": "sensor-1",
    "value": 85.5
  },
  "qos": 1,
  "retain": false
}
```

---

## Testing

### Backend Testing

**Run all tests:**
```bash
cd backend
pytest
```

**Run with coverage:**
```bash
pytest --cov=homepot --cov-report=html
# Open htmlcov/index.html to view report
```

**Run specific test file:**
```bash
pytest tests/test_push_notifications.py
```

**Run specific test:**
```bash
pytest tests/test_push_notifications.py::test_send_notification
```

**Writing tests:**

```python
# tests/test_example.py
import pytest
from homepot.services import example_service

def test_example_function():
    """Test example function"""
    result = example_service.process_data("input")
    assert result == "expected output"

@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await example_service.async_process()
    assert result is not None

@pytest.fixture
def sample_device():
    """Fixture providing sample device"""
    return {
        "id": "test-123",
        "name": "Test Device",
        "status": "online"
    }

def test_with_fixture(sample_device):
    """Test using fixture"""
    assert sample_device["status"] == "online"
```

### Frontend Testing

**Run tests:**
```bash
cd frontend
npm test
```

**Run with coverage:**
```bash
npm run test:coverage
```

**Watch mode (auto-rerun on changes):**
```bash
npm test -- --watch
```

**Writing unit tests (Vitest):**

```javascript
// tests/services/api.test.js
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api } from '../../src/services/api'

describe('API Service', () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks()
  })
  
  it('should login successfully', async () => {
    const credentials = {
      username: 'test@example.com',
      password: 'password123'
    }
    
    const response = await api.login(credentials)
    
    expect(response).toHaveProperty('access_token')
    expect(response.token_type).toBe('bearer')
  })
  
  it('should handle login error', async () => {
    const credentials = {
      username: 'invalid',
      password: 'wrong'
    }
    
    await expect(api.login(credentials)).rejects.toThrow()
  })
})
```

**Writing component tests (React Testing Library):**

```javascript
// tests/components/DeviceCard.test.jsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import DeviceCard from '../../src/components/DeviceCard'

describe('DeviceCard', () => {
  const mockDevice = {
    id: '123',
    name: 'Test Device',
    status: 'online'
  }
  
  it('renders device name', () => {
    render(<DeviceCard device={mockDevice} />)
    expect(screen.getByText('Test Device')).toBeInTheDocument()
  })
  
  it('calls onDelete when delete button clicked', () => {
    const onDelete = vi.fn()
    render(<DeviceCard device={mockDevice} onDelete={onDelete} />)
    
    const deleteButton = screen.getByText('Delete')
    fireEvent.click(deleteButton)
    
    expect(onDelete).toHaveBeenCalledWith('123')
  })
})
```

### E2E Testing (Playwright)

**Install:**
```bash
cd frontend
npm install -D @playwright/test
npx playwright install
```

**Run E2E tests:**
```bash
npx playwright test
npx playwright test --ui  # Interactive mode
npx playwright test --debug  # Debug mode
```

**Writing E2E tests:**

```javascript
// e2e/auth.spec.js
import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('should login successfully', async ({ page }) => {
    await page.goto('http://localhost:5173')
    
    // Click login link
    await page.click('text=Login')
    
    // Fill form
    await page.fill('input[name="username"]', 'test@example.com')
    await page.fill('input[name="password"]', 'password123')
    
    // Submit
    await page.click('button[type="submit"]')
    
    // Should redirect to dashboard
    await expect(page).toHaveURL('http://localhost:5173/dashboard')
    
    // Should see welcome message
    await expect(page.locator('text=Welcome')).toBeVisible()
  })
  
  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('http://localhost:5173/login')
    
    await page.fill('input[name="username"]', 'invalid')
    await page.fill('input[name="password"]', 'wrong')
    await page.click('button[type="submit"]')
    
    // Should see error message
    await expect(page.locator('text=Invalid credentials')).toBeVisible()
  })
})
```

---

## Deployment

### Docker Deployment

**Build and run:**
```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.prod.yml up -d
```

**Docker Compose configuration:**

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE__URL=postgresql://user:pass@db:5432/homepot
      - REDIS__URL=redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
    depends_on:
      - backend
    restart: always

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=homepot
      - POSTGRES_USER=homepot_user
      - POSTGRES_PASSWORD=homepot_dev_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
    restart: always

volumes:
  postgres_data:
```

### Manual Deployment

**Backend (Production):**

```bash
# Install dependencies
pip install -r requirements.txt

# Set production environment variables
export ENVIRONMENT=production
export DEBUG=false
export DATABASE__URL=postgresql://...

# Run migrations
alembic upgrade head

# Start with gunicorn (production WSGI server)
gunicorn homepot.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

**Frontend (Production):**

```bash
# Build production bundle
npm run build
# Creates optimized build in dist/

# Serve with nginx or any static server
# dist/ folder contains all static files
```

**Nginx Configuration:**

```nginx
# nginx.conf
server {
    listen 80;
    server_name homepot.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name homepot.example.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # Frontend
    location / {
        root /var/www/homepot/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Environment-Specific Configuration

**Development:**
- SQLite database
- Debug mode enabled
- Hot reload
- Detailed logging
- CORS allow all

**Staging:**
- PostgreSQL database
- Debug mode disabled
- Production-like settings
- Testing environment

**Production:**
- PostgreSQL with read replicas
- Debug mode disabled
- Redis for caching
- Rate limiting enabled
- CORS restricted to domain
- SSL/TLS required
- Error tracking (Sentry)
- Structured logging
- Health checks
- Auto-scaling

---

## Troubleshooting

### Common Issues

#### Backend won't start

**Error:** `ModuleNotFoundError: No module named 'homepot'`

**Solution:**
```bash
cd backend
pip install -e .
# OR
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

**Error:** `8 validation errors for Settings - Extra inputs are not permitted`

**Solution:**  
Environment variables must use nested format with `__` delimiter:
```bash
# WRONG:
SECRET_KEY=xxx
LOG_LEVEL=INFO

# CORRECT:
AUTH__SECRET_KEY=xxx
LOGGING__LEVEL=INFO
```

**Error:** `Database connection failed`

**Solution:**
```bash
# Check database path is correct
DATABASE__URL=sqlite:///../data/homepot.db

# Create data directory
mkdir -p data
touch data/homepot.db
```

#### Frontend won't start

**Error:** `Cannot find module 'axios'`

**Solution:**
```bash
cd frontend
npm install
```

**Error:** `VITE_API_BASE_URL is not defined`

**Solution:**
Create `.env.local` file:
```bash
cd frontend
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
```

#### Push Notifications not working

**Error:** `VAPID public key not found`

**Solution:**
Generate VAPID keys:
```bash
# Using Python
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import base64

private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
public_key = private_key.public_key()

# Export keys in base64 URL-safe format
print('Public Key:', base64.urlsafe_b64encode(...).decode())
print('Private Key:', base64.urlsafe_b64encode(...).decode())
"

# OR use the integration script (recommended)
./scripts/test-integration.sh
```

**Error:** `Push permission denied`

**Solution:**
- Check browser supports push notifications
- Request permission from user action (button click)
- Check site is served over HTTPS (required for production)
- Clear browser data and retry

**Error:** `Service Worker registration failed`

**Solution:**
```bash
# Check sw.js is in public/ folder
ls frontend/public/sw.js

# Check service worker scope
# Must be served from root or /
# Scope: '/' in pushNotifications.js
```

#### WebSocket connection fails

**Error:** `WebSocket connection to 'ws://localhost:8000/ws' failed`

**Solution:**
```bash
# Check WebSocket is enabled in backend/.env
WEBSOCKET__ENABLED=true

# Check firewall allows WebSocket connections

# For production with nginx, ensure proxy configured:
location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

#### CORS errors

**Error:** `Access-Control-Allow-Origin header is missing`

**Solution:**
```bash
# Development - Allow all (backend/.env)
CORS__ALLOW_ORIGINS=["*"]

# Production - Specific domains only
CORS__ALLOW_ORIGINS=["https://homepot.example.com"]
```

### Debugging

**Backend:**
```bash
# Enable debug logging
LOGGING__LEVEL=DEBUG

# Check logs
tail -f backend.log

# Use Python debugger
import pdb; pdb.set_trace()

# Or use breakpoint() (Python 3.7+)
breakpoint()
```

**Frontend:**
```bash
# Check console in browser DevTools (F12)

# Enable React DevTools
# Install browser extension

# Check network tab for API calls

# Add debugging
console.log('Debug:', variable)
debugger;  // Breakpoint
```

**API Testing:**
```bash
# Test endpoints with curl
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'

# Or use httpie (more user-friendly)
http POST localhost:8000/api/v1/auth/login \
  username=test password=test

# Or use Postman/Insomnia (GUI tools)
```

### Performance Issues

**Slow API responses:**
- Check database indexes
- Enable query logging: `DATABASE__ECHO_SQL=true`
- Use database query profiling
- Implement caching (Redis)

**High memory usage:**
- Check for memory leaks
- Limit query result sizes
- Implement pagination
- Use database connection pooling

**Frontend slow to load:**
- Check bundle size: `npm run build -- --analyze`
- Implement code splitting
- Lazy load routes/components
- Optimize images
- Use CDN for static assets

### Getting Help

**Check documentation:**
- API docs: http://localhost:8000/docs
- This guide: `/docs/integration-guide.md`
- Engineering TODO: `/docs/engineering-todo.md`

**Search existing issues:**
- GitHub Issues: Check if problem already reported
- GitHub Discussions: Ask questions

**Create new issue:**
Include:
- Steps to reproduce
- Expected vs actual behavior
- Error messages
- Environment (OS, Python version, Node version)
- Logs (backend.log, frontend console)

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed contribution guidelines.

**Quick Start:**
1. Fork repository
2. Create feature branch
3. Make changes
4. Write tests
5. Update documentation
6. Submit pull request

---

## License

See [LICENSE](../LICENSE) file for details.

---

## Changelog

### v1.0.0 (October 24, 2025)

**Added:**
- Complete backend-frontend integration
- Push notification support (5 platforms)
- ONE-COMMAND integration script
- Comprehensive API endpoints
- Frontend service layer (API client, Push manager)
- Service Worker for Web Push
- NotificationSettings component
- WebSocket support
- Audit logging
- Agent simulation framework
- Complete documentation

**Infrastructure:**
- FastAPI backend with modular architecture
- React frontend with Vite
- SQLite database (development)
- Docker support
- Testing framework (pytest, vitest, playwright)
- CI/CD ready

---

**Last Updated:** October 24, 2025  
**Version:** 1.0.0  
**Maintained By:** HOMEPOT Development Team
