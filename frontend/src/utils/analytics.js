import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const trackActivity = async (
  activityType, // "page_view", "click", "search", etc.
  pageUrl, // current page
  extraData = {}, // extra info
  elementId = null, // optional: id of clicked element
  searchQuery = null, // optional: search text
  durationMs = null // optional: duration in milliseconds
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

// Helper for search events
export const trackSearch = async (query, pageUrl, durationMs = null) => {
  await trackActivity('search', pageUrl, {}, null, query, durationMs);
};

//  Track user activity get method of by users
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
