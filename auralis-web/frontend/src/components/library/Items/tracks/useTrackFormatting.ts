import { useCallback } from 'react';

/**
 * useTrackFormatting - Formatting utilities for track display
 *
 * Handles:
 * - Duration formatting (mm:ss)
 * - String conversion for styled components
 */
export const useTrackFormatting = () => {
  const formatDuration = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return {
    formatDuration,
  };
};
