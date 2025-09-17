import React, { useState, useRef, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  ButtonGroup,
  Slider,
  IconButton,
  Grid,
  Paper,
  Chip,
  LinearProgress,
  Divider,
  Tooltip,
  Alert
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  CompareArrows,
  VolumeUp,
  Sync,
  Visibility,
  VisibilityOff,
  SwapHoriz,
  FileUpload
} from '@mui/icons-material';

interface Track {
  id: string;
  name: string;
  path: string;
  duration: number;
  loaded: boolean;
}

interface ABComparisonPlayerProps {
  websocket: WebSocket | null;
}

const ABComparisonPlayer: React.FC<ABComparisonPlayerProps> = ({ websocket }) => {
  const [trackA, setTrackA] = useState<Track | null>(null);
  const [trackB, setTrackB] = useState<Track | null>(null);
  const [activeTrack, setActiveTrack] = useState<'A' | 'B' | 'both'>('A');
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [volume, setVolume] = useState(50);
  const [syncPlayback, setSyncPlayback] = useState(true);
  const [blindTest, setBlindTest] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fileInputRefA = useRef<HTMLInputElement>(null);
  const fileInputRefB = useRef<HTMLInputElement>(null);

  // API call helper
  const apiCall = useCallback(async (endpoint: string, method: string = 'GET', body?: any) => {
    try {
      const response = await fetch(`/api${endpoint}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'API call failed');
      }

      return await response.json();
    } catch (err) {
      console.error('API Error:', err);
      throw err;
    }
  }, []);

  // Load track into player
  const loadTrack = async (trackPath: string, slot: 'A' | 'B') => {
    setIsLoading(true);
    try {
      await apiCall('/player/load', 'POST', { track_path: trackPath });

      const newTrack: Track = {
        id: `track_${slot}_${Date.now()}`,
        name: trackPath.split('/').pop() || 'Unknown Track',
        path: trackPath,
        duration: 180, // Mock duration
        loaded: true
      };

      if (slot === 'A') {
        setTrackA(newTrack);
      } else {
        setTrackB(newTrack);
      }

      // Broadcast track load via WebSocket
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
          type: 'ab_track_loaded',
          data: { slot, track: newTrack }
        }));
      }

    } catch (err) {
      console.error(`Failed to load track ${slot}:`, err);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle file upload
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>, slot: 'A' | 'B') => {
    const file = event.target.files?.[0];
    if (!file) return;

    // For demo purposes, create a mock track
    const mockTrack: Track = {
      id: `upload_${slot}_${Date.now()}`,
      name: file.name,
      path: URL.createObjectURL(file),
      duration: 200, // Mock duration
      loaded: true
    };

    if (slot === 'A') {
      setTrackA(mockTrack);
    } else {
      setTrackB(mockTrack);
    }
  };

  // Playback controls
  const handlePlay = async () => {
    try {
      await apiCall('/player/play', 'POST');
      setIsPlaying(true);

      // Broadcast playback state
      if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify({
          type: 'ab_playback_started',
          data: { active_track: activeTrack }
        }));
      }
    } catch (err) {
      console.error('Failed to start playback:', err);
    }
  };

  const handlePause = async () => {
    try {
      await apiCall('/player/pause', 'POST');
      setIsPlaying(false);
    } catch (err) {
      console.error('Failed to pause playback:', err);
    }
  };

  const handleStop = async () => {
    try {
      await apiCall('/player/stop', 'POST');
      setIsPlaying(false);
      setPosition(0);
    } catch (err) {
      console.error('Failed to stop playback:', err);
    }
  };

  // Switch between tracks
  const switchToTrack = (track: 'A' | 'B') => {
    setActiveTrack(track);

    // Load the selected track
    const selectedTrack = track === 'A' ? trackA : trackB;
    if (selectedTrack) {
      loadTrack(selectedTrack.path, track);
    }

    // Broadcast track switch
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: 'ab_track_switched',
        data: { active_track: track }
      }));
    }
  };

  // Quick A/B switch
  const quickSwitch = () => {
    const newTrack = activeTrack === 'A' ? 'B' : 'A';
    switchToTrack(newTrack);
  };

  // Sync position when switching tracks
  const handleSeek = async (newPosition: number) => {
    setPosition(newPosition);
    try {
      await apiCall('/player/seek', 'POST', { position: newPosition });
    } catch (err) {
      console.error('Failed to seek:', err);
    }
  };

  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get current track info
  const currentTrack = activeTrack === 'A' ? trackA : trackB;
  const otherTrack = activeTrack === 'A' ? trackB : trackA;

  return (
    <Card
      elevation={3}
      sx={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        borderRadius: 3
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CompareArrows /> A/B Comparison Player
          </Typography>

          <Box display="flex" alignItems="center" gap={2}>
            <Chip
              label={blindTest ? 'Blind Test ON' : 'Blind Test OFF'}
              icon={blindTest ? <VisibilityOff /> : <Visibility />}
              onClick={() => setBlindTest(!blindTest)}
              variant={blindTest ? 'filled' : 'outlined'}
              sx={{
                color: 'white',
                borderColor: 'rgba(255,255,255,0.5)',
                backgroundColor: blindTest ? 'rgba(255,255,255,0.2)' : 'transparent'
              }}
            />

            <Tooltip title="Quick A/B Switch">
              <IconButton
                onClick={quickSwitch}
                disabled={!trackA || !trackB}
                sx={{
                  color: 'white',
                  backgroundColor: 'rgba(255,255,255,0.1)',
                  '&:hover': { backgroundColor: 'rgba(255,255,255,0.2)' }
                }}
              >
                <SwapHoriz />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Track A Section */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={2}
              sx={{
                p: 2,
                background: activeTrack === 'A' ? 'rgba(76, 175, 80, 0.2)' : 'rgba(255,255,255,0.1)',
                border: activeTrack === 'A' ? '2px solid #4caf50' : '1px solid rgba(255,255,255,0.2)',
                borderRadius: 2
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" color={activeTrack === 'A' ? '#4caf50' : 'white'}>
                  Track A {blindTest ? '(?)' : '(Original)'}
                </Typography>
                <Button
                  variant={activeTrack === 'A' ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => switchToTrack('A')}
                  disabled={!trackA}
                  sx={{
                    color: 'white',
                    borderColor: 'rgba(255,255,255,0.5)',
                    backgroundColor: activeTrack === 'A' ? 'rgba(76, 175, 80, 0.8)' : 'transparent'
                  }}
                >
                  Select A
                </Button>
              </Box>

              {trackA ? (
                <Box>
                  <Typography variant="body2" gutterBottom>
                    {trackA.name}
                  </Typography>
                  <Typography variant="caption" color="rgba(255,255,255,0.7)">
                    Duration: {formatTime(trackA.duration)}
                  </Typography>
                </Box>
              ) : (
                <Box>
                  <input
                    type="file"
                    ref={fileInputRefA}
                    style={{ display: 'none' }}
                    accept="audio/*"
                    onChange={(e) => handleFileUpload(e, 'A')}
                  />
                  <Button
                    variant="outlined"
                    startIcon={<FileUpload />}
                    onClick={() => fileInputRefA.current?.click()}
                    sx={{
                      color: 'white',
                      borderColor: 'rgba(255,255,255,0.5)',
                      width: '100%'
                    }}
                  >
                    Load Track A
                  </Button>
                </Box>
              )}
            </Paper>
          </Grid>

          {/* Track B Section */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={2}
              sx={{
                p: 2,
                background: activeTrack === 'B' ? 'rgba(33, 150, 243, 0.2)' : 'rgba(255,255,255,0.1)',
                border: activeTrack === 'B' ? '2px solid #2196f3' : '1px solid rgba(255,255,255,0.2)',
                borderRadius: 2
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6" color={activeTrack === 'B' ? '#2196f3' : 'white'}>
                  Track B {blindTest ? '(?)' : '(Enhanced)'}
                </Typography>
                <Button
                  variant={activeTrack === 'B' ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => switchToTrack('B')}
                  disabled={!trackB}
                  sx={{
                    color: 'white',
                    borderColor: 'rgba(255,255,255,0.5)',
                    backgroundColor: activeTrack === 'B' ? 'rgba(33, 150, 243, 0.8)' : 'transparent'
                  }}
                >
                  Select B
                </Button>
              </Box>

              {trackB ? (
                <Box>
                  <Typography variant="body2" gutterBottom>
                    {trackB.name}
                  </Typography>
                  <Typography variant="caption" color="rgba(255,255,255,0.7)">
                    Duration: {formatTime(trackB.duration)}
                  </Typography>
                </Box>
              ) : (
                <Box>
                  <input
                    type="file"
                    ref={fileInputRefB}
                    style={{ display: 'none' }}
                    accept="audio/*"
                    onChange={(e) => handleFileUpload(e, 'B')}
                  />
                  <Button
                    variant="outlined"
                    startIcon={<FileUpload />}
                    onClick={() => fileInputRefB.current?.click()}
                    sx={{
                      color: 'white',
                      borderColor: 'rgba(255,255,255,0.5)',
                      width: '100%'
                    }}
                  >
                    Load Track B
                  </Button>
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>

        <Divider sx={{ my: 3, borderColor: 'rgba(255,255,255,0.2)' }} />

        {/* Playback Controls */}
        <Box mb={3}>
          <Typography variant="subtitle2" gutterBottom>
            Now Playing: {currentTrack ? `Track ${activeTrack} - ${currentTrack.name}` : 'No track selected'}
          </Typography>

          {/* Progress */}
          {currentTrack && (
            <Box mb={2}>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="caption">
                  {formatTime(position)}
                </Typography>
                <Typography variant="caption">
                  {formatTime(currentTrack.duration)}
                </Typography>
              </Box>
              <Slider
                value={position}
                max={currentTrack.duration}
                onChange={(_, value) => handleSeek(value as number)}
                sx={{
                  color: 'rgba(255,255,255,0.8)',
                  '& .MuiSlider-thumb': { backgroundColor: 'white' }
                }}
              />
            </Box>
          )}

          {/* Control Buttons */}
          <Box display="flex" justifyContent="center" alignItems="center" gap={2} mb={2}>
            <ButtonGroup variant="contained" sx={{ backgroundColor: 'rgba(255,255,255,0.1)' }}>
              <Button
                onClick={() => switchToTrack('A')}
                disabled={!trackA}
                variant={activeTrack === 'A' ? 'contained' : 'outlined'}
                sx={{
                  backgroundColor: activeTrack === 'A' ? '#4caf50' : 'transparent',
                  color: 'white',
                  borderColor: 'rgba(255,255,255,0.5)'
                }}
              >
                A
              </Button>
              <Button
                onClick={() => switchToTrack('B')}
                disabled={!trackB}
                variant={activeTrack === 'B' ? 'contained' : 'outlined'}
                sx={{
                  backgroundColor: activeTrack === 'B' ? '#2196f3' : 'transparent',
                  color: 'white',
                  borderColor: 'rgba(255,255,255,0.5)'
                }}
              >
                B
              </Button>
            </ButtonGroup>

            <IconButton
              onClick={isPlaying ? handlePause : handlePlay}
              disabled={!currentTrack || isLoading}
              size="large"
              sx={{
                color: 'white',
                backgroundColor: 'rgba(255,255,255,0.2)',
                '&:hover': { backgroundColor: 'rgba(255,255,255,0.3)' }
              }}
            >
              {isPlaying ? <Pause /> : <PlayArrow />}
            </IconButton>

            <IconButton
              onClick={handleStop}
              disabled={!currentTrack}
              sx={{ color: 'white' }}
            >
              <Stop />
            </IconButton>
          </Box>

          {/* Volume Control */}
          <Box display="flex" alignItems="center" gap={1}>
            <VolumeUp sx={{ color: 'white' }} />
            <Slider
              value={volume}
              onChange={(_, value) => setVolume(value as number)}
              sx={{
                color: 'rgba(255,255,255,0.8)',
                '& .MuiSlider-thumb': { backgroundColor: 'white' }
              }}
            />
            <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'right' }}>
              {volume}%
            </Typography>
          </Box>
        </Box>

        {/* Status */}
        {(!trackA || !trackB) && (
          <Alert
            severity="info"
            sx={{
              backgroundColor: 'rgba(25, 118, 210, 0.1)',
              color: 'white',
              '& .MuiAlert-icon': { color: 'white' }
            }}
          >
            Load both tracks to enable A/B comparison. Track A should be your original, Track B your enhanced version.
          </Alert>
        )}

        {isLoading && (
          <Box mt={2}>
            <LinearProgress
              sx={{
                backgroundColor: 'rgba(255,255,255,0.2)',
                '& .MuiLinearProgress-bar': { backgroundColor: 'rgba(255,255,255,0.8)' }
              }}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default ABComparisonPlayer;