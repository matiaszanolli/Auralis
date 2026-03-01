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
  borderRadius: '8px',
  background: tokens.gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: `0 4px 12px ${tokens.colors.opacityScale.accent.strong}`,

  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: `linear-gradient(90deg, transparent, rgba(255,255,255,${0.3}), transparent)`,
    backgroundSize: '200% 100%',
    animation: `${shimmer} 3s infinite`,
  },
}));

export const WaveIcon = styled('svg')<{ size: number }>(({ size }) => ({
  width: size * 0.6,
  height: size * 0.6,
  position: 'relative',
  zIndex: 1,
}));

export const LogoText = styled(Typography, {
  shouldForwardProp: (prop) => prop !== 'animated',
})<{ size: string; animated?: boolean }>(({ size, animated }) => {
  const fontSize = {
    small: '16px',
    medium: '20px',
    large: '28px',
  }[size];

  return {
    fontSize,
    fontWeight: 700,
    background: tokens.gradients.aurora,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-0.5px',
    backgroundSize: animated ? '200% auto' : '100% auto',
    animation: animated ? `${shimmer} 3s linear infinite` : 'none',
  };
});
