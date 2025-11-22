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
 * - Optimized re-renders
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React, { useState, useEffect } from 'react';
import { Box, styled } from '@mui/material';
import { MusicNote } from '@mui/icons-material';
import { SkeletonContainer, SkeletonBox } from '../library/Skeleton.styles';
import { fadeIn } from '../library/Animation.styles';
import { Skeleton } from './SkeletonLoader';

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
  flexShrink: 0, // Prevent container from collapsing
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
  background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%)',
  color: 'rgba(255, 255, 255, 0.4)',
  animation: `${fadeIn} 0.3s cubic-bezier(0.4, 0, 0.2, 1)`,
});

/**
 * Progressive Image with smooth loading transitions
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
  onError
}) => {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    // Reset states when src changes
    setImageLoaded(false);
    setImageError(false);
    setImageSrc(null);
    setRetryCount(0);

    if (!src) {
      setImageError(true);
      return;
    }

    // Preload image
    const img = new Image();

    img.onload = () => {
      setImageSrc(src);
      setImageLoaded(true);
      onLoad?.();
    };

    img.onerror = () => {
      // Retry logic
      if (retryOnError && retryCount < maxRetries) {
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 3000); // Exponential backoff
        setTimeout(() => {
          setRetryCount(prev => prev + 1);
        }, retryDelay);
      } else {
        setImageError(true);
        onError?.();
      }
    };

    // Add cache busting for retries
    img.src = retryCount > 0 ? `${src}?retry=${retryCount}` : src;

    // Cleanup
    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [src, onLoad, onError, retryCount, retryOnError, maxRetries]);

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
            background: fallbackGradient || 'linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%)',
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
