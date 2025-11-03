# WNS Windows Integration Guide

## Overview

This guide explains how to set up and use **Windows Notification Service (WNS)** with HOMEPOT Client to send push notifications to Windows devices.

**What is WNS?**  
Windows Notification Service is Microsoft's free service for sending notifications to Windows 10 and Windows 11 devices. Think of it as a way to instantly alert your Windows POS terminals about important updates.

**When to use WNS:**
- Your POS terminals run on Windows 10 or Windows 11
- Your POS terminals are Windows IoT devices
- You need to send configuration updates to Windows devices
- You want to update Live Tiles on the Windows Start menu
- You need background updates without showing notifications

---

## Quick Start

### Step 1: Register Your App with Microsoft

Before you can send notifications, you need to register your app with Microsoft:

1. **Go to Microsoft Partner Center**
   - Visit: <https://partner.microsoft.com/dashboard>
   - Sign in with your Microsoft account

2. **Create or Select Your App**
   - Click "Apps and games" → "Create a new app"
   - Or select your existing app

3. **Get Your WNS Credentials**
   - Go to **Product management** → **WNS/MPNS**
   - Note your **Package SID** (looks like: `ms-app://s-1-15-2-...`)
   - Click "Generate new secret" to get your **Client Secret**
   - Copy both - you'll need them soon!

> **Important**: Keep your Package SID and Client Secret secure! They're like passwords for sending notifications.

---

### Step 2: Configure HOMEPOT Client

Edit your HOMEPOT configuration file to enable WNS:

```yaml
# config.yaml or environment variables

push_notifications:
  provider: "wns_windows"  # Use WNS for Windows devices
  
  wns_config:
    package_sid: "ms-app://s-1-15-2-1234567890-..."
    client_secret: "your-client-secret-here"
    notification_type: "toast"  # Options: toast, tile, badge, raw
    batch_size: 100  # Optional: how many notifications to send at once
    timeout_seconds: 30  # Optional: how long to wait for responses
```

**What each setting means:**
- `provider`: Tells HOMEPOT to use WNS
- `package_sid`: Your app's unique identifier from Microsoft
- `client_secret`: Your secret key from Microsoft
- `notification_type`: What kind of notification to send (explained below)
- `batch_size`: How many notifications to send in one batch (default: 100)
- `timeout_seconds`: How long to wait before giving up (default: 30)

---

### Step 3: Register Your Devices

Each Windows device needs a unique **Channel URI**. Think of this like a device's mailing address for notifications.

**How to get Channel URIs:**

On your Windows device, your app needs to request a channel from Windows.

