import { useState, useEffect, useCallback } from 'react';
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
// Beta 13.0: Using PlayerBarV2 - Complete redesign with design system
// 100% design token compliance, memoized components, crossfade support
// Replaces BottomPlayerBarUnified with cleaner architecture
import PlayerBarV2Connected from './components/player-bar-v2/PlayerBarV2Connected';
import AutoMasteringPane from './components/AutoMasteringPane';
// Beta 13.0: EnhancementPaneV2 - Complete redesign with 10 focused components
// 100% design token compliance, 84% code reduction, drop-in replacement for AutoMasteringPane
import EnhancementPaneV2 from './components/enhancement-pane-v2';
import CozyLibraryView from './components/CozyLibraryView';
import GlobalSearch from './components/library/GlobalSearch';
import SettingsDialog from './components/settings/SettingsDialog';
import LyricsPanel from './components/player/LyricsPanel';
import KeyboardShortcutsHelp from './components/shared/KeyboardShortcutsHelp';
import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { useKeyboardShortcuts, KeyboardShortcut } from './hooks/useKeyboardShortcuts';
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
  const [viewKey, setViewKey] = useState(0); // Increment to force view reset
  const [searchResultView, setSearchResultView] = useState<{type: string; id: number} | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);
  // Beta 13.0: Feature flag to toggle between AutoMasteringPane (old) and EnhancementPaneV2 (new)
  const [useEnhancementPaneV2, setUseEnhancementPaneV2] = useState(
    process.env.REACT_APP_USE_ENHANCEMENT_PANE_V2 === 'true'
  );

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
        info(apiIsPlaying ? 'Paused' : 'Playing');
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
        const newVolume = Math.min(apiVolume + 10, 100);
        setApiVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'ArrowDown',
      description: 'Volume down',
      category: 'Playback',
      handler: () => {
        const newVolume = Math.max(apiVolume - 10, 0);
        setApiVolume(newVolume);
        info(`Volume: ${newVolume}%`);
      }
    },
    {
      key: 'm',
      description: 'Mute/Unmute',
      category: 'Playback',
      handler: () => {
        const newVolume = apiVolume > 0 ? 0 : 80;
        setApiVolume(newVolume);
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
        setViewKey(prev => prev + 1);
        info('Songs view');
      }
    },
    {
      key: '2',
      description: 'Show Albums',
      category: 'Navigation',
      handler: () => {
        setCurrentView('albums');
        setViewKey(prev => prev + 1);
        info('Albums view');
      }
    },
    {
      key: '3',
      description: 'Show Artists',
      category: 'Navigation',
      handler: () => {
        setCurrentView('artists');
        setViewKey(prev => prev + 1);
        info('Artists view');
      }
    },
    {
      key: '4',
      description: 'Show Playlists',
      category: 'Navigation',
      handler: () => {
        setCurrentView('playlists');
        setViewKey(prev => prev + 1);
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
        } else if (lyricsOpen) {
          setLyricsOpen(false);
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

  const handleSearchResultClick = (result: {type: string; id: number}) => {
    if (result.type === 'track') {
      // Play the track directly
      console.log('Play track from search:', result.id);
    } else if (result.type === 'album') {
      setCurrentView('albums');
      setViewKey(prev => prev + 1); // Force view reset
      setSearchResultView(result);
    } else if (result.type === 'artist') {
      setCurrentView('artists');
      setViewKey(prev => prev + 1); // Force view reset
      setSearchResultView(result);
    }
  };

  const handleMobileMenuToggle = () => {
    setMobileDrawerOpen(!mobileDrawerOpen);
  };

  const handleMobileNavigation = (view: string) => {
    setCurrentView(view);
    setViewKey(prev => prev + 1); // Force view reset
    setMobileDrawerOpen(false); // Close drawer after navigation on mobile
  };

  const handleSidebarNavigation = (view: string) => {
    setCurrentView(view);
    setViewKey(prev => prev + 1); // Force view reset
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
            onNavigate={handleSidebarNavigation}
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
              pb: '120px' // Space for bottom player bar (80px + 40px margin for better visibility)
            }}
          >
            <CozyLibraryView
              key={viewKey}
              onTrackPlay={handleTrackPlay}
              view={currentView}
            />
          </Box>
        </Box>

        {/* Right Auto-Mastering Pane - Hidden on mobile/tablet */}
        {/* Beta 13.0: Toggle between old AutoMasteringPane and new EnhancementPaneV2 */}
        {!isTablet && useEnhancementPaneV2 && (
          <EnhancementPaneV2
            collapsed={presetPaneCollapsed}
            onToggleCollapse={() => setPresetPaneCollapsed(!presetPaneCollapsed)}
            onMasteringToggle={handleMasteringToggle}
          />
        )}
        {!isTablet && !useEnhancementPaneV2 && (
          <AutoMasteringPane
            collapsed={presetPaneCollapsed}
            onToggleCollapse={() => setPresetPaneCollapsed(!presetPaneCollapsed)}
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

      {/* Keyboard Shortcuts Help Dialog - RE-ENABLED FOR BETA.11.1 */}
      <KeyboardShortcutsHelp
        open={isHelpOpen}
        shortcuts={shortcuts}
        onClose={closeHelp}
        formatShortcut={formatShortcut}
      />
    </Box>

    {/* Bottom Player Bar - Beta 13.0: PlayerBarV2 with design system */}
    <PlayerBarV2Connected />
  </DragDropContext>
  );
}

export default ComfortableApp;
