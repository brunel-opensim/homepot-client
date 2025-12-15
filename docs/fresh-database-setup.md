# Fresh Database Setup Complete

**Date:** December 10, 2025  
**Branch:** feature/analytics-validation-script (PR#60)  
**Purpose:** Clean database for new user validation and ICCS paper data collection

## What Was Done

### 1. Complete Database Reset
```sql
DROP DATABASE IF EXISTS homepot_db;
DROP USER IF EXISTS homepot_user;
CREATE USER homepot_user WITH PASSWORD 'homepot_dev_password';
CREATE DATABASE homepot_db OWNER homepot_user;
GRANT ALL PRIVILEGES ON DATABASE homepot_db TO homepot_user;
```

### 2. All Tables Created (11 Total)

**Core Tables (6):**
- `users` - Authentication and user management
- `sites` - Multi-site deployment locations
- `devices` - IoT device registry
- `jobs` - Device management jobs
- `health_checks` - System health monitoring
- `audit_logs` - Audit trail

**Analytics Tables (5):**
- `api_request_logs` - Automatic API request tracking
- `user_activities` - Frontend interaction analytics
- `device_state_history` - Device lifecycle events
- `job_outcomes` - Job success/failure patterns
- `error_logs` - System error tracking

### 3. Seed Data Created

**Test User:**
- Email: `analytics-test@example.com`
- Password: `testpass123`
- Role: Regular user (not admin)

**Sites (3):**
- `site-001` - Main Store - Downtown (5 POS terminals)
- `site-002` - West Branch (3 POS terminals)
- `site-003` - East Side Mall (4 POS terminals)

**Devices (12):**
- POS-001 through POS-012
- All marked as "online"
- Distributed across 3 sites

## Database Configuration

**Connection Details:**
```
Host: localhost
Port: 5432
Database: homepot_db
User: homepot_user
Password: homepot_dev_password
```

**Connection String:**
```
postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db
```

**Important:** The backend uses credentials from `backend/.env` file, which is configured with `homepot_dev_password`. If the `.env` file is missing, the backend falls back to default credentials in `config.py`.

### Password-Free Access Setup (Recommended)

To avoid password prompts when working with the database, run:

```bash
./scripts/setup-pgpass.sh
```

This creates a `~/.pgpass` file with your credentials, allowing seamless database access:

```bash
# No password prompt needed!
psql -h localhost -U homepot_user -d homepot_db
./scripts/query-db.sh count
```

**Alternative approaches:**
1. **Set environment variable** (temporary for current session):
   ```bash
   export PGPASSWORD='homepot_dev_password'
   psql -h localhost -U homepot_user -d homepot_db
   ```

2. **Use connection string**:
   ```bash
   psql "postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db"
   ```

See [Database Password Management](#database-password-management) section below for details.

## Issues Resolved

### Issue 1: Site ID Type Mismatch 
**Problem:** User code incorrectly used `site.id` (INTEGER) instead of `site.site_id` (VARCHAR)

**Note:** The `init-postgresql.sh` script works correctly. The issue occurred when the developer used the wrong field in their own code.

**Fix Applied by Developer:**
```python
# Wrong (lines 156, 168, 180):
device.site_id = site1.id  # INTEGER

# Correct:
device.site_id = site1.site_id  # VARCHAR
```

**Root Cause:** Site model has two ID fields:
- `id` (INTEGER) - Database primary key
- `site_id` (VARCHAR) - Business identifier (e.g., "site-001")

**Best Practice:** Always use `site_id` (string) for foreign key relationships.

### Issue 2: Analytics API Authentication
**Problem:** `POST /api/v1/analytics/user-activity` returns `{"detail": "Failed to log activity"}`

**Root Cause:** Missing Authorization header (JWT Bearer token required)

**Solution - Three Steps:**

#### Step 1: Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "analytics-test@example.com",
    "password": "testpass123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Step 2: Extract Token
Save the `access_token` value from the response.

#### Step 3: Use Token
```bash
curl -X POST http://localhost:8000/api/v1/analytics/user-activity \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "activity_type": "search",
    "page_url": "/dashboard",
    "search_query": "device status",
    "extra_data": {
      "results_count": 5
    }
  }'
```

**Success Response:**
```json
{
  "message": "Activity logged successfully",
  "activity_id": 1
}
```

## Testing Fresh Database

### Start Backend Server
```bash
cd /home/mghorbani/workspace/homepot-client/backend
source venv/bin/activate
uvicorn homepot.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Validation Tests
```bash
cd /home/mghorbani/workspace/homepot-client
bash scripts/run-validation-test.sh
```

### Verify Data
```bash
# Check record counts
sudo -u postgres psql -d homepot_db -c "
SELECT 'Users:' as table_name, COUNT(*)::text as count FROM users
UNION ALL SELECT 'Sites:', COUNT(*)::text FROM sites
UNION ALL SELECT 'Devices:', COUNT(*)::text FROM devices
UNION ALL SELECT 'User Activities:', COUNT(*)::text FROM user_activities;
"
```

## Known Issues

### 1. Datetime Timezone Inconsistency
**Status:** Works but has deprecation warnings

**Problem:** Two different Base classes use different datetime approaches:
- `UserModel.py`: Uses `datetime.utcnow()` (deprecated, naive datetime)
- `models.py`: Uses `datetime.now(timezone.utc)` (modern, timezone-aware)

**Impact:** 
- Seed data uses naive datetime to match UserModel schema
- Deprecation warnings appear (harmless but should be fixed)

**Recommendation:** Standardize on timezone-aware datetime:
```python
# Replace this:
created_at = Column(DateTime, default=datetime.utcnow)

# With this:
from datetime import datetime, timezone
created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

### 2. bcrypt Version Warning
**Status:** Harmless, functionality works

**Warning:** `(trapped) error reading bcrypt version`

**Cause:** bcrypt module structure changed in newer versions

**Impact:** None - password hashing works correctly

## Next Steps

### For Developer (@radhakrishnan-getfudogroup)

1. **Test Analytics API:**
   - Start backend server
   - Follow authentication steps above
   - Test all analytics endpoints with Bearer token

2. **Create GitHub Issue:**
   - Document site_id type mismatch (resolved)
   - Document analytics authentication requirement
   - Include code examples from this document

3. **Validation:**
   - Run `bash scripts/run-validation-test.sh`
   - Verify all tests pass with fresh database
   - Report any failures

### For ICCS Paper Data Collection

1. **Start Fresh:**
   - Database is clean, no legacy data
   - All analytics tables ready
   - Seed data provides baseline

2. **Collect Metrics:**
   - Run system for 3-5 days
   - Analytics tables will capture:
     - API request patterns
     - User interaction data
     - Device state changes
     - Job outcomes
     - Error patterns

3. **Extract Data:**
   ```sql
   -- API request metrics
   SELECT COUNT(*), AVG(response_time), endpoint 
   FROM api_request_logs 
   GROUP BY endpoint;
   
   -- User activity patterns
   SELECT activity_type, COUNT(*) 
   FROM user_activities 
   GROUP BY activity_type;
   
   -- Device state changes
   SELECT device_id, previous_state, new_state, COUNT(*)
   FROM device_state_history 
   GROUP BY device_id, previous_state, new_state;
   ```

## References

**Documentation:**
- Authentication: `docs/user-authentication-api.md`
- Analytics: `docs/backend-analytics.md`
- Database: `docs/database-guide.md`
- Testing: `docs/api-testing-guide.md`
- **Password Management: See [Database Password Management](#database-password-management) below**

**Code Files:**
- Analytics Endpoint: `backend/src/homepot/app/api/API_v1/Endpoints/AnalyticsEndpoint.py`
- Analytics Models: `backend/src/homepot/app/models/AnalyticsModel.py`
- Auth Endpoint: `backend/src/homepot/app/api/API_v1/Endpoints/AuthEndpoint.py`
- Config: `backend/src/homepot/config.py`

**Scripts:**
- Database Init: `scripts/init-postgresql.sh`
- Validation: `scripts/run-validation-test.sh`
- **Password Setup: `scripts/setup-pgpass.sh`**

---

## Database Password Management

### Problem: Password Prompts

When running `psql` commands, you may encounter password prompts:

```bash
$ psql -h localhost -U homepot_user -d homepot_db
Password for user homepot_user: _
```

This interrupts scripts and requires manual input. Here are three solutions:

### Solution 1: `.pgpass` File (RECOMMENDED for developers)

**Setup once, works forever:**

```bash
# Run the setup script
./scripts/setup-pgpass.sh
```

**What it does:**
- Creates `~/.pgpass` file in your home directory
- Adds: `localhost:5432:homepot_db:homepot_user:homepot_dev_password`
- Sets permissions to 600 (owner read/write only)

**After setup:**
```bash
# No password prompt!
psql -h localhost -U homepot_user -d homepot_db
./scripts/query-db.sh count
./scripts/init-postgresql.sh
```

**Security:**
- Standard PostgreSQL password file
- Only readable by you (chmod 600)
- Used by all PostgreSQL client tools

**To remove:**
```bash
sed -i '/homepot_db/d' ~/.pgpass
# Or delete the entire file:
rm ~/.pgpass
```

### Solution 2: PGPASSWORD Environment Variable

**For temporary sessions:**

```bash
# Set for current terminal session
export PGPASSWORD='homepot_dev_password'
psql -h localhost -U homepot_user -d homepot_db
```

**For single command:**

```bash
PGPASSWORD='homepot_dev_password' psql -h localhost -U homepot_user -d homepot_db -c "SELECT COUNT(*) FROM users;"
```

**Note:** All project scripts automatically set `PGPASSWORD`, so they work without manual setup.

### Solution 3: Connection String

**Include password in URL:**

```bash
psql "postgresql://homepot_user:homepot_dev_password@localhost:5432/homepot_db"
```

**Pros:**
- Works everywhere
- No setup needed
- Explicit credentials

**Cons:**
- Password visible in command history
- Longer to type

### Comparison

| Method | Setup | Security | Convenience | CI/CD |
|--------|-------|----------|-------------|-------|
| `.pgpass` | Once | High | Best | No |
| `PGPASSWORD` | Each session | Medium | Good | Yes |
| Connection String | None | Low | OK | Yes |

### Recommendation

**For developers:**
1. Run `./scripts/setup-pgpass.sh` once
2. Enjoy password-free database access forever

**For CI/CD:**
- Scripts automatically use `PGPASSWORD`
- No manual setup needed

**For quick testing:**
- Use connection string for one-off commands

---

## Summary

- **Database completely reset from scratch**  
- **All 11 tables created successfully**  
- **Seed data added (1 user, 3 sites, 12 devices)**  
- **Both developer issues analyzed and resolved**  
- **Authentication flow documented with examples**  
- **Password management simplified with `.pgpass` setup**
- **Ready for validation testing and data collection**

**Database is clean and ready for new user validation!**

---

**For questions or issues, refer to this document or the main documentation in `/docs`.**
