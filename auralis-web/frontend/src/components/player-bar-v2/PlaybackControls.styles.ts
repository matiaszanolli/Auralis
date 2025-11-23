/**
 * PlaybackControls Styled Components
 *
 * Centralized styling for playback control buttons.
 */

import { Box, IconButton, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const ControlsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
});

export const ControlButton = styled(IconButton)({
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

export const PlayPauseButton = styled(IconButton)({
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
