import { useState, useCallback } from 'react';

interface UseSidebarStateReturn {
  selectedItem: string;
  playlistsOpen: boolean;
  handleItemClick: (itemId: string) => void;
  setPlaylistsOpen: (open: boolean) => void;
}

/**
 * Hook for managing Sidebar state
 *
 * Handles:
 * - Selected menu item tracking
 * - Playlists section expand/collapse state
 * - Item selection callbacks
 */
export const useSidebarState = (onNavigate?: (view: string) => void): UseSidebarStateReturn => {
  const [playlistsOpen, setPlaylistsOpen] = useState(true);
  const [selectedItem, setSelectedItem] = useState('songs');

  const handleItemClick = useCallback(
    (itemId: string) => {
      setSelectedItem(itemId);
      if (onNavigate) {
        onNavigate(itemId);
      }
    },
    [onNavigate]
  );

  return {
    selectedItem,
    playlistsOpen,
    handleItemClick,
    setPlaylistsOpen,
  };
};

export default useSidebarState;
