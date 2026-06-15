# Device Enrollment — Next Steps & Responsibilities

With the introduction of the HOMEPOT User App and the dual device registration methods (Pre-Provisioned vs. Self-Enrolled), we need to coordinate efforts across teams to ensure a smooth end-to-end integration. 

This document outlines the immediate next steps and assigns clear responsibilities to the respective teams.

Based on the enrollment logic we've implemented, there are two distinct paths:

Self-Enrolled (User-Initiated): The IT Admin creates a Site on the dashboard and securely provides the Site ID to the end-user. The user then enters this Site ID into the Setup Wizard on the User App. The backend uses that ID to associate their newly registered device with the correct site. (This is exactly why we surfaced the Site ID visibly on the Dashboard and Site Details pages).

Pre-Provisioned (Admin-Initiated): The IT Admin already knows the device's unique identifier (like a serial number) and registers it to a site directly from the dashboard before the user even receives the device. When the user opens the app, it automatically syncs with its assigned site.

---

## 1. Dealdio (Backend Responsibilities)
**Focus:** API enhancements, Database Schema, and Enrollment Logic.

*   **Database Schema Update:**
    *   Update the `Device` model in the database to include an `enrollment_method` column (enum: `pre-provisioned`, `self-enrolled`).
    *   Update the schema to handle a secure "Enrollment Token" for pre-provisioned devices.
*   **API Enhancements (`POST /api/v1/devices/sites/{site_id}/devices`):**
    *   Update the endpoint to accept and validate the `enrollment_method` payload.
    *   **Logic A:** If `pre-provisioned`, the endpoint must validate the enrollment token, find the existing device placeholder, and "claim" it by updating its status to active.
    *   **Logic B:** If `self-enrolled`, the endpoint must dynamically create a new device record mapped to the provided `site_id`, verifying the user's SSO authorization.
*   **Dashboard Stats API:**
    *   Provide a new or updated endpoint (e.g., `GET /api/v1/sites/{site_id}/stats`) that returns the breakdown of registered devices by enrollment method (e.g., how many are self-enrolled vs. pre-provisioned) for the Dashboard UI.

---

## 2. GetFudo (Frontend Responsibilities)
**Focus:** User App Setup Wizard and Admin Dashboard UI constraints.

*   **HOMEPOT User App (Agent):**
    *   Update `SetupWizard.tsx` to handle passing the correct `enrollment_method` payload to the backend during the `onComplete` SSO step.
    *   *(Future)* Add a flow where if an IT admin supplies an "Enrollment Token" instead of just a Site ID, the app claims the pre-provisioned slot rather than self-enrolling.
*   **Admin Dashboard:**
    *   Update the "Sites" detail view to consume the new Stats API from Dealdio.
    *   Display the **Total Devices** count, accompanied by a breakdown: 
        *   `X` via User App (Self-Enrolled)
        *   `Y` via Dashboard (Pre-Provisioned)
    *   Ensure the "Register Device" button in the dashboard clearly indicates to the Admin that they are pre-provisioning a device for secure environments.

---

## 3. Brunel (Integration & Review Responsibilities)
**Focus:** Code review, architectural enforcement, and end-to-end (E2E) testing.

*   **Cross-Team Code Reviews:**
    *   Review PRs from Dealdio to ensure that the API payloads match the documentation (`docs/device-registration.md`).
    *   Review PRs from GetFudo to verify that both the Dashboard and the User App accurately reflect the new endpoints and UI UX guidelines.
*   **End-to-End Testing Synchronization:**
    *   Use the newly created `start-dashboard.sh` and `start-userapp.sh` scripts to run both platforms concurrently on ports `5173` and `5174`.
    *   Manually simulate the End-to-End flow: Create a Site in the Admin Dashboard, use the Site ID in the User App Wizard, and verify the device appears correctly under the Site in the Dashboard with the correct enrollment tag.
*   **Documentation Maintenance:**
    *   Continuously keep the MkDocs structure updated as new edge cases regarding Device Enrollment or IPC background communication arise.