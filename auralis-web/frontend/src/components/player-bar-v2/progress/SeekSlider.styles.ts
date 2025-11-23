/**
 * SeekSlider Styled Components
 */

import { Box, Slider, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

export const SliderContainer = styled(Box)({
  flex: 1,
  position: 'relative',
});

export const StyledSlider = styled(Slider)({
  color: tokens.colors.accent.primary,
  height: 6,
  padding: '8px 0',

  '& .MuiSlider-track': {
    border: 'none',
    background: tokens.gradients.aurora,
    height: 6,
  },

  '& .MuiSlider-rail': {
    backgroundColor: tokens.colors.bg.elevated,
    opacity: 1,
    height: 6,
  },

  '& .MuiSlider-thumb': {
    height: 16,
    width: 16,
    backgroundColor: tokens.colors.text.primary,
    border: `2px solid ${tokens.colors.accent.primary}`,
    boxShadow: tokens.shadows.glow,
    transition: tokens.transitions.all,

    '&:hover, &.Mui-focusVisible': {
      boxShadow: tokens.shadows.glowStrong,
      transform: 'scale(1.2)',
    },

    '&.Mui-active': {
      boxShadow: tokens.shadows.glowStrong,
    },
  },

  '& .MuiSlider-valueLabel': {
    fontFamily: tokens.typography.fontFamily.mono,
    fontSize: tokens.typography.fontSize.xs,
    background: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },
});
