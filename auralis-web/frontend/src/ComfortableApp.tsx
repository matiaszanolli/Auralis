import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { useSelector } from 'react-redux';

// No need to import DragDropContext - it's wrapped in AppContainer
import Player from './components/player/Player';
import EnhancementPane from './components/enhancement-pane';
import CozyLibraryView from './components/library/CozyLibraryView';
import SettingsDialog from './components/settings/SettingsDialog';
import KeyboardShortcutsHelp from './components/shared/KeyboardShortcutsHelp';

// Core app layout components
import {
  AppContainer,
  AppSidebar,
  AppTopBar,
  AppMainContent,
  AppEnhancementPane,
} from './components/core';

// Custom hooks for business logic
import { useAppLayout } from '@/hooks/app/useAppLayout';
import { useAppDragDrop } from '@/hooks/app/useAppDragDrop';

import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { useKeyboardShortcuts, KeyboardShortcut } from '@/hooks/app/useKeyboardShortcuts';
import { selectIsPlaying, selectVolume } from './store/slices/playerSlice';
import { getApiUrl } from './config/api';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  isEnhanced?: boolean;
}

function ComfortableApp() {
  const theme = useTheme();
  const isTablet = useMediaQuery(theme.breakpoints.down('lg')); // < 1200px

  // Layout state management (useAppLayout handles responsive sidebar/drawer)
  const {
    isMobile,
    sidebarCollapsed,
    mobileDrawerOpen,
    presetPaneCollapsed,
    setSidebarCollapsed,
    setMobileDrawerOpen,
    setPresetPaneCollapsed,
  } = useAppLayout();

  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState('songs'); // songs, favourites, recent, etc.
  const [settingsOpen, setSettingsOpen] = useState(false);

  // WebSocket connection for real-time updates (using shared WebSocketContext)
  const { isConnected } = useWebSocketContext();

  // Toast notifications
  const { success, info } = useToast();

  // Redux selectors for player state (read-only)
  const isPlaying = useSelector(selectIsPlaying);
  const volume = useSelector(selectVolume);

  // Player API helpers for issuing commands to backend
  const togglePlayPause = useCallback(async () => {
    try {
      const endpoint = isPlaying ? '/api/player/pause' : '/api/player/play';
      await fetch(endpoint, { method: 'POST' });
    } catch (err) {
      console.error('Playback control error:', err);
    }
  }, [isPlaying]);

  const nextTrack = useCallback(async () => {
    try {
      await fetch('/api/player/next', { method: 'POST' });
    } catch (err) {
      console.error('Next track error:', err);
    }
  }, []);

  const previousTrack = useCallback(async () => {
    try {
      await fetch('/api/player/previous', { method: 'POST' });
    } catch (err) {
      console.error('Previous track error:', err);
    }
  }, []);

  const setVolume = useCallback(async (newVolume: number) => {
    try {
      await fetch('/api/player/volume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume: newVolume })
      });
    } catch (err) {
      console.error('Volume control error:', err);
    }
  }, []);

  // Drag-drop handler (useAppDragDrop handles all queue/playlist operations)
  const { handleDragEnd } = useAppDragDrop({ info, success });

  // Event handlers - MUST be defined before useKeyboardShortcuts to avoid TDZ errors
  const handleTrackPlay = (track: Track) => {
    setCurrentTrack(track);
    console.log('Playing track:', track.title);
  };

  // Keyboard shortcuts - FIXED FOR BETA.11.1
  // Using new service-based architecture to avoid minification issues
  const keyboardShortcutsArray: KeyboardShortcut[] = [
    // Playback controls
    {
      key: ' ',
      description: 'Play/Pause',
      category: 'Playback',
      handler: () => {
        togglePlayPause();
        info(isPlaying ? 'Paused' : 'Playing');
      }
    },
    {
      key: 'ArrowRight',
      description: 'Next track',
      category: 'Playback',
      handler: () => {
        nextTrack();
        info('Next track');
      }
    },
    {
      key: 'ArrowLeft',
      description: 'Previous track',
      category: 'Playback',
      handler: () => {
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
        const newVolume = volume > 0 ? 0 : 80;
        setVolume(newVolume);
        info(newVolume === 0 ? 'Muted' : 'Unmuted');
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
        // Will be set below
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
  ];

  // Use V2 hook with service-based architecture
  const {
    shortcuts,
    isHelpOpen,
    openHelp,
    closeHelp,
    formatShortcut
  } = useKeyboardShortcuts(keyboardShortcutsArray);

  // Set the help shortcut handler (needs openHelp from hook)
  useEffect(() => {
    const helpShortcut = keyboardShortcutsArray.find(s => s.key === '?');
    if (helpShortcut) {
      helpShortcut.handler = openHelp;
    }
  }, [openHelp]);

  const handleMasteringToggle = (enabled: boolean) => {
    console.log('Mastering:', enabled ? 'enabled' : 'disabled');
    info(enabled ? '✨ Mastering enabled' : 'Mastering disabled');
  };

  const handleSidebarNavigation = useCallback((view: string) => {
    setCurrentView(view);
  }, []);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', width: '100vw', height: '100vh', overflow: 'hidden' }}>
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
          />

          {/* Main content area with library view */}
          <AppMainContent>
            <CozyLibraryView
              onTrackPlay={handleTrackPlay}
              view={currentView}
            />
          </AppMainContent>
        </Box>

        {/* Right enhancement pane - Hidden on tablet/mobile */}
        {!isTablet && (
          <AppEnhancementPane
            useV2={true}
            initiallyCollapsed={presetPaneCollapsed}
            onToggleV2={() => {}} // V1 fallback removed, EnhancementPane is now default
          >
            <EnhancementPane
              collapsed={presetPaneCollapsed}
              onToggleCollapse={() => setPresetPaneCollapsed(!presetPaneCollapsed)}
              onMasteringToggle={handleMasteringToggle}
            />
          </AppEnhancementPane>
        )}
      </AppContainer>

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSettingsChange={(settings) => {
          console.log('Settings changed:', settings);
          success('Settings saved successfully');
        }}
      />

      {/* Keyboard Shortcuts Help Dialog */}
      <KeyboardShortcutsHelp
        open={isHelpOpen}
        shortcuts={shortcuts}
        onClose={closeHelp}
        formatShortcut={formatShortcut}
      />

      {/* Bottom Player Bar - Fixed at bottom of viewport, not inside flex layout */}
      <Box sx={{ flexShrink: 0 }}>
        <Player />
      </Box>
    </Box>
  );
}

export default ComfortableApp;
