import React, { useState } from 'react';
import { Container } from '@mui/material';
import { EmptyState } from '../../shared/ui/feedback';
import DetailLoading from './DetailLoading';
import { useArtistDetailsData } from './useArtistDetailsData';
import { ArtistDetailHeaderSection } from './ArtistDetailHeader';
import { ArtistDetailTabsSection } from './ArtistDetailTabs';

interface Track {
  id: number;
  title: string;
  album: string;
  duration: number;
  track_number?: number;
}

interface ArtistDetailViewProps {
  artistId: number;
  artistName?: string;
  onBack?: () => void;
  onTrackPlay?: (track: Track) => void;
  onAlbumClick?: (albumId: number) => void;
  currentTrackId?: number;
  isPlaying?: boolean;
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
export const ArtistDetailView: React.FC<ArtistDetailViewProps> = ({
  artistId,
  onBack,
  onTrackPlay,
  onAlbumClick,
  currentTrackId,
  isPlaying = false
}) => {
  const { artist, loading, error } = useArtistDetailsData(artistId);
  const [activeTab, setActiveTab] = useState(0);

  // Handle play all - plays first track
  const handlePlayAll = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      onTrackPlay(artist.tracks[0]);
    }
  };

  // Handle shuffle play - plays random track
  const handleShufflePlay = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      const randomIndex = Math.floor(Math.random() * artist.tracks.length);
      onTrackPlay(artist.tracks[randomIndex]);
    }
  };

  // Handle track click - delegates to parent
  const handleTrackClick = (track: Track) => {
    if (onTrackPlay) {
      onTrackPlay(track);
    }
  };

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
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <EmptyState
          title={error ? 'Error Loading Artist' : 'Artist not found'}
          description={error || undefined}
        />
      </Container>
    );
  }

  // Main render - orchestrates header and tabs sections
  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
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
        currentTrackId={currentTrackId}
        isPlaying={isPlaying}
        onTrackClick={handleTrackClick}
        onAlbumClick={handleAlbumClick}
      />
    </Container>
  );
};

export default ArtistDetailView;
