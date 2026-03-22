import React from 'react';
import { Box, styled } from '@mui/material';
import { rotate, pulse } from '@/components/library/Styles/Animation.styles';
import { tokens, CircularProgress } from '@/design-system';

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

export const LoadingSpinner = ({
  size = 40,
  thickness = 4,
  gradient: _gradient = tokens.gradients.aurora,
  className,
}: LoadingSpinnerProps) => {
  const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <SpinnerContainer className={className} role="status" aria-label="Loading">
      <GradientSVG width={0} height={0}>
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={tokens.colors.accent.primary} />
            <stop offset="100%" stopColor={tokens.colors.accent.primary} />
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

const LoadingText = styled(Box)(({ theme: _theme }) => ({
  fontSize: tokens.typography.fontSize.base,
  color: tokens.colors.text.secondary,
  fontWeight: tokens.typography.fontWeight.medium,
  animation: `${pulse} 2s ease-in-out infinite`,
}));

export const CenteredLoading = ({
  text,
  size = 48,
}: CenteredLoadingProps) => {
  return (
    <CenteredContainer>
      <LoadingSpinner size={size} />
      {text && <LoadingText>{text}</LoadingText>}
    </CenteredContainer>
  );
};

export default LoadingSpinner;
