/**
 * SidebarContent - Main navigation content with library, collections, and playlists
 */

import React from 'react';
import { Box } from '@mui/material';
import { LibraryMusic, Album, Person, Favorite, History } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { SectionLabel } from './SidebarStyles';
import NavigationSection from './NavigationSection';
import PlaylistList from '../../playlist/PlaylistList';

interface SidebarContentProps {
  selectedItem: string;
  onItemClick: (itemId: string) => void;
}

export const SidebarContent: React.FC<SidebarContentProps> = ({ selectedItem, onItemClick }) => {
  // Navigation items definitions
  const libraryItems = [
    { id: 'songs', label: 'Songs', icon: <LibraryMusic /> },
    { id: 'albums', label: 'Albums', icon: <Album /> },
    { id: 'artists', label: 'Artists', icon: <Person /> },
    { id: 'favourites', label: 'Favourites', icon: <Favorite /> },
  ];

  const recentlyPlayedItem = [
    { id: 'recent', label: 'Recently Played', icon: <History /> },
  ];

  return (
    <Box sx={{
      flex: 1,
      overflowY: 'auto',
      overflowX: 'hidden',
      // Custom scrollbar for organic feel
      '&::-webkit-scrollbar': {
        width: '6px',
      },
      '&::-webkit-scrollbar-track': {
        background: 'transparent',
      },
      '&::-webkit-scrollbar-thumb': {
        background: tokens.colors.accent.primary,
        opacity: 0.3,
        borderRadius: tokens.borderRadius.sm,
        '&:hover': {
          opacity: 0.5,
        },
      },
    }}>
      {/* Library Section - Natural cluster */}
      <SectionLabel>Library</SectionLabel>
      <Box sx={{ marginBottom: tokens.spacing.section }}> {/* 32px section break after library cluster */}
        <NavigationSection
          items={libraryItems}
          selectedItem={selectedItem}
          onItemClick={onItemClick}
        />
      </Box>

      {/* Recently Played - Separate section with breathing room */}
      <Box sx={{ marginBottom: tokens.spacing.section }}> {/* 32px section break */}
        <NavigationSection
          items={recentlyPlayedItem}
          selectedItem={selectedItem}
          onItemClick={onItemClick}
        />
      </Box>

      {/* Playlists Section - Major section break */}
      <Box sx={{ marginTop: tokens.spacing.group }}> {/* 16px group spacing before playlists */}
        <PlaylistList
          selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
          onPlaylistSelect={(playlistId) => onItemClick(`playlist-${playlistId}`)}
          hideHeader={true}
        />
      </Box>
    </Box>
  );
};

export default SidebarContent;
