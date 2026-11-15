/**
 * Marker emitted by the Python device agent on stdout when an operator sends a
 * `notify_user` command. The Electron supervisor renders it as a native OS
 * toast rather than shelling out to a dialog that the local Windows account
 * would be stamped on.
 *
 * Keep in sync with NOTIFY_USER_MARKER in
 * backend/src/homepot/agent/utils/command_poller.py.
 */
export const NOTIFY_USER_MARKER = '__HOMEPOT_NOTIFY_USER__'

export interface NotifyPayload {
  title: string
  message: string
}

/**
 * Decode a `notify_user` marker payload (base64-encoded JSON) into its title
 * and message. Returns `null` for anything malformed so a stray or corrupted
 * line can never take down the supervisor's stdout loop.
 *
 * Kept free of Electron imports so it is unit-testable under Vitest.
 */
export function decodeNotifyMarker(payload: string | undefined): NotifyPayload | null {
  if (!payload) return null
  try {
    const parsed = JSON.parse(Buffer.from(payload, 'base64').toString('utf-8')) as {
      title?: unknown
      message?: unknown
    }
    if (typeof parsed.title !== 'string' || typeof parsed.message !== 'string') {
      return null
    }
    return { title: parsed.title, message: parsed.message }
  } catch {
    return null
  }
}
