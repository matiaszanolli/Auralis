import { useState, useEffect, useCallback, useRef } from 'react';
import { get } from '@/utils/apiRequest';
import { ENDPOINTS } from '@/config/api';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface UseSearchLogicReturn {
  query: string;
  setQuery: (query: string) => void;
  results: SearchResult[];
  loading: boolean;
  showResults: boolean;
  handleResultClick: (result: SearchResult) => void;
  handleClear: () => void;
  groupedResults: {
    tracks: SearchResult[];
    albums: SearchResult[];
    artists: SearchResult[];
  };
}

/**
 * useSearchLogic - Encapsulates global search logic
 *
 * Manages:
 * - Debounced search (300ms) across tracks, albums, artists
 * - Query state and results
 * - Result grouping by type
 * - Loading and visibility states
 *
 * Features:
 * - Server-side search via ?search= query param (5 results per type)
 * - Parallel API calls via Promise.all
 * - AbortController to cancel stale in-flight requests
 * - Debounced query to prevent excessive API calls
 * - Result grouping for UI organization
 */
export const useSearchLogic = (
  onResultClick?: (result: SearchResult) => void
): UseSearchLogicReturn => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      setShowResults(false);
      return;
    }

    const timeoutId = setTimeout(() => {
      performSearch(query);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [query]);

  const performSearch = async (searchQuery: string) => {
    // Cancel any in-flight request before starting a new one
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setLoading(true);

    try {
      const encoded = encodeURIComponent(searchQuery);
      const [tracksData, albumsData, artistsData] = await Promise.all([
        get(`${ENDPOINTS.LIBRARY_TRACKS}?search=${encoded}&limit=5`, { signal: controller.signal }),
        get(`${ENDPOINTS.LIBRARY_ALBUMS}?search=${encoded}&limit=5`, { signal: controller.signal }),
        get(`${ENDPOINTS.LIBRARY_ARTISTS}?search=${encoded}&limit=5`, { signal: controller.signal }),
      ]);

      // Ignore results from a cancelled request
      if (controller.signal.aborted) return;

      const tracks: SearchResult[] = (tracksData.tracks ?? []).map((track: any) => ({
        type: 'track' as const,
        id: track.id,
        title: track.title,
        subtitle: `${track.artist} • ${track.album}`,
        albumId: track.album_id,
      }));

      const albums: SearchResult[] = (albumsData.albums ?? []).map((album: any) => ({
        type: 'album' as const,
        id: album.id,
        title: album.title,
        subtitle: album.artist,
        albumId: album.id,
      }));

      const artists: SearchResult[] = (artistsData.artists ?? []).map((artist: any) => ({
        type: 'artist' as const,
        id: artist.id,
        title: artist.name,
        subtitle: `${artist.album_count || 0} albums • ${artist.track_count || 0} tracks`,
      }));

      setResults([...tracks, ...albums, ...artists]);
      setShowResults(true);
    } catch (error) {
      if (controller.signal.aborted) return;
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResultClick = useCallback((result: SearchResult) => {
    if (onResultClick) {
      onResultClick(result);
    }
    setQuery('');
    setShowResults(false);
  }, [onResultClick]);

  const handleClear = useCallback(() => {
    setQuery('');
    setResults([]);
    setShowResults(false);
  }, []);

  // Group results by type
  const groupedResults = {
    tracks: results.filter(r => r.type === 'track'),
    albums: results.filter(r => r.type === 'album'),
    artists: results.filter(r => r.type === 'artist'),
  };

  return {
    query,
    setQuery,
    results,
    loading,
    showResults,
    handleResultClick,
    handleClear,
    groupedResults,
  };
};

export default useSearchLogic;
