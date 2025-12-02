/**
 * ArtistDetailTabs Component
 *
 * Tab navigation for albums and tracks
 */

import React from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import AlbumsTab from '../Views/AlbumsTab';
import TracksTab from '../Views/TracksTab';

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
    <Box sx={{ mt: tokens.spacing.xl }}>
      <Tabs
        value={activeTab}
        onChange={(e, newValue) => onTabChange(newValue)}
        sx={{
          borderBottom: `1px solid ${tokens.colors.border.light}`,
          marginBottom: tokens.spacing.lg,
          '& .MuiTabs-indicator': {
            background: tokens.gradients.aurora,
            height: '3px',
            borderRadius: tokens.borderRadius.full,
          },
          '& .MuiTab-root': {
            color: tokens.colors.text.secondary,
            fontWeight: tokens.typography.fontWeight.semibold,
            fontSize: tokens.typography.fontSize.md,
            transition: tokens.transitions.all,
            textTransform: 'none',
            '&:hover': {
              color: tokens.colors.text.primary,
            },
            '&.Mui-selected': {
              color: tokens.colors.accent.primary,
            },
          },
        }}
      >
        <Tab label={`Albums (${artist.albums?.length || 0})`} />
        <Tab label={`All Tracks (${artist.tracks?.length || 0})`} />
      </Tabs>

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
