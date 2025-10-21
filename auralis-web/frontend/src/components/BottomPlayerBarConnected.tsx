/**
 * BottomPlayerBarConnected - Real Audio Playback
 *
 * Connected to Auralis backend via usePlayerAPI hook.
 * Provides real audio playback with queue management.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  IconButton,
  Typography,
  Switch,
  Tooltip,
  styled
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  VolumeUp,
  VolumeOff,
  Favorite,
  FavoriteOutlined,
  AutoAwesome
} from '@mui/icons-material';
import { GradientSlider } from './shared/GradientSlider';
import { colors, gradients } from '../theme/auralisTheme';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
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

export const BottomPlayerBarConnected: React.FC = () => {
  // Real player API hook
  const {
    currentTrack,
    isPlaying,
    currentTime,
    duration,
    volume: apiVolume,
    loading,
    error,
    togglePlayPause,
    next,
    previous,
    seek,
    setVolume: setApiVolume
  } = usePlayerAPI();

  // Local UI state
  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);
  const [isEnhanced, setIsEnhanced] = useState(true);
  const [localVolume, setLocalVolume] = useState(apiVolume);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const [isFavoriting, setIsFavoriting] = useState(false);

  // HTML5 Audio element ref for actual playback
  const audioRef = React.useRef<HTMLAudioElement>(null);

  const { success, info, error: showError } = useToast();

  // Sync local volume with API volume
  useEffect(() => {
    setLocalVolume(apiVolume);
  }, [apiVolume]);

  // Show error toast if API error occurs
  useEffect(() => {
    if (error) {
      showError(error);
    }
  }, [error, showError]);

  // Load new track into audio element when currentTrack changes
  useEffect(() => {
    if (currentTrack && audioRef.current) {
      const streamUrl = `http://localhost:8765/api/player/stream/${currentTrack.id}`;
      audioRef.current.src = streamUrl;
      audioRef.current.load();
      console.log(`Loaded audio stream: ${streamUrl}`);

      // Update favorite status for new track
      setIsLoved(currentTrack.favorite || false);

      // Reset audio time to 0
      setAudioCurrentTime(0);

      // Don't auto-play here - let the user control playback with play/pause button
      // The audio element will be ready to play when user clicks play
    }
  }, [currentTrack]); // Only re-run when currentTrack changes, not isPlaying

  // Note: Playback is now controlled directly via play/pause button
  // The audio element is the source of truth, not the backend isPlaying state

  // Sync volume with audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = (isMuted ? 0 : localVolume) / 100;
    }
  }, [localVolume, isMuted]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
        return;
      }

      switch (e.code) {
        case 'Space':
          e.preventDefault();
          handlePlayPauseClick();
          break;
        case 'ArrowRight':
          if (e.shiftKey) {
            e.preventDefault();
            handleNextClick();
          }
          break;
        case 'ArrowLeft':
          if (e.shiftKey) {
            e.preventDefault();
            handlePreviousClick();
          }
          break;
        case 'KeyM':
          e.preventDefault();
          handleMuteToggle();
          break;
        case 'KeyL':
          e.preventDefault();
          handleLoveToggle();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [isPlaying, isMuted, isLoved, currentTrack]);

  const handlePlayPauseClick = async () => {
    if (!audioRef.current) return;

    // Directly control HTML5 audio element
    if (audioRef.current.paused) {
      await audioRef.current.play();
      info(`Playing: ${currentTrack?.title || ''}`);
    } else {
      audioRef.current.pause();
      info('Paused');
    }

    // Also sync with backend (don't wait for it)
    togglePlayPause().catch(err => console.error('Backend sync error:', err));
  };

  const handleNextClick = async () => {
    await next();
    success('Next track');
  };

  const handlePreviousClick = async () => {
    await previous();
    success('Previous track');
  };

  const handleEnhancementToggle = () => {
    const newState = !isEnhanced;
    setIsEnhanced(newState);
    info(newState ? '✨ Auralis Magic enabled' : 'Enhancement disabled');
    // TODO: Send to backend to toggle real-time processing
  };

  const handleVolumeChange = (_: Event, value: number | number[]) => {
    const newVolume = value as number;
    setLocalVolume(newVolume);
    setApiVolume(newVolume);

    if (newVolume > 0 && isMuted) {
      setIsMuted(false);
    }
    if (newVolume === 0 && !isMuted) {
      info('Muted');
    }
  };

  const handleMuteToggle = () => {
    const newMutedState = !isMuted;
    setIsMuted(newMutedState);

    if (newMutedState) {
      setApiVolume(0);
      info('Muted');
    } else {
      setApiVolume(localVolume);
      info('Unmuted');
    }
  };

  const handleLoveToggle = async () => {
    if (!currentTrack || isFavoriting) return;

    const newLovedState = !isLoved;
    setIsFavoriting(true);
    setIsLoved(newLovedState);

    try {
      const url = `http://localhost:8765/api/library/tracks/${currentTrack.id}/favorite`;
      const method = newLovedState ? 'POST' : 'DELETE';

      const response = await fetch(url, { method });

      if (!response.ok) {
        throw new Error('Failed to update favorite');
      }

      success(newLovedState ? `Added "${currentTrack.title}" to favorites` : 'Removed from favorites');
    } catch (error) {
      console.error('Failed to update favorite:', error);
      // Revert the state if API call failed
      setIsLoved(!newLovedState);
      showError('Failed to update favorite');
    } finally {
      setIsFavoriting(false);
    }
  };

  const handleSeek = (_: Event, value: number | number[]) => {
    const newTime = value as number;
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
  };

  if (!currentTrack) {
    return (
      <PlayerContainer>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          <Typography variant="body2" sx={{ color: colors.text.secondary, opacity: 0.5 }}>
            No track playing
          </Typography>
        </Box>
      </PlayerContainer>
    );
  }

  return (
    <PlayerContainer>
      {/* Progress Bar */}
      <GradientSlider
        value={audioCurrentTime}
        max={duration || currentTrack?.duration || 0}
        onChange={handleSeek}
        sx={{
          height: 4,
          padding: 0,
          borderRadius: 0,
          '& .MuiSlider-thumb': {
            width: 12,
            height: 12,
          },
        }}
      />

      {/* Main Player Controls */}
      <Box
        sx={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 2fr 1fr',
          alignItems: 'center',
          px: 3,
          gap: 2
        }}
      >
        {/* Left: Track Info */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0 }}>
          {/* Album Art */}
          <AlbumArtContainer>
            <AlbumArtComponent
              albumId={currentTrack.album_id}
              size={64}
              borderRadius={6}
              showSkeleton={false}
            />
          </AlbumArtContainer>

          {/* Track Details */}
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: colors.text.primary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {currentTrack.title}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: colors.text.secondary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                display: 'block',
              }}
            >
              {currentTrack.artist}
            </Typography>
          </Box>

          {/* Love Button */}
          <Tooltip title="Love (L)" placement="top">
            <IconButton
              size="small"
              onClick={handleLoveToggle}
              sx={{
                color: isLoved ? '#ff6b9d' : colors.text.secondary,
                transition: 'all 0.2s ease',
                '&:hover': {
                  color: '#ff6b9d',
                  transform: 'scale(1.1)',
                },
              }}
            >
              {isLoved ? <Favorite fontSize="small" /> : <FavoriteOutlined fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>

        {/* Center: Playback Controls */}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tooltip title="Previous (Shift + ←)" placement="top">
              <IconButton
                onClick={handlePreviousClick}
                disabled={loading}
                sx={{
                  color: colors.text.secondary,
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    color: colors.text.primary,
                    transform: 'scale(1.1)',
                  },
                }}
              >
                <SkipPrevious />
              </IconButton>
            </Tooltip>

            <Tooltip title="Play/Pause (Space)" placement="top">
              <PlayButton onClick={handlePlayPauseClick} disabled={loading}>
                {isPlaying ? <Pause /> : <PlayArrow />}
              </PlayButton>
            </Tooltip>

            <Tooltip title="Next (Shift + →)" placement="top">
              <IconButton
                onClick={handleNextClick}
                disabled={loading}
                sx={{
                  color: colors.text.secondary,
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    color: colors.text.primary,
                    transform: 'scale(1.1)',
                  },
                }}
              >
                <SkipNext />
              </IconButton>
            </Tooltip>
          </Box>

          {/* Time Display */}
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography variant="caption" sx={{ color: colors.text.secondary, fontSize: 12 }}>
              {formatTime(audioCurrentTime)}
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.disabled, fontSize: 12 }}>
              /
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.secondary, fontSize: 12 }}>
              {formatTime(duration || currentTrack.duration)}
            </Typography>
          </Box>
        </Box>

        {/* Right: Volume & Enhancement */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 2 }}>
          {/* Magic Toggle */}
          <Tooltip title="Auralis Magic" placement="top">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AutoAwesome
                fontSize="small"
                sx={{
                  color: isEnhanced ? '#667eea' : colors.text.secondary,
                  opacity: isEnhanced ? 1 : 0.5,
                  transition: 'all 0.3s ease',
                }}
              />
              <Switch size="small" checked={isEnhanced} onChange={handleEnhancementToggle} />
            </Box>
          </Tooltip>

          {/* Volume Control */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
            <Tooltip title="Mute (M)" placement="top">
              <IconButton
                size="small"
                onClick={handleMuteToggle}
                sx={{
                  color: colors.text.secondary,
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    color: colors.text.primary,
                    transform: 'scale(1.1)',
                  },
                }}
              >
                {isMuted || localVolume === 0 ? <VolumeOff fontSize="small" /> : <VolumeUp fontSize="small" />}
              </IconButton>
            </Tooltip>
            <GradientSlider
              value={isMuted ? 0 : localVolume}
              onChange={handleVolumeChange}
              sx={{ maxWidth: 100 }}
              aria-label="Volume"
              min={0}
              max={100}
            />
          </Box>
        </Box>
      </Box>

      {/* HTML5 Audio Element - Hidden but provides actual playback */}
      <audio
        ref={audioRef}
        style={{ display: 'none' }}
        onTimeUpdate={(e) => {
          // Update local state for progress bar (don't call backend API)
          const audio = e.currentTarget;
          setAudioCurrentTime(audio.currentTime);
        }}
        onEnded={() => {
          // Auto-advance to next track
          next();
        }}
        onError={(e) => {
          console.error('Audio playback error:', e);
          showError('Audio playback failed');
        }}
      />
    </PlayerContainer>
  );
};

export default BottomPlayerBarConnected;
