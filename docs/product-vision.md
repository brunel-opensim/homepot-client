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

### 2. HOMEPOT User App
*Target Audience: Employees, Remote Workers, BYOD Users*

This is a lightweight application installed on the device that acts as a bridge between the hardware and the HOMEPOT Dashboard. Instead of wrapping a full workspace, it functions as a dedicated communication agent.

*   **Platform:** Mobile App (iOS/Android), Desktop App (Windows/macOS)
*   **Key Functions:**
    *   **Communication Bridge:** Facilitates secure bi-directional communication between the device and the Dashboard.
    *   **Device Telemetry:** Collects and transmits performance metrics and status updates.
    *   **Command Execution:** Receives and processes management commands from the admin console.
    *   **Connectivity Management:** Ensures persistent connection for real-time monitoring.
    *   **Simple Interface:** Provides essential status information to the user without complex workspace features.

## Integration Architectures

### Hybrid Fleet Strategy
To satisfy the D3.1 requirements while maintaining flexibility, HOMEPOT employs a Hybrid Fleet strategy:

| Feature | Managed Endpoint (MDM) | Lightweight Endpoint (BYOD) |
| :--- | :--- | :--- |
| **Control Level** | OS-Level (Root) | App-Level (Bridge) |
| **Deployment** | Corporate Issued | User Owned |
| **Agent Type** | System Service | HOMEPOT User App |
| **Privacy** | Low (Full Device Visibility) | High (Telemetry Only) |
| **Use Case** | High-security, Fixed POS | Remote Work, Contractors |

### The "User App" Bridge
The `HOMEPOT User App` effectively serves as the "Communication Bridge" required by the real-device transition.
*   It does **not** act as a containerized workspace wrapper.
*   It **does** act as a relay for telemetry and management commands between the device OS and the Dashboard.

## Commercial Rollout Phases

1.  **Phase 1: Web Foundation (Current)**
    *   Fully functional `HOMEPOT Control` via Web PWA.
    *   Basic device telemetry reporting via Browser APIs.

2.  **Phase 2: The User App Bridge**
    *   Developing the standalone User App for facilitating device communication.
    *   Enabling reliable "Bridge" connectivity for real-time telemetry.
    *   Implementing device registration and secure handshake protocols.

3.  **Phase 3: AI-Driven Security**
    *   Integrating the `AnalysisMode` engine to block access if the device shows "abnormal behavior" (e.g., accessed from a new country at 3 AM).
