/**
 * MediaCardInfo Component
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Metadata display below artwork (title, artist, album/track count, etc.)
 * Unified component for both track and album metadata.
 */

import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

interface MediaCardInfoProps {
  /** Primary title */
  title: string;
  /** Primary metadata line (artist) */
  primary: string;
  /** Secondary metadata line (album for tracks, track count for albums) */
  secondary: string;
  /** Whether this item is currently playing */
  isPlaying?: boolean;
}

/**
 * MediaCardInfo - Metadata display component
 *
 * Layout:
 * - Title (ellipsis truncation)
 * - Primary metadata (artist name)
 * - Secondary metadata (album/track count)
 *
 * Highlights title when playing.
 */
export const MediaCardInfo: React.FC<MediaCardInfoProps> = ({
  title,
  primary,
  secondary,
  isPlaying = false,
}) => {
  return (
    <Box
      sx={{
        padding: tokens.spacing.md,
        flexGrow: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: tokens.spacing.xs,
      }}
    >
      {/* Title */}
      <Typography
        variant="subtitle2"
        sx={{
          fontWeight: tokens.typography.fontWeight.semibold,
          fontSize: tokens.typography.fontSize.sm,
          color: isPlaying ? tokens.colors.accent.primary : tokens.colors.text.primary,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {title}
      </Typography>

      {/* Primary metadata (artist) */}
      <Typography
        variant="body2"
        sx={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.secondary,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {primary}
      </Typography>

      {/* Secondary metadata (album/track count) */}
      <Typography
        variant="caption"
        sx={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.disabled,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {secondary}
      </Typography>
    </Box>
  );
};
