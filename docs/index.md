# HOMEPOT Client Documentation

Welcome to the HOMEPOT Client documentation! This comprehensive guide will help you get started with the HOMEPOT IoT device management platform.

## Quick Navigation

### For New Users
- **[Getting Started](getting-started.md)** - First time setup
- **[Running Locally](running-locally.md)** - How to run the application
- **[Integration Guide](integration-guide.md)** - Complete setup and usage guide

### For Developers
- **[Engineering TODO](engineering-todo.md)** - Task list with priorities
- **[Development Guide](development-guide.md)** - How to contribute
- **[Testing Guide](testing-guide.md)** - How to test your code

### For Stakeholders
- **[Project Vision](../PROJECT_VISION.md)** - Strategic roadmap
- **[Integration Summary](../INTEGRATION_SUMMARY.md)** - What's accomplished

## New Documentation (October 2025)

### Integration Guide
**2000+ lines** - Your complete technical reference covering architecture, installation, API reference, frontend guide, push notifications (all 5 platforms), testing, deployment, and troubleshooting.

[Read Integration Guide →](integration-guide.md)

### Engineering TODO
**1500+ lines** - Clear, actionable task list with phase-by-phase breakdown, priorities, estimates, acceptance criteria, and quick reference commands.

[Read Engineering TODO →](engineering-todo.md)

### Project Vision
**900+ lines** - Strategic overview with executive summary, 8-phase roadmap, timelines, success metrics, and team information.

[Read Project Vision →](../PROJECT_VISION.md)

## Quick Start

```bash
# ONE COMMAND to run everything:
./scripts/test-integration.sh

# Access:
# Frontend: http://localhost:5173
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Feature Guides

Explore HOMEPOT's capabilities:

- **[POS Management](pos-management.md)** - Manage sites, devices, and jobs
- **[Real-time Dashboard](real-time-dashboard.md)** - Live monitoring and WebSocket features
- **[Agent Simulation](agent-simulation.md)** - POS terminal simulation and management
- **[Audit & Compliance](audit-compliance.md)** - Enterprise logging and reporting

## Technical Documentation

For developers and system administrators:

- **[Development Guide](development-guide.md)** - Testing, code quality, and contributing
- **[Database Guide](database-guide.md)** - Database setup, management, and usage

## Platform Integration Guides

Push notification integrations for different platforms:

- **[Push Notification System](push-notification.md)** - Overview and architecture
- **[Firebase Cloud Messaging (FCM)](fcm-linux-integration.md)** - Android/Linux device push notifications
- **[Windows Notification Service (WNS)](wns-windows-integration.md)** - Windows device push notifications
- **[Apple Push Notification service (APNs)](apns-apple-integration.md)** - iOS/macOS/watchOS/tvOS device push notifications

## System Overview

HOMEPOT is a complete **four-phase enterprise POS management system**:

### Phase 1: Core Infrastructure
- SQLite/PostgreSQL database with comprehensive models
- Complete CRUD operations for sites, devices, jobs, and users
- Robust error handling and transaction management

### Phase 2: Enhanced API & Dashboard
- FastAPI application with automatic documentation
- WebSocket-powered real-time dashboard
- Interactive monitoring interface

### Phase 3: Agent Simulation
- 23+ realistic POS terminal simulators
- State machine-driven behavior (Idle → Updating → Health Check)
- Realistic hardware metrics and error simulation

### Phase 4: Audit & Compliance
- Enterprise-grade audit logging (20+ event types)
- Compliance-ready event tracking
- Real-time audit statistics and reporting

## What's Included

Out of the box, HOMEPOT provides:

- **14 Pre-configured Sites** (restaurants, retail stores)
- **23+ Active POS Agents** (realistic terminal simulation)
- **Real-time Dashboard** (live monitoring with WebSocket updates)
- **Enterprise Audit Logging** (compliance-ready event tracking)
- **Complete REST API** (comprehensive device management)
- **Interactive Documentation** (Swagger/OpenAPI interface)

## Getting Help

- **[GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)** - Bug reports and feature requests
- **[Collaboration Guide](collaboration-guide.md)** - Development and contribution guidelines
- **[Development Guide](development-guide.md)** - Testing and code quality

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
                 HOMEPOT POS Management Dashboard                 
                      (Real-time Monitoring)                       
├─────────────────────────────────────────────────────────────────┤
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  
       Live Site            POS Agent            Audit Trail       
       Monitoring           Simulation            & Reports        
       (WebSocket)          (23+ agents)         (Compliance)     
   └─────────────────┘  └─────────────────┘  └─────────────────┘  
├─────────────────────────────────────────────────────────────────┤
                       FastAPI REST API                           
                (Sites, Devices, Jobs, Audit)                     
├─────────────────────────────────────────────────────────────────┤
                      Database Layer                              
           (Sites, Devices, Jobs, Users, Audit Logs)             
└─────────────────────────────────────────────────────────────────┘
```

---

*Ready to get started? Begin with the [Getting Started Guide](getting-started.md) for a 5-minute setup.*
