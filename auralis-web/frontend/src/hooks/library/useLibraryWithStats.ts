/**
 * useLibraryWithStats - Library Data and Statistics Composition Hook
 *
 * Unified hook combining library data fetching and statistics.
 * Provides both track pagination and library-level statistics in a single hook.
 *
 * This consolidates useLibraryData and useLibraryStats into a single composition,
 * reducing hook complexity and improving state management cohesion.
 *
 * Features:
 * - Paginated track loading (50 tracks per page)
 * - Infinite scroll support
 * - Library statistics (total tracks, artists, albums, etc.)
 * - Folder scanning via API
 * - Favorites vs. all tracks support
 * - Single unified loading and error state
 *
 * Usage:
 * ```tsx
 * const {
 *   // Data
 *   tracks,
 *   stats,
 *
 *   // State
 *   loading,
 *   hasMore,
 *   isLoadingMore,
 *   scanning,
 *   error,
 *
 *   // Methods
 *   fetchTracks,
 *   loadMore,
 *   handleScanFolder,
 *   refetchStats
 * } = useLibraryWithStats({ view: 'all' });
 * ```
 *
 * @see useLibraryData.ts (deprecated, use this instead)
 * @see useLibraryStats.ts (deprecated, use this instead)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useToast } from '@/components/shared/Toast';
import type { LibraryStats } from '@/types/domain';

// ============================================================================
// Types
// ============================================================================

export type { LibraryStats };

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

export interface UseLibraryWithStatsOptions {
  view: string;
  autoLoad?: boolean;
  includeStats?: boolean;
}

export interface UseLibraryWithStatsReturn {
  // Data
  tracks: Track[];
  stats: LibraryStats | null;

  // State - Unified
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  totalTracks: number;
  offset: number;
  isLoadingMore: boolean;
  scanning: boolean;
  statsLoading: boolean;

  // Methods - Data
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  loadMore: () => Promise<void>;
  handleScanFolder: () => Promise<void>;
  refetchStats: () => Promise<void>;

  // Utilities
  isElectron: () => boolean;
}

// ============================================================================
// Mock Data
// ============================================================================

const MOCK_TRACKS: Track[] = [
  {
    id: 1,
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    album: 'A Night at the Opera',
    duration: 355,
    quality: 0.95,
    isEnhanced: true,
    genre: 'Rock',
    year: 1975,
    albumArt: 'https://via.placeholder.com/300x300/1976d2/white?text=Queen'
  },
  {
    id: 2,
    title: 'Hotel California',
    artist: 'Eagles',
    album: 'Hotel California',
    duration: 391,
    quality: 0.88,
    isEnhanced: false,
    genre: 'Rock',
    year: 1976,
    albumArt: 'https://via.placeholder.com/300x300/d32f2f/white?text=Eagles'
  },
  {
    id: 3,
    title: 'Billie Jean',
    artist: 'Michael Jackson',
    album: 'Thriller',
    duration: 294,
    quality: 0.92,
    isEnhanced: true,
    genre: 'Pop',
    year: 1982,
    albumArt: 'https://via.placeholder.com/300x300/388e3c/white?text=MJ'
  },
  {
    id: 4,
    title: "Sweet Child O' Mine",
    artist: "Guns N' Roses",
    album: 'Appetite for Destruction',
    duration: 356,
    quality: 0.89,
    isEnhanced: false,
    genre: 'Rock',
    year: 1987,
    albumArt: 'https://via.placeholder.com/300x300/f57c00/white?text=GNR'
  }
];

// ============================================================================
// Hook Implementation
// ============================================================================

export const useLibraryWithStats = ({
  view,
  autoLoad = true,
  includeStats = true
}: UseLibraryWithStatsOptions): UseLibraryWithStatsReturn => {
  // Track Data State
  const [tracks, setTracks] = useState<Track[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [totalTracks, setTotalTracks] = useState(0);
  const [offset, setOffset] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [scanning, setScanning] = useState(false);

  // Statistics State
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(includeStats);

  // Prevent multiple simultaneous fetches (debounce protection)
  const fetchInProgressRef = useRef(false);

  const { success, error: toastError, info } = useToast();

  // ========================================================================
  // Utilities
  // ========================================================================

  const isElectron = useCallback(() => {
    return !!(window as any).electronAPI;
  }, []);

  const loadMockData = useCallback(() => {
    setTracks(MOCK_TRACKS);
    setHasMore(false);
    setTotalTracks(MOCK_TRACKS.length);
  }, []);

  // ========================================================================
  // Track Data Methods
  // ========================================================================

  const fetchTracks = useCallback(
    async (resetPagination = true) => {
      // Prevent multiple simultaneous fetches (anti-spam/debounce)
      if (fetchInProgressRef.current) {
        console.log('[useLibraryWithStats] Fetch already in progress, skipping');
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
        const currentOffset = resetPagination ? 0 : offset;

        const endpoint =
          view === 'favourites'
            ? `/api/library/tracks/favorites?limit=${limit}&offset=${currentOffset}`
            : `/api/library/tracks?limit=${limit}&offset=${currentOffset}`;

        const response = await fetch(endpoint);
        if (response.ok) {
          const data = await response.json();

          const transformedTracks = (data.tracks || []).map((track: any) => ({
            ...track,
            artist:
              Array.isArray(track.artists) && track.artists.length > 0
                ? track.artists[0]
                : track.artist || 'Unknown Artist',
            albumArt: track.album_art || track.albumArt
          }));

          setHasMore(data.has_more || false);
          setTotalTracks(data.total || 0);

          if (resetPagination) {
            setTracks(transformedTracks);
          } else {
            setTracks((prev) => [...prev, ...transformedTracks]);
          }

          console.log(
            'Loaded',
            data.tracks?.length || 0,
            view === 'favourites' ? 'favorite tracks' : 'tracks from library'
          );
          console.log(
            `Pagination: ${currentOffset + (data.tracks?.length || 0)}/${data.total || 0}, has_more: ${data.has_more}`
          );

          if (resetPagination && data.tracks && data.tracks.length > 0) {
            success(
              `Loaded ${data.tracks.length} of ${data.total} ${view === 'favourites' ? 'favorites' : 'tracks'}`
            );
          } else if (resetPagination && view === 'favourites') {
            info('No favorites yet. Click the heart icon on tracks to add them!');
          }
        } else {
          console.error('Failed to fetch tracks');
          setError('Failed to load library');
          toastError('Failed to load library');

          if (view !== 'favourites' && resetPagination) {
            loadMockData();
          }
        }
      } catch (err) {
        console.error('Error fetching tracks:', err);
        const errorMsg = 'Failed to connect to server';
        setError(errorMsg);
        toastError(errorMsg);

        if (view !== 'favourites') {
          loadMockData();
        }
      } finally {
        setLoading(false);
        fetchInProgressRef.current = false;
      }
    },
    // NOTE: Do NOT include 'offset' in dependencies - it's only used for loadMore (non-reset case)
    // fetchTracks is called with resetPagination=true from useEffect, which always uses currentOffset=0
    // Including offset would cause fetchTracks to be recreated every time offset changes, leading to infinite loops
    [view, success, toastError, info, loadMockData]
  );

  const loadMore = useCallback(async () => {
    // Check guards using refs and state getters to avoid dependency loop
    if (fetchInProgressRef.current) {
      console.log('[useLibraryWithStats] loadMore already in progress, skipping');
      return;
    }

    // NOTE: We can't use isLoadingMore or hasMore in dependencies because they change frequently
    // Instead, we check them here and use refs to guard against parallel calls
    // The state values are read here at callback invocation time
    fetchInProgressRef.current = true;
    setIsLoadingMore(true);

    try {
      const limit = 50;
      // Get current offset value using updater function pattern
      let newOffset = 0;
      setOffset((prevOffset) => {
        newOffset = prevOffset + limit;
        return newOffset;
      });

      // Wait for state update to complete
      await new Promise((resolve) => setTimeout(resolve, 0));

      const endpoint =
        view === 'favourites'
          ? `/api/library/tracks/favorites?limit=${limit}&offset=${newOffset}`
          : `/api/library/tracks?limit=${limit}&offset=${newOffset}`;

      const response = await fetch(endpoint);
      if (response.ok) {
        const data = await response.json();

        const transformedTracks = (data.tracks || []).map((track: any) => ({
          ...track,
          artist:
            Array.isArray(track.artists) && track.artists.length > 0
              ? track.artists[0]
              : track.artist || 'Unknown Artist',
          albumArt: track.album_art || track.albumArt
        }));

        setTracks((prev) => [...prev, ...transformedTracks]);
        setHasMore(data.has_more || false);
        setTotalTracks(data.total || 0);

        console.log(`Loaded more: ${newOffset + transformedTracks.length}/${data.total || 0}`);
      }
    } catch (err) {
      console.error('Error loading more tracks:', err);
    } finally {
      setIsLoadingMore(false);
      fetchInProgressRef.current = false;
    }
  }, [view]);

  const handleScanFolder = useCallback(async () => {
    let folderPath: string | undefined;

    if (isElectron()) {
      try {
        const result = await (window as any).electronAPI.selectFolder();
        if (result && result.length > 0) {
          folderPath = result[0];
        } else {
          return;
        }
      } catch (error) {
        console.error('Failed to open folder picker:', error);
        alert('❌ Failed to open folder picker');
        return;
      }
    } else {
      folderPath = prompt('Enter folder path to scan:\n(e.g., /home/user/Music)') || undefined;
      if (!folderPath) return;
    }

    setScanning(true);
    try {
      const response = await fetch('/api/library/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ directory: folderPath })
      });

      if (response.ok) {
        const result = await response.json();
        alert(`✅ Scan complete!\nAdded: ${result.files_added || 0} tracks`);
        await fetchTracks();
        // Refresh stats after scan
        if (includeStats) {
          await refetchStats();
        }
      } else {
        const errorData = await response.json();
        alert(`❌ Scan failed: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Scan error:', error);
      alert(`❌ Error scanning folder: ${error}`);
    } finally {
      setScanning(false);
    }
  }, [isElectron, fetchTracks, includeStats]);

  // ========================================================================
  // Statistics Methods
  // ========================================================================

  const refetchStats = useCallback(async () => {
    if (!includeStats) return;

    setStatsLoading(true);
    try {
      const response = await fetch('/api/library/stats');

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching library stats:', err);
      // Don't treat stats failure as fatal - still allow library view to work
    } finally {
      setStatsLoading(false);
    }
  }, [includeStats]);

  // ========================================================================
  // Effects
  // ========================================================================

  // Auto-load on mount or when view changes
  // NOTE: Only depend on view, autoLoad, and includeStats to avoid infinite loops
  // fetchTracks and refetchStats are functions that change frequently due to dependencies on toast functions
  useEffect(() => {
    console.log(`[useLibraryWithStats] useEffect triggered for view="${view}", autoLoad=${autoLoad}, includeStats=${includeStats}`);
    if (autoLoad) {
      console.log(`[useLibraryWithStats] Calling fetchTracks() for view="${view}"`);
      fetchTracks();
      if (includeStats) {
        console.log(`[useLibraryWithStats] Calling refetchStats()`);
        refetchStats();
      }
    }
    // Dependency array only includes view, autoLoad, includeStats to prevent re-render loops
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, autoLoad, includeStats]);

  // ========================================================================
  // Return
  // ========================================================================

  return {
    // Data
    tracks,
    stats,

    // State - Unified
    loading,
    error,
    hasMore,
    totalTracks,
    offset,
    isLoadingMore,
    scanning,
    statsLoading,

    // Methods - Data
    fetchTracks,
    loadMore,
    handleScanFolder,
    refetchStats,

    // Utilities
    isElectron
  };
};

export default useLibraryWithStats;
