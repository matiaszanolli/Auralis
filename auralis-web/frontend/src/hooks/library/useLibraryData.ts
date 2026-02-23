/**
 * useLibraryData - Library Data Fetching Hook
 *
 * Manages library data fetching, pagination, and folder scanning.
 * Extracted from CozyLibraryView.tsx for reusability and maintainability.
 *
 * Features:
 * - Paginated track loading (50 tracks per page)
 * - Infinite scroll support
 * - Folder scanning via API
 * - Favorites vs. all tracks support
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  album_id?: number;
  duration: number;
  albumArt?: string;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

export interface UseLibraryDataOptions {
  view: string;
  autoLoad?: boolean;
}

export interface UseLibraryDataReturn {
  // State
  tracks: Track[];
  loading: boolean;
  hasMore: boolean;
  totalTracks: number;
  offset: number;
  isLoadingMore: boolean;
  scanning: boolean;
  /** Controlled folder-path value for the web-browser (non-Electron) scan input. */
  webFolderPath: string;

  // Methods
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  loadMore: () => Promise<void>;
  handleScanFolder: () => Promise<void>;
  isElectron: () => boolean;
  /** Setter for the web-browser scan-path controlled input. */
  setWebFolderPath: (path: string) => void;
}

/**
 * Custom hook for library data management
 */
export const useLibraryData = ({
  view,
  autoLoad = true
}: UseLibraryDataOptions): UseLibraryDataReturn => {
  // State
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [offset, setOffset] = useState(0);
  const offsetRef = useRef(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  // Ref-based guard to prevent concurrent loadMore calls from racing (fixes #2603).
  // State-based guard (`isLoadingMore`) is stale within the same React render frame,
  // so two rapid scroll events can both enter loadMore before React re-renders.
  const isLoadingMoreRef = useRef(false);
  const [scanning, setScanning] = useState(false);
  // Controlled input for folder path in web (non-Electron) environments (fixes #2359).
  const [webFolderPath, setWebFolderPath] = useState('');

  const { success, error, info } = useToast();

  // Check if running in Electron
  const isElectron = useCallback(() => {
    return !!(window as any).electronAPI;
  }, []);

  // Fetch tracks from API with pagination
  const fetchTracks = useCallback(async (resetPagination = true) => {
    setLoading(true);
    if (resetPagination) {
      offsetRef.current = 0;
      setOffset(0);
      setTracks([]);
    }

    try {
      const limit = 50;
      // Read offset from ref so this callback never closes over stale state
      const currentOffset = resetPagination ? 0 : offsetRef.current;

      // Determine which endpoint to use based on view
      // Use relative URLs to leverage Vite proxy (avoids CORS issues)
      const endpoint = view === 'favourites'
        ? `/api/library/tracks/favorites?limit=${limit}&offset=${currentOffset}`
        : `/api/library/tracks?limit=${limit}&offset=${currentOffset}`;

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();

        // Transform tracks data to match frontend interface
        const transformedTracks = (data.tracks || []).map((track: any) => ({
          ...track,
          artist: Array.isArray(track.artists) && track.artists.length > 0 ? track.artists[0] : track.artist || 'Unknown Artist',
          albumArt: track.artwork_url || track.album_art || track.albumArt, // artwork_url is current name (issue #2386)
        }));

        // Update state with pagination info
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        if (resetPagination) {
          setTracks(transformedTracks);
        } else {
          setTracks(prev => [...prev, ...transformedTracks]);
        }

        console.log('Loaded', data.tracks?.length || 0, view === 'favourites' ? 'favorite tracks' : 'tracks from library');
        console.log(`Pagination: ${currentOffset + (data.tracks?.length || 0)}/${data.total || 0}, has_more: ${data.has_more}`);

        if (resetPagination && data.tracks && data.tracks.length > 0) {
          success(`Loaded ${data.tracks.length} of ${data.total} ${view === 'favourites' ? 'favorites' : 'tracks'}`);
        } else if (resetPagination && view === 'favourites') {
          info('No favorites yet. Click the heart icon on tracks to add them!');
        }
      } else {
        console.error('Failed to fetch tracks');
        // Show error state — never fall back to mock data in production (fixes #2344).
        error('Failed to load library. Check that the Auralis backend is running.');
      }
    } catch (err) {
      console.error('Error fetching tracks:', err);
      // Show error state — never fall back to mock data in production (fixes #2344).
      error('Cannot connect to Auralis server. Retry when the backend is available.');
    } finally {
      setLoading(false);
    }
  }, [view, success, error, info]);

  // Load more tracks (for infinite scroll).
  // Uses ref-based guard to prevent duplicate fetches from concurrent scroll events (fixes #2603).
  const loadMore = useCallback(async () => {
    if (isLoadingMoreRef.current || !hasMore) {
      return;
    }

    // Synchronous ref update prevents concurrent calls within the same frame
    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);
    try {
      const limit = 50;
      const newOffset = offsetRef.current + limit;
      offsetRef.current = newOffset;
      setOffset(newOffset);

      // Use relative URLs to leverage Vite proxy (avoids CORS issues)
      const endpoint = view === 'favourites'
        ? `/api/library/tracks/favorites?limit=${limit}&offset=${newOffset}`
        : `/api/library/tracks?limit=${limit}&offset=${newOffset}`;

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();

        // Transform tracks data to match frontend interface
        const transformedTracks = (data.tracks || []).map((track: any) => ({
          ...track,
          artist: Array.isArray(track.artists) && track.artists.length > 0 ? track.artists[0] : track.artist || 'Unknown Artist',
          albumArt: track.artwork_url || track.album_art || track.albumArt, // artwork_url is current name (issue #2386)
        }));

        // Append new tracks
        setTracks(prev => [...prev, ...transformedTracks]);
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        console.log(`Loaded more: ${newOffset + transformedTracks.length}/${data.total || 0}`);
      }
    } catch (err) {
      console.error('Error loading more tracks:', err);
    } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [hasMore, view]);

  // Handle folder scan
  // Blocking alert()/prompt() replaced with toast notifications (fixes #2359).
  const handleScanFolder = useCallback(async () => {
    let folderPath: string | undefined;

    // Use native folder picker in Electron
    if (isElectron()) {
      try {
        const result = await (window as any).electronAPI.selectFolder();
        if (result && result.length > 0) {
          folderPath = result[0];
        } else {
          return; // User cancelled
        }
      } catch (err) {
        console.error('Failed to open folder picker:', err);
        error('Failed to open folder picker');
        return;
      }
    } else {
      // Web browser: read from the controlled input (set via setWebFolderPath).
      folderPath = webFolderPath.trim() || undefined;
      if (!folderPath) {
        info('Enter a folder path in the scan field and try again');
        return;
      }
    }

    setScanning(true);
    try {
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directories: [folderPath] })
      });

      if (response.ok) {
        const result = await response.json();
        success(`Scan complete — ${result.files_added || 0} track(s) added`);
        // Refresh the library
        await fetchTracks();
      } else {
        const errorData = await response.json().catch(() => ({}));
        error(`Scan failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Scan error:', err);
      error('Error scanning folder — check the backend is reachable');
    } finally {
      setScanning(false);
    }
  }, [isElectron, fetchTracks, webFolderPath, success, error, info]);

  // Auto-load on mount or when view/autoLoad changes.
  // fetchTracks is safe to include now that offset is held in a ref (not closure).
  useEffect(() => {
    if (autoLoad) {
      fetchTracks();
    }
  }, [view, autoLoad, fetchTracks]);

  return {
    // State
    tracks,
    loading,
    hasMore,
    totalTracks,
    offset,
    isLoadingMore,
    scanning,
    webFolderPath,

    // Methods
    fetchTracks,
    loadMore,
    handleScanFolder,
    isElectron,
    setWebFolderPath,
  };
};

export default useLibraryData;
