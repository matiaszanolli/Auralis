/**
 * Progressive Image Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Loads images with smooth fade-in animation and skeleton fallback.
 * Provides better perceived performance through progressive loading.
 *
 * Features:
 * - Skeleton loader while image loads
 * - Smooth fade-in animation (300ms)
 * - Error state handling with fallback
 * - Lazy loading support
 * - Retry logic with exponential backoff
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { MusicNote } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { SkeletonContainer } from '../../../library/Styles/Skeleton.styles';
import { fadeIn } from '../../../library/Styles/Animation.styles';
import { Skeleton } from '../loaders';
import { useProgressiveImageLoader } from './useProgressiveImageLoader';

interface ProgressiveImageProps {
  src: string;
  alt: string;
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  objectFit?: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down';
  showFallback?: boolean;
  lazyLoad?: boolean;
  fallbackGradient?: string;
  iconSize?: string | number;
  retryOnError?: boolean;
  maxRetries?: number;
  onLoad?: () => void;
  onError?: () => void;
}

const ImageContainer = styled(Box)({
  position: 'relative',
  overflow: 'hidden',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexShrink: 0,
});

const StyledImage = styled('img')<{ isloaded: string }>(({ isloaded }) => ({
  width: '100%',
  height: '100%',
  opacity: isloaded === 'true' ? 1 : 0,
  animation: isloaded === 'true' ? `${fadeIn} 0.3s cubic-bezier(0.4, 0, 0.2, 1)` : 'none',
  transition: 'opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
}));

const FallbackContainer = styled(Box)({
  width: '100%',
  height: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${tokens.colors.opacityScale.accent.light} 100%)`,
  color: tokens.colors.opacityScale.accent.standard,
  animation: `${fadeIn} 0.3s cubic-bezier(0.4, 0, 0.2, 1)`,
});

/**
 * Progressive Image with smooth loading transitions
 * Uses custom hook for retry logic and image state management
 */
export const ProgressiveImage: React.FC<ProgressiveImageProps> = ({
  src,
  alt,
  width = '100%',
  height = '100%',
  borderRadius = '8px',
  objectFit = 'cover',
  showFallback = true,
  lazyLoad = true,
  fallbackGradient,
  iconSize = '3rem',
  retryOnError = true,
  maxRetries = 2,
  onLoad,
  onError,
}) => {
  const { imageLoaded, imageError, imageSrc } = useProgressiveImageLoader({
    src,
    retryOnError,
    maxRetries,
    onLoad,
    onError,
  });

  return (
    <ImageContainer
      sx={{
        width,
        height,
        borderRadius,
      }}
    >
      {/* Skeleton loader while loading */}
      {!imageLoaded && !imageError && (
        <SkeletonContainer>
          <Skeleton
            width="100%"
            height="100%"
            borderRadius={borderRadius}
            variant="rectangular"
          />
        </SkeletonContainer>
      )}

      {/* Image */}
      {imageSrc && !imageError && (
        <StyledImage
          src={imageSrc}
          alt={alt}
          isloaded={imageLoaded ? 'true' : 'false'}
          loading={lazyLoad ? 'lazy' : 'eager'}
          style={{
            objectFit,
            borderRadius,
          }}
        />
      )}

      {/* Fallback when error or no src */}
      {imageError && showFallback && (
        <FallbackContainer
          sx={{
            borderRadius,
            background: fallbackGradient || `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${tokens.colors.opacityScale.accent.light} 100%)`,
          }}
        >
          <MusicNote
            sx={{
              fontSize: iconSize,
              opacity: 0.5,
            }}
          />
        </FallbackContainer>
      )}
    </ImageContainer>
  );
};

export default ProgressiveImage;
