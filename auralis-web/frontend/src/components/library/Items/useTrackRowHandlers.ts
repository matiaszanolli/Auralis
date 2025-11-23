import { useCallback } from 'react';

export interface UseTrackRowHandlersProps {
  trackId: number;
  isCurrent: boolean;
  isPlaying: boolean;
  onPlay: (trackId: number) => void;
  onPause?: () => void;
  onDoubleClick?: (trackId: number) => void;
}

/**
 * useTrackRowHandlers - Encapsulates track row interaction handlers
 *
 * Handles:
 * - Play/pause button clicks
 * - Row selection and double-click
 * - Context menu positioning
 */
export const useTrackRowHandlers = ({
  trackId,
  isCurrent,
  isPlaying,
  onPlay,
  onPause,
  onDoubleClick,
}: UseTrackRowHandlersProps) => {
  const handlePlayClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (isCurrent && isPlaying && onPause) {
        onPause();
      } else {
        onPlay(trackId);
      }
    },
    [trackId, isCurrent, isPlaying, onPlay, onPause]
  );

  const handleRowClick = useCallback(() => {
    onPlay(trackId);
  }, [trackId, onPlay]);

  const handleRowDoubleClick = useCallback(() => {
    onDoubleClick?.(trackId);
  }, [trackId, onDoubleClick]);

  return {
    handlePlayClick,
    handleRowClick,
    handleRowDoubleClick,
  };
};
