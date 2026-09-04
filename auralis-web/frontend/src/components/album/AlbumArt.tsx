/**
 * Album Art Component
 *
 * Displays album artwork with progressive loading and smooth fade-in.
 * Supports loading states, error handling, varied gradient fallbacks, and caching.
 * Enhanced with ProgressiveImage for better perceived performance and retry logic.
 */

import { CSSProperties, KeyboardEvent } from 'react';
import { Box, styled } from '@mui/material';
import { ProgressiveImage } from '@/components/shared/ui/media';
import { tokens, withOpacity } from '@/design-system';
import { useArtworkRevision } from '@/hooks/library/useArtworkUpdates';
import { getArtworkUrl } from '@/services/artworkService';

interface AlbumArtProps {
  albumId?: number;
  size?: number | string;
  borderRadius?: number | string;
  onClick?: () => void;
  showSkeleton?: boolean;
  style?: CSSProperties;
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
    transition: tokens.transitions.state_inOut,
    flexShrink: 0, // Prevent shrinking in flex containers

    '&:hover': clickable ? {
      transform: 'scale(1.05)',
      boxShadow: `0 8px 32px ${tokens.colors.opacityScale.accent.veryStrong}`,
    } : {},

    '&:focus-visible': clickable ? {
      outline: `2px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    } : {},
  })
);

/**
 * Generate a unique gradient for each album based on its ID
 * Creates visual variety in fallback placeholders using design tokens
 */
const getGradientForAlbum = (albumId?: number): string => {
  if (!albumId) {
    return `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${withOpacity(tokens.colors.accent.secondary, 0.15)} 100%)`;
  }

  // 8 distinct gradient combinations using design tokens
  const gradients = [
    `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${withOpacity(tokens.colors.accent.secondary, 0.15)} 100%)`, // Violet-Aqua
    `linear-gradient(135deg, ${withOpacity(tokens.colors.accent.secondary, 0.15)} 0%, ${withOpacity(tokens.colors.accent.tertiary, 0.15)} 100%)`,  // Aqua-Lavender
    `linear-gradient(135deg, ${withOpacity(tokens.colors.semantic.success, 0.15)} 0%, ${tokens.colors.opacityScale.accent.lighter} 100%)`,  // Green-Purple
    `linear-gradient(135deg, ${withOpacity(tokens.colors.accent.tertiary, 0.15)} 0%, ${withOpacity(tokens.colors.accent.energy, 0.15)} 100%)`,   // Lavender-Amber
    `linear-gradient(135deg, ${withOpacity(tokens.colors.accent.primary, 0.15)} 0%, ${withOpacity(tokens.colors.semantic.success, 0.15)} 100%)`,    // Violet-Green
    `linear-gradient(135deg, ${withOpacity(tokens.colors.accent.energy, 0.15)} 0%, ${withOpacity(tokens.colors.accent.tertiary, 0.15)} 100%)`,   // Amber-Lavender
    `linear-gradient(135deg, ${withOpacity(tokens.colors.accent.secondary, 0.15)} 0%, ${withOpacity(tokens.colors.accent.primary, 0.15)} 100%)`,   // Aqua-Violet
    `linear-gradient(135deg, ${tokens.colors.opacityScale.accent.lighter} 0%, ${withOpacity(tokens.colors.semantic.success, 0.15)} 100%)`,  // Purple-Green
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

export const AlbumArt = ({
  albumId,
  size = 160,
  borderRadius = 8,
  onClick,
  showSkeleton: _showSkeleton = true,
  style,
}: AlbumArtProps) => {
  // Subscribe to artwork_updated WS messages for cache-busting (#2867)
  const artworkRevision = useArtworkRevision(albumId ?? 0);
  // Request a size-appropriate variant so a small thumbnail doesn't decode the
  // full-resolution bitmap (#4447). Only a numeric size is a usable px hint.
  const sizeHint = typeof size === 'number' ? size : undefined;
  const artworkUrl = albumId
    ? getArtworkUrl(albumId, { size: sizeHint, revision: artworkRevision })
    : '';
  const artworkLabel = albumId ? `Album ${albumId} artwork` : 'Album artwork';

  return (
    <ArtworkContainer
      size={size}
      clickable={!!onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={onClick ? artworkLabel : undefined}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (event: KeyboardEvent) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      sx={{ borderRadius }}
      style={style}
    >
      <ProgressiveImage
        src={artworkUrl}
        alt={artworkLabel}
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
