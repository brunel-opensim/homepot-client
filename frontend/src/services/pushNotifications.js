/**
 * HOMEPOT Push Notification Manager
 *
 * Manages Web Push notifications:
 * - Service Worker registration
 * - Push subscription
 * - Permission handling
 * - Notification display
 */

import api, { apiHelpers } from './api';

class PushNotificationManager {
  constructor() {
    this.swRegistration = null;
    this.subscription = null;
    this.vapidPublicKey = null;
    this.isSupported = this.checkSupport();
  }

  /**
   * Check if push notifications are supported
   */
  checkSupport() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  /**
   * Initialize push notification manager
   */
  async initialize() {
    if (!this.isSupported) {
      console.warn('Push notifications are not supported in this browser');
      return false;
    }

    try {
      // Register service worker
      await this.registerServiceWorker();

      // Get VAPID public key from server
      await this.getVapidKey();

      // Check existing subscription
      await this.checkSubscription();

      return true;
    } catch (error) {
      console.error('Failed to initialize push notifications:', error);
      return false;
    }
  }

  /**
   * Register service worker
   */
  async registerServiceWorker() {
    try {
      this.swRegistration = await navigator.serviceWorker.register('/sw.js', {
        scope: '/',
      });

      console.log('Service Worker registered:', this.swRegistration);

      // Wait for service worker to be ready
      await navigator.serviceWorker.ready;

      return this.swRegistration;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      throw error;
    }
  }

  /**
   * Get VAPID public key from server
   */
  async getVapidKey() {
    try {
      const response = await api.push.getVapidKey();
      this.vapidPublicKey = response.publicKey;
      console.log('VAPID public key retrieved');
      return this.vapidPublicKey;
    } catch (error) {
      console.error('Failed to get VAPID key:', error);
      throw error;
    }
  }

  /**
   * Check existing push subscription
   */
  async checkSubscription() {
    try {
      if (!this.swRegistration) {
        throw new Error('Service Worker not registered');
      }

      this.subscription = await this.swRegistration.pushManager.getSubscription();

      if (this.subscription) {
        console.log('Existing push subscription found');
        return this.subscription;
      }

      return null;
    } catch (error) {
      console.error('Failed to check subscription:', error);
      return null;
    }
  }

  /**
   * Request notification permission
   */
  async requestPermission() {
    if (!this.isSupported) {
      throw new Error('Push notifications not supported');
    }

    const permission = await Notification.requestPermission();
    console.log('Notification permission:', permission);

    return permission === 'granted';
  }

  /**
   * Subscribe to push notifications
   */
  async subscribe() {
    try {
      // Check permission
      if (Notification.permission !== 'granted') {
        const granted = await this.requestPermission();
        if (!granted) {
          throw new Error('Notification permission denied');
        }
      }

      // Ensure service worker is registered
      if (!this.swRegistration) {
        await this.registerServiceWorker();
      }

      // Ensure we have VAPID key
      if (!this.vapidPublicKey) {
        await this.getVapidKey();
      }

      // Convert VAPID key to Uint8Array
      const applicationServerKey = apiHelpers.urlBase64ToUint8Array(this.vapidPublicKey);

      // Subscribe to push
      this.subscription = await this.swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey,
      });

      console.log('Push subscription created:', this.subscription);

      // Send subscription to server
      await this.sendSubscriptionToServer(this.subscription);

      return this.subscription;
    } catch (error) {
      console.error('Push subscription failed:', error);
      throw error;
    }
  }

  /**
   * Unsubscribe from push notifications
   */
  async unsubscribe() {
    try {
      if (!this.subscription) {
        console.log('No active subscription to unsubscribe');
        return true;
      }

      const success = await this.subscription.unsubscribe();

      if (success) {
        console.log('Push subscription removed');
        this.subscription = null;

        // TODO: Notify server about unsubscription
      }

      return success;
    } catch (error) {
      console.error('Failed to unsubscribe:', error);
      throw error;
    }
  }

  /**
   * Send subscription details to server
   */
  async sendSubscriptionToServer(subscription) {
    try {
      const subscriptionJson = subscription.toJSON();

      const response = await api.push.subscribe({
        platform: 'web_push',
        device_token: JSON.stringify(subscriptionJson),
        device_info: {
          userAgent: navigator.userAgent,
          platform: navigator.platform,
          language: navigator.language,
        },
        user_id: localStorage.getItem('user_id'),
        device_id: this.getDeviceId(),
      });

      console.log('Subscription sent to server:', response);

      // Store subscription locally
      localStorage.setItem('push_subscription', JSON.stringify(subscriptionJson));

      return response;
    } catch (error) {
      console.error('Failed to send subscription to server:', error);
      throw error;
    }
  }

  /**
   * Get or create device ID
   */
  getDeviceId() {
    let deviceId = localStorage.getItem('device_id');

    if (!deviceId) {
      deviceId = `web_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('device_id', deviceId);
    }

    return deviceId;
  }

  /**
   * Get current permission status
   */
  getPermissionStatus() {
    if (!this.isSupported) {
      return 'unsupported';
    }

    return Notification.permission;
  }

  /**
   * Check if subscribed
   */
  isSubscribed() {
    return !!this.subscription;
  }

  /**
   * Show local notification (for testing)
   */
  async showNotification(title, options = {}) {
    if (!this.isSupported) {
      throw new Error('Notifications not supported');
    }

    if (Notification.permission !== 'granted') {
      throw new Error('Notification permission not granted');
    }

    if (!this.swRegistration) {
      throw new Error('Service Worker not registered');
    }

    await this.swRegistration.showNotification(title, {
      body: options.body || '',
      icon: options.icon || '/icon-192x192.png',
      badge: options.badge || '/badge-72x72.png',
      image: options.image,
      data: options.data || {},
      tag: options.tag || 'homepot-notification',
      requireInteraction: options.requireInteraction || false,
      vibrate: [200, 100, 200],
      timestamp: Date.now(),
      ...options,
    });
  }

  /**
   * Send test notification via server
   */
  async sendTestNotification() {
    try {
      if (!this.subscription) {
        throw new Error('Not subscribed to push notifications');
      }

      const subscriptionJson = this.subscription.toJSON();

      const response = await api.push.sendTest('web_push', JSON.stringify(subscriptionJson));

      console.log('Test notification sent:', response);
      return response;
    } catch (error) {
      console.error('Failed to send test notification:', error);
      throw error;
    }
  }

  /**
   * Get subscription info
   */
  getSubscriptionInfo() {
    if (!this.subscription) {
      return null;
    }

    return {
      endpoint: this.subscription.endpoint,
      expirationTime: this.subscription.expirationTime,
      keys: this.subscription.toJSON().keys,
    };
  }
}

// Create singleton instance
const pushManager = new PushNotificationManager();

export default pushManager;
