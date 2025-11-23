/**
 * VolumeControl Styled Components
 *
 * Centralized styling for volume slider and button.
 */

import { Box, IconButton, Slider, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const VolumeContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  minWidth: '150px',
});

export const VolumeButton = styled(IconButton)({
  color: tokens.colors.text.primary,
  transition: tokens.transitions.all,

  '&:hover': {
    transform: 'scale(1.1)',
    backgroundColor: tokens.colors.bg.elevated,
  },

  '& .MuiSvgIcon-root': {
    fontSize: '22px',
  },
});

export const VolumeSlider = styled(Slider)({
  color: tokens.colors.accent.primary,
  height: 4,
  width: '100px',

  '& .MuiSlider-track': {
    border: 'none',
    background: tokens.gradients.auroraSoft,
    height: 4,
  },

  '& .MuiSlider-rail': {
    backgroundColor: tokens.colors.bg.elevated,
    opacity: 1,
    height: 4,
  },

  '& .MuiSlider-thumb': {
    height: 12,
    width: 12,
    backgroundColor: tokens.colors.text.primary,
    border: `2px solid ${tokens.colors.accent.primary}`,
    transition: tokens.transitions.all,

    '&:hover, &.Mui-focusVisible': {
      boxShadow: tokens.shadows.glow,
      transform: 'scale(1.3)',
    },

    '&.Mui-active': {
      boxShadow: tokens.shadows.glowStrong,
    },
  },
});
