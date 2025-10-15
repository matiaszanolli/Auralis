import React from 'react';
import { Button, ButtonProps, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

interface GradientButtonProps extends Omit<ButtonProps, 'variant'> {
  gradient?: string;
}

const StyledGradientButton = styled(Button)<{ gradientbg?: string }>(({ gradientbg }) => ({
  background: gradientbg || gradients.aurora,
  color: '#ffffff',
  fontWeight: 600,
  border: 'none',
  padding: '12px 32px',
  borderRadius: '8px',
  transition: 'all 0.3s ease',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',

  '&:hover': {
    background: gradientbg || gradients.aurora,
    filter: 'brightness(1.2)',
    transform: 'translateY(-2px)',
    boxShadow: '0 6px 20px rgba(102, 126, 234, 0.4)',
  },

  '&:active': {
    transform: 'translateY(0)',
    boxShadow: '0 2px 8px rgba(102, 126, 234, 0.3)',
  },

  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: '-100%',
    width: '100%',
    height: '100%',
    background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
    transition: 'left 0.5s',
  },

  '&:hover::before': {
    left: '100%',
  },

  '&.Mui-disabled': {
    background: '#2a3150',
    color: '#5a5f7a',
    boxShadow: 'none',
  },
}));

export const GradientButton: React.FC<GradientButtonProps> = ({
  children,
  gradient,
  ...props
}) => {
  return (
    <StyledGradientButton gradientbg={gradient} {...props}>
      {children}
    </StyledGradientButton>
  );
};

export default GradientButton;
