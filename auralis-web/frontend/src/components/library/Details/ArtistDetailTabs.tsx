/**
 * ArtistDetailTabs Component
 *
 * Tab navigation for albums and tracks
 */

import React from 'react';
import { Box, Tab } from '@mui/material';
import { StyledTabs } from '../Styles/ArtistDetail.styles';
import AlbumsTab from './AlbumsTab';
import TracksTab from './TracksTab';

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

interface ArtistDetailTabsProps {
  artist: Artist;
  activeTab: number;
  onTabChange: (newValue: number) => void;
  currentTrackId?: number;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  onAlbumClick: (albumId: number) => void;
}

export const ArtistDetailTabsSection: React.FC<ArtistDetailTabsProps> = ({
  artist,
  activeTab,
  onTabChange,
  currentTrackId,
  isPlaying,
  onTrackClick,
  onAlbumClick,
}) => {
  return (
    <Box>
      <StyledTabs value={activeTab} onChange={(e, newValue) => onTabChange(newValue)}>
        <Tab label={`Albums (${artist.albums?.length || 0})`} />
        <Tab label={`All Tracks (${artist.tracks?.length || 0})`} />
      </StyledTabs>

      {activeTab === 0 && (
        <AlbumsTab
          albums={artist.albums || []}
          onAlbumClick={onAlbumClick}
        />
      )}

      {activeTab === 1 && (
        <TracksTab
          tracks={artist.tracks || []}
          currentTrackId={currentTrackId}
          isPlaying={isPlaying}
          onTrackClick={onTrackClick}
        />
      )}
    </Box>
  );
};
