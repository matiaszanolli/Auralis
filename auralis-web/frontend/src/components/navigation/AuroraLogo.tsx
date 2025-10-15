import React from 'react';
import { Box, Typography, styled, keyframes } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

interface AuroraLogoProps {
  size?: 'small' | 'medium' | 'large';
  showText?: boolean;
  animated?: boolean;
}

const float = keyframes`
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-4px);
  }
`;

const shimmer = keyframes`
  0% {
    background-position: -200% center;
  }
  100% {
    background-position: 200% center;
  }
`;

const LogoContainer = styled(Box)<{ animated?: boolean }>(({ animated }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  animation: animated ? `${float} 3s ease-in-out infinite` : 'none',
}));

const LogoIcon = styled(Box)<{ size: number }>(({ size }) => ({
  width: size,
  height: size,
  borderRadius: '8px',
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
  overflow: 'hidden',
  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',

  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
    backgroundSize: '200% 100%',
    animation: `${shimmer} 3s infinite`,
  },
}));

const WaveIcon = styled('svg')<{ size: number }>(({ size }) => ({
  width: size * 0.6,
  height: size * 0.6,
  position: 'relative',
  zIndex: 1,
}));

const LogoText = styled(Typography)<{ size: string; animated?: boolean }>(({ size, animated }) => {
  const fontSize = {
    small: '16px',
    medium: '20px',
    large: '28px',
  }[size];

  return {
    fontSize,
    fontWeight: 700,
    background: gradients.aurora,
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-0.5px',
    backgroundSize: animated ? '200% auto' : '100% auto',
    animation: animated ? `${shimmer} 3s linear infinite` : 'none',
  };
});

export const AuroraLogo: React.FC<AuroraLogoProps> = ({
  size = 'medium',
  showText = true,
  animated = false,
}) => {
  const iconSize = {
    small: 32,
    medium: 40,
    large: 56,
  }[size];

  return (
    <LogoContainer animated={animated}>
      <LogoIcon size={iconSize}>
        <WaveIcon size={iconSize} viewBox="0 0 24 24" fill="none">
          {/* Aurora wave pattern */}
          <path
            d="M2 12C2 12 4 8 8 8C12 8 12 16 16 16C20 16 22 12 22 12"
            stroke="white"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M2 16C2 16 4 12 8 12C12 12 12 20 16 20C20 20 22 16 22 16"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.6"
          />
          <path
            d="M2 8C2 8 4 4 8 4C12 4 12 12 16 12C20 12 22 8 22 8"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.4"
          />
        </WaveIcon>
      </LogoIcon>

      {showText && (
        <LogoText size={size} animated={animated}>
          Auralis
        </LogoText>
      )}
    </LogoContainer>
  );
};

export default AuroraLogo;
