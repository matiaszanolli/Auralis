/**
 * TrackCard Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Card for displaying individual tracks in grid view.
 * Shows artwork, track title, artist, album, and duration.
 */

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow,
  MusicNote,
} from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';
import { auroraOpacity } from '../library/Color.styles';
import { tokens } from '@/design-system/tokens';

interface TrackCardProps {
  id: number;
  title: string;
  artist: string;
  album: string;
  albumId?: number;
  duration: number;
  albumArt?: string;
  onPlay: (id: number) => void;
}

// Generate consistent color from album name for placeholders
const getAlbumColor = (albumName: string | undefined | null): string => {
  const gradientList = [
    gradients.aurora, // Purple
    gradients.gradientPink, // Pink
    gradients.gradientBlue, // Blue
    gradients.gradientGreen, // Green
    gradients.gradientSunset, // Sunset
    gradients.gradientTeal, // Ocean/Teal
    gradients.gradientPastel, // Pastel
    gradients.gradientRose, // Rose
  ];

  // Use default album name if not provided
  const name = albumName || 'Unknown Album';

  // Simple hash function
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % gradientList.length;
  return gradientList[index];
};

// Format duration in MM:SS
const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

export const TrackCard: React.FC<TrackCardProps> = ({
  id,
  title,
  artist,
  album,
  albumId,
  duration,
  albumArt,
  onPlay,
}) => {
  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <Card
      sx={{
        position: 'relative',
        borderRadius: 2,
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'all 0.3s ease',
        background: colors.background.surface,
        border: `1px solid ${colors.background.hover}`,
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: `0 8px 24px ${auroraOpacity.standard}`,
          border: `1px solid ${auroraOpacity.strong}`,
        },
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onPlay(id)}
    >
      {/* Artwork or placeholder */}
      <Box
        sx={{
          position: 'relative',
          width: '100%',
          paddingTop: '100%', // 1:1 aspect ratio
          background: albumArt
            ? `url(${albumArt}) center/cover`
            : getAlbumColor(album),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* No artwork icon */}
        {!albumArt && (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MusicNote
              sx={{
                fontSize: 64,
                color: auroraOpacity.lighter,
              }}
            />
          </Box>
        )}

        {/* Play button overlay */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: isHovered
              ? 'rgba(0, 0, 0, 0.5)'
              : 'transparent',
            backdropFilter: isHovered ? 'blur(4px)' : 'none',
            transition: 'all 0.3s ease',
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
            onClick={(e) => {
              e.stopPropagation();
              onPlay(id);
            }}
          >
            <PlayArrow sx={{ fontSize: 32 }} />
          </IconButton>
        </Box>

        {/* Duration badge */}
        <Box
          sx={{
            position: 'absolute',
            bottom: 8,
            right: 8,
            px: 1,
            py: 0.5,
            borderRadius: 1,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(10px)',
          }}
        >
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
        </Box>
      </Box>

      {/* Track info */}
      <CardContent sx={{ p: 2 }}>
        <Tooltip title={title} placement="top">
          <Typography
            variant="subtitle1"
            sx={{
              fontWeight: 600,
              color: colors.text.primary,
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
              color: colors.text.secondary,
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
              color: colors.text.disabled,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'block',
            }}
          >
            {album}
          </Typography>
        </Tooltip>
      </CardContent>
    </Card>
  );
};
