import React from 'react';
import { Slider, SliderProps, styled } from '@mui/material';
import { gradients, colors } from '../../theme/auralisTheme';

interface GradientSliderProps extends Omit<SliderProps, 'color'> {
  gradient?: string;
}

const StyledGradientSlider = styled(Slider)<{ gradientbg?: string }>(({ gradientbg }) => ({
  height: 6,
  padding: '13px 0',

  '& .MuiSlider-track': {
    height: 6,
    borderRadius: 3,
    background: gradientbg || gradients.aurora,
    border: 'none',
    transition: 'all 0.3s ease',
  },

  '& .MuiSlider-rail': {
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.background.surface,
    opacity: 1,
  },

  '& .MuiSlider-thumb': {
    width: 20,
    height: 20,
    backgroundColor: '#ffffff',
    border: '2px solid currentColor',
    borderColor: '#ffffff',
    boxShadow: '0 3px 8px rgba(0, 0, 0, 0.3)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',

    '&:hover, &.Mui-focusVisible': {
      boxShadow: '0 0 0 8px rgba(102, 126, 234, 0.16)',
      transform: 'scale(1.1)',
    },

    '&.Mui-active': {
      boxShadow: '0 0 0 12px rgba(102, 126, 234, 0.24)',
      transform: 'scale(1.15)',
    },

    '&::before': {
      content: '""',
      position: 'absolute',
      width: '100%',
      height: '100%',
      borderRadius: '50%',
      background: gradientbg || gradients.aurora,
      opacity: 0,
      transition: 'opacity 0.3s ease',
    },

    '&:hover::before': {
      opacity: 0.3,
    },
  },

  '&.Mui-disabled': {
    '& .MuiSlider-track': {
      background: colors.text.disabled,
    },
    '& .MuiSlider-thumb': {
      backgroundColor: colors.text.disabled,
      borderColor: colors.text.disabled,
    },
  },
}));

export const GradientSlider: React.FC<GradientSliderProps> = ({
  gradient,
  ...props
}) => {
  return (
    <StyledGradientSlider
      gradientbg={gradient}
      {...props}
    />
  );
};

export default GradientSlider;