Example (C#/UWP):
```csharp
// Request a channel from Windows
var channel = await PushNotificationChannelManager
    .CreatePushNotificationChannelForApplicationAsync();

string channelUri = channel.Uri;

// Send this URI to HOMEPOT
Console.WriteLine($"Channel URI: {channelUri}");
```

The Channel URI looks like this:
```
https://db5.notify.windows.com/?token=AwYAAACUmm...
```

---

### Step 4: Send Your First Notification

Now you can send notifications to your Windows devices!

**Example 1: Send a Toast Notification (Pop-up)**

Toast notifications are the pop-up messages that appear on Windows screens.

```python
from homepot.push_notifications import get_notification_provider
from homepot.push_notifications.base import PushNotificationPayload, PushPriority

# Initialize the WNS provider
wns_provider = get_notification_provider("wns_windows", {
    "package_sid": "ms-app://s-1-15-2-...",
    "client_secret": "your-secret",
    "notification_type": "toast"  # Pop-up notification
})

await wns_provider.initialize()

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

# Send to a specific Windows device
channel_uri = "https://db5.notify.windows.com/?token=..."  # From your device
result = await wns_provider.send_notification(channel_uri, notification)

if result.success:
    print("Notification sent successfully!")
else:
    print(f"Failed: {result.error_message}")
```

**Example 2: Send to Multiple Devices**

```python
# List of devices to notify
devices = [
    ("https://db5.notify.windows.com/?token=Device1...", notification),
    ("https://db5.notify.windows.com/?token=Device2...", notification),
    ("https://db5.notify.windows.com/?token=Device3...", notification),
]

# Send to all devices at once
results = await wns_provider.send_bulk_notifications(devices)

# Check results
for i, result in enumerate(results):
    if result.success:
        print(f"Device {i+1}: Sent")
    else:
        print(f"Device {i+1}: Failed - {result.error_message}")
```

**Example 3: Update a Live Tile (Start Menu)**

Tile notifications update the app's tile on the Windows Start menu.

```python
# Configure for Live Tile updates
wns_tile = get_notification_provider("wns_windows", {
    "package_sid": "ms-app://s-1-15-2-...",
    "client_secret": "your-secret",
    "notification_type": "tile"  # Live Tile update
})

await wns_tile.initialize()

# Create tile notification
tile_notification = PushNotificationPayload(
    title="5 / 5 Terminals",
    body="All systems operational",
    data={"status": "healthy"}
)

result = await wns_tile.send_notification(channel_uri, tile_notification)
```

---

## Understanding Notification Types

WNS supports 4 different types of notifications:

### 1. Toast (Pop-up Notifications)

**What it is:** A pop-up message that appears on the Windows screen  
**When to use:** Important updates that users should see immediately  
**Example:** "Configuration update available"

```python
config["notification_type"] = "toast"
```

### 2. Tile (Live Tile Updates)

**What it is:** Updates the app's tile on the Windows Start menu  
**When to use:** Status displays, counters, quick info  
**Example:** "5/5 terminals online"

```python
config["notification_type"] = "tile"
```

### 3. Badge (Icon or Number)

**What it is:** Shows a small number or icon on the app tile  
**When to use:** Unread count, status indicators  
**Example:** Show "3" to indicate 3 pending updates

```python
config["notification_type"] = "badge"

# Show number 3 on the badge
payload = PushNotificationPayload(
    title="Badge Update",
    body="Updates available",
    data={"badge_value": 3}
)
```

### 4. Raw (Background Updates)

**What it is:** Silent notification delivered to your app's background task  
**When to use:** Updates that don't need to show anything to the user  
**Example:** Download new configuration silently

```python
config["notification_type"] = "raw"

# Silent background update
payload = PushNotificationPayload(
    title="Silent Update",
    body="Background configuration update",
    data={
        "action": "update_config",
        "restart_required": True
    }
)
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

WNS has a **5KB (5,120 bytes)** limit per notification.

**What fits in 5KB?**
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
    body="x" * 6000,  # Way too big!
    data={"huge_file": "..." * 2000}
)
```

If your payload is too large, you'll get an error:
```
Error: PAYLOAD_TOO_LARGE - Notification exceeds 5KB limit
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

## Channel URI Management

### What is a Channel URI?

A **Channel URI** is like a device's unique mailing address for notifications. Each Windows device gets its own Channel URI from Microsoft's WNS service.

**Channel URI Example:**
```
https://db5.notify.windows.com/?token=AwYAAACUmm...
```

### How Devices Get Channel URIs

On your Windows device, your app requests a Channel URI from Windows:

**C# Example (UWP/Windows App):**
```csharp
// Request a channel from Windows
var channel = await PushNotificationChannelManager
    .CreatePushNotificationChannelForApplicationAsync();

string channelUri = channel.Uri;

// Now send this URI to your HOMEPOT server
Console.WriteLine($"Channel URI: {channelUri}");
```

**JavaScript Example (Windows JavaScript App):**
```javascript
// Request a channel from WNS
const channelOperation = Windows.Networking.PushNotifications
    .PushNotificationChannelManager.createPushNotificationChannelForApplicationAsync();

channelOperation.then(function (channel) {
    const channelUri = channel.uri;
    console.log("Channel URI:", channelUri);
    
    // Send this to HOMEPOT
    registerDeviceWithHomepot(channelUri);
});
```

### Validating Channel URIs

HOMEPOT automatically validates Channel URIs:

```python
# Check if a Channel URI is valid
is_valid = wns_provider.validate_device_token(channel_uri)

if is_valid:
    print("Channel URI is valid")
else:
    print("Channel URI is invalid")
```

**Valid Channel URIs must:**
- Start with `https://`
- Contain a Microsoft WNS domain (like `notify.windows.com`)
- Be between 100-200 characters long

---

## Error Handling

WNS can fail for several reasons. Here's how to handle them:

```python
result = await wns_provider.send_notification(channel_uri, notification)

if not result.success:
    error_code = result.error_code
    
    if error_code == "CHANNEL_EXPIRED":
        print("Channel has expired (device needs to re-register)")
        # Remove this channel from your database
        
    elif error_code == "INVALID_CHANNEL_URI":
        print("Channel URI format is wrong")
        # Validate and update the URI
        
    elif error_code == "UNAUTHORIZED":
        print("Authentication failed")
        # Check your Package SID and Client Secret
        
    elif error_code == "THROTTLED":
        print("You're sending too many notifications")
        # Wait before sending more
        
    elif error_code == "PAYLOAD_TOO_LARGE":
        print("Notification is bigger than 5KB")
        # Reduce the size of your notification
        
    else:
        print(f"Unknown error: {result.error_message}")
```

**Common Error Codes:**

| Error Code | What It Means | How to Fix |
|------------|---------------|------------|
| `INVALID_CHANNEL_URI` | Channel URI format is wrong | Validate the URI format |
| `CHANNEL_EXPIRED` | Channel has expired (404) | Device needs to re-register |
| `CHANNEL_GONE` | Channel permanently deleted (410) | Remove device from database |
| `UNAUTHORIZED` | Authentication failed (401) | Check Package SID and Client Secret |
| `FORBIDDEN` | Permission denied (403) | Verify your app registration |
| `THROTTLED` | Too many requests (406) | Wait before sending more |
| `PAYLOAD_TOO_LARGE` | Notification exceeds 5KB (413) | Reduce payload size |
| `SERVICE_UNAVAILABLE` | WNS is temporarily down (503) | Retry later |

---

## Handling Expired Channels

Channel URIs can expire or become invalid over time. Here's how to handle it:

```python
result = await wns_provider.send_notification(channel_uri, notification)

if result.error_code == "CHANNEL_EXPIRED":
    print("Channel expired - asking device to re-register")
    # Mark device as needing re-registration
    # Device will request a new channel URI next time it connects
    
elif result.error_code == "CHANNEL_GONE":
    print("Channel permanently gone - removing device")
    # Remove this device from your database
    # The app was probably uninstalled
```

**Why do channels expire?**
- User uninstalled the app
- Windows reset the channel
- Channel wasn't used for a long time (30 days)
- Device was reset or reimaged

---

## Best Practices

### Do's

1. **Use Environment Variables for Credentials**
   ```python
   import os
   
   config = {
       "package_sid": os.getenv("WNS_PACKAGE_SID"),
       "client_secret": os.getenv("WNS_CLIENT_SECRET"),
   }
   ```

2. **Choose the Right Notification Type**
   - Use **Toast** for important user-facing alerts
   - Use **Tile** for status displays
   - Use **Badge** for counters
   - Use **Raw** for silent background updates

3. **Handle Errors Gracefully**
   - Always check `result.success`
   - Remove expired channels from database
   - Retry on temporary failures (503)

4. **Use Batch Operations for Multiple Devices**
   ```python
   # Faster than sending one by one
   results = await wns_provider.send_bulk_notifications(devices)
   ```

5. **Set Appropriate TTL**
   ```python
   # For urgent updates: short TTL
   notification.ttl_seconds = 300  # 5 minutes
   
   # For non-urgent: longer TTL
   notification.ttl_seconds = 86400  # 24 hours
   ```

### Don'ts

1. **Don't Hardcode Credentials**
   ```python
   # BAD - credentials exposed in code
   config = {
       "package_sid": "ms-app://s-1-15-2-...",  # Bad!
       "client_secret": "your-secret",  # Very bad!
   }
   
   # GOOD - use environment variables
   config = {
       "package_sid": os.getenv("WNS_PACKAGE_SID"),
       "client_secret": os.getenv("WNS_CLIENT_SECRET"),
   }
   ```

2. **Don't Send Too Frequently**
   - Users will disable notifications
   - May hit rate limits
   - Drains device battery

3. **Don't Send Large Payloads**
   - Keep under 5KB
   - Use URLs for big data

4. **Don't Ignore Expired Channels**
   - Clean up your database regularly
   - Remove invalid channels

5. **Don't Use CRITICAL Priority for Everything**
   - Reserve for real emergencies
   - Overuse reduces effectiveness

---

---

## Checking Provider Health

Monitor your WNS connection:

```python
# Check if WNS is working
health = await wns_provider.health_check()

print(f"Status: {health['status']}")  # "healthy" or "unhealthy"
print(f"Platform: {health['platform']}")  # "wns_windows"
print(f"Initialized: {health['initialized']}")  # True or False

# Get detailed information
info = await wns_provider.get_platform_info()

print(f"Platform: {info['platform']}")
print(f"Service Status: {info['service_status']}")
print(f"Notification Type: {info['notification_type']}")
print(f"Token Valid: {info['token_valid']}")
```

---

## Testing Without Real Devices

You can test WNS without actual Windows devices using the simulation provider:

```python
# For testing/development
wns_provider = get_notification_provider("simulation", {})
await wns_provider.initialize()

# This will simulate sending (no real notification)
result = await wns_provider.send_notification("test-channel", notification)
print(result.success)  # True (simulated)
```

When you're ready for production, switch to `"wns_windows"`.

---

## Troubleshooting

### Problem: "Authentication Failed" (401)

**Symptoms:**
```
Error: UNAUTHORIZED - Authentication failed
```

**Solutions:**
1. Verify Package SID is correct (should start with `ms-app://s-1-15-2-`)
2. Check Client Secret hasn't expired
3. Regenerate Client Secret in Microsoft Partner Center if needed
4. Ensure no extra spaces in credentials

### Problem: "Channel Expired" (404)

**Symptoms:**
```
Error: CHANNEL_EXPIRED - Channel not found
```

**Solutions:**
1. Device needs to request a new Channel URI from Windows
2. Remove expired channel from your database
3. Wait for device to re-register with new channel

### Problem: "Service Unavailable" (503)

**Symptoms:**
```
Error: SERVICE_UNAVAILABLE - WNS is temporarily down
```

**Solutions:**
1. This is temporary - Microsoft's servers are busy
2. Implement retry logic with delays
3. Wait a few minutes and try again
4. Check Microsoft's service status page

### Problem: "Payload Too Large" (413)

**Symptoms:**
```
Error: PAYLOAD_TOO_LARGE - Notification exceeds 5KB limit
```

**Solutions:**
1. Remove unnecessary data from `data` field
2. Shorten `title` and `body` text
3. Use URLs instead of embedding full content
4. Split into multiple smaller notifications

### Problem: "Too Many Requests" (406)

**Symptoms:**
```
Error: THROTTLED - Rate limit exceeded
```

**Solutions:**
1. Slow down - you're sending too fast
2. Use batch operations instead of individual sends
3. Wait for the `retry_after` time before sending more
4. Reduce notification frequency

---

## Complete Example

Here's a full working example:

```python
import asyncio
import os
from homepot.push_notifications import get_notification_provider
from homepot.push_notifications.base import (
    PushNotificationPayload, 
    PushPriority
)

async def send_config_update():
    """Send configuration update to all Windows POS terminals."""
    
    # Step 1: Initialize WNS provider
    wns = get_notification_provider("wns_windows", {
        "package_sid": os.getenv("WNS_PACKAGE_SID"),
        "client_secret": os.getenv("WNS_CLIENT_SECRET"),
        "notification_type": "toast"
    })
    
    await wns.initialize()
    
    # Step 2: Create notification
    notification = PushNotificationPayload(
        title="Configuration Update Available",
        body="Please restart your terminal to apply new settings",
        data={
            "version": "1.2.3",
            "config_url": "https://api.homepot.com/config/v1.2.3",
            "action": "update_required"
        },
        priority=PushPriority.HIGH,
        ttl_seconds=3600,  # Valid for 1 hour
        collapse_key="config-update"
    )
    
    # Step 3: Get device channel URIs from database
    # (In real app, you'd get these from your database)
    channel_uris = [
        "https://db5.notify.windows.com/?token=Device1...",
        "https://db5.notify.windows.com/?token=Device2...",
        "https://db5.notify.windows.com/?token=Device3...",
    ]
    
    # Step 4: Send to all terminals (batch operation)
    devices = [(uri, notification) for uri in channel_uris]
    results = await wns.send_bulk_notifications(devices)
    
    # Step 5: Check results
    successful = sum(1 for r in results if r.success)
    print(f"Sent to {successful}/{len(results)} terminals")
    
    # Handle failures
    for i, result in enumerate(results):
        if not result.success:
            print(f"Terminal {i+1}: {result.error_code} - {result.error_message}")
            
            # Handle expired channels
            if result.error_code == "CHANNEL_EXPIRED":
                print(f"   → Removing expired channel from database")
                # Remove from your database
    
    # Step 6: Cleanup
    await wns.cleanup()
    print("Update complete!")

# Run it
if __name__ == "__main__":
    asyncio.run(send_config_update())
```

---

## Security Tips

### 1. Protect Your Credentials

```bash
# Store in environment variables (not in code!)
export WNS_PACKAGE_SID="ms-app://s-1-15-2-..."
export WNS_CLIENT_SECRET="your-secret"
```

```python
# Load from environment
import os

config = {
    "package_sid": os.getenv("WNS_PACKAGE_SID"),
    "client_secret": os.getenv("WNS_CLIENT_SECRET"),
}
```

### 2. Rotate Secrets Regularly

1. Go to Microsoft Partner Center
2. Generate a new Client Secret
3. Update your environment variable
4. Restart HOMEPOT Client
5. Delete the old secret after confirming the new one works

### 3. Use HTTPS Everywhere

WNS only works over HTTPS - all communication is encrypted automatically.

### 4. Validate Channel URIs

```python
# Always validate before sending
if wns_provider.validate_device_token(channel_uri):
    result = await wns_provider.send_notification(channel_uri, notification)
else:
    print("Invalid channel URI - skipping")
```

---

## Summary

**What You Learned:**
- How to register your app with Microsoft
- How to get Package SID and Client Secret
- How to configure WNS in HOMEPOT
- How to send all 4 notification types (Toast, Tile, Badge, Raw)
- How to manage Channel URIs
- How to handle errors properly
- Best practices for notifications

**Next Steps:**
1. Register your app with Microsoft Partner Center
2. Get your Package SID and Client Secret
3. Configure HOMEPOT with WNS
4. Register your first Windows device
5. Send a test notification
6. Monitor and optimize

**Need Help?**
- WNS Documentation: <https://docs.microsoft.com/en-us/windows/uwp/design/shell/tiles-and-notifications/windows-push-notification-services--wns--overview>
- HOMEPOT Issues: <https://github.com/brunel-opensim/homepot-client/issues>

---

**Last Updated:** December 2024  
**Version:** 1.0  
**For:** HOMEPOT Client v0.1.0+
