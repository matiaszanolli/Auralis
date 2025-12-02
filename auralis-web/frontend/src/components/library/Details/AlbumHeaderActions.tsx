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
import { Box } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import DetailViewHeader from './DetailViewHeader';
import AlbumArt from '../../album/AlbumArt';
import { AlbumMetadata } from './AlbumMetadata';
import { AlbumActionButtons } from './AlbumActionButtons';
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
  return (
    <DetailViewHeader
      artwork={
        <Box sx={{
          width: '280px',
          height: '280px',
          borderRadius: tokens.borderRadius.lg,
          overflow: 'hidden',
          boxShadow: tokens.shadows.lg,
          transition: tokens.transitions.all,
          '&:hover': {
            transform: 'scale(1.02)',
            boxShadow: tokens.shadows.glowMd,
          },
        }}>
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
        <AlbumMetadata
          year={album.year}
          trackCount={album.track_count}
          totalDuration={album.total_duration}
          genre={album.genre}
        />
      }
      actions={
        <AlbumActionButtons
          isPlaying={isPlaying && currentTrackId === album.tracks?.[0]?.id}
          isFavorite={isFavorite}
          savingFavorite={savingFavorite}
          firstTrackId={album.tracks?.[0]?.id}
          onPlay={onPlay}
          onToggleFavorite={onToggleFavorite}
        />
      }
    />
  );
};

export default AlbumHeaderActions;
