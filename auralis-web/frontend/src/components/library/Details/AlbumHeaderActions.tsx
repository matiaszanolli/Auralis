/**
 * AlbumHeaderActions Component
 *
 * Album header with metadata and action buttons:
 * - Album artwork display
 * - Title, artist, year, genre
 * - Play, favorite, queue, more actions buttons
 *
 * Usage:
 * ```tsx
 * <AlbumHeaderActions
 *   album={albumData}
 *   isPlaying={isPlaying}
 *   currentTrackId={currentTrackId}
 *   isFavorite={isFavorite}
 *   savingFavorite={savingFavorite}
 *   onPlay={handlePlayAlbum}
 *   onToggleFavorite={toggleFavorite}
 * />
 * ```
 */

import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  AddToQueue,
  MoreVert,
  Favorite,
  FavoriteBorder
} from '@mui/icons-material';
import DetailViewHeader from './DetailViewHeader';
import { PlayButton } from '../Styles/Button.styles';
import AlbumArt from '../album/AlbumArt';
import { auroraOpacity } from '../Styles/Color.styles';
import { tokens } from '@/design-system/tokens';
import type { Album } from './useAlbumDetails';

interface AlbumHeaderActionsProps {
  album: Album;
  isPlaying?: boolean;
  currentTrackId?: number;
  isFavorite: boolean;
  savingFavorite: boolean;
  onPlay: () => void;
  onToggleFavorite: () => void;
}

export const AlbumHeaderActions: React.FC<AlbumHeaderActionsProps> = ({
  album,
  isPlaying = false,
  currentTrackId,
  isFavorite,
  savingFavorite,
  onPlay,
  onToggleFavorite,
}) => {
  const formatTotalDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours} hr ${mins} min`;
    }
    return `${mins} min`;
  };

  return (
    <DetailViewHeader
      artwork={
        <Box sx={{ width: 280, height: 280, borderRadius: 1.5, overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.19)' }}>
          <AlbumArt
            albumId={album.id}
            size={280}
            borderRadius={0}
          />
        </Box>
      }
      title={album.title}
      subtitle={album.artist_name || album.artist}
      metadata={
        <Box>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            {album.year && `${album.year} • `}
            {album.track_count} {album.track_count === 1 ? 'track' : 'tracks'}
            {' • '}
            {formatTotalDuration(album.total_duration)}
          </Typography>
          {album.genre && (
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Genre: {album.genre}
            </Typography>
          )}
        </Box>
      }
      actions={
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <PlayButton
            startIcon={isPlaying && currentTrackId === album.tracks?.[0]?.id ? <Pause /> : <PlayArrow />}
            onClick={onPlay}
          >
            {isPlaying && currentTrackId === album.tracks?.[0]?.id ? 'Pause' : 'Play Album'}
          </PlayButton>

          <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}>
            <IconButton
              onClick={onToggleFavorite}
              disabled={savingFavorite}
              sx={{
                color: isFavorite ? tokens.colors.accent.error : 'text.secondary',
                '&:hover': {
                  backgroundColor: auroraOpacity.ultraLight
                },
                '&:disabled': {
                  opacity: 0.6,
                  cursor: 'not-allowed'
                }
              }}
            >
              {isFavorite ? <Favorite /> : <FavoriteBorder />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Add to queue">
            <IconButton
              sx={{
                '&:hover': {
                  backgroundColor: auroraOpacity.ultraLight
                }
              }}
            >
              <AddToQueue />
            </IconButton>
          </Tooltip>

          <Tooltip title="More options">
            <IconButton
              sx={{
                '&:hover': {
                  backgroundColor: auroraOpacity.ultraLight
                }
              }}
            >
              <MoreVert />
            </IconButton>
          </Tooltip>
        </Box>
      }
    />
  );
};

export default AlbumHeaderActions;
