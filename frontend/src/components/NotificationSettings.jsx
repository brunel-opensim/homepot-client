/**
 * Notification Settings Component
 *
 * Allows users to manage push notification preferences
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Bell, BellOff, CheckCircle2, XCircle, AlertCircle, Send } from 'lucide-react';
import pushManager from '../services/pushNotifications';
import api from '../services/api';

export default function NotificationSettings() {
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState('default');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [subscriptionInfo, setSubscriptionInfo] = useState(null);
  const [platforms, setPlatforms] = useState([]);

  const loadPlatforms = useCallback(async () => {
    try {
      const response = await api.push.listPlatforms();
      setPlatforms(response.platforms || []);
    } catch (error) {
      console.error('Failed to load platforms:', error);
    }
  }, []);

  const initializeSettings = useCallback(async () => {
    // Check support
    setIsSupported(pushManager.isSupported);

    if (!pushManager.isSupported) {
      setMessage({
        type: 'error',
        text: 'Push notifications are not supported in your browser',
      });
      return;
    }

    // Initialize push manager
    await pushManager.initialize();

    // Update state
    setPermission(pushManager.getPermissionStatus());
    setIsSubscribed(pushManager.isSubscribed());
    setSubscriptionInfo(pushManager.getSubscriptionInfo());

    // Load available platforms
    loadPlatforms();
  }, [loadPlatforms]);

  const handleSubscribe = async () => {
    setLoading(true);
    setMessage(null);

    try {
      await pushManager.subscribe();

      setPermission(pushManager.getPermissionStatus());
      setIsSubscribed(true);
      setSubscriptionInfo(pushManager.getSubscriptionInfo());

      setMessage({
        type: 'success',
        text: 'Successfully subscribed to push notifications!',
      });
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to subscribe: ${error.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleUnsubscribe = async () => {
    setLoading(true);
    setMessage(null);

    try {
      await pushManager.unsubscribe();

      setIsSubscribed(false);
      setSubscriptionInfo(null);

      setMessage({
        type: 'success',
        text: 'Successfully unsubscribed from push notifications',
      });
    } catch (error) {
      setMessage({
        type: 'error',
        text: `Failed to unsubscribe: ${error.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async () => {
    setLoading(true);
    setMessage(null);

    try {
      // Send test via server
      await pushManager.sendTestNotification();

      setMessage({
        type: 'success',
        text: 'Test notification sent! Check your notifications.',
      });
    } catch (error) {
      // Fallback to local notification
      try {
        await pushManager.showNotification('HOMEPOT Test Notification', {
          body: 'This is a local test notification',
          icon: '/icon-192x192.png',
          tag: 'test-notification',
        });

        setMessage({
          type: 'success',
          text: 'Local test notification displayed!',
        });
      } catch {
        setMessage({
          type: 'error',
          text: `Failed to send test notification: ${error.message}`,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // Initialize settings on component mount
  useEffect(() => {
    initializeSettings();
  }, [initializeSettings]);

  const getPermissionBadge = () => {
    switch (permission) {
      case 'granted':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircle2 className="w-4 h-4 mr-1" />
            Granted
          </span>
        );
      case 'denied':
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
            <XCircle className="w-4 h-4 mr-1" />
            Denied
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            <AlertCircle className="w-4 h-4 mr-1" />
            Not Set
          </span>
        );
    }
  };

  if (!isSupported) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <BellOff className="w-6 h-6 text-gray-400" />
            <h2 className="text-xl font-semibold">Push Notifications</h2>
          </div>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-800">
              Push notifications are not supported in your browser. Please try using a modern
              browser like Chrome, Firefox, or Edge.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Bell className="w-6 h-6 text-blue-600" />
            <h2 className="text-xl font-semibold">Push Notifications</h2>
          </div>
          {getPermissionBadge()}
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mb-4 p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 border border-green-200'
                : message.type === 'error'
                  ? 'bg-red-50 border border-red-200'
                  : 'bg-blue-50 border border-blue-200'
            }`}
          >
            <p
              className={`text-sm ${
                message.type === 'success'
                  ? 'text-green-800'
                  : message.type === 'error'
                    ? 'text-red-800'
                    : 'text-blue-800'
              }`}
            >
              {message.text}
            </p>
          </div>
        )}

        {/* Subscription Status */}
        <div className="mb-6">
          <h3 className="font-medium mb-3">Subscription Status</h3>
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-600">Status:</span>
              <span
                className={`text-sm font-medium ${isSubscribed ? 'text-green-600' : 'text-gray-400'}`}
              >
                {isSubscribed ? 'Subscribed' : 'Not Subscribed'}
              </span>
            </div>

            {subscriptionInfo && (
              <>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-gray-600">Endpoint:</span>
                  <span className="text-xs text-gray-500 truncate max-w-xs">
                    {subscriptionInfo.endpoint.substring(0, 40)}...
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Expiration:</span>
                  <span className="text-xs text-gray-500">
                    {subscriptionInfo.expirationTime
                      ? new Date(subscriptionInfo.expirationTime).toLocaleDateString()
                      : 'Never'}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3">
          {!isSubscribed ? (
            <Button
              onClick={handleSubscribe}
              disabled={loading || permission === 'denied'}
              className="w-full"
            >
              {loading ? 'Subscribing...' : 'Enable Push Notifications'}
            </Button>
          ) : (
            <>
              <Button
                onClick={handleTestNotification}
                disabled={loading}
                variant="outline"
                className="w-full"
              >
                <Send className="w-4 h-4 mr-2" />
                {loading ? 'Sending...' : 'Send Test Notification'}
              </Button>

              <Button
                onClick={handleUnsubscribe}
                disabled={loading}
                variant="destructive"
                className="w-full"
              >
                {loading ? 'Unsubscribing...' : 'Disable Push Notifications'}
              </Button>
            </>
          )}
        </div>

        {/* Platform Status */}
        {platforms.length > 0 && (
          <div className="mt-6 pt-6 border-t">
            <h3 className="font-medium mb-3">Available Platforms</h3>
            <div className="space-y-2">
              {platforms.map((platform) => (
                <div
                  key={platform.platform}
                  className="flex items-center justify-between bg-gray-50 rounded p-3"
                >
                  <span className="text-sm font-medium capitalize">
                    {platform.platform.replace('_', ' ')}
                  </span>
                  <span
                    className={`text-xs px-2 py-1 rounded ${
                      platform.available ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {platform.available ? 'Available' : 'Unavailable'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Help Text */}
        {permission === 'denied' && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-sm text-red-800">
              <strong>Permission Denied:</strong> You have blocked notifications for this site. To
              enable them, please update your browser settings.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
