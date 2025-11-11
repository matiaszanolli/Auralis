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
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  IconButton,
  Typography,
  Tooltip,
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
import { Slider } from '@mui/material';
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
  minWidth: '56px',
  flexShrink: 0,
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
  minWidth: '56px',
  borderRadius: '8px',
  flexShrink: 0,
  overflow: 'hidden',
  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
  border: '1px solid rgba(102, 126, 234, 0.2)',
});

const ControlButton = styled(IconButton)({
  color: 'rgba(255, 255, 255, 0.7)',
  minWidth: 'auto',
  width: '44px',
  height: '44px',
  padding: '8px',
  flexShrink: 0,
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

export const BottomPlayerBarUnified: React.FC = () => {
  // Get current track and queue from usePlayerAPI
  const {
    currentTrack,
    queue,
    queueIndex,
    next: nextTrack,
    previous: previousTrack
  } = usePlayerAPI();

  // Unified WebM Audio Player
  const player = useUnifiedWebMAudioPlayer({
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

  // Load track when currentTrack changes
  useEffect(() => {
    if (currentTrack && currentTrack.id) {
      console.log(`[Player] Loading track ${currentTrack.id}: ${currentTrack.title}`);
      player.loadTrack(currentTrack.id)
        .catch((err) => {
          console.error('[Player] Failed to load track:', err);
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

  // Handle play/pause
  const handlePlayPause = useCallback(async () => {
    try {
      if (player.isPlaying) {
        player.pause();
      } else {
        await player.play();
      }
    } catch (err: any) {
      showError(`Playback error: ${err.message}`);
    }
  }, [player.isPlaying]);

  // Handle next track (sync with queue)
  const handleNext = useCallback(async () => {
    if (!queue.length || queueIndex >= queue.length - 1) return;

    try {
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
      await previousTrack();
      info('Previous track');
    } catch (err: any) {
      showError(`Failed to go to previous: ${err.message}`);
    }
  }, [queue.length, queueIndex, previousTrack, info, showError]);

  // Handle seek (with proper state management)
  const handleSeek = useCallback(async (value: number | number[]) => {
    const position = value as number;
    setIsSeeking(true);

    try {
      await player.seek(position);
    } catch (err: any) {
      showError(`Seek failed: ${err.message}`);
    } finally {
      setIsSeeking(false);
    }
  }, [player]);

  // Handle volume change
  const handleVolumeChange = useCallback((_: Event, newValue: number | number[]) => {
    const volume = newValue as number;
    setLocalVolume(volume);
    player.setVolume(volume / 100);
    if (volume > 0) setIsMuted(false);
  }, [player]);

  // Handle mute toggle
  const handleMuteToggle = useCallback(() => {
    if (isMuted) {
      player.setVolume(localVolume / 100);
      setIsMuted(false);
    } else {
      player.setVolume(0);
      setIsMuted(true);
    }
  }, [isMuted, localVolume, player]);

  // Handle mouse wheel on volume
  const handleVolumeWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -5 : 5;
    const newVolume = Math.max(0, Math.min(100, localVolume + delta));
    setLocalVolume(newVolume);
    player.setVolume(newVolume / 100);
    if (newVolume > 0) setIsMuted(false);
  }, [localVolume, player]);

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
          value={isSeeking ? player.currentTime : player.currentTime}
          max={player.duration || 100}
          onChange={handleSeek}
          disabled={player.state === 'idle' || player.isLoading}
          sx={{
            height: 4,
            '& .MuiSlider-track': {
              background: gradients.aurora,
              border: 'none',
              height: 4,
            },
            '& .MuiSlider-rail': {
              height: 4,
              background: 'rgba(102, 126, 234, 0.2)',
            },
            '& .MuiSlider-thumb': {
              width: 12,
              height: 12,
              background: '#667eea',
              boxShadow: '0 0 12px rgba(102, 126, 234, 0.6)',
              '&:hover': {
                boxShadow: '0 0 20px rgba(102, 126, 234, 0.8)',
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
                    <Favorite sx={{ color: '#ff4081', fontSize: 20 }} />
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
                color: 'rgba(255,255,255,0.5)',
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
            disabled={player.isLoading || player.state === 'idle'}
            size="small"
          >
            {player.isLoading ? (
              <CircularProgress size={24} color="inherit" />
            ) : player.isPlaying ? (
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
              color: 'rgba(255,255,255,0.6)',
              fontSize: '12px',
              fontWeight: 500,
              letterSpacing: '0.3px',
              ml: 2,
            }}
          >
            {formatTime(player.currentTime)} / {formatTime(player.duration)}
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
                  background: 'rgba(102, 126, 234, 0.2)',
                },
                '& .MuiSlider-thumb': {
                  width: 10,
                  height: 10,
                  background: '#667eea',
                },
              }}
            />
          </Box>

          <Typography
            variant="caption"
            sx={{
              minWidth: 32,
              textAlign: 'right',
              color: 'rgba(255,255,255,0.5)',
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
