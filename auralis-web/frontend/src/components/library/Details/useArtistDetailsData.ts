/**
 * useArtistDetailsData Hook
 *
 * Manages artist data fetching and state
 */

import { useState, useEffect } from 'react';
import type { Artist as DomainArtist } from '@/types/domain';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album?: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

export interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

export interface Artist extends DomainArtist {
  albums?: Album[];
  tracks?: Track[];
}

export const useArtistDetailsData = (artistId: number) => {
  const [artist, setArtist] = useState<Artist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchArtistDetails = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/artists/${artistId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch artist details');
      }

      const data = await response.json();

      const artistData: Artist = {
        id: data.artist_id,
        name: data.artist_name,
        albumCount: data.total_albums ?? 0,
        trackCount: data.total_tracks ?? 0,
        albums: data.albums || [],
        tracks: [],
      };

      setArtist(artistData);
    } catch (err) {
      console.error('Error fetching artist details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load artist details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArtistDetails();
  }, [artistId]);

  return {
    artist,
    loading,
    error,
  };
};
