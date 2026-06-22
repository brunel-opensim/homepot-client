# HOMEPOT User App — Test & Integration Report


## 1. What We Have Built

All 4 pages of the HOMEPOT User App are complete from the frontend (UI) side.

| Page | Description | UI Status |
|---|---|---|
| Page 1 — Setup Wizard | 3-step device enrollment flow | Done |
| Page 2 — Home Dashboard | Status badge, gauge rings, heartbeat | Done |
| Page 3 — Permissions | 4 access control toggles | Done |
| Page 4 — Device Info | DNA table, check updates, unpair | Done |


---

### Page 1 — Setup Wizard

- Next button is disabled until Site ID is entered — **works**
- Step indicator progresses 1 → 2 → 3 correctly — **works**
- SSO Login button shows loading spinner — **works**
- Back button on Step 2 returns to Step 1 — **works**
- Complete Setup button navigates to Home Dashboard — **works**

**Result: PASS**

---

### Page 2 — Home Dashboard

- SECURE — ONLINE status badge shows in green — **works**
- Gauge rings display CPU / Memory / Disk — **works**
- Heartbeat timestamp updates every second — **works**
- Tab bar navigation (Home / Perms / Settings) — **works**

**Result: PASS**

---

### Page 3 — Permissions

- All 4 toggles load with correct ON/OFF states — **works**
- Toggle click changes state correctly — **works**
- Warning banner "Syncing changes..." appears on toggle — **works**

**Result: PASS**

---

### Page 4 — Device Info & Settings

- Device DNA table shows 6 rows — **works**
- Check for Updates shows spinner then success message — **works**
- Disconnect & Unpair shows confirm dialog — **works**
- Cancel button in confirm dialog works — **works**

**Result: PASS**

---

## 3. Current Data — Simulated 

**All data is currently simulated (fake/hardcoded). No real device data is being read.**

| Data | Current Source | Real Source (Future) |
|---|---|---|
| CPU / Memory / Disk | Hardcoded — `42%, 61%, 28%` | Dealdio IPC agent (Phase 3) |
| Device hostname | From localStorage | Real OS hostname |
| MAC Address | Hardcoded — `A1:B2:C3:D4:E5:F6` | Dealdio IPC agent |
| Local IP | Hardcoded — `192.168.1.101` | Dealdio IPC agent |
| OS details | Hardcoded — `Linux 6.17` | Dealdio IPC agent |
| Heartbeat | UI timer only — not sent to backend | Real API call |
| Token after setup | Mock token in localStorage | Real `api_key` from backend |

---

## 4. Issues Found

### Device DNA Table Shows Wrong Values

**Page:** Page 4 — Device Info & Settings

**What happens:** The DNA table shows hardcoded values regardless of what the user entered during setup.
- Hostname shows `My-Device` instead of the device name entered
- Site ID shows `site-1234` instead of the actual Site ID entered
- MAC Address, Local IP, OS — all fake values

**Impact:** Medium — a user who sets up with their real Site ID will see a different Site ID in Settings, which is confusing.

**Fix:** This will be resolved once the backend API integration is complete and real device data is available.

---

## 5. Backend Connection Status

| Item | Status |
|---|---|
| Backend API at `localhost:8000` | Not reachable — backend not running locally |
| All pages | Working on mock / localStorage data only |
| Real device registration | Not happening — no backend connection |

---

## 6. API Endpoints

### Already Built (Ready to wire)

| # | Endpoint | Method | Page |
|---|---|---|---|
| 1 | `/api/v1/devices/provision` | POST | Page 1 — Setup Wizard |
| 2 | `/api/v1/agent/heartbeat` | POST | Page 2 — Home Dashboard |
| 3 | `/api/v1/agent/telemetry` | POST | Page 2 — Home Dashboard |
| 4 | `/api/v1/agent/{device_id}/status` | GET | Page 2 — Home Dashboard |
| 5 | `/api/v1/agent/device-dna` | POST | Page 4 — Device Info |

> **Note:** These endpoints are already built on the backend. Frontend integration is pending and will be implemented once the backend base URL is confirmed.

### Need to be Built 

| # | Endpoint | Method | Page |
|---|---|---|---|
| 6 | `/api/v1/agent/{device_id}/permissions` | GET | Page 3 — Permissions |
| 7 | `/api/v1/agent/{device_id}/permissions` | PATCH | Page 3 — Permissions |
| 8 | `/api/v1/agent/{device_id}/unpair` | POST | Page 4 — Device Info |
| 9 | `/api/v1/agent/version/latest` | GET | Page 4 — Device Info |

> Full request and response details for all endpoints: `docs/user-app-api-research.md`

---

## 7. What is Next

### GetFudo  — To Do

- Fix Next button issue in Setup Wizard Step 1
- Fix DNA table to read Site ID and device name from localStorage correctly
- Wire existing APIs (provision, heartbeat, telemetry, status, device-dna) once backend URL is confirmed
- Update gauge rings with real IPC data once Dealdio port is confirmed
  > Gauge rings are the circular charts on Page 2 showing CPU, Memory, and Disk usage. Currently they display hardcoded values. Real values will come from the Dealdio Python agent once the IPC port is confirmed.


### Future — Phase 3

- Connect gauge rings to real Dealdio IPC data
- Package User App as Android APK for real device testing
- Move from localhost to a server for remote testing

---

## 8. Server Deployment Research (Free Plans)

As discussed in the meeting, moving from localhost to a real server is the next step. Below are free options for hosting the frontend, backend, and database.

---

### Frontend (React User App + Admin Dashboard)

**Netlify**
- Free plan: 100 GB bandwidth per month
- Storage: 1 GB per site
- Supports static builds (Vite/React)
- Custom domain supported
- Easy GitHub integration — auto deploy on push

**Vercel**
- Free plan: 100 GB bandwidth per month
- Storage: 1 GB
- Supports static and server-side rendering
- Easy GitHub integration
- Best for React/Vite apps

**Render (Static Sites)**
- Free plan: Unlimited bandwidth for static sites
- Storage: Not specified for static
- Auto deploy from GitHub
- Free custom domain with SSL

---

### Backend (FastAPI / Python)

**Render (Web Service)**
- Free plan: 512 MB RAM, 0.1 CPU
- Disk: 1 GB
- Limitation: Server spins down after 15 minutes of no activity — slow on first request
- Good for testing, not for production

**Railway**
- Free plan: $5 credit per month (roughly 500 hours)
- RAM: 512 MB
- Disk: 1 GB
- Does not spin down like Render
- Good for small backend services

**Fly.io**
- Free plan: 3 shared VMs, 256 MB RAM each
- Disk: 3 GB total
- Does not spin down
- Requires Docker setup

---

### Database (PostgreSQL)

**Neon**
- Free plan: 0.5 GB storage
- 1 project, 1 database
- Serverless PostgreSQL — scales automatically
- Best lightweight option for this project

**Supabase**
- Free plan: 500 MB storage
- 2 projects
- PostgreSQL with built-in API
- Includes authentication (could help with SSO later)

**Railway (PostgreSQL)**
- Free plan: Included in $5 monthly credit
- Storage: 1 GB
- Easy to connect with Railway backend service

---

### Recommended Setup (Free Tier)

| Part | Recommended Service | Reason |
|---|---|---|
| Frontend (User App + Dashboard) | Netlify or Vercel | Easy, fast, free, GitHub auto-deploy |
| Backend (FastAPI) | Railway | No spin-down, $5 free credit | or Render 
| Database (PostgreSQL) | Neon | Free 0.5 GB, serverless, easy setup |

> **Note:** This setup is suitable for testing and demo purposes. 

---

