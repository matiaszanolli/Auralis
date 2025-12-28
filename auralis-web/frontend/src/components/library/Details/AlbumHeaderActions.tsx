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
import { tokens } from '@/design-system';
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
  /** Phase 4: Artwork glow CSS (box-shadow) from color extraction */
  artworkGlow?: string;
}

export const AlbumHeaderActions: React.FC<AlbumHeaderActionsProps> = ({
  album,
  isPlaying = false,
  currentTrackId,
  isFavorite,
  savingFavorite,
  onPlay,
  onToggleFavorite,
  artworkGlow,
}) => {
  return (
    <DetailViewHeader
      isPlaying={isPlaying} // Phase 1: Reduce header opacity during playback
      artwork={
        <Box sx={{
          width: '280px',
          height: '280px',
          borderRadius: tokens.borderRadius.lg,
          overflow: 'hidden',
          // Phase 4: Use artwork-based glow if available, fallback to default shadow
          boxShadow: artworkGlow || tokens.shadows.lg,
          transition: tokens.transitions.all,
          '&:hover': {
            transform: 'scale(1.02)',
            // Phase 4: Intensify artwork glow on hover
            boxShadow: artworkGlow ? artworkGlow.replace(/0\.15\)/g, '0.25)') : tokens.shadows.glowMd,
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
