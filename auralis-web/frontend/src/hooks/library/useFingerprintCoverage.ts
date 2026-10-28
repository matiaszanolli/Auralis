/**
 * Library-wide fingerprint coverage — how much of the library has been analysed.
 *
 * Distinct from `hooks/enhancement/useFingerprintStatus`, which reports the
 * *per-track* `fingerprint_progress` WebSocket messages during enhanced playback
 * ("analysing this track"). This is the library aggregate: how many of N tracks
 * have a fingerprint at all, and roughly how long the rest will take (#4865).
 *
 * Polled rather than pushed: there is no WebSocket message for library-wide
 * coverage, and the numbers move slowly (roughly one track per 30 s of queue
 * work), so a poll while work is outstanding is proportionate. Polling stops
 * once nothing is pending, so an idle settings dialog issues one request.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { get, post } from '@/utils/apiRequest';

/** Matches `FingerprintingStatusResponse` in `routers/fingerprint_status.py`. */
export interface FingerprintCoverage {
  totalTracks: number;
  fingerprintedTracks: number;
  pendingTracks: number;
  /** 0–100. */
  progressPercent: number;
  /** Display-ready line built by the backend. */
  status: string;
  /** Rough ETA at 30 s/track; 0 when nothing is pending. */
  estimatedRemainingSeconds: number;
}

interface RawCoverage {
  total_tracks: number;
  fingerprinted_tracks: number;
  pending_tracks: number;
  progress_percent: number;
  status: string;
  estimated_remaining_seconds: number;
}

export interface UseFingerprintCoverageReturn {
  coverage: FingerprintCoverage | null;
  loading: boolean;
  error: string | null;
  /** Non-error outcome of the last enqueue-all (e.g. tracks the full queue dropped, #5920). */
  notice: string | null;
  /** True while an enqueue-all request is in flight. */
  enqueueing: boolean;
  /** Queue every track still missing a fingerprint, then refresh. */
  analyseRemaining: () => Promise<void>;
  refresh: () => Promise<void>;
}

/** How often to re-read coverage while tracks are still pending. */
export const POLL_INTERVAL_MS = 10_000;

function toCoverage(raw: RawCoverage): FingerprintCoverage {
  return {
    totalTracks: raw.total_tracks,
    fingerprintedTracks: raw.fingerprinted_tracks,
    pendingTracks: raw.pending_tracks,
    progressPercent: raw.progress_percent,
    status: raw.status,
    estimatedRemainingSeconds: raw.estimated_remaining_seconds,
  };
}

export function useFingerprintCoverage(enabled = true): UseFingerprintCoverageReturn {
  const [coverage, setCoverage] = useState<FingerprintCoverage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [enqueueing, setEnqueueing] = useState(false);

  // Guards every setState after an await: the settings dialog is unmounted the
  // moment it closes, which is routinely mid-poll.
  const mountedRef = useRef(true);
  // Aborts any in-flight read/enqueue on unmount, so a hung request cannot sit
  // behind the 10 s poll and stack more behind it (#5649/#5650).
  const abortRef = useRef(new AbortController());
  useEffect(() => {
    mountedRef.current = true;
    if (abortRef.current.signal.aborted) abortRef.current = new AbortController();
    return () => {
      mountedRef.current = false;
      abortRef.current.abort();
    };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // Shared transport: DEFAULT_TIMEOUT_MS, backend `detail`, status on the error.
      const raw = await get<RawCoverage>('/api/library/fingerprints/status', {
        signal: abortRef.current.signal,
      });
      if (!mountedRef.current) return;
      setCoverage(toCoverage(raw));
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to read analysis progress');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  const analyseRemaining = useCallback(async () => {
    setEnqueueing(true);
    setNotice(null);
    try {
      const result = await post<{ dropped_queue_full?: number | null; message?: string }>(
        '/api/similarity/fingerprint-queue/enqueue-all',
        undefined,
        { signal: abortRef.current.signal },
      );
      if (!mountedRef.current) return;
      setError(null);
      // The backend words the full-queue case; refresh() below must not erase it.
      if (result?.dropped_queue_full) setNotice(result.message ?? null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Failed to queue tracks for analysis');
    } finally {
      if (mountedRef.current) setEnqueueing(false);
    }
    // Outside the try: the queue depth changed either way, and a refresh error
    // is reported by refresh() itself.
    await refresh();
  }, [refresh]);

  // Initial read.
  useEffect(() => {
    if (!enabled) return;
    void refresh();
  }, [enabled, refresh]);

  // Poll only while there is outstanding work.
  useEffect(() => {
    if (!enabled) return;
    if (!coverage || coverage.pendingTracks === 0) return;

    const id = setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [enabled, coverage, refresh]);

  return { coverage, loading, error, notice, enqueueing, analyseRemaining, refresh };
}

export default useFingerprintCoverage;
