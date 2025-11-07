# HOMEPOT Website Integration Testing Guide

This guide will help you manually test the complete HOMEPOT website integration.

## Current Status

**✅ Running:**
- Backend: `http://localhost:8000` (API v1 structure)
- Frontend: `http://localhost:5173` (React + Vite)
- Database: PostgreSQL (homepot_db)

**📝 Note:** The authentication system has a bcrypt password hashing issue. We'll test the UI flow and other integrated features.

## Testing Checklist

### 1. Homepage & Routing ✓

**Test:** Open the website
```
URL: http://localhost:5173
```

**Expected Behavior:**
- ✅ Should automatically redirect to `/login` (since not authenticated)
- ✅ Login page should load without errors
- ✅ No console errors in browser DevTools

**How to Verify:**
1. Open browser DevTools (F12)
2. Check Console tab - should be clean
3. Check Network tab - should show successful requests

---

### 2. Login Page UI ✓

**Test:** Examine the login page

**Expected Elements:**
- ✅ "HOMEPOT" title/logo
- ✅ Tab selector: "ENGINEER" and "USER"
- ✅ Email input field
- ✅ Password input field
- ✅ "Login" button
- ✅ "Sign up" link
- ✅ Dark theme with teal/cyan accents

**How to Verify:**
1. Visual inspection of all elements
2. Try switching between ENGINEER and USER tabs
3. Check hover effects on buttons

---

### 3. Signup Page Navigation ✓

**Test:** Navigate to signup page

**Steps:**
1. Click "Sign up" link on login page

**Expected Behavior:**
- ✅ URL changes to `/signup`
- ✅ Signup form loads
- ✅ Shows fields: Email, Password, Name, Role dropdown
- ✅ "Create Account" button visible
- ✅ "Sign in" link visible

**How to Verify:**
1. Check URL bar shows `/signup`
2. All form fields are visible and styled correctly
3. Role dropdown works (ENGINEER/USER options)

---

### 4. Form Validation (Frontend) ✓

**Test:** Try submitting empty forms

**Steps:**
1. On signup page, click "Create Account" without filling fields

**Expected Behavior:**
- ✅ Error message: "Please fill in all fields"
- ✅ Error displayed in red/warning color
- ✅ Form doesn't submit

**Additional Tests:**
- Try password < 6 characters → Should show "Password must be at least 6 characters long"
- Try invalid email format → Built-in HTML5 validation should trigger

---

### 5. Backend API Connection ✓

**Test:** Verify frontend can reach backend

**Open Browser Console and run:**
```javascript
fetch('http://localhost:8000/')
  .then(r => r.json())
  .then(console.log)
```

**Expected Output:**
```json
{
  "message": "I Am Alive"
}
```

**Alternative Test:**
```javascript
fetch('http://localhost:8000/api/v1/sites/sites')
  .then(r => r.json())
  .then(console.log)
```

**Expected:** Should return sites data (list of sites)

---

### 6. Dashboard Access (Protected Route) ✓

**Test:** Try accessing dashboard without login

**Steps:**
1. Manually navigate to: `http://localhost:5173/dashboard`

**Expected Behavior:**
- ✅ Should automatically redirect to `/login`
- ✅ Protected route guard is working

**How to Verify:**
1. URL bar should show `/login` (not `/dashboard`)
2. No dashboard content visible

---

### 7. Sites API Integration ✓

**Test:** Check if Dashboard would load sites data

**Method 1 - Using Browser Console:**
```javascript
// Simulate the API call the Dashboard makes
fetch('http://localhost:8000/api/v1/sites/sites')
  .then(r => r.json())
  .then(data => {
    console.log('Sites loaded:', data.sites);
    console.log('Number of sites:', data.sites.length);
  })
```

**Expected Output:**
```javascript
Sites loaded: [
  {site_id: "site-test-001", name: "Test Branch API", ...},
  {site_id: "site-002", name: "West Branch", ...},
  {site_id: "site-001", name: "Main Store - Downtown", ...}
]
Number of sites: 3 (or more)
```

