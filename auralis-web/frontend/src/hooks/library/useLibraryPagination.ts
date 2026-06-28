const DEBUG = import.meta.env.DEV;

import { useState, useCallback, useEffect, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import { transformBackendTrack, type LibraryTrack, type TrackApiResponse } from '@/types/domain';

export interface UseLibraryPaginationOptions {
  view: string;
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
  loadMore: () => Promise<void>;
  fetchAbortRef: React.MutableRefObject<AbortController | null>;
}

export const useLibraryPagination = ({ view }: UseLibraryPaginationOptions): UseLibraryPaginationReturn => {
  const [tracks, setTracks] = useState<LibraryTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const fetchInProgressRef = useRef(false);
  const fetchAbortRef = useRef<AbortController | null>(null);

  // Mirror `offset` into a ref so fetchTracks(false) can read the live value
  // without `offset` in useCallback deps — avoids recreating fetchTracks on
  // every page advance and prevents re-render loops (#3378).
  const offsetRef = useRef(0);
  offsetRef.current = offset;

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
      if (fetchInProgressRef.current) {
        DEBUG && console.log('[useLibraryPagination] Fetch already in progress, skipping');
        return;
      }

      fetchInProgressRef.current = true;
      setLoading(true);
      setError(null);

      if (resetPagination) {
        setOffset(0);
        setTracks([]);
      }

      try {
        const limit = 50;
        const currentOffset = resetPagination ? 0 : offsetRef.current;
        const endpoint =
          view === 'favourites'
            ? `/api/library/tracks/favorites?limit=${limit}&offset=${currentOffset}`
            : `/api/library/tracks?limit=${limit}&offset=${currentOffset}`;

        fetchAbortRef.current?.abort();
        const controller = new AbortController();
        fetchAbortRef.current = controller;

        const response = await fetch(endpoint, { signal: controller.signal });
        if (response.ok) {
          const data: { tracks?: TrackApiResponse[]; has_more?: boolean; total?: number } = await response.json();
          const transformedTracks: LibraryTrack[] = (data.tracks || []).map(transformBackendTrack);

          setHasMore(data.has_more || false);
          setTotalTracks(data.total || 0);

          if (resetPagination) {
            setTracks(transformedTracks);
          } else {
            setTracks((prev) => [...prev, ...transformedTracks]);
          }

          DEBUG && console.log('Loaded', data.tracks?.length || 0, view === 'favourites' ? 'favorite tracks' : 'tracks from library');
          DEBUG && console.log(`Pagination: ${currentOffset + (data.tracks?.length || 0)}/${data.total || 0}, has_more: ${data.has_more}`);

          if (resetPagination && data.tracks && data.tracks.length > 0) {
            toastRef.current.success(`Loaded ${data.tracks.length} of ${data.total} ${view === 'favourites' ? 'favorites' : 'tracks'}`);
          } else if (resetPagination && view === 'favourites') {
            toastRef.current.info('No favorites yet. Click the heart icon on tracks to add them!');
          }
        } else {
          console.error('Failed to fetch tracks');
          setError('Failed to load library');
          toastRef.current.toastError('Failed to load library');
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        console.error('Error fetching tracks:', err);
        const errorMsg = 'Failed to connect to server';
        setError(errorMsg);
        toastRef.current.toastError(errorMsg);
      } finally {
        setLoading(false);
        fetchInProgressRef.current = false;
      }
    },
    // Toast fns read via toastRef, so only 'view' affects identity (#3943 / #3378).
    [view]
  );

  const loadMore = useCallback(async () => {
    if (fetchInProgressRef.current) {
      DEBUG && console.log('[useLibraryPagination] loadMore already in progress, skipping');
      return;
    }

    fetchInProgressRef.current = true;
    setIsLoadingMore(true);

    try {
      const limit = 50;
      // Read live offset via ref — avoids stale closure capturing page-0 offset (#3378).
      const newOffset = offsetRef.current + limit;
      const endpoint =
        view === 'favourites'
          ? `/api/library/tracks/favorites?limit=${limit}&offset=${newOffset}`
          : `/api/library/tracks?limit=${limit}&offset=${newOffset}`;

      fetchAbortRef.current?.abort();
      const controller = new AbortController();
      fetchAbortRef.current = controller;

      const response = await fetch(endpoint, { signal: controller.signal });
      if (response.ok) {
        const data: { tracks?: TrackApiResponse[]; has_more?: boolean; total?: number } = await response.json();
        const transformedTracks: LibraryTrack[] = (data.tracks || []).map(transformBackendTrack);

        // Commit offset advance only after successful fetch
        setOffset(newOffset);
        setTracks((prev) => [...prev, ...transformedTracks]);
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        DEBUG && console.log(`Loaded more: ${newOffset + transformedTracks.length}/${data.total || 0}`);
      } else {
        // Mirror fetchTracks' non-OK handling (#4173): surface the error and
        // clear hasMore so the infinite-scroll trigger stops re-firing into a
        // retry storm against a struggling server. A manual refetch (which
        // resets hasMore on success) recovers.
        console.error('Failed to load more tracks');
        setError('Failed to load more tracks');
        toastRef.current.toastError('Failed to load more tracks');
        setHasMore(false);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      console.error('Error loading more tracks:', err);
      const errorMsg = 'Failed to connect to server';
      setError(errorMsg);
      toastRef.current.toastError(errorMsg);
      // Stop the scroll trigger from looping on a transient network failure.
      setHasMore(false);
    } finally {
      setIsLoadingMore(false);
      fetchInProgressRef.current = false;
    }
  }, [view]);

  return { tracks, loading, error, hasMore, totalTracks, offset, isLoadingMore, fetchTracks, loadMore, fetchAbortRef };
};
