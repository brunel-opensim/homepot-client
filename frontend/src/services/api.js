/**
 * HOMEPOT API Service
 *
 * Centralized API client for all backend communications.
 * Handles authentication, error handling, and request/response formatting.
 *
 * SECURITY: Authentication uses httpOnly cookies (set by the backend)
 * - Tokens are NOT stored in localStorage (XSS protection)
 * - Cookies are automatically sent with requests (withCredentials: true)
 * - Cookies are httpOnly (not accessible via JavaScript)
 */

import axios from 'axios';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const API_VERSION = 'v1';
const API_TIMEOUT = import.meta.env.VITE_API_TIMEOUT || 30000;

console.log('API Service Config:', {
  mode: import.meta.env.MODE,
  dev: import.meta.env.DEV,
  baseUrl: API_BASE_URL,
  finalUrl: `${API_BASE_URL}/api/${API_VERSION}`,
});

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/${API_VERSION}`,
  withCredentials: true, // Required for httpOnly cookies
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor - handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;

      switch (status) {
        case 401:
          // Unauthorized - handled by AuthContext interceptor
          // Don't redirect here to avoid conflicts
          break;
        case 403:
          console.error('Forbidden:', data.detail || 'Access denied');
          break;
        case 404:
          console.error('Not Found:', data.detail || 'Resource not found');
          break;
        case 500:
          console.error('Server Error:', data.detail || 'Internal server error');
          break;
        default:
          console.error('API Error:', data.detail || error.message);
      }
    } else if (error.request) {
      // Request made but no response received
      console.error('Network Error: No response from server');
    } else {
      // Error in request setup
      console.error('Request Error:', error.message);
    }

    return Promise.reject(error);
  }
);

/**
 * API Service Object
 */
const api = {
  // Expose raw axios instance for interceptor access
  raw: apiClient,

  // ==================== Authentication ====================

  auth: {
    /**
     * User signup
     */
    signup: async (userData) => {
      const response = await apiClient.post('/auth/signup', userData);
      return response.data;
    },

    /**
     * User login
     * Server sets httpOnly cookie (XSS protected)
     * Returns: { success: true, message: "Login successful", data: { username, is_admin } }
     */
    login: async (credentials) => {
      const response = await apiClient.post('/auth/login', credentials);
      return response.data;
    },

    /**
     * Logout - clears httpOnly cookie on server
     */
    logout: async () => {
      const response = await apiClient.post('/auth/logout');
      return response.data;
    },

    /**
     * Get current user info (from httpOnly cookie)
     */
    me: async () => {
      const response = await apiClient.get('/auth/me');
      return response.data;
    },
  },

  // ==================== Health & Status ====================

  health: {
    /**
     * Check API health
     */
    check: async () => {
      const response = await apiClient.get('/health');
      return response.data;
    },

    /**
     * Get site health
     */
    getSiteHealth: async (siteId) => {
      const response = await apiClient.get(`/sites/${siteId}/health`);
      return response.data;
    },

    /**
     * Get device health
     */
    getDeviceHealth: async (deviceId) => {
      const response = await apiClient.get(`/health/devices/${deviceId}/health`);
      return response.data;
    },

    /**
     * Trigger health check
     */
    triggerHealthCheck: async (deviceId) => {
      const response = await apiClient.post(`/health/devices/${deviceId}/health`);
      return response.data;
    },
  },

  // ==================== Sites ====================

  sites: {
    /**
     * List all sites
     */
    list: async () => {
      const response = await apiClient.get('/sites');
      return response.data;
    },

    /**
     * Get site details
     */
    get: async (siteId) => {
      const response = await apiClient.get(`/sites/${siteId}`);
      return response.data;
    },

    /**
     * Create new site
     */
    create: async (siteData) => {
      const response = await apiClient.post('/sites', siteData);
      return response.data;
    },

    /**
     * Update site
     */
    update: async (siteId, siteData) => {
      const response = await apiClient.put(`/sites${siteId}`, siteData);
      return response.data;
    },

    /**
     * Delete site
     */
    delete: async (siteId) => {
      const response = await apiClient.delete(`/sites/sites/${siteId}`);
      return response.data;
    },
  },

  // ==================== Devices ====================

  devices: {
    list: async () => {
      const response = await apiClient.get('/devices/device');
      return response.data;
    },
    /**
     * Create device
     */
    create: async (siteId, deviceData) => {
      const response = await apiClient.post(`/devices/sites/${siteId}/devices`, deviceData);
      return response.data;
    },

    getSiteId: async (siteId) => {
      const response = await apiClient.get(`/devices/sites/${siteId}/devices`);
      return response.data;
    },

    getDeviceById: async (deviceId) => {
      const response = await apiClient.get(`/devices/device/${deviceId}`);
      return response.data;
    },

    /**
     * Restart device
     */
    restart: async (deviceId) => {
      const response = await apiClient.post(`/devices/${deviceId}/restart`);
      return response.data;
    },
  },

  // ==================== Jobs ====================

  jobs: {
    /**
     * Create job
     */
    create: async (siteId, jobData) => {
      const response = await apiClient.post(`/jobs/sites/${siteId}/jobs`, jobData);
      return response.data;
    },

    /**
     * Get job status
     */
    getStatus: async (jobId) => {
      const response = await apiClient.get(`/jobs/${jobId}`);
      return response.data;
    },
  },

  // ==================== Agents ====================

  agents: {
    /**
     * List all agents
     */
    list: async () => {
      const response = await apiClient.get('/agents');
      return response.data;
    },

    /**
     * Get agent status
     */
    getStatus: async (deviceId) => {
      const response = await apiClient.get(`/agents/${deviceId}`);
      return response.data;
    },

    getListAgents: async () => {
      const response = await apiClient.get(`/agents/agents`);
      return response.data;
    },
    /**
     * Send push notification to agent
     */
    sendPush: async (deviceId, notificationData) => {
      const response = await apiClient.post(`/agents/agents/${deviceId}/push`, notificationData);
      return response.data;
    },
  },

  // ==================== Push Notifications ====================

  push: {
    /**
     * Get VAPID public key for Web Push
     */
    getVapidKey: async () => {
      const response = await apiClient.get('/push/vapid-public-key');
      return response.data;
    },

    /**
     * Subscribe to push notifications
     */
    subscribe: async (subscriptionData) => {
      const response = await apiClient.post('/push/subscribe', subscriptionData);
      return response.data;
    },

    /**
     * Send notification to device
     */
    send: async (notificationData) => {
      const response = await apiClient.post('/push/send', notificationData);
      return response.data;
    },

    /**
     * Send bulk notifications
     */
    sendBulk: async (bulkData) => {
      const response = await apiClient.post('/push/send-bulk', bulkData);
      return response.data;
    },

    /**
     * Publish MQTT topic
     */
    publishMqtt: async (topicData) => {
      const response = await apiClient.post('/push/mqtt/publish', topicData);
      return response.data;
    },

    /**
     * List all platforms
     */
    listPlatforms: async () => {
      const response = await apiClient.get('/push/platforms');
      return response.data;
    },

    /**
     * Get platform info
     */
    getPlatformInfo: async (platform) => {
      const response = await apiClient.get(`/push/platforms/${platform}/info`);
      return response.data;
    },

    /**
     * Send test notification
     */
    sendTest: async (platform, deviceToken) => {
      const response = await apiClient.post('/push/test', null, {
        params: { platform, device_token: deviceToken },
      });
      return response.data;
    },
  },

  // ==================== Client Management ====================

  client: {
    /**
     * Get client status
     */
    getStatus: async () => {
      const response = await apiClient.get('/client/status');
      return response.data;
    },

    /**
     * Connect client
     */
    connect: async () => {
      const response = await apiClient.post('/client/connect');
      return response.data;
    },

    /**
     * Disconnect client
     */
    disconnect: async () => {
      const response = await apiClient.post('/client/disconnect');
      return response.data;
    },

    /**
     * Get version
     */
    getVersion: async () => {
      const response = await apiClient.get('/client/version');
      return response.data;
    },
  },
};

/**
 * Helper functions for common operations
 */
export const apiHelpers = {
  /**
   * Format error message from API response
   */
  formatError: (error) => {
    if (error.response?.data?.detail) {
      return error.response.data.detail;
    }
    if (error.message) {
      return error.message;
    }
    return 'An unknown error occurred';
  },

  /**
   * Convert base64 URL-safe string to Uint8Array (for VAPID key)
   */
  urlBase64ToUint8Array: (base64String) => {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  },
};

export default api;
