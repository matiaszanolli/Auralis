import React from 'react';
import { Box, CircularProgress, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';
import { rotate, pulse } from '../library/Animation.styles';
import { colorAuroraPrimary, colorAuroraSecondary } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface LoadingSpinnerProps {
  size?: number;
  thickness?: number;
  gradient?: string;
  className?: string;
}

const SpinnerContainer = styled(Box)({
  display: 'inline-flex',
  position: 'relative',
  animation: `${pulse} 2s ease-in-out infinite`,
});

const GradientSVG = styled('svg')({
  position: 'absolute',
  top: 0,
  left: 0,
  pointerEvents: 'none',
});

const SpinnerWrapper = styled(Box)({
  position: 'relative',
  display: 'inline-flex',
  animation: `${rotate} 1.4s linear infinite`,
});

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 40,
  thickness = 4,
  gradient = gradients.aurora,
  className,
}) => {
  const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <SpinnerContainer className={className}>
      <GradientSVG width={0} height={0}>
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={colorAuroraPrimary} />
            <stop offset="100%" stopColor={colorAuroraSecondary} />
          </linearGradient>
        </defs>
      </GradientSVG>

      <SpinnerWrapper>
        <CircularProgress
          size={size}
          thickness={thickness}
          sx={{
            color: 'transparent',
            '& .MuiCircularProgress-circle': {
              stroke: `url(#${gradientId})`,
              strokeLinecap: 'round',
            },
          }}
        />
      </SpinnerWrapper>
    </SpinnerContainer>
  );
};

// Centered loading spinner with optional text
interface CenteredLoadingProps {
  text?: string;
  size?: number;
}

const CenteredContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  gap: `${tokens.spacing.md}px`,
  padding: `${tokens.spacing.xxxl}px`,
  minHeight: '200px',
});

const LoadingText = styled(Box)(({ theme }) => ({
  fontSize: '14px',
  color: tokens.colors.text.secondary,
  fontWeight: 500,
  animation: `${pulse} 2s ease-in-out infinite`,
}));

export const CenteredLoading: React.FC<CenteredLoadingProps> = ({
  text,
  size = 48,
}) => {
  return (
    <CenteredContainer>
      <LoadingSpinner size={size} />
      {text && <LoadingText>{text}</LoadingText>}
    </CenteredContainer>
  );
};

export default LoadingSpinner;
