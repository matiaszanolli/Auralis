import { useState, useCallback } from 'react';
import { Container } from '@mui/material';
import { ApiErrorHandler } from '@/types/api';
import { tokens } from '@/design-system';
import { EmptyState } from '@/components/shared/ui/feedback';
import DetailLoading from './DetailLoading';
import type { DetailTrack as Track } from '@/types/domain';
import { usePlayTrack } from '@/hooks/player';
import { useArtistDetailsData } from './useArtistDetailsData';
import { ArtistDetailHeaderSection } from './ArtistDetailHeader';
import { ArtistDetailTabsSection } from './ArtistDetailTabs';

interface ArtistDetailViewProps {
  artistId: number;
  artistName?: string;
  onBack?: () => void;
  onAlbumClick?: (albumId: number) => void;
}

/**
 * ArtistDetailView - Detailed artist view with albums and tracks
 *
 * Displays:
 * - Artist header (avatar, name, stats, play controls)
 * - Tab-based navigation (Albums and All Tracks)
 * - Albums grid or tracks table
 * - Loading and error states
 *
 * Orchestrates header, tabs, and data fetching via extracted modules
 */
export const ArtistDetailView = ({
  artistId,
  onBack,
  onAlbumClick,
}: ArtistDetailViewProps) => {
  const { artist, loading, error } = useArtistDetailsData(artistId);
  const [activeTab, setActiveTab] = useState(0);
  const { playTrack } = usePlayTrack();

  // Handle play all - plays first track
  const handlePlayAll = () => {
    if (artist?.tracks && artist.tracks.length > 0) {
      playTrack(artist.tracks[0]);
    }
  };

  // Handle shuffle play - plays random track
  const handleShufflePlay = () => {
    if (artist?.tracks && artist.tracks.length > 0) {
      const randomIndex = Math.floor(Math.random() * artist.tracks.length);
      playTrack(artist.tracks[randomIndex]);
    }
  };

  // Handle track click - play the selected track. useCallback so ArtistTrackRow's
  // React.memo isn't defeated by a fresh closure each render (#4472).
  const handleTrackClick = useCallback((track: Track) => {
    playTrack(track);
  }, [playTrack]);

  // Handle album click - delegates to parent
  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  // Loading state
  if (loading) {
    return <DetailLoading />;
  }

  // Error or not found state
  if (error || !artist) {
    // #4643: a 404 (stale/deleted artist link) is recoverable and reads
    // better as "not found" than as a generic failure; a real 500/network
    // error keeps the distinct "Error Loading" framing + message — see the
    // sibling AlbumDetailView for the identical fix and full rationale.
    const notFound = !error || ApiErrorHandler.isNotFound(error);
    return (
      <Container maxWidth="xl" sx={{
        py: tokens.spacing.xl,
        px: tokens.spacing.lg,
      }} role="alert" aria-live="assertive">
        <EmptyState
          title={notFound ? 'Artist not found' : 'Error Loading Artist'}
          description={notFound ? undefined : error?.message}
        />
      </Container>
    );
  }

  // Main render - orchestrates header and tabs sections
  return (
    <Container maxWidth="xl" sx={{
      py: tokens.spacing.xl,
      px: tokens.spacing.lg,
    }}>
      <ArtistDetailHeaderSection
        artist={artist}
        onBack={onBack}
        onPlayAll={handlePlayAll}
        onShuffle={handleShufflePlay}
      />

      <ArtistDetailTabsSection
        artist={artist}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onTrackClick={handleTrackClick}
        onAlbumClick={handleAlbumClick}
      />
    </Container>
  );
};

export default ArtistDetailView;
