/**
 * BottomPlayerBarUnified - Unified Player Integration
 * ===================================================
 *
 * Simplified player bar using UnifiedPlayerManager.
 * Replaces complex dual-player logic with clean unified API.
 *
 * This is a streamlined version for testing the unified player.
 * Once proven, can replace BottomPlayerBarConnected.tsx.
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  IconButton,
  Typography,
  Switch,
  Tooltip,
  Select,
  MenuItem,
  Chip,
  CircularProgress,
  styled
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  VolumeUp,
  VolumeOff,
  VolumeDown,
  VolumeMute,
  Favorite,
  FavoriteOutlined
} from '@mui/icons-material';
import { GradientSlider } from './shared/GradientSlider';
import { colors, gradients } from '../theme/auralisTheme';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useUnifiedPlayer } from '../hooks/useUnifiedPlayer';
import { useEnhancement } from '../contexts/EnhancementContext';
import AlbumArtComponent from './album/AlbumArt';

const PlayerContainer = styled(Box)({
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  height: '96px',
  background: colors.background.secondary,
  borderTop: `1px solid rgba(102, 126, 234, 0.1)`,
  display: 'flex',
  flexDirection: 'column',
  zIndex: 1000,
  boxShadow: '0 -4px 24px rgba(0, 0, 0, 0.3)',
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  color: '#ffffff',
  width: '48px',
  height: '48px',
  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)',
  transition: 'all 0.3s ease',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.1)',
    boxShadow: '0 6px 20px rgba(102, 126, 234, 0.5)',
  },

  '&:active': {
    transform: 'scale(1.05)',
  },
});

const AlbumArtContainer = styled(Box)({
  width: '64px',
  height: '64px',
  borderRadius: '6px',
  flexShrink: 0,
  overflow: 'hidden',
  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
});

export const BottomPlayerBarUnified: React.FC = () => {
  // Get current track and queue from usePlayerAPI (keep for track metadata and queue management)
  const {
    currentTrack,
    queue,
    queueIndex,
    next: nextTrack,
    previous: previousTrack
  } = usePlayerAPI();

  // Enhancement settings
  const {
    settings: enhancementSettings,
    setEnabled: setEnhancementEnabled,
    setPreset: setEnhancementPreset
  } = useEnhancement();

  // Unified player
  const player = useUnifiedPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: true
  });

  // Local UI state
  const [localVolume, setLocalVolume] = useState(50);
  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);

  const { success, info, error: showError } = useToast();

  // Load track when currentTrack changes
  useEffect(() => {
    if (currentTrack && currentTrack.id) {
      console.log(`[UnifiedPlayer] Loading track ${currentTrack.id}: ${currentTrack.title}`);
      player.loadTrack(currentTrack.id)
        .then(() => {
          console.log(`[UnifiedPlayer] Track loaded, auto-playing`);
          return player.play();
        })
        .catch((err) => {
          console.error('[UnifiedPlayer] Failed to load/play track:', err);
          showError(`Playback error: ${err.message}`);
        });
    }
  }, [currentTrack?.id]);

  // Show error toast
  useEffect(() => {
    if (player.error) {
      showError(`Playback error: ${player.error.message}`);
    }
  }, [player.error]);

  // Handle enhancement toggle
  const handleEnhancementToggle = async (enabled: boolean) => {
    console.log(`[UnifiedPlayer] Enhancement ${enabled ? 'enabled' : 'disabled'}`);
    try {
      await player.setEnhanced(enabled, enhancementSettings.preset);
      setEnhancementEnabled(enabled);
      info(enabled ? `Enhancement enabled (${enhancementSettings.preset})` : 'Enhancement disabled');
    } catch (err: any) {
      showError(`Failed to toggle enhancement: ${err.message}`);
    }
  };

  // Handle preset change
  const handlePresetChange = async (preset: string) => {
    console.log(`[UnifiedPlayer] Preset changed to: ${preset}`);
    try {
      await player.setPreset(preset);
      setEnhancementPreset(preset);
      info(`Preset: ${preset}`);
    } catch (err: any) {
      showError(`Failed to change preset: ${err.message}`);
    }
  };

  // Handle play/pause
  const handlePlayPause = async () => {
    try {
      if (player.isPlaying) {
        player.pause();
      } else {
        await player.play();
      }
    } catch (err: any) {
      showError(`Playback error: ${err.message}`);
    }
  };

  // Handle volume change
  const handleVolumeChange = (_: Event, newValue: number | number[]) => {
    const volume = newValue as number;
    setLocalVolume(volume);
    player.setVolume(volume / 100);
    if (volume > 0) setIsMuted(false);
  };

  // Handle mute toggle
  const handleMuteToggle = () => {
    if (isMuted) {
      player.setVolume(localVolume / 100);
      setIsMuted(false);
    } else {
      player.setVolume(0);
      setIsMuted(true);
    }
  };

  // Handle mouse wheel on volume
  const handleVolumeWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -5 : 5;
    const newVolume = Math.max(0, Math.min(100, localVolume + delta));
    setLocalVolume(newVolume);
    player.setVolume(newVolume / 100);
    if (newVolume > 0) setIsMuted(false);
  };

  // Get volume icon
  const getVolumeIcon = () => {
    if (isMuted || localVolume === 0) return <VolumeMute />;
    if (localVolume < 33) return <VolumeDown />;
    return <VolumeUp />;
  };

  // Format time as MM:SS
  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <PlayerContainer>
      {/* Progress Bar */}
      <Box sx={{ px: 2, pt: 1 }}>
        <GradientSlider
          value={player.currentTime}
          max={player.duration || 100}
          onChange={(_, value) => player.seek(value as number)}
          disabled={player.state === 'idle' || player.isLoading}
          sx={{ height: 4 }}
        />
      </Box>

      {/* Main Controls */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        px: 2,
        flex: 1,
        gap: 2
      }}>
        {/* Album Art + Track Info */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0, flex: '0 1 400px' }}>
          <AlbumArtContainer>
            {currentTrack && (
              <AlbumArtComponent
                albumId={currentTrack.album_id}
                size={64}
              />
            )}
          </AlbumArtContainer>

          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
              {currentTrack?.title || 'No track loaded'}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {currentTrack?.artist || 'Unknown artist'}
            </Typography>
          </Box>

          <IconButton size="small" onClick={() => setIsLoved(!isLoved)}>
            {isLoved ? <Favorite sx={{ color: '#ff4081' }} /> : <FavoriteOutlined />}
          </IconButton>
        </Box>

        {/* Playback Controls */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'center', flex: '0 1 300px' }}>
          <IconButton onClick={previousTrack} disabled={!queue.length || queueIndex === 0}>
            <SkipPrevious />
          </IconButton>

          <PlayButton
            onClick={handlePlayPause}
            disabled={player.isLoading || player.state === 'idle'}
          >
            {player.isLoading ? (
              <CircularProgress size={24} color="inherit" />
            ) : player.isPlaying ? (
              <Pause />
            ) : (
              <PlayArrow />
            )}
          </PlayButton>

          <IconButton onClick={nextTrack} disabled={!queue.length || queueIndex >= queue.length - 1}>
            <SkipNext />
          </IconButton>

          <Typography variant="caption" sx={{ minWidth: 100, textAlign: 'center' }}>
            {formatTime(player.currentTime)} / {formatTime(player.duration)}
          </Typography>
        </Box>

        {/* Enhancement Controls + Volume */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: '0 1 400px', justifyContent: 'flex-end' }}>
          {/* Mode indicator */}
          <Tooltip title={`Mode: ${player.mode === 'mse' ? 'Progressive Streaming' : 'Enhanced Processing'}`}>
            <Chip
              label={player.mode.toUpperCase()}
              size="small"
              color={player.mode === 'html5' ? 'primary' : 'default'}
              sx={{ minWidth: 60 }}
            />
          </Tooltip>

          {/* State indicator */}
          {player.state === 'switching' && (
            <Tooltip title="Switching mode...">
              <CircularProgress size={16} />
            </Tooltip>
          )}

          {/* Enhancement toggle */}
          <Tooltip title="Enable audio enhancement">
            <Switch
              checked={player.mode === 'html5'}
              onChange={(e) => handleEnhancementToggle(e.target.checked)}
              disabled={player.isLoading}
              size="small"
            />
          </Tooltip>

          {/* Preset selector */}
          <Select
            value={enhancementSettings.preset}
            onChange={(e) => handlePresetChange(e.target.value)}
            size="small"
            disabled={player.mode !== 'html5' || player.isLoading}
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="adaptive">Adaptive</MenuItem>
            <MenuItem value="warm">Warm</MenuItem>
            <MenuItem value="bright">Bright</MenuItem>
            <MenuItem value="punchy">Punchy</MenuItem>
            <MenuItem value="gentle">Gentle</MenuItem>
          </Select>

          {/* Volume */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 150 }}>
            <IconButton size="small" onClick={handleMuteToggle}>
              {getVolumeIcon()}
            </IconButton>
            <Box sx={{ flex: 1 }} onWheel={handleVolumeWheel}>
              <GradientSlider
                value={isMuted ? 0 : localVolume}
                onChange={handleVolumeChange}
                min={0}
                max={100}
                sx={{ height: 4 }}
              />
            </Box>
            <Typography variant="caption" sx={{ minWidth: 35, textAlign: 'right' }}>
              {Math.round(isMuted ? 0 : localVolume)}%
            </Typography>
          </Box>
        </Box>
      </Box>
    </PlayerContainer>
  );
};

export default BottomPlayerBarUnified;
