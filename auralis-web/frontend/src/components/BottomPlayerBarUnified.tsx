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
import { useUnifiedWebMAudioPlayer } from '../hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '../contexts/EnhancementContext';
import AlbumArtComponent from './album/AlbumArt';

const PlayerContainer = styled(Box)({
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  width: '100vw',
  height: '80px',
  margin: 0,
  padding: 0,
  background: 'linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(10, 14, 39, 0.99) 100%)',
  backdropFilter: 'blur(20px)',
  WebkitBackdropFilter: 'blur(20px)', // Safari support
  borderTop: `1px solid rgba(102, 126, 234, 0.15)`,
  display: 'flex',
  flexDirection: 'column',
  zIndex: 1300, // Higher than MUI modals (1200)
  boxShadow: '0 -8px 32px rgba(0, 0, 0, 0.5), 0 -2px 8px rgba(102, 126, 234, 0.15)',
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  color: '#ffffff',
  width: '56px',
  height: '56px',
  boxShadow: '0 4px 16px rgba(102, 126, 234, 0.4), 0 0 24px rgba(102, 126, 234, 0.2)',
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.05)',
    boxShadow: '0 8px 24px rgba(102, 126, 234, 0.6), 0 0 32px rgba(102, 126, 234, 0.3)',
  },

  '&:active': {
    transform: 'scale(0.98)',
  },

  '&:disabled': {
    background: 'rgba(102, 126, 234, 0.2)',
    color: 'rgba(255, 255, 255, 0.3)',
  },
});

const AlbumArtContainer = styled(Box)({
  width: '56px',
  height: '56px',
  borderRadius: '8px',
  flexShrink: 0,
  overflow: 'hidden',
  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
  border: '1px solid rgba(102, 126, 234, 0.2)',
});

const ControlButton = styled(IconButton)({
  color: 'rgba(255, 255, 255, 0.7)',
  transition: 'all 0.2s ease',

  '&:hover': {
    color: '#ffffff',
    background: 'rgba(102, 126, 234, 0.1)',
    transform: 'scale(1.1)',
  },

  '&:disabled': {
    color: 'rgba(255, 255, 255, 0.2)',
  },
});

const StyledChip = styled(Chip)({
  background: 'rgba(102, 126, 234, 0.15)',
  border: '1px solid rgba(102, 126, 234, 0.3)',
  color: '#667eea',
  fontWeight: 600,
  fontSize: '11px',
  letterSpacing: '0.5px',

  '& .MuiChip-label': {
    padding: '0 8px',
  },
});

const StyledSelect = styled(Select)({
  borderRadius: '8px',
  fontSize: '13px',
  background: 'rgba(26, 31, 58, 0.6)',
  border: '1px solid rgba(102, 126, 234, 0.2)',

  '& .MuiOutlinedInput-notchedOutline': {
    border: 'none',
  },

  '&:hover': {
    background: 'rgba(26, 31, 58, 0.8)',
    border: '1px solid rgba(102, 126, 234, 0.4)',
  },

  '&.Mui-focused': {
    background: 'rgba(26, 31, 58, 0.9)',
    border: '1px solid rgba(102, 126, 234, 0.6)',
  },
});

