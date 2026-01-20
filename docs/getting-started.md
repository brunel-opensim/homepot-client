# Getting Started with HOMEPOT

Welcome to **HOMEPOT** (Homogenous Cyber Management of End-Points and OT). This guide provides a straightforward path to getting the system up and running using our automated scripts.

## Prerequisites

Before starting, ensure your system meets the following requirements:

1.  **Operating System**: Linux (Ubuntu 22.04+ recommended) or macOS.
2.  **Git**: Installed and configured.
3.  **Package Manager**:
    *   **macOS**: [Homebrew](https://brew.sh/) is required for automated installation of dependencies.
    *   **Linux**: `apt` (for Ubuntu/Debian).
4.  **Python**: Version 3.11 or higher.
5.  **Node.js**: Version v22.
    *   *(Note: Our install script will attempt to install this automatically if missing.)*
6.  **Ollama** (Required for AI Features):
    *   **Option A (Automated)**: Run `./scripts/setup-ollama.sh` (uses Homebrew on Mac).
    *   **Option B (Manual)**: Install from [ollama.com](https://ollama.com) and pull the `llama3.2` model manually.

## Quick Start Guide

Follow these three steps to launch the complete HOMEPOT system.

### Step 1: Install Dependencies

Make scripts executable and run the installer. This script sets up the Python virtual environment, installs backend/AI dependencies, and automatically installs/configures Node.js and frontend dependencies.

```bash
chmod +x scripts/*.sh
./scripts/install.sh
```

> **Note**: If you haven't installed Ollama yet, run the AI setup script next. On macOS, this will use Homebrew to install Ollama and pull the required model.
> ```bash
> ./scripts/setup-ollama.sh
> ```

### Step 2: Initialize Database

Initialize the PostgreSQL database with the required schema and demo data. This script detects your local PostgreSQL installation (via Homebrew on macOS or system packages on Linux) and ensures the service is running before creating the database.

```bash
./scripts/init-postgresql.sh
```

> **Note**: This setup uses a local PostgreSQL instance and does not require Docker.


### Step 3: Start the Application

Use the following command to ensure any previous instances are stopped before starting the new session. This launches both the backend API and the frontend dashboard.

```bash
./scripts/stop-website.sh && ./scripts/start-website.sh
```

---

## What's Next?

Once the system is running, you can access:

- **Dashboard**: [http://localhost:5173](http://localhost:5173)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

For detailed development information, refer to the [Development Guide](development-guide.md).
