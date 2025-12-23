/* eslint-env serviceworker */
/**
 * HOMEPOT Service Worker
 * 
 * Handles Web Push notifications in the background.
 * Displays notifications when the app is not in focus.
 */

// Service Worker version - increment to force update
const SW_VERSION = 'v1.0.0';
const CACHE_NAME = `homepot-cache-${SW_VERSION}`;

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing Service Worker', SW_VERSION);
  
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching app shell');
      return cache.addAll([
        '/',
        '/index.html',
        '/manifest.json',
      ]).catch((err) => {
        console.error('[SW] Cache failed:', err);
      });
    })
  );
  
  // Force the waiting service worker to become the active service worker
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating Service Worker', SW_VERSION);
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  // Claim all clients immediately
  return self.clients.claim();
});

// IndexedDB helper to store device_id
const DB_NAME = 'homepot-db';
const STORE_NAME = 'settings';

async function getDeviceId() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME);
      }
    };

    request.onsuccess = (event) => {
      const db = event.target.result;
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const getRequest = store.get('device_id');

      getRequest.onsuccess = () => {
        if (getRequest.result) {
          resolve(getRequest.result);
        } else {
          // Generate new ID if not found
          const newId = self.crypto.randomUUID();
          const writeTransaction = db.transaction(STORE_NAME, 'readwrite');
          const writeStore = writeTransaction.objectStore(STORE_NAME);
          writeStore.put(newId, 'device_id');
          resolve(newId);
        }
      };
      
      getRequest.onerror = () => reject(getRequest.error);
    };

    request.onerror = () => reject(request.error);
  });
}

async function acknowledgePush(messageId) {
  if (!messageId) return;
  
  try {
    const deviceId = await getDeviceId();
    await fetch('/api/v1/push/ack', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message_id: messageId,
        device_id: deviceId,
        status: 'delivered',
        received_at: new Date().toISOString(),
        platform: 'web_push'
      })
    });
    console.log('[SW] Acknowledged push:', messageId);
  } catch (err) {
    console.error('[SW] Failed to acknowledge push:', err);
  }
}

// Push event - handle incoming push notifications
self.addEventListener('push', (event) => {
  console.log('[SW] Push notification received:', event);
  
  let notificationData = {
    title: 'HOMEPOT Notification',
    body: 'You have a new notification',
    icon: '/icon-192x192.png',
    badge: '/badge-72x72.png',
    data: {},
  };
  
  // Parse notification data
  if (event.data) {
    try {
      const payload = event.data.json();
      notificationData = {
        title: payload.title || notificationData.title,
        body: payload.body || payload.message || notificationData.body,
        icon: payload.icon || notificationData.icon,
        badge: payload.badge || notificationData.badge,
        image: payload.image,
        data: payload.data || payload,
        tag: payload.tag || 'homepot-notification',
        requireInteraction: payload.requireInteraction || false,
        actions: payload.actions || [],
      };

      // Acknowledge receipt if message_id is present
      if (payload.message_id) {
        event.waitUntil(acknowledgePush(payload.message_id));
      }
    } catch (error) {
      console.error('[SW] Error parsing push data:', error);
      notificationData.body = event.data.text();
    }
  }
  
  // Show notification
  event.waitUntil(
    self.registration.showNotification(notificationData.title, {
      body: notificationData.body,
      icon: notificationData.icon,
      badge: notificationData.badge,
      image: notificationData.image,
      data: notificationData.data,
      tag: notificationData.tag,
      requireInteraction: notificationData.requireInteraction,
      actions: notificationData.actions,
      vibrate: [200, 100, 200],
      timestamp: Date.now(),
    })
  );
});

// Notification click event - handle user interaction
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event.notification);
  
  event.notification.close();
  
  const notificationData = event.notification.data || {};
  const urlToOpen = notificationData.url || '/dashboard';
  
  // Handle action button clicks
  if (event.action) {
    console.log('[SW] Action clicked:', event.action);
    
    switch (event.action) {
      case 'view':
        // Open the notification URL
        break;
      case 'dismiss':
        // Just close the notification
        return;
      default:
        // Custom action handling
        break;
    }
  }
  
  // Open or focus the app
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Check if there's already a window open
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if (client.url.includes(urlToOpen) && 'focus' in client) {
          return client.focus();
        }
      }
      
      // No matching client found, open a new window
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});

// Notification close event - track dismissals
self.addEventListener('notificationclose', (event) => {
  console.log('[SW] Notification dismissed:', event.notification);
  
  // Optional: Send analytics or feedback to server
  const notificationData = event.notification.data || {};
  
  if (notificationData.trackDismissal) {
    // You can track notification dismissals here
    console.log('[SW] Tracking notification dismissal');
  }
});

// Sync event - for background sync (future enhancement)
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync triggered:', event.tag);
  
  if (event.tag === 'sync-notifications') {
    event.waitUntil(
      // Sync logic here
      Promise.resolve()
    );
  }
});

// Message event - handle messages from main app
self.addEventListener('message', (event) => {
  console.log('[SW] Message received:', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: SW_VERSION });
  }
});

// Fetch event - cache-first strategy for static assets
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip API calls - always fetch from network
  if (event.request.url.includes('/api/')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      
      return fetch(event.request).then((response) => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        
        // Clone the response
        const responseToCache = response.clone();
        
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });
        
        return response;
      }).catch((error) => {
        console.error('[SW] Fetch failed:', error);
        
        // Return a custom offline page if available
        return caches.match('/offline.html').then((offlineResponse) => {
          return offlineResponse || new Response('Offline', { status: 503 });
        });
      });
    })
  );
});

console.log('[SW] Service Worker loaded', SW_VERSION);
