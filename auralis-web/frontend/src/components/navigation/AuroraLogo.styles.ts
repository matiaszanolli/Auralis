/**
 * AuroraLogo Styled Components and Animations
 */

import { Box, Typography, styled, keyframes } from '@mui/material';
import { tokens } from '@/design-system';

export const float = keyframes`
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-4px);
  }
`;

export const shimmer = keyframes`
  0% {
    background-position: -200% center;
  }
  100% {
    background-position: 200% center;
  }
`;

export const LogoContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'animated',
})<{ animated?: boolean }>(({ animated }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  animation: animated ? `${float} 3s ease-in-out infinite` : 'none',
}));

export const LogoIcon = styled(Box)<{ size: number }>(({ size }) => ({
  width: size,
  height: size,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}));

export const WaveIcon = styled('svg')<{ size: number }>(({ size }) => ({
  width: size,
  height: size,
  overflow: 'visible',
}));

export const LogoText = styled(Typography, {
  shouldForwardProp: (prop) => prop !== 'animated',
})<{ size: string; animated?: boolean }>(({ size, animated }) => {
  const fontSize = {
    small: tokens.typography.fontSize.md,
    medium: tokens.typography.fontSize.lg,
    large: tokens.typography.fontSize['2xl'],
  }[size];

  return {
    fontSize,
    fontWeight: tokens.typography.fontWeight.bold,
    background: tokens.gradients.aurora,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-0.5px',
    backgroundSize: animated ? '200% auto' : '100% auto',
    animation: animated ? `${shimmer} 3s linear infinite` : 'none',
  };
});
