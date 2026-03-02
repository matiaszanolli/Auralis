/**
 * MediaCardOverlay Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Overlay with play button and optional badges (duration, track count, etc.)
 * Appears on hover or when playing.
 */

import React from 'react';
import { Box, IconButton } from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import { tokens } from '@/design-system';

interface MediaCardOverlayProps {
  /** Whether card is hovered */
  isHovered: boolean;
  /** Whether card is currently playing */
  isPlaying?: boolean;
  /** Play button click handler */
  onPlay: (e: React.MouseEvent) => void;
  /** Optional badge content (duration, track count, etc.) */
  badgeContent?: React.ReactNode;
}

/**
 * MediaCardOverlay - Interactive overlay for media cards
 *
 * Features:
 * - Play button (centered, appears on hover or when playing)
 * - Optional badge (bottom-right corner)
 * - Smooth fade transitions
 */
export const MediaCardOverlay: React.FC<MediaCardOverlayProps> = ({
  isHovered,
  isPlaying = false,
  onPlay,
  badgeContent,
}) => {
  const showOverlay = isHovered || isPlaying;

  return (
    <>
      {/* Darkening overlay on hover */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.4)',
          opacity: showOverlay ? 1 : 0,
          transition: tokens.transitions.base,
          pointerEvents: 'none',
        }}
      />

      {/* Play button (centered) */}
      <Box
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          opacity: showOverlay ? 1 : 0,
          transition: tokens.transitions.base,
        }}
      >
        <IconButton
          onClick={onPlay}
          sx={{
            background: tokens.colors.accent.primary,
            color: tokens.colors.text.primary,
            width: 56,
            height: 56,
            '&:hover': {
              background: tokens.colors.accent.secondary,
              transform: 'scale(1.1)',
            },
            transition: tokens.transitions.fast,
          }}
        >
          <PlayArrow sx={{ fontSize: 32 }} />
        </IconButton>
      </Box>

      {/* Optional badge (bottom-right corner) */}
      {badgeContent && (
        <Box
          sx={{
            position: 'absolute',
            bottom: tokens.spacing.sm,
            right: tokens.spacing.sm,
            padding: `${tokens.spacing.xs}px ${tokens.spacing.sm}px`,
            borderRadius: tokens.borderRadius.sm,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(8px)',
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.xs,
            fontWeight: tokens.typography.fontWeight.medium,
          }}
        >
          {badgeContent}
        </Box>
      )}
    </>
  );
};
