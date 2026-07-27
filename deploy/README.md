# HOMEPOT Dev Server — Traditional Deployment

This directory contains systemd units, environment overrides, and a setup
script for deploying HOMEPOT on a Linux dev server **without Docker**.

## Quick start

```bash
sudo ./scripts/setup-dev-server.sh
```

The script above runs the full setup.  To do it step by step:

## 1. Create the homepot user

```bash
sudo useradd --system --user-group --create-home --home-dir /opt/homepot homepot
```

## 2. Install dependencies

```bash
sudo apt-get install python3.11 python3.11-venv nodejs postgresql
```

## 3. Clone the project

```bash
sudo -u homepot git clone https://github.com/brunel-opensim/homepot-client.git /opt/homepot
cd /opt/homepot
```

## 4. Set up the Python virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e backend/
```

## 5. Install and build the frontend

```bash
cd frontend
npm install
npm run build
cd ..
```

## 6. Configure the environment

```bash
cp deploy/env-override.sh /opt/homepot/deploy/env-override.sh
# Edit /opt/homepot/deploy/env-override.sh with your database credentials and secrets
```

## 7. Provision the database

```bash
./scripts/init-postgresql.sh
```

## 8. Install systemd services

```bash
sudo cp deploy/homepot-api.service /etc/systemd/system/
sudo cp deploy/homepot-agent.service /etc/systemd/system/
sudo cp deploy/homepot-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
```

## 9. Enable and start services

```bash
sudo systemctl enable --now homepot-api
sudo systemctl enable --now homepot-frontend
# Only if a real device is attached:
sudo systemctl enable --now homepot-agent
```

## 10. Verify

```bash
curl -s http://localhost:8000/health | jq .
# Or open http://localhost:3000 in a browser
```

## Service management

| Command | Description |
|---|---|
| `sudo journalctl -u homepot-api -f` | Follow API logs |
| `sudo journalctl -u homepot-agent -f` | Follow agent logs |
| `sudo systemctl restart homepot-api` | Restart the API |
| `sudo systemctl status homepot-*` | Check all service statuses |

## Files

| File | Description |
|---|---|
| `homepot-api.service` | Systemd unit for the FastAPI backend (uvicorn on port 8000) |
| `homepot-agent.service` | Systemd unit for the real device agent |
| `homepot-frontend.service` | Systemd unit for the built dashboard (Python HTTP server on port 3000) |
| `env-override.sh` | Environment variable overrides (DB URL, secrets, CORS origins) |
| `setup-dev-server.sh` | One-shot opinionated setup script |
