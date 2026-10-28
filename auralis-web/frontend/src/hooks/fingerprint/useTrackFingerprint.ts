/**
 * useTrackFingerprint Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Fetches fingerprint for a specific track.
 * Used by AlbumCharacterPane to show currently playing track's sonic character.
 *
 * Features:
 * - Lazy loading (only fetches when trackId is provided)
 * - Caching via React Query
 * - Error handling with graceful fallback
 * - Auto-polling when fingerprint not ready
 */

import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { APIRequestError, getOrNullOn404 } from '@/utils/apiRequest';
import { QUERY_GC_TIME_MS, QUERY_STALE_TIME_MS } from '@/config/timing';

/**
 * Failures that say "the backend is briefly unavailable", not "this request is
 * wrong": transport failure/timeout (0), 408, 429 and 502-504. A track that is
 * still queued for its fingerprint keeps being polled through these (#6064). A
 * plain 500 or any other 4xx stops polling and surfaces the error once (#4847).
 */
const TRANSIENT_OUTAGE_STATUSES: ReadonlySet<number> = new Set([0, 408, 429, 502, 503, 504]);

/** ~3 minutes of polling at the default 5 s interval before giving up (#5893). */
const DEFAULT_MAX_PENDING_POLLS = 36;

interface TrackFingerprintResponse {
  track_id: number;
  track_title: string;
  artist: string;
  album: string;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch track fingerprint from backend.
 *
 * A 404 is the one expected non-error outcome (fingerprint queued but not
 * ready yet), so it resolves to `null` via `getOrNullOn404` (#6221).
 * Everything else — a non-2xx status or a network-level failure — rejects
 * instead of being swallowed to `null` (#4847): a 404 and "the endpoint is
 * broken" used to be indistinguishable, both driving refetchInterval's
 * indefinite 5s poll and leaving `query.error` permanently empty.
 */
const fetchTrackFingerprint = (
  trackId: number,
  signal?: AbortSignal
): Promise<TrackFingerprintResponse | null> =>
  // #5019: shared transport, which bounds the request at DEFAULT_TIMEOUT_MS.
  // The bare fetch() this replaces had no signal and no timeout, so a stalled
  // backend left the query loading forever with `refetchInterval` unable to
  // reach a terminal state.
  getOrNullOn404<TrackFingerprintResponse>(`/api/tracks/${trackId}/fingerprint`, { signal });

/**
 * Hook to fetch track fingerprint with caching
 *
 * @param trackId - Track ID (null/undefined to skip fetching)
 * @param options - Query options
 * @returns Fingerprint data and metadata or null if unavailable
 *
 * @example
 * ```tsx
 * const { fingerprint, trackTitle, isLoading } = useTrackFingerprint(currentTrackId);
 *
 * <AlbumCharacterPane
 *   fingerprint={fingerprint}
 *   albumTitle={trackTitle}
 *   isLoading={isLoading}
 * />
 * ```
 */
export function useTrackFingerprint(
  trackId: number | null | undefined,
  options?: {
    enabled?: boolean;
    /** Retry interval in ms when fingerprint not ready (default: 5000) */
    retryInterval?: number;
    /**
     * Stop polling a still-missing fingerprint after this many answers (default: 36,
     * ~3 minutes at the default interval). Every poll re-enqueues the track, so a
     * file that can never be fingerprinted (unreadable, DSP missing, timeout) was
     * retried every 5 s for as long as the pane stayed open (#5893).
     */
    maxPendingPolls?: number;
  }
) {
  const enabled = (options?.enabled ?? true) && trackId != null && trackId > 0;
  const retryInterval = options?.retryInterval ?? 5000;
  const maxPendingPolls = options?.maxPendingPolls ?? DEFAULT_MAX_PENDING_POLLS;

  // Answers received for this track (a new track starts again). Kept here rather
  // than read off the query because the observer result does not expose a count.
  const answersRef = useRef({ trackId, answers: 0 });
  if (answersRef.current.trackId !== trackId) answersRef.current = { trackId, answers: 0 };
  // State, not just the ref: giving up changes nothing in the query result, so
  // without it the hook would never re-render to stop reporting "pending".
  const [gaveUpOn, setGaveUpOn] = useState<number | null | undefined>(null);

  const query = useQuery({
    queryKey: ['track-fingerprint', trackId],
    // { signal } forwarded so unmount / key change aborts the in-flight request (#5650).
    queryFn: async ({ signal }) => {
      if (!trackId) return null;
      const response = await fetchTrackFingerprint(trackId, signal);
      answersRef.current.answers += 1;
      if (response === null && answersRef.current.answers >= maxPendingPolls) setGaveUpOn(trackId);
      return response;
    },
    staleTime: QUERY_STALE_TIME_MS, // fingerprints don't change
    gcTime: QUERY_GC_TIME_MS,   // 30 minutes cache retention
    enabled,
    // No retry override: the app-wide shouldRetryQuery decides. A 404 is not an
    // error here (getOrNullOn404 resolves null), so `retry: false` protected
    // nothing and only denied the retry a transient failure deserves (#6064).
    // Re-fetch periodically if fingerprint not ready (queued for generation)
    refetchInterval: (query) => {
      // #4847: a failed fetch leaves `data` at its last value — `null` for a
      // track that was still queued — so the error check must come first, or
      // polling never stops and the error is masked as "pending" forever.
      // Only a transient outage on a still-pending track keeps polling (#6064):
      // one dropped request used to end the polling for the whole session.
      if (query.state.status === 'error') {
        const error = query.state.error;
        const transient = error instanceof APIRequestError && TRANSIENT_OUTAGE_STATUSES.has(error.statusCode);
        // `data` is undefined (never fetched) or null (queued): both are still pending.
        return transient && !query.state.data ? retryInterval : false;
      }
      // If we got null (not ready), poll every 5 seconds
      if (query.state.data === null) {
        return answersRef.current.answers >= maxPendingPolls ? false : retryInterval;
      }
      return false; // Stop polling once we have data
    },
  });

  const data = query.data;

  return {
    fingerprint: data?.fingerprint ?? null,
    trackTitle: data?.track_title ?? null,
    artist: data?.artist ?? null,
    album: data?.album ?? null,
    isLoading: query.isLoading,
    // Fingerprint queued but not ready — distinct from a genuine error
    // (#4847), which used to look identical to this state.
    isPending: query.data === null && !query.isError && gaveUpOn !== trackId,
    error: query.error,
    refetch: query.refetch,
  };
}