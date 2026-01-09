# Getting Started with HOMEPOT

Welcome to **HOMEPOT** (Homogenous Cyber Management of End-Points and OT). This guide provides a straightforward path to getting the system up and running using our automated scripts.

## Prerequisites

Before starting, ensure your system meets the following requirements:

1.  **Operating System**: Linux (Ubuntu 22.04+ recommended) or macOS.
2.  **Git**: Installed and configured.
3.  **Python**: Version 3.11 or higher.
4.  **Node.js**: Version v22 (managed via `nvm` recommended).
5.  **Ollama** (Required for AI Features):
    *   **Option A (Automated)**: You can run our setup script `./scripts/setup-ollama.sh` during the installation phase.
    *   **Option B (Manual)**: Install from [ollama.com](https://ollama.com) and pull the `llama3.2` model manually.

## Quick Start Guide

Follow these three steps to launch the complete HOMEPOT system.

### Step 1: Install Dependencies

This script sets up the Python virtual environment, installs backend/AI dependencies, and configures the frontend environment.

```bash
./scripts/install.sh
```

> **Note**: If you haven't installed Ollama yet, you should also run the AI setup script to ensure the local LLM is ready:
> ```bash
> ./scripts/setup-ollama.sh
> ```

### Step 2: Initialize Database

Initialize the PostgreSQL database with the required schema and demo data.

```bash
./scripts/init-postgresql.sh
```

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
