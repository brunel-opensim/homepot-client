# User App: Device Lifecycle & Unpairing Logic

This document outlines the architecture and user experience logic regarding device lifecycle management in the Homepot application ecosystem, particularly focusing on how the User App handles device unpairing and deletion.

## Overview

Recent updates to the system have fundamentally shifted how we handle device removal. Instead of **destructive (hard) deletion** (where a device and its associated records are permanently erased from the database), we have implemented a **soft deletion (unpairing)** strategy. This aligns with enterprise best practices for data retention and analytics.

## The Logic Behind "Soft Deletion"

When a user elects to "delete" or "unpair" a device from the User App, the system severs the connection but preserves the historical footprint. 

**Why we made this change:**
1. **Preserve Analytics Data:** Deleting a device previously meant losing all its historical metrics (hardware performance, network stability, temperatures). Keeping this data is vital for aggregate fleet analytics and identifying systemic hardware issues over time.
2. **Audit & Compliance Tracking:** We need to maintain a continuous, immutable audit log of when devices were enrolled, who unpaired them, and their final state before being removed. 
3. **Prevent Orphaned Data Crashes:** True database deletion requires complex cascades that can fail (e.g., the 500 API errors on Site Deletion). Soft-deleting gracefully sidesteps integrity constraint violations.

## Backend Implementation Mechanics

When the User App triggers an unpair action, the API executes the following sequence:

1. **Status Update:** The device's `status` property is updated to the newly introduced `UNPAIRED` enum state. 
2. **Deactivation:** The `is_active` boolean is flipped to `False`, immediately hiding it from active dashboard aggregate metrics and live monitoring sockets.
3. **Security Severance:** The `api_key_hash` is nullified securely. This guarantees that even if the physical device retains its token, it immediately loses all API authorization to publish metrics or pull configurations.
4. **Audit Logging:** An `AuditLog` entry is explicitly generated, capturing the actor, the timestamp, and the exact state of the device right before unpairing.

## User App (Frontend) Impact & UX

These backend adjustments bring several deliberate changes to how the User App behaves:

### 1. Distinct Status Indicators
The app now strictly differentiates between a device's networking state and its lifecycle state:
* **Connectivity (`online` / `offline`):** Represents whether the device maintains an active MQTT/WebSocket heartbeat.
* **Pairing Status (`paired` / `unpaired`):** Represents the relationship lifecycle. 
* *Result:* A device can be "Offline" but "Paired" (turned off), or it can be completely "Unpaired" and archived.

### 2. Immediate UI Responsiveness
When a device is successfully unpaired via the User App SetupWizard or DeviceInfo screens:
* The React state updates **immediately** and locally.
* "Total Devices" counters decrement instantly without requiring the app to poll the API or force a page reload. 

### 3. Setup Wizard & Device Info (`DeviceInfo.tsx`, `SetupWizard.tsx`)
* **Device Info view:** If an unpaired device is somehow queried (e.g., from an old notification link), the UI safely handles it by reflecting its `UNPAIRED` badge and disabling command/control actions.
* **Enrollment overrides:** If an unpaired device is re-enrolled (e.g., after a factory reset), the setup wizard can theoretically claim the same physical hardware ID and generate fresh API keys, starting a new lifecycle epoch.