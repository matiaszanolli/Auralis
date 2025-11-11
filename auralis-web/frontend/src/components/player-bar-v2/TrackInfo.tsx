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
import { Box, Typography, IconButton, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import MusicNoteIcon from '@mui/icons-material/MusicNote';
import FavoriteIcon from '@mui/icons-material/Favorite';
import FavoriteBorderIcon from '@mui/icons-material/FavoriteBorder';

interface TrackInfoProps {
  track: {
    title?: string;
    artist?: string;
    album?: string;
    artwork_url?: string;
  } | null;
}

const TrackInfoContainer = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  gap: tokens.spacing.md,
  minWidth: 0, // Enable flex item shrinking
  maxWidth: '400px',
});

const AlbumArtwork = styled(Box)({
  width: '56px',
  height: '56px',
  borderRadius: tokens.borderRadius.md,
  overflow: 'hidden',
  flexShrink: 0,
  background: tokens.colors.bg.elevated,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  boxShadow: tokens.shadows.md,
  transition: tokens.transitions.transform,

  '& img': {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },

  '&:hover': {
    transform: 'scale(1.05)',
  },
});

const ArtworkPlaceholder = styled(Box)({
  color: tokens.colors.text.tertiary,
  fontSize: '24px',
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

const FavoriteButton = styled(IconButton)({
  color: tokens.colors.text.secondary,
  padding: 0,
  minWidth: '24px',
  width: '24px',
  height: '24px',
  flexShrink: 0,
  transition: tokens.transitions.all,

  '&:hover': {
    color: tokens.colors.status.error,
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

export const TrackInfo: React.FC<TrackInfoProps> = React.memo(({ track }) => {
  const [isFavorite, setIsFavorite] = useState(false);

  const handleFavoriteToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFavorite(!isFavorite);
  };

  if (!track) {
    return (
      <TrackInfoContainer>
        <AlbumArtwork>
          <ArtworkPlaceholder>
            <MusicNoteIcon fontSize="inherit" />
          </ArtworkPlaceholder>
        </AlbumArtwork>
        <TrackDetails>
          <TrackTitle>No track playing</TrackTitle>
          <TrackArtist>Select a track to start</TrackArtist>
        </TrackDetails>
      </TrackInfoContainer>
    );
  }

  return (
    <TrackInfoContainer>
      <AlbumArtwork>
        {track.artwork_url ? (
          <img
            src={track.artwork_url}
            alt={`${track.album || 'Album'} artwork`}
            loading="lazy"
          />
        ) : (
          <ArtworkPlaceholder>
            <MusicNoteIcon fontSize="inherit" />
          </ArtworkPlaceholder>
        )}
      </AlbumArtwork>

      <TrackDetails>
        <TitleContainer>
          <TrackTitle title={track.title} sx={{ flex: 1 }}>
            {track.title || 'Unknown Track'}
          </TrackTitle>
          <FavoriteButton
            onClick={handleFavoriteToggle}
            aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
            size="small"
          >
            {isFavorite ? <FavoriteIcon /> : <FavoriteBorderIcon />}
          </FavoriteButton>
        </TitleContainer>
        <TrackArtist title={track.artist}>
          {track.artist || 'Unknown Artist'}
        </TrackArtist>
      </TrackDetails>
    </TrackInfoContainer>
  );
});

TrackInfo.displayName = 'TrackInfo';
