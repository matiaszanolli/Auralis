/**
 * MSEPlayerExample - Example Component
 * =====================================
 *
 * Demonstrates how to use the MSEPlayer with the useMSEPlayer hook.
 *
 * This is a minimal example showing:
 * - Player initialization
 * - Basic playback controls
 * - Preset switching
 * - State tracking
 * - Performance monitoring
 *
 * For production use, see BottomPlayerBarConnected integration.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React, { useEffect, useState } from 'react';
import { Box, Button, Typography, Select, MenuItem, LinearProgress, Alert } from '@mui/material';
import { useMSEPlayer } from '../hooks/useMSEPlayer';

export const MSEPlayerExample: React.FC = () => {
  // Initialize MSE player
  const {
    player,
    state,
    metadata,
    currentTime,
    isSupported,
    initialize,
    play,
    pause,
    seek,
    switchPreset,
    lastChunk,
    presetSwitchStats
  } = useMSEPlayer({
    enhanced: true,
    preset: 'adaptive',
    intensity: 1.0,
    debug: true
  });

  const [trackId, setTrackId] = useState(1); // Example track ID
  const [currentPreset, setCurrentPreset] = useState('adaptive');
  const [isInitialized, setIsInitialized] = useState(false);

  // Browser support check
  if (!isSupported) {
    return (
      <Alert severity="error">
        Media Source Extensions not supported in this browser.
        Please use Chrome, Firefox, Edge, or Safari.
      </Alert>
    );
  }

  // Initialize player with track
  const handleInitialize = async () => {
    try {
      await initialize(trackId);
      setIsInitialized(true);
    } catch (error) {
      console.error('Initialization failed:', error);
    }
  };

  // Handle preset switch
  const handlePresetChange = async (newPreset: string) => {
    try {
      await switchPreset(newPreset);
      setCurrentPreset(newPreset);
    } catch (error) {
      console.error('Preset switch failed:', error);
    }
  };

  // Format time for display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Calculate progress percentage
  const progress = metadata ? (currentTime / metadata.duration) * 100 : 0;

  return (
    <Box sx={{ p: 4, maxWidth: 800, mx: 'auto' }}>
      <Typography variant="h4" gutterBottom>
        MSE Player Example
      </Typography>

      {/* Player State */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="textSecondary">
          State: <strong>{state}</strong>
        </Typography>
        {metadata && (
          <Typography variant="body2" color="textSecondary">
            Track: {metadata.track_id} | Duration: {formatTime(metadata.duration)} |
            Chunks: {metadata.total_chunks}
          </Typography>
        )}
      </Box>

      {/* Initialization */}
      {!isInitialized && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body1" gutterBottom>
            Track ID:
          </Typography>
          <input
            type="number"
            value={trackId}
            onChange={(e) => setTrackId(parseInt(e.target.value))}
            style={{ marginRight: 8 }}
          />
          <Button variant="contained" onClick={handleInitialize}>
            Initialize Player
          </Button>
        </Typography>
      )}

      {/* Playback Controls */}
      {isInitialized && (
        <>
          <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              onClick={play}
              disabled={state === 'playing'}
            >
              Play
            </Button>
            <Button
              variant="contained"
              onClick={pause}
              disabled={state !== 'playing'}
            >
              Pause
            </Button>
            <Button
              variant="outlined"
              onClick={() => seek(0)}
            >
              Restart
            </Button>
          </Box>

          {/* Progress Bar */}
          <Box sx={{ mb: 3 }}>
            <LinearProgress variant="determinate" value={progress} />
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              {formatTime(currentTime)} / {formatTime(metadata?.duration || 0)}
            </Typography>
          </Box>

          {/* Preset Switcher */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="body1" gutterBottom>
              Enhancement Preset:
            </Typography>
            <Select
              value={currentPreset}
              onChange={(e) => handlePresetChange(e.target.value)}
              fullWidth
            >
              <MenuItem value="adaptive">Adaptive</MenuItem>
              <MenuItem value="gentle">Gentle</MenuItem>
              <MenuItem value="warm">Warm</MenuItem>
              <MenuItem value="bright">Bright</MenuItem>
              <MenuItem value="punchy">Punchy</MenuItem>
            </Select>
          </Box>

          {/* Performance Stats */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Performance
            </Typography>
            {lastChunk && (
              <Typography variant="body2" color="textSecondary">
                Last Chunk: #{lastChunk.chunk_idx} |
                Cache: {lastChunk.cache_tier} |
                Latency: {lastChunk.latency_ms?.toFixed(1)}ms
              </Typography>
            )}
            {presetSwitchStats.count > 0 && (
              <Typography variant="body2" color="textSecondary">
                Preset Switches: {presetSwitchStats.count} |
                Avg Latency: {presetSwitchStats.avgLatencyMs.toFixed(1)}ms
              </Typography>
            )}
          </Box>

          {/* Debug Info */}
          <Box sx={{ mt: 4, p: 2, bgcolor: 'grey.900', borderRadius: 1 }}>
            <Typography variant="caption" component="pre" sx={{ color: 'grey.400' }}>
              {JSON.stringify(
                {
                  state,
                  isPlaying: state === 'playing',
                  currentTime: currentTime.toFixed(2),
                  duration: metadata?.duration.toFixed(2),
                  progress: `${progress.toFixed(1)}%`,
                  preset: currentPreset,
                  lastChunkCacheTier: lastChunk?.cache_tier
                },
                null,
                2
              )}
            </Typography>
          </Box>
        </>
      )}
    </Box>
  );
};

export default MSEPlayerExample;
