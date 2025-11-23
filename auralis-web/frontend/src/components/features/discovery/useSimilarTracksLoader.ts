import { useState, useEffect, useCallback } from 'react';
import similarityService, { SimilarTrack } from '@/services/similarityService';

interface UseSimilarTracksLoaderProps {
  trackId: number | null;
  limit: number;
  useGraph: boolean;
}

export const useSimilarTracksLoader = ({
  trackId,
  limit,
  useGraph,
}: UseSimilarTracksLoaderProps) => {
  const [similarTracks, setSimilarTracks] = useState<SimilarTrack[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSimilarTracks = useCallback(async () => {
    if (!trackId) {
      setSimilarTracks([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const tracks = await similarityService.findSimilar(trackId, limit, useGraph);
      setSimilarTracks(tracks);
    } catch (err) {
      console.error('Failed to load similar tracks:', err);
      setError(err instanceof Error ? err.message : 'Failed to load similar tracks');
      setSimilarTracks([]);
    } finally {
      setLoading(false);
    }
  }, [trackId, limit, useGraph]);

  useEffect(() => {
    loadSimilarTracks();
  }, [trackId, limit, useGraph, loadSimilarTracks]);

  return { similarTracks, loading, error };
};
