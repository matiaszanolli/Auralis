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
  AutoAwesome,
  Lyrics as LyricsIcon
} from '@mui/icons-material';
import { GradientSlider } from './shared/GradientSlider';
import { colors, gradients } from '../theme/auralisTheme';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import AlbumArtComponent from './album/AlbumArt';
import { useEnhancement } from '../contexts/EnhancementContext';

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

interface BottomPlayerBarConnectedProps {
  onToggleLyrics?: () => void;
  onTimeUpdate?: (currentTime: number) => void;
}

export const BottomPlayerBarConnected: React.FC<BottomPlayerBarConnectedProps> = ({ onToggleLyrics, onTimeUpdate }) => {
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

  // Get enhancement settings from global context
  const { settings: enhancementSettings, setEnabled: setEnhancementEnabled, isProcessing } = useEnhancement();

  // Local UI state
  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);
  const [localVolume, setLocalVolume] = useState(apiVolume);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const [isFavoriting, setIsFavoriting] = useState(false);

  // HTML5 Audio elements for gapless playback
  const audioRef = React.useRef<HTMLAudioElement>(null);
  const nextAudioRef = React.useRef<HTMLAudioElement>(null);

  // Track the last loaded track ID to prevent redundant reloads
  const lastLoadedTrackId = React.useRef<number | null>(null);

  // Track which audio element is currently playing (for gapless switching)
  const [activeAudioElement, setActiveAudioElement] = React.useState<'primary' | 'secondary'>('primary');

  // Next track info for pre-loading
  const [nextTrack, setNextTrack] = React.useState<any | null>(null);
  const [gaplessEnabled, setGaplessEnabled] = React.useState(true);
  const [crossfadeEnabled, setCrossfadeEnabled] = React.useState(false);
  const [crossfadeDuration, setCrossfadeDuration] = React.useState(5.0); // seconds

  const { success, info, error: showError } = useToast();

  // Load playback settings from backend
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await fetch('http://localhost:8765/api/settings');
        if (response.ok) {
          const settings = await response.json();
          setGaplessEnabled(settings.gapless_enabled ?? true);
          setCrossfadeEnabled(settings.crossfade_enabled ?? false);
          setCrossfadeDuration(settings.crossfade_duration ?? 5.0);
          console.log('Gapless:', settings.gapless_enabled ? 'enabled' : 'disabled');
          console.log('Crossfade:', settings.crossfade_enabled ? `enabled (${settings.crossfade_duration}s)` : 'disabled');
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    };
    loadSettings();
  }, []);

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

  // Load new track into audio element when currentTrack or enhancement settings change
  useEffect(() => {
    if (currentTrack && audioRef.current) {
      // Build stream URL with enhancement parameters from global context
      const params = new URLSearchParams();
      if (enhancementSettings.enabled) {
        params.append('enhanced', 'true');
        params.append('preset', enhancementSettings.preset);
        params.append('intensity', enhancementSettings.intensity.toString());
      }

      const streamUrl = `http://localhost:8765/api/player/stream/${currentTrack.id}${params.toString() ? '?' + params.toString() : ''}`;

      // Only reload if it's actually a different stream URL
      const currentStreamUrl = audioRef.current.src;
      if (currentStreamUrl === streamUrl) {
        console.log(`✅ Stream URL unchanged (${streamUrl}), skipping reload`);
        return;
      }

      // Additional guard: Don't reload if track ID and enhancement settings haven't changed
      const isSameTrackAndSettings =
        lastLoadedTrackId.current === currentTrack.id &&
        audioRef.current.src.includes(`/stream/${currentTrack.id}`);

      if (isSameTrackAndSettings && currentStreamUrl && !audioRef.current.paused) {
        console.log(`✅ Same track already loaded and playing, skipping reload`);
        return;
      }

      // Check if this is the same track (just different enhancement settings)
      const isSameTrack = lastLoadedTrackId.current === currentTrack.id;

      // Save current position and playing state if changing enhancement on same track
      const savedPosition = isSameTrack ? audioRef.current.currentTime : 0;
      const wasPlaying = isSameTrack && !audioRef.current.paused;

      // Abort any pending load operation first
      if (audioRef.current.src) {
        audioRef.current.pause();
        audioRef.current.removeAttribute('src');
        audioRef.current.load(); // This aborts any pending network requests
      }

      audioRef.current.src = streamUrl;
      audioRef.current.load();
      console.log(`Loaded audio stream: ${streamUrl}`, enhancementSettings.enabled ? `(enhanced: ${enhancementSettings.preset})` : '(original)');

      // Update last loaded track ID
      lastLoadedTrackId.current = currentTrack.id;

      // Update favorite status for new track
      setIsLoved(currentTrack.favorite || false);

      // If same track, restore position and playback state after load completes
      if (isSameTrack && savedPosition > 0) {
        const restorePlayback = () => {
          audioRef.current!.currentTime = savedPosition;
          setAudioCurrentTime(savedPosition);
          if (wasPlaying) {
            audioRef.current!.play().catch(e => console.error('Failed to resume playback:', e));
          }
          audioRef.current!.removeEventListener('loadedmetadata', restorePlayback);
        };
        audioRef.current.addEventListener('loadedmetadata', restorePlayback);
      } else {
        // New track - reset to beginning
        setAudioCurrentTime(0);
      }

      // Don't auto-play here - let the user control playback with play/pause button
      // The audio element will be ready to play when user clicks play
    }
  }, [currentTrack, enhancementSettings.enabled, enhancementSettings.preset, enhancementSettings.intensity]); // Re-run when track or enhancement settings change

  // Note: Playback is now controlled directly via play/pause button
  // The audio element is the source of truth, not the backend isPlaying state

  // Sync volume with both audio elements
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = (isMuted ? 0 : localVolume) / 100;
    }
    if (nextAudioRef.current) {
      nextAudioRef.current.volume = (isMuted ? 0 : localVolume) / 100;
    }
  }, [localVolume, isMuted]);

  // Fetch next track from queue for pre-loading
  useEffect(() => {
    const fetchNextTrack = async () => {
      if (!gaplessEnabled || !currentTrack) {
        setNextTrack(null);
        return;
      }

      try {
        const response = await fetch('http://localhost:8765/api/player/queue');
        if (response.ok) {
          const queueData = await response.json();
          const currentIndex = queueData.current_index || 0;
          const tracks = queueData.tracks || [];

          // Get next track
          if (currentIndex + 1 < tracks.length) {
            setNextTrack(tracks[currentIndex + 1]);
          } else {
            setNextTrack(null);
          }
        }
      } catch (error) {
        console.error('Failed to fetch next track:', error);
      }
    };

    fetchNextTrack();
  }, [currentTrack, gaplessEnabled, crossfadeEnabled]);

  // Pre-load next track when current track is near the end
  useEffect(() => {
    if ((!gaplessEnabled && !crossfadeEnabled) || !nextTrack || !audioRef.current || !nextAudioRef.current) {
      return;
    }

    const checkPreload = () => {
      if (!audioRef.current) return;

      const timeRemaining = audioRef.current.duration - audioRef.current.currentTime;

      // Calculate when to pre-load based on mode:
      // - Crossfade: Pre-load at crossfade_duration + 1 second buffer
      // - Gapless: Pre-load at 3 seconds remaining
      const preloadThreshold = crossfadeEnabled ? crossfadeDuration + 1 : 3;

      if (timeRemaining > 0 && timeRemaining <= preloadThreshold && nextAudioRef.current && !nextAudioRef.current.src) {
        console.log(`Pre-loading next track for ${crossfadeEnabled ? 'crossfade' : 'gapless'} playback:`, nextTrack.title);

        // Build stream URL for next track (use same enhancement settings)
        const params = new URLSearchParams();
        if (enhancementSettings.enabled) {
          params.append('enhanced', 'true');
          params.append('preset', enhancementSettings.preset);
          params.append('intensity', enhancementSettings.intensity.toString());
        }

        const streamUrl = `http://localhost:8765/api/player/stream/${nextTrack.id}${params.toString() ? '?' + params.toString() : ''}`;
        nextAudioRef.current.src = streamUrl;
        nextAudioRef.current.load();
      }
    };

    // Check every 500ms during playback
    const intervalId = setInterval(checkPreload, 500);
    return () => clearInterval(intervalId);
  }, [nextTrack, enhancementSettings.enabled, enhancementSettings.preset, enhancementSettings.intensity, gaplessEnabled, crossfadeEnabled, crossfadeDuration]);

  // Crossfade effect: Start fading at the right time
  useEffect(() => {
    if (!crossfadeEnabled || !nextTrack || !audioRef.current || !nextAudioRef.current) {
      return;
    }

    const checkCrossfade = () => {
      if (!audioRef.current || !nextAudioRef.current) return;

      const timeRemaining = audioRef.current.duration - audioRef.current.currentTime;

      // Start crossfade when time remaining equals crossfade duration
      if (timeRemaining > 0 && timeRemaining <= crossfadeDuration) {
        // Only start if next track is loaded and not already playing
        if (nextAudioRef.current.src && nextAudioRef.current.paused) {
          console.log(`Starting ${crossfadeDuration}s crossfade`);

          // Start playing the next track (it will fade in)
          nextAudioRef.current.volume = 0; // Start at 0 volume
          nextAudioRef.current.play().catch(err => {
            console.error('Failed to start crossfade:', err);
          });

          // Perform the crossfade
          performCrossfade(audioRef.current, nextAudioRef.current, crossfadeDuration);
        }
      }
    };

    const intervalId = setInterval(checkCrossfade, 100); // Check more frequently for smooth fade
    return () => clearInterval(intervalId);
  }, [crossfadeEnabled, crossfadeDuration, nextTrack, localVolume, isMuted]);

  // Crossfade function: fade out current, fade in next
  const performCrossfade = (currentAudio: HTMLAudioElement, nextAudio: HTMLAudioElement, duration: number) => {
    const startTime = Date.now();
    const targetVolume = (isMuted ? 0 : localVolume) / 100;
    const currentStartVolume = currentAudio.volume;

    const fade = () => {
      const elapsed = (Date.now() - startTime) / 1000; // seconds
      const progress = Math.min(elapsed / duration, 1); // 0 to 1

      // Ease-in-out curve for smoother transition
      const eased = progress < 0.5
        ? 2 * progress * progress
        : 1 - Math.pow(-2 * progress + 2, 2) / 2;

      // Fade out current track
      currentAudio.volume = currentStartVolume * (1 - eased);

      // Fade in next track
      nextAudio.volume = targetVolume * eased;

      if (progress < 1) {
        requestAnimationFrame(fade);
      } else {
        // Crossfade complete
        currentAudio.volume = 0;
        nextAudio.volume = targetVolume;
        currentAudio.pause();
        currentAudio.src = ''; // Clear the finished track

        // Swap audio element references for next cycle
        const temp = audioRef.current;
        audioRef.current = nextAudioRef.current;
        nextAudioRef.current = temp;
      }
    };

    requestAnimationFrame(fade);
  };

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
      try {
        await audioRef.current.play();
        info(`Playing: ${currentTrack?.title || ''}`);
      } catch (error) {
        console.error('Play failed:', error);
        // Try reloading the stream if play fails
        if (currentTrack && audioRef.current) {
          console.log('Retrying playback after error...');
          audioRef.current.load();
          // Try playing again after a brief delay
          setTimeout(() => {
            audioRef.current?.play().catch(e => console.error('Retry failed:', e));
          }, 100);
        }
      }
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

  const handleEnhancementToggle = async () => {
    const newState = !enhancementSettings.enabled;

    // Update via enhancement context (which calls the API)
    await setEnhancementEnabled(newState);

    // Show user feedback
    info(newState ? `✨ Auralis Magic enabled (${enhancementSettings.preset})` : 'Enhancement disabled');
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
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0, flex: '0 1 300px', maxWidth: 300 }}>
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
          {/* Lyrics Toggle */}
          {onToggleLyrics && (
            <Tooltip title="Show Lyrics" placement="top">
              <IconButton
                size="small"
                onClick={onToggleLyrics}
                sx={{
                  color: colors.text.secondary,
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    color: '#667eea',
                    transform: 'scale(1.1)',
                  },
                }}
              >
                <LyricsIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          {/* Magic Toggle */}
          <Tooltip title={enhancementSettings.enabled ? `Auralis Magic (${enhancementSettings.preset})` : "Auralis Magic (Off)"} placement="top">
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AutoAwesome
                fontSize="small"
                sx={{
                  color: enhancementSettings.enabled ? '#667eea' : colors.text.secondary,
                  opacity: enhancementSettings.enabled ? 1 : 0.5,
                  transition: 'all 0.3s ease',
                  animation: isProcessing ? 'pulse 1.5s ease-in-out infinite' : 'none',
                  '@keyframes pulse': {
                    '0%': { opacity: 0.5 },
                    '50%': { opacity: 1 },
                    '100%': { opacity: 0.5 },
                  },
                }}
              />
              <Switch
                size="small"
                checked={enhancementSettings.enabled}
                onChange={handleEnhancementToggle}
                disabled={isProcessing}
              />
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
          const currentTime = audio.currentTime;
          setAudioCurrentTime(currentTime);

          // Notify parent component (for lyrics synchronization)
          if (onTimeUpdate) {
            onTimeUpdate(currentTime);
          }
        }}
        onEnded={() => {
          // Crossfade mode: Track already transitioned via crossfade, just clean up
          if (crossfadeEnabled && nextAudioRef.current && !nextAudioRef.current.paused) {
            console.log('Crossfade already in progress, track ended naturally');
            // The crossfade handler already swapped the audio elements
            // Just call next() to update backend state
            next();
            return;
          }

          // Gapless playback: seamlessly switch to pre-loaded next track
          if (gaplessEnabled && nextAudioRef.current && nextAudioRef.current.src) {
            console.log('Gapless transition to next track');
            // Start playing the pre-loaded next track immediately
            nextAudioRef.current.play().catch(err => {
              console.error('Failed to play next track:', err);
            });
            // Clear the current audio source
            if (audioRef.current) {
              audioRef.current.src = '';
            }
          } else {
            // Standard mode: call next() to fetch and load the next track
            next();
          }
        }}
        onError={(e) => {
          console.error('Audio playback error:', e);
          showError('Audio playback failed');
        }}
      />

      {/* Second audio element for gapless pre-loading */}
      <audio
        ref={nextAudioRef}
        style={{ display: 'none' }}
        onTimeUpdate={(e) => {
          // This audio element is for pre-loading only during primary playback
          // When it becomes active, we need to track its time instead
          if (nextAudioRef.current && nextAudioRef.current.src && !nextAudioRef.current.paused) {
            const currentTime = e.currentTarget.currentTime;
            setAudioCurrentTime(currentTime);

            // Notify parent component (for lyrics synchronization)
            if (onTimeUpdate) {
              onTimeUpdate(currentTime);
            }
          }
        }}
        onEnded={() => {
          // When the pre-loaded track ends, advance to the next one
          next();
        }}
        onPlaying={() => {
          // When the pre-loaded track starts playing, it becomes the current track
          console.log('Pre-loaded track is now playing');
          // Swap references for next pre-load cycle
          const temp = audioRef.current;
          audioRef.current = nextAudioRef.current;
          nextAudioRef.current = temp;
        }}
        onError={(e) => {
          console.error('Next audio playback error:', e);
        }}
      />
    </PlayerContainer>
  );
};

export default BottomPlayerBarConnected;
