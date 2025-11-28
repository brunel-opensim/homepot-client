# Complete HOMEPOT Website Setup Guide

This guide provides step-by-step instructions to run the complete HOMEPOT website with full frontend-backend integration.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Setup](#manual-setup)
- [Verification](#verification)
- [Available Features](#available-features)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Python**: 3.11+ (3.12.3 recommended)
- **Node.js**: 22.12+ (22.21.1 recommended)
- **PostgreSQL**: 13+ (for production database)
- **Operating System**: Linux, macOS, or Windows with WSL

### Installed Tools

- Git
- Python virtual environment support
- Node Version Manager (nvm) - recommended
- curl (for testing)
- PostgreSQL server and client

### Important Dependencies

⚠️ **bcrypt Version:** The project requires `bcrypt==4.1.3` for compatibility with `passlib`. Version 5.x has breaking changes that cause authentication failures. This is already pinned in `backend/requirements.txt`.

## Quick Start

Use the provided script to start everything automatically:

```bash
# From the repository root
./scripts/start-complete-website.sh
```

This script will:
1. Activate the Python virtual environment
2. Start the backend server on `http://localhost:8000`
3. Switch to Node.js 22
4. Start the frontend server on `http://localhost:5173`
5. Open the website in your browser

## Manual Setup

If you prefer to start services manually or need more control:

### Step 1: Start the Backend

```bash
# From repository root
cd backend

# Activate virtual environment
source ../scripts/activate-homepot.sh

# Start the backend server
python -m uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
INFO:homepot.push_notifications.factory: Registered push notification provider: fcm_linux
INFO:homepot.push_notifications.factory: Registered push notification provider: apns
...
```

**Verify Backend:**
```bash
curl http://localhost:8000/
# Should return: {"message": "I Am Alive"}

curl http://localhost:8000/docs
# Should open FastAPI Swagger documentation
```

### Step 2: Start the Frontend

In a **new terminal**:

```bash
# From repository root
cd frontend

# Switch to Node.js 22 (if using nvm)
nvm use 22

# Start the frontend development server
npm run dev
```

**Expected Output:**
```
VITE v7.2.1  ready in 188 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### Step 3: Access the Website

Open your browser and navigate to:
```
http://localhost:5173
```

You should be automatically redirected to the login page.

## Verification

### 1. Backend Health Check

```bash
# Test root endpoint
curl http://localhost:8000/
# Expected: {"message": "I Am Alive"}

# Test API documentation
curl http://localhost:8000/docs
# Should return HTML (Swagger UI)

# Test sites endpoint
curl http://localhost:8000/api/v1/sites/sites
# Should return JSON with sites data
```

### 2. Frontend-Backend Connection

```bash
# Check if frontend can reach backend
curl -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/sites/sites

# Should return sites data with 200 status
```

### 3. Full Integration Test

1. **Open the website**: `http://localhost:5173`
2. **Login Page**: You should see the login form
3. **Create Account**: Click "Sign up" to create a new account
4. **Dashboard**: After login, you should see:
   - List of sites (fetched from backend)
   - System status indicators
   - Navigation buttons

### 4. Test User Registration

```bash
# Create a test user via API
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test123!@#",
    "role": "admin"
  }'
```

### 5. Test Login

```bash
# Login with test user
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!@#"
  }'

# Should return access token
```

## Available Features

### Fully Functional

1. **Authentication**
   - User registration (signup)
   - User login with JWT tokens
   - Session management with auto-expiry
   - Protected routes

2. **Dashboard**
   - Real-time site list from backend
   - System status overview
   - Navigation to different sections

3. **Site Management**
   - View all sites
   - Search and filter sites
   - Site details view

4. **API Integration**
   - Complete API client service
   - Automatic token handling
   - Error handling and retries
   - Session expiry detection

### In Development

1. **Real-time Updates**
   - WebSocket connections (backend ready, frontend pending)
   - Live device status updates

2. **Device Management**
   - Device registration UI
   - Device monitoring dashboard
   - Device health checks

3. **Job Orchestration**
   - Job creation UI
   - Job status monitoring
   - Job history

## API Endpoints

### Authentication (`/api/v1/auth`)

- `POST /signup` - Create new user account
- `POST /login` - Login and get access token

### Sites (`/api/v1/sites`)

- `GET /sites` - List all sites
- `GET /sites/{site_id}` - Get site details
- `POST /sites` - Create new site
- `GET /sites/{site_id}/health` - Get site health status

### Devices (`/api/v1/devices`)

- `POST /sites/{site_id}/devices` - Register new device
- `POST /devices/{device_id}/restart` - Restart device

### Jobs (`/api/v1/jobs`)

- `POST /sites/{site_id}/jobs` - Create new job
- `GET /jobs/{job_id}` - Get job status

### Agents (`/api/v1/agents`)

- `GET /agents` - List all agents
- `GET /agents/{device_id}` - Get agent status
- `POST /agents/{device_id}/push` - Send push notification

### Health (`/api/v1/health`)

- `GET /health/status` - Get system health
- `GET /devices/{device_id}/health` - Get device health
- `POST /devices/{device_id}/health` - Trigger health check

### Push Notifications (`/api/v1/push`)

- `POST /push/send` - Send notification
- `POST /push/send-bulk` - Send bulk notifications
- `GET /push/platforms` - List available platforms

### Mobivisor (`/api/v1/mobivisor`)

- Integration with Mobivisor device management

## Environment Configuration

### Backend Configuration

Location: `backend/src/homepot/config.py`

Key settings:
- Database path: `../data/homepot.db`
- CORS origins (includes `http://localhost:5173`)
- API settings

### Frontend Configuration

Location: `frontend/.env.local`

```env
# Backend API Configuration
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# API Settings
VITE_API_TIMEOUT=30000

# Feature Flags
VITE_ENABLE_WEBSOCKET=true
VITE_ENABLE_PUSH_NOTIFICATIONS=true

# Development
VITE_ENABLE_DEBUG_LOGS=true
```

## Troubleshooting

### Backend Issues

**Problem**: `ModuleNotFoundError: No module named 'uvicorn'`

**Solution**: 
```bash
source scripts/activate-homepot.sh
cd backend
pip install -r requirements.txt
```

**Problem**: `Address already in use` on port 8000

**Solution**:
```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9

# Or use a different port
python -m uvicorn homepot.app.main:app --port 8001
```

**Problem**: Database errors

**Solution**:
```bash
# Reset the database
rm -f data/homepot.db
python -m uvicorn homepot.app.main:app --reload
```

### Frontend Issues

**Problem**: `You are using Node.js X.X.X. Vite requires Node.js version 20.19+ or 22.12+`

**Solution**:
```bash
# Install Node.js 22
nvm install 22
nvm use 22

# Verify version
node --version
```

**Problem**: Port 5173 already in use

**Solution**:
```bash
# Kill existing Vite process
pkill -f vite

# Or the server will automatically use next available port (5174)
```

**Problem**: Frontend can't connect to backend

**Solution**:
1. Verify backend is running: `curl http://localhost:8000/`
2. Check `.env.local` has correct URL: `VITE_API_BASE_URL=http://localhost:8000`
3. Restart frontend: `npm run dev`
4. Check browser console for CORS errors

**Problem**: CORS errors in browser

**Solution**:
The backend is already configured with CORS for `localhost:5173`. If you're using a different port:

1. Edit `backend/src/homepot/config.py`
2. Add your URL to `cors_origins` list
3. Restart backend

### Login/Authentication Issues

**Problem**: "Invalid credentials" when trying to login

**Solution**:
1. Create a test account first via signup page
2. Or use the API to create a user (see verification section)
3. Verify email/password combination

**Problem**: Session expires immediately

**Solution**:
Check backend logs for token generation issues. The default session is 24 hours.

## Development Workflow

### Making Changes

1. **Backend Changes**:
   ```bash
   # Backend has auto-reload enabled
   # Just edit files in backend/src/homepot/
   # Server will restart automatically
   ```

2. **Frontend Changes**:
   ```bash
   # Frontend has Hot Module Replacement (HMR)
   # Just edit files in frontend/src/
   # Changes appear immediately in browser
   ```

### Testing Changes

1. Use the API testing guide: `docs/api-testing-guide.md`
2. Check browser console for frontend errors
3. Check terminal logs for backend errors
4. Use Swagger UI: `http://localhost:8000/docs`

## Production Deployment

For production deployment, see:
- `docs/deployment-guide.md` - General deployment guide
- `docs/frontend-ci-cd.md` - Frontend-specific CI/CD

## Additional Resources

- **API Testing Guide**: `docs/api-testing-guide.md`
- **Development Guide**: `docs/development-guide.md`
- **Running Locally**: `docs/running-locally.md`
- **API Documentation**: `http://localhost:8000/docs` (when backend is running)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the existing documentation in `/docs`
3. Check GitHub issues
4. Review backend logs and browser console

## Version Information

- **Backend**: FastAPI with Python 3.12.3
- **Frontend**: React 19.1.1 + Vite 7.2.1
- **API Version**: v1
- **Last Updated**: November 7, 2025
