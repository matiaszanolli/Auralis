import { useCallback } from 'react';

export interface UseTrackRowHandlersProps {
  trackId: number;
  isCurrent: boolean;
  onPlay: (trackId: number) => void;
  /**
   * Toggles the shared playback session (the transport bar's handlePlayPause,
   * #5514). Called for ANY click on the current track's row — playing pauses,
   * paused resumes from the pause position instead of restarting from 0.
   */
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
  onPlay,
  onPause,
  onDoubleClick,
}: UseTrackRowHandlersProps) => {
  const toggleOrPlay = useCallback(() => {
    if (isCurrent && onPause) {
      onPause();
    } else {
      onPlay(trackId);
    }
  }, [trackId, isCurrent, onPlay, onPause]);

  const handlePlayClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      toggleOrPlay();
    },
    [toggleOrPlay]
  );

  const handleRowClick = useCallback(() => {
    toggleOrPlay();
  }, [toggleOrPlay]);

  const handleRowDoubleClick = useCallback(() => {
    onDoubleClick?.(trackId);
  }, [trackId, onDoubleClick]);

  return {
    handlePlayClick,
    handleRowClick,
    handleRowDoubleClick,
  };
};
