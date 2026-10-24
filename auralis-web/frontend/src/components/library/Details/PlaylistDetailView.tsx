/**
 * PlaylistDetailView Component
 *
 * Shows one playlist's tracks under the playlist's own name (#6007). Before
 * this view existed, clicking a playlist in the sidebar set a `playlist-N`
 * view id that nothing routed — CozyLibraryView fell through to the Songs
 * config and paginated the ENTIRE library under a "Songs" heading, and
 * bulk actions there acted on library tracks as if they were playlist
 * members.
 *
 * Structure mirrors AlbumDetailView: data hook + header + shared track
 * table. The header is deliberately minimal (no artwork palette, no
 * favorite toggle — playlists have neither).
 */

import { useState, useCallback } from 'react';
import { ApiErrorHandler } from '@/types/api';
import { tokens } from '@/design-system';
import { formatDuration } from '@/utils/timeFormat';
import { EmptyState } from '@/components/shared/ui/feedback';
import { SimilarTracksModal } from '@/components/shared/SimilarTracksModal';
import AlbumTrackTable from '@/components/library/Items/tables/AlbumTrackTable';
import type { Track } from '@/types/domain';
import { usePlayTrack } from '@/hooks/player';
import { usePlaylistDetails } from './usePlaylistDetails';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { Button, IconButton } from '@/design-system';
import { Box, Container, Skeleton, Typography } from '@mui/material';
import { themeVars } from '@/theme/semanticTheme';

interface PlaylistDetailViewProps {
  playlistId: number;
  /** Back navigation; supplied by CozyLibraryView (routes to 'songs'). */
  onBack?: () => void;
}

export const PlaylistDetailView = ({
  playlistId,
  onBack,
}: PlaylistDetailViewProps) => {
  const { playlist, loading, error } = usePlaylistDetails(playlistId);
  const { playTrack } = usePlayTrack();

  const [similarTracksModalOpen, setSimilarTracksModalOpen] = useState(false);
  const [similarTrackId, setSimilarTrackId] = useState<number | null>(null);
  const [similarTrackTitle, setSimilarTrackTitle] = useState<string>('');

  const handleFindSimilar = useCallback((trackId: number) => {
    const track = playlist?.tracks?.find((t: Track) => t.id === trackId);
    setSimilarTrackId(trackId);
    setSimilarTrackTitle(track?.title || 'this track');
    setSimilarTracksModalOpen(true);
  }, [playlist?.tracks]);

  const handleCloseSimilarTracksModal = useCallback(() => {
    setSimilarTracksModalOpen(false);
    setSimilarTrackId(null);
    setSimilarTrackTitle('');
  }, []);

  const handlePlayPlaylist = () => {
    if (playlist?.tracks && playlist.tracks.length > 0) {
      playTrack(playlist.tracks[0]);
    }
  };

  // Stable identity so track rows' React.memo isn't defeated by a fresh
  // closure on every render (#4472, same as AlbumDetailView).
  const handleTrackClick = useCallback((track: Track) => {
    playTrack(track);
  }, [playTrack]);

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: tokens.spacing.xl, px: tokens.spacing.lg }}
        role="status" aria-live="polite" aria-label="Loading playlist details">
        <Skeleton variant="rectangular" height={120}
          sx={{ borderRadius: tokens.borderRadius.lg, mb: tokens.spacing.xl }} />
        <Skeleton variant="rectangular" height={300}
          sx={{ borderRadius: tokens.borderRadius.lg }} />
      </Container>
    );
  }

  if (error || !playlist) {
    // A 404 here usually means the playlist was just deleted elsewhere
    // (stale sidebar link) — same recovery framing as AlbumDetailView
    // (#4643).
    const notFound = !error || ApiErrorHandler.isNotFound(error);
    return (
      <Container maxWidth="xl" sx={{ py: tokens.spacing.xl, px: tokens.spacing.lg }}>
        <EmptyState
          title={notFound ? 'Playlist not found' : 'Error Loading Playlist'}
          description={notFound ? undefined : error?.message}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: tokens.spacing.lg }}>
            <Button
              onClick={onBack}
              startIcon={<ArrowBack />}
              sx={{
                background: tokens.gradients.aurora,
                color: themeVars.textPrimary,
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
              Back to Songs
            </Button>
          </Box>
        )}
      </Container>
    );
  }

  const tracks = playlist.tracks ?? [];
  const totalDuration = tracks.reduce((sum, t) => sum + (t.duration || 0), 0);

  return (
    <Container maxWidth="xl" sx={{ py: tokens.spacing.xl, px: tokens.spacing.lg }}>
      {onBack && (
        <IconButton
          onClick={onBack}
          aria-label="Go back to songs"
          sx={{
            mb: tokens.spacing.md,
            color: themeVars.textSecondary,
            border: `1px solid ${tokens.colors.border.light}`,
            borderRadius: tokens.borderRadius.md,
            padding: tokens.spacing.sm,
            transition: tokens.transitions.all,
            '&:hover': {
              backgroundColor: themeVars.surfaceSecondary,
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

      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: tokens.spacing.md, mb: tokens.spacing.lg, flexWrap: 'wrap' }}>
        <Typography variant="h4" component="h1" sx={{ color: themeVars.textPrimary, fontWeight: tokens.typography.fontWeight.bold }}>
          {playlist.name}
        </Typography>
        <Typography variant="body2" sx={{ color: themeVars.textSecondary }}>
          {tracks.length} {tracks.length === 1 ? 'track' : 'tracks'} · {formatDuration(totalDuration)}
        </Typography>
        <Button
          onClick={handlePlayPlaylist}
          disabled={tracks.length === 0}
          size="small"
          sx={{
            background: tokens.gradients.aurora,
            color: themeVars.textPrimary,
            fontWeight: tokens.typography.fontWeight.semibold,
            borderRadius: tokens.borderRadius.md,
            textTransform: 'none',
            '&:hover': { boxShadow: tokens.shadows.glowMd },
          }}
        >
          Play
        </Button>
      </Box>

      {tracks.length === 0 ? (
        <EmptyState
          title="This playlist is empty"
          description="Add tracks from the Songs view via the context menu or drag & drop."
        />
      ) : (
        <AlbumTrackTable
          tracks={tracks}
          onTrackClick={handleTrackClick}
          onFindSimilar={handleFindSimilar}
          formatDuration={formatDuration}
        />
      )}

      <SimilarTracksModal
        open={similarTracksModalOpen}
        trackId={similarTrackId}
        trackTitle={similarTrackTitle}
        onClose={handleCloseSimilarTracksModal}
        onTrackPlay={(trackId) => {
          const track = tracks.find((t: Track) => t.id === trackId);
          if (track) {
            playTrack(track);
          }
        }}
        limit={20}
      />
    </Container>
  );
};

export default PlaylistDetailView;
