/**
 * PlaybackControls - Play, pause, previous, next buttons
 *
 * Features:
 * - Animated play/pause icon transition
 * - Hover states with scale effect
 * - Large touch targets (48x48px)
 * - Design token styling
 */

import React from 'react';
import { Box, IconButton, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import SkipNextIcon from '@mui/icons-material/SkipNext';

interface PlaybackControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onPrevious: () => void;
  onNext: () => void;
  queueLength?: number;
  queueIndex?: number;
}

const ControlsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
});

const ControlButton = styled(IconButton)({
  width: '40px',
  height: '40px',
  color: tokens.colors.text.primary,
  transition: tokens.transitions.all,

  '&:hover:not(:disabled)': {
    transform: 'scale(1.1)',
    backgroundColor: tokens.colors.bg.elevated,
  },

  '&:active:not(:disabled)': {
    transform: 'scale(0.95)',
  },

  '&:disabled': {
    color: tokens.colors.text.tertiary,
    opacity: 0.5,
    cursor: 'not-allowed',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '24px',
  },
});

const PlayPauseButton = styled(IconButton)({
  width: '48px',
  height: '48px',
  background: tokens.gradients.aurora,
  color: tokens.colors.text.primary,
  boxShadow: tokens.shadows.glow,
  transition: tokens.transitions.all,

  '&:hover': {
    transform: 'scale(1.15)',
    boxShadow: tokens.shadows.glowStrong,
    background: tokens.gradients.aurora,
  },

  '&:active': {
    transform: 'scale(1.0)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '28px',
    transition: tokens.transitions.transform,
  },
});

/**
 * Animated play/pause icon that smoothly transitions
 */
const PlayPauseIcon: React.FC<{ isPlaying: boolean }> = ({ isPlaying }) => {
  return (
    <Box
      sx={{
        position: 'relative',
        width: '28px',
        height: '28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          transition: tokens.transitions.all,
          opacity: isPlaying ? 0 : 1,
          transform: isPlaying ? 'scale(0.5) rotate(90deg)' : 'scale(1) rotate(0deg)',
        }}
      >
        <PlayArrowIcon fontSize="inherit" />
      </Box>
      <Box
        sx={{
          position: 'absolute',
          transition: tokens.transitions.all,
          opacity: isPlaying ? 1 : 0,
          transform: isPlaying ? 'scale(1) rotate(0deg)' : 'scale(0.5) rotate(-90deg)',
        }}
      >
        <PauseIcon fontSize="inherit" />
      </Box>
    </Box>
  );
};

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
