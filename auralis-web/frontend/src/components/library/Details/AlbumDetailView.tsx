/**
 * AlbumDetailView Component (Refactored + Phase 4: Emotional Anchor)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Album detail view with modular subcomponents:
 * - useAlbumDetails - Data fetching and state management
 * - AlbumHeaderActions - Album header with artwork and controls
 * - AlbumTrackTable - Track listing (existing component)
 * - useArtworkPalette - Phase 4: Extract colors from artwork for theming
 *
 * Phase 4 Enhancements:
 * - Subtle background gradient derived from album artwork (8% opacity)
 * - Artwork glow effect using vibrant colors (15% opacity)
 * - Smooth color transitions when navigating between albums
 */

import React, { useState, useCallback } from 'react';

import { tokens } from '@/design-system';
import { EmptyState } from '../../shared/ui/feedback';
import { SimilarTracksModal } from '../../shared/SimilarTracksModal';
import AlbumTrackTable from '../Items/tables/AlbumTrackTable';
import AlbumHeaderActions from './AlbumHeaderActions';
import { useAlbumDetails, type Track } from './useAlbumDetails';
import { useArtworkPalette } from '@/hooks/app/useArtworkPalette';
import { useAlbumFingerprint } from '@/hooks/fingerprint/useAlbumFingerprint';
import { AlbumCharacterPane } from '../AlbumCharacterPane';
import { ArrowBack } from '@mui/icons-material';
import { Button, IconButton } from '@/design-system';
import { Box, Container, Skeleton } from '@mui/material';

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

  // Fetch album fingerprint for character pane
  const { fingerprint, isLoading: fingerprintLoading } = useAlbumFingerprint(albumId);

  // Phase 4: Extract artwork colors for theming
  const { palette, gradient, glow } = useArtworkPalette(albumId, !loading && !error);

  // Phase 5: Similar tracks modal state
  const [similarTracksModalOpen, setSimilarTracksModalOpen] = useState(false);
  const [similarTrackId, setSimilarTrackId] = useState<number | null>(null);
  const [similarTrackTitle, setSimilarTrackTitle] = useState<string>('');

  const handleFindSimilar = useCallback((trackId: number) => {
    const track = album?.tracks?.find((t: Track) => t.id === trackId);
    setSimilarTrackId(trackId);
    setSimilarTrackTitle(track?.title || 'this track');
    setSimilarTracksModalOpen(true);
  }, [album?.tracks]);

  const handleCloseSimilarTracksModal = useCallback(() => {
    setSimilarTracksModalOpen(false);
    setSimilarTrackId(null);
    setSimilarTrackTitle('');
  }, []);

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
    <Box
      sx={{
        // Phase 4: Artwork-based background gradient (very subtle, 8% opacity)
        background: gradient !== 'transparent' ? gradient : 'transparent',
        transition: `background ${tokens.transitions.slow}`, // 500-600ms smooth color fade
        minHeight: '100vh', // Full viewport height for immersive experience
        display: 'flex',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Main content area */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
        }}
      >
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

          {/* Album Header with Actions - Phase 4: Pass artwork glow */}
          <AlbumHeaderActions
            album={album}
            isPlaying={isPlaying}
            currentTrackId={currentTrackId}
            isFavorite={isFavorite}
            savingFavorite={savingFavorite}
            onPlay={handlePlayAlbum}
            onToggleFavorite={toggleFavorite}
            artworkGlow={glow !== 'none' ? glow : undefined} // Phase 4: Pass extracted glow
          />

          {/* Track Listing */}
          <AlbumTrackTable
            tracks={album.tracks || []}
            currentTrackId={currentTrackId}
            isPlaying={isPlaying}
            onTrackClick={handleTrackClick}
            onFindSimilar={handleFindSimilar}
            formatDuration={formatDuration}
          />

          {/* Phase 5: Similar Tracks Modal */}
          <SimilarTracksModal
            open={similarTracksModalOpen}
            trackId={similarTrackId}
            trackTitle={similarTrackTitle}
            onClose={handleCloseSimilarTracksModal}
            onTrackPlay={(trackId) => {
              const track = album.tracks?.find((t: Track) => t.id === trackId);
              if (track && onTrackPlay) {
                onTrackPlay(track);
              }
            }}
            limit={20}
          />
        </Container>
      </Box>

      {/* Album Character Pane - Right sidebar */}
      <AlbumCharacterPane
        fingerprint={fingerprint ?? null}
        albumTitle={album.title}
        isLoading={fingerprintLoading}
      />
    </Box>
  );
};

export default AlbumDetailView;
