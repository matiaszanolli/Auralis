const DEBUG = import.meta.env.DEV;

import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import type { LibraryTrack } from '@/types/domain';
import { PAGE_LIMIT, fetchTracksPage, friendlyFetchError } from './libraryPageFetch';

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
  const requestIdRef = useRef(0);

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

  const fetchTracks = useCallback(
    async (resetPagination = true) => {
      const requestId = ++requestIdRef.current;
      const isStale = () => requestIdRef.current !== requestId;
      fetchInProgressRef.current = true;
      setLoading(true);
      setError(null);

      if (resetPagination) {
        setOffset(0);
        setTracks([]);
        setHasMore(true);
        setTotalTracks(0);
      }

      // Declared outside the try so the catch block can tell "this request
      // was deliberately aborted (supersession or unmount)" apart from a
      // genuine failure without depending on error type/name, which get()
      // does not preserve (#5346 — see the file-level comment on loadMore's
      // matching hoist).
      let controller: AbortController | undefined;
      try {
        const currentOffset = resetPagination ? 0 : offsetRef.current;

        fetchAbortRef.current?.abort();
        controller = new AbortController();
        fetchAbortRef.current = controller;

        const page = await fetchTracksPage(view, currentOffset, controller.signal, search);
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
      } catch (err) {
        if (controller?.signal.aborted) return;
        if (isStale()) return;

        console.error('Error fetching tracks:', err);
        const errorMsg = friendlyFetchError(err, 'Failed to load library');
        setError(errorMsg);
        toastRef.current.toastError(errorMsg);
      } finally {
        // A superseded request must not clear the active refresh's loading
        // state or guard.
        if (!isStale()) {
          setLoading(false);
          fetchInProgressRef.current = false;
        }
      }
    },
    // Toast fns read via toastRef, so only 'view' affects identity (#3943 / #3378).
    [view, search]
  );

  /**
   * Re-fetch the already-loaded pages in place (#5626).
   *
   * Post-mutation refreshes (metadata save, bulk actions, library_updated,
   * scan complete) used to go through fetchTracks(), which empties the list,
   * raises the full-screen `loading`, and drops everything past page 1 — the
   * virtualized list was torn down to a skeleton and the user lost scroll,
   * focus, selection and pagination on every save. This re-fetches exactly
   * as many pages as are loaded, replaces the array wholesale (never
   * appends — no duplicates), and never touches `loading`: the list stays
   * mounted and the old rows ride out the request. A failure keeps the old
   * list and surfaces the toast error.
   */
  const refreshTracks = useCallback(async () => {
    const loaded = tracksLengthRef.current;
    if (loaded === 0) {
      // Nothing mounted yet — the initial-load path is the right UX here.
      return fetchTracks(true);
    }

    const requestId = ++requestIdRef.current;
    const isStale = () => requestIdRef.current !== requestId;
    fetchInProgressRef.current = true;
    setError(null);

    let controller: AbortController | undefined;
    try {
      const refreshed: LibraryTrack[] = [];
      let newOffset = 0;
      let more = true;
      let latestTotal = 0;
      // Re-fetch exactly as many pages as are loaded: the visible rows are
      // replaced with current data AND pagination continuity is kept —
      // loadMore continues from the refresh's last offset.
      while (refreshed.length < loaded && more) {
        fetchAbortRef.current?.abort();
        controller = new AbortController();
        fetchAbortRef.current = controller;

        const page = await fetchTracksPage(view, newOffset, controller.signal, search);
        if (isStale()) return;

        refreshed.push(...page.tracks);
        more = page.hasMore;
        latestTotal = page.total;
        newOffset += PAGE_LIMIT;
      }

      setTracks(refreshed);
      setOffset(newOffset);
      setHasMore(more);
      setTotalTracks(latestTotal);
    } catch (err) {
      if (controller?.signal.aborted) return;
      if (isStale()) return;

      console.error('Error refreshing tracks:', err);
      const errorMsg = friendlyFetchError(err, 'Failed to refresh library');
      setError(errorMsg);
      toastRef.current.toastError(errorMsg);
      // The previously-loaded list stays exactly as it was.
    } finally {
      if (!isStale()) {
        fetchInProgressRef.current = false;
      }
    }
  }, [view, fetchTracks]);

  const loadMore = useCallback(async () => {
    if (loadMoreInProgressRef.current || fetchInProgressRef.current) {
      DEBUG && console.log('[useLibraryPagination] loadMore already in progress, skipping');
      return;
    }

    loadMoreInProgressRef.current = true;
    const requestId = ++requestIdRef.current;
    const isStale = () => requestIdRef.current !== requestId;
    setIsLoadingMore(true);

    // See fetchTracks' matching hoist for why: get() does not preserve the
    // original error's type/name, so abort detection reads the controller's
    // own signal instead (#5346).
    let controller: AbortController | undefined;
    try {
      // Read live offset via ref — avoids stale closure capturing page-0 offset (#3378).
      const newOffset = offsetRef.current + PAGE_LIMIT;

      fetchAbortRef.current?.abort();
      controller = new AbortController();
      fetchAbortRef.current = controller;

      // Same guard as fetchTracks (#5346) — this is the loadMore call site
      // the issue's WIRING check named explicitly.
      const page = await fetchTracksPage(view, newOffset, controller.signal, search);
      if (isStale()) return;

      // Commit offset advance only after successful fetch
      setOffset(newOffset);
      setTracks((prev) => [...prev, ...page.tracks]);
      setHasMore(page.hasMore);
      setTotalTracks(page.total);

      DEBUG && console.log(`Loaded more: ${newOffset + page.tracks.length}/${page.total}`);
    } catch (err) {
      if (controller?.signal.aborted) return;
      if (isStale()) return;

      console.error('Error loading more tracks:', err);
      const errorMsg = friendlyFetchError(err, 'Failed to load more tracks');
      setError(errorMsg);
      toastRef.current.toastError(errorMsg);
      // Stop the scroll trigger from looping on a transient network failure.
      setHasMore(false);
    } finally {
      setIsLoadingMore(false);
      loadMoreInProgressRef.current = false;
    }
  }, [view, search]);

  return { tracks, loading, error, hasMore, totalTracks, offset, isLoadingMore, fetchTracks, refreshTracks, loadMore, fetchAbortRef };
};
