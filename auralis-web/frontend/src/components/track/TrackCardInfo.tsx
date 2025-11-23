/**
 * TrackCardInfo Component
 *
 * Renders track metadata section:
 * - Track title
 * - Artist name
 * - Album name
 */

import React from 'react';
import { Typography, Tooltip } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { TrackCardContent } from './TrackCardStyles';

interface TrackCardInfoProps {
  title: string;
  artist: string;
  album: string;
}

export const TrackCardInfo: React.FC<TrackCardInfoProps> = ({
  title,
  artist,
  album,
}) => {
  return (
    <TrackCardContent>
      <Tooltip title={title} placement="top">
        <Typography
          variant="subtitle1"
          sx={{
            fontWeight: 600,
            color: tokens.colors.text.primary,
            mb: 0.5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
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
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: 0.5,
          }}
        >
          {artist}
        </Typography>
      </Tooltip>

      <Tooltip title={album} placement="top">
        <Typography
          variant="caption"
          sx={{
            color: tokens.colors.text.disabled,
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
