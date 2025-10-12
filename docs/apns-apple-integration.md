# APNs Integration Guide

## Overview

This guide explains how to set up and use **Apple Push Notification service (APNs)** with HOMEPOT Client to send push notifications to Apple devices.

**What is APNs?**  
Apple Push Notification service is Apple's free service for sending notifications to iPhones, iPads, Macs, Apple Watches, and Apple TVs. Think of it as a way to instantly alert your Apple POS terminals about important updates.

**When to use APNs:**
- Your POS terminals run on iOS (iPhone/iPad)
- Your POS terminals run on macOS (Mac computers)
- You have Apple Watch or Apple TV-based terminals
- You need to send configuration updates to Apple devices
- You want to notify terminals about payment gateway changes
- You need badge updates on app icons

---

## Quick Start

### Step 1: Get Apple Developer Credentials

Before you can send notifications, you need an Apple Developer account and credentials:

1. **Enroll in Apple Developer Program**
   - Visit: <https://developer.apple.com/programs/>
   - Sign up for the program ($99/year for organizations)
   - Complete enrollment and verification

2. **Create an App ID**
   - Go to: <https://developer.apple.com/account>
   - Select "Certificates, Identifiers & Profiles"
   - Click "Identifiers" → Click the "+" button
   - Select "App IDs" → Click "Continue"
   - Enter a description (e.g., "HOMEPOT Client")
   - Enter a Bundle ID (e.g., `com.homepot.client`)
   - Check "Push Notifications" capability
   - Click "Continue" → "Register"

3. **Create APNs Authentication Key (Recommended)**
   - Go to "Keys" section → Click the "+" button
   - Enter a key name (e.g., "HOMEPOT APNs Key")
   - Check "Apple Push Notifications service (APNs)"
   - Click "Continue" → "Register"
   - **Download the `.p8` file immediately** (you can't download it again!)
   - Note your **Key ID** (10 characters, like `XYZ987WXYZ`)
   - Note your **Team ID** (10 characters, in "Membership" section)

> **Important**: Keep your `.p8` file secure! It's like a master key for sending notifications to all your apps.

> **Why .p8 instead of certificates?** Token-based authentication (`.p8` files) is easier to use, doesn't expire yearly, and works for all your apps. Certificate-based authentication requires renewal every year and separate certificates per app.

---

### Step 2: Configure HOMEPOT Client

Edit your HOMEPOT configuration file to enable APNs:

```yaml
# config.yaml or environment variables

push_notifications:
  provider: "apns"  # Use APNs for Apple devices
  
  apns_config:
    team_id: "ABC123DEFG"  # Your 10-character Team ID
    key_id: "XYZ987WXYZ"   # Your 10-character Key ID
    auth_key_path: "/path/to/AuthKey_XYZ987WXYZ.p8"  # Path to .p8 file
    bundle_id: "com.homepot.client"  # Your app's Bundle ID
    environment: "production"  # Options: production, sandbox
    topic: "com.homepot.client"  # Usually same as bundle_id
```

**What each setting means:**
- `provider`: Tells HOMEPOT to use APNs
- `team_id`: Your Apple Developer Team identifier (found in "Membership" section)
- `key_id`: The ID of your APNs authentication key
- `auth_key_path`: Where your `.p8` private key file is located
- `bundle_id`: Your app's unique identifier
- `environment`: Use `production` for live apps, `sandbox` for testing
- `topic`: The notification topic (usually your bundle ID)

**Finding Your Team ID:**
1. Go to <https://developer.apple.com/account>
2. Click "Membership" in the left sidebar
3. Your Team ID is listed there (10 characters)

---

### Step 3: Register Your Devices

Each Apple device needs a unique **Device Token**. Think of this like a device's phone number for notifications.

**How to get device tokens:**

On your iOS/macOS device, your app needs to:

1. Request notification permissions
2. Register for remote notifications
3. Receive a device token
4. Send that token to HOMEPOT

**Example (iOS/Swift):**
```swift
import UserNotifications

// 1. Request permission
UNUserNotificationCenter.current().requestAuthorization(
    options: [.alert, .sound, .badge]
) { granted, error in
    if granted {
        // 2. Register for remote notifications
        DispatchQueue.main.async {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }
}

// 3. Receive device token
func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
) {
    // Convert to hex string
    let token = deviceToken.map { String(format: "%02x", $0) }.joined()
    
    // Send this token to HOMEPOT
    print("APNs Device Token: \(token)")
    // Example: "a1b2c3d4e5f6..."
}
```

**Example (macOS/Swift):**
```swift
import Cocoa

// In your AppDelegate
func applicationDidFinishLaunching(_ notification: Notification) {
    NSApp.registerForRemoteNotifications()
}

func application(
    _ application: NSApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
) {
    let token = deviceToken.map { String(format: "%02x", $0) }.joined()
    print("APNs Device Token: \(token)")
}
```

The device token is **exactly 64 hexadecimal characters**, like:
```
a1b2c3d4e5f6789012345678901234567890abcdefabcdef1234567890abcd
```

---

### Step 4: Send Your First Notification

Now you can send notifications to your Apple devices!

#### Python Example

```python
from homepot_client.push_notifications import get_push_provider
from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority
)

# Configuration
apns_config = {
    "team_id": "ABC123DEFG",
    "key_id": "XYZ987WXYZ",
    "auth_key_path": "/path/to/AuthKey_XYZ987WXYZ.p8",
    "bundle_id": "com.homepot.client",
    "environment": "production",
    "topic": "com.homepot.client"
}

# Initialize APNs provider
provider = await get_push_provider("apns", apns_config)

# Device token (from your iOS/macOS app)
device_token = "a1b2c3d4e5f6789012345678901234567890abcdefabcdef1234567890abcd"

# Create notification
payload = PushNotificationPayload(
    title="Payment Pending",
    body="Transaction #12345 awaiting approval at Terminal POS-001",
    data={
        "transaction_id": "12345",
        "pos_id": "POS-001",
        "amount": "150.00",
        "action": "approve_payment"
    },
    priority=PushPriority.HIGH
)

# Send notification
result = await provider.send_notification(device_token, payload)

if result.success:
    print(f"Notification sent! ID: {result.message_id}")
else:
    print(f"Failed: {result.message} (Error: {result.error_code})")
```

**What you should see:**
```
Notification sent! ID: 12345678-ABCD-1234-5678-1234567890AB
```

On the device, you'll see:
```
Payment Pending
   Transaction #12345 awaiting approval at Terminal POS-001
```

---

## Understanding APNs Notification Types

APNs supports different types of notifications for different purposes:

### 1. Alert Notifications (Most Common)

Visual notifications with title, body, sound, and badge.

```python
payload = PushNotificationPayload(
    title="New Transaction",
    body="Customer payment received: $150.00",
    platform_data={
        "badge": 5,          # Red badge number on app icon
        "sound": "default"   # Plays notification sound
    }
)
```

**What the user sees:**
- Banner or alert on screen
- Sound plays
- Badge appears on app icon

---

### 2. Silent Background Notifications

Updates app data without showing any notification to the user.

```python
payload = PushNotificationPayload(
    title="Background Update",
    body="Syncing configuration",
    platform_data={
        "content_available": True,  # Enable background mode
        "sound": None                # No sound
    }
)
```

**What happens:**
- App wakes up in background
- Performs data sync
- User sees nothing

**Use cases:**
- Configuration updates
- Price list updates
- Menu synchronization

---

### 3. Badge Updates

Update the app icon badge number without showing a notification.

```python
payload = PushNotificationPayload(
    title="Badge Update",
    body="",
    platform_data={
        "badge": 3,      # Update to 3 pending items
        "sound": None    # Silent
    }
)
```

---

### 4. Custom Sounds

Use your own notification sounds.

```python
payload = PushNotificationPayload(
    title="High Priority Alert",
    body="System error detected",
    platform_data={
        "sound": "critical_alert.caf"  # Custom sound file
    }
)
```

> **Note**: Custom sound files must be in your app's bundle and in AIFF, WAV, or CAF format, maximum 30 seconds.

---

### 5. Actionable Notifications

Add action buttons to notifications.

```python
payload = PushNotificationPayload(
    title="Transaction Pending",
    body="Approve or decline transaction #12345?",
    platform_data={
        "category": "TRANSACTION_ACTIONS"  # Matches category in your app
    }
)
```

In your app, define the category:
```swift
let approveAction = UNNotificationAction(
    identifier: "APPROVE",
    title: "Approve",
    options: .foreground
)

let declineAction = UNNotificationAction(
    identifier: "DECLINE",
    title: "Decline",
    options: .destructive
)

let category = UNNotificationCategory(
    identifier: "TRANSACTION_ACTIONS",
    actions: [approveAction, declineAction],
    intentIdentifiers: []
)

UNUserNotificationCenter.current().setNotificationCategories([category])
```

User sees notification with "Approve" and "Decline" buttons.

---

## Notification Priority Levels

APNs has two priority levels:

| Priority | APNs Value | Behavior | Use For |
|----------|-----------|----------|---------|
| **HIGH / CRITICAL** | 10 | Immediate delivery, wakes device | Urgent alerts, transactions, errors |
| **NORMAL / LOW** | 5 | Conserves battery, may delay | Updates, news, non-urgent info |

```python
# High priority (immediate)
payload = PushNotificationPayload(
    title="Critical Alert",
    body="Payment gateway offline",
    priority=PushPriority.HIGH  # Delivers immediately
)

# Normal priority (battery-efficient)
payload = PushNotificationPayload(
    title="Daily Report",
    body="Sales summary ready",
    priority=PushPriority.NORMAL  # May delay delivery
)
```

---

## Sending Bulk Notifications

Send to multiple devices efficiently using HTTP/2 multiplexing:

```python
# List of (device_token, payload) tuples
notifications = [
    ("device_token_1", payload_for_device_1),
    ("device_token_2", payload_for_device_2),
    ("device_token_3", payload_for_device_3),
    # ... up to hundreds of devices
]

# Send all at once
results = await provider.send_bulk_notifications(notifications)

# Check results
for result in results:
    if result.success:
        print(f"Sent to {result.device_token}")
    else:
        print(f"Failed {result.device_token}: {result.error_code}")
```

**Performance:**
- HTTP/2 allows concurrent requests over one connection
- Much faster than sending one-by-one
- Recommended for 10+ devices

---

## Error Handling

APNs returns specific error codes. Here's how to handle them:

### Common Error Codes

| Error Code | Status | Meaning | What to Do |
|------------|--------|---------|------------|
| `SUCCESS` | 200 | Notification sent | Nothing, success! |
| `BAD_REQUEST` | 400 | Invalid payload | Check your notification format |
| `AUTH_FAILED` | 403 | Invalid credentials | Verify Team ID, Key ID, and .p8 file |
| `NOT_FOUND` | 404 | Invalid token/topic | Check device token and bundle ID |
| `UNREGISTERED` | 410 | Device uninstalled app | **Remove token from database** |
| `PAYLOAD_TOO_LARGE` | 413 | Payload > 4KB | Reduce notification size |
| `TOO_MANY_REQUESTS` | 429 | Rate limit exceeded | Slow down, retry later |
| `SERVER_ERROR` | 500/503 | APNs server issue | Retry with backoff |

### Handling Unregistered Devices (410)

**Critical**: When you get a `410` error, it means the user uninstalled your app. You **must** delete that token from your database.

```python
result = await provider.send_notification(device_token, payload)

if result.error_code == "UNREGISTERED":
    # User uninstalled the app - remove token from database
    await database.delete_device_token(device_token)
    print(f"Removed unregistered device: {device_token}")
```

### Example Error Handling

```python
result = await provider.send_notification(device_token, payload)

if result.success:
    print(f"Notification sent")
    
elif result.error_code == "UNREGISTERED":
    # App uninstalled - remove from database
    await remove_device_from_database(device_token)
    
elif result.error_code == "AUTH_FAILED":
    # Credentials problem
    print("Check your Team ID, Key ID, and .p8 file")
    
elif result.error_code == "TOO_MANY_REQUESTS":
    # Rate limited - wait and retry
    await asyncio.sleep(result.retry_after or 60)
    result = await provider.send_notification(device_token, payload)
    
elif result.error_code == "SERVER_ERROR":
    # APNs server issue - retry
    await asyncio.sleep(30)
    result = await provider.send_notification(device_token, payload)
    
else:
    print(f"Error: {result.message}")
```

---

## Production vs Sandbox Environments

APNs has two environments for testing and production:

### Sandbox Environment (Testing)

Use for development and testing:

```python
apns_config = {
    # ... other config
    "environment": "sandbox"
}
```

- **Endpoint**: `api.sandbox.push.apple.com`
- **Use with**: Development builds, TestFlight apps
- **Device tokens**: From devices with development profiles

### Production Environment (Live Apps)

Use for App Store releases:

```python
apns_config = {
    # ... other config
    "environment": "production"
}
```

- **Endpoint**: `api.push.apple.com`
- **Use with**: App Store apps
- **Device tokens**: From devices with production apps

> **Important**: Device tokens from sandbox environment **will not work** in production environment and vice versa!

---

## Payload Size Limits

APNs has strict size limits:

| Limit | Size | What Happens if Exceeded |
|-------|------|--------------------------|
| **Maximum payload** | 4096 bytes (4 KB) | Notification rejected with 413 error |
| **Recommended size** | < 2 KB | Faster delivery, better performance |

**What counts toward the limit:**
- Title and body text
- Custom data fields
- All JSON structure
- Everything in the payload!

### Check Payload Size

```python
import json

# Build payload
payload = PushNotificationPayload(
    title="Very Long Title" * 100,  # Too long!
    body="Message",
    data={"large_data": "x" * 5000}  # Too much data!
)

# APNs provider will automatically check
result = await provider.send_notification(device_token, payload)

if result.error_code == "PAYLOAD_TOO_LARGE":
    print(f"Payload exceeds 4KB limit - reduce content")
```

### Tips to Reduce Payload Size

1. **Keep titles short**: "Payment Pending" not "Transaction Payment is Currently Pending Approval"
2. **Minimize custom data**: Send IDs, not full records
3. **Use abbreviations**: `tx_id` instead of `transaction_identifier`
4. **Fetch details in app**: Send notification ID, let app fetch details

---

## Testing Your APNs Integration

### Test Checklist

- [ ] Device token is exactly 64 hexadecimal characters
- [ ] `.p8` file path is correct and file exists
- [ ] Team ID is correct (10 characters)
- [ ] Key ID is correct (10 characters)
- [ ] Bundle ID matches your app
- [ ] Environment matches your app (sandbox vs production)
- [ ] Topic matches your bundle ID
- [ ] Notification permissions granted on device
- [ ] Device is connected to internet

### Testing with cURL

You can test APNs directly without HOMEPOT:

```bash
# Generate JWT token (using openssl)
# This is complex - better to use the HOMEPOT provider!

# But if you want to test manually:
curl -v \
  --header "authorization: bearer $JWT_TOKEN" \
  --header "apns-topic: com.homepot.client" \
  --header "apns-priority: 10" \
  --data '{"aps":{"alert":{"title":"Test","body":"Testing APNs"}}}' \
  https://api.push.apple.com/3/device/$DEVICE_TOKEN
```

### Testing with HOMEPOT

Much easier - use the built-in health check:

```python
# Check if APNs is working
provider = await get_push_provider("apns", apns_config)
health = await provider.health_check()

print(f"Status: {health['status']}")
print(f"Environment: {health['platform_info']['environment']}")
print(f"JWT Valid: {health['platform_info']['jwt_valid']}")
```

---

## Troubleshooting

### Problem: "Invalid credentials" (403 error)

**Symptoms:**
- Get `AUTH_FAILED` error
- Can't send any notifications

**Solutions:**
1. Verify Team ID is correct (10 characters)
2. Verify Key ID matches your downloaded `.p8` file
3. Check `.p8` file path is correct
4. Ensure `.p8` file is readable (check file permissions)
5. Make sure you're using the correct Apple Developer account

```bash
# Check if file exists and is readable
ls -la /path/to/AuthKey_XYZ987WXYZ.p8
```

---

### Problem: "Token no longer valid" (410 error)

**Symptoms:**
- Get `UNREGISTERED` error for specific device
- Notification worked before but stopped

**Explanation:**
User uninstalled your app or disabled notifications.

**Solution:**
Remove that device token from your database:

```python
if result.error_code == "UNREGISTERED":
    # Delete from database
    await db.execute(
        "DELETE FROM device_tokens WHERE token = ?",
        (device_token,)
    )
```

---

### Problem: "Invalid device token" (404 error)

**Symptoms:**
- Get `NOT_FOUND` error
- Device token looks wrong

**Solutions:**
1. Verify token is exactly 64 hexadecimal characters
2. Check no extra spaces or newlines in token
3. Ensure token is from the correct environment (sandbox vs production)
4. Verify app bundle ID matches configuration

```python
# Validate token format
token = device_token.strip()  # Remove whitespace
if len(token) != 64:
    print(f"Invalid token length: {len(token)} (should be 64)")
```

---

### Problem: Notification not appearing on device

**Symptoms:**
- No error, but user doesn't see notification
- Success response from APNs

**Solutions:**

1. **Check device settings:**
   - Settings → Notifications → Your App → Allow Notifications
   - Banner Style set to "Persistent" or "Temporary"
   - Sounds enabled

2. **Check notification format:**
   ```python
   # Make sure you have title AND body
   payload = PushNotificationPayload(
       title="Test",      # Required!
       body="Testing",    # Required!
   )
   ```

3. **Check if background notification:**
   ```python
   # Background notifications don't show UI
   platform_data={
       "content_available": True  # This makes it silent!
   }
   ```

4. **Check environment:**
   - Development build → Use sandbox environment
   - App Store build → Use production environment

5. **Check Do Not Disturb:**
   - Device may be in Do Not Disturb mode
   - Try scheduling notification

---

### Problem: "Payload too large" (413 error)

**Symptoms:**
- Get `PAYLOAD_TOO_LARGE` error
- Notification has lots of data

**Solution:**
Reduce payload size to under 4KB:

```python
# Before (too large)
payload = PushNotificationPayload(
    title="Transaction Report",
    body="Here are all the details...",
    data={
        "full_report": "... 5KB of data ..."  # Too much!
    }
)

# After (optimized)
payload = PushNotificationPayload(
    title="Report Ready",
    body="Tap to view",
    data={
        "report_id": "12345"  # Just the ID, fetch details in app
    }
)
```

---

### Problem: "Too many requests" (429 error)

**Symptoms:**
- Get `TOO_MANY_REQUESTS` error
- Sending many notifications quickly

**Solution:**
Implement rate limiting and backoff:

```python
# Use bulk send for many devices
results = await provider.send_bulk_notifications(notifications)

# Or add delays between sends
for device_token, payload in notifications:
    result = await provider.send_notification(device_token, payload)
    
    if result.error_code == "TOO_MANY_REQUESTS":
        # Wait before retrying
        wait_time = result.retry_after or 60
        await asyncio.sleep(wait_time)
        result = await provider.send_notification(device_token, payload)
```

---

## Best Practices

### 1. Token Management

**Do:**
- Store device tokens in your database
- Update tokens when they change
- Remove tokens that return 410 errors

**Don't:**
- Hardcode device tokens
- Ignore 410 errors
- Keep invalid tokens

### 2. Security

**Do:**
- Keep `.p8` file secure (never commit to git)
- Use environment variables for credentials
- Restrict file permissions: `chmod 600 AuthKey_*.p8`

**Don't:**
- Share `.p8` files publicly
- Include credentials in code
- Store credentials in version control

```bash
# Add to .gitignore
echo "*.p8" >> .gitignore
echo "*.pem" >> .gitignore
```

### 3. Error Handling

**Do:**
- Log all errors for debugging
- Retry on server errors (500/503)
- Remove tokens on 410 errors
- Implement exponential backoff

**Don't:**
- Ignore errors silently
- Retry infinitely
- Keep sending to invalid tokens

### 4. Payload Optimization

**Do:**
- Keep payloads small (< 2KB ideal)
- Use IDs instead of full data
- Test payload sizes
- Localize messages on device

**Don't:**
- Send full database records
- Include unnecessary data
- Use very long messages

### 5. Testing

**Do:**
- Test with sandbox environment first
- Test on real devices
- Test error scenarios
- Monitor APNs logs

**Don't:**
- Test only in production
- Skip error testing
- Assume everything works

---

## Real-World Example

Here's a complete example for a POS payment notification system:

```python
import asyncio
from homepot_client.push_notifications import get_push_provider
from homepot_client.push_notifications.base import (
    PushNotificationPayload,
    PushPriority
)

class POSNotificationSystem:
    def __init__(self):
        self.apns_config = {
            "team_id": "ABC123DEFG",
            "key_id": "XYZ987WXYZ",
            "auth_key_path": "/secure/AuthKey_XYZ987WXYZ.p8",
            "bundle_id": "com.homepot.pos",
            "environment": "production",
            "topic": "com.homepot.pos"
        }
        self.provider = None
    
    async def initialize(self):
        """Initialize APNs provider."""
        self.provider = await get_push_provider("apns", self.apns_config)
        health = await self.provider.health_check()
        
        if health['status'] != 'healthy':
            raise RuntimeError("APNs provider not healthy")
        
        print("APNs initialized successfully")
    
    async def notify_payment_pending(
        self,
        device_token: str,
        transaction_id: str,
        amount: float,
        terminal_id: str
    ):
        """Send payment approval notification."""
        
        payload = PushNotificationPayload(
            title="Payment Approval Required",
            body=f"Transaction #{transaction_id}: ${amount:.2f}",
            data={
                "transaction_id": transaction_id,
                "amount": str(amount),
                "terminal_id": terminal_id,
                "action": "approve_payment",
                "timestamp": datetime.utcnow().isoformat()
            },
            priority=PushPriority.HIGH,
            platform_data={
                "badge": 1,
                "sound": "payment_alert.caf",
                "category": "PAYMENT_APPROVAL"
            }
        )
        
        result = await self.provider.send_notification(
            device_token,
            payload
        )
        
        if result.success:
            print(f"Payment notification sent: {result.message_id}")
            return True
        elif result.error_code == "UNREGISTERED":
            # Device uninstalled app - remove from database
            await self.remove_device(device_token)
            print(f"🗑️ Removed unregistered device")
            return False
        else:
            print(f"Notification failed: {result.message}")
            return False
    
    async def notify_configuration_update(self, device_tokens: list):
        """Send silent background update to multiple devices."""
        
        payload = PushNotificationPayload(
            title="Configuration Update",
            body="",
            data={
                "update_type": "configuration",
                "version": "2.1.0"
            },
            priority=PushPriority.NORMAL,
            platform_data={
                "content_available": True,  # Silent notification
                "sound": None
            }
        )
        
        notifications = [
            (token, payload) for token in device_tokens
        ]
        
        results = await self.provider.send_bulk_notifications(notifications)
        
        success_count = sum(1 for r in results if r.success)
        print(f"Configuration update sent to {success_count}/{len(results)} devices")
        
        # Handle unregistered devices
        for result in results:
            if result.error_code == "UNREGISTERED":
                await self.remove_device(result.device_token)
    
    async def remove_device(self, device_token: str):
        """Remove device from database."""
        # Your database logic here
        print(f"Removing device: {device_token}")

# Usage
async def main():
    system = POSNotificationSystem()
    await system.initialize()
    
    # Send payment notification
    await system.notify_payment_pending(
        device_token="a1b2c3d4e5f6...64chars...",
        transaction_id="TXN-12345",
        amount=150.00,
        terminal_id="POS-001"
    )
    
    # Send config update to all devices
    all_devices = [
        "device_token_1",
        "device_token_2",
        "device_token_3"
    ]
    await system.notify_configuration_update(all_devices)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Summary

Congratulations! You now know how to:

Set up APNs with Apple Developer credentials  
Configure HOMEPOT Client for APNs  
Get device tokens from iOS/macOS apps  
Send different types of notifications  
Handle errors properly  
Send bulk notifications efficiently  
Optimize payload sizes  
Test your integration  

### Quick Reference

| Task | Code |
|------|------|
| **Initialize** | `provider = await get_push_provider("apns", config)` |
| **Send notification** | `result = await provider.send_notification(token, payload)` |
| **Bulk send** | `results = await provider.send_bulk_notifications(notifications)` |
| **Check health** | `health = await provider.health_check()` |
| **High priority** | `payload.priority = PushPriority.HIGH` |
| **Silent notification** | `platform_data={"content_available": True}` |
| **Badge update** | `platform_data={"badge": 5}` |

### Need Help?

- **APNs Documentation**: <https://developer.apple.com/documentation/usernotifications>
- **Device Token Issues**: Check app permissions and environment
- **Payload Errors**: Keep payload under 4KB
- **Authentication Errors**: Verify Team ID, Key ID, and .p8 file
