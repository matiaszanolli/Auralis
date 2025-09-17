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
  Equalizer,
  Favorite,
  TrendingUp,
  MusicNote
} from '@mui/icons-material';

import MagicalMusicPlayer from './components/MagicalMusicPlayer.tsx';
import CozyLibraryView from './components/CozyLibraryView.tsx';
import ClassicVisualizer from './components/ClassicVisualizer.tsx';
import EnhancedAudioPlayer from './components/EnhancedAudioPlayer.tsx';
import RealtimeAudioVisualizer from './components/RealtimeAudioVisualizer.tsx';
import AudioProcessingControls from './components/AudioProcessingControls.tsx';
import ABComparisonPlayer from './components/ABComparisonPlayer.tsx';
import { useWebSocket } from './hooks/useWebSocket.ts';
import { useLibraryStats } from './hooks/useLibraryStats.ts';

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
  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws');

  // Library statistics
  const { stats, isLoading: statsLoading, error: statsError } = useLibraryStats();

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
    { label: 'Audio Player', icon: <MusicNote /> },
    { label: 'Visualizer', icon: <Equalizer /> },
    { label: 'Favorites', icon: <Favorite /> },
    { label: 'Stats', icon: <TrendingUp /> }
  ];

  return (
    <Box
      sx={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 50%, #0d1421 100%)',
        color: 'white',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Magical Header */}
      <AppBar
        position="static"
        elevation={0}
        sx={{
          background: 'rgba(25, 118, 210, 0.1)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
        }}
      >
        <Toolbar>
          <Typography
            variant="h4"
            component="h1"
            fontWeight="bold"
            sx={{
              background: 'linear-gradient(45deg, #1976d2, #42a5f5, #90caf9)',
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
              opacity: 0.8,
              fontStyle: 'italic'
            }}
          >
            Rediscover the magic in your music
          </Typography>

          {/* Connection Status */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 2,
              py: 0.5,
              borderRadius: 2,
              background: connected ? 'rgba(76, 175, 80, 0.2)' : 'rgba(255, 152, 0, 0.2)',
              border: `1px solid ${connected ? '#4caf50' : '#ff9800'}`
            }}
          >
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: connected ? '#4caf50' : '#ff9800',
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
              color: 'rgba(255, 255, 255, 0.7)',
              '&.Mui-selected': {
                color: '#42a5f5'
              }
            },
            '& .MuiTabs-indicator': {
              background: 'linear-gradient(90deg, #1976d2, #42a5f5)',
              height: 3,
              borderRadius: 2
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

        {/* Enhanced Audio Player */}
        <TabPanel value={currentTab} index={1}>
          <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ mb: 4, textAlign: 'center' }}>
              <Typography variant="h3" component="h2" fontWeight="bold" gutterBottom>
                🎵 Enhanced Audio Player
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                Real-time audio processing with advanced controls
              </Typography>
            </Box>

            <Box sx={{ maxWidth: 800, mx: 'auto', mb: 4 }}>
              <EnhancedAudioPlayer websocket={connected ? new WebSocket('ws://localhost:8000/ws') : null} />
            </Box>

            {/* Real-time Audio Visualizer */}
            <Box sx={{ maxWidth: 900, mx: 'auto', mb: 4 }}>
              <RealtimeAudioVisualizer websocket={connected ? new WebSocket('ws://localhost:8000/ws') : null} />
            </Box>

            {/* Advanced Audio Processing Controls */}
            <Box sx={{ maxWidth: 1000, mx: 'auto', mb: 4 }}>
              <AudioProcessingControls
                websocket={connected ? new WebSocket('ws://localhost:8000/ws') : null}
                onSettingsChange={(settings) => console.log('Processing settings updated:', settings)}
              />
            </Box>

            {/* A/B Comparison Player */}
            <Box sx={{ maxWidth: 1000, mx: 'auto', mb: 4 }}>
              <ABComparisonPlayer websocket={connected ? new WebSocket('ws://localhost:8000/ws') : null} />
            </Box>

            <Box sx={{ mt: 4, textAlign: 'center' }}>
              <Paper
                elevation={2}
                sx={{
                  p: 3,
                  background: 'rgba(255, 255, 255, 0.05)',
                  backdropFilter: 'blur(10px)',
                  borderRadius: 3
                }}
              >
                <Typography variant="h6" gutterBottom>
                  🎛️ Features
                </Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2, mt: 2 }}>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Real-time Level Matching</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Automatic dynamic range enhancement
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Queue Management</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Advanced playlist and queue controls
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Audio Analysis</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Real-time peak and RMS monitoring
                    </Typography>
                  </Box>
                  <Box>
                    <Typography variant="subtitle2" gutterBottom>Processing Controls</Typography>
                    <Typography variant="body2" color="text.secondary">
                      Fine-tune audio enhancement settings
                    </Typography>
                  </Box>
                </Box>
              </Paper>
            </Box>
          </Container>
        </TabPanel>

        {/* Visualizer */}
        <TabPanel value={currentTab} index={2}>
          <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ mb: 4, textAlign: 'center' }}>
              <Typography variant="h3" component="h2" fontWeight="bold" gutterBottom>
                🎵 Classic Audio Experience
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                Nostalgic visualizations that bring music to life
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
                    background: 'rgba(255, 255, 255, 0.05)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: 3
                  }}
                >
                  <Typography variant="h6" gutterBottom>
                    Now Playing
                  </Typography>
                  <Typography variant="body1">
                    {currentTrack.title} - {currentTrack.artist}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {currentTrack.album}
                  </Typography>
                </Paper>
              </Box>
            )}
          </Container>
        </TabPanel>

        {/* Favorites */}
        <TabPanel value={currentTab} index={3}>
          <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ textAlign: 'center', py: 8 }}>
              <Favorite sx={{ fontSize: 64, color: '#f44336', mb: 2 }} />
              <Typography variant="h4" gutterBottom>
                Your Favorite Tracks
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Coming soon - heart tracks to build your personal collection
              </Typography>
            </Box>
          </Container>
        </TabPanel>

        {/* Stats */}
        <TabPanel value={currentTab} index={4}>
          <Container maxWidth="lg" sx={{ py: 4 }}>
            <Typography variant="h3" component="h2" fontWeight="bold" gutterBottom textAlign="center">
              📊 Your Music Journey
            </Typography>

            {stats && (
              <Box sx={{ mt: 4 }}>
                <Paper
                  elevation={4}
                  sx={{
                    p: 4,
                    background: 'rgba(255, 255, 255, 0.05)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: 3
                  }}
                >
                  <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 3 }}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h2" color="primary" fontWeight="bold">
                        {stats.total_tracks || 0}
                      </Typography>
                      <Typography variant="h6" color="text.secondary">
                        Magical Tracks
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h2" color="secondary" fontWeight="bold">
                        {(stats.total_filesize_gb || 0).toFixed(1)}
                      </Typography>
                      <Typography variant="h6" color="text.secondary">
                        GB of Music
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h2" color="success.main" fontWeight="bold">
                        ✨
                      </Typography>
                      <Typography variant="h6" color="text.secondary">
                        Enhanced Quality
                      </Typography>
                    </Box>
                  </Box>
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
              background: 'linear-gradient(45deg, #1976d2, #42a5f5)',
              color: 'white',
              borderRadius: 3,
              zIndex: 2000,
              minWidth: 250
            }}
          >
            <Typography variant="body2" fontWeight="bold">
              {notification.message}
            </Typography>
          </Paper>
        </Fade>
      )}
    </Box>
  );
}

export default MagicalApp;