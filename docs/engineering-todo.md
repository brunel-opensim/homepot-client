# Engineering TODO List

> **Last Updated:** October 24, 2025  
> **Project:** HOMEPOT Client - Backend-Frontend Integration  
> **Branch:** `feature/backend-frontend-integration`

## Project Vision

Build a complete, production-ready **HOMEPOT Client web application** that enables users to:
- Manage IoT devices across multiple sites
- Monitor device health and status in real-time
- Send push notifications across 5 platforms (FCM, WNS, APNs, Web Push, MQTT)
- Schedule and track device jobs
- View analytics and system insights
- Configure and test device behaviors through agent simulation

---

## Current Status

### COMPLETED (Foundation)

#### Backend Infrastructure
- FastAPI application structure with modular architecture
- Complete REST API endpoints for all resources
- Push notification integration (5 platforms: FCM, WNS, APNs, Web Push, MQTT)
- VAPID key generation and management for Web Push
- PostgreSQL database with SQLAlchemy ORM
- JWT authentication and authorization
- WebSocket support for real-time updates
- Audit logging system
- Agent simulation framework
- Health check endpoints
- API documentation (Swagger/OpenAPI)

#### Frontend Infrastructure
- React 19 application with Vite build system
- Tailwind CSS configuration
- shadcn/ui component library setup
- Axios-based API service layer (`services/api.js`)
- Push notification manager (`services/pushNotifications.js`)
- Service Worker for Web Push (`public/sw.js`)
- NotificationSettings component
- Environment configuration

#### DevOps & Automation
- One-command integration script (`test-integration.sh`)
- Automated dependency installation
- VAPID key auto-generation
- Database initialization
- Process monitoring and graceful shutdown
- Docker configuration (Dockerfile, docker-compose.yml)
- Development documentation

### Progress Metrics
- **Backend API Endpoints:** 50+ (Sites, Devices, Jobs, Agents, Push, Auth, Health)
- **Frontend Services:** 2 core services (API client, Push manager)
- **Backend Test Coverage:** ~85%
- **Frontend Test Coverage:** To be established
- **Documentation Pages:** 25+

---

## PHASE 1: Core Application

**Goal:** Build the essential multi-page application structure with routing, authentication, and basic CRUD operations.

### Priority: CRITICAL

#### 1.1 Frontend Routing & Navigation
**Assignee:** _Unassigned_  
**Estimate:** 2-3 days  
**Dependencies:** None

- Install React Router DOM
  ```bash
  cd frontend && npm install react-router-dom
  ```
- Create route configuration in `frontend/src/routes/index.jsx`
- Implement main layouts:
  - `MainLayout.jsx` - Header, sidebar, footer for logged-in users
  - `AuthLayout.jsx` - Clean layout for login/signup pages
  - `DashboardLayout.jsx` - Dashboard-specific wrapper
- Create `ProtectedRoute.jsx` component for auth guards
- Update `App.jsx` to use React Router
- Test navigation between pages

**Files to Create:**
```
frontend/src/
├── App.jsx (MODIFY)
├── routes/
│   ├── index.jsx (NEW)
│   └── ProtectedRoute.jsx (NEW)
└── layouts/
    ├── MainLayout.jsx (NEW)
    ├── AuthLayout.jsx (NEW)
    └── DashboardLayout.jsx (NEW)
```

**Acceptance Criteria:**
- Browser navigation works (forward/back buttons)
- Authenticated routes redirect to login if not logged in
- Clean URLs (no hash routing)
- Active navigation item highlighted

---

#### 1.2 Authentication Pages
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** 1.1 (Routing)

- Create Login page with form validation
- Create Signup page with form validation
- Implement authentication state management (Zustand or Context)
- Add token storage (localStorage or httpOnly cookies)
- Implement auto-redirect after login
- Add logout functionality
- Handle authentication errors gracefully
- Add "Remember Me" functionality
- Create password reset flow (frontend only, backend TODO)

**Files to Create:**
```
frontend/src/
├── pages/
│   ├── Login.jsx (NEW)
│   ├── Signup.jsx (NEW)
│   └── ForgotPassword.jsx (NEW - optional)
├── components/Auth/
│   ├── LoginForm.jsx (NEW)
│   └── SignupForm.jsx (NEW)
└── store/
    └── authStore.js (NEW)
```

**Backend APIs (Already Available):**
- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`

**Acceptance Criteria:**
- User can sign up with email/password
- User can log in with credentials
- Invalid credentials show clear error messages
- Token is stored and sent with API requests
- User stays logged in after page refresh
- Logout clears token and redirects to login

---

#### 1.3 Main Dashboard Page
**Assignee:** _Unassigned_  
**Estimate:** 4-5 days  
**Dependencies:** 1.1 (Routing), 1.2 (Auth)

- Create Dashboard page with overview cards
- Display key metrics:
  - Total sites count
  - Active devices count
  - Pending jobs count
  - Recent notifications count
- Add quick actions section (Create Site, Add Device, etc.)
- Show recent activity feed
- Add system health status indicator
- Implement auto-refresh for real-time data

**Files to Create:**
```
frontend/src/
├── pages/
│   └── Dashboard.jsx (NEW)
└── components/Dashboard/
    ├── MetricCard.jsx (NEW)
    ├── QuickActions.jsx (NEW)
    ├── RecentActivity.jsx (NEW)
    └── SystemHealth.jsx (NEW)
```

**Backend APIs to Use:**
- `GET /api/v1/health` - System health
- `GET /api/v1/sites` - Sites count
- `GET /api/v1/devices` - Devices count
- `GET /api/v1/jobs` - Jobs count

**Acceptance Criteria:**
- Dashboard loads within 2 seconds
- All metrics display correctly
- Metrics update every 30 seconds
- Responsive design (mobile-friendly)
- Loading states for async data

---

#### 1.4 Sites Management Pages
**Assignee:** _Unassigned_  
**Estimate:** 5-6 days  
**Dependencies:** 1.1 (Routing), 1.2 (Auth)

- Create Sites List page with data table
- Add search and filter functionality
- Implement pagination (client-side or server-side)
- Create Site Detail page
- Create Site Create/Edit form
- Add validation for site data
- Implement delete confirmation dialog
- Add breadcrumb navigation
- Show associated devices for each site

**Files to Create:**
```
frontend/src/
├── pages/Sites/
│   ├── SitesList.jsx (NEW)
│   ├── SiteDetail.jsx (NEW)
│   └── SiteForm.jsx (NEW)
└── components/Sites/
    ├── SiteCard.jsx (NEW)
    ├── SiteTable.jsx (NEW)
    └── SiteDeleteDialog.jsx (NEW)
```

**Backend APIs (Already Available):**
- `GET /api/v1/sites` - List all sites
- `POST /api/v1/sites` - Create site
- `GET /api/v1/sites/{id}` - Get site details
- `PUT /api/v1/sites/{id}` - Update site
- `DELETE /api/v1/sites/{id}` - Delete site
- `GET /api/v1/sites/{id}/devices` - Get site devices

**Acceptance Criteria:**
- User can view all sites in a table
- User can search sites by name
- User can create a new site
- User can edit existing site
- User can delete site (with confirmation)
- Form validation works correctly
- Success/error messages display

---

## PHASE 2: Feature Development

**Goal:** Implement device management, job scheduling, and real-time features.

### Priority: HIGH

#### 2.1 Devices Management Pages
**Assignee:** _Unassigned_  
**Estimate:** 6-7 days  
**Dependencies:** 1.4 (Sites Management)

- Create Devices List page with status indicators
- Add filter by site, status, type
- Implement real-time status updates (WebSocket)
- Create Device Detail page with tabs:
  - Overview (info, status, health)
  - Jobs (job history)
  - Notifications (push settings)
  - Configuration (device settings)
- Create Device Create/Edit form
- Add device registration flow with push notification setup
- Implement bulk actions (delete, update status)
- Add device health visualization (charts)

**Files to Create:**
```
frontend/src/
├── pages/Devices/
│   ├── DevicesList.jsx (NEW)
│   ├── DeviceDetail.jsx (NEW)
│   └── DeviceForm.jsx (NEW)
├── components/Devices/
│   ├── DeviceCard.jsx (NEW)
│   ├── DeviceTable.jsx (NEW)
│   ├── DeviceStatusBadge.jsx (NEW)
│   ├── DeviceHealthChart.jsx (NEW)
│   └── DeviceDeleteDialog.jsx (NEW)
└── store/
    └── deviceStore.js (NEW)
```

**Backend APIs (Already Available):**
- `GET /api/v1/devices` - List devices
- `POST /api/v1/devices` - Create device
- `GET /api/v1/devices/{id}` - Get device
- `PUT /api/v1/devices/{id}` - Update device
- `DELETE /api/v1/devices/{id}` - Delete device
- `GET /api/v1/devices/health` - Device health

**Acceptance Criteria:**
- Device status updates in real-time
- Color-coded status badges (online=green, offline=red)
- User can register new device with push tokens
- User can view device health metrics
- Filters work correctly
- Bulk operations execute successfully

---

#### 2.2 Jobs & Task Management
**Assignee:** _Unassigned_  
**Estimate:** 5-6 days  
**Dependencies:** 2.1 (Devices Management)

- Create Jobs List page
- Add status filters (pending, running, completed, failed)
- Create Job Detail page with progress tracking
- Implement job creation form
- Add job scheduler (date/time picker)
- Show job logs viewer
- Add retry/cancel actions
- Implement job queue visualization

**Files to Create:**
```
frontend/src/
├── pages/Jobs/
│   ├── JobsList.jsx (NEW)
│   ├── JobDetail.jsx (NEW)
│   └── JobForm.jsx (NEW)
└── components/Jobs/
    ├── JobCard.jsx (NEW)
    ├── JobStatusBadge.jsx (NEW)
    ├── JobProgressBar.jsx (NEW)
    └── JobLogsViewer.jsx (NEW)
```

**Backend APIs (Already Available):**
- `GET /api/v1/jobs` - List jobs
- `POST /api/v1/jobs` - Create job
- `GET /api/v1/jobs/{id}` - Get job
- `PUT /api/v1/jobs/{id}` - Update job
- `DELETE /api/v1/jobs/{id}` - Delete job

**Acceptance Criteria:**
- User can schedule jobs for devices
- Job status updates in real-time
- User can view job execution logs
- User can retry failed jobs
- User can cancel pending jobs

---

#### 2.3 Push Notifications Management
**Assignee:** _Unassigned_  
**Estimate:** 4-5 days  
**Dependencies:** 2.1 (Devices Management)

- Integrate existing `NotificationSettings.jsx` into Settings page
- Create Notification Center page (inbox)
- Show notification history with filters
- Add mark as read/unread functionality
- Create Notification Composer page
- Implement recipient selection (devices/sites)
- Add platform selection (FCM, WNS, APNs, Web Push, MQTT)
- Create notification preview
- Add schedule for later option
- Show notification delivery stats

**Files to Create:**
```
frontend/src/
├── pages/Notifications/
│   ├── NotificationCenter.jsx (NEW)
│   ├── NotificationComposer.jsx (NEW)
│   └── NotificationSettings.jsx (MOVE from components/)
└── components/Notifications/
    ├── NotificationCard.jsx (NEW)
    ├── NotificationPreview.jsx (NEW)
    └── PlatformSelector.jsx (NEW)
```

**Backend APIs (Already Available):**
- `GET /api/v1/push/vapid-public-key` - Get VAPID key
- `POST /api/v1/push/subscribe` - Subscribe device
- `POST /api/v1/push/send` - Send notification
- `POST /api/v1/push/send-bulk` - Bulk send
- `POST /api/v1/push/mqtt/publish` - MQTT publish
- `GET /api/v1/push/platforms` - List platforms
- `POST /api/v1/push/test` - Test notification

**Acceptance Criteria:**
- User can view notification history
- User can compose and send notifications
- User can select recipients (individual/bulk)
- User can choose notification platform
- Notifications preview correctly
- Push notification settings accessible

---

#### 2.4 Real-time WebSocket Integration
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** 2.1 (Devices Management)

- Install socket.io-client
  ```bash
  cd frontend && npm install socket.io-client
  ```
- Create WebSocket service (`services/websocket.js`)
- Implement connection management
- Add event listeners:
  - `device:status` - Device status changes
  - `job:progress` - Job progress updates
  - `notification:new` - New notifications
  - `site:update` - Site changes
- Integrate with device list (auto-update status)
- Integrate with job detail (auto-update progress)
- Add connection status indicator in UI
- Handle reconnection logic
- Add error handling and fallback

**Files to Create:**
```
frontend/src/
├── services/
│   └── websocket.js (NEW)
├── components/
│   └── ConnectionStatus.jsx (NEW)
└── hooks/
    └── useWebSocket.js (NEW)
```

**Backend WebSocket (Already Available):**
- WebSocket server configured
- Device status events
- Job progress events

**Acceptance Criteria:**
- WebSocket connects on app load
- Device status updates without refresh
- Job progress updates in real-time
- Connection status shows in UI
- Reconnects automatically on disconnect
- Graceful degradation if WebSocket unavailable

---

## PHASE 3: Data Visualization & Analytics

**Goal:** Add charts, graphs, and analytics to provide insights.

### Priority: MEDIUM

#### 3.1 Dashboard Charts & Visualization
**Assignee:** _Unassigned_  
**Estimate:** 4-5 days  
**Dependencies:** 1.3 (Dashboard), 2.1 (Devices)

- Install charting library
  ```bash
  cd frontend && npm install recharts
  ```
- Add device status over time chart
- Add notification delivery rates chart
- Add job success/failure trends
- Add site activity heatmap
- Implement time range selector (24h, 7d, 30d, custom)
- Add export to PNG/SVG functionality
- Create responsive chart components

**Files to Create:**
```
frontend/src/
├── components/Charts/
│   ├── DeviceStatusChart.jsx (NEW)
│   ├── NotificationChart.jsx (NEW)
│   ├── JobTrendsChart.jsx (NEW)
│   └── SiteActivityHeatmap.jsx (NEW)
└── utils/
    └── chartHelpers.js (NEW)
```

**Backend APIs Needed:**
- `GET /api/v1/analytics/device-status` - Device status history
- `GET /api/v1/analytics/notifications` - Notification stats
- `GET /api/v1/analytics/jobs` - Job statistics
- `GET /api/v1/analytics/sites` - Site activity

**Note:** Backend analytics endpoints need to be created.

**Acceptance Criteria:**
- Charts display correctly on all screen sizes
- Data updates when time range changes
- Charts are accessible (ARIA labels)
- Export functionality works
- Loading states while fetching data

---

#### 3.2 Analytics & Reports Page
**Assignee:** _Unassigned_  
**Estimate:** 5-6 days  
**Dependencies:** 3.1 (Charts)

- Create Analytics dashboard page
- Add device uptime reports
- Add notification delivery reports
- Add job execution reports
- Implement data export (CSV, Excel, PDF)
- Add report scheduling (email reports)
- Create custom report builder

**Files to Create:**
```
frontend/src/
├── pages/Analytics/
│   ├── AnalyticsDashboard.jsx (NEW)
│   ├── DeviceReports.jsx (NEW)
│   ├── NotificationReports.jsx (NEW)
│   └── JobReports.jsx (NEW)
└── components/Analytics/
    ├── ReportCard.jsx (NEW)
    ├── ExportButton.jsx (NEW)
    └── DateRangePicker.jsx (NEW)
```

**Packages to Install:**
```bash
npm install date-fns react-day-picker
npm install file-saver xlsx # For Excel export
npm install jspdf # For PDF export
```

**Acceptance Criteria:**
- Reports display accurate data
- User can export to CSV/Excel/PDF
- Date range selection works
- Comparison views functional
- Reports load within 3 seconds

---

## PHASE 4: UI/UX Polish

**Goal:** Enhance user experience with advanced UI features.

### Priority: MEDIUM

#### 4.1 UI Components & Theming
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** None

- Install additional shadcn/ui components
  ```bash
  npx shadcn@latest add toast skeleton alert-dialog dropdown-menu tabs
  ```
- Implement dark mode toggle
- Add loading skeletons for all pages
- Create toast notification system
- Add confirmation dialogs (delete actions)
- Implement error boundaries
- Add empty states (no data)
- Create 404 page

**Files to Create:**
```
frontend/src/
├── components/ui/
│   └── theme-toggle.jsx (NEW)
├── components/
│   ├── ErrorBoundary.jsx (NEW)
│   ├── EmptyState.jsx (NEW)
│   └── LoadingSkeleton.jsx (NEW)
└── pages/
    └── NotFound.jsx (NEW)
```

**Acceptance Criteria:**
- Dark mode persists across sessions
- All CRUD actions show confirmation
- Loading states on all async operations
- Toast notifications for success/error
- Errors caught by error boundaries
- 404 page displays correctly

---

#### 4.2 Forms & Validation
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** 4.1 (UI Components)

- Install form libraries
  ```bash
  npm install react-hook-form zod @hookform/resolvers
  ```
- Refactor all forms to use react-hook-form
- Add Zod schemas for validation
- Implement field-level validation
- Add helpful error messages
- Create reusable form components
- Add auto-save drafts (optional)

**Files to Create:**
```
frontend/src/
├── components/Forms/
│   ├── FormField.jsx (NEW)
│   ├── FormSelect.jsx (NEW)
│   └── FormTextarea.jsx (NEW)
└── schemas/
    ├── siteSchema.js (NEW)
    ├── deviceSchema.js (NEW)
    └── jobSchema.js (NEW)
```

**Acceptance Criteria:**
- All forms use react-hook-form
- Validation works on blur and submit
- Error messages are clear
- Forms are accessible (ARIA)
- Submit buttons disabled during submission

---

#### 4.3 Advanced UX Features
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** 4.1, 4.2

- Implement search with debouncing
- Add infinite scroll for large lists
- Implement drag-and-drop reordering (job queue)
- Add keyboard shortcuts (Cmd+K search, etc.)
- Create command palette (Cmd+K)
- Add breadcrumb navigation
- Implement undo/redo for actions
- Add tour/onboarding for new users

**Packages to Install:**
```bash
npm install cmdk # Command palette
npm install @dnd-kit/core @dnd-kit/sortable # Drag & drop
npm install react-hotkeys-hook # Keyboard shortcuts
```

**Acceptance Criteria:**
- Search debounces input (300ms delay)
- Keyboard shortcuts work
- Command palette accessible
- Drag-and-drop smooth on all devices
- Tour guides new users

---

## PHASE 5: Testing & Quality

**Goal:** Ensure code quality and reliability through comprehensive testing.

### Priority: HIGH

#### 5.1 Frontend Unit Tests
**Assignee:** _Unassigned_  
**Estimate:** 5-6 days  
**Dependencies:** All frontend features

- Write tests for API service (`api.js`)
- Write tests for Push notification manager
- Write tests for WebSocket service
- Write tests for authentication store
- Write tests for utility functions
- Achieve 70%+ code coverage
- Set up coverage reporting

**Files to Create:**
```
frontend/tests/
├── services/
│   ├── api.test.js (NEW)
│   ├── pushNotifications.test.js (NEW)
│   └── websocket.test.js (NEW)
├── store/
│   └── authStore.test.js (NEW)
└── utils/
    └── helpers.test.js (NEW)
```

**Run Tests:**
```bash
cd frontend && npm test
npm run test:coverage
```

**Acceptance Criteria:**
- All tests pass
- Code coverage ≥ 70%
- No console errors during tests
- Tests run in CI pipeline

---

#### 5.2 Component Tests
**Assignee:** _Unassigned_  
**Estimate:** 4-5 days  
**Dependencies:** 5.1 (Unit Tests)

- Install testing library
  ```bash
  npm install -D @testing-library/react @testing-library/user-event
  ```
- Write tests for NotificationSettings component
- Write tests for DeviceCard component
- Write tests for SiteForm component
- Write tests for Dashboard components
- Test user interactions (clicks, inputs)
- Test conditional rendering
- Test error states

**Files to Create:**
```
frontend/tests/components/
├── NotificationSettings.test.jsx (NEW)
├── Dashboard/
│   └── MetricCard.test.jsx (NEW)
├── Devices/
│   └── DeviceCard.test.jsx (NEW)
└── Sites/
    └── SiteForm.test.jsx (NEW)
