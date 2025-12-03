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
import { tokens } from '@/design-system/tokens';
import { EmptyState } from '../../shared/ui/feedback';
import AlbumTrackTable from '../Items/tables/AlbumTrackTable';
import AlbumHeaderActions from './AlbumHeaderActions';
import { useAlbumDetails, type Track } from './useAlbumDetails';
import { ArrowBack } from '@mui/icons-material';

interface AlbumDetailViewProps {
  albumId: number;
  onBack?: () => void;
  onTrackPlay?: (track: Track) => void | Promise<void>;
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
      <Container maxWidth="xl" sx={{
        py: tokens.spacing.xl,
        px: tokens.spacing.lg,
      }} role="status" aria-live="polite" aria-label="Loading album details">
        <Skeleton
          variant="rectangular"
          height={400}
          sx={{
            borderRadius: tokens.borderRadius.lg,
            mb: tokens.spacing.xl,
          }}
        />
        <Skeleton
          variant="rectangular"
          height={300}
          sx={{
            borderRadius: tokens.borderRadius.lg,
          }}
        />
      </Container>
    );
  }

  if (error || !album) {
    return (
      <Container maxWidth="xl" sx={{
        py: tokens.spacing.xl,
        px: tokens.spacing.lg,
      }}>
        <EmptyState
          title={error ? 'Error Loading Album' : 'Album not found'}
          description={error || undefined}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: tokens.spacing.lg }}>
            <Button
              onClick={onBack}
              startIcon={<ArrowBack />}
              sx={{
                background: tokens.gradients.aurora,
                color: tokens.colors.text.primary,
                fontWeight: tokens.typography.fontWeight.semibold,
                padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
                borderRadius: tokens.borderRadius.md,
                border: 'none',
                transition: tokens.transitions.all,
                boxShadow: tokens.shadows.md,
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: tokens.shadows.glowMd,
                },
              }}
            >
              Back to Albums
            </Button>
          </Box>
        )}
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{
      py: tokens.spacing.xl,
      px: tokens.spacing.lg,
    }}>
      {/* Back Button */}
      {onBack && (
        <IconButton
          onClick={onBack}
          aria-label="Go back to albums library"
          sx={{
            mb: tokens.spacing.lg,
            color: tokens.colors.text.secondary,
            border: `1px solid ${tokens.colors.border.light}`,
            borderRadius: tokens.borderRadius.md,
            padding: tokens.spacing.sm,
            transition: tokens.transitions.all,
            '&:hover': {
              backgroundColor: tokens.colors.bg.tertiary,
              borderColor: tokens.colors.accent.primary,
              transform: 'scale(1.05)',
            },
            '&:focus-visible': {
              outline: `3px solid ${tokens.colors.accent.primary}`,
              outlineOffset: '2px',
            },
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
