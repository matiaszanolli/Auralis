/**
 * MediaCardArtwork Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Artwork container with responsive aspect ratio and placeholder support.
 * Unified component for both track and album artwork display.
 */

import React from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { MediaCardVariant } from './MediaCard.types';

interface MediaCardArtworkProps {
  /** Artwork URL (optional) */
  artworkUrl?: string;
  /** Fallback text for placeholder (album or track name) */
  fallbackText: string;
  /** Card variant (affects placeholder color) */
  variant: MediaCardVariant;
  /** Child elements (overlay) */
  children?: React.ReactNode;
}

/**
 * Generate placeholder color based on text hash
 * (Extracted from TrackCardHelpers.getAlbumColor)
 */
const getPlaceholderColor = (text: string): string => {
  const colors = [
    'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
    'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
    'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
    'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  ];

  const hash = text.split('').reduce((acc, char) => {
    return char.charCodeAt(0) + ((acc << 5) - acc);
  }, 0);

  return colors[Math.abs(hash) % colors.length];
};

/**
 * MediaCardArtwork - Artwork container with placeholder fallback
 */
export const MediaCardArtwork: React.FC<MediaCardArtworkProps> = ({
  artworkUrl,
  fallbackText,
  variant,
  children,
}) => {
  return (
    <Box
      sx={{
        position: 'relative',
        paddingTop: '100%', // 1:1 aspect ratio
        borderRadius: `${tokens.borderRadius.lg}px ${tokens.borderRadius.lg}px 0 0`,
        overflow: 'hidden',
        background: artworkUrl
          ? `url(${artworkUrl}) center/cover no-repeat`
          : getPlaceholderColor(fallbackText),
      }}
    >
      {/* Overlay container (play button, badges, etc.) */}
      {children && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
          }}
        >
          {children}
        </Box>
      )}
    </Box>
  );
};
