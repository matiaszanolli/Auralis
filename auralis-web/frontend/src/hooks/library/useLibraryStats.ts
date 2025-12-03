import { useState, useEffect } from 'react';

interface LibraryStats {
  total_tracks: number;
  total_artists: number;
  total_albums: number;
  total_genres: number;
  total_playlists: number;
  total_duration: number;
  total_duration_formatted: string;
  total_filesize: number;
  total_filesize_gb: number;
  avg_dr_rating?: number;
  avg_lufs?: number;
  avg_mastering_quality?: number;
}

interface UseLibraryStatsReturn {
  stats: LibraryStats | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

export const useLibraryStats = (): UseLibraryStatsReturn => {
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch('/api/library/stats');

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch stats';
      setError(errorMessage);
      console.error('Error fetching library stats:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return { stats, isLoading, error, refetch: fetchStats };
};