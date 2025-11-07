/**
 * HOMEPOT API Service
 *
 * Centralized API client for all backend communications.
 * Handles authentication, error handling, and request/response formatting.
 */

import axios from 'axios';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://192.168.0.253:8000';
const API_VERSION = 'v1';
const API_TIMEOUT = import.meta.env.VITE_API_TIMEOUT || 30000;

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/${API_VERSION}`,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token if available and check expiry
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    const tokenExpiry = localStorage.getItem('token_expiry');
    
    if (token && tokenExpiry) {
      const expiryTime = parseInt(tokenExpiry, 10);
      const now = Date.now();
      
      // Check if token is expired
      if (now >= expiryTime) {
        // Token expired, clear storage and reject request
        localStorage.removeItem('auth_token');
        localStorage.removeItem('token_expiry');
        localStorage.removeItem('user_data');
        
        // Redirect to login
        window.location.href = '/login';
        
        return Promise.reject(new Error('Session expired'));
      }
      
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;

      switch (status) {
        case 401:
          // Unauthorized - clear token and redirect to login
          localStorage.removeItem('auth_token');
          localStorage.removeItem('token_expiry');
          localStorage.removeItem('user_data');
          
          // Only redirect if not already on login page
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
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
  // ==================== Authentication ====================

  auth: {
    /**
     * User signup
     */
    signup: async (userData) => {
      const response = await apiClient.post('/auth/signup', userData);
      // Return the full response to preserve the structure
      return response.data;
    },

    /**
     * User login
     * Returns: { success: true, message: "Login successful", data: { access_token, username, role } }
     */
    login: async (credentials) => {
      const response = await apiClient.post('/auth/login', credentials);
      // Return the full response structure from your API
      return response.data;
    },

    /**
     * Logout
     */
    logout: () => {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('token_expiry');
      localStorage.removeItem('user_data');
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
      const response = await apiClient.get('/sites/sites');
      return response.data;
    },

    /**
     * Get site details
     */
    get: async (siteId) => {
      const response = await apiClient.get(`/sites/sites/${siteId}`);
      return response.data;
    },

    /**
     * Create new site
     */
    create: async (siteData) => {
      const response = await apiClient.post('/sites/sites', siteData);
      return response.data;
    },
  },

  // ==================== Devices ====================

  devices: {
    /**
     * Create device
     */
    create: async (siteId, deviceData) => {
      const response = await apiClient.post(`/sites/${siteId}/devices`, deviceData);
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
      const response = await apiClient.post(`/sites/${siteId}/jobs`, jobData);
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

    /**
     * Send push notification to agent
     */
    sendPush: async (deviceId, notificationData) => {
      const response = await apiClient.post(`/agents/${deviceId}/push`, notificationData);
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
   * Check if user is authenticated
   */
  isAuthenticated: () => {
    const token = localStorage.getItem('auth_token');
    const tokenExpiry = localStorage.getItem('token_expiry');
    
    if (!token || !tokenExpiry) {
      return false;
    }
    
    const expiryTime = parseInt(tokenExpiry, 10);
    const now = Date.now();
    
    return now < expiryTime;
  },

  /**
   * Get stored auth token
   */
  getAuthToken: () => {
    return localStorage.getItem('auth_token');
  },

  /**
   * Get time remaining until session expires (in milliseconds)
   */
  getSessionTimeRemaining: () => {
    const tokenExpiry = localStorage.getItem('token_expiry');
    if (!tokenExpiry) return 0;
    
    const expiryTime = parseInt(tokenExpiry, 10);
    const now = Date.now();
    
    return Math.max(0, expiryTime - now);
  },

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