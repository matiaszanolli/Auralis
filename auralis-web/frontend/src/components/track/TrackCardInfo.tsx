/**
 * TrackCardInfo Component
 *
 * Renders track metadata section:
 * - Track title
 * - Artist name
 * - Album name
 */

import React from 'react';

import { tokens } from '@/design-system';
import { TrackCardContent } from './TrackCardStyles';
import { Tooltip } from '@/design-system';
import { Typography } from '@mui/material';

interface TrackCardInfoProps {
  title: string;
  artist: string;
  album: string;
  isPlaying?: boolean;
}

export const TrackCardInfo: React.FC<TrackCardInfoProps> = ({
  title,
  artist,
  album,
  isPlaying = false,
}) => {
  return (
    <TrackCardContent>
      <Tooltip title={title} placement="top">
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: isPlaying ? 700 : 600, // Higher contrast for visual anchor
            color: tokens.colors.text.primary,
            mb: 1,
            lineHeight: 1.4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            opacity: isPlaying ? 1 : 0.95, // Slightly more prominent when playing
          }}
        >
          {title}
        </Typography>
      </Tooltip>

      <Tooltip title={artist} placement="top">
        <Typography
          variant="body2"
          sx={{
            color: tokens.colors.text.secondary,
            fontWeight: 400, // Reduced from default (less weight variance)
            lineHeight: 1.5, // Increased for secondary text breathing room
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: 0.75, // Increased from 0.5 for more spacing
          }}
        >
          {artist}
        </Typography>
      </Tooltip>

      <Tooltip title={album} placement="top">
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.tertiary, // Changed from disabled to tertiary (better hierarchy)
            fontWeight: 400,
            lineHeight: 1.5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'block',
          }}
        >
          {album}
        </Typography>
      </Tooltip>
    </TrackCardContent>
  );
};
