/**
 * PlayPauseIcon - Animated play/pause icon transition
 *
 * Smoothly transitions between play and pause icons with rotation.
 */

import React from 'react';
import { Box } from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import { tokens } from '@/design-system/tokens';

interface PlayPauseIconProps {
  isPlaying: boolean;
}

export const PlayPauseIcon: React.FC<PlayPauseIconProps> = ({ isPlaying }) => {
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
