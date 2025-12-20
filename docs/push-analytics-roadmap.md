# Push Notification Analytics Roadmap

**Status**: Draft  
**Target Audience**: Developers, Data Scientists  
**Goal**: Implement comprehensive analytics for the Push Notification subsystem to ensure reliability in real-world deployments (Restaurant Industry).

---

## 1. Executive Summary

As HOMEPOT transitions from simulation to real-world deployment in the restaurant industry, relying solely on "Job Success" metrics is insufficient. We need granular visibility into the **delivery pipeline** of push notifications.

This roadmap outlines the implementation of a **Push Analytics Module** that tracks the lifecycle of every message, measures latency, identifies network bottlenecks, and provides actionable insights to technicians.

**Key Metrics to Track:**
1.  **Delivery Rate**: Percentage of messages successfully acknowledged by devices.
2.  **End-to-End Latency**: Time difference between `sent_at` (Server) and `received_at` (Device).
3.  **Provider Reliability**: Success rates per provider (FCM vs. APNs vs. MQTT).
4.  **Device Reachability**: Identifying "Zombie Devices" that are online but not receiving pushes.

---

## 2. Architecture Strategy

### 2.1 The "Ack" Loop
Currently, push notifications are "Fire and Forget". We will implement a "Fire and Acknowledge" pattern.

1.  **Server** sends Push with a unique `message_id` and `sent_at` timestamp.
2.  **Device** receives Push (background wake-up).
3.  **Device** immediately calls `POST /api/v1/push/ack` with `message_id` and `received_at`.
4.  **Server** calculates latency and updates the `PushNotificationLog`.

### 2.2 Database Schema
We need a dedicated model to track individual messages, separate from the high-level "Jobs".

**Proposed Model:**
```python
class PushNotificationLog(Base):
    __tablename__ = "push_notification_logs"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(100), unique=True, index=True)
    
    # Context
    device_id = Column(String(100), ForeignKey("devices.device_id"))
    job_id = Column(String(100), ForeignKey("jobs.job_id"), nullable=True)
    provider = Column(String(20))  # fcm, apns, mqtt
    
    # Timestamps
    sent_at = Column(DateTime(timezone=True), default=utc_now)
    received_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metrics
    latency_ms = Column(Integer, nullable=True)  # Calculated on ack
    status = Column(String(20))  # sent, delivered, failed, expired
    
    # Error Tracking
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
```

---

## 3. Implementation Roadmap

### Phase 1: Backend Infrastructure
*   **Task 1.1**: Create `PushNotificationLog` model and migration.
*   **Task 1.2**: Update `PushNotificationProvider` base class to return `message_id` and log the "Send" event.
*   **Task 1.3**: Create `POST /api/v1/push/ack` endpoint to handle device acknowledgments.

### Phase 2: Client Integration (SDK)
*   **Task 2.1**: Update the HOMEPOT Client SDK (Android/iOS/Windows) to:
    *   Extract `message_id` and `sent_at` from payload.
    *   Call the Ack endpoint immediately upon receipt.
*   **Task 2.2**: Update `simulation.py` to simulate realistic network latency (e.g., random delays for "bad Wi-Fi").

### Phase 3: Analytics Engine
*   **Task 3.1**: Implement "Stale Message Detector" background task.
    *   Mark messages as `EXPIRED` if not acknowledged within TTL (e.g., 5 mins).
*   **Task 3.2**: Create Aggregation Queries:
    *   Average Latency per Site.
    *   Delivery Rate per Provider.

### Phase 4: Visualization (Dashboard)
*   **Task 4.1**: Add "Push Health" widget to Dashboard.
    *   Heatmap of delivery latency.
    *   Alerts for sites with high failure rates.

---

## 4. Success Criteria

*   **Visibility**: Technicians can see *exactly* when a device received a command.
*   **Troubleshooting**: We can distinguish between "Device Offline" vs. "Push Provider Failure".
*   **Optimization**: Data allows us to choose the fastest provider for each site (e.g., "Site A works better with MQTT").

---

## 5. Handling Unreachable Devices (The Fallback Strategy)

A critical concern in diverse deployments (especially industrial POS) is devices that cannot use standard push services (FCM/APNs). This includes:

1.  **AOSP Devices**: Android terminals without Google Play Services (no FCM).
2.  **Legacy Systems**: Windows Embedded/IoT devices without WNS support.
3.  **Strict Firewalls**: Networks blocking `googleapis.com` or `apple.com`.

### 5.1 The MQTT Fallback Layer
To ensure 100% reachability, HOMEPOT will implement an **MQTT Fallback Layer**.

*   **Primary Channel**: Standard Push (FCM/APNs) - Preferred for battery efficiency.
*   **Secondary Channel**: MQTT (Direct Connection) - Used when Primary fails or is unavailable.

**Implementation Plan:**
1.  **Client Logic**: The HOMEPOT Agent will attempt to register with FCM/APNs. If it fails (or detects no GMS), it automatically establishes a persistent MQTT connection to the HOMEPOT Broker.
2.  **Server Logic**: The `PushNotificationProvider` will check the device's `capabilities`. If `fcm_token` is missing but `mqtt_client_id` is present, it routes the message via MQTT.
3.  **Analytics**: The Analytics Engine will track "Fallback Rate" to identify sites with systemic connectivity issues.
