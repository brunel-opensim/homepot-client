# Frontend Analytics Integration Guide

## Overview
This guide provides step-by-step instructions for integrating user activity tracking into the HOMEPOT frontend.

## What We're Building
Track user behavior to understand:
- Which pages users visit most
- What features they use
- Search patterns and queries
- Navigation flows
- Error experiences

## Prerequisites
- Backend analytics infrastructure (PR #53)  
- Backend endpoints available at `/api/v1/analytics/*`  
- Authentication system in place (cookies)

## Implementation Steps

### Step 1: Create Analytics Helper

Create `frontend/src/utils/analytics.js`:

```javascript
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Track user activity in the backend analytics system
 * @param {string} activityType - Type of activity (page_view, button_click, search, etc.)
 * @param {string} pageUrl - Current page URL or route
 * @param {Object} extraData - Additional context (optional)
 */
export const trackActivity = async (activityType, pageUrl, extraData = {}) => {
  try {
    await axios.post(
      `${API_BASE_URL}/api/v1/analytics/user-activity`,
      {
        activity_type: activityType,
        page_url: pageUrl,
        extra_data: extraData
      },
      {
        withCredentials: true, // Important: sends auth cookie
        timeout: 2000 // Don't block UI if analytics is slow
      }
    );
  } catch (error) {
    // Silently fail - don't break user experience if analytics fails
    console.debug('Analytics tracking failed:', error.message);
  }
};

/**
 * Track search queries
 * @param {string} query - Search query text
 * @param {string} pageUrl - Where the search happened
 * @param {number} resultsCount - Number of results (optional)
 */
export const trackSearch = async (query, pageUrl, resultsCount = null) => {
  const extraData = resultsCount !== null ? { results_count: resultsCount } : {};
  await trackActivity('search', pageUrl, { search_query: query, ...extraData });
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
        extra_data: { page_url: pageUrl }
      },
      {
        withCredentials: true,
        timeout: 2000
      }
    );
  } catch (error) {
    console.debug('Error tracking failed:', error.message);
  }
};
```

### Step 2: Track Page Views

Update your router to track page navigation.

**If using React Router**, modify your main routing component:

```javascript
// Example: frontend/src/App.jsx or similar
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { trackActivity } from './utils/analytics';

function App() {
  const location = useLocation();

  // Track page views on route changes
  useEffect(() => {
    trackActivity('page_view', location.pathname);
  }, [location.pathname]);

  return (
    // ... existing App component
  );
}
```

**Activity Types to Track:**
- `page_view` - User navigates to a page
- `button_click` - User clicks important buttons
- `form_submit` - User submits a form
- `search` - User performs a search
- `filter_applied` - User applies filters
- `export_data` - User exports data
- `modal_open` - User opens a modal/dialog

### Step 3: Track Key User Actions

Add tracking to important interactions across your pages:

#### Example: Device Management Page
```javascript
// frontend/src/pages/Devices.jsx (or similar)
import { trackActivity } from '../utils/analytics';

function DevicesPage() {
  const handleDeviceAction = async (deviceId, action) => {
    // Track the action
    await trackActivity('button_click', '/devices', {
      action: action,
      device_id: deviceId
    });
    
    // ... existing device action code
  };

  const handleFilterChange = async (filterType, filterValue) => {
    await trackActivity('filter_applied', '/devices', {
      filter_type: filterType,
      filter_value: filterValue
    });
    
    // ... existing filter code
  };

  return (
    // ... existing component
  );
}
```

#### Example: Job Management
```javascript
// frontend/src/pages/Jobs.jsx (or similar)
import { trackActivity } from '../utils/analytics';

function JobsPage() {
  const handleCreateJob = async (jobData) => {
    await trackActivity('form_submit', '/jobs', {
      action: 'create_job',
      job_type: jobData.action
    });
    
    // ... existing job creation code
  };

  return (
    // ... existing component
  );
}
```

### Step 4: Track Search Functionality

Add search tracking wherever have search:

```javascript
// Example: Search component
import { trackSearch } from '../utils/analytics';

function SearchBar() {
  const handleSearch = async (searchQuery) => {
    // Track the search
    await trackSearch(searchQuery, window.location.pathname);
    
    // ... existing search code
    const results = await performSearch(searchQuery);
    
    // Optionally track results count
    await trackSearch(searchQuery, window.location.pathname, results.length);
  };

  return (
    // ... existing search component
  );
}
```

### Step 5: Track Errors

Add error tracking to error handlers and API calls:

```javascript
// Example: API error handler
import { trackError } from '../utils/analytics';

// In your axios interceptor or error boundary
axios.interceptors.response.use(
  response => response,
  async error => {
    if (error.response) {
      // Track API errors
      await trackError(
        error.response.data.detail || 'API request failed',
        window.location.pathname,
        'api_error'
      );
    }
    return Promise.reject(error);
  }
);

// Or in individual components
const handleSubmit = async (formData) => {
  try {
    await submitData(formData);
  } catch (error) {
    await trackError(
      error.message,
      '/form-page',
      'form_submission_error'
    );
    // Show error to user
  }
};
```

### Step 6: Test Implementation

#### Manual Testing Checklist:
1. **Page Views**
   - Navigate between pages
   - Check browser DevTools Network tab for POST to `/api/v1/analytics/user-activity`
   - Verify requests return 200/201

2. **Button Clicks**
   - Click important buttons (Create Job, Update Device, etc.)
   - Verify analytics requests sent

3. **Search**
   - Perform searches
   - Verify search queries tracked

4. **Errors**
   - Trigger an error (invalid form, API failure)
   - Verify error logged

#### Verification Query in Backend Team:
```bash
# Backend team can verify data is arriving:
curl -X GET "http://localhost:8000/api/v1/metrics/user-activity?hours=1" \
  -H "Cookie: access_token=YOUR_TOKEN"
```

## Important Notes

### Do NOT Track:
- Passwords or sensitive data
- PII (personally identifiable information) unless required
- Full form contents (just track "form submitted")
- Every mouse movement or keystroke

### DO Track:
- Page navigation
- Feature usage (which buttons/actions)
- Search queries (helps understand user intent)
- Filters and sort preferences
- Errors users encounter

### Performance Considerations:
- Analytics calls are **async** and **non-blocking**
- 2-second timeout prevents UI slowdown
- Failed analytics don't break user experience
- No need to wait for analytics response

## Integration Points Summary

**Minimum Required (Core AI Data):**
1. Page view tracking in router
2. Device action tracking (view, update, delete)
3. Job action tracking (create, view, status check)
4. Site navigation tracking
5. Error tracking in API calls

**Nice to Have (Enhanced Insights):**
1. Search tracking
2. Filter/sort tracking
3. Modal/dialog open tracking
4. Export action tracking
5. Settings changes tracking

## Support

- **Documentation**: `docs/backend-analytics.md` (backend API details)
- **API Endpoints**: Already deployed and tested
- **Questions**: Contact Maziar (Brunel University)
