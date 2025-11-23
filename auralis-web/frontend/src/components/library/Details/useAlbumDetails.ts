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

export interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

export interface Album {
  id: number;
  title: string;
  artist: string;
  artist_name?: string;
  year?: number;
  genre?: string;
  track_count: number;
  total_duration: number;
  tracks?: Track[];
}

export const useAlbumDetails = (albumId: number) => {
  const [album, setAlbum] = useState<Album | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);
  const [savingFavorite, setSavingFavorite] = useState(false);

  useEffect(() => {
    fetchAlbumDetails();
  }, [albumId]);

  const fetchAlbumDetails = async () => {
    setLoading(true);
    setError(null);

    try {
      // Use new REST API endpoint for album tracks
      const response = await fetch(`/api/albums/${albumId}/tracks`);
      if (!response.ok) {
        throw new Error('Failed to fetch album details');
      }

      const data = await response.json();

      // Transform API response to match Album interface
      const albumData: Album = {
        id: data.album_id,
        title: data.album_title,
        artist: data.artist,
        artist_name: data.artist,
        year: data.year,
        track_count: data.total_tracks,
        total_duration: data.tracks?.reduce((sum: number, t: Track) => sum + (t.duration || 0), 0) || 0,
        tracks: data.tracks || []
      };

      setAlbum(albumData);
    } catch (err) {
      console.error('Error fetching album details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load album details');
    } finally {
      setLoading(false);
    }
  };

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
