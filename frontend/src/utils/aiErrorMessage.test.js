import { describe, it, expect } from 'vitest';

import { aiErrorMessage, isCancel } from './aiErrorMessage';
import { AI_QUERY_TIMEOUT_MINUTES } from './aiTimeouts';

/** Minimal axios-shaped error. */
const failed = (status, { data, headers } = {}) => ({
  response: { status, data, headers },
});

describe('aiErrorMessage', () => {
  it('explains a busy inference slot (503) and honours Retry-After', () => {
    const message = aiErrorMessage(failed(503, { headers: { 'retry-after': '5' } }));
    expect(message).toMatch(/busy answering another question/i);
    expect(message).toMatch(/5 seconds/);
  });

  it('still names the busy case when Retry-After is absent', () => {
    expect(aiErrorMessage(failed(503))).toMatch(/a few seconds/);
  });

  it('explains a client-side timeout (ECONNABORTED)', () => {
    const message = aiErrorMessage({ code: 'ECONNABORTED' });
    expect(message).toMatch(/timed out/i);
    expect(message).toMatch(/CPU/);
    // The message must name the same ceiling the client actually waits for.
    expect(message).toContain(`${AI_QUERY_TIMEOUT_MINUTES} minutes`);
  });

  it('explains a 504 from the reverse proxy as the same slow-model case', () => {
    expect(aiErrorMessage(failed(504))).toMatch(/timed out/i);
  });

  it('distinguishes an expired session (401)', () => {
    expect(aiErrorMessage(failed(401))).toMatch(/sign in again/i);
  });

  it('distinguishes a permission problem (403)', () => {
    expect(aiErrorMessage(failed(403))).toMatch(/permission/i);
  });

  it('surfaces the backend detail on a server error', () => {
    const message = aiErrorMessage(failed(500, { data: { detail: 'Context build failed' } }));
    expect(message).toMatch(/HTTP 500: Context build failed/);
  });

  it('ignores a non-string server detail', () => {
    const message = aiErrorMessage(failed(500, { data: { detail: { nested: true } } }));
    expect(message).toMatch(/HTTP 500/);
    expect(message).not.toMatch(/nested/);
  });

  it('blames the network when no response arrived', () => {
    expect(aiErrorMessage({ request: {} })).toMatch(/could not reach the server/i);
  });

  it('never returns an empty message', () => {
    expect(aiErrorMessage(undefined)).toBeTruthy();
    expect(aiErrorMessage({})).toBeTruthy();
  });

  it('does not report a deliberate Stop/Esc as a failure', () => {
    // axios raises ERR_CANCELED for an aborted request, which is the user's
    // own action -- not the timeout case, and not a server error.
    expect(aiErrorMessage({ code: 'ERR_CANCELED' })).toMatch(/cancelled/i);
    expect(aiErrorMessage({ name: 'CanceledError' })).toMatch(/cancelled/i);
    expect(aiErrorMessage({ code: 'ERR_CANCELED' })).not.toMatch(/timed out/i);
  });
});

describe('isCancel', () => {
  it('recognises the shapes axios uses for an aborted request', () => {
    expect(isCancel({ code: 'ERR_CANCELED' })).toBe(true);
    expect(isCancel({ name: 'CanceledError' })).toBe(true);
  });

  it('does not mistake a timeout or a server error for a cancel', () => {
    expect(isCancel({ code: 'ECONNABORTED' })).toBe(false);
    expect(isCancel({ response: { status: 503 } })).toBe(false);
    expect(isCancel(undefined)).toBe(false);
  });
});
