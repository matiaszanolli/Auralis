/**
 * AlbumInfo Component
 *
 * Displays album metadata information:
 * - Album title
 * - Artist name
 * - Track count, duration, release year
 */

import React from 'react';

import { tokens } from '@/design-system';
import { Tooltip } from '@/design-system';
import { CardContent, Typography } from '@mui/material';

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
            mb: 1, // Increased from 0.5 for more breathing room
            lineHeight: 1.4, // Improved line height for better readability
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

      {/* Album Metadata */}
      <Typography
        variant="caption"
        sx={{
          color: tokens.colors.text.tertiary, // Changed from disabled to tertiary (better hierarchy)
          fontWeight: 400,
          lineHeight: 1.5,
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