**Method 2 - Using curl:**
```bash
curl -s http://localhost:8000/api/v1/sites/sites | python3 -m json.tool
```

---

### 8. API Documentation ✓

**Test:** Access Swagger API docs

**URL:**
```
http://localhost:8000/docs
```

**Expected:**
- ✅ FastAPI Swagger UI loads
- ✅ All API v1 endpoints visible:
  - /api/v1/auth
  - /api/v1/sites
  - /api/v1/devices
  - /api/v1/jobs
  - /api/v1/agents
  - /api/v1/health
  - /api/v1/push
  - /api/v1/mobivisor

**How to Verify:**
1. Expand each section
2. Try "Try it out" on simple GET endpoints like `/api/v1/sites/sites`

---

### 9. Page Navigation Flow ✓

**Test:** Navigate between all pages

**Navigation Map:**
```
/ (Home) 
  → /login (Login)
    → /signup (Signup)
      ← Back to /login
  → /dashboard (Protected - requires auth)
  → /site (Protected - requires auth)
  → /device (Protected - requires auth)
  → /site/:siteId (Protected - requires auth)
```

**Test Flow:**
1. Start at `/` → redirects to `/login` ✓
2. Click "Sign up" → goes to `/signup` ✓
3. Click "Sign in" → back to `/login` ✓
4. Try `/dashboard` → redirects to `/login` ✓
5. Try `/site` → redirects to `/login` ✓
6. Try `/device` → redirects to `/login` ✓

---

### 10. Frontend Features (Without Auth)

**Test:** UI Components and Interactions

**On Login Page:**
- ✅ Tab switching (ENGINEER ↔ USER) works smoothly
- ✅ Input fields have focus states
- ✅ Button hover effects work
- ✅ Responsive design (resize browser window)

**On Signup Page:**
- ✅ Role dropdown opens and closes
- ✅ Tab switching works
- ✅ All form fields functional
- ✅ Error messages display correctly

---

### 11. Console Error Check ✓

**Test:** Check for any JavaScript errors

**Steps:**
1. Open DevTools (F12)
2. Go to Console tab
3. Navigate through all pages: `/`, `/login`, `/signup`, `/dashboard`, `/site`, `/device`

**Expected:**
- ✅ No red errors (errors allowed: auth redirects are normal)
- ✅ May see warnings about authentication (expected)
- ✅ Network requests should be successful (200 status)

**Acceptable Warnings:**
- "Session expired" or "Unauthorized" when trying protected routes
- CORS preflight requests

---

### 12. Network Traffic Analysis ✓

**Test:** Monitor API calls

**Steps:**
1. Open DevTools (F12)
2. Go to Network tab
3. Navigate to different pages

**Check for:**
- ✅ XHR/Fetch requests to `localhost:8000`
- ✅ All requests have proper headers
- ✅ No CORS errors
- ✅ Status codes: 200 (success) or 401 (unauthorized, expected)

---

## Mock Login Testing (When Database is Fixed)

Once the database connection is resolved, test these flows:

### Create Test Account
1. Go to `/signup`
2. Fill in:
   - **Email:** `test@homepot.com`
   - **Password:** `Test123!`
   - **Name:** `Test User`
   - **Role:** `ENGINEER`
3. Click "Create Account"
4. Should redirect to `/login`

### Login Flow
1. On `/login` page
2. Enter:
   - **Email:** `test@homepot.com`
   - **Password:** `Test123!`
3. Click "Login"
4. Should redirect to `/dashboard`
5. Should see:
   - List of sites (real data from API)
   - System status
   - Navigation buttons

### Dashboard Interaction
1. Click "View Sites" button
2. Should navigate to `/site`
3. Should see searchable site list
4. Click "View Devices" button
5. Should navigate to `/device`

### Logout
1. Look for logout button/icon (may need to implement)
2. Click logout
3. Should redirect to `/login`
4. Session cleared from localStorage

---

## Quick API Testing Commands

### Test Backend Health
```bash
curl http://localhost:8000/
```

### Get All Sites
```bash
curl http://localhost:8000/api/v1/sites/sites
```

### Get Site Details
```bash
curl http://localhost:8000/api/v1/sites/site-001
```

### Create Test User (when DB is fixed)
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@homepot.com",
    "password": "Test123!",
    "name": "Test User",
    "role": "admin"
  }'
```

### Login Test (when DB is fixed)
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@homepot.com",
    "password": "Test123!"
  }'
```

---

## Known Issues

### 1. bcrypt Password Hashing Issue
**Issue:** Password hashing in authentication endpoints needs proper async bcrypt implementation.

**Impact:** Authentication endpoints (/signup, /login) may have errors during password operations.

**Workaround:** Test UI flows and non-auth endpoints. Auth will work after bcrypt fix.

### 2. Missing Logout UI
**Issue:** No visible logout button in the UI yet

**Workaround:** Can manually clear localStorage:
```javascript
// In browser console:
localStorage.clear()
location.reload()
```

---

## Success Criteria

### ✅ Phase 1: UI & Navigation (Can Test Now)
- [x] Frontend loads without errors
- [x] Login page renders correctly
- [x] Signup page renders correctly
- [x] Tab switching works
- [x] Form validation works
- [x] Protected routes redirect to login
- [x] Page transitions are smooth
- [x] No console errors
- [x] Responsive design works

### ⏳ Phase 2: Backend Integration (Needs DB Fix)
- [ ] Signup creates user account
- [ ] Login returns JWT token
- [ ] Token stored in localStorage
- [ ] Dashboard loads with real sites data
- [ ] Site list displays correctly
- [ ] Logout clears session

### ⏳ Phase 3: Full Features (Future)
- [ ] Device management UI
- [ ] Job creation/monitoring
- [ ] Real-time updates (WebSocket)
- [ ] Push notifications
- [ ] User profile management

---

## Browser Console Testing Snippets

### Check if Token Exists
```javascript
console.log('Token:', localStorage.getItem('auth_token'));
console.log('Token Expiry:', localStorage.getItem('token_expiry'));
console.log('User Data:', localStorage.getItem('user_data'));
```

### Simulate Authenticated State (for testing protected routes)
```javascript
// Set a dummy token
localStorage.setItem('auth_token', 'dummy_token_for_testing');
localStorage.setItem('token_expiry', Date.now() + 86400000); // 24 hours from now
localStorage.setItem('user_data', JSON.stringify({
  email: 'test@homepot.com',
  role: 'admin',
  username: 'Test User'
}));

// Reload to see protected routes
location.reload();
```

### Clear Authentication
```javascript
localStorage.removeItem('auth_token');
localStorage.removeItem('token_expiry');
localStorage.removeItem('user_data');
location.reload();
```

### Test API Call with Token
```javascript
const token = 'YOUR_TOKEN_HERE'; // Get from successful login
fetch('http://localhost:8000/api/v1/sites/sites', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(r => r.json())
.then(console.log);
```

---

## Next Steps

1. **Fix bcrypt Implementation:**
   - Update authentication to use proper async bcrypt
   - Add password validation and security

2. **Test Authentication Flow:**
   - Create test users
   - Login/logout
   - Token management

3. **Complete Integration:**
   - Connect all dashboard widgets to real data
   - Implement real-time updates
   - Add device management features

4. **Create PR:**
   - Document all changes
   - Include testing results
   - Submit for review

---

## Troubleshooting

### Frontend won't load
```bash
# Check if frontend is running
ps aux | grep vite

# Restart if needed
cd frontend
npm run dev
```

### Backend not responding
```bash
# Check if backend is running
ps aux | grep uvicorn

# Check the correct app is running
# Should be: homepot.app.main:app (not homepot.main:app)
```

### CORS Errors
- Backend already configured for localhost:5173
- Check `.env.local` in frontend has correct API URL
- Restart frontend after env changes

### Port Already in Use
```bash
# Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

---

**Ready to test!** Start with Phase 1 (UI & Navigation) and report any issues you find.
