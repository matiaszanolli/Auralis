import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  Typography,
  IconButton,
  useMediaQuery,
  useTheme,
  Drawer
} from '@mui/material';
import {
  Search,
  Menu as MenuIcon
} from '@mui/icons-material';

import Sidebar from './components/Sidebar';
// MSE Progressive Streaming integration - DISABLED (initialization issues + complexity)
// Issues: SourceBuffer errors, rapid component mounting/unmounting, destroy() method issues
// Decision: Get multi-tier buffer working solidly first, then reintegrate MSE with proper testing
// See: docs/sessions/oct27_mse_and_fingerprints/MSE_BUFFER_CONFLICT.md
import BottomPlayerBarConnected from './components/BottomPlayerBarConnected';
import PresetPane from './components/PresetPane';
import CozyLibraryView from './components/CozyLibraryView';
import GlobalSearch from './components/library/GlobalSearch';
import SettingsDialog from './components/settings/SettingsDialog';
import LyricsPanel from './components/player/LyricsPanel';
import { useWebSocketContext } from './contexts/WebSocketContext';
import { useToast } from './components/shared/Toast';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

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

  // Auto-collapse sidebar on mobile and hide preset pane on tablet
  useEffect(() => {
    if (isMobile) {
      setSidebarCollapsed(true);
    }
    if (isTablet) {
      setPresetPaneCollapsed(true);
    }
  }, [isMobile, isTablet]);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onPlayPause: handlePlayPause,
    onNext: () => {
      // TODO: Implement next track
      info('Next track');
    },
    onPrevious: () => {
      // TODO: Implement previous track
      info('Previous track');
    },
    onVolumeUp: () => {
      // TODO: Implement volume up
      info('Volume up');
    },
    onVolumeDown: () => {
      // TODO: Implement volume down
      info('Volume down');
    },
    onMute: () => {
      // TODO: Implement mute
      info('Mute toggled');
    },
    onToggleLyrics: () => {
      setLyricsOpen(!lyricsOpen);
      info(lyricsOpen ? 'Lyrics hidden' : 'Lyrics shown');
    },
    onToggleEnhancement: () => {
      if (currentTrack) {
        const newState = !currentTrack.isEnhanced;
        handlePlayerEnhancementToggle(newState);
      }
    },
    onFocusSearch: () => {
      // Focus search input
      const searchInput = document.querySelector('input[placeholder*="Search"]') as HTMLInputElement;
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    },
    onOpenSettings: () => {
      setSettingsOpen(true);
    },
    onPresetChange: handlePresetChange
  });

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

  return (
    <Box
      sx={{
        width: '100vw',
        height: '100vh',
        background: 'var(--midnight-blue)',
        color: 'var(--silver)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
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

        {/* Mobile Drawer - Shown on mobile */}
        {isMobile && (
          <Drawer
            anchor="left"
            open={mobileDrawerOpen}
            onClose={() => setMobileDrawerOpen(false)}
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
          </Drawer>
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
                    sx={{
                      color: 'var(--silver)',
                      '&:hover': {
                        background: 'rgba(102, 126, 234, 0.1)',
                      },
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
              pb: '100px' // Space for bottom player bar
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

      {/* Bottom Player Bar - Fixed - REAL PLAYBACK! */}
      <BottomPlayerBarConnected
        onToggleLyrics={() => setLyricsOpen(!lyricsOpen)}
        onTimeUpdate={(time) => setPlaybackTime(time)}
      />

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSettingsChange={(settings) => {
          console.log('Settings changed:', settings);
          success('Settings saved successfully');
        }}
      />
    </Box>
  );
}

export default ComfortableApp;
