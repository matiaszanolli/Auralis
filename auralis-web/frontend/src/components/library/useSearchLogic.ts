import { useState, useEffect, useCallback } from 'react';

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
 * - Multi-type simultaneous API calls
 * - Filters and limits results to 5 per type
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
    setLoading(true);
    const allResults: SearchResult[] = [];

    try {
      // Search tracks
      const tracksResponse = await fetch(
        `/api/library/tracks?limit=100`
      );
      if (tracksResponse.ok) {
        const tracksData = await tracksResponse.json();
        const matchingTracks = tracksData.tracks
          .filter((track: any) =>
            track.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            track.artist.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((track: any) => ({
            type: 'track' as const,
            id: track.id,
            title: track.title,
            subtitle: `${track.artist} • ${track.album}`,
            albumId: track.album_id
          }));
        allResults.push(...matchingTracks);
      }

      // Search albums
      const albumsResponse = await fetch('/api/library/albums');
      if (albumsResponse.ok) {
        const albumsData = await albumsResponse.json();
        const matchingAlbums = albumsData.albums
          .filter((album: any) =>
            album.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            album.artist.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((album: any) => ({
            type: 'album' as const,
            id: album.id,
            title: album.title,
            subtitle: album.artist,
            albumId: album.id
          }));
        allResults.push(...matchingAlbums);
      }

      // Search artists
      const artistsResponse = await fetch('/api/library/artists');
      if (artistsResponse.ok) {
        const artistsData = await artistsResponse.json();
        const matchingArtists = artistsData.artists
          .filter((artist: any) =>
            artist.name.toLowerCase().includes(searchQuery.toLowerCase())
          )
          .slice(0, 5)
          .map((artist: any) => ({
            type: 'artist' as const,
            id: artist.id,
            title: artist.name,
            subtitle: `${artist.album_count || 0} albums • ${artist.track_count || 0} tracks`
          }));
        allResults.push(...matchingArtists);
      }

      setResults(allResults);
      setShowResults(true);
    } catch (error) {
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
    artists: results.filter(r => r.type === 'artist')
  };

  return {
    query,
    setQuery,
    results,
    loading,
    showResults,
    handleResultClick,
    handleClear,
    groupedResults
  };
};

export default useSearchLogic;
