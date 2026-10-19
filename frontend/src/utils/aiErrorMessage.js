/**
 * Turn a failed AI query into something the user can act on.
 *
 * The assistant runs a local, CPU-bound model behind a single inference slot,
 * so "it didn't answer" has several distinct causes that a generic
 * "Failed to get a response. Please try again." hides:
 *
 *   - 503: another query holds the only slot (docs/ai-concurrency.md).
 *   - Client/axios timeout (ECONNABORTED) or a 504 from the reverse proxy:
 *     the model was still generating. The first question after a break pays a
 *     cold model load, which is by far the slowest case.
 *   - 401/403: the session or role is the problem, not the AI.
 *   - 5xx: an internal error, where the backend's own detail is the useful bit.
 *   - No response at all: the network, not the AI.
 *
 * Pure, so it can be tested without a browser (see aiErrorMessage.test.js).
 */

import { AI_QUERY_TIMEOUT_MINUTES } from './aiTimeouts';

/** A server error body carries `detail`; only use it when it is readable text. */
function serverDetail(error) {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' && detail.trim() ? detail.trim() : null;
}

export function aiErrorMessage(error) {
  const status = error?.response?.status;
  const detail = serverDetail(error);

  // The one-inference-slot queue: the most common "sometimes" failure.
  if (status === 503) {
    const retryAfter = error?.response?.headers?.['retry-after'];
    const wait = retryAfter ? `${retryAfter} seconds` : 'a few seconds';
    return (
      'The AI assistant is busy answering another question — it handles one at ' +
      `a time. Please try again in ${wait}.`
    );
  }

  // Still generating: axios gave up, or the reverse proxy cut the connection.
  if (error?.code === 'ECONNABORTED' || status === 504) {
    return (
      `The AI assistant was still thinking after ${AI_QUERY_TIMEOUT_MINUTES} minutes and the ` +
      'request timed out. The model runs on CPU, and the first question after a ' +
      'break is the slowest — please ask again, the next attempt is usually faster.'
    );
  }

  if (status === 401) {
    return 'Your session has expired. Please sign in again, then retry your question.';
  }

  if (status === 403) {
    return 'Your account does not have permission to use the AI assistant.';
  }

  if (status >= 500) {
    const suffix = detail ? `: ${detail}` : '';
    return (
      `The AI assistant hit a server error (HTTP ${status}${suffix}). ` +
      'Please try again; if it keeps happening, check the service logs.'
    );
  }

  // A request that never got a response is a connectivity problem, not the AI.
  if (error?.request) {
    return 'Could not reach the server. Check your connection and try again.';
  }

  return detail || 'The AI assistant could not be reached. Please try again.';
}

export default aiErrorMessage;