```

**Acceptance Criteria:**
- Component tests pass
- User interactions tested
- Accessibility issues caught
- Snapshot tests for UI consistency

---

#### 5.3 End-to-End Tests
**Assignee:** _Unassigned_  
**Estimate:** 5-6 days  
**Dependencies:** All features complete

- Install Playwright
  ```bash
  npm install -D @playwright/test
  npx playwright install
  ```
- Write E2E test for login flow
- Write E2E test for create site → add device → send notification
- Write E2E test for job scheduling
- Write E2E test for real-time updates
- Write E2E test for push notification subscription
- Set up E2E tests in CI
- Create test data fixtures

**Files to Create:**
```
frontend/e2e/
├── auth.spec.js (NEW)
├── sites.spec.js (NEW)
├── devices.spec.js (NEW)
├── notifications.spec.js (NEW)
└── jobs.spec.js (NEW)
```

**Run E2E Tests:**
```bash
npx playwright test
npx playwright test --ui # Interactive mode
```

**Acceptance Criteria:**
- Critical user flows tested
- Tests run on multiple browsers
- Tests run in CI pipeline
- Screenshots on failure

---

#### 5.4 Backend Testing Improvements
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** None

- Review existing backend tests (currently ~85%)
- Add missing test cases for new endpoints
- Write integration tests for push notifications
- Add performance tests (load testing)
- Test error handling and edge cases
- Achieve 90%+ backend coverage

**Files to Review/Update:**
```
backend/tests/
├── test_push_notifications.py (REVIEW)
├── test_devices.py (REVIEW)
└── test_integration.py (NEW)
```

**Run Backend Tests:**
```bash
cd backend
pytest --cov=homepot --cov-report=html
```

**Acceptance Criteria:**
- Backend coverage ≥ 90%
- All edge cases tested
- Integration tests pass
- Performance acceptable

---

## PHASE 6: Deployment & Production

**Goal:** Prepare application for production deployment.

### Priority: CRITICAL

#### 6.1 Production Configuration
**Assignee:** _Unassigned_  
**Estimate:** 2-3 days  
**Dependencies:** All features complete

- Create production environment files
- Configure production database (PostgreSQL recommended)
- Set up Redis for production
- Configure CORS for production domain
- Set up environment variable management
- Add rate limiting
- Configure logging (structured logs)
- Set up error tracking (Sentry)

**Files to Create/Update:**
```
backend/
├── .env.production (NEW - template)
└── homepot/
    └── config.py (UPDATE - production settings)

frontend/
└── .env.production (NEW)
```

**Acceptance Criteria:**
- Production config separated from dev
- Secrets not committed to git
- Environment variables documented
- Error tracking configured

---

#### 6.2 Docker Production Build
**Assignee:** _Unassigned_  
**Estimate:** 2-3 days  
**Dependencies:** 6.1 (Production Config)

- Optimize Dockerfile for production
- Create multi-stage builds
- Update docker-compose for production
- Add nginx reverse proxy
- Configure SSL/TLS certificates
- Set up health checks
- Add volume mounts for data persistence
- Configure container restart policies

**Files to Update:**
```
├── Dockerfile (UPDATE - multi-stage build)
├── docker-compose.yml (UPDATE)
└── docker-compose.prod.yml (NEW)
```

**Docker Commands:**
```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

**Acceptance Criteria:**
- Docker images build successfully
- Containers run in production mode
- Health checks pass
- Data persists across restarts
- SSL/TLS configured

---

#### 6.3 CI/CD Pipeline
**Assignee:** _Unassigned_  
**Estimate:** 3-4 days  
**Dependencies:** 6.2 (Docker), 5.x (All testing)

- Create GitHub Actions workflow for backend
  - Run tests on push
  - Build Docker image
  - Push to container registry
  - Deploy to staging
- Create GitHub Actions workflow for frontend
  - Run tests and linting
  - Build production bundle
  - Deploy to hosting (Vercel/Netlify/AWS)
- Set up automatic deployments on merge to main
- Add deployment notifications (Slack/Discord)
- Create staging environment

**Files to Create:**
```
.github/workflows/
├── backend-ci.yml (NEW)
├── frontend-ci.yml (NEW)
└── deploy-production.yml (NEW)
```

**Acceptance Criteria:**
- Tests run automatically on PR
- Builds deploy to staging on merge
- Manual approval for production
- Rollback mechanism exists
- Team notified of deployments

---

#### 6.4 Documentation & Handoff
**Assignee:** _Unassigned_  
**Estimate:** 2-3 days  
**Dependencies:** All phases complete

- Update API documentation
- Create deployment guide
- Write operations runbook
- Document environment variables
- Create troubleshooting guide
- Add architecture diagrams
- Record demo videos
- Write user manual

**Files to Create/Update:**
```
docs/
├── api-reference.md (UPDATE)
├── deployment-production.md (NEW)
├── operations-runbook.md (NEW)
├── troubleshooting-production.md (NEW)
├── architecture-diagrams.md (UPDATE)
└── user-manual.md (NEW)
```

**Acceptance Criteria:**
- All docs up-to-date
- Deployment guide tested
- Runbook covers common issues
- Architecture diagrams current
- User manual complete

---

## PHASE 7: Future Enhancements (Backlog)

**Goal:** Advanced features for future iterations.

### Priority: LOW / FUTURE

#### 7.1 Advanced Features
- Multi-tenancy support (organizations)
- Role-based access control (RBAC) - granular permissions
- Custom dashboards (drag-and-drop widgets)
- Advanced scheduling (cron expressions)
- API rate limiting per user
- Webhooks for external integrations
- Mobile app (React Native)
- Desktop app (Electron)

#### 7.2 Integrations
- Third-party integrations:
  - Slack notifications
  - Microsoft Teams notifications
  - Email notifications (SendGrid/AWS SES)
  - SMS notifications (Twilio)
  - PagerDuty integration
- Import/Export:
  - Bulk device import (CSV)
  - Configuration backup/restore
  - Data migration tools

#### 7.3 Performance & Scalability
- Implement caching layer (Redis)
- Add database read replicas
- Implement message queue (RabbitMQ/Kafka)
- Add CDN for static assets
- Optimize database queries
- Implement lazy loading for large lists
- Add service worker for offline support
- Implement progressive web app (PWA)

#### 7.4 Security Enhancements
- Two-factor authentication (2FA)
- Single Sign-On (SSO) - SAML, OAuth
- API key management
- Audit log viewer (UI)
- Security scanning (OWASP ZAP)
- Penetration testing
- GDPR compliance features
- Data encryption at rest

---

## Quick Reference

### Prerequisites
```bash
# Backend
Python 3.12+
pip (package manager)

# Frontend  
Node.js 20+
npm (package manager)

# Optional
Docker & Docker Compose
Redis (for production)
PostgreSQL (for production)
```

### Development Workflow

**Start Development:**
```bash
# ONE COMMAND to run everything:
./scripts/test-integration.sh

# Access:
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

**Install Frontend Packages:**
```bash
cd frontend
npm install <package-name>
```

**Install Backend Packages:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install <package-name>
pip freeze > requirements.txt
```

**Run Tests:**
```bash
# Frontend
cd frontend && npm test

# Backend
cd backend && pytest

# E2E
cd frontend && npx playwright test
```

**Code Quality:**
```bash
# Frontend linting
cd frontend && npm run lint

# Backend type checking
cd backend && mypy homepot/
```

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, commit often
git add .
git commit -m "feat: your feature description"

# Push to remote
git push origin feature/your-feature-name

# Create Pull Request on GitHub
```

---

## Getting Help

### Team Communication
- **Issues:** Use GitHub Issues for bugs and feature requests
- **Discussions:** Use GitHub Discussions for questions
- **Pull Requests:** Follow PR template and request reviews

### Common Commands
```bash
# Check what's running
./scripts/test-integration.sh --quick  # Skip dependency install

# View logs
tail -f backend.log
tail -f frontend.log

# Stop services
# Press Ctrl+C in terminal running test-integration.sh

# Clean restart
rm -rf backend/venv frontend/node_modules
./scripts/test-integration.sh
```

---

## Current Sprint Focus

**Sprint Goal:** Complete Phase 1 - Core Application Structure

**Priorities:**
1. Backend-Frontend Integration (DONE)
2. Frontend Routing & Navigation (TODO)
3. Authentication Pages (TODO)
4. Main Dashboard Page (TODO)

**Blockers:** None currently

**Next Sprint:** Phase 2 - Feature Development (Devices, Jobs, Notifications)

---

> **Last Updated:** October 24, 2025  
> **Maintained By:** Engineering Team  
> **Review Frequency:** Weekly during standup
