/**
 * TrackInfo - Display current track information
 *
 * Features:
 * - Album artwork with fallback
 * - Track title and artist
 * - Favorite button toggle
 * - Text truncation for long names
 * - Smooth animations
 */

import React, { useState } from 'react';
import { Box, Typography, IconButton, Tooltip, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import FavoriteIcon from '@mui/icons-material/Favorite';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';
import LyricsIcon from '@mui/icons-material/Lyrics';
import AlbumArtDisplay from '../shared/AlbumArtDisplay';

interface TrackInfoProps {
  track: {
    id?: number;
    title?: string;
    artist?: string;
    album?: string;
    artwork_url?: string;
  } | null;
  onToggleLyrics?: () => void;
  showLyricsButton?: boolean;
}

const TrackInfoContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,
  minWidth: 0, // Enable flex item shrinking
  maxWidth: '400px',
});


const TrackDetails = styled(Box)({
  minWidth: 0, // Enable text truncation
  flex: 1,
});

const TitleContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.sm,
  minWidth: 0,
});

const ActionButtonsContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.xs,
  flexShrink: 0,
});

const ActionButton = styled(IconButton)({
  color: tokens.colors.text.secondary,
  padding: 0,
  minWidth: '24px',
  width: '24px',
  height: '24px',
  flexShrink: 0,
  transition: tokens.transitions.all,

  '&:hover': {
    color: tokens.colors.accent.error,
    transform: 'scale(1.2)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

const TrackTitle = styled(Typography)({
  fontSize: tokens.typography.fontSize.base,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.primary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: tokens.typography.lineHeight.tight,
  marginBottom: tokens.spacing.xs,
});

const TrackArtist = styled(Typography)({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  lineHeight: tokens.typography.lineHeight.tight,
  transition: tokens.transitions.color,

  '&:hover': {
    color: tokens.colors.text.primary,
  },
});

export const TrackInfo: React.FC<TrackInfoProps> = React.memo(({
  track,
  onToggleLyrics,
  showLyricsButton = true
}) => {
  const [isFavorite, setIsFavorite] = useState(false);

  const handleFavoriteToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFavorite(!isFavorite);
  };

  if (!track) {
    return (
      <TrackInfoContainer>
        <AlbumArtDisplay
          size={56}
          title="No track"
          album="No track"
        />
        <TrackDetails>
          <TrackTitle>No track playing</TrackTitle>
          <TrackArtist>Select a track to start</TrackArtist>
        </TrackDetails>
      </TrackInfoContainer>
    );
  }

  return (
    <TrackInfoContainer>
      <AlbumArtDisplay
        size={56}
        artworkPath={track.artwork_url}
        title={track.title}
        album={track.album}
      />

      <TrackDetails>
        <TitleContainer>
          <TrackTitle title={track.title} sx={{ flex: 1 }}>
            {track.title || 'Unknown Track'}
          </TrackTitle>
          <ActionButtonsContainer>
            <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'} arrow>
              <ActionButton
                onClick={handleFavoriteToggle}
                aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                size="small"
              >
                {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
              </ActionButton>
            </Tooltip>
            {showLyricsButton && onToggleLyrics && (
              <Tooltip title="Toggle lyrics" arrow>
                <ActionButton
                  onClick={onToggleLyrics}
                  aria-label="Toggle lyrics"
                  size="small"
                >
                  <LyricsIcon />
                </ActionButton>
              </Tooltip>
            )}
          </ActionButtonsContainer>
        </TitleContainer>
        <TrackArtist title={track.artist}>
          {track.artist || 'Unknown Artist'}
        </TrackArtist>
      </TrackDetails>
    </TrackInfoContainer>
  );
});

TrackInfo.displayName = 'TrackInfo';
