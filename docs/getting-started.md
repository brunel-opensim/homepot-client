# Getting Started with HOMEPOT

Welcome to **HOMEPOT** (Homogenous Cyber Management of End-Points and OT) - an enterprise-grade POS payment gateway management system for the HOMEPOT consortium.

## Quick Start (5 minutes)

### Prerequisites

- **Python**: 3.9 or higher
- **Git**: Latest version
- **HOMEPOT Consortium Access**: Repository access required

### Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/brunel-opensim/homepot-client.git
cd homepot-client

# 2. Install dependencies
./scripts/install.sh --dev

# 3. Check the version
python -m homepot_client.cli version

# 4. More information
python -m homepot_client.cli info

# 5. Test configuration
python -m pytest tests/test_client.py -v --disable-warnings
```

When ready to start the client:

```bash
# 6. Start the system
python -m homepot_client.main
```

Or, specifically set arguments:

```bash
python -m uvicorn src.homepot_client.main:app --host 0.0.0.0 --port 8000 --reload
```

### Verify Installation

Open a new terminal and test the system:

```bash
# Check system health
curl http://localhost:8000/health | python3 -m json.tool
# Expected: {"status":"healthy","client_connected":true,"version":"0.1.0"}

# View all POS sites
curl http://localhost:8000/sites | python3 -m json.tool
# Expected: Array of 14 pre-configured sites
```

Expected output for health check:

```json
{
    "status": "healthy",
    "client_connected": true,
    "version": "0.1.0",
    "timestamp": 2021.463
}
```

### Access the System

- **Dashboard**: [http://localhost:8000](http://localhost:8000) - Real-time POS monitoring
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) - Interactive API explorer
- **Health**: [http://localhost:8000/health](http://localhost:8000/health) - System status

## What You Have

Congratulations! You now have a complete enterprise POS management system with:

- **14 Pre-configured Sites** (restaurants, retail stores)
- **23+ Active POS Agents** (realistic terminal simulation)
- **Real-time Dashboard** (live monitoring with WebSocket updates)
- **Enterprise Audit Logging** (compliance-ready event tracking)
- **Complete REST API** (comprehensive device management)

## Next Steps

### For New Users
- **[POS Management Guide](pos-management.md)** - Manage sites, devices, and jobs
- **[Dashboard Guide](real-time-dashboard.md)** - Real-time monitoring and WebSocket features

### For Developers
- **[Agent Simulation Guide](agent-simulation.md)** - POS terminal simulation and management
- **[Development Guide](development-guide.md)** - Testing, code quality, and contributing

### For Operators
- **[Audit & Compliance Guide](audit-compliance.md)** - Enterprise logging and reporting
- **[Deployment Guide](deployment-guide.md)** - Production deployment with Docker

## Troubleshooting

### Common Issues

**"Address already in use" Error:**
```bash
# Kill process using port 8000
sudo kill $(lsof -ti :8000)

# Restart the server
python -m homepot_client.main
```

**Connection Issues:**
```bash
# Check if server is running
curl http://localhost:8000/health

# If connection refused, restart
python -m homepot_client.main
```

### Getting Help

- **[GitHub Issues](https://github.com/brunel-opensim/homepot-client/issues)** - Bug reports and feature requests
- **[Contributing Guide](../CONTRIBUTING.md)** - Development guidelines
- **[Security Policy](../SECURITY.md)** - Vulnerability reporting

---

*Ready to explore? Start with the [POS Management Guide](pos-management.md) to learn how to manage your POS ecosystem.*
