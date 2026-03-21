/**
 * useArtistDetailsData Hook
 *
 * Manages artist data fetching and state
 */

import { useState, useEffect } from 'react';
import type { Artist as DomainArtist, DetailTrack } from '@/types/domain';
import type { ArtistDetailApiResponse } from '@/api/transformers/types';
import { transformArtistDetail } from '@/api/transformers/artistTransformer';

export interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

export interface Artist extends DomainArtist {
  albums?: Album[];
  tracks?: DetailTrack[];
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

      const data: ArtistDetailApiResponse = await response.json();
      const base = transformArtistDetail(data);

      const artistData: Artist = {
        ...base,
        albums: (data.albums || []).map((a) => ({
          id: a.id,
          title: a.title,
          year: a.year ?? undefined,
          track_count: a.track_count,
          total_duration: a.total_duration ?? 0,
        })),
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
