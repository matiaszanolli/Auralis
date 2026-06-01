/**
 * TrackCardOverlay Component
 *
 * Renders the overlay content on track card artwork:
 * - Play button on hover
 * - Duration badge
 * - No artwork icon fallback
 */

import { MouseEvent } from 'react';
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
  onPlay: (e: MouseEvent) => void;
  title?: string;
}

export const TrackCardOverlay = ({
  duration,
  hasArtwork,
  isHovered,
  onPlay,
  title,
}: TrackCardOverlayProps) => {
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
          background: isHovered ? tokens.colors.opacityScale.dark.intense : 'transparent',
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
            transition: tokens.transitions.state_inOut,
            '&:hover': {
              background: tokens.gradients.decorative.electricPurple,
              transform: 'scale(1.1)',
            },
          }}
          aria-label={title ? `Play ${title}` : 'Play'}
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
            ? tokens.glass.starfield.sharp // #3950: unified starfield glass (sharper on hover)
            : tokens.glass.starfield.medium, // #3950: unified starfield glass (subtle at rest)
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: isHovered ? tokens.colors.text.primary : tokens.colors.text.tertiary,
            fontWeight: tokens.typography.fontWeight.medium,
            fontSize: tokens.typography.fontSize.xs,
            transition: tokens.transitions.color,
          }}
        >
          {formatDuration(duration)}
        </Typography>
      </DurationBadge>
    </>
  );
};
