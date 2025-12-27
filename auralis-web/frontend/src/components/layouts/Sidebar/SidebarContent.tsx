/**
 * SidebarContent - Main navigation content with library, collections, and playlists
 */

import React from 'react';
import { Box, Divider } from '@mui/material';
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
  ];

  const collectionItems = [
    { id: 'favourites', label: 'Favourites', icon: <Favorite /> },
    { id: 'recent', label: 'Recently Played', icon: <History /> },
  ];

  return (
    <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
      {/* Library Section */}
      <SectionLabel>Library</SectionLabel>
      <NavigationSection
        items={libraryItems}
        selectedItem={selectedItem}
        onItemClick={onItemClick}
      />

      <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.lg, opacity: 0.5 }} /> {/* Increased spacing + faded */}

      {/* Collections Section */}
      <NavigationSection
        items={collectionItems}
        selectedItem={selectedItem}
        onItemClick={onItemClick}
      />

      <Divider sx={{ borderColor: tokens.colors.border.light, my: tokens.spacing.lg, opacity: 0.5 }} /> {/* Increased spacing + faded */}

      {/* Playlists Section */}
      <PlaylistList
        selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
        onPlaylistSelect={(playlistId) => onItemClick(`playlist-${playlistId}`)}
      />
    </Box>
  );
};

export default SidebarContent;
