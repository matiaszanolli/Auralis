/**
 * ArtistDetailTabs Component
 *
 * Tab navigation for albums and tracks
 */

import React from 'react';
import { Box, Tab, Tabs } from '@mui/material';
import { tokens } from '@/design-system';
import AlbumsTab from '../Views/AlbumsTab';
import TracksTab from '../Views/TracksTab';
import { type Track, type Album, type Artist } from './useArtistDetailsData';

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
        aria-label="Artist content sections"
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
        <Tab label={`Albums (${artist.albums?.length || 0})`} id="albums-tab" aria-controls="albums-panel" />
        <Tab label={`All Tracks (${artist.tracks?.length || 0})`} id="tracks-tab" aria-controls="tracks-panel" />
      </Tabs>

      {activeTab === 0 && (
        <Box id="albums-panel" role="tabpanel" aria-labelledby="albums-tab">
          <AlbumsTab
            albums={artist.albums || []}
            onAlbumClick={onAlbumClick}
          />
        </Box>
      )}

      {activeTab === 1 && (
        <Box id="tracks-panel" role="tabpanel" aria-labelledby="tracks-tab">
          <TracksTab
            tracks={artist.tracks || []}
            currentTrackId={currentTrackId}
            isPlaying={isPlaying}
            onTrackClick={onTrackClick}
          />
        </Box>
      )}
    </Box>
  );
};
