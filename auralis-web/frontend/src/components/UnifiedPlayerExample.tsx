/**
 * UnifiedPlayerExample - Demo component for UnifiedPlayerManager
 * ==============================================================
 *
 * Demonstrates usage of useUnifiedPlayer hook with:
 * - Track loading and playback
 * - Mode switching (MSE vs HTML5)
 * - Preset changes
 * - Position preservation
 *
 * This serves as a reference implementation for integrating
 * into BottomPlayerBarConnected.
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  Slider,
  FormControlLabel,
  Switch,
  Select,
  MenuItem,
  Paper,
  Stack
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious
} from '@mui/icons-material';
import { useUnifiedPlayer } from '../hooks/useUnifiedPlayer';

export const UnifiedPlayerExample: React.FC = () => {
  const [trackId, setTrackId] = useState<number>(1);

  const player = useUnifiedPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: false,
    preset: 'adaptive',
    debug: true
  });

  // Format time as MM:SS
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Paper elevation={3} sx={{ p: 3, maxWidth: 600, mx: 'auto', mt: 4 }}>
      <Typography variant="h5" gutterBottom>
        Unified Player Demo
      </Typography>

      {/* Status */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          State: <strong>{player.state}</strong> | Mode: <strong>{player.mode}</strong>
        </Typography>
        {player.error && (
          <Typography variant="body2" color="error">
            Error: {player.error.message}
          </Typography>
        )}
      </Box>

      {/* Track Selection */}
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Select
          value={trackId}
          onChange={(e) => setTrackId(Number(e.target.value))}
          size="small"
        >
          <MenuItem value={1}>Track 1</MenuItem>
          <MenuItem value={2}>Track 2</MenuItem>
          <MenuItem value={3}>Track 3</MenuItem>
        </Select>

        <Button
          variant="contained"
          onClick={() => player.loadTrack(trackId)}
          disabled={player.isLoading}
        >
          {player.isLoading ? 'Loading...' : 'Load Track'}
        </Button>
      </Stack>

      {/* Playback Controls */}
      <Stack direction="row" spacing={2} justifyContent="center" sx={{ mb: 2 }}>
        <Button
          variant="outlined"
          startIcon={<SkipPrevious />}
          disabled={player.state === 'idle'}
        >
          Previous
        </Button>

        <Button
          variant="contained"
          color="primary"
          startIcon={player.isPlaying ? <Pause /> : <PlayArrow />}
          onClick={player.isPlaying ? player.pause : player.play}
          disabled={player.state === 'idle' || player.isLoading}
          sx={{ minWidth: 120 }}
        >
          {player.isPlaying ? 'Pause' : 'Play'}
        </Button>

        <Button
          variant="outlined"
          startIcon={<SkipNext />}
          disabled={player.state === 'idle'}
        >
          Next
        </Button>
      </Stack>

      {/* Progress Bar */}
      <Box sx={{ mb: 2 }}>
        <Slider
          value={player.currentTime}
          max={player.duration || 100}
          onChange={(_, value) => player.seek(value as number)}
          disabled={player.state === 'idle'}
          valueLabelDisplay="auto"
          valueLabelFormat={formatTime}
        />
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="caption">
            {formatTime(player.currentTime)}
          </Typography>
          <Typography variant="caption">
            {formatTime(player.duration)}
          </Typography>
        </Stack>
      </Box>

      {/* Enhancement Controls */}
      <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Enhancement Settings
        </Typography>

        <FormControlLabel
          control={
            <Switch
              checked={player.mode === 'html5'}
              onChange={(e) => player.setEnhanced(e.target.checked)}
              disabled={player.isLoading}
            />
          }
          label="Enable Enhancement"
        />

        <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1 }}>
          <Typography variant="body2">Preset:</Typography>
          <Select
            value={'adaptive'}
            onChange={(e) => player.setPreset(e.target.value)}
            size="small"
            disabled={player.mode !== 'html5' || player.isLoading}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="adaptive">Adaptive</MenuItem>
            <MenuItem value="warm">Warm</MenuItem>
            <MenuItem value="bright">Bright</MenuItem>
            <MenuItem value="punchy">Punchy</MenuItem>
            <MenuItem value="gentle">Gentle</MenuItem>
          </Select>
        </Stack>
      </Box>

      {/* Volume Control */}
      <Box>
        <Typography variant="body2" gutterBottom>
          Volume
        </Typography>
        <Slider
          defaultValue={50}
          onChange={(_, value) => player.setVolume((value as number) / 100)}
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => `${value}%`}
        />
      </Box>

      {/* Debug Info */}
      <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.900', borderRadius: 1 }}>
        <Typography variant="caption" component="pre" sx={{ color: 'grey.300' }}>
          {JSON.stringify(
            {
              state: player.state,
              mode: player.mode,
              currentTime: player.currentTime.toFixed(2),
              duration: player.duration.toFixed(2),
              isPlaying: player.isPlaying,
              isLoading: player.isLoading
            },
            null,
            2
          )}
        </Typography>
      </Box>
    </Paper>
  );
};

export default UnifiedPlayerExample;
