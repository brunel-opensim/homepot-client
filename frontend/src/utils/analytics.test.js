import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import { trackActivity, trackSearch, getUserActivities, trackError } from './analytics';

vi.mock('axios');

describe('analytics.js', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('trackActivity sends correct payload', async () => {
    axios.post.mockResolvedValue({});

    await trackActivity('click', '/dashboard', { btn: 'save' }, 'save-btn');

    expect(axios.post).toHaveBeenCalled();
  });

  it('trackSearch is debounced and triggers trackActivity after delay', async () => {
    axios.post.mockResolvedValue({});

    trackSearch('pizza', '/search');

    // Should not be called immediately
    expect(axios.post).not.toHaveBeenCalled();

    // Advance time
    vi.advanceTimersByTime(500);

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/user-activity'),
      expect.objectContaining({
        activity_type: 'search',
        search_query: 'pizza',
      }),
      expect.any(Object)
    );
  });

  it('trackSearch debounces multiple rapid calls', async () => {
    axios.post.mockResolvedValue({});

    trackSearch('p', '/search');
    trackSearch('pi', '/search');
    trackSearch('piz', '/search');

    vi.advanceTimersByTime(200);
    expect(axios.post).not.toHaveBeenCalled();

    trackSearch('pizza', '/search');

    vi.advanceTimersByTime(500);

    expect(axios.post).toHaveBeenCalledTimes(1);
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/user-activity'),
      expect.objectContaining({
        search_query: 'pizza',
      }),
      expect.any(Object)
    );
  });

  it('getUserActivities returns data', async () => {
    axios.get.mockResolvedValue({
      data: { activities: [] },
    });

    const res = await getUserActivities();

    expect(res.activities).toBeDefined();
  });

  it('trackError does not throw on failure', async () => {
    axios.post.mockRejectedValue(new Error('fail'));

    await expect(trackError('Error', '/page')).resolves.not.toThrow();
  });
});
