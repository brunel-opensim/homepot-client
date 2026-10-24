import { describe, it, expect } from 'vitest'
import {
  AgentSupervisor,
  DEFAULT_CRASH_LOOP_POLICY,
  AGENT_SHUTDOWN_GRACE_MS,
} from '../../electron/agentSupervisor'

/** A controllable clock so the rolling-window logic is deterministic. */
function makeClock(startMs = 1_000_000): { now: () => number; advance: (ms: number) => void } {
  let t = startMs
  return {
    now: () => t,
    advance: (ms: number) => {
      t += ms
    },
  }
}

describe('AgentSupervisor', () => {
  it('does not restart after an intentional stop', () => {
    const s = new AgentSupervisor()
    s.markIntentionalStop()
    expect(s.onExit()).toEqual({ kind: 'intentional' })
  })

  it('shutdown grace exceeds the agent shutdown timeout (30s)', () => {
    // The agent's graceful-shutdown budget is `shutdown_timeout_seconds` = 30s;
    // Electron must not SIGKILL before that or the final OFFLINE heartbeat is
    // cut short.
    expect(AGENT_SHUTDOWN_GRACE_MS).toBeGreaterThanOrEqual(30_000)
  })

  it('clears the intentional flag after an intentional exit', () => {
    const s = new AgentSupervisor()
    s.markIntentionalStop()
    s.onExit()
    expect(s.onExit()).toEqual({ kind: 'restart' })
  })

  it('restarts on an unexpected exit', () => {
    const s = new AgentSupervisor()
    expect(s.onExit()).toEqual({ kind: 'restart' })
  })

  it('honours the crash-loop limit', () => {
    const s = new AgentSupervisor()
    for (let i = 0; i < DEFAULT_CRASH_LOOP_POLICY.maxRestarts; i += 1) {
      expect(s.onExit()).toEqual({ kind: 'restart' })
    }
    expect(s.onExit()).toEqual({ kind: 'crash-loop-limit' })
  })

  it('expires restart history outside the rolling window', () => {
    const clock = makeClock()
    const s = new AgentSupervisor(DEFAULT_CRASH_LOOP_POLICY, clock.now)
    for (let i = 0; i < DEFAULT_CRASH_LOOP_POLICY.maxRestarts; i += 1) {
      s.onExit()
    }
    expect(s.onExit()).toEqual({ kind: 'crash-loop-limit' })

    clock.advance(DEFAULT_CRASH_LOOP_POLICY.windowMs + 1)
    expect(s.onExit()).toEqual({ kind: 'restart' })
  })

  it('resetCrashLoop grants a fresh restart budget', () => {
    const s = new AgentSupervisor()
    for (let i = 0; i < DEFAULT_CRASH_LOOP_POLICY.maxRestarts; i += 1) {
      s.onExit()
    }
    expect(s.onExit()).toEqual({ kind: 'crash-loop-limit' })
    s.resetCrashLoop()
    expect(s.onExit()).toEqual({ kind: 'restart' })
  })

  it('resetIntentionalStop lets a fresh child crash be treated as unexpected', () => {
    const s = new AgentSupervisor()
    s.markIntentionalStop()
    s.resetIntentionalStop()
    expect(s.onExit()).toEqual({ kind: 'restart' })
  })
})
