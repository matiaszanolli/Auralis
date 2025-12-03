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
 * - Mock data fallback for development
 */

import { useState, useEffect, useCallback } from 'react';
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

  // Methods
  fetchTracks: (resetPagination?: boolean) => Promise<void>;
  loadMore: () => Promise<void>;
  handleScanFolder: () => Promise<void>;
  isElectron: () => boolean;
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
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [scanning, setScanning] = useState(false);

  const { success, error, info } = useToast();

  // Check if running in Electron
  const isElectron = useCallback(() => {
    return !!(window as any).electronAPI;
  }, []);

  // Load mock data as fallback
  const loadMockData = useCallback(() => {
    const mockTracks: Track[] = [
      {
        id: 1,
        title: "Bohemian Rhapsody",
        artist: "Queen",
        album: "A Night at the Opera",
        duration: 355,
        quality: 0.95,
        isEnhanced: true,
        genre: "Rock",
        year: 1975,
        albumArt: "https://via.placeholder.com/300x300/1976d2/white?text=Queen"
      },
      {
        id: 2,
        title: "Hotel California",
        artist: "Eagles",
        album: "Hotel California",
        duration: 391,
        quality: 0.88,
        isEnhanced: false,
        genre: "Rock",
        year: 1976,
        albumArt: "https://via.placeholder.com/300x300/d32f2f/white?text=Eagles"
      },
      {
        id: 3,
        title: "Billie Jean",
        artist: "Michael Jackson",
        album: "Thriller",
        duration: 294,
        quality: 0.92,
        isEnhanced: true,
        genre: "Pop",
        year: 1982,
        albumArt: "https://via.placeholder.com/300x300/388e3c/white?text=MJ"
      },
      {
        id: 4,
        title: "Sweet Child O' Mine",
        artist: "Guns N' Roses",
        album: "Appetite for Destruction",
        duration: 356,
        quality: 0.89,
        isEnhanced: false,
        genre: "Rock",
        year: 1987,
        albumArt: "https://via.placeholder.com/300x300/f57c00/white?text=GNR"
      }
    ];

    setTracks(mockTracks);
    setHasMore(false);
    setTotalTracks(mockTracks.length);
  }, []);

  // Fetch tracks from API with pagination
  const fetchTracks = useCallback(async (resetPagination = true) => {
    setLoading(true);
    if (resetPagination) {
      setOffset(0);
      setTracks([]);
    }

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

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
          albumArt: track.album_art || track.albumArt, // Map album_art from backend to albumArt
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
        error('Failed to load library');
        // Fall back to mock data only for regular view
        if (view !== 'favourites' && resetPagination) {
          loadMockData();
        }
      }
    } catch (err) {
      console.error('Error fetching tracks:', err);
      error('Failed to connect to server');
      // Fall back to mock data only for regular view
      if (view !== 'favourites') {
        loadMockData();
      }
    } finally {
      setLoading(false);
    }
  }, [view, offset, success, error, info, loadMockData]);

  // Load more tracks (for infinite scroll)
  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    setIsLoadingMore(true);
    try {
      const limit = 50;
      const newOffset = offset + limit;
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
          albumArt: track.album_art || track.albumArt, // Map album_art from backend to albumArt
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
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, hasMore, offset, view]);

  // Handle folder scan
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
      } catch (error) {
        console.error('Failed to open folder picker:', error);
        alert('❌ Failed to open folder picker');
        return;
      }
    } else {
      // Fallback to prompt in web browser
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
        // Refresh the library
        await fetchTracks();
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
  }, [isElectron, fetchTracks]);

  // Auto-load on mount or when view changes
  useEffect(() => {
    if (autoLoad) {
      fetchTracks();
    }
  }, [view]); // Only depend on view, not fetchTracks (to avoid infinite loop)

  return {
    // State
    tracks,
    loading,
    hasMore,
    totalTracks,
    offset,
    isLoadingMore,
    scanning,

    // Methods
    fetchTracks,
    loadMore,
    handleScanFolder,
    isElectron
  };
};

export default useLibraryData;
