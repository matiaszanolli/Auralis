/**
 * Types and the error class for the HTTP transport.
 *
 * Split out of apiRequest.ts (#5841); apiRequest re-exports all three, so
 * existing imports are unchanged.
 */

/**
 * Default request timeout (ms). `hooks/api/useRestAPI.ts` uses the same 30s so
 * the two remaining layers behave identically (#4442).
 */
export const DEFAULT_TIMEOUT_MS = 30000;

export class APIRequestError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'APIRequestError';
  }
}

export interface RequestOptions<T = unknown> extends Omit<RequestInit, 'body'> {
  body?: Record<string, any>;
  /**
   * AbortSignal for cancelling in-flight requests (e.g. on component unmount).
   *
   * @example
   * const controller = new AbortController();
   * get('/api/library/tracks', { signal: controller.signal });
   * // On cleanup:
   * controller.abort();
   */
  signal?: AbortSignal;

  /**
   * Per-request timeout in milliseconds. Defaults to {@link DEFAULT_TIMEOUT_MS}.
   * The internal timeout composes with any caller-supplied `signal` — whichever
   * aborts first wins. Pass `0` to disable the internal timeout.
   */
  timeoutMs?: number;

  /**
   * Optional runtime shape guard for the parsed response body (#4607).
   *
   * `Response.json()` is `Promise<any>`, so TypeScript silently narrows it to
   * the caller's `T` with no runtime check — every interface in `types/api.ts`
   * is a compile-time-only contract. Backend field drift therefore surfaced as
   * a downstream `undefined`/NaN far from its cause (#3593, #3976, #4440,
   * #4441), never at the boundary.
   *
   * A type predicate tied to the call's `T` (#5637): the guard's asserted type
   * must match (or narrow to) the requested `T`, so pairing a guard for one
   * shape with `get<AnotherShape>()` is a compile error, and a passing guard
   * lets {@link apiRequest} return the body as the guarded type instead of an
   * unchecked `as T`. Guards live in `@/api/responseGuards`.
   *
   * When supplied and the body fails the guard, {@link apiRequest} throws an
   * {@link APIRequestError} naming the endpoint. Endpoints without a guard
   * behave exactly as before (the compile-time-only contract), so adoption is
   * incremental.
   *
   * Not invoked for 204 No Content, which resolves to `undefined` by contract.
   *
   * @example
   * get('/api/library/tracks', { validate: isTracksListShape });
   */
  validate?: (value: unknown) => value is T;
}
