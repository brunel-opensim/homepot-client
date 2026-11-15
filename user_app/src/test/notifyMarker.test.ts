import { describe, expect, it } from 'vitest'

import { NOTIFY_USER_MARKER, decodeNotifyMarker } from '../../electron/notifyMarker'

function encode(payload: unknown): string {
  return Buffer.from(JSON.stringify(payload), 'utf-8').toString('base64')
}

describe('decodeNotifyMarker', () => {
  it('decodes a valid title + message payload', () => {
    const payload = encode({ title: 'Notification from HOMEPOT', message: 'hello' })
    expect(decodeNotifyMarker(payload)).toEqual({
      title: 'Notification from HOMEPOT',
      message: 'hello',
    })
  })

  it('round-trips a message with newlines and unicode', () => {
    const message = 'line one\nline two — ünïcode'
    const payload = encode({ title: 'HOMEPOT', message })
    expect(decodeNotifyMarker(payload)?.message).toBe(message)
  })

  it('returns null for a missing payload', () => {
    expect(decodeNotifyMarker(undefined)).toBeNull()
    expect(decodeNotifyMarker('')).toBeNull()
  })

  it('returns null for malformed JSON', () => {
    expect(decodeNotifyMarker(Buffer.from('not json').toString('base64'))).toBeNull()
  })

  it('returns null when title or message is not a string', () => {
    expect(decodeNotifyMarker(encode({ title: 1, message: 'x' }))).toBeNull()
    expect(decodeNotifyMarker(encode({ message: 'x' }))).toBeNull()
    expect(decodeNotifyMarker(encode({ title: 'x', message: null }))).toBeNull()
  })

  it('exposes the marker the agent and supervisor share', () => {
    // Keep in sync with NOTIFY_USER_MARKER in
    // backend/src/homepot/agent/utils/command_poller.py.
    expect(NOTIFY_USER_MARKER).toBe('__HOMEPOT_NOTIFY_USER__')
  })
})
