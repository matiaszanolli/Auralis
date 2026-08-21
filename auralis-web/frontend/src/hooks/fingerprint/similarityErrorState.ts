/**
 * Classify a failed similarity request into the state the backend meant (#4626).
 *
 * `routers/similarity.py` + `routers/similarity_common.py` deliberately encode
 * the actionable part of a failure in `HTTPException.detail`, and three of the
 * reachable outcomes are semantically distinct even though two of them share a
 * status code:
 *
 *   404 + "…does not have a fingerprint. Queued for background processing."
 *        The track is fine. The router has *already enqueued* it, so a retry in
 *        a few seconds succeeds. This is the most common first-run experience.
 *   404, anything else
 *        The track genuinely does not exist. Retrying never helps.
 *   503  The similarity system has not finished initialising. Transient.
 *
 * Rendering all three as one red "search failed" is the defect this module
 * exists to close.
 */

/** Which of the backend's distinct failure states a response represents. */
export type SimilarityErrorKind = 'queued' | 'initialising' | 'not-found' | 'failed';

export interface SimilarityErrorState {
  kind: SimilarityErrorKind;
  /** Headline for the UI. */
  title: string;
  /** Secondary line explaining what the user should do. */
  hint: string;
  /** Whether simply trying again shortly is expected to succeed. */
  retryable: boolean;
  /** True for states that are progress, not failure — render them calmly. */
  transient: boolean;
}

/**
 * Marker that separates the two 404s.
 *
 * This is a prose match, and it is deliberate: keeping the queued case a 404
 * means no existing consumer's `!response.ok` handling changes, whereas the
 * `202` the issue floats as an alternative is `ok` and would send every current
 * caller down the parse-the-body path. The single word is matched rather than
 * the full sentence so a reword that preserves the meaning still classifies.
 *
 * Paired with `routers/similarity_common.py::require_fingerprinted_tracks`,
 * which is the only place that emits it. If that message stops saying "queued",
 * `similarityErrorState.test.ts` is what should fail.
 */
const QUEUED_MARKER = 'queued';

/**
 * Turn `(error message, HTTP status)` from `useSimilarTracks` into a renderable
 * state.
 *
 * @param message - The error message, which is the backend's `detail` whenever
 *   it sent one (see `utils/httpError.ts`).
 * @param status - HTTP status, or null for a network-level failure.
 */
export function classifySimilarityError(
  message: string,
  status: number | null
): SimilarityErrorState {
  if (status === 503) {
    return {
      kind: 'initialising',
      title: 'Getting the similarity engine ready',
      hint: 'This finishes shortly after startup — try again in a moment.',
      retryable: true,
      transient: true,
    };
  }

  if (status === 404) {
    if (message.toLowerCase().includes(QUEUED_MARKER)) {
      return {
        kind: 'queued',
        title: 'Analysing this track',
        hint: 'It has been queued for fingerprinting. Check back in a few seconds.',
        retryable: true,
        transient: true,
      };
    }

    return {
      kind: 'not-found',
      title: 'That track is no longer in your library',
      hint: message,
      retryable: false,
      transient: false,
    };
  }

  return {
    kind: 'failed',
    // `message` is the backend's detail when there was one. It falls back to
    // `HTTP {status}: {statusText}` — never to a bare `statusText`, which is
    // empty over HTTP/2 and used to render as "Similarity search failed: 404 ".
    title: headline(message),
    hint: 'Try again or select a different track.',
    retryable: true,
    transient: false,
  };
}

/** Keep the generic branch's headline readable when `message` is empty. */
function headline(message: string): string {
  return message.trim() || 'Similarity search failed';
}
