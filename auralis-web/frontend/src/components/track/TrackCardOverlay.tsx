/**
 * TrackCardOverlay Component
 *
 * Renders the overlay content on track card artwork:
 * - Play button on hover
 * - Duration badge
 * - No artwork icon fallback
 */

import React from 'react';
import { Box, IconButton, Typography } from '@mui/material';
import { PlayArrow, MusicNote } from '@mui/icons-material';
import { auroraOpacity, gradients } from '../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';
import { PlayOverlay, DurationBadge, NoArtworkIcon } from './TrackCardStyles';
import { formatDuration } from './TrackCardHelpers';

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
      {/* No artwork icon */}
      {!hasArtwork && (
        <NoArtworkIcon>
          <MusicNote
            sx={{
              fontSize: 64,
              color: auroraOpacity.lighter,
            }}
          />
        </NoArtworkIcon>
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
            background: gradients.aurora,
            color: tokens.colors.text.primary,
            transform: isHovered ? 'scale(1)' : 'scale(0.8)',
            transition: 'all 0.3s ease',
            '&:hover': {
              background: gradients.electricPurple,
              transform: 'scale(1.1)',
            },
          }}
          onClick={onPlay}
        >
          <PlayArrow sx={{ fontSize: 32 }} />
        </IconButton>
      </PlayOverlay>

      {/* Duration badge */}
      <DurationBadge>
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.primary,
            fontWeight: 500,
            fontSize: '0.7rem',
          }}
        >
          {formatDuration(duration)}
        </Typography>
      </DurationBadge>
    </>
  );
};
