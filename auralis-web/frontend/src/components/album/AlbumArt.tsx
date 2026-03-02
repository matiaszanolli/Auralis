/**
 * Album Art Component
 *
 * Displays album artwork with progressive loading and smooth fade-in.
 * Supports loading states, error handling, varied gradient fallbacks, and caching.
 * Enhanced with ProgressiveImage for better perceived performance and retry logic.
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import { ProgressiveImage } from '../shared/ui/media';
import { tokens } from '@/design-system';

interface AlbumArtProps {
  albumId?: number;
  size?: number | string;
  borderRadius?: number | string;
  onClick?: () => void;
  showSkeleton?: boolean;
  style?: React.CSSProperties;
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
      boxShadow: `0 8px 32px ${tokens.colors.opacityScale.accent.veryStrong}`,
    } : {},
  })
);

/**
 * Generate a unique gradient for each album based on its ID
 * Creates visual variety in fallback placeholders using design tokens
 */
const getGradientForAlbum = (albumId?: number): string => {
  // Helper to add alpha to hex colors
  const hexToRgba = (hex: string, alpha: number): string => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  if (!albumId) {
    return `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${hexToRgba(tokens.colors.accent.secondary, 0.15)} 100%)`;
  }

  // 8 distinct gradient combinations using design tokens
  const gradients = [
    `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${hexToRgba(tokens.colors.accent.secondary, 0.15)} 100%)`, // Violet-Aqua
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.accent.secondary, 0.15)} 0%, ${hexToRgba(tokens.colors.accent.tertiary, 0.15)} 100%)`,  // Aqua-Lavender
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.semantic.success, 0.15)} 0%, ${tokens.colors.opacityScale.accent.lighter} 100%)`,  // Green-Purple
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.accent.tertiary, 0.15)} 0%, ${hexToRgba(tokens.colors.accent.energy, 0.15)} 100%)`,   // Lavender-Amber
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.accent.primary, 0.15)} 0%, ${hexToRgba(tokens.colors.semantic.success, 0.15)} 100%)`,    // Violet-Green
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.accent.energy, 0.15)} 0%, ${hexToRgba(tokens.colors.accent.tertiary, 0.15)} 100%)`,   // Amber-Lavender
    `linear-gradient(135deg, ${hexToRgba(tokens.colors.accent.secondary, 0.15)} 0%, ${hexToRgba(tokens.colors.accent.primary, 0.15)} 100%)`,   // Aqua-Violet
    `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${hexToRgba(tokens.colors.semantic.success, 0.15)} 100%)`,  // Purple-Green
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
  showSkeleton: _showSkeleton = true,
  style,
}) => {
  // Construct artwork URL
  const artworkUrl = albumId ? `/api/albums/${albumId}/artwork` : '';

  return (
    <ArtworkContainer
      size={size}
      clickable={!!onClick}
      onClick={onClick}
      sx={{ borderRadius }}
      style={style}
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
