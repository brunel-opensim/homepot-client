import { describe, it, expect, afterEach, vi } from 'vitest';

import { newQueryId } from './aiQueryId';

describe('newQueryId (docs/ai-concurrency.md)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses crypto.randomUUID when the context is secure', () => {
    const randomUUID = vi.fn(() => '11111111-2222-3333-4444-555555555555');
    vi.stubGlobal('crypto', { randomUUID });

    expect(newQueryId()).toBe('11111111-2222-3333-4444-555555555555');
    expect(randomUUID).toHaveBeenCalledTimes(1);
  });

  it('falls back to a timestamp/random id when randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', {});

    const id = newQueryId();

    expect(id).toMatch(/^q-[a-z0-9]+-[a-z0-9]+$/);
    // Must fit the backend's query_id (max 64 chars).
    expect(id.length).toBeLessThanOrEqual(64);
  });

  it('produces a different id per query', () => {
    const ids = new Set([newQueryId(), newQueryId(), newQueryId()]);
    expect(ids.size).toBe(3);
  });
});
