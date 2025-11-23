/**
 * BottomPlayerBarUnified - Unified Player Integration
 * ===================================================
 *
 * Production-ready player bar with proper queue navigation, progress interaction,
 * and clean UI layout. Uses unified audio player architecture.
 *
 * UI Layout:
 * - Left: Album art + track info (flex: 1)
 * - Center: Play/pause + prev/next + time (absolutely centered)
 * - Right: Volume control (flex: 1, right-aligned)
 * - Top: Progress bar (full width)
 *
 * Fixed Issues:
 * ✅ Previous/Next buttons now sync with queue navigation
 * ✅ Progress bar seek works smoothly without breaking playback
 * ✅ Favorite icon properly positioned in track info
 * ✅ Preset selector removed from player bar (moved to settings)
 * ✅ Layout fixes prevent element overlap
 *
 * Phase 4a Consolidation:
 * ✅ Updated to use usePlayerWithAudio composition hook (Phase 4a consolidation)
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Tooltip,
  CircularProgress
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
import { Slider } from '@mui/material';
import { colors } from '../theme/auralisTheme';
import { useToast } from './shared/Toast';
import { usePlayerWithAudio } from '../hooks/usePlayerWithAudio';
import { auroraOpacity } from './library/Color.styles';
import { useEnhancement } from '../contexts/EnhancementContext';
import AlbumArtComponent from './album/AlbumArt';
import { triggerAudioPlayGesture } from './player/HiddenAudioElement';
import { PlayerContainer, PlayButton, AlbumArtContainer, ControlButton } from './player-bar-v2/PlayerBar.styles';

export const BottomPlayerBarUnified: React.FC = () => {
  // Phase 4a Consolidation: Use unified player with audio composition hook
  const {
    currentTrack,
    queue,
    queueIndex,
    isPlaying,
    currentTime,
    duration,
    volume,
    loading: playerLoading,
    error: playerError,
    audioState,
    audioMetadata,
    audioError,
    play,
    pause,
    togglePlayPause,
    next: nextTrack,
    previous: previousTrack,
    seek,
    setVolume: setPlayerVolume,
    setEnhanced,
    setPreset,
    player
  } = usePlayerWithAudio({
    apiBaseUrl: 'http://localhost:8765',
    debug: true,
    autoPlay: true
  });

  // Local UI state
  const [localVolume, setLocalVolume] = useState(50);
  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);
  const [isSeeking, setIsSeeking] = useState(false);

  const { info, error: showError } = useToast();

  // Show error toast
  useEffect(() => {
    if (playerError) {
      showError(`Playback error: ${playerError}`);
    }
    if (audioError) {
      showError(`Playback error: ${audioError.message}`);
    }
  }, [playerError, audioError, showError]);

  // Handle play/pause
  const handlePlayPause = useCallback(async () => {
    try {
      // Trigger audio play gesture to satisfy browser autoplay policies
      triggerAudioPlayGesture();
      await togglePlayPause();
    } catch (err: any) {
      console.error('[Player] Playback error:', err);
      showError(`Playback error: ${err.message}`);
    }
  }, [togglePlayPause, showError]);

  // Handle next track (sync with queue)
  const handleNext = useCallback(async () => {
    if (!queue.length || queueIndex >= queue.length - 1) return;

    try {
      triggerAudioPlayGesture();
      await nextTrack();
      info('Next track');
    } catch (err: any) {
      showError(`Failed to skip to next: ${err.message}`);
    }
  }, [queue.length, queueIndex, nextTrack, info, showError]);

  // Handle previous track (sync with queue)
  const handlePrevious = useCallback(async () => {
    if (!queue.length || queueIndex === 0) return;

    try {
      triggerAudioPlayGesture();
      await previousTrack();
      info('Previous track');
    } catch (err: any) {
      showError(`Failed to go to previous: ${err.message}`);
    }
  }, [queue.length, queueIndex, previousTrack, info, showError]);

  // Handle seek (with proper state management)
  const handleSeek = useCallback((_: Event, value: number | number[]) => {
    const position = value as number;
    setIsSeeking(true);

    seek(position).catch((err: any) => {
      showError(`Seek failed: ${err.message}`);
    }).finally(() => {
      setIsSeeking(false);
    });
  }, [seek, showError]);

  // Handle volume change
  const handleVolumeChange = useCallback(async (_: Event, newValue: number | number[]) => {
    const volume = newValue as number;
    setLocalVolume(volume);
    await setPlayerVolume(volume);
    if (volume > 0) setIsMuted(false);
  }, [setPlayerVolume]);

  // Handle mute toggle
  const handleMuteToggle = useCallback(async () => {
    if (isMuted) {
      await setPlayerVolume(localVolume);
      setIsMuted(false);
    } else {
      await setPlayerVolume(0);
      setIsMuted(true);
    }
  }, [isMuted, localVolume, setPlayerVolume]);

  // Handle mouse wheel on volume
  const handleVolumeWheel = useCallback(async (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -5 : 5;
    const newVolume = Math.max(0, Math.min(100, localVolume + delta));
    setLocalVolume(newVolume);
    await setPlayerVolume(newVolume);
    if (newVolume > 0) setIsMuted(false);
  }, [localVolume, setPlayerVolume]);

  // Get volume icon
  const getVolumeIcon = useCallback(() => {
    if (isMuted || localVolume === 0) return <VolumeMute />;
    if (localVolume < 33) return <VolumeDown />;
    return <VolumeUp />;
  }, [isMuted, localVolume]);

  // Format time as MM:SS
  const formatTime = useCallback((seconds: number): string => {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }, []);

  return (
    <PlayerContainer>
      {/* Progress Bar - Full width, snapped to top */}
      <Box sx={{ width: '100%', px: 3, py: 0.75 }}>
        <Slider
          value={isSeeking ? currentTime : currentTime}
          max={duration || 100}
          onChange={handleSeek}
          disabled={audioState === 'idle' || playerLoading}
          sx={{
            height: 4,
            '& .MuiSlider-track': {
              background: gradients.aurora,
              border: 'none',
              height: 4,
            },
            '& .MuiSlider-rail': {
              height: 4,
              background: auroraOpacity.standard,
            },
            '& .MuiSlider-thumb': {
              width: 12,
              height: 12,
              background: tokens.colors.accent.purple,
              boxShadow: `0 0 12px ${auroraOpacity.veryStrong}`,
              '&:hover': {
                boxShadow: `0 0 20px ${auroraOpacity.saturated}`,
              },
            },
          }}
        />
      </Box>

      {/* Main Controls Section */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 3,
        py: 1,
        flex: 1,
        gap: 2,
      }}>
        {/* Left Section: Album Art + Track Info + Favorite */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          minWidth: 0,
          flex: 1,
        }}>
          <AlbumArtContainer>
            {currentTrack && (
              <AlbumArtComponent
                albumId={currentTrack.album_id}
                size={56}
              />
            )}
          </AlbumArtContainer>

          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography
                variant="body2"
                noWrap
                sx={{
                  fontWeight: 600,
                  fontSize: '14px',
                  flex: 1,
                }}
              >
                {currentTrack?.title || 'No track loaded'}
              </Typography>
              <Tooltip title={isLoved ? 'Remove from favorites' : 'Add to favorites'} arrow>
                <ControlButton
                  size="small"
                  onClick={() => setIsLoved(!isLoved)}
                  sx={{ ml: 'auto' }}
                >
                  {isLoved ? (
                    <Favorite sx={{ color: tokens.colors.accent.pink, fontSize: 20 }} />
                  ) : (
                    <FavoriteOutlined sx={{ fontSize: 20 }} />
                  )}
                </ControlButton>
              </Tooltip>
            </Box>
            <Typography
              variant="caption"
              noWrap
              sx={{
                color: auroraOpacity.standard,
                fontSize: '12px',
              }}
            >
              {currentTrack?.artist || 'Unknown artist'}
            </Typography>
          </Box>
        </Box>

        {/* Center Section: Playback Controls */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 1,
        }}>
          <Tooltip title="Previous track" arrow>
            <span>
              <ControlButton
                onClick={handlePrevious}
                disabled={!queue.length || queueIndex === 0}
                size="small"
              >
                <SkipPrevious sx={{ fontSize: 24 }} />
              </ControlButton>
            </span>
          </Tooltip>

          <PlayButton
            onClick={handlePlayPause}
            disabled={playerLoading || audioState === 'idle'}
            size="small"
          >
            {playerLoading ? (
              <CircularProgress size={24} color="inherit" />
            ) : isPlaying ? (
              <Pause sx={{ fontSize: 28 }} />
            ) : (
              <PlayArrow sx={{ fontSize: 28 }} />
            )}
          </PlayButton>

          <Tooltip title="Next track" arrow>
            <span>
              <ControlButton
                onClick={handleNext}
                disabled={!queue.length || queueIndex >= queue.length - 1}
                size="small"
              >
                <SkipNext sx={{ fontSize: 24 }} />
              </ControlButton>
            </span>
          </Tooltip>

          <Typography
            variant="caption"
            sx={{
              minWidth: 100,
              textAlign: 'center',
              color: auroraOpacity.stronger,
              fontSize: '12px',
              fontWeight: 500,
              letterSpacing: '0.3px',
              ml: 2,
            }}
          >
            {formatTime(currentTime)} / {formatTime(duration)}
          </Typography>
        </Box>

        {/* Right Section: Volume Control */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flex: 1,
          justifyContent: 'flex-end',
          minWidth: 180,
        }}>
          <Tooltip title={isMuted ? 'Unmute' : 'Mute'} arrow>
            <ControlButton
              size="small"
              onClick={handleMuteToggle}
              sx={{ flexShrink: 0 }}
            >
              {getVolumeIcon()}
            </ControlButton>
          </Tooltip>

          <Box sx={{ flex: 1, minWidth: 80 }} onWheel={handleVolumeWheel}>
            <Slider
              value={isMuted ? 0 : localVolume}
              onChange={handleVolumeChange}
              min={0}
              max={100}
              sx={{
                height: 3,
                '& .MuiSlider-track': {
                  background: gradients.aurora,
                  border: 'none',
                },
                '& .MuiSlider-rail': {
                  background: auroraOpacity.standard,
                },
                '& .MuiSlider-thumb': {
                  width: 10,
                  height: 10,
                  background: tokens.colors.accent.purple,
                },
              }}
            />
          </Box>

          <Typography
            variant="caption"
            sx={{
              minWidth: 32,
              textAlign: 'right',
              color: auroraOpacity.standard,
              fontSize: '11px',
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {Math.round(isMuted ? 0 : localVolume)}%
          </Typography>
        </Box>
      </Box>
    </PlayerContainer>
  );
};

export default BottomPlayerBarUnified;
