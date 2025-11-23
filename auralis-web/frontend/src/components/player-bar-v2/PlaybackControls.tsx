/**
 * PlaybackControls - Play, pause, previous, next buttons
 *
 * Features:
 * - Animated play/pause icon transition
 * - Hover states with scale effect
 * - Large touch targets (48x48px)
 * - Design token styling
 *
 * Styled components extracted to PlaybackControls.styles.ts
 * PlayPauseIcon extracted to separate component
 */

import React from 'react';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import { PlayPauseIcon } from './PlayPauseIcon';
import { ControlsContainer, ControlButton, PlayPauseButton } from './PlaybackControls.styles';

interface PlaybackControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onPrevious: () => void;
  onNext: () => void;
  queueLength?: number;
  queueIndex?: number;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = React.memo(({
  isPlaying,
  onPlayPause,
  onPrevious,
  onNext,
  queueLength = 0,
  queueIndex = 0,
}) => {
  // Determine if navigation buttons should be disabled
  const canGoPrevious = queueLength > 0 && queueIndex > 0;
  const canGoNext = queueLength > 0 && queueIndex < queueLength - 1;

  return (
    <ControlsContainer>
      {/* Previous track */}
      <ControlButton
        onClick={onPrevious}
        disabled={!canGoPrevious}
        aria-label="Previous track"
        title={canGoPrevious ? "Previous track (Ctrl+Left)" : "No previous track"}
      >
        <SkipPreviousIcon />
      </ControlButton>

      {/* Play/Pause */}
      <PlayPauseButton
        onClick={onPlayPause}
        aria-label={isPlaying ? 'Pause' : 'Play'}
        title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
      >
        <PlayPauseIcon isPlaying={isPlaying} />
      </PlayPauseButton>

      {/* Next track */}
      <ControlButton
        onClick={onNext}
        disabled={!canGoNext}
        aria-label="Next track"
        title={canGoNext ? "Next track (Ctrl+Right)" : "No next track"}
      >
        <SkipNextIcon />
      </ControlButton>
    </ControlsContainer>
  );
});

PlaybackControls.displayName = 'PlaybackControls';