const StyledSwitch = styled(Switch)({
  '& .MuiSwitch-switchBase.Mui-checked': {
    color: '#667eea',
  },
  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
    backgroundColor: '#667eea',
  },
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

  // NEW Unified WebM Audio Player (Phase 2)
  const player = useUnifiedWebMAudioPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: true,
    autoPlay: true
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

  // Sync enhancement settings with player when they change
  useEffect(() => {
    if (player.player) {
      console.log(`[UnifiedPlayer] Enhancement settings changed: enabled=${enhancementSettings.enabled}, preset=${enhancementSettings.preset}`);
      player.setEnhanced(enhancementSettings.enabled, enhancementSettings.preset).catch((err) => {
        console.error('[UnifiedPlayer] Failed to sync enhancement settings:', err);
      });
    }
  }, [enhancementSettings.enabled, enhancementSettings.preset, enhancementSettings.intensity]);

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
      {/* Progress Bar - snapped to top, no padding */}
      <Box sx={{ px: 3 }}>
        <GradientSlider
          value={player.currentTime}
          max={player.duration || 100}
          onChange={(_, value) => player.seek(value as number)}
          disabled={player.state === 'idle' || player.isLoading}
          sx={{ height: 3 }}
        />
      </Box>

      {/* Main Controls - distributed across full width with centered play button */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        px: 3,
        flex: 1,
        justifyContent: 'space-between',
        gap: 2,
        position: 'relative'
      }}>
        {/* Left Section: Album Art + Track Info */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0, flex: 1 }}>
          <AlbumArtContainer>
            {currentTrack && (
              <AlbumArtComponent
                albumId={currentTrack.album_id}
                size={56}
              />
            )}
          </AlbumArtContainer>

          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 600, fontSize: '14px' }}>
              {currentTrack?.title || 'No track loaded'}
            </Typography>
            <Typography variant="caption" noWrap sx={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px' }}>
              {currentTrack?.artist || 'Unknown artist'}
            </Typography>
          </Box>

          <ControlButton size="small" onClick={() => setIsLoved(!isLoved)}>
            {isLoved ? <Favorite sx={{ color: '#ff4081' }} /> : <FavoriteOutlined />}
          </ControlButton>
        </Box>

        {/* Center Section: Playback Controls (absolutely centered) */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)'
        }}>
          <ControlButton onClick={previousTrack} disabled={!queue.length || queueIndex === 0}>
            <SkipPrevious sx={{ fontSize: 28 }} />
          </ControlButton>

          <PlayButton
            onClick={handlePlayPause}
            disabled={player.isLoading || player.state === 'idle'}
          >
            {player.isLoading ? (
              <CircularProgress size={28} color="inherit" />
            ) : player.isPlaying ? (
              <Pause sx={{ fontSize: 32 }} />
            ) : (
              <PlayArrow sx={{ fontSize: 32 }} />
            )}
          </PlayButton>

          <ControlButton onClick={nextTrack} disabled={!queue.length || queueIndex >= queue.length - 1}>
            <SkipNext sx={{ fontSize: 28 }} />
          </ControlButton>

          <Typography variant="caption" sx={{
            minWidth: 90,
            textAlign: 'center',
            color: 'rgba(255,255,255,0.6)',
            fontSize: '12px',
            fontWeight: 500,
            letterSpacing: '0.3px'
          }}>
            {formatTime(player.currentTime)} / {formatTime(player.duration)}
          </Typography>
        </Box>

        {/* Right Section: Enhancement Controls + Volume */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, justifyContent: 'flex-end' }}>
          {/* Format indicator */}
          <Tooltip title="WebM/Opus Streaming (Unified Architecture)" arrow>
            <StyledChip
              label="WebM"
              size="small"
            />
          </Tooltip>

          {/* State indicator */}
          {player.isLoading && (
            <CircularProgress size={16} sx={{ color: '#667eea' }} />
          )}

          {/* Enhancement toggle */}
          <Tooltip title="Enable audio enhancement" arrow>
            <StyledSwitch
              checked={enhancementSettings.enabled}
              onChange={(e) => handleEnhancementToggle(e.target.checked)}
              disabled={player.isLoading}
              size="small"
            />
          </Tooltip>

          {/* Preset selector */}
          <StyledSelect
            value={enhancementSettings.preset}
            onChange={(e) => handlePresetChange(e.target.value)}
            size="small"
            disabled={!enhancementSettings.enabled || player.isLoading}
            sx={{ minWidth: 110, fontSize: '13px' }}
          >
            <MenuItem value="adaptive">Adaptive</MenuItem>
            <MenuItem value="warm">Warm</MenuItem>
            <MenuItem value="bright">Bright</MenuItem>
            <MenuItem value="punchy">Punchy</MenuItem>
            <MenuItem value="gentle">Gentle</MenuItem>
          </StyledSelect>

          {/* Volume */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 140 }}>
            <ControlButton size="small" onClick={handleMuteToggle}>
              {getVolumeIcon()}
            </ControlButton>
            <Box sx={{ flex: 1 }} onWheel={handleVolumeWheel}>
              <GradientSlider
                value={isMuted ? 0 : localVolume}
                onChange={handleVolumeChange}
                min={0}
                max={100}
                sx={{ height: 3 }}
              />
            </Box>
            <Typography variant="caption" sx={{
              minWidth: 32,
              textAlign: 'right',
              color: 'rgba(255,255,255,0.5)',
              fontSize: '11px',
              fontWeight: 600
            }}>
              {Math.round(isMuted ? 0 : localVolume)}%
            </Typography>
          </Box>
        </Box>
      </Box>
    </PlayerContainer>
  );
};

export default BottomPlayerBarUnified;
