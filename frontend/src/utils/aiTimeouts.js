/**
 * The AI query timeout, in one place.
 *
 * The assistant runs synchronous CPU inference on the server: a normal answer
 * takes 40-120s and a cold model load can take several minutes, so the generic
 * 30s API timeout is far too short. This value is deliberately matched to the
 * reverse proxy (Apache `ProxyTimeout`), so whichever ceiling is reached first
 * produces the same "still thinking" message (see aiErrorMessage.js and
 * docs/ai-concurrency.md).
 */

export const AI_QUERY_TIMEOUT_MS = Number(import.meta.env?.VITE_AI_QUERY_TIMEOUT) || 600000;

export const AI_QUERY_TIMEOUT_MINUTES = Math.max(1, Math.round(AI_QUERY_TIMEOUT_MS / 60000));
