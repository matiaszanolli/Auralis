import { useState, useCallback, useRef, useMemo, lazy, Suspense } from 'react';
import { Box } from '@mui/material';
import { useSelector } from 'react-redux';
import { usePlaybackControls } from '@/contexts/PlaybackSessionContext';

// No need to import DragDropContext - it's wrapped in AppContainer
import Player from './components/player/Player';

// Route-level code splitting: heavy views loaded on demand (fixes #2811)
const CozyLibraryView = lazy(() => import('./components/library/CozyLibraryView'));
const SettingsDialog = lazy(() => import('./components/settings/SettingsDialog'));
const KeyboardShortcutsHelp = lazy(() => import('./components/shared/KeyboardShortcutsHelp'));

// Core app layout components
import {
  AppContainer,
  AppSidebar,
  AppTopBar,
  AppMainContent,
} from './components/core';
import { ErrorBoundary } from './components/core/ErrorBoundary';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import DesktopPlatformNotice from '@/components/platform/DesktopPlatformNotice';
import { AppViewAnnouncement } from '@/components/core/AppViewAnnouncement';

// Custom hooks for business logic
import { useAppLayout } from '@/hooks/app/useAppLayout';
import { useAppDragDrop } from '@/hooks/app/useAppDragDrop';

import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { useKeyboardShortcuts, KeyboardShortcut } from '@/hooks/app/useKeyboardShortcuts';
import { selectVolume } from './store/slices/playerSlice';
import type { ViewMode } from '@/components/navigation/ViewToggle';

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
  const [currentView, setCurrentView] = useState('songs'); // songs, favourites, recent, etc.
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [settingsOpen, setSettingsOpen] = useState(false);

  // WebSocket connection for real-time updates (using shared WebSocketContext)
  const wsContext = useWebSocketContext();
  const { isConnected } = wsContext;

  // Toast notifications
  const { success, info } = useToast();

  // Redux selector for the volume shortcuts' +/-10 stepping (read-only).
  const volume = useSelector(selectVolume);

  // #4541: global shortcuts must operate on the SAME enhanced-audio session
  // Player.tsx drives, not a disconnected legacy control plane — sending
  // 'play_normal' (the old usePlaybackControl.play()) cancelled the user's
  // own in-flight enhanced stream server-side with no visible error.
  const session = usePlaybackControls();
  const isPlaying = session.isStreaming && !session.isPaused;
  const togglePlayPause = session.handlePlayPause;
  const nextTrack = session.handleNext;
  const previousTrack = session.handlePrevious;
  const setVolume = useCallback(
    // handleVolumeChange expects 0.0-1.0 — clamp + scale the 0-100 value
    // used by the keyboard-shortcut UI.
    (newVolume: number) =>
      session.handleVolumeChange(Math.max(0, Math.min(100, newVolume)) / 100),
    [session]
  );

  // Drag-drop handler (useAppDragDrop handles all queue/playlist operations)
  const { handleDragEnd } = useAppDragDrop({ info, success });

  // Keyboard shortcuts - FIXED FOR BETA.11.1
  // Using new service-based architecture to avoid minification issues
  const keyboardShortcutsArray: KeyboardShortcut[] = useMemo(() => [
    // Playback controls
    {
      key: ' ',
      description: 'Play/Pause',
      category: 'Playback',
      handler: () => {
        // #5008: runTransportCommand's shared commandPendingRef silently
        // drops this command if a different transport command (Next/
        // Previous/Play-Pause) is still in flight — checking isCommandPending
        // here stops the confirmation toast from firing on a dropped command
        // the mouse-path buttons already refuse via the same flag.
        if (session.isCommandPending) return;
        togglePlayPause();
        info(isPlaying ? 'Paused' : 'Playing');
      }
    },
    {
      key: 'ArrowRight',
      description: 'Next track',
      category: 'Playback',
      handler: () => {
        if (session.isCommandPending) return;
        nextTrack();
        info('Next track');
      }
    },
    {
      key: 'ArrowLeft',
      description: 'Previous track',
      category: 'Playback',
      handler: () => {
        if (session.isCommandPending) return;
        previousTrack();
        info('Previous track');
      }
    },
    {
      key: 'ArrowUp',
      description: 'Volume up',
      category: 'Playback',
      handler: () => {
        const newVolume = Math.min(volume + 10, 100);
        setVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'ArrowDown',
      description: 'Volume down',
      category: 'Playback',
      handler: () => {
        const newVolume = Math.max(volume - 10, 0);
        setVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'm',
      description: 'Mute/Unmute',
      category: 'Playback',
      handler: () => {
        // Shares Player.tsx's mute/unmute semantics (restore pre-mute volume
        // rather than a hardcoded 80%) so both surfaces agree (#4541).
        session.handleMuteToggle().then((nowMuted) => {
          info(nowMuted ? 'Muted' : 'Unmuted');
        });
      }
    },
    // Navigation shortcuts
    {
      key: '1',
      description: 'Show Songs',
      category: 'Navigation',
      handler: () => {
        setCurrentView('songs');
        info('Songs view');
      }
    },
    {
      key: '2',
      description: 'Show Albums',
      category: 'Navigation',
      handler: () => {
        setCurrentView('albums');
        info('Albums view');
      }
    },
    {
      key: '3',
      description: 'Show Artists',
      category: 'Navigation',
      handler: () => {
        setCurrentView('artists');
        info('Artists view');
      }
    },
    {
      key: '4',
      description: 'Show Playlists',
      category: 'Navigation',
      handler: () => {
        setCurrentView('playlists');
        info('Playlists view');
      }
    },
    {
      key: '/',
      description: 'Focus search',
      category: 'Navigation',
      handler: () => {
        const searchInput = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    },
    {
      key: 'Escape',
      description: 'Clear search / Close dialogs',
      category: 'Navigation',
      handler: () => {
        if (searchQuery) {
          setSearchQuery('');
          info('Search cleared');
        } else if (settingsOpen) {
          setSettingsOpen(false);
        }
      }
    },
    // Global shortcuts
    {
      key: '?',
      description: 'Show keyboard shortcuts',
      category: 'Global',
      handler: () => {
        openHelpRef.current?.();
      }
    },
    {
      key: ',',
      ctrl: true,
      description: 'Open settings',
      category: 'Global',
      handler: () => {
        setSettingsOpen(true);
      }
    }
  ], [togglePlayPause, isPlaying, nextTrack, previousTrack, volume, setVolume, session,
      searchQuery, setSearchQuery, settingsOpen, setSettingsOpen, setCurrentView, info]);

  // Ref to break circular dependency: array references openHelp, but
  // openHelp comes from the hook that receives the array (fixes #3077).
  const openHelpRef = useRef<(() => void) | null>(null);

  // Keyboard shortcuts via unified hook
  const {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    formatShortcut
  } = useKeyboardShortcuts(keyboardShortcutsArray);

  // Keep ref in sync with latest openHelp
  openHelpRef.current = openHelp;

  const handleSidebarNavigation = useCallback((view: string) => {
    setCurrentView(view);
  }, []);

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
            connectionStatus={isConnected ? 'connected' : 'connecting'}
            isMobile={isMobile}
            onSearchClear={() => setSearchQuery('')}
            {...(['songs', 'favourites', 'recent'].includes(currentView) ? {
              viewMode,
              onViewModeChange: setViewMode,
            } : {})}
          />

          {/* Main content area with library view.
              Wrapped in a dedicated ErrorBoundary (#3583) so a library render
              crash doesn't kill the entire app — player/sidebar remain usable. */}
          <AppMainContent>
            <ErrorBoundary
              fallback={
                <Box
                  sx={{
                    p: tokens.spacing.lg,
                    background: themeVars.errorSoft,
                    border: `1px solid ${themeVars.error}`,
                    borderRadius: tokens.borderRadius.md,
                    color: themeVars.textPrimary,
                    fontSize: tokens.typography.fontSize.sm,
                    textAlign: 'center',
                    m: tokens.spacing.lg,
                  }}
                >
                  Library failed to render. The rest of the app (player, sidebar,
                  settings) is still available. Refresh the page to retry.
                </Box>
              }
            >
              <Suspense fallback={null}>
                <CozyLibraryView
                  view={currentView}
                  searchQuery={searchQuery}
                  viewMode={viewMode}
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
        fallback={
          <Box
            sx={{
              p: tokens.spacing.lg,
              background: themeVars.errorSoft,
              border: `1px solid ${themeVars.error}`,
              borderRadius: tokens.borderRadius.md,
              color: themeVars.textPrimary,
              fontSize: tokens.typography.fontSize.sm,
              textAlign: 'center',
              m: tokens.spacing.lg,
            }}
          >
            Settings failed to render. The rest of the app (library, player,
            sidebar) is still available. Refresh the page to retry.
          </Box>
        }
      >
        <Suspense fallback={null}>
          <SettingsDialog
            open={settingsOpen}
            onClose={() => setSettingsOpen(false)}
            onSettingsChange={(settings) => {
              console.log('Settings changed:', settings);
              success('Settings saved successfully');
            }}
          />
        </Suspense>
      </ErrorBoundary>

      {/* Keyboard Shortcuts Help Dialog.
          Wrapped in a dedicated ErrorBoundary (#4880) for the same reason as
          SettingsDialog above. */}
      <ErrorBoundary
        fallback={
          <Box
            sx={{
              p: tokens.spacing.lg,
              background: themeVars.errorSoft,
              border: `1px solid ${themeVars.error}`,
              borderRadius: tokens.borderRadius.md,
              color: themeVars.textPrimary,
              fontSize: tokens.typography.fontSize.sm,
              textAlign: 'center',
              m: tokens.spacing.lg,
            }}
          >
            Keyboard shortcuts help failed to render. The rest of the app is
            still available. Refresh the page to retry.
          </Box>
        }
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
          doesn't kill the entire app — library/queue/settings remain usable. */}
      <Box sx={{ flexShrink: 0 }}>
        <ErrorBoundary
          fallback={
            <Box
              sx={{
                p: tokens.spacing.md,
                background: themeVars.errorSoft,
                borderTop: `1px solid ${themeVars.error}`,
                color: themeVars.textPrimary,
                fontSize: tokens.typography.fontSize.sm,
                textAlign: 'center',
              }}
            >
              Player encountered an error. Refresh the page to restart playback.
            </Box>
          }
        >
          <Player />
        </ErrorBoundary>
      </Box>
    </Box>
  );
}

export default ComfortableApp;
