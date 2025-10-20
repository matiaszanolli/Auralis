import React, { useState, useEffect } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Tab,
  Tabs,
  Paper,
  Fade,
  useTheme,
  useMediaQuery
} from '@mui/material';
import {
  LibraryMusic,
  Equalizer
} from '@mui/icons-material';

import MagicalMusicPlayer from './components/MagicalMusicPlayer';
import CozyLibraryView from './components/CozyLibraryView';
import ClassicVisualizer from './components/ClassicVisualizer';
import { useWebSocket } from './hooks/useWebSocket';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  isEnhanced?: boolean;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`magical-tabpanel-${index}`}
      aria-labelledby={`magical-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Fade in={true} timeout={500}>
          <Box>{children}</Box>
        </Fade>
      )}
    </div>
  );
}

function MagicalApp() {
  const [currentTab, setCurrentTab] = useState(0);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // WebSocket connection for real-time updates
  const { connected, lastMessage } = useWebSocket('ws://localhost:8765/ws');

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const message = JSON.parse(lastMessage);

        switch (message.type) {
          case 'scan_complete':
            setNotification({
              message: `✨ Magic complete: ${message.data.files_added} tracks enhanced`,
              type: 'success'
            });
            break;

          case 'scan_error':
            setNotification({
              message: `Scan failed: ${message.data.error}`,
              type: 'error'
            });
            break;
        }
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    }
  }, [lastMessage]);

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

    // Show magical notification
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

  const tabsData = [
    { label: 'Your Music', icon: <LibraryMusic /> },
    { label: 'Visualizer', icon: <Equalizer /> }
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'var(--midnight-blue)',
        color: 'var(--silver)',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Magical Header */}
      <AppBar
        position="static"
        elevation={0}
        sx={{
          background: 'var(--charcoal)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(226, 232, 240, 0.1)'
        }}
      >
        <Toolbar>
          <Typography
            variant="h4"
            component="h1"
            sx={{
              fontFamily: 'var(--font-heading)',
              fontWeight: 600,
              background: 'var(--aurora-gradient)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              mr: 2
            }}
          >
            ✨ Auralis
          </Typography>

          <Typography
            variant="subtitle1"
            sx={{
              flexGrow: 1,
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              opacity: 0.8,
              fontStyle: 'italic'
            }}
          >
            Your music player with magical audio enhancement
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
            <Typography variant="caption">
              {connected ? 'Connected' : 'Connecting...'}
            </Typography>
          </Box>
        </Toolbar>

        {/* Navigation Tabs */}
        <Tabs
          value={currentTab}
          onChange={(_, newValue) => setCurrentTab(newValue)}
          centered={!isMobile}
          variant={isMobile ? 'scrollable' : 'standard'}
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': {
              fontFamily: 'var(--font-heading)',
              fontWeight: 600,
              color: 'rgba(226, 232, 240, 0.7)',
              '&.Mui-selected': {
                color: 'var(--aurora-violet)'
              }
            },
            '& .MuiTabs-indicator': {
              background: 'var(--aurora-horizontal)',
              height: 3,
              borderRadius: 'var(--radius-sm)'
            }
          }}
        >
          {tabsData.map((tab, index) => (
            <Tab
              key={index}
              icon={tab.icon}
              label={tab.label}
              iconPosition="start"
              sx={{ minHeight: 48 }}
            />
          ))}
        </Tabs>
      </AppBar>

      {/* Main Content */}
      <Box sx={{ flex: 1, overflow: 'hidden' }}>
        {/* Your Music */}
        <TabPanel value={currentTab} index={0}>
          <CozyLibraryView
            onTrackPlay={handleTrackPlay}
            onEnhancementToggle={handleEnhancementToggle}
          />
        </TabPanel>

        {/* Visualizer */}
        <TabPanel value={currentTab} index={1}>
          <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ mb: 4, textAlign: 'center' }}>
              <Typography
                variant="h3"
                component="h2"
                sx={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 600
                }}
                gutterBottom
              >
                🎵 Audio Visualizer
              </Typography>
              <Typography
                variant="subtitle1"
                sx={{
                  fontFamily: 'var(--font-body)',
                  color: 'var(--silver)',
                  opacity: 0.7
                }}
              >
                Watch your music come alive
              </Typography>
            </Box>

            <ClassicVisualizer
              isPlaying={isPlaying}
              width={800}
              height={300}
            />

            {currentTrack && (
              <Box sx={{ mt: 4 }}>
                <Paper
                  elevation={4}
                  sx={{
                    p: 3,
                    background: 'var(--charcoal)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid rgba(226, 232, 240, 0.1)'
                  }}
                >
                  <Typography
                    variant="h6"
                    sx={{ fontFamily: 'var(--font-heading)', fontWeight: 600 }}
                    gutterBottom
                  >
                    Now Playing
                  </Typography>
                  <Typography
                    variant="body1"
                    sx={{ fontFamily: 'var(--font-body)', color: 'var(--silver)' }}
                  >
                    {currentTrack.title} - {currentTrack.artist}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ fontFamily: 'var(--font-body)', color: 'var(--silver)', opacity: 0.7 }}
                  >
                    {currentTrack.album}
                  </Typography>
                </Paper>
              </Box>
            )}
          </Container>
        </TabPanel>
      </Box>

      {/* Magical Music Player - Always Visible */}
      <Box sx={{ position: 'sticky', bottom: 0, zIndex: 1000 }}>
        <MagicalMusicPlayer
          currentTrack={currentTrack || undefined}
          isPlaying={isPlaying}
          onPlayPause={handlePlayPause}
          onEnhancementToggle={handlePlayerEnhancementToggle}
        />
      </Box>

      {/* Magical Notification */}
      {notification && (
        <Fade in={true}>
          <Paper
            elevation={8}
            sx={{
              position: 'fixed',
              top: 100,
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

export default MagicalApp;