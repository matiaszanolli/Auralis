/**
 * Album Art Component
 *
 * Displays album artwork with progressive loading and smooth fade-in.
 * Supports loading states, error handling, and caching.
 * Enhanced with ProgressiveImage for better perceived performance.
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { ProgressiveImage } from '../shared/ProgressiveImage';

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
    position: 'relative',
    overflow: 'hidden',
    cursor: clickable ? 'pointer' : 'default',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',

    '&:hover': clickable ? {
      transform: 'scale(1.05)',
      boxShadow: '0 8px 32px rgba(102, 126, 234, 0.4)',
    } : {},
  })
);

export const AlbumArt: React.FC<AlbumArtProps> = ({
  albumId,
  size = 160,
  borderRadius = 8,
  onClick,
  showSkeleton = true,
}) => {
  // Construct artwork URL
  const artworkUrl = albumId ? `http://localhost:8765/api/albums/${albumId}/artwork` : '';

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
      />
    </ArtworkContainer>
  );
};

export default AlbumArt;
