import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  Typography,
  IconButton,
  useMediaQuery,
  useTheme,
  Drawer,
  SwipeableDrawer
} from '@mui/material';
import {
  Search,
  Menu as MenuIcon
} from '@mui/icons-material';
import { DragDropContext, DropResult } from '@hello-pangea/dnd';

import Sidebar from './components/Sidebar';
// Phase 3: Using NEW Unified WebM Audio Player (always WebM/Opus)
// Replaced old dual MSE/HTML5 player with single Web Audio API player
// See: docs/sessions/nov1_unified_player/
import BottomPlayerBarUnified from './components/BottomPlayerBarUnified';
import PresetPane from './components/PresetPane';
import CozyLibraryView from './components/CozyLibraryView';
import GlobalSearch from './components/library/GlobalSearch';
import SettingsDialog from './components/settings/SettingsDialog';
import LyricsPanel from './components/player/LyricsPanel';
import KeyboardShortcutsHelp from './components/shared/KeyboardShortcutsHelp';
import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { usePlayerAPI } from './hooks/usePlayerAPI';

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
  const isMobile = useMediaQuery(theme.breakpoints.down('md')); // < 900px
  const isTablet = useMediaQuery(theme.breakpoints.down('lg')); // < 1200px

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [presetPaneCollapsed, setPresetPaneCollapsed] = useState(false);
  const [lyricsOpen, setLyricsOpen] = useState(false);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState('songs'); // songs, favourites, recent, etc.
  const [searchResultView, setSearchResultView] = useState<{type: string; id: number} | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);

  // WebSocket connection for real-time updates (using shared WebSocketContext)
  const { isConnected } = useWebSocketContext();

  // Toast notifications
  const { success, info } = useToast();

  // Player API for real playback control
  const {
    currentTrack: apiCurrentTrack,
    isPlaying: apiIsPlaying,
    volume: apiVolume,
    togglePlayPause,
    next: nextTrack,
    previous: previousTrack,
    setVolume: setApiVolume
  } = usePlayerAPI();

  // Auto-collapse sidebar on mobile and hide preset pane on tablet
  useEffect(() => {
    if (isMobile) {
      setSidebarCollapsed(true);
      setMobileDrawerOpen(false); // Ensure drawer is closed on mobile by default
    } else {
      setSidebarCollapsed(false); // Show sidebar on desktop
    }
    if (isTablet) {
      setPresetPaneCollapsed(true);
    } else {
      setPresetPaneCollapsed(false); // Show preset pane on large screens
    }
  }, [isMobile, isTablet]);

  // Event handlers - MUST be defined before useKeyboardShortcuts to avoid TDZ errors
  const handleTrackPlay = (track: Track) => {
    setCurrentTrack(track);
    setIsPlaying(true);
    console.log('Playing track:', track.title);
  };

  const handlePlayPause = () => {
    setIsPlaying(!isPlaying);
  };

  const handleEnhancementToggle = (trackId: number, enabled: boolean) => {
    console.log(`Track ${trackId} enhancement ${enabled ? 'enabled' : 'disabled'}`);
    info(enabled ? '✨ Auralis magic enabled' : 'Enhancement disabled');
  };

  const handlePlayerEnhancementToggle = (enabled: boolean) => {
    if (currentTrack) {
      setCurrentTrack({ ...currentTrack, isEnhanced: enabled });
      handleEnhancementToggle(currentTrack.id, enabled);
    }
  };

  const handlePresetChange = (preset: string) => {
    console.log('Preset changed to:', preset);
    info(`Preset changed to ${preset}`);
  };

  // Keyboard shortcuts - DISABLED FOR BETA.6 (causes circular dependency in minified build)
  // Will be fixed in Beta.7
  // const {
  //   shortcuts,
  //   isHelpOpen,
  //   openHelp,
  //   closeHelp
  // } = useKeyboardShortcuts({
  const shortcuts: any[] = [];
  const isHelpOpen = false;
  const openHelp = () => {};
  const closeHelp = () => {};
  /*{
    // Playback controls
    onPlayPause: () => {
      togglePlayPause();
      info(apiIsPlaying ? 'Paused' : 'Playing');
    },
    onNext: () => {
      nextTrack();
      info('Next track');
    },
    onPrevious: () => {
      previousTrack();
      info('Previous track');
    },
    onVolumeUp: () => {
      const newVolume = Math.min(apiVolume + 10, 100);
      setApiVolume(newVolume);
      info(`Volume: ${newVolume}%`);
    },
    onVolumeDown: () => {
      const newVolume = Math.max(apiVolume - 10, 0);
      setApiVolume(newVolume);
      info(`Volume: ${newVolume}%`);
    },
    onMute: () => {
      const newVolume = apiVolume > 0 ? 0 : 80; // Toggle between 0 and default 80%
      setApiVolume(newVolume);
      info(newVolume === 0 ? 'Muted' : 'Unmuted');
    },

    // Navigation shortcuts
    onShowSongs: () => {
      setCurrentView('songs');
      info('Songs view');
    },
    onShowAlbums: () => {
      setCurrentView('albums');
      info('Albums view');
    },
    onShowArtists: () => {
      setCurrentView('artists');
      info('Artists view');
    },
    onShowPlaylists: () => {
      setCurrentView('playlists');
      info('Playlists view');
    },
    onFocusSearch: () => {
      // Focus search input
      const searchInput = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    },
    onEscape: () => {
      // Clear search or close dialogs
      if (searchQuery) {
        setSearchQuery('');
        info('Search cleared');
      } else if (settingsOpen) {
        setSettingsOpen(false);
      } else if (lyricsOpen) {
        setLyricsOpen(false);
      }
    },

    // Global shortcuts
    onShowHelp: openHelp,
    onOpenSettings: () => {
      setSettingsOpen(true);
    },

    // Debug mode (optional)
    debug: false
  });*/

  const handleMasteringToggle = (enabled: boolean) => {
    console.log('Mastering:', enabled ? 'enabled' : 'disabled');
    info(enabled ? '✨ Mastering enabled' : 'Mastering disabled');
  };

  const handleSearchResultClick = (result: {type: string; id: number}) => {
    if (result.type === 'track') {
      // Play the track directly
      console.log('Play track from search:', result.id);
    } else if (result.type === 'album') {
      setCurrentView('albums');
      setSearchResultView(result);
    } else if (result.type === 'artist') {
      setCurrentView('artists');
      setSearchResultView(result);
    }
  };

  const handleMobileMenuToggle = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  const handleMobileNavigation = (view: string) => {
    setCurrentView(view);
    setMobileDrawerOpen(false); // Close drawer after navigation on mobile
  };

  // Drag and drop handler
  const handleDragEnd = useCallback(async (result: DropResult) => {
    const { source, destination, draggableId } = result;

    // Dropped outside a valid droppable area
    if (!destination) {
      return;
    }

    // Dropped in the same position
    if (
      source.droppableId === destination.droppableId &&
      source.index === destination.index
    ) {
      return;
    }

    // Extract track ID from draggableId (format: "track-123")
    const trackId = parseInt(draggableId.replace('track-', ''), 10);

    try {
      // Handle different drop targets
      if (destination.droppableId === 'queue') {
        // Add to queue
        const response = await fetch('/api/player/queue/add-track', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            track_id: trackId,
            position: destination.index
          })
        });

        if (response.ok) {
          success(`Added track to queue at position ${destination.index + 1}`);
        } else {
          throw new Error('Failed to add track to queue');
        }
      } else if (destination.droppableId.startsWith('playlist-')) {
        // Add to playlist
        const playlistId = parseInt(destination.droppableId.replace('playlist-', ''), 10);
        const response = await fetch(`/api/playlists/${playlistId}/tracks/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            track_id: trackId,
            position: destination.index
          })
        });

        if (response.ok) {
          success(`Added track to playlist`);
        } else {
          throw new Error('Failed to add track to playlist');
        }
      } else if (destination.droppableId === source.droppableId) {
        // Reorder within the same list
        if (source.droppableId === 'queue') {
          // Reorder queue
          const response = await fetch('/api/player/queue/move', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              from_index: source.index,
              to_index: destination.index
            })
          });

          if (response.ok) {
            info('Queue reordered');
          } else {
            throw new Error('Failed to reorder queue');
          }
        } else if (source.droppableId.startsWith('playlist-')) {
          // Reorder within playlist
          const playlistId = parseInt(source.droppableId.replace('playlist-', ''), 10);
          const response = await fetch(`/api/playlists/${playlistId}/tracks/reorder`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              from_index: source.index,
              to_index: destination.index
            })
          });

          if (response.ok) {
            info('Playlist reordered');
          } else {
            throw new Error('Failed to reorder playlist');
          }
        }
      }
    } catch (err) {
      console.error('Drag and drop error:', err);
      info('Failed to complete drag and drop operation');
    }
  }, [info, success]);

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <Box
        sx={{
          width: '100vw',
          height: '100vh',
          background: 'var(--midnight-blue)',
          color: 'var(--silver)',
          display: 'flex',
          flexDirection: 'column',
          // overflow: 'hidden' removed - fixed player is outside this box and needs to be visible
        }}
      >
        {/* Main Layout: Sidebar + Content */}
        <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Desktop Sidebar - Hidden on mobile */}
        {!isMobile && (
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            onNavigate={setCurrentView}
            onOpenSettings={() => setSettingsOpen(true)}
          />
        )}

        {/* Mobile Drawer - Swipeable on mobile */}
        {isMobile && (
          <SwipeableDrawer
            anchor="left"
            open={mobileDrawerOpen}
            onClose={() => setMobileDrawerOpen(false)}
            onOpen={() => setMobileDrawerOpen(true)}
            disableSwipeToOpen={false}
            swipeAreaWidth={20}
            ModalProps={{
              keepMounted: true, // Better performance on mobile
            }}
            PaperProps={{
              sx: {
                width: 240,
                background: 'var(--midnight-blue)',
                borderRight: '1px solid rgba(102, 126, 234, 0.1)',
              }
            }}
          >
            <Sidebar
              collapsed={false}
              onNavigate={handleMobileNavigation}
              onOpenSettings={() => {
                setSettingsOpen(true);
                setMobileDrawerOpen(false);
              }}
            />
          </SwipeableDrawer>
        )}

        {/* Main Content Area */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          {/* Top Bar with Search */}
          <Box
            sx={{
              p: 3,
              pb: 2,
              borderBottom: '1px solid rgba(226, 232, 240, 0.1)',
              background: 'var(--midnight-blue)'
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              {/* Left: Mobile Menu + Title */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {/* Mobile Hamburger Menu */}
                {isMobile && (
                  <IconButton
                    onClick={handleMobileMenuToggle}
                    aria-label="Open navigation menu"
                    aria-expanded={mobileDrawerOpen}
                    sx={{
                      color: 'var(--silver)',
                      '&:hover': {
                        background: 'rgba(102, 126, 234, 0.1)',
                      },
                      '&:active': {
                        background: 'rgba(102, 126, 234, 0.2)',
                      },
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <MenuIcon />
                  </IconButton>
                )}

                <Typography
                  variant="h5"
                  sx={{
                    fontFamily: 'var(--font-heading)',
                    fontWeight: 600,
                    color: 'var(--silver)'
                  }}
                >
                  Your Music
                </Typography>
              </Box>

              {/* Connection Status */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 2,
                  py: 0.5,
                  borderRadius: 'var(--radius-md)',
                  background: isConnected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                  border: `1px solid ${isConnected ? 'var(--success)' : 'var(--warning)'}`
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: isConnected ? 'var(--success)' : 'var(--warning)',
                    animation: isConnected ? 'pulse 2s infinite' : 'none',
                    '@keyframes pulse': {
                      '0%': { opacity: 1 },
                      '50%': { opacity: 0.5 },
                      '100%': { opacity: 1 }
                    }
                  }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    fontFamily: 'var(--font-body)',
                    fontSize: 12
                  }}
                >
                  {isConnected ? 'Connected' : 'Connecting...'}
                </Typography>
              </Box>
            </Box>

            {/* Search Bar */}
            <GlobalSearch onResultClick={handleSearchResultClick} />
          </Box>

          {/* Content Area - Library View */}
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              pb: '104px' // Space for bottom player bar (80px + 24px margin)
            }}
          >
            <CozyLibraryView
              onTrackPlay={handleTrackPlay}
              onEnhancementToggle={handleEnhancementToggle}
              view={currentView}
            />
          </Box>
        </Box>

        {/* Right Preset Pane - Hidden on mobile/tablet */}
        {!isTablet && (
          <PresetPane
            collapsed={presetPaneCollapsed}
            onToggleCollapse={() => setPresetPaneCollapsed(!presetPaneCollapsed)}
            onPresetChange={handlePresetChange}
            onMasteringToggle={handleMasteringToggle}
          />
        )}

        {/* Lyrics Panel - Optional */}
        {lyricsOpen && currentTrack && (
          <LyricsPanel
            trackId={currentTrack.id}
            currentTime={playbackTime}
            onClose={() => setLyricsOpen(false)}
          />
        )}
      </Box>

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSettingsChange={(settings) => {
          console.log('Settings changed:', settings);
          success('Settings saved successfully');
        }}
      />

      {/* Keyboard Shortcuts Help Dialog - DISABLED FOR BETA.6 */}
      {/*<KeyboardShortcutsHelp
        open={isHelpOpen}
        shortcuts={shortcuts}
        onClose={closeHelp}
      />*/}
    </Box>

    {/* Bottom Player Bar - MOVED OUTSIDE overflow:hidden container */}
    <BottomPlayerBarUnified />
  </DragDropContext>
  );
}

export default ComfortableApp;
