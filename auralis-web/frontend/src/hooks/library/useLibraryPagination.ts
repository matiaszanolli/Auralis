const DEBUG = import.meta.env.DEV;

import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { useLatestRequestGuard } from '@/hooks/shared/useLatestRequestGuard';
import type { LibraryTrack } from '@/types/domain';
import {
  PAGE_LIMIT,
  fetchLoadedPages,
  fetchTracksPage,
  friendlyFetchError,
  replaceAbortController,
} from './libraryPageFetch';

export interface UseLibraryPaginationOptions {
  view: string;
  /** Server-side search (#5866); changing it re-keys the fetch callbacks. */
  search?: string;
}

export interface UseLibraryPaginationReturn {
  tracks: LibraryTrack[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  totalTracks: number;
  offset: number;
  isLoadingMore: boolean;
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  /** In-place refresh of the loaded pages — never empties the list (#5626). */
  refreshTracks: () => Promise<void>;
  loadMore: () => Promise<void>;
  fetchAbortRef: React.MutableRefObject<AbortController | null>;
}

export const useLibraryPagination = ({ view, search = '' }: UseLibraryPaginationOptions): UseLibraryPaginationReturn => {
  const [tracks, setTracks] = useState<LibraryTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const fetchInProgressRef = useRef(false);
  const loadMoreInProgressRef = useRef(false);
  const fetchAbortRef = useRef<AbortController | null>(null);
  // A refresh supersedes every older request. This prevents a stale page from
  // appending after the user switches views, even if a fetch mock or transport
  // ignores AbortController cancellation (#4891).
  const beginRequest = useLatestRequestGuard();

  // Mirror `offset` into a ref so fetchTracks(false) can read the live value
  // without `offset` in useCallback deps — avoids recreating fetchTracks on
  // every page advance and prevents re-render loops (#3378).
  const offsetRef = useRef(0);
  offsetRef.current = offset;

  // Mirror tracks.length so refreshTracks can size its re-fetch without
  // depending on `tracks` (same identity-stability reasoning as offsetRef).
  const tracksLengthRef = useRef(0);
  tracksLengthRef.current = tracks.length;

  const { success, error: toastError, info } = useToast();
  // Mirror toast fns into a ref so fetchTracks deps stay stable across renders
  // (#3943 — useToast returns fresh identities every render).
  const toastRef = useRef({ success, toastError, info });
  toastRef.current = { success, toastError, info };

  // Abort in-flight fetch on unmount.
  useEffect(() => {
    return () => { fetchAbortRef.current?.abort(); };
  }, []);

  /**
   * The request envelope all three paths share: take a fresh request id (a refresh/load supersedes
   * every older request, so a stale page never appends after a view switch even if a transport
   * ignores AbortController cancellation, #4891), run `body`, and report a genuine failure.
   *
   * A deliberate abort (supersession or unmount) is told apart from a failure by the
   * controller's own signal, not the error: get() does not preserve the error's type/name (#5346).
   */
  const runGuarded = useCallback(
    async (spec: {
      logLabel: string;
      failureMessage: string;
      body: (isStale: () => boolean, nextSignal: () => AbortSignal) => Promise<void>;
      onFailure?: () => void;
      onSettled: (isStale: () => boolean) => void;
    }) => {
      const isStale = beginRequest();
      let controller: AbortController | undefined;
      const nextSignal = () => (controller = replaceAbortController(fetchAbortRef)).signal;
      try {
        await spec.body(isStale, nextSignal);
      } catch (err) {
        if (controller?.signal.aborted) return;
        if (isStale()) return;

        console.error(`Error ${spec.logLabel}:`, err);
        const errorMsg = friendlyFetchError(err, spec.failureMessage);
        setError(errorMsg);
        toastRef.current.toastError(errorMsg);
        spec.onFailure?.();
      } finally {
        spec.onSettled(isStale);
      }
    },
    [beginRequest]
  );

  const fetchTracks = useCallback(
    async (resetPagination = true) => {
      fetchInProgressRef.current = true;
      setLoading(true);
      setError(null);

      if (resetPagination) {
        setOffset(0);
        setTracks([]);
        setHasMore(true);
        setTotalTracks(0);
      }

      await runGuarded({
        logLabel: 'fetching tracks',
        failureMessage: 'Failed to load library',
        body: async (isStale, nextSignal) => {
          const currentOffset = resetPagination ? 0 : offsetRef.current;
          const page = await fetchTracksPage(view, currentOffset, nextSignal(), search);
          if (isStale()) return;

          setHasMore(page.hasMore);
          setTotalTracks(page.total);

          if (resetPagination) {
            setTracks(page.tracks);
          } else {
            setTracks((prev) => [...prev, ...page.tracks]);
          }

          DEBUG && console.log('Loaded', page.rawCount, view === 'favourites' ? 'favorite tracks' : 'tracks from library');
          DEBUG && console.log(`Pagination: ${currentOffset + page.rawCount}/${page.total}, has_more: ${page.hasMore}`);

          if (resetPagination && page.rawCount > 0) {
            toastRef.current.success(`Loaded ${page.rawCount} of ${page.total} ${view === 'favourites' ? 'favorites' : 'tracks'}`);
          } else if (resetPagination && view === 'favourites') {
            toastRef.current.info('No favorites yet. Click the heart icon on tracks to add them!');
          }
        },
        // A superseded request must not clear the active refresh's loading state or guard.
        onSettled: (isStale) => {
          if (!isStale()) {
            setLoading(false);
            fetchInProgressRef.current = false;
          }
        },
      });
    },
    // Toast fns read via toastRef, so only 'view' affects identity (#3943 / #3378).
    [view, search, runGuarded]
  );

  /**
   * Re-fetch the already-loaded pages in place (#5626).
   *
   * Post-mutation refreshes (metadata save, bulk actions, library_updated, scan complete) used to
   * go through fetchTracks(), which empties the list, raises the full-screen `loading`, and drops
   * everything past page 1 - the virtualized list was torn down to a skeleton and the user lost
   * scroll, focus, selection and pagination on every save. This re-fetches exactly as many pages
   * as are loaded, replaces the array wholesale (never appends - no duplicates), and never touches
   * `loading`: the list stays mounted and the old rows ride out the request. A failure keeps the
   * old list and surfaces the toast error.
   */
  const refreshTracks = useCallback(async () => {
    const loaded = tracksLengthRef.current;
    // Nothing mounted yet - the initial-load path is the right UX here.
    if (loaded === 0) return fetchTracks(true);

    fetchInProgressRef.current = true;
    setError(null);

    await runGuarded({
      logLabel: 'refreshing tracks',
      failureMessage: 'Failed to refresh library',
      body: async (isStale, nextSignal) => {
        const refreshed = await fetchLoadedPages(view, search, loaded, nextSignal, isStale);
        if (!refreshed) return;

        setTracks(refreshed.tracks);
        setOffset(refreshed.offset);
        setHasMore(refreshed.hasMore);
        setTotalTracks(refreshed.total);
      },
      onSettled: (isStale) => {
        if (!isStale()) fetchInProgressRef.current = false;
      },
    });
  }, [view, search, fetchTracks, runGuarded]);

  const loadMore = useCallback(async () => {
    if (loadMoreInProgressRef.current || fetchInProgressRef.current) {
      DEBUG && console.log('[useLibraryPagination] loadMore already in progress, skipping');
      return;
    }

    loadMoreInProgressRef.current = true;
    setIsLoadingMore(true);

    await runGuarded({
      logLabel: 'loading more tracks',
      failureMessage: 'Failed to load more tracks',
      body: async (isStale, nextSignal) => {
        // Read live offset via ref - avoids a stale closure capturing the page-0 offset (#3378).
        const newOffset = offsetRef.current + PAGE_LIMIT;
        const page = await fetchTracksPage(view, newOffset, nextSignal(), search);
        if (isStale()) return;

        // Commit the offset advance only after a successful fetch.
        setOffset(newOffset);
        setTracks((prev) => [...prev, ...page.tracks]);
        setHasMore(page.hasMore);
        setTotalTracks(page.total);

        DEBUG && console.log(`Loaded more: ${newOffset + page.tracks.length}/${page.total}`);
      },
      // Stop the scroll trigger from looping on a transient network failure.
      onFailure: () => setHasMore(false),
      onSettled: () => {
        setIsLoadingMore(false);
        loadMoreInProgressRef.current = false;
      },
    });
  }, [view, search, runGuarded]);

  return { tracks, loading, error, hasMore, totalTracks, offset, isLoadingMore, fetchTracks, refreshTracks, loadMore, fetchAbortRef };
};
