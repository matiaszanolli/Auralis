import React, { useState } from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  Typography
} from '@mui/material';
import {
  Search
} from '@mui/icons-material';

import Sidebar from './components/Sidebar';
import BottomPlayerBarConnected from './components/BottomPlayerBarConnected';
import PresetPane from './components/PresetPane';
import CozyLibraryView from './components/CozyLibraryView';
import GlobalSearch from './components/library/GlobalSearch';
import SettingsDialog from './components/settings/SettingsDialog';
import LyricsPanel from './components/player/LyricsPanel';
import { useWebSocket } from './hooks/useWebSocket';
import { useToast } from './components/shared/Toast';

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [presetPaneCollapsed, setPresetPaneCollapsed] = useState(false);
  const [lyricsOpen, setLyricsOpen] = useState(false);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState('songs'); // songs, favourites, recent, etc.
  const [searchResultView, setSearchResultView] = useState<{type: string; id: number} | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);

  // WebSocket connection for real-time updates
  const { connected } = useWebSocket('ws://localhost:8765/ws');

  // Toast notifications
  const { success, info } = useToast();

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
        {/* Left Sidebar */}
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          onNavigate={setCurrentView}
          onOpenSettings={() => setSettingsOpen(true)}
        />

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

              {/* Connection Status */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 2,
                  py: 0.5,
                  borderRadius: 'var(--radius-md)',
                  background: connected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                  border: `1px solid ${connected ? 'var(--success)' : 'var(--warning)'}`
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: connected ? 'var(--success)' : 'var(--warning)',
                    animation: connected ? 'pulse 2s infinite' : 'none',
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
                  {connected ? 'Connected' : 'Connecting...'}
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

        {/* Right Preset Pane - Optional */}
        <PresetPane
          collapsed={presetPaneCollapsed}
          onToggleCollapse={() => setPresetPaneCollapsed(!presetPaneCollapsed)}
          onPresetChange={handlePresetChange}
          onMasteringToggle={handleMasteringToggle}
        />

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
