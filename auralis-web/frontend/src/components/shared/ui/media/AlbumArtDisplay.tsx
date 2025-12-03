/**
 * AlbumArtDisplay - Shared Album Artwork Component
 *
 * Reusable album artwork display with consistent styling,
 * fallback handling, and optional interactivity.
 *
 * Features:
 * - Flexible sizing
 * - Image loading and error handling
 * - Placeholder/fallback UI
 * - Design token styling
 */

import React from 'react';
import { Box, styled } from '@mui/material';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import { tokens } from '@/design-system';
import { auroraOpacity } from '../../../library/Styles/Color.styles';

export interface AlbumArtDisplayProps {
  /**
   * Artwork URL or path
   */
  artworkPath?: string;

  /**
   * Album/track title for alt text
   */
  title?: string;

  /**
   * Album name
   */
  album?: string;

  /**
   * Size in pixels (width and height)
   */
  size?: number;

  /**
   * Use design tokens for styling (default: true)
   */
  useTokens?: boolean;

  /**
   * Additional sx styles
   */
  sx?: any;

  /**
   * Placeholder icon size
   */
  iconSize?: string | number;
}

interface StyledAlbumArtProps {
  size: number;
  useTokens: boolean;
}

const StyledAlbumArt = styled(Box)<StyledAlbumArtProps>(({ size, useTokens }) => ({
  width: size,
  height: size,
  borderRadius: useTokens ? tokens.borderRadius.md : '6px',
  overflow: 'hidden',
  flexShrink: 0,
  background: useTokens ? tokens.colors.bg.elevated : `linear-gradient(135deg, ${auroraOpacity.veryLight} 0%, ${auroraOpacity.veryLight} 100%)`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  boxShadow: useTokens ? tokens.shadows.md : '0 2px 8px rgba(0, 0, 0, 0.3)',
  transition: useTokens ? tokens.transitions.transform : 'transform 0.2s ease',

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },

  '&:hover': useTokens ? {
    transform: 'scale(1.05)',
  } : {
    transform: 'scale(1.02)',
  },
}));

const PlaceholderIcon = styled(MusicNoteIcon)(({ theme }) => ({
  color: tokens.colors.text.tertiary,
  fontSize: '24px',
}));

export const AlbumArtDisplay: React.FC<AlbumArtDisplayProps> = React.memo(({
  artworkPath,
  title = 'Album',
  album = 'Album',
  size = 64,
  useTokens = true,
  sx,
  iconSize = '24px',
}) => {
  return (
    <StyledAlbumArt
      size={size}
      useTokens={useTokens}
      sx={sx}
    >
      {artworkPath ? (
        <img
          src={artworkPath}
          alt={`${album || title} artwork`}
          loading="lazy"
        />
      ) : (
        <PlaceholderIcon sx={{ fontSize: iconSize as string | number }} />
      )}
    </StyledAlbumArt>
  );
});

AlbumArtDisplay.displayName = 'AlbumArtDisplay';

export default AlbumArtDisplay;
