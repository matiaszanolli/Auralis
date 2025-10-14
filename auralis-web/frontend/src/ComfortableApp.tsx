import React, { useState } from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  Fade,
  Paper,
  Typography
} from '@mui/material';
import {
  Search
} from '@mui/icons-material';

import Sidebar from './components/Sidebar.tsx';
import BottomPlayerBar from './components/BottomPlayerBar.tsx';
import PresetPane from './components/PresetPane.tsx';
import CozyLibraryView from './components/CozyLibraryView.tsx';
import { useWebSocket } from './hooks/useWebSocket.ts';

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
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // WebSocket connection for real-time updates
  const { connected } = useWebSocket('ws://localhost:8000/ws');

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

    // Show notification
    setNotification({
      message: enabled ? '✨ Auralis magic enabled' : 'Enhancement disabled',
      type: 'info'
    });

    // Hide notification after 3 seconds
    setTimeout(() => setNotification(null), 3000);
  };

  const handlePlayerEnhancementToggle = (enabled: boolean) => {
    if (currentTrack) {
      setCurrentTrack({ ...currentTrack, isEnhanced: enabled });
      handleEnhancementToggle(currentTrack.id, enabled);
    }
  };

  const handlePresetChange = (preset: string) => {
    console.log('Preset changed to:', preset);
    setNotification({
      message: `Preset changed to ${preset}`,
      type: 'info'
    });
    setTimeout(() => setNotification(null), 3000);
  };

  const handleMasteringToggle = (enabled: boolean) => {
    console.log('Mastering:', enabled ? 'enabled' : 'disabled');
    setNotification({
      message: enabled ? '✨ Mastering enabled' : 'Mastering disabled',
      type: 'info'
    });
    setTimeout(() => setNotification(null), 3000);
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
            <TextField
              fullWidth
              placeholder="Search songs, albums, artists..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search sx={{ color: 'var(--silver)', opacity: 0.5 }} />
                  </InputAdornment>
                )
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  fontFamily: 'var(--font-body)',
                  color: 'var(--silver)',
                  background: 'var(--charcoal)',
                  borderRadius: 'var(--radius-md)',
                  '& fieldset': {
                    borderColor: 'rgba(226, 232, 240, 0.1)'
                  },
                  '&:hover fieldset': {
                    borderColor: 'rgba(226, 232, 240, 0.2)'
                  },
                  '&.Mui-focused fieldset': {
                    borderColor: 'var(--aurora-violet)',
                    borderWidth: 1
                  }
                },
                '& .MuiOutlinedInput-input': {
                  padding: '12px 14px'
                }
              }}
            />
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
      </Box>

      {/* Bottom Player Bar - Fixed */}
      <BottomPlayerBar
        currentTrack={currentTrack || undefined}
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onEnhancementToggle={handlePlayerEnhancementToggle}
      />

      {/* Notification Toast */}
      {notification && (
        <Fade in={true}>
          <Paper
            elevation={8}
            sx={{
              position: 'fixed',
              top: 20,
              right: 20,
              p: 2,
              background: 'var(--aurora-gradient)',
              color: 'white',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--glow-medium)',
              zIndex: 2000,
              minWidth: 250
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'var(--font-heading)',
                fontWeight: 600
              }}
            >
              {notification.message}
            </Typography>
          </Paper>
        </Fade>
      )}
    </Box>
  );
}

export default ComfortableApp;
