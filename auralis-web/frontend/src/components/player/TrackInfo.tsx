/**
 * TrackInfo - Track Information Display
 *
 * Displays current track information including album art, title, artist,
 * and interactive buttons (favorite, lyrics).
 *
 * Features:
 * - Album art with fallback
 * - Track title and artist
 * - Favorite/love button
 * - Lyrics button (optional)
 */

import React from 'react';
import { Box, IconButton, Tooltip, Typography, styled } from '@mui/material';
import { Favorite, FavoriteOutlined, Lyrics as LyricsIcon } from '@mui/icons-material';
import AlbumArtComponent from '../album/AlbumArt';
import AlbumArtDisplay from '../shared/AlbumArtDisplay';

export interface Track {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  favorite?: boolean;
  artwork_path?: string;
  [key: string]: any;
}

export interface TrackInfoProps {
  // Current track
  track: Track | null;

  // Favorite state
  isLoved: boolean;
  isFavoriting?: boolean;

  // Callbacks
  onToggleLove: () => void;
  onToggleLyrics?: () => void;

  // Optional customization
  showLyricsButton?: boolean;
}

/**
 * Track Info Component
 *
 * Displays current track metadata with interactive controls.
 */
export const TrackInfo: React.FC<TrackInfoProps> = ({
  track,
  isLoved,
  isFavoriting = false,
  onToggleLove,
  onToggleLyrics,
  showLyricsButton = true
}) => {
  if (!track) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          minWidth: '280px',
        }}
      >
        <AlbumArtDisplay
          size={64}
          useTokens={false}
          title="No track"
          album="No track"
        />

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="body2"
            sx={{
              color: '#8b92b0',
              fontSize: '13px',
            }}
          >
            No track playing
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        minWidth: '280px',
      }}
    >
      {/* Album Art */}
      <AlbumArtContainer>
        <AlbumArtComponent
          track={track}
          size={64}
          showPlayButton={false}
        />
      </AlbumArtContainer>

      {/* Track metadata */}
      <Box
        sx={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
        }}
      >
        {/* Track title */}
        <Typography
          variant="body1"
          sx={{
            color: '#ffffff',
            fontWeight: 500,
            fontSize: '14px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {track.title}
        </Typography>

        {/* Artist name */}
        {track.artist && (
          <Typography
            variant="body2"
            sx={{
              color: '#8b92b0',
              fontSize: '12px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {track.artist}
          </Typography>
        )}
      </Box>

      {/* Action buttons */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
        }}
      >
        {/* Favorite button */}
        <Tooltip title={isLoved ? "Remove from favorites (L)" : "Add to favorites (L)"} arrow>
          <span>
            <IconButton
              onClick={onToggleLove}
              disabled={isFavoriting}
              size="small"
              sx={{
                color: isLoved ? '#e91e63' : '#8b92b0',
                '&:hover': {
                  color: '#e91e63',
                  transform: 'scale(1.1)',
                },
                transition: 'all 0.2s ease',
                opacity: isFavoriting ? 0.5 : 1,
              }}
            >
              {isLoved ? <Favorite /> : <FavoriteOutlined />}
            </IconButton>
          </span>
        </Tooltip>

        {/* Lyrics button */}
        {showLyricsButton && onToggleLyrics && (
          <Tooltip title="Toggle lyrics" arrow>
            <IconButton
              onClick={onToggleLyrics}
              size="small"
              sx={{
                color: '#8b92b0',
                '&:hover': {
                  color: '#667eea',
                  transform: 'scale(1.1)',
                },
                transition: 'all 0.2s ease',
              }}
            >
              <LyricsIcon />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
};

export default TrackInfo;
