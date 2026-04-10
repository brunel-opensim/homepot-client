# GetFudo: User App UI/UX & Frontend Implementation

**Owner:** GetFudo Design & Frontend Team  
**Status:** Pending (Awaiting Return)  
**Objective:** Design and build the lightweight native client agent ("Digital Security Badge") that runs on employee devices (Android, Windows, Linux, macOS).

---

## Part 1: Design Requirements

**Philosophy**: Ensure the app looks secure, stable, unobtrusive. High Trust Design.  
**Stack Alignment**: Tailwind CSS + Radix UI (Match the Dashboard's aesthetics/dark mode).

### Required High-Fidelity Views
1.  **The "Digital Badge" (Home)**
    *   Large reassuring status ring/shield (Green/Red).
    *   Prominent User Avatar/Identity.
    *   Actions: "Sync Now" and "Corporate Files".
2.  **The Setup Wizard (Onboarding)**
    *   Server URL input -> User Login (SSO/OIDC) -> OS Admin Permissions explanation.
    *   Note: Use Trust Design principles for the Permissions request.
3.  **Device DNA (Details)**
    *   Clean list format showing: OS Version, IP Address, Policy Version, Last Heartbeat Timestamp.
4.  **System Tray / Widget**
    *   A minimized view of the app for Desktop (Windows/macOS/Linux).

---

## Part 2: Technical Frontend Implementation

**Architecture Model**: Hybrid Monolith (Single codebase across 5 OS's)
*   **Directory**: Initialize in `/workspace/homepot-client/user-app/` (Sibling to `frontend/`).
*   **Core stack**: React 19 + Vite.
*   **Desktop Shell**: Electron (Windows/macOS/Linux).
*   **Mobile Shell**: Capacitor 8 (Android).
*   **Database**: SQLite (`@capacitor-community/sqlite` and `better-sqlite3`).

### Key Delivery Milestones
*   **Milestone 1: Scaffold Infrastructure**
    *   Initialize the Vite/React workspace in the new `user-app/` directory.
    *   Configure Electron build wrappers and Capacitor hooks.
*   **Milestone 2: Agent IPC Integration**
    *   Connect the React frontend to the local API / Socket established by the **Dealdio** engine.
    *   Alternatively, initialize development using Dealdio's `mock_dna.json` and `mock_telemetry.json` payloads.
*   **Milestone 3: UI Component Build**
    *   Implement Digital Badge, Onboarding, and Details views.
*   **Milestone 4: Native Capabilities**
    *   Wire up native alerts, background polling hooks, and Tray components.
