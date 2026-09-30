/**
 * Helpers for showing who is working on a device.
 *
 * Two technicians can hold the same device open at once and the command queue
 * used to be anonymous, so there was no way to see that a colleague had just
 * acted on a device you were looking at. These helpers are pure so they can be
 * tested without a browser.
 */

/** Commands predating the issued_by column have no actor. */
export function isOwnCommand(command, currentUserEmail) {
  if (!command) return true;
  if (!currentUserEmail) return false;
  if (!command.issued_by) return false;
  return command.issued_by === currentUserEmail;
}

/**
 * Commands issued by somebody else, newest first.
 *
 * A command with no actor is never reported as foreign: we cannot know who sent
 * it, and guessing would accuse a colleague of work they may not have done.
 */
export function foreignCommands(history, currentUserEmail) {
  if (!Array.isArray(history)) return [];
  if (!currentUserEmail) return [];
  return history.filter((command) => command.issued_by && command.issued_by !== currentUserEmail);
}

/** The most recent command that records an actor, or null if none does. */
export function lastAttributedCommand(history) {
  if (!Array.isArray(history)) return null;
  return history.find((command) => Boolean(command && command.issued_by)) || null;
}

/** A short label for who last acted on a device, or null when unknown. */
export function lastActorLabel(history) {
  const command = lastAttributedCommand(history);
  return command ? command.issued_by : null;
}

/**
 * Command ids that are new since a known set, ignoring the current user.
 *
 * Used while polling: when this returns something, another technician has acted
 * on the device since the page was last refreshed.
 */
export function newForeignCommands(history, knownCommandIds, currentUserEmail) {
  const known = new Set(Array.isArray(knownCommandIds) ? knownCommandIds : []);
  return foreignCommands(history, currentUserEmail).filter(
    (command) => !known.has(command.command_id)
  );
}
