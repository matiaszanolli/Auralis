/**
 * TrackCardOverlay Component
 *
 * Renders the overlay content on track card artwork:
 * - Play button on hover
 * - Duration badge
 * - No artwork icon fallback
 */

import React from 'react';

import { PlayArrow, MusicNote } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { PlayOverlay, DurationBadge, NoArtworkIcon, ShimmerOverlay } from './TrackCardStyles';
import { formatDuration } from './TrackCardHelpers';
import { IconButton } from '@/design-system';
import { Typography } from '@mui/material';

interface TrackCardOverlayProps {
  duration: number;
  hasArtwork: boolean;
  isHovered: boolean;
  onPlay: (e: React.MouseEvent) => void;
}

export const TrackCardOverlay: React.FC<TrackCardOverlayProps> = ({
  duration,
  hasArtwork,
  isHovered,
  onPlay,
}) => {
  return (
    <>
      {/* No artwork icon + shimmer effect */}
      {!hasArtwork && (
        <>
          <NoArtworkIcon>
            <MusicNote
              sx={{
                fontSize: 64,
                color: tokens.colors.opacityScale.accent.lighter,
              }}
            />
          </NoArtworkIcon>
          {/* Shimmer overlay - animates on hover */}
          <ShimmerOverlay className="shimmer-overlay" />
        </>
      )}

      {/* Play button overlay */}
      <PlayOverlay
        sx={{
          background: isHovered ? 'rgba(0, 0, 0, 0.5)' : 'transparent',
          backdropFilter: isHovered ? 'blur(4px)' : 'none',
          opacity: isHovered ? 1 : 0,
        }}
      >
        <IconButton
          sx={{
            width: 56,
            height: 56,
            background: tokens.gradients.aurora,
            color: tokens.colors.text.primary,
            transform: isHovered ? 'scale(1)' : 'scale(0.8)',
            transition: 'all 0.3s ease',
            '&:hover': {
              background: tokens.gradients.decorative.electricPurple,
              transform: 'scale(1.1)',
            },
          }}
          onClick={onPlay}
        >
          <PlayArrow sx={{ fontSize: 32 }} />
        </IconButton>
      </PlayOverlay>

      {/* Duration badge - fades in on hover, low contrast at rest */}
      <DurationBadge
        sx={{
          opacity: isHovered ? 1 : 0.6, // Fade in on hover
          background: isHovered
            ? 'rgba(27, 35, 46, 0.70)' // Sharper on hover
            : 'rgba(27, 35, 46, 0.50)', // Subtle at rest
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: isHovered ? tokens.colors.text.primary : tokens.colors.text.tertiary,
            fontWeight: 500,
            fontSize: '0.7rem',
            transition: 'color 0.2s ease',
          }}
        >
          {formatDuration(duration)}
        </Typography>
      </DurationBadge>
    </>
  );
};
