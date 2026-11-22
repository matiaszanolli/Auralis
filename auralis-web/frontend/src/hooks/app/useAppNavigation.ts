import { useCallback, useState } from 'react';
import type { ViewMode } from '@/components/navigation/ViewToggle';

/**
 * The app shell's navigation state (#6703): the current library view
 * ('songs', 'favourites', or an artist-N / album-N / playlist-N detail view),
 * the grid/list mode, and the reset token for re-picking the current view.
 */
export function useAppNavigation() {
  const [currentView, setCurrentView] = useState('songs');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  // Picking the nav item of the view you are already in leaves any open detail page: the view id is
  // unchanged, so a counter tells the library view to reset (#6014).
  const [navigationResetToken, setNavigationResetToken] = useState(0);

  const handleSidebarNavigation = useCallback((view: string) => {
    setCurrentView(view);
    setNavigationResetToken((token) => token + 1);
  }, []);

  return {
    currentView,
    setCurrentView,
    viewMode,
    setViewMode,
    navigationResetToken,
    handleSidebarNavigation,
  };
}
