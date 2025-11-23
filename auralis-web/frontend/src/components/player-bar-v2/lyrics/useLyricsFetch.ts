import { useState, useEffect, useCallback } from 'react';

export interface LyricsData {
  lyrics: string | null;
  format: 'plain' | 'lrc' | null;
  loading: boolean;
}

/**
 * useLyricsFetch - Fetches lyrics for a track
 *
 * Handles:
 * - Fetching lyrics from backend
 * - Loading state management
 * - Format detection (plain text or LRC)
 */
export const useLyricsFetch = (trackId: number | null): LyricsData => {
  const [lyrics, setLyrics] = useState<string | null>(null);
  const [format, setFormat] = useState<'plain' | 'lrc' | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchLyrics = useCallback(async () => {
    if (!trackId) {
      setLyrics(null);
      setFormat(null);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/api/library/tracks/${trackId}/lyrics`);
      if (response.ok) {
        const data = await response.json();
        setLyrics(data.lyrics);
        setFormat(data.format);
      }
    } catch (error) {
      console.error('Failed to fetch lyrics:', error);
      setLyrics(null);
      setFormat(null);
    } finally {
      setLoading(false);
    }
  }, [trackId]);

  useEffect(() => {
    fetchLyrics();
  }, [trackId, fetchLyrics]);

  return {
    lyrics,
    format,
    loading,
  };
};
