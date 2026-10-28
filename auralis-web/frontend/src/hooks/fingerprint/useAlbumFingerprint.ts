/**
 * useAlbumFingerprint Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Fetches median fingerprint for an album (aggregated from all tracks).
 * Used to generate unique gradient placeholders based on sonic identity.
 *
 * Features:
 * - Lazy loading (only fetches when needed)
 * - Caching via React Query
 * - Error handling with graceful fallback
 * - Returns partial fingerprint for safe gradient generation
 */

import { useQuery, useQueries } from '@tanstack/react-query';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';
import { get, getOrNullOn404 } from '@/utils/apiRequest';
import { QUERY_GC_TIME_MS, QUERY_STALE_TIME_MS } from '@/config/timing';

interface AlbumFingerprintResponse {
  album_id: number;
  album_title: string;
  track_count: number;
  fingerprinted_track_count: number;
  fingerprint: AudioFingerprint;
}

/**
 * Fetch album fingerprint from backend.
 *
 * A 404 is the one expected non-error outcome (no fingerprint yet), so it
 * resolves to `null` via `getOrNullOn404` (#6221) and the caller falls back
 * to the hash gradient. Everything else — a non-2xx status or a network-level
 * failure — rejects.
 *
 * This used to wrap its own `throw` in a `try/catch` that turned every failure
 * back into `null` (#5122), which made a broken endpoint indistinguishable from
 * "this album has no fingerprint yet": the `useQuery` queryFn never rejected, so
 * `query.error` was permanently `undefined` and `query.isError` permanently
 * `false`. It also disabled retries — React Query is configured `retry: 1`, and
 * a resolved `null` is a success, so a transient 500 was cached for the 5-minute
 * staleTime instead of being retried. #4847 fixed exactly this in the sibling
 * `useTrackFingerprint`; this is the half that sweep missed, and it converges on
 * that hook's shape rather than inventing a third.
 */
const fetchAlbumFingerprint = (
  albumId: number,
  signal?: AbortSignal
): Promise<AudioFingerprint | null> =>
  // #5019: shared transport, which bounds the request at DEFAULT_TIMEOUT_MS.
  // The bare fetch() this replaces had no signal and no timeout, and a grid
  // of album tiles issues one of these per tile. The caller's query signal
  // is forwarded so unmount/invalidation aborts in-flight requests (#5611).
  getOrNullOn404<AlbumFingerprintResponse>(`/api/albums/${albumId}/fingerprint`, { signal })
    .then((data) => (data === null ? null : data.fingerprint));

/**
 * Hook to fetch album fingerprint with caching
 *
 * @param albumId - Album ID
 * @param options - Query options
 * @returns Fingerprint data or null if unavailable
 *
 * @example
 * ```tsx
 * const { fingerprint, isLoading } = useAlbumFingerprint(albumId);
 *
 * <AlbumCard
 *   albumId={albumId}
 *   fingerprint={fingerprint}
 *   ...
 * />
 * ```
 */
export function useAlbumFingerprint(
  albumId: number,
  options?: {
    enabled?: boolean;
  }
) {
  const query = useQuery({
    queryKey: ['album-fingerprint', albumId],
    // { signal } forwarded so unmount/invalidation aborts the in-flight
    // request (#5650's gap, same as the batch hook below already did).
    queryFn: ({ signal }) => fetchAlbumFingerprint(albumId, signal),
    staleTime: QUERY_STALE_TIME_MS, // fingerprints don't change often
    gcTime: QUERY_GC_TIME_MS,   // 30 minutes cache retention
    enabled: options?.enabled ?? true,
    // Kept false, but the original rationale no longer applies: since #5122 a
    // 404 resolves to `null` rather than throwing, so it was never going to be
    // retried anyway. What `false` now suppresses is retrying a genuine 5xx.
    // Settled decision, not a pending revisit: album art is decorative and
    // every tile has a hash-gradient fallback, so retrying a failing endpoint
    // once per visible album is not worth the request volume.
    retry: false,
  });

  return {
    fingerprint: query.data ?? undefined,
    isLoading: query.isLoading,
    error: query.error,
  };
}

/**
 * #3644: concurrency cap. The Electron-local FastAPI serves all requests
 * serially in the ASGI loop, so firing many requests at once starves
 * audio-streaming requests of I/O time. A promise-pool gate keeps at most N
 * batch requests in flight (#5611).
 */
const FINGERPRINT_BATCH_CONCURRENCY = 4;

/** Ids per `GET /api/albums/fingerprints`; the route caps the list at 200. */
const FINGERPRINT_BATCH_MAX_IDS = 100;

let fingerprintSlotsInUse = 0;
const fingerprintSlotWaiters: Array<() => void> = [];

