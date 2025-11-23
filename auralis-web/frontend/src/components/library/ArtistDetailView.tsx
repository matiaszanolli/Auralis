import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Button,
  Tab,
  IconButton
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { EmptyState } from '../shared/EmptyState';
import { StyledTabs } from './ArtistDetail.styles';
import ArtistHeader from './ArtistHeader';
import AlbumsTab from './AlbumsTab';
import TracksTab from './TracksTab';
import DetailLoading from './DetailLoading';

interface Track {
  id: number;
  title: string;
  album: string;
  duration: number;
  track_number?: number;
}

interface Album {
  id: number;
  title: string;
  year?: number;
  track_count: number;
  total_duration: number;
}

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
  albums?: Album[];
  tracks?: Track[];
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
 * Orchestrates 4 subcomponents for album/track display
 */
export const ArtistDetailView: React.FC<ArtistDetailViewProps> = ({
  artistId,
  artistName,
  onBack,
  onTrackPlay,
  onAlbumClick,
  currentTrackId,
  isPlaying = false
}) => {
  const [artist, setArtist] = useState<Artist | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    fetchArtistDetails();
  }, [artistId]);

  const fetchArtistDetails = async () => {
    setLoading(true);
    setError(null);

    try {
      // Use new REST API endpoint for artist details
      const response = await fetch(`/api/artists/${artistId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch artist details');
      }

      const data = await response.json();

      // Transform API response to match Artist interface
      const artistData: Artist = {
        id: data.artist_id,
        name: data.artist_name,
        album_count: data.total_albums,
        track_count: data.total_tracks,
        albums: data.albums || [],
        tracks: [] // Tracks loaded separately if needed
      };

      setArtist(artistData);
    } catch (err) {
      console.error('Error fetching artist details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load artist details');
    } finally {
      setLoading(false);
    }
  };

  const handlePlayAll = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      onTrackPlay(artist.tracks[0]);
    }
  };

  const handleShufflePlay = () => {
    if (artist?.tracks && artist.tracks.length > 0 && onTrackPlay) {
      const randomIndex = Math.floor(Math.random() * artist.tracks.length);
      onTrackPlay(artist.tracks[randomIndex]);
    }
  };

  const handleTrackClick = (track: Track) => {
    if (onTrackPlay) {
      onTrackPlay(track);
    }
  };

  const handleAlbumCardClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  if (loading) {
    return <DetailLoading />;
  }

  if (error || !artist) {
    return (
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <EmptyState
          title={error ? 'Error Loading Artist' : 'Artist not found'}
          description={error || undefined}
        />
        {onBack && (
          <Box sx={{ textAlign: 'center', mt: 2 }}>
            <Button onClick={onBack} startIcon={<ArrowBack />}>
              Back to Artists
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
              backgroundColor: 'rgba(255,255,255,0.1)'
            }
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      {/* Artist Header */}
      <ArtistHeader
        artist={artist}
        onPlayAll={handlePlayAll}
        onShuffle={handleShufflePlay}
      />

      {/* Tabs for Albums and Tracks */}
      <Box>
        <StyledTabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
          <Tab label={`Albums (${artist.albums?.length || 0})`} />
          <Tab label={`All Tracks (${artist.tracks?.length || 0})`} />
        </StyledTabs>

        {/* Albums Tab */}
        {activeTab === 0 && (
          <AlbumsTab
            albums={artist.albums || []}
            onAlbumClick={handleAlbumCardClick}
          />
        )}

        {/* Tracks Tab */}
        {activeTab === 1 && (
          <TracksTab
            tracks={artist.tracks || []}
            currentTrackId={currentTrackId}
            isPlaying={isPlaying}
            onTrackClick={handleTrackClick}
          />
        )}
      </Box>
    </Container>
  );
};

export default ArtistDetailView;
