/**
 * SidebarContent - Main navigation content with library, collections, and playlists
 */

import { Box } from '@mui/material';
import LibraryMusic from '@mui/icons-material/LibraryMusic';
import Album from '@mui/icons-material/Album';
import Person from '@mui/icons-material/Person';
import Favorite from '@mui/icons-material/Favorite';
import { tokens } from '@/design-system';
import { SectionLabel } from './SidebarStyles';
import NavigationSection from './NavigationSection';
import PlaylistList from '@/components/playlist/PlaylistList';

interface SidebarContentProps {
  selectedItem: string;
  onItemClick: (itemId: string) => void;
}

export const SidebarContent = ({ selectedItem, onItemClick }: SidebarContentProps) => {
  // Navigation items definitions
  const libraryItems = [
    { id: 'songs', label: 'Songs', icon: <LibraryMusic /> },
    { id: 'albums', label: 'Albums', icon: <Album /> },
    { id: 'artists', label: 'Artists', icon: <Person /> },
    { id: 'favourites', label: 'Favourites', icon: <Favorite /> },
  ];

  return (
    <Box component="nav" aria-label="Library navigation" sx={{
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

      {/* Playlists Section - Major section break */}
      <Box sx={{ marginTop: tokens.spacing.group }}> {/* 16px group spacing before playlists (the playlists live here, not as a main view — #5620) */}
        <PlaylistList
          selectedPlaylistId={selectedItem.startsWith('playlist-') ? parseInt(selectedItem.replace('playlist-', '')) : undefined}
          onPlaylistSelect={(playlistId) =>
            // -1 is usePlaylistOperations' "selected playlist was deleted"
            // sentinel: navigate to songs, never `playlist--1` (#6007).
            onItemClick(playlistId === -1 ? 'songs' : `playlist-${playlistId}`)
          }
          hideHeader={true}
        />
      </Box>
    </Box>
  );
};

export default SidebarContent;
