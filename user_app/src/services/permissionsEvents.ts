// Lightweight pub/sub so the Permissions page refreshes immediately after a
// permission decision is made elsewhere (e.g. the consent prompt), instead of
// waiting for its 15s polling interval.

type Listener = () => void

const listeners = new Set<Listener>()

export function onPermissionsChanged(fn: Listener): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

export function emitPermissionsChanged(): void {
  listeners.forEach((fn) => fn())
}

// The owner-facing permission tier groups. "Monitor device" maps to the
// non-root read-only capabilities (diagnostics, monitoring); "Manage device"
// is the elevated grant (root_access) that enables command/script execution,
// filesystem scans, config/firmware updates, and reboot/shutdown.
export const MANAGE_KEY = 'root_access'
export const MONITOR_KEYS = [
  'command_execution',
  'filesystem_access',
  'process_monitoring',
  'network_monitoring',
]