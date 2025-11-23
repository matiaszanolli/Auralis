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
