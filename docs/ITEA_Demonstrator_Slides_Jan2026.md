---
marp: true
theme: gaia
paginate: true
backgroundColor: #fff
style: |
  section {
    font-size: 24px;
  }
  h1 {
    color: #004488;
  }
  h2 {
    color: #d63384;
  }
  .warning {
    color: #d9534f;
    font-weight: bold;
  }
  .success {
    color: #3e8e41;
    font-weight: bold;
  }
---

<!-- _class: lead -->

# UK Demonstrator: Live Platform Validation
**HOMEPOT Client: Cyber-Physical Orchestration**

**Presenter:** UK Consortium
**Date:** January 2026

---

## Slide 1: Demonstrator Scope
### Validating Functionality in a Controlled Environment

We are demonstrating **TRL 4.5 (Technology Validated in Lab)**.

*   **The Scenario:** A decentralized retail operation (Retail/Hospitality).
*   **The Environment:**
    *   **14 Active Sites:** Simulating real-world chaos (McDonalds, Starbucks, Target).
    *   **23 Intelligent Agents:** Running varying OS simulations (Linux/POS, Android).
    *   **Simulation Engine:** Generates realistic traffic, heatbeats, and anomalies.

**Objective:** Prove that the **Architecture** (WP2) successfully drives the **Execution** (WP5).

---

## Slide 2: The "Cast" (Simulation Parameters)
### What you will see on screen

We are simulating a **"Monday Morning Rush"** scenario.

1.  **Heterogeneous Fleet:**
    *   **POS Terminals:** High-value, locked-down devices (e.g., `POS_001`).
    *   **Staff Tablets:** Roaming BYOD devices (e.g., `TABLET_005`).
    *   **Kitchen Controllers:** High-temperature alerts.
2.  **Traffic Profile:**
    *   **Heartbeats:** Every 2 seconds.
    *   **Transaction Volume:** Cumulative growth reflecting live sales.
    *   **Error Rates:** Random injection of network failures (5% probability).

---

## Slide 3: Demo Phase 1 - Orchestration & Visibility
### "The Commander View"

**Action:**
1.  Navigate to **Dashboard**.
2.  Filter by **Site: Starbucks Coffee #1**.
3.  Observe **Real-Time Telemetry**.

**Validation Criteria:**
*   [ ] **Latency:** Data reflects < 200ms delay from Agent to UI.
*   [ ] **Unified View:** Linux POS and Android Tablets appear in the same grid.
*   [ ] **Status Indicators:** Green/Amber/Red indicators match the "Agent State Machine" (IDLE / BUSY / UPDATING).

---

## Slide 4: Demo Phase 2 - Job Dispatch (Push)
### "The Active Control"

**Action:**
1.  Select a group of devices (e.g., "All Kitchen Tablets").
2.  **Dispatch Job:** "Firmware Update v2.1".
3.  Watch the **State Transition** across the fleet.

**Under the Hood (Trace):**
*   **User Click** $\rightarrow$ **API Gateway** $\rightarrow$ **Celery Queue** $\rightarrow$ **Push Notification (FCM/MQTT)** $\rightarrow$ **Agent Wakeup** $\rightarrow$ **Job Execution**.

**Validation Criteria:**
*   [ ] Agents transition to **DOWNLOADING** state instantly.
*   [ ] Real-time progress bars update on the dashboard.

---

## Slide 5: Demo Phase 3 - AI & Anomaly Detection
### "The Cognitive Technician"

**Scenario:** We intentionally sabotage `POS_003` (simulate Memory Leak).

**Action:**
1.  Agent `POS_003` begins reporting **95% RAM Usage** + **High Latency**.
2.  **Anomaly Detector** (Backend) calculates `Score > 0.8` (CRITICAL).
3.  **UI Alert:** A red "Anomaly Detected" banner appears.
4.  **AI Insight:** "Device exhibiting gradual memory exhaustion pattern. Recommending reboot."

**Validation Criteria:**
*   [ ] Alert triggers **automatically** without human rule-setting.
*   [ ] The system distinguishes between "Busy" (High CPU) and "Broken" (High Error Rate).

---

## Slide 6: Summary of Capabilities
### What we have proven today

| Feature | Status | Technology |
| :--- | :--- | :--- |
| **Real-Time C2** | ✅ Verified | WebSocket / React |
| **Hybrid Fleet** | ✅ Verified | Python Factory Pattern |
| **Push / MQTT** | ✅ Verified | AsyncIO Broker |
| **AI Detection** | ✅ Verified | Heuristic Scoring Engine |

**Next Step for WP5 (Demonstrator):** Move from "Virtual Agents" to "Physical Deployment" on Raspberry Pi hardware (Scheduled Q2 2026).
