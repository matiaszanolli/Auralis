/**
 * useDurationFormatter - Custom hook for formatting duration to MM:SS format
 */

import { useCallback } from 'react';

export const useDurationFormatter = () => {
  const formatDuration = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return { formatDuration };
};

export default useDurationFormatter;
