import { describe, expect, it } from 'vitest';
import {
  canCancelCommand,
  getStatusMeta,
  isTerminalStatus,
} from '../../src/utils/commandLifecycle';

describe('command lifecycle exit strategy', () => {
  it('isTerminalStatus treats cancelled as terminal', () => {
    expect(isTerminalStatus('completed')).toBe(true);
    expect(isTerminalStatus('failed')).toBe(true);
    expect(isTerminalStatus('expired')).toBe(true);
    expect(isTerminalStatus('cancelled')).toBe(true);
    expect(isTerminalStatus('pending')).toBe(false);
    expect(isTerminalStatus('sent')).toBe(false);
  });

  it('only in-flight commands can be cancelled', () => {
    expect(canCancelCommand({ status: 'pending' })).toBe(true);
    expect(canCancelCommand({ status: 'sent' })).toBe(true);
    expect(canCancelCommand({ status: 'completed' })).toBe(false);
    expect(canCancelCommand({ status: 'failed' })).toBe(false);
    expect(canCancelCommand({ status: 'expired' })).toBe(false);
    expect(canCancelCommand({ status: 'cancelled' })).toBe(false);
    expect(canCancelCommand(null)).toBe(false);
    expect(canCancelCommand({})).toBe(false);
  });

  it('cancelled gets a status badge label', () => {
    const meta = getStatusMeta('cancelled');
    expect(meta.label).toBe('Cancelled');
  });
});