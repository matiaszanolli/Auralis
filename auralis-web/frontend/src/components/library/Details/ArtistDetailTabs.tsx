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
    <Box sx={{ mt: tokens.spacing['2xl'] }}> {/* Increased spacing */}
      <Tabs
        value={activeTab}
        onChange={(e, newValue) => onTabChange(newValue)}
        aria-label="Artist content sections"
        sx={{
          borderBottom: `2px solid ${tokens.colors.border.light}`,  // Tab border
          marginBottom: tokens.spacing.xl,                    // Breathing room
          paddingTop: tokens.spacing.lg,                      // Vertical spacing
          '& .MuiTabs-indicator': {
            background: tokens.gradients.aurora,
            height: '4px',                                    // Active indicator strength
            borderRadius: tokens.borderRadius.full,           // 9999px - pill shape
            boxShadow: `0 0 8px ${tokens.colors.accent.primary}40`,  // 40% glow
          },
          '& .MuiTab-root': {
            color: tokens.colors.text.secondary,
            fontWeight: tokens.typography.fontWeight.semibold,
            fontSize: tokens.typography.fontSize.lg,          // 16px
            transition: tokens.transitions.all,
            textTransform: 'none',
            minHeight: '56px',                                // Vertical space (organic)
            paddingTop: tokens.spacing.md,
            paddingBottom: tokens.spacing.md,
            '&:hover': {
              color: tokens.colors.text.primary,
              transform: 'translateY(-2px)',                  // Subtle lift (2px)
            },
            '&.Mui-selected': {
              color: tokens.colors.accent.primary,
              fontWeight: tokens.typography.fontWeight.bold,
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
