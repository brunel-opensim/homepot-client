# Push Notification Payloads

## Overview

HOMEPOT uses a standardized payload structure for all push notifications, regardless of the underlying platform (FCM, APNs, WNS, MQTT). This ensures consistent behavior across the entire device fleet.

## The Payload Structure

When the Orchestrator triggers a notification (e.g., for a Configuration Update), it constructs a `PushNotificationPayload` object.

### Internal Data Model (`backend/src/homepot/push_notifications/base.py`)

```python
@dataclass
class PushNotificationPayload:
    title: str                  # Notification Title
    body: str                   # Notification Body Text
    data: Dict[str, Any]        # Invisible data payload for the Agent
    priority: PushPriority      # HIGH or NORMAL
    ttl_seconds: int            # Time-to-live (expiration)
    collapse_key: str           # Grouping key (e.g., "config-update")
    device_tokens: List[str]    # Target device IDs
```

### JSON Representation (Over the Wire)

When serialized for transmission (or debugging via `curl`), the structure maps logically to the components you identified:

```json
{
  "title": "Configuration Update v2.1.0",
  "body": "New configuration available for device-123",
  "data": {
    "config_url": "https://config.homepot.local/site-1/pos/v2.1.0.json",
    "config_version": "v2.1.0",
    "priority": "high"
  },
  "priority": "high",
  "ttl_seconds": 300,
  "collapse_key": "homepot-config-v2.1.0"
}
```

## Comparison with Your Example

Your `curl` example is a perfect representation of a **High-Level API Request** to trigger a notification.

| Your Example Field | HOMEPOT Internal Field | Description |
| :--- | :--- | :--- |
| `payload.title` | `title` | User-visible header (e.g., "System Alert"). |
| `payload.body` | `body` | User-visible message. |
| `policy.priority` | `priority` | Criticality. Config updates are usually `HIGH`. |
| `policy.ttl_sec` | `ttl_seconds` | How long to keep trying if device is offline. |
| `policy.collapse_key` | `collapse_key` | Replaces older notifications of the same type. |
| `targets` | `device_tokens` | Who receives the message. |

## The "Configuration Update" Command

In `backend/src/homepot/orchestrator.py`, the specific command to push a configuration update is constructed as follows:

```python
# Orchestrator Logic (Simplified)
payload = PushNotificationPayload(
    title=f"Configuration Update {version}",
    body=f"New configuration available for {device_id}",
    data={
        "config_url": "https://...",  # The Agent downloads this URL
        "config_version": "v2.1.0",
        "command": "APPLY_CONFIG"     # Implicit instruction
    },
    priority=PushPriority.HIGH,       # Wake up the device immediately
    ttl_seconds=300                   # Expire if not delivered in 5 mins
)
```

This confirms that **Data Payload** (`data`) is the most critical part for MDM. The `title` and `body` are for humans; the `data` dictionary is what the Agent reads to actually perform the update.
