/**
 * useAlbumDetails Hook
 *
 * Manages album data fetching and state:
 * - Fetch album details from API
 * - Handle loading/error states
 * - Format album metadata
 * - Support for favorite toggling
 */

import { useState, useEffect } from 'react';
import type { DetailTrack } from '@/types/domain';

export interface Album {
  id: number;
  title: string;
  artist: string;
  artist_name?: string;
  year?: number;
  genre?: string;
  track_count: number;
  total_duration: number;
  tracks?: DetailTrack[];
}

export const useAlbumDetails = (albumId: number) => {
  const [album, setAlbum] = useState<Album | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);

  // #3601: AbortController on the fetch so we don't setState on a dead
  // component if the user navigates away mid-request, and so the in-flight
  // request itself is cancelled rather than running to completion uselessly.
  useEffect(() => {
    const controller = new AbortController();
    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/albums/${albumId}/tracks`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error('Failed to fetch album details');
        }
        const data = await response.json();
        if (controller.signal.aborted) return;

        const albumData: Album = {
          id: data.album_id,
          title: data.album_title,
          artist: data.artist,
          artist_name: data.artist,
          year: data.year,
          track_count: data.total_tracks,
          total_duration:
            data.tracks?.reduce(
              (sum: number, t: DetailTrack) => sum + (t.duration || 0),
              0
            ) || 0,
          tracks: (data.tracks || []).map((t: DetailTrack) => ({
            id: t.id,
            title: t.title ?? '',
            artist: t.artist ?? '',
            album: t.album ?? '',
            duration: t.duration ?? 0,
            filepath: t.filepath ?? '',
            artworkUrl: t.artworkUrl ?? null,
            genre: t.genre ?? null,
            year: t.year ?? null,
            trackNumber: t.trackNumber ?? null,
            discNumber: t.discNumber ?? null,
            albumId: t.albumId ?? null,
            favorite: t.favorite ?? undefined,
          })),
        };
        setAlbum(albumData);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('Error fetching album details:', err);
        setError(err instanceof Error ? err.message : 'Failed to load album details');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    run();
    return () => controller.abort();
  }, [albumId]);

  const toggleFavorite = async () => {
    setSavingFavorite(true);
    try {
      // Use first track's ID to toggle favorite (albums don't have direct favorite endpoints)
      const trackId = album?.tracks?.[0]?.id;
      if (!trackId) {
        setError('Cannot favorite album: no tracks available');
        return;
      }

      const response = await fetch(`/api/library/tracks/${trackId}/favorite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to update favorite status');
      }

      setIsFavorite(!isFavorite);
    } catch (err) {
      console.error('Error toggling favorite:', err);
      setError(err instanceof Error ? err.message : 'Failed to update favorite status');
    } finally {
      setSavingFavorite(false);
    }
  };

  return {
    album,
    loading,
    error,
    isFavorite,
    savingFavorite,
    toggleFavorite,
    setError,
  };
};
