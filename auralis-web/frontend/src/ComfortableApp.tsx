import { useState, Suspense } from 'react';
import { Box } from '@mui/material';
import { useSelector } from 'react-redux';

// No need to import DragDropContext - it's wrapped in AppContainer
import Player from './components/player/Player';
import { lazyWithRetry } from '@/utils/lazyWithRetry';

// Route-level code splitting: heavy views loaded on demand (fixes #2811)
// lazyWithRetry: a failed chunk load must be recoverable from the boundary's retry (#6035).
const CozyLibraryView = lazyWithRetry(() => import('./components/library/CozyLibraryView'));
const SettingsDialog = lazyWithRetry(() => import('./components/settings/SettingsDialog'));
const KeyboardShortcutsHelp = lazyWithRetry(() => import('./components/shared/KeyboardShortcutsHelp'));

// Core app layout components
import {
  AppContainer,
  AppSidebar,
  AppTopBar,
  AppMainContent,
} from './components/core';
import { ErrorBoundary } from './components/core/ErrorBoundary';
import { RegionErrorFallback } from './components/core/RegionErrorFallback';
import { themeVars } from '@/theme/semanticTheme';
import DesktopPlatformNotice from '@/components/platform/DesktopPlatformNotice';
import { AppViewAnnouncement } from '@/components/core/AppViewAnnouncement';

// Custom hooks for business logic
import { useAppLayout } from '@/hooks/app/useAppLayout';
import { useAppDragDrop } from '@/hooks/app/useAppDragDrop';
import { useAppKeyboard } from '@/hooks/app/useAppKeyboard';
import { useAppNavigation } from '@/hooks/app/useAppNavigation';

import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { playerSelectors } from './store/selectors';

function ComfortableApp() {
  // Layout state management (useAppLayout handles responsive sidebar/drawer)
  const {
    isMobile,
    sidebarCollapsed,
    mobileDrawerOpen,
    setSidebarCollapsed,
    setMobileDrawerOpen,
  } = useAppLayout();

  const [searchQuery, setSearchQuery] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const {
    currentView,
    setCurrentView,
    viewMode,
    setViewMode,
    navigationResetToken,
    handleSidebarNavigation,
  } = useAppNavigation();

  // WebSocket connection for real-time updates (using shared WebSocketContext)
  const wsContext = useWebSocketContext();
  // The hook's full 4-state status, not a boolean collapse: a permanently
  // failed connection must render as error/disconnected, not as an eternal
  // "connecting" (#5468).
  const { connectionStatus } = wsContext;

  // Toast notifications
  const { success, info } = useToast();

  // The Player boundary recovers when the track changes: the same bad track would crash every
  // "Try again", the next one need not (#6035).
  const currentTrackId = useSelector(playerSelectors.selectCurrentTrack)?.id;

  // Drag-drop handler (useAppDragDrop handles all queue/playlist operations)
  const { handleDragEnd } = useAppDragDrop({ info, success });

  const { shortcuts, isHelpOpen, closeHelp, formatShortcut } = useAppKeyboard({
    info,
    searchQuery,
    setSearchQuery,
    settingsOpen,
    setSettingsOpen,
    setCurrentView,
  });

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        backgroundColor: themeVars.canvas,
        color: themeVars.textPrimary,
      }}
    >
      <DesktopPlatformNotice />
      <AppViewAnnouncement view={currentView} />
      <AppContainer onDragEnd={handleDragEnd}>
        {/* Sidebar (desktop or mobile drawer) */}
        <AppSidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onNavigate={handleSidebarNavigation}
          activeView={currentView}
          onOpenSettings={() => setSettingsOpen(true)}
          mobileDrawerOpen={mobileDrawerOpen}
          onCloseMobileDrawer={() => setMobileDrawerOpen(false)}
          isMobile={isMobile}
        />

        {/* Main content column */}
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          {/* Top bar with search and title */}
          <AppTopBar
            onSearch={setSearchQuery}
            onOpenMobileDrawer={() => setMobileDrawerOpen(true)}
            title="Your Music"
            connectionStatus={connectionStatus}
            isMobile={isMobile}
            onSearchClear={() => setSearchQuery('')}
            searchValue={searchQuery}
            {...(['songs', 'favourites'].includes(currentView) ? {
              viewMode,
              onViewModeChange: setViewMode,
            } : {})}
          />

          {/* Main content area with library view.
              Wrapped in a dedicated ErrorBoundary (#3583) so a library render
              crash doesn't kill the entire app — player/sidebar remain usable.
              #5627: the fallback offers a working retry, and switching views
              resets the boundary, so a transient crash no longer needs a
              reload or even a click. */}
          <AppMainContent>
            <ErrorBoundary
              resetKeys={[currentView]}
              fallback={(_error, retry) => (
                <RegionErrorFallback
                  message="Library failed to render. The rest of the app (player, sidebar, settings) is still available."
                  retry={retry}
                />
              )}
            >
              <Suspense fallback={null}>
                <CozyLibraryView
                  view={currentView}
                  searchQuery={searchQuery}
                  viewMode={viewMode}
                  onNavigate={handleSidebarNavigation}
                  navigationResetToken={navigationResetToken}
                />
              </Suspense>
            </ErrorBoundary>
          </AppMainContent>
        </Box>

        {/* Right pane - AlbumCharacterPane replaces EnhancementPane globally */}
        {/* Rendered via ViewContainer in CozyLibraryView/LibraryViewRouter for all views */}
      </AppContainer>

      {/* Settings Dialog.
          Wrapped in a dedicated ErrorBoundary (#4880) so a render crash in any
          settings-tab panel doesn't propagate past this boundary and unmount
          the whole app — library/player remain usable. Suspense alone does
          not catch render errors. */}
      <ErrorBoundary
        fallback={(_error, retry) => (
          <RegionErrorFallback
            message="Settings failed to render. The rest of the app (library, player, sidebar) is still available."
            // A dialog the parent still holds open would crash again on a bare retry: close it
            // first (#6035).
            retry={() => { setSettingsOpen(false); retry(); }}
          />
        )}
      >
        <Suspense fallback={null}>
          <SettingsDialog
            open={settingsOpen}
            onClose={() => setSettingsOpen(false)}
            onSettingsChange={() => success('Settings saved successfully')}
            onSettingsReset={() => success('Settings reset to defaults')}
          />
        </Suspense>
      </ErrorBoundary>

      {/* Keyboard Shortcuts Help Dialog.
          Wrapped in a dedicated ErrorBoundary (#4880) for the same reason as
          SettingsDialog above. */}
      <ErrorBoundary
        fallback={(_error, retry) => (
          <RegionErrorFallback
            message="Keyboard shortcuts help failed to render. The rest of the app is still available."
            retry={() => { closeHelp(); retry(); }}
          />
        )}
      >
        <Suspense fallback={null}>
          <KeyboardShortcutsHelp
            open={isHelpOpen}
            shortcuts={shortcuts}
            onClose={closeHelp}
            formatShortcut={formatShortcut}
          />
        </Suspense>
      </ErrorBoundary>

      {/* Bottom Player Bar - Fixed at bottom of viewport, not inside flex layout.
          Wrapped in a dedicated ErrorBoundary (#3115) so a Player render crash
          doesn't kill the entire app — library/queue/settings remain usable.
          QueuePanel has its own boundary INSIDE Player (#5627), so a queue
          render error no longer takes the transport controls with it. */}
      <Box sx={{ flexShrink: 0 }}>
        <ErrorBoundary
          resetKeys={[currentTrackId]}
          fallback={(_error, retry) => (
            <RegionErrorFallback
              message="Player encountered an error."
              retry={retry}
              variant="bottomBar"
            />
          )}
        >
          <Player />
        </ErrorBoundary>
      </Box>
    </Box>
  );
}

export default ComfortableApp;
