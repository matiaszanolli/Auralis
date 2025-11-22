/**
 * Album Art Component
 *
 * Displays album artwork with progressive loading and smooth fade-in.
 * Supports loading states, error handling, varied gradient fallbacks, and caching.
 * Enhanced with ProgressiveImage for better perceived performance and retry logic.
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { ProgressiveImage } from '../shared/ProgressiveImage';
import { auroraOpacity } from '../library/Color.styles';

interface AlbumArtProps {
  albumId?: number;
  size?: number | string;
  borderRadius?: number | string;
  onClick?: () => void;
  showSkeleton?: boolean;
}

const ArtworkContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'clickable' && prop !== 'size'
})<{ size: number | string; clickable?: boolean }>(
  ({ size, clickable }) => ({
    width: size,
    height: size,
    minWidth: size,
    minHeight: size,
    position: 'relative',
    overflow: 'hidden',
    cursor: clickable ? 'pointer' : 'default',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    flexShrink: 0, // Prevent shrinking in flex containers

    '&:hover': clickable ? {
      transform: 'scale(1.05)',
      boxShadow: `0 8px 32px ${auroraOpacity.veryStrong}`,
    } : {},
  })
);

/**
 * Generate a unique gradient for each album based on its ID
 * Creates visual variety in fallback placeholders
 */
const getGradientForAlbum = (albumId?: number): string => {
  if (!albumId) {
    return `linear-gradient(135deg, ${auroraOpacity.lighter} 0%, rgba(118, 75, 162, 0.15) 100%)`;
  }

  // 8 distinct gradient combinations for visual variety
  const gradients = [
    `linear-gradient(135deg, ${auroraOpacity.lighter} 0%, rgba(118, 75, 162, 0.15) 100%)`, // Purple-Violet
    'linear-gradient(135deg, rgba(118, 75, 162, 0.15) 0%, rgba(237, 66, 100, 0.15) 100%)',  // Violet-Pink
    `linear-gradient(135deg, rgba(0, 212, 170, 0.15) 0%, ${auroraOpacity.lighter} 100%)`,  // Teal-Blue
    'linear-gradient(135deg, rgba(237, 66, 100, 0.15) 0%, rgba(255, 184, 0, 0.15) 100%)',   // Pink-Orange
    'linear-gradient(135deg, rgba(67, 97, 238, 0.15) 0%, rgba(0, 212, 170, 0.15) 100%)',    // Blue-Teal
    'linear-gradient(135deg, rgba(255, 184, 0, 0.15) 0%, rgba(237, 66, 100, 0.15) 100%)',   // Orange-Pink
    'linear-gradient(135deg, rgba(118, 75, 162, 0.15) 0%, rgba(67, 97, 238, 0.15) 100%)',   // Violet-Blue
    `linear-gradient(135deg, ${auroraOpacity.lighter} 0%, rgba(0, 212, 170, 0.15) 100%)`,  // Purple-Teal
  ];

  return gradients[albumId % gradients.length];
};

/**
 * Calculate icon size based on container size
 */
const getIconSize = (size: number | string): string => {
  const sizeNum = typeof size === 'number' ? size : parseInt(String(size));
  if (isNaN(sizeNum)) return '3rem';

  if (sizeNum <= 64) return '1.5rem';
  if (sizeNum <= 128) return '2.5rem';
  if (sizeNum <= 200) return '3.5rem';
  return '5rem';
};

export const AlbumArt: React.FC<AlbumArtProps> = ({
  albumId,
  size = 160,
  borderRadius = 8,
  onClick,
  showSkeleton = true,
}) => {
  // Construct artwork URL
  const artworkUrl = albumId ? `/api/albums/${albumId}/artwork` : '';

  return (
    <ArtworkContainer
      size={size}
      clickable={!!onClick}
      onClick={onClick}
      sx={{ borderRadius }}
    >
      <ProgressiveImage
        src={artworkUrl}
        alt={`Album ${albumId} artwork`}
        width="100%"
        height="100%"
        borderRadius={borderRadius}
        objectFit="cover"
        showFallback={true}
        lazyLoad={true}
        fallbackGradient={getGradientForAlbum(albumId)}
        iconSize={getIconSize(size)}
        retryOnError={false}
        maxRetries={0}
      />
    </ArtworkContainer>
  );
};

export default AlbumArt;
