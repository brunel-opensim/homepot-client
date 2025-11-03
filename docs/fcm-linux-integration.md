# FCM Linux Integration Guide

## Overview

This guide explains how to set up and use **Firebase Cloud Messaging (FCM)** with HOMEPOT Client to send push notifications to Android devices and Linux systems.

**What is FCM?**  
Firebase Cloud Messaging is Google's free service for sending notifications to Android phones, tablets, and Linux computers. Think of it as a way to instantly alert your POS terminals about important updates.

**When to use FCM:**
- Your POS terminals run on Android devices
- Your POS terminals run on Linux computers
- You need to send configuration updates to devices
- You want to notify terminals about payment gateway changes

---

## Quick Start

### Step 1: Get Firebase Credentials

Before you can send notifications, you need a Firebase account and credentials:

1. **Go to Firebase Console**
   - Visit: https://console.firebase.google.com/
   - Sign in with your Google account

2. **Create a Project**
   - Click "Add project"
   - Enter a project name (e.g., "HOMEPOT-Notifications")
   - Follow the setup wizard

3. **Download Service Account File**
   - In Firebase Console, click the gear icon (⚙️) → "Project settings"
   - Go to "Service accounts" tab
   - Click "Generate new private key"
   - Save the JSON file securely (e.g., `firebase-service-account.json`)

4. **Get Your Project ID**
   - In "Project settings" → "General" tab
   - Copy your "Project ID" (you'll need this later)

> **Important**: Keep your service account file secure! It's like a password for sending notifications.

---

### Step 2: Configure HOMEPOT Client

Edit your HOMEPOT configuration file to enable FCM:

```yaml
# config.yaml or environment variables

push_notifications:
  provider: "fcm_linux"  # Use FCM for Android/Linux devices
  
  fcm_config:
    service_account_path: "/path/to/firebase-service-account.json"
    project_id: "your-project-id"  # From Firebase Console
    batch_size: 500  # Optional: how many notifications to send at once
    timeout_seconds: 30  # Optional: how long to wait for responses
```

**What each setting means:**
- `provider`: Tells HOMEPOT to use FCM
- `service_account_path`: Where your Firebase credentials file is located
- `project_id`: Your Firebase project identifier
- `batch_size`: How many notifications to send in one batch (default: 500)
- `timeout_seconds`: How long to wait before giving up (default: 30)

---

### Step 3: Register Your Devices

Each device (POS terminal) needs a unique **FCM token**. Think of this like a device's phone number for notifications.

**How to get device tokens:**

On your Android or Linux device, your app needs to:

1. Import Firebase SDK
2. Request a registration token
3. Send that token to HOMEPOT

Example (Android/Java):
```java
FirebaseMessaging.getInstance().getToken()
    .addOnCompleteListener(task -> {
        String token = task.getResult();
        // Send this token to HOMEPOT
        System.out.println("FCM Token: " + token);
    });
```

The token looks like this:
```
fMXKz9vHRx2qwe...(about 152-163 characters)...xyz123
```

---

### Step 4: Send Your First Notification

Now you can send notifications to your devices!

**Example 1: Send to One Device**

```python
from homepot.push_notifications import get_notification_provider
from homepot.push_notifications.base import PushNotificationPayload, PushPriority

# Initialize the FCM provider
fcm_provider = get_notification_provider("fcm_linux", {
    "service_account_path": "/path/to/firebase-service-account.json",
    "project_id": "your-project-id"
})

await fcm_provider.initialize()

# Create your notification
notification = PushNotificationPayload(
    title="Configuration Update",
    body="New payment gateway settings are available",
    data={
        "config_version": "v1.2.3",
        "update_url": "https://example.com/config.json"
    },
    priority=PushPriority.HIGH
)

# Send to a specific device
device_token = "fMXKz9vH..."  # Your device's FCM token
result = await fcm_provider.send_notification(device_token, notification)

if result.success:
    print("Notification sent successfully!")
else:
    print(f"Failed: {result.error_message}")
```

**Example 2: Send to Multiple Devices**

```python
# List of devices to notify
devices = [
    ("device_token_1", notification),
    ("device_token_2", notification),
    ("device_token_3", notification),
]

# Send to all devices at once
results = await fcm_provider.send_bulk_notifications(devices)

# Check results
for i, result in enumerate(results):
    if result.success:
        print(f"Device {i+1}: Sent")
    else:
        print(f"Device {i+1}: Failed - {result.error_message}")
```

**Example 3: Send to a Topic (Broadcast)**

Topics let you send one notification to all devices subscribed to that topic:

```python
# Send to all devices subscribed to "pos-terminals" topic
result = await fcm_provider.send_topic_notification(
    topic="pos-terminals",
    payload=notification
)

if result.success:
    print("Broadcast sent to all terminals!")
```

---

## Understanding Notification Payloads

A notification has several parts:

```python
notification = PushNotificationPayload(
    title="Alert Title",           # What the user sees first
    body="Detailed message here",  # Main notification text
    data={                         # Extra data for your app
        "action": "update_config",
        "url": "https://..."
    },
    priority=PushPriority.HIGH,    # How urgent is this?
    ttl_seconds=3600,              # How long to keep trying (1 hour)
    collapse_key="config-update"   # Group similar notifications
)
```

**Field Explanations:**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `title` | Yes | Notification headline | "Configuration Update" |
| `body` | Yes | Detailed message | "Settings v1.2.3 available" |
| `data` | No | Custom data for your app | `{"version": "1.2.3"}` |
| `priority` | No | Urgency level | `HIGH`, `NORMAL`, `LOW` |
| `ttl_seconds` | No | Time to live (how long to retry) | `3600` (1 hour) |
| `collapse_key` | No | Group similar notifications | "config-update" |

---

## Priority Levels

Choose the right priority for your notifications:

| Priority | When to Use | Battery Impact | Example |
|----------|-------------|----------------|---------|
| `CRITICAL` | Emergencies only | High | "System breach detected!" |
| `HIGH` | Important updates | Medium | "New configuration required" |
| `NORMAL` | Regular updates | Low | "Daily report available" |
| `LOW` | Non-urgent info | Very Low | "Maintenance scheduled" |

> **Tip**: Use `HIGH` or `CRITICAL` sparingly to preserve device battery life.

---

## Payload Size Limits

FCM has a **4KB (4,096 bytes)** limit per notification.

**What fits in 4KB?**
- Short messages with data
- Configuration updates
- URLs and small JSON objects
- Large images or files
- Complete configuration files

**Example of size management:**

```python
# GOOD: Small payload
notification = PushNotificationPayload(
    title="Update Available",
    body="Version 1.2.3 is ready",
    data={"version": "1.2.3", "url": "https://example.com"}
)

# BAD: Too large
notification = PushNotificationPayload(
    title="Update",
    body="x" * 5000,  # Way too big!
    data={"huge_file": "..." * 1000}
)
```

If your payload is too large, you'll get an error:
```
Error: PAYLOAD_TOO_LARGE - Notification exceeds 4KB limit
```

**Solution**: Send a URL instead of large data:
```python
# Instead of sending the entire config, send a download link
notification = PushNotificationPayload(
    title="Config Update",
    body="Download new configuration",
    data={"download_url": "https://example.com/config.json"}
)
```

---

## Topics and Broadcasting

Topics let you organize devices into groups and send broadcasts.

**Step 1: Subscribe Devices to Topics**

On your device (Android/Java):
```java
FirebaseMessaging.getInstance().subscribeToTopic("pos-terminals")
    .addOnCompleteListener(task -> {
        System.out.println("Subscribed to topic!");
    });
```

**Step 2: Send to Topic**

```python
# Send one notification to all subscribed devices
await fcm_provider.send_topic_notification(
    topic="pos-terminals",
    payload=notification
)
```

**Common Topic Examples:**
- `all-devices` - Every device
- `pos-terminals` - Only POS terminals
- `production` - Production devices only
- `test-devices` - Testing devices

---

## Error Handling

FCM can fail for several reasons. Here's how to handle them:

```python
result = await fcm_provider.send_notification(device_token, notification)

if not result.success:
    error_code = result.error_code
    
    if error_code == "INVALID_TOKEN":
        print("Device token is invalid or expired")
        # Remove this token from your database
        
    elif error_code == "AUTHENTICATION_ERROR":
        print("Service account credentials are wrong")
        # Check your firebase-service-account.json file
        
    elif error_code == "QUOTA_EXCEEDED":
        print("You've sent too many notifications")
        # Wait a bit before sending more
        
    elif error_code == "PAYLOAD_TOO_LARGE":
        print("Notification is bigger than 4KB")
        # Reduce the size of your notification
        
    else:
        print(f"Unknown error: {result.error_message}")
```

**Common Error Codes:**

| Error Code | What It Means | How to Fix |
|------------|---------------|------------|
| `INVALID_TOKEN` | Device token is wrong/expired | Remove the token, ask device to re-register |
| `AUTHENTICATION_ERROR` | Credentials are invalid | Check service account file and project ID |
| `QUOTA_EXCEEDED` | Too many notifications sent | Wait before sending more, upgrade Firebase plan |
| `PAYLOAD_TOO_LARGE` | Notification exceeds 4KB | Reduce message size or use URLs |
| `NOT_FOUND` | Device uninstalled app | Remove token from database |
| `UNAVAILABLE` | FCM service is down | Retry later |

---

## Checking Provider Health

Monitor your FCM connection:

```python
# Check if FCM is working
health = await fcm_provider.health_check()

print(f"Status: {health['status']}")  # "healthy" or "unhealthy"
print(f"Platform: {health['platform']}")  # "fcm_linux"
print(f"Initialized: {health['initialized']}")  # True or False

# Get detailed information
info = await fcm_provider.get_platform_info()

print(f"Project ID: {info['project_id']}")
print(f"Service Status: {info['service_status']}")
print(f"Batch Size: {info['batch_size']}")
print(f"Has Credentials: {info['has_credentials']}")
```

---

## Best Practices

### Do's

1. **Use Topics for Broadcasting**
   - Instead of sending to 1000 devices individually, use topics
   - Faster and more efficient

2. **Set Appropriate TTL**
   ```python
   # For urgent updates: short TTL
   notification.ttl_seconds = 300  # 5 minutes
   
   # For non-urgent: longer TTL
   notification.ttl_seconds = 86400  # 24 hours
   ```

3. **Use Collapse Keys**
   - Group similar notifications together
   - Devices only see the latest one
   ```python
   notification.collapse_key = "config-update"
   ```

4. **Handle Errors Gracefully**
   - Always check `result.success`
   - Remove invalid tokens from database
   - Retry on temporary failures

5. **Keep Credentials Secure**
   - Never commit service account files to git
   - Use environment variables or secure vaults
   - Restrict file permissions: `chmod 600 firebase-service-account.json`

### Don'ts

1. **Don't Send Too Frequently**
   - Users will disable notifications
   - May hit rate limits
   - Drains device battery

2. **Don't Send Large Payloads**
   - Keep under 4KB
   - Use URLs for big data

3. **Don't Ignore Failed Tokens**
   - Clean up your database regularly
   - Remove expired/invalid tokens

4. **Don't Use CRITICAL Priority for Everything**
   - Reserve for real emergencies
   - Overuse reduces effectiveness

---

## Testing Without Real Devices

You can test FCM without actual devices using the simulation provider:

```python
# For testing/development
fcm_provider = get_notification_provider("simulation", {})
await fcm_provider.initialize()

# This will simulate sending (no real notification)
result = await fcm_provider.send_notification("test-token", notification)
print(result.success)  # True (simulated)
```

When you're ready for production, switch to `"fcm_linux"`.

---

## Troubleshooting

### Problem: "Authentication Error"

**Symptoms:**
```
Error: AUTHENTICATION_ERROR - Failed to authenticate with FCM
```

**Solutions:**
1. Check service account file path is correct
2. Verify JSON file is valid (open in text editor)
3. Ensure project ID matches Firebase Console
4. Regenerate service account key if needed

### Problem: "No Notifications Received"

**Check:**
1. Device token is correct and up-to-date
2. Device has internet connection
3. App has notification permissions enabled
4. Topic subscription is active (for topic messages)
5. Check device logs for errors

### Problem: "Quota Exceeded"

**Solutions:**
1. Upgrade your Firebase plan (free tier has limits)
2. Reduce notification frequency
3. Use topics instead of individual sends
4. Batch notifications together

### Problem: "Payload Too Large"

**Solutions:**
1. Remove unnecessary data from `data` field
2. Shorten `title` and `body` text
3. Use URLs instead of embedding full content
4. Split into multiple smaller notifications

---

## Complete Example

Here's a full working example:

```python
import asyncio
from homepot.push_notifications import get_notification_provider
from homepot.push_notifications.base import (
    PushNotificationPayload, 
    PushPriority
)

async def send_config_update():
    """Send configuration update to all POS terminals."""
    
    # Step 1: Initialize FCM provider
    fcm = get_notification_provider("fcm_linux", {
        "service_account_path": "/etc/homepot/firebase-key.json",
        "project_id": "homepot-notifications"
    })
    
    await fcm.initialize()
    
    # Step 2: Create notification
    notification = PushNotificationPayload(
        title="Configuration Update Available",
        body="Please restart your terminal to apply new payment gateway settings",
        data={
            "version": "1.2.3",
            "config_url": "https://api.homepot.com/config/v1.2.3",
            "action": "update_required"
        },
        priority=PushPriority.HIGH,
        ttl_seconds=3600,  # Valid for 1 hour
        collapse_key="config-update"
    )
    
    # Step 3: Send to all terminals (using topic)
    result = await fcm.send_topic_notification(
        topic="pos-terminals",
        payload=notification
    )
    
    # Step 4: Check result
    if result.success:
        print("Configuration update sent to all terminals!")
        print(f"Message ID: {result.message_id}")
    else:
        print(f"Failed to send: {result.error_message}")
        print(f"Error code: {result.error_code}")
    
    # Step 5: Cleanup
    await fcm.cleanup()

# Run it
if __name__ == "__main__":
    asyncio.run(send_config_update())
```

---

## Summary

**What You Learned:**
- How to set up Firebase and get credentials
- How to configure FCM in HOMEPOT
- How to send notifications to devices
- How to use topics for broadcasting
- How to handle errors properly
- Best practices for notifications

**Next Steps:**
1. Create your Firebase project
2. Download service account credentials
3. Configure HOMEPOT with FCM
4. Register your first device
5. Send a test notification
6. Monitor and optimize

**Need Help?**
- Firebase Documentation: https://firebase.google.com/docs/cloud-messaging
- HOMEPOT Issues: https://github.com/brunel-opensim/homepot-client/issues

---

**Last Updated:** December 2024  
**Version:** 1.0  
**For:** HOMEPOT Client v0.1.0+
