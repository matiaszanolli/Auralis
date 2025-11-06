/**
 * Slider Primitive Component
 *
 * Slider for volume, progress, and parameter controls.
 *
 * Usage:
 *   <Slider value={50} onChange={handleChange} />
 *   <Slider value={75} min={0} max={100} variant="gradient" />
 *   <Slider value={30} size="sm" showValue />
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

import React from 'react';
import { styled } from '@mui/material/styles';
import MuiSlider, { SliderProps as MuiSliderProps } from '@mui/material/Slider';
import { tokens } from '../tokens';

export interface SliderProps extends Omit<MuiSliderProps, 'size' | 'color'> {
  /**
   * Visual variant
   */
  variant?: 'default' | 'gradient' | 'accent';

  /**
   * Size
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Show value label
   */
  showValue?: boolean;
}

const StyledSlider = styled(MuiSlider, {
  shouldForwardProp: (prop) =>
    !['variant', 'size'].includes(prop as string),
})<SliderProps>(({ variant = 'default', size = 'md' }) => {
  // Size styles
  const sizeStyles = {
    sm: {
      height: '4px',
      '& .MuiSlider-thumb': {
        width: '12px',
        height: '12px',
      },
    },
    md: {
      height: '6px',
      '& .MuiSlider-thumb': {
        width: '16px',
        height: '16px',
      },
    },
    lg: {
      height: '8px',
      '& .MuiSlider-thumb': {
        width: '20px',
        height: '20px',
      },
    },
  };

  // Variant styles
  const variantStyles = {
    default: {
      color: tokens.colors.text.secondary,

      '& .MuiSlider-track': {
        background: tokens.colors.text.secondary,
        border: 'none',
      },

      '& .MuiSlider-thumb': {
        background: tokens.colors.text.primary,
        boxShadow: tokens.shadows.md,

        '&:hover, &.Mui-focusVisible': {
          boxShadow: `0 0 0 8px rgba(139, 146, 176, 0.16)`,
        },
      },

      '& .MuiSlider-rail': {
        background: tokens.colors.bg.elevated,
        opacity: 1,
      },
    },

    gradient: {
      '& .MuiSlider-track': {
        background: tokens.gradients.aurora,
        border: 'none',
      },

      '& .MuiSlider-thumb': {
        background: tokens.colors.text.primary,
        boxShadow: tokens.shadows.glow,

        '&:hover, &.Mui-focusVisible': {
          boxShadow: tokens.shadows.glowStrong,
        },
      },

      '& .MuiSlider-rail': {
        background: tokens.colors.bg.elevated,
        opacity: 1,
      },
    },

    accent: {
      color: tokens.colors.accent.primary,

      '& .MuiSlider-track': {
        background: tokens.colors.accent.primary,
        border: 'none',
      },

      '& .MuiSlider-thumb': {
        background: tokens.colors.accent.primary,
        boxShadow: tokens.shadows.md,

        '&:hover, &.Mui-focusVisible': {
          boxShadow: `0 0 0 8px rgba(102, 126, 234, 0.16)`,
        },
      },

      '& .MuiSlider-rail': {
        background: tokens.colors.bg.elevated,
        opacity: 1,
      },
    },
  };

  return {
    ...sizeStyles[size],
    ...variantStyles[variant],
    borderRadius: tokens.borderRadius.full,

    '& .MuiSlider-thumb': {
      transition: tokens.transitions.all,

      '&:hover': {
        transform: 'scale(1.2)',
      },

      '&:active': {
        transform: 'scale(1.1)',
      },
    },

    '& .MuiSlider-valueLabel': {
      background: tokens.colors.bg.elevated,
      borderRadius: tokens.borderRadius.sm,
      fontSize: tokens.typography.fontSize.xs,
      padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
      color: tokens.colors.text.primary,
    },
  };
});

export const Slider: React.FC<SliderProps> = ({
  variant = 'default',
  size = 'md',
  showValue = false,
  ...props
}) => {
  return (
    <StyledSlider
      variant={variant}
      size={size}
      valueLabelDisplay={showValue ? 'auto' : 'off'}
      {...props}
    />
  );
};

export default Slider;
