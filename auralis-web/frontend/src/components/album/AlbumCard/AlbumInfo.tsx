/**
 * AlbumInfo Component
 *
 * Displays album metadata information:
 * - Album title
 * - Artist name
 * - Track count, duration, release year
 */

import React from 'react';
import { CardContent, Typography, Tooltip } from '@mui/material';
import { tokens } from '@/design-system';

interface AlbumInfoProps {
  title: string;
  artist: string;
  trackCount?: number;
  duration?: number;
  year?: number;
}

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
};

export const AlbumInfo: React.FC<AlbumInfoProps> = ({
  title,
  artist,
  trackCount = 0,
  duration,
  year,
}) => {
  return (
    <CardContent sx={{ p: 2, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
      {/* Album Title */}
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

      {/* Artist Name */}
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

      {/* Album Metadata */}
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.disabled,
          display: 'block',
        }}
      >
        {trackCount > 0 && `${trackCount} ${trackCount === 1 ? 'track' : 'tracks'}`}
        {duration && trackCount > 0 && ' • '}
        {duration && formatDuration(duration)}
        {year && ' • '}
        {year}
      </Typography>
    </CardContent>
  );
};

export default AlbumInfo;
