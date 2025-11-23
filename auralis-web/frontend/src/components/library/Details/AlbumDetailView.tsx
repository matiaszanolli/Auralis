/**
 * AlbumDetailView Component (Refactored)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Album detail view with modular subcomponents:
 * - useAlbumDetails - Data fetching and state management
 * - AlbumHeaderActions - Album header with artwork and controls
 * - AlbumTrackTable - Track listing (existing component)
 */

import React from 'react';
import {
  Box,
  Container,
  Button,
  Skeleton,
  IconButton,
} from '@mui/material';
import { EmptyState } from '../shared/EmptyState';
import AlbumTrackTable from './AlbumTrackTable';
import AlbumHeaderActions from './AlbumHeaderActions';
import { useAlbumDetails, Track } from './useAlbumDetails';
import { ArrowBack } from '@mui/icons-material';
import { auroraOpacity } from '../Styles/Color.styles';

interface AlbumDetailViewProps {
  albumId: number;
  onBack?: () => void;
  onTrackPlay?: (track: Track) => void;
  currentTrackId?: number;
  isPlaying?: boolean;
}

export const AlbumDetailView: React.FC<AlbumDetailViewProps> = ({
  albumId,
  onBack,
  onTrackPlay,
  currentTrackId,
  isPlaying = false
}) => {
  const { album, loading, error, isFavorite, savingFavorite, toggleFavorite } = useAlbumDetails(albumId);

  const formatDuration = (seconds: number): string => {
    const totalSeconds = Math.floor(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlayAlbum = () => {
    if (album?.tracks && album.tracks.length > 0 && onTrackPlay) {
      onTrackPlay(album.tracks[0]);
    }
  };

  const handleTrackClick = (track: Track) => {
    if (onTrackPlay) {
      onTrackPlay(track);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Skeleton variant="rectangular" height={400} sx={{ borderRadius: 2, mb: 4 }} />
        <Skeleton variant="rectangular" height={300} sx={{ borderRadius: 2 }} />
      </Container>
    );
  }

  if (error || !album) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <EmptyState
          title={error ? 'Error Loading Album' : 'Album not found'}
          description={error || undefined}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Button onClick={onBack} startIcon={<ArrowBack />}>
              Back to Albums
            </Button>
          </Box>
        )}
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Back Button */}
      {onBack && (
        <IconButton
          onClick={onBack}
          sx={{
            mb: 2,
            '&:hover': {
              backgroundColor: auroraOpacity.ultraLight
            }
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      {/* Album Header with Actions */}
      <AlbumHeaderActions
        album={album}
        isPlaying={isPlaying}
        currentTrackId={currentTrackId}
        isFavorite={isFavorite}
        savingFavorite={savingFavorite}
        onPlay={handlePlayAlbum}
        onToggleFavorite={toggleFavorite}
      />

      {/* Track Listing */}
      <AlbumTrackTable
        tracks={album.tracks || []}
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
        onTrackClick={handleTrackClick}
        formatDuration={formatDuration}
      />
    </Container>
  );
};

export default AlbumDetailView;
