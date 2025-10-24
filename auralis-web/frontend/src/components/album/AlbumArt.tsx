/**
 * Album Art Component
 *
 * Displays album artwork with fallback to placeholder
 * Supports loading states, error handling, and caching
 */

import React, { useState } from 'react';
import { Box, Skeleton, styled } from '@mui/material';
import { Album as AlbumIcon } from '@mui/icons-material';
import { colors } from '../../theme/auralisTheme';

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
    background: 'linear-gradient(135deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: clickable ? 'pointer' : 'default',
    transition: 'transform 0.2s ease, box-shadow 0.2s ease',

    '&:hover': clickable ? {
      transform: 'scale(1.05)',
      boxShadow: '0 8px 24px rgba(102, 126, 234, 0.3)',
    } : {},
  })
);

const ArtworkImage = styled('img')({
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  display: 'block',
});

const PlaceholderIcon = styled(AlbumIcon)(({ theme }) => ({
  fontSize: '48px',
  color: 'rgba(255, 255, 255, 0.7)',
  opacity: 0.9,
}));

export const AlbumArt: React.FC<AlbumArtProps> = ({
  albumId,
  size = 160,
  borderRadius = 8,
  onClick,
  showSkeleton = true,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Construct artwork URL
  const artworkUrl = albumId ? `http://localhost:8765/api/albums/${albumId}/artwork` : null;

  const handleImageLoad = () => {
    setLoading(false);
    setError(false);
  };

  const handleImageError = () => {
    setLoading(false);
    setError(true);
  };

  return (
    <ArtworkContainer
      size={size}
      clickable={!!onClick}
      onClick={onClick}
      sx={{ borderRadius }}
    >
      {/* Loading skeleton */}
      {showSkeleton && loading && !error && (
        <Skeleton
          variant="rectangular"
          width="100%"
          height="100%"
          animation="wave"
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            borderRadius,
          }}
        />
      )}

      {/* Artwork image or placeholder */}
      {artworkUrl && !error ? (
        <ArtworkImage
          src={artworkUrl}
          alt="Album artwork"
          onLoad={handleImageLoad}
          onError={handleImageError}
          style={{
            opacity: loading ? 0 : 1,
            transition: 'opacity 0.3s ease',
          }}
        />
      ) : (
        <PlaceholderIcon data-testid="AlbumIcon" />
      )}
    </ArtworkContainer>
  );
};

export default AlbumArt;
