/**
 * useSeekControls - Hook for managing seek slider state and event handlers
 *
 * Handles:
 * - Seek preview while dragging
 * - Seek start/end states
 * - Display time calculation (preview vs current)
 */

import { useState, useCallback } from 'react';

interface UseSeekControlsProps {
  onSeek: (time: number) => void;
}

export const useSeekControls = ({ onSeek }: UseSeekControlsProps) => {
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekPreview, setSeekPreview] = useState<number | null>(null);

  // Handle seek start
  const handleSeekStart = useCallback(() => {
    setIsSeeking(true);
  }, []);

  // Handle seek change (preview while dragging)
  const handleSeekChange = useCallback((event: Event, value: number | number[]) => {
    const time = Array.isArray(value) ? value[0] : value;
    setSeekPreview(time);
  }, []);

  // Handle seek end (commit the seek)
  const handleSeekEnd = useCallback(
    (event: Event | React.SyntheticEvent, value: number | number[]) => {
      const time = Array.isArray(value) ? value[0] : value;
      setIsSeeking(false);
      setSeekPreview(null);
      onSeek(time);
    },
    [onSeek]
  );

  return {
    handleSeekStart,
    handleSeekChange,
    handleSeekEnd,
    seekPreview,
  };
};

export default useSeekControls;
