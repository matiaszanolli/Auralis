/**
 * useAlbumGridPagination Hook
 *
 * Manages album data fetching and pagination logic
 */

import { useState, useRef } from 'react';

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
  artwork_path?: string;
}

export const useAlbumGridPagination = () => {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [totalAlbums, setTotalAlbums] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const isFetchingRef = useRef(false);

  const fetchAlbums = async (resetPagination = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    if (resetPagination) {
      setLoading(true);
      setOffset(0);
      setAlbums([]);
    } else {
      setIsLoadingMore(true);
    }

    setError(null);

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

      const response = await fetch(`/api/albums?limit=${limit}&offset=${currentOffset}`);
      if (!response.ok) {
        throw new Error('Failed to fetch albums');
      }

      const data = await response.json();

      setHasMore(data.has_more || false);
      setTotalAlbums(data.total || 0);

      if (resetPagination) {
        setAlbums(data.albums || []);
      } else {
        const newAlbums = data.albums || [];
        setAlbums(prev => {
          const existingIds = new Set(prev.map((a: Album) => a.id));
          return [...prev, ...newAlbums.filter((a: Album) => !existingIds.has(a.id))];
        });
      }
    } catch (err) {
      console.error('Error fetching albums:', err);
      setError(err instanceof Error ? err.message : 'Failed to load albums');
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
      isFetchingRef.current = false;
    }
  };

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    const limit = 50;
    const newOffset = offset + limit;
    setOffset(newOffset);
    await fetchAlbums(false);
  };

  return {
    albums,
    loading,
    error,
    offset,
    hasMore,
    totalAlbums,
    isLoadingMore,
    fetchAlbums,
    loadMore,
  };
};
