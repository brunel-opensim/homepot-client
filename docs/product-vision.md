# Product Vision & Commercial Roadmap

This document outlines the strategic vision for the HOMEPOT commercial product suite, defining the distinct roles of the administrative control center and the end-user workspace app.

## Core Product Duality

The HOMEPOT ecosystem is divided into two distinct interfaces, each serving a specific user persona and operational need:

1.  **HOMEPOT Control** (Web Admin)
2.  **HOMEPOT Workspace** (User App)

### 1. HOMEPOT Control (Web Admin)
*Target Audience: IT Administrators, Security Managers, Network Operations (NetOps)*

This is the centralized management console. It is a pure web application (PWA) accessible via any browser. It provides deep visibility and control over the entire fleet.

*   **Platform:** Web (Browser-based)
*   **Key Functions:**
    *   **Fleet Overview:** Dashboard of all registered devices (Managed & Unmanaged).
    *   **Telemetry Visualization:** Real-time graphs for CPU, Memory, and Network usage.
    *   **Security Policy Management:** Defining Allow/Block lists, Geofencing, and Time-based access rules.
    *   **Incident Response:** Viewing anomalies detected by the AI Engine (WP4) and triggering remote wipes or locks.
    *   **User Management:** Provisioning staff accounts.

### 2. HOMEPOT Workspace (User App)
*Target Audience: Employees, Remote Workers, BYOD Users*

This is the "Super App" for the end-user. While it is built on the same React technology as the web platform, it is packaged as a **Native Wrapper** (using React Native or Capacitor) to gain access to OS-level APIs.

*   **Platform:** Mobile App (iOS/Android), Desktop App (Windows/macOS)
*   **Key Functions:**
    *   **Corporate Sandbox:** A secure container for accessing work email, documents, and internal portals.
    *   **"Work Mode" Toggle:** A clear switch to separate Personal vs. Work contexts on BYOD devices.
    *   **Local Agent:** Runs in the background (Service Worker) to collect telemetry and heartbeat signals.
    *   **Access Gateway:** Provides VPN-less secure access to the intranet (Zero Trust).
    *   **Offline Capability:** Caches critical work data for non-connected environments.

## Integration Architectures

### Hybrid Fleet Strategy
To satisfy the D3.1 requirements while maintaining flexibility, HOMEPOT employs a Hybrid Fleet strategy:

| Feature | Managed Endpoint (MDM) | Lightweight Endpoint (BYOD) |
| :--- | :--- | :--- |
| **Control Level** | OS-Level (Root) | App-Level (Sandbox) |
| **Deployment** | Corporate Issued | User Owned |
| **Agent Type** | System Service | HOMEPOT Workspace |
| **Privacy** | Low (Full Device Visibility) | High (Work Container Only) |
| **Use Case** | High-security, Fixed POS | Remote Work, Contractors |

### The "Workspace" Wrapper
The `HOMEPOT Workspace` application effectively serves as the "Lightweight Agent" required by the D3.1 architecture.
*   It does **not** take over the user's phone.
*   It **does** ensure that corporate data *inside* the app is managed, encrypted, and wipeable.

## Commercial Rollout Phases

1.  **Phase 1: Web Foundation (Current)**
    *   Fully functional `HOMEPOT Control` via Web PWA.
    *   Basic device telemetry reporting via Browser APIs.

2.  **Phase 2: The "Workspace" Wrapper**
    *   Wrapping the existing React frontend into a Native Binary.
    *   Enabling "Background Sync" for reliable telemetry.
    *   Implementing Biometric Auth (FaceID/TouchID) for app entry.

3.  **Phase 3: AI-Driven Security**
    *   Integrating the `AnalysisMode` engine to block access if the device shows "abnormal behavior" (e.g., accessed from a new country at 3 AM).
