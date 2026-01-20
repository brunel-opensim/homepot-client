# Google SSO Setup & API Guide

This document provides a comprehensive guide for setting up and using Google Single Sign-On (SSO) with the HomePot system.

## 1. Google Cloud Console Configuration

To enable Google Login, you must first register your application on the [Google Cloud Console](https://console.cloud.google.com/).

### Step 1: Create a Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project** > **New Project**.
3. Give your project a name (e.g., "HomePot") and click **Create**.

### Step 2: Configure OAuth Consent Screen
1. In the sidebar, go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** and click **Create**.
3. Fill in the required app information:
   - **App name**: HomePot
   - **User support email**: Your email
   - **Developer contact info**: Your email
4. Click **Save and Continue**.
5. In the **Scopes** section, click **Add or Remove Scopes** and add:
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
   - `openid`
6. Finish the wizard.

### Step 3: Create Credentials
1. Go to **APIs & Services** > **Credentials**.
2. Click **Create Credentials** > **OAuth client ID**.
3. Select **Web application** as the application type.
4. Add the following **Authorized redirect URIs**:
   - `http://localhost:8000/api/v1/auth/callback` (Backend callback)
   - `http://localhost:5173/auth/callback` (If using frontend-initiated flow)
   *Note: Ensure these match your environment variables exactly.*
5. Click **Create**. You will receive your `Client ID` and `Client Secret`.

---

## 2. Environment Setup

Add the following variables to your `backend/.env` file:

```env
# Google OAuth Credentials
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# Frontend Redirect Location
FRONTEND_URL=http://localhost:5173

# Security Settings
COOKIE_SECURE=false  # Set to true in production (HTTPS)
COOKIE_SAMESITE=lax   # "lax", "strict", or "none"
```

---

## 3. API Reference

### 1. Initiate Google Login
**Endpoint**: `GET /api/v1/auth/login`  
**Description**: Generates the Google OAuth authorization URL.

**Success Response (200 OK)**:
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=..."
}
```

### 2. Google Callback Handling
**Endpoint**: `GET /api/v1/auth/callback`  
**Description**: Receives the `code` from Google, exchanges it for tokens, creates/links the user in HomePot, sets an `httpOnly` cookie, and redirects to the dashboard.

**Query Parameters**:
- `code` (string): The authorization code from Google.

**Workflow**:
1. Exchanges `code` for Google `id_token`.
2. Verifies the token and extracts email/name.
3. If the user doesn't exist, a new account is created automatically.
4. Generates an internal App JWT.
5. Sets the JWT as an `httpOnly` cookie (`access_token`).
6. Redirects the browser to `${FRONTEND_URL}/dashboard`.

---

## 4. How to Execute (Testing)

### Manual Browser Test
1. Start the backend: `uvicorn homepot.app.main:app --reload`
2. Open your browser to `http://localhost:8000/api/v1/auth/login`.
3. Copy the `auth_url` from the JSON response.
4. Paste it into your browser address bar.
5. Log in with your Google account.
6. Upon success, Google will redirect you to:
   `http://localhost:8000/api/v1/auth/callback?code=...`
7. The backend will process the code and redirect you to `http://localhost:5173/dashboard`.

### Automated Tests
Run the provided test suite to verify the integration:
```bash
cd backend
python3 -m pytest tests/test_google_auth.py
```

---

## 5. Security Notes
- **JWT Storage**: The `access_token` is stored in an `httpOnly` cookie. This prevents client-side JavaScript from accessing the token, significantly reducing XSS risks.
- **CSRF Protection**: The cookie uses `SameSite=lax` by default.
- **Production**: Always set `COOKIE_SECURE=true` in production to ensure tokens are only transmitted over HTTPS.
