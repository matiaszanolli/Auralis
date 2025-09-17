import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  IconButton,
  Typography,
  Slider,
  Switch,
  FormControlLabel,
  LinearProgress,
  Chip,
  Grid,
  Tooltip,
  Alert
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  SkipNext,
  SkipPrevious,
  VolumeUp,
  VolumeDown,
  Shuffle,
  Repeat,
  GraphicEq,
  Tune
} from '@mui/icons-material';

interface PlayerStatus {
  state: string;
  volume: number;
  position: number;
  duration: number;
  current_track: string | null;
  queue_size: number;
  shuffle_enabled: boolean;
  repeat_mode: string;
  analysis?: {
    peak_level: number;
    rms_level: number;
    frequency_spectrum: number[];
  };
}

interface EnhancedAudioPlayerProps {
  websocket: WebSocket | null;
}

const EnhancedAudioPlayer: React.FC<EnhancedAudioPlayerProps> = ({ websocket }) => {
  const [playerStatus, setPlayerStatus] = useState<PlayerStatus>({
    state: 'stopped',
    volume: 1.0,
    position: 0,
    duration: 0,
    current_track: null,
    queue_size: 0,
    shuffle_enabled: false,
    repeat_mode: 'none'
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [levelMatchingEnabled, setLevelMatchingEnabled] = useState(true);

  // API call helper
  const apiCall = useCallback(async (endpoint: string, method: string = 'GET', body?: any) => {
    try {
      setError(null);
      const response = await fetch(`/api${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'API call failed');
      }

      return await response.json();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('API Error:', errorMessage);
      throw err;
    }
  }, []);

  // Fetch player status
  const fetchPlayerStatus = useCallback(async () => {
    try {
      const status = await apiCall('/player/status');
      setPlayerStatus(status);
    } catch (err) {
      console.error('Failed to fetch player status:', err);
    }
  }, [apiCall]);

  // WebSocket message handler
  useEffect(() => {
    if (!websocket) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        switch (message.type) {
          case 'playback_started':
          case 'playback_paused':
          case 'playback_stopped':
          case 'track_loaded':
          case 'volume_changed':
          case 'position_changed':
          case 'track_changed':
            fetchPlayerStatus();
            break;
          default:
            console.log('Unhandled WebSocket message:', message);
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };

    websocket.addEventListener('message', handleMessage);
    return () => websocket.removeEventListener('message', handleMessage);
  }, [websocket, fetchPlayerStatus]);

  // Fetch initial status
  useEffect(() => {
    fetchPlayerStatus();
    const interval = setInterval(fetchPlayerStatus, 2000); // Poll every 2 seconds
    return () => clearInterval(interval);
  }, [fetchPlayerStatus]);

  // Player control handlers
  const handlePlay = async () => {
    setIsLoading(true);
    try {
      await apiCall('/player/play', 'POST');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePause = async () => {
    setIsLoading(true);
    try {
      await apiCall('/player/pause', 'POST');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      await apiCall('/player/stop', 'POST');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNext = async () => {
    setIsLoading(true);
    try {
      await apiCall('/player/next', 'POST');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrevious = async () => {
    setIsLoading(true);
    try {
      await apiCall('/player/previous', 'POST');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVolumeChange = async (event: Event, newValue: number | number[]) => {
    const volume = Array.isArray(newValue) ? newValue[0] : newValue;
    try {
      await apiCall('/player/volume', 'POST', { volume: volume / 100 });
    } catch (err) {
      console.error('Failed to set volume:', err);
    }
  };

  const handleSeek = async (event: Event, newValue: number | number[]) => {
    const position = Array.isArray(newValue) ? newValue[0] : newValue;
    try {
      await apiCall('/player/seek', 'POST', { position });
    } catch (err) {
      console.error('Failed to seek:', err);
    }
  };

  const handleLevelMatchingToggle = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const enabled = event.target.checked;
    setLevelMatchingEnabled(enabled);
    try {
      await apiCall('/processing/enable_matching', 'POST', { enabled });
    } catch (err) {
      console.error('Failed to toggle level matching:', err);
    }
  };

  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Get playback progress percentage
  const getProgress = (): number => {
    if (playerStatus.duration === 0) return 0;
    return (playerStatus.position / playerStatus.duration) * 100;
  };

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
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Track Info */}
        <Box mb={2}>
          <Typography variant="h6" gutterBottom>
            🎵 Enhanced Audio Player
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.9 }}>
            {playerStatus.current_track || 'No track loaded'}
          </Typography>

          {/* Player Status Chips */}
          <Box mt={1} display="flex" gap={1} flexWrap="wrap">
            <Chip
              label={playerStatus.state.toUpperCase()}
              size="small"
              color={playerStatus.state === 'playing' ? 'success' : 'default'}
              variant="outlined"
            />
            <Chip
              label={`Queue: ${playerStatus.queue_size}`}
              size="small"
              variant="outlined"
            />
            {playerStatus.analysis && (
              <Chip
                label={`Peak: ${(playerStatus.analysis.peak_level * 100).toFixed(1)}%`}
                size="small"
                variant="outlined"
                icon={<GraphicEq />}
              />
            )}
          </Box>
        </Box>

        {/* Progress Bar */}
        <Box mb={2}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="caption">
              {formatTime(playerStatus.position)}
            </Typography>
            <Typography variant="caption">
              {formatTime(playerStatus.duration)}
            </Typography>
          </Box>

          {playerStatus.duration > 0 ? (
            <Slider
              value={playerStatus.position}
              max={playerStatus.duration}
              onChange={handleSeek}
              sx={{
                color: 'rgba(255,255,255,0.8)',
                '& .MuiSlider-thumb': {
                  backgroundColor: 'white',
                }
              }}
            />
          ) : (
            <LinearProgress
              variant="determinate"
              value={getProgress()}
              sx={{
                backgroundColor: 'rgba(255,255,255,0.2)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: 'rgba(255,255,255,0.8)'
                }
              }}
            />
          )}
        </Box>

        {/* Control Buttons */}
        <Grid container spacing={1} justifyContent="center" alignItems="center" mb={2}>
          <Grid item>
            <Tooltip title="Previous Track">
              <IconButton
                onClick={handlePrevious}
                disabled={isLoading}
                sx={{ color: 'white' }}
              >
                <SkipPrevious />
              </IconButton>
            </Tooltip>
          </Grid>

          <Grid item>
            <Tooltip title={playerStatus.state === 'playing' ? 'Pause' : 'Play'}>
              <IconButton
                onClick={playerStatus.state === 'playing' ? handlePause : handlePlay}
                disabled={isLoading}
                size="large"
                sx={{
                  color: 'white',
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  '&:hover': {
                    backgroundColor: 'rgba(255,255,255,0.3)'
                  }
                }}
              >
                {playerStatus.state === 'playing' ? <Pause /> : <PlayArrow />}
              </IconButton>
            </Tooltip>
          </Grid>

          <Grid item>
            <Tooltip title="Stop">
              <IconButton
                onClick={handleStop}
                disabled={isLoading}
                sx={{ color: 'white' }}
              >
                <Stop />
              </IconButton>
            </Tooltip>
          </Grid>

          <Grid item>
            <Tooltip title="Next Track">
              <IconButton
                onClick={handleNext}
                disabled={isLoading}
                sx={{ color: 'white' }}
              >
                <SkipNext />
              </IconButton>
            </Tooltip>
          </Grid>
        </Grid>

        {/* Volume Control */}
        <Box mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <VolumeDown sx={{ color: 'white' }} />
            <Slider
              value={playerStatus.volume * 100}
              onChange={handleVolumeChange}
              sx={{
                color: 'rgba(255,255,255,0.8)',
                '& .MuiSlider-thumb': {
                  backgroundColor: 'white',
                }
              }}
            />
            <VolumeUp sx={{ color: 'white' }} />
            <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'right' }}>
              {Math.round(playerStatus.volume * 100)}%
            </Typography>
          </Box>
        </Box>

        {/* Processing Controls */}
        <Box>
          <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tune /> Real-time Processing
          </Typography>

          <FormControlLabel
            control={
              <Switch
                checked={levelMatchingEnabled}
                onChange={handleLevelMatchingToggle}
                sx={{
                  '& .MuiSwitch-switchBase.Mui-checked': {
                    color: 'white',
                  },
                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                    backgroundColor: 'rgba(255,255,255,0.5)',
                  },
                }}
              />
            }
            label="Level Matching"
            sx={{ color: 'white' }}
          />
        </Box>

        {/* Real-time Analysis Display */}
        {playerStatus.analysis && (
          <Box mt={2}>
            <Typography variant="subtitle2" gutterBottom>
              📊 Audio Analysis
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="caption">
                  RMS Level: {(playerStatus.analysis.rms_level * 100).toFixed(1)}%
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption">
                  Peak Level: {(playerStatus.analysis.peak_level * 100).toFixed(1)}%
                </Typography>
              </Grid>
            </Grid>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default EnhancedAudioPlayer;