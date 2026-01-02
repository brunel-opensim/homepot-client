# Device Configuration & MDM Strategy

## Overview

HOMEPOT employs a **Management Plane** strategy for device configuration. Unlike traditional remote desktop tools that mirror the device's screen, HOMEPOT exposes a curated set of "manageable" settings defined by the device's policy.

This approach ensures:
1.  **Security:** Only authorized settings can be modified.
2.  **Consistency:** Settings are applied uniformly across fleets of devices.
3.  **Efficiency:** Administrators focus on business-critical configurations rather than OS-level noise.

## The Management Plane Concept

We do not attempt to mirror the native Settings app of the underlying OS (Android, Linux, Windows). Instead, we define a **Schema** for each device type that dictates:
*   Which settings are **Visible** (Read-Only telemetry).
*   Which settings are **Editable** (Remote configuration).

### Why not Remote Control?
*   **Bandwidth:** Streaming a full UI is heavy for IoT devices.
*   **Complexity:** Android alone has 1000+ settings, most of which (wallpaper, ringtones) are irrelevant to enterprise management.
*   **Automation:** A schema-based approach allows for API-driven bulk updates, which is impossible with visual remote control.

### Strategic Choice: Active Management vs. Static Templates

You might ask: *"Why use this editable method instead of just applying a static template to thousands of devices?"*

While **Templates** (Policy Groups) are excellent for initial provisioning ("Day 0"), the **Active Management** approach is superior for ongoing operations ("Day 2+"):

1.  **Environmental Variance:** Real-world devices have unique needs. A POS terminal facing a sunny window needs **100% Brightness**, while the same model in a dark corner needs **50%**. A rigid template system forces a "one size fits all" failure; our method allows for local overrides.
2.  **Troubleshooting & Diagnostics:** When a specific device malfunctions, operators need to tweak settings *on that device* (e.g., enable Debug Logging, disable Sleep Mode) without altering the global fleet policy.
3.  **The "Atomic Unit" of MDM:** This direct configuration capability is the foundation. Once we can reliably read/write settings to one device, we can easily build a "Policy Engine" on top to apply these settings to thousands. You cannot build a reliable template system without this granular control layer first.

## Device Schemas

The frontend dynamically renders the settings page based on the `device_type`. This is controlled by the `SETTINGS_SCHEMAS` definition.

### 1. POS Terminal (`pos_terminal`)
Focused on retail operations and kiosk stability.

| Setting | Type | Description |
| :--- | :--- | :--- |
| **Kiosk Mode** | Boolean | Locks the device to a single application. |
| **System Volume** | Range (0-100) | Controls audio output for alerts. |
| **Screen Brightness** | Range (0-100) | Manages power consumption and visibility. |
| **Auto Update** | Boolean | Allows the agent to auto-update business apps. |

### 2. IoT Gateway (`gateway`)
Focused on infrastructure management and connectivity.

| Setting | Type | Description |
| :--- | :--- | :--- |
| **SSH Access** | Boolean | Enables/Disables remote shell access for debugging. |
| **Log Level** | Select | Sets verbosity (INFO, DEBUG, ERROR). |
| **Docker Auto Prune** | Boolean | Automatically cleans up unused containers to save disk space. |

### 3. IoT Sensor (`iot_sensor`)
Focused on power management and data reporting.

| Setting | Type | Description |
| :--- | :--- | :--- |
| **Reporting Interval** | Number (sec) | How often the sensor wakes up to send data. |
| **Threshold Temp** | Number | Trigger point for local alerts. |
| **Deep Sleep Mode** | Boolean | Forces the device into low-power mode. |

## Configuration Workflow

1.  **User Action:** Admin modifies a value (e.g., "Enable Kiosk Mode") in the Dashboard.
2.  **API Request:** The frontend sends a JSON payload to the backend.
    ```json
    POST /api/v1/devices/{id}/settings
    {
      "kiosk_mode": true
    }
    ```
3.  **Command Queue:** The backend queues a `CONFIGURE` command for the specific device agent.
4.  **Agent Execution:**
    *   The on-device Agent receives the command.
    *   It executes the necessary OS calls (e.g., Android Device Policy Manager APIs).
    *   It verifies the change.
5.  **State Synchronization:** The Agent reports the new state back to the backend, updating the "Read-Only" view.

## Future Roadmap

*   **Policy Groups:** Apply a settings schema to a group of devices (e.g., "All NYC Store POS").
*   **Drift Detection:** Alert when a device's local state does not match the desired configuration.
*   **Offline Queuing:** Queue configuration changes for devices that are currently offline.

## Configuration History & Auditing

To ensure accountability and traceability, HOMEPOT maintains a detailed audit log of all configuration changes applied to a device.

### Data Flow
1.  **Command Execution:** When a configuration command (Push Notification) is sent to a device, the device agent applies the changes.
2.  **Feedback Loop:** The agent reports back the success of the operation along with the specific parameters that were modified.
3.  **Dynamic Logging:** The backend (`agents.py`) dynamically parses the incoming payload to identify which keys were changed (e.g., `brightness`, `volume`, `kiosk_mode`) and logs them into the `ConfigurationHistory` table. This ensures that even custom or new parameters are automatically tracked without schema changes.

### UI Features
*   **History Log:** The Device Settings page displays a chronological list of all configuration changes, showing the timestamp and the configuration version.
*   **Transaction Details:** Clicking on a history item opens a "Transaction Details" modal. This view presents the raw JSON payload of the change, allowing administrators to verify exactly what data was sent to and acknowledged by the device.
*   **History Management:** Administrators can delete individual history records to clean up the log or remove sensitive test data. This is performed via a dedicated delete action that updates the backend records immediately.
