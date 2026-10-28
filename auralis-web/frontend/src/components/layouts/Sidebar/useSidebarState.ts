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
export const useSidebarState = (
  onNavigate?: (view: string) => void,
  activeView?: string
): UseSidebarStateReturn => {
  const [playlistsOpen, setPlaylistsOpen] = useState(true);
  const [localSelected, setSelectedItem] = useState('songs');
  // The app's current view is the source of truth when the shell provides it: the 1/2/3 shortcuts
  // change the view without going through this sidebar, and a remount (desktop <-> mobile drawer)
  // used to reset the highlight to 'songs' whatever view was showing (#6014).
  const selectedItem = activeView ?? localSelected;

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