async function withFingerprintSlot<T>(fn: () => Promise<T>, signal?: AbortSignal): Promise<T> {
  while (fingerprintSlotsInUse >= FINGERPRINT_BATCH_CONCURRENCY) {
    await new Promise<void>((release) => fingerprintSlotWaiters.push(release));
  }
  fingerprintSlotsInUse++;
  try {
    // #5650: a batch whose queries were all cancelled (unmount, key change,
    // scrolled away) while it waited for a slot must not then be requested.
    signal?.throwIfAborted();
    return await fn();
  } finally {
    fingerprintSlotsInUse--;
    fingerprintSlotWaiters.shift()?.();
  }
}

interface AlbumFingerprintsResponse {
  albums: Array<{ album_id: number; fingerprint: AudioFingerprint }>;
}

interface PendingFingerprint {
  albumId: number;
  signal?: AbortSignal;
  resolve: (fingerprint: AudioFingerprint | null) => void;
  reject: (reason: unknown) => void;
}

let pendingFingerprints: PendingFingerprint[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * #5873: the grid issued one `/api/albums/{id}/fingerprint` per loaded album
 * (each hydrating the full album server-side), thousands over a long scroll.
 * Every per-album queryFn started in the same tick (a new page mounting its
 * tiles) now joins one `/api/albums/fingerprints?ids=…` request. An album
 * absent from the answer has no fingerprint yet and resolves to null, which
 * the tile renders as the hash gradient — the batch route's equivalent of the
 * single route's 404.
 */
function flushFingerprintBatch(): void {
  flushTimer = null;
  const waiting = pendingFingerprints;
  pendingFingerprints = [];
  const live = waiting.filter((entry) => {
    // #5650: a query cancelled (unmount, key change) before the request was
    // built must not then be fetched.
    if (entry.signal?.aborted) entry.reject(entry.signal.reason);
    return !entry.signal?.aborted;
  });
  for (let start = 0; start < live.length; start += FINGERPRINT_BATCH_MAX_IDS) {
    const batch = live.slice(start, start + FINGERPRINT_BATCH_MAX_IDS);
    const params = new URLSearchParams();
    new Set(batch.map((entry) => entry.albumId)).forEach((id) => params.append('ids', String(id)));
    const signal = abortWhenAllAbort(batch);
    withFingerprintSlot(
      () => get<AlbumFingerprintsResponse>(`/api/albums/fingerprints?${params}`, { signal }),
      signal,
    )
      .then((data) => {
        const byId = new Map(data.albums.map((album) => [album.album_id, album.fingerprint]));
        batch.forEach((entry) => entry.resolve(byId.get(entry.albumId) ?? null));
      })
      .catch((error: unknown) => batch.forEach((entry) => entry.reject(error)));
  }
}

/** A signal that aborts once every query in *batch* has been cancelled. */
function abortWhenAllAbort(batch: PendingFingerprint[]): AbortSignal {
  const controller = new AbortController();
  let remaining = batch.length;
  batch.forEach(({ signal }) => {
    if (!signal) return;
    signal.addEventListener('abort', () => {
      remaining -= 1;
      if (remaining === 0) controller.abort(signal.reason);
    }, { once: true });
  });
  return controller.signal;
}

function fetchAlbumFingerprintBatched(
  albumId: number,
  signal?: AbortSignal
): Promise<AudioFingerprint | null> {
  return new Promise((resolve, reject) => {
    pendingFingerprints.push({ albumId, signal, resolve, reject });
    flushTimer ??= setTimeout(flushFingerprintBatch, 0);
  });
}

export function useAlbumFingerprints(albumIds: number[]) {
  // #5611: one query per album, keyed exactly like useAlbumFingerprint so the
  // two hooks share a cache — not one batch query keyed by the whole id list.
  // The old single key changed on every infinite-scroll page, so each page
  // refetched every album from scratch (O(N²/50) requests over a scroll) and
  // the hook returned an empty Map while it ran, blanking every tile's
  // fingerprint colouring. Per-album keys are stable under any list growth:
  // scrolling only starts queries for albums not already cached, and those
  // share one request per page through the batcher above (#5873).
  const queries = useQueries({
    queries: albumIds.map((albumId) => ({
      queryKey: ['album-fingerprint', albumId],
      queryFn: ({ signal }: { signal?: AbortSignal }) =>
        fetchAlbumFingerprintBatched(albumId, signal),
      staleTime: QUERY_STALE_TIME_MS,
      gcTime: QUERY_GC_TIME_MS,
      // Same settled decision as the single-album hook: album art is
      // decorative and every tile has a hash-gradient fallback.
      retry: false,
    })),
  });

  // Rebuilt per render — cheap at grid sizes, and the old hook likewise
  // returned a fresh Map each render. Cached albums are present immediately,
  // so adding a page never blanks the existing tiles.
  const fingerprints = new Map<number, AudioFingerprint | null>();
  albumIds.forEach((albumId, index) => {
    fingerprints.set(albumId, queries[index]?.data ?? null);
  });

  return {
    fingerprints,
    isLoading: queries.some(query => query.isLoading),
    error: queries.find(query => query.error)?.error ?? null,
  };
}
