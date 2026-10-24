/**
 * Crash-loop supervisor for the on-device agent child process.
 *
 * The User App spawns the Python device agent (`homepot.agent.real_device_agent`)
 * as a child process. If that process exits without being asked to (a crash,
 * OOM, antivirus kill), the supervisor restarts it — but only a bounded number
 * of times within a rolling window, after which it stops and surfaces an error
 * instead of restarting forever. An intentional stop (unpair, re-enrol, quit)
 * never resurrects the agent.
 *
 * Kept free of Electron imports so the decision logic is unit-testable.
 */

export interface CrashLoopPolicy {
  /** Maximum automatic restarts allowed within `windowMs`. */
  maxRestarts: number
  /** Rolling window (ms) in which `maxRestarts` is counted. */
  windowMs: number
}

export const DEFAULT_CRASH_LOOP_POLICY: CrashLoopPolicy = {
  maxRestarts: 3,
  windowMs: 5 * 60 * 1000,
}

export type AgentExitDecision =
  | { kind: 'intentional' }
  | { kind: 'restart' }
  | { kind: 'crash-loop-limit' }

export class AgentSupervisor {
  private intentionalStop = false
  private restartTimestamps: number[] = []
  private readonly policy: CrashLoopPolicy
  private readonly now: () => number

  constructor(
    policy: CrashLoopPolicy = DEFAULT_CRASH_LOOP_POLICY,
    now: () => number = Date.now,
  ) {
    this.policy = policy
    this.now = now
  }

  /** Mark the in-flight stop as intentional so the next exit is not restarted. */
  markIntentionalStop(): void {
    this.intentionalStop = true
  }

  /** Clear the intentional-stop flag (called after a fresh spawn). */
  resetIntentionalStop(): void {
    this.intentionalStop = false
  }

  /** Forget any recent crash-restart history (called before a manual start). */
  resetCrashLoop(): void {
    this.restartTimestamps = []
  }

  /** Decide what to do after the current agent process exited. */
  onExit(): AgentExitDecision {
    if (this.intentionalStop) {
      this.intentionalStop = false
      return { kind: 'intentional' }
    }
    const now = this.now()
    this.restartTimestamps = this.restartTimestamps.filter(
      (t) => now - t < this.policy.windowMs,
    )
    if (this.restartTimestamps.length >= this.policy.maxRestarts) {
      return { kind: 'crash-loop-limit' }
    }
    this.restartTimestamps.push(now)
    return { kind: 'restart' }
  }
}
