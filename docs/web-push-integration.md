# Web Push Notifications Integration Guide

## Overview

Web Push notifications enable the HOMEPOT Client to send push notifications to web browsers across all major platforms. This completes the unified push notification system supporting:

- **FCM (Firebase Cloud Messaging)** - Android/Linux devices
- **WNS (Windows Notification Service)** - Windows devices  
- **APNs (Apple Push Notification service)** - iOS/macOS/watchOS/tvOS devices
- **Web Push** - All modern web browsers (NEW)

## Supported Browsers

Web Push notifications work on:

- **Chrome/Chromium** (Desktop & Mobile)
- **Microsoft Edge** (Desktop & Mobile)
- **Firefox** (Desktop & Mobile)
- **Opera** (Desktop & Mobile)
- **Safari** (macOS 16.1+, iOS 16.4+)
- **Samsung Internet** (Android)

## Architecture

Web Push uses the [Web Push Protocol (RFC 8030)](https://datatracker.ietf.org/doc/html/rfc8030) with VAPID (Voluntary Application Server Identification) for authentication.

### Components

1. **Backend Provider** (`web_push.py`):
   - Implements `PushNotificationProvider` base class
   - Handles VAPID authentication
   - Encrypts notification payloads
   - Sends via browser push services

2. **VAPID Keys**:
   - Public/private key pair for server identification
   - Used to sign push requests
   - Allows browsers to verify notification source

3. **Push Subscriptions**:
   - Created by browser Push API
   - Contains endpoint URL and encryption keys
   - Stored as JSON in device tokens

## Setup Guide

### Step 1: Generate VAPID Keys

You need to generate a VAPID key pair for your server:

#### Option A: Using pywebpush CLI

```bash
# Install pywebpush
pip install pywebpush

# Generate VAPID keys
python -m pywebpush gen-vapid-keys
```

Output:
```
Private Key (PEM format):
-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIJO...your-private-key...
-----END EC PRIVATE KEY-----

Public Key (base64 URL-safe):
BNcRdreALRFXTkOOUHK5EZfTBTmHlTGgGzvPajdoJNB5E...your-public-key...
```

#### Option B: Using OpenSSL

```bash
# Generate VAPID private key
openssl ecparam -name prime256v1 -genkey -noout -out vapid_private.pem

# Extract public key
openssl ec -in vapid_private.pem -pubout -outform DER | \
  tail -c 65 | base64 | tr '/+' '_-' | tr -d '='
```

#### Option C: Using Node.js (web-push)

```bash
npm install -g web-push
web-push generate-vapid-keys
```

### Step 2: Configure Backend

Add VAPID credentials to your backend configuration:

**`.env` file:**

```bash
# Web Push Configuration
WEB_PUSH_VAPID_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIJO...your-private-key-here...
-----END EC PRIVATE KEY-----"

WEB_PUSH_VAPID_PUBLIC_KEY="BNcRdreALRFXTkOOUHK5EZfTBTmHlTGgGzvPajdoJNB5E...your-public-key-here..."

# Contact information (required)
WEB_PUSH_VAPID_SUBJECT="mailto:admin@homepot.com"
# OR use HTTPS URL:
# WEB_PUSH_VAPID_SUBJECT="https://homepot.com"

# Optional settings
WEB_PUSH_TTL_SECONDS=300
WEB_PUSH_TIMEOUT_SECONDS=30
```

**Python code:**

```python
from homepot_client.push_notifications import get_push_provider

# Configure Web Push provider
config = {
    "vapid_private_key": os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY"),
    "vapid_public_key": os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY"),
    "vapid_subject": os.getenv("WEB_PUSH_VAPID_SUBJECT"),
    "ttl_seconds": int(os.getenv("WEB_PUSH_TTL_SECONDS", 300)),
    "timeout_seconds": int(os.getenv("WEB_PUSH_TIMEOUT_SECONDS", 30)),
}

# Get Web Push provider
web_push_provider = await get_push_provider("web_push", config)
```

### Step 3: Frontend Integration

#### Install Service Worker

Create `public/sw.js` (Service Worker):

```javascript
// Service Worker for push notifications
self.addEventListener('push', function(event) {
  console.log('Push received:', event);
  
  const data = event.data ? event.data.json() : {};
  const notification = data.notification || {};
  
  const title = notification.title || 'New Notification';
  const options = {
    body: notification.body || '',
    icon: notification.icon || '/icon-192.png',
    badge: notification.badge || '/badge-72.png',
    image: notification.image,
    tag: notification.tag,
    requireInteraction: notification.requireInteraction,
    silent: notification.silent,
    vibrate: notification.vibrate,
    data: notification.data,
    actions: notification.actions || [],
  };
  
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', function(event) {
  console.log('Notification clicked:', event);
  
  event.notification.close();
  
  // Handle notification click
  const urlToOpen = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.openWindow(urlToOpen)
  );
});
```

#### Register Service Worker and Subscribe

```javascript
// main.js or app.js
async function initializePushNotifications() {
  // Check if push notifications are supported
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    console.log('Push notifications not supported');
    return;
  }
  
  try {
    // Register service worker
    const registration = await navigator.serviceWorker.register('/sw.js');
    console.log('Service Worker registered:', registration);
    
    // Request notification permission
    const permission = await Notification.requestPermission();
    
    if (permission !== 'granted') {
      console.log('Notification permission denied');
      return;
    }
    
    // Get VAPID public key from backend
    const response = await fetch('http://localhost:8000/push/vapid-public-key');
    const { publicKey } = await response.json();
    
    // Subscribe to push notifications
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
    
    console.log('Push subscription:', subscription);
    
    // Send subscription to backend
    await fetch('http://localhost:8000/push/subscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subscription: subscription.toJSON(),
        device_info: {
          browser: navigator.userAgent,
          platform: navigator.platform,
        },
      }),
    });
    
    console.log('Successfully subscribed to push notifications');
    
  } catch (error) {
    console.error('Failed to initialize push notifications:', error);
  }
}

// Helper function to convert base64 to Uint8Array
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/\-/g, '+')
    .replace(/_/g, '/');
  
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  
  return outputArray;
}

// Initialize on page load
initializePushNotifications();
```

### Step 4: Backend API Endpoints

Add endpoints to handle subscriptions and provide VAPID public key:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json

router = APIRouter(prefix="/push", tags=["Push Notifications"])

class PushSubscription(BaseModel):
    subscription: dict
    device_info: dict = {}

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get VAPID public key for client-side subscription."""
    try:
        provider = await get_push_provider("web_push")
        public_key = provider.get_vapid_public_key()
        
        return {
            "publicKey": public_key,
            "platform": "web_push"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get VAPID public key: {str(e)}"
        )

@router.post("/subscribe")
async def subscribe_to_push(subscription_data: PushSubscription):
    """Store push subscription for a user/device."""
    try:
        # Store subscription in database
        device_token = json.dumps(subscription_data.subscription)
        
        # Validate subscription format
        provider = await get_push_provider("web_push")
        is_valid = provider.validate_device_token(device_token)
        
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail="Invalid subscription format"
            )
        
        # TODO: Store in database with user/device association
        # await db.save_push_subscription(
        #     user_id=current_user.id,
        #     platform="web_push",
        #     device_token=device_token,
        #     device_info=subscription_data.device_info
        # )
        
        return {
            "status": "success",
            "message": "Push subscription registered",
            "platform": "web_push"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register subscription: {str(e)}"
        )

@router.post("/send")
async def send_push_notification(
    device_token: str,
    title: str,
    body: str,
    data: dict = {},
    icon: str = None,
):
    """Send a test push notification."""
    try:
        provider = await get_push_provider("web_push")
        
        payload = PushNotificationPayload(
            title=title,
            body=body,
            data=data,
            priority=PushPriority.HIGH,
            platform_data={
                "icon": icon or "/icon-192.png",
                "badge": "/badge-72.png",
            }
        )
        
        result = await provider.send_notification(device_token, payload)
        
        return {
            "status": "success" if result.success else "failed",
            "message": result.message,
            "platform": result.platform
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send push notification: {str(e)}"
        )
```

## Usage Examples

### Send Single Notification

```python
from homepot_client.push_notifications import get_push_provider, PushNotificationPayload

# Get provider
provider = await get_push_provider("web_push")

# Device token is the subscription object as JSON
device_token = json.dumps({
    "endpoint": "https://fcm.googleapis.com/fcm/send/...",
    "keys": {
        "p256dh": "BNcR...base64url...",
        "auth": "tBHI...base64url..."
    }
})

# Create payload
payload = PushNotificationPayload(
    title="Payment Update",
    body="New payment gateway configuration available",
    data={
        "url": "/config/payment",
        "version": "2.1.0"
    },
    priority=PushPriority.HIGH,
    platform_data={
        "icon": "/icons/payment.png",
        "badge": "/icons/badge.png",
        "requireInteraction": True,
        "actions": [
            {"action": "view", "title": "View Details"},
            {"action": "dismiss", "title": "Dismiss"}
        ]
    }
)

# Send notification
result = await provider.send_notification(device_token, payload)

if result.success:
    print(f"✓ Notification sent: {result.message}")
else:
    print(f"✗ Failed: {result.message} ({result.error_code})")
```

### Send Bulk Notifications

```python
# Prepare notifications for multiple browsers
notifications = [
    (subscription1_json, payload1),
    (subscription2_json, payload2),
    (subscription3_json, payload3),
]

# Send all notifications
results = await provider.send_bulk_notifications(notifications)

# Check results
success_count = sum(1 for r in results if r.success)
print(f"Sent {success_count}/{len(results)} notifications successfully")
```

## Testing

### Test with Simulation Mode

```python
# Use simulation provider for testing without real credentials
sim_provider = await get_push_provider("simulation")

payload = PushNotificationPayload(
    title="Test Notification",
    body="This is a test",
)

result = await sim_provider.send_notification("test-token", payload)
print(f"Simulation result: {result.message}")
```

### Test with Browser Console

```javascript
// In browser console
Notification.requestPermission().then(permission => {
  console.log('Permission:', permission);
});

// Check current subscription
navigator.serviceWorker.ready.then(registration => {
  registration.pushManager.getSubscription().then(subscription => {
    console.log('Current subscription:', subscription?.toJSON());
  });
});
```

## Troubleshooting

### Common Issues

**1. "PushManager not available"**
- Solution: HTTPS is required (or localhost for development)
- Ensure site is served over HTTPS in production

**2. "Notification permission denied"**
- Solution: User must grant permission
- Cannot programmatically override browser permission

**3. "Invalid VAPID keys"**
- Solution: Ensure keys are properly formatted
- Private key: PEM format
- Public key: Base64 URL-safe, 65 bytes when decoded

**4. "Subscription expired (410 Gone)"**
- Solution: Remove expired subscription from database
- Re-subscribe user with new subscription

**5. "pywebpush not installed"**
- Solution: `pip install pywebpush cryptography`

### Debug Logging

Enable debug logging to see detailed information:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("homepot_client.push_notifications.web_push")
logger.setLevel(logging.DEBUG)
```

## Security Considerations

1. **VAPID Keys**: Keep private key secret, never expose in client code
2. **HTTPS Only**: Web Push requires HTTPS (except localhost)
3. **Subscription Privacy**: Treat subscriptions as sensitive data
4. **Payload Encryption**: Automatic with Web Push Protocol
5. **Origin Validation**: Browsers verify VAPID subject matches origin

## Browser Compatibility

| Browser | Desktop | Mobile | Notes |
|---------|---------|--------|-------|
| Chrome | v42+ | v42+ | Full support |
| Edge | v17+ | v79+ | Full support |
| Firefox | v44+ | v48+ | Full support |
| Safari | v16.1+ | v16.4+ | Limited features |
| Opera | v39+ | v37+ | Full support |

## Best Practices

1. **Request Permission Wisely**: Ask at appropriate moments, not immediately
2. **Provide Value**: Send meaningful, relevant notifications
3. **Handle Unsubscribe**: Allow users to easily opt-out
4. **Manage Subscriptions**: Clean up expired/invalid subscriptions
5. **Fallback Strategy**: Handle browsers without push support gracefully
6. **Test Thoroughly**: Test across different browsers and devices

## References

- [Web Push Protocol (RFC 8030)](https://datatracker.ietf.org/doc/html/rfc8030)
- [VAPID Specification (RFC 8292)](https://datatracker.ietf.org/doc/html/rfc8292)
- [Push API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [Notification API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API)
- [pywebpush Documentation](https://github.com/web-push-libs/pywebpush)
