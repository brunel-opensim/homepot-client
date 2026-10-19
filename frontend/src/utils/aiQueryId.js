/**
 * Id for one AI query, so Stop/Esc can be reported to the server.
 *
 * Aborting the HTTP request is not enough on its own: the API runs behind Apache
 * and behind a BaseHTTPMiddleware, both of which swallow the disconnect, so the
 * client tells the server explicitly by posting this id to
 * `/ai/query/cancel` (docs/ai-concurrency.md).
 *
 * `crypto.randomUUID` needs a secure context (https or localhost). The fallback
 * only has to be unique among the user's own in-flight queries: the cancel
 * endpoint also checks that the id belongs to the caller, so an unguessable id
 * is not what protects other users' queries.
 */

export function newQueryId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Math.random() can be 0, which base-36-encodes to "0" and slices away.
  const random = Math.random().toString(36).slice(2, 10) || 'x';
  return `q-${Date.now().toString(36)}-${random}`;
}

export default newQueryId;
