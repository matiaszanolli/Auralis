/**
 * Timing policy shared across the frontend (#5800).
 *
 * Each of these was a literal re-typed at several call sites, which is how the
 * WebSocket reconnect backoff ended up 1.5x in the declared default and 2x in
 * the only caller. Request timeouts live with the request code
 * (`DEFAULT_TIMEOUT_MS` in `utils/apiRequest.ts`) and reconnect policy with
 * `WebSocketManager` (`utils/errorHandling.ts`).
 */

/** How long React Query treats fetched data as fresh. Fingerprints and the app default use it. */
export const QUERY_STALE_TIME_MS = 5 * 60 * 1000;

/**
 * How long React Query keeps an inactive query's cache before garbage
 * collecting it (the fingerprint hooks each re-typed 30 minutes, #6221).
 * Named to match #6064's proposal so that sweep and this constant converge
 * on one name.
 */
export const QUERY_GC_TIME_MS = 30 * 60 * 1000;

/** Keystrokes settle this long before a search request fires. */
export const SEARCH_DEBOUNCE_MS = 300;
