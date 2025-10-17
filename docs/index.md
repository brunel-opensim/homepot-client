# HOMEPOT Documentation

Welcome to the HOMEPOT (Homogenous Cyber Management of End-Points and OT) documentation. HOMEPOT is an enterprise-grade POS payment gateway management system for the HOMEPOT consortium.

## Quick Start

New to HOMEPOT? Start here:

- **[Getting Started](getting-started.md)** - Installation and basic setup

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
- **[Deployment Guide](deployment-guide.md)** - Production deployment with Docker

## Platform Integration Guides

Push notification integrations for different platforms:

- **[Push Notification System](push-notification.md)** - Overview and architecture
- **[Firebase Cloud Messaging (FCM)](fcm-linux-integration.md)** - Android/Linux device push notifications
- **[Windows Notification Service (WNS)](wns-windows-integration.md)** - Windows device push notifications

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
- **[Contributing Guide](../CONTRIBUTING.md)** - Development guidelines
- **[Security Policy](../SECURITY.md)** - Vulnerability reporting

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                HOMEPOT POS Management Dashboard                 │
│                   (Real-time Monitoring)                       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Live Site     │  │   POS Agent     │  │  Audit Trail    │ │
│  │   Monitoring    │  │   Simulation    │  │   & Reports     │ │
│  │   (WebSocket)   │  │   (23+ agents)  │  │   (Compliance)  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│                      FastAPI REST API                          │
│               (Sites, Devices, Jobs, Audit)                    │
├─────────────────────────────────────────────────────────────────┤
│                     Database Layer                             │
│          (Sites, Devices, Jobs, Users, Audit Logs)            │
└─────────────────────────────────────────────────────────────────┘
```

---

*Ready to get started? Begin with the [Getting Started Guide](getting-started.md) for a 5-minute setup.*
