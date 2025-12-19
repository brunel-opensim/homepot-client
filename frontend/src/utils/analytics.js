import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

/**
 * @typedef {Object} AnalyticsPayload
 * @property {string} activity_type - Type of activity (click, page_view, etc.)
 * @property {string} page_url - URL where activity occurred
 * @property {string|null} [element_id] - ID of the interacted element
 * @property {string|null} [search_query] - Search query text
 * @property {Object} [extra_data] - Additional context data
 * @property {number|null} [duration_ms] - Duration of action
 */

/**
 * Track generic user activity
 * @param {string} activityType - "page_view", "click", "search", etc.
 * @param {string} pageUrl - Current page URL
 * @param {Object} [extraData={}] - Extra info objects
 * @param {string|null} [elementId=null] - ID of clicked element
 * @param {string|null} [searchQuery=null] - Search text
 * @param {number|null} [durationMs=null] - Duration in milliseconds
 */
export const trackActivity = async (
  activityType,
  pageUrl,
  extraData = {},
  elementId = null,
  searchQuery = null,
  durationMs = null
) => {
  try {
    const payload = {
      activity_type: activityType,
      page_url: pageUrl,
      element_id: elementId,
      search_query: searchQuery,
      extra_data: extraData,
      duration_ms: durationMs,
    };

    // Remove null fields so backend only gets relevant info
    Object.keys(payload).forEach((key) => payload[key] == null && delete payload[key]);

    await axios.post(`${API_BASE_URL}/api/v1/analytics/user-activity`, payload, {
      withCredentials: true,
      timeout: 2000,
    });
  } catch (error) {
    console.debug('Analytics tracking failed:', error.message);
  }
};

/**
 * Simple debounce implementation
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} - Debounced function
 */
const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

// Internal debounced function for search
const debouncedSearch = debounce(async (query, pageUrl, durationMs) => {
  await trackActivity('search', pageUrl, {}, null, query, durationMs);
}, 500);

/**
 * Track search queries (Debounced by 500ms)
 * @param {string} query - Search text
 * @param {string} pageUrl - Current page URL
 * @param {number|null} [durationMs=null] - Duration
 */
export const trackSearch = (query, pageUrl, durationMs = null) => {
  debouncedSearch(query, pageUrl, durationMs);
};

/**
 * Fetch user activities
 * @param {number} [limit=20] - Number of activities to fetch
 * @returns {Promise<Object>} - API response data
 */
export const getUserActivities = async (limit = 20) => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/v1/analytics/user-activities`, {
      params: { limit },
      withCredentials: true,
    });
    return res.data;
  } catch (error) {
    console.error('Failed to fetch user activities:', error);
    throw error;
  }
};

/**
 * Track errors encountered by users
 * @param {string} errorMessage - Error message shown to user
 * @param {string} pageUrl - Where error occurred
 * @param {string} errorType - Type of error (api_error, validation_error, etc.)
 */
export const trackError = async (errorMessage, pageUrl, errorType = 'client_error') => {
  try {
    await axios.post(
      `${API_BASE_URL}/api/v1/analytics/error`,
      {
        category: errorType,
        severity: 'error',
        message: errorMessage,
        extra_data: { page_url: pageUrl },
      },
      {
        withCredentials: true,
        timeout: 2000,
      }
    );
  } catch (error) {
    console.debug('Error tracking failed:', error.message);
  }
};
