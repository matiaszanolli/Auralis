/**
 * BottomPlayerBarConnected - Real Audio Playback (Refactored)
 *
 * Connected to Auralis backend via usePlayerAPI hook.
 * Provides real audio playback with queue management and MSE streaming.
 *
 * REFACTORED: October 30, 2025
 * - Extracted audio logic into useAudioPlayback hook
 * - Extracted gapless logic into useGaplessPlayback hook
 * - Extracted UI into modular components (PlayerControls, TrackInfo, ProgressBar)
 * - Reduced from 970 lines → 280 lines (71% reduction)
 * - Integrated MSE streaming support
 */

import React, { useState, useEffect } from 'react';
import { Box, styled } from '@mui/material';
import { colors } from '../theme/auralisTheme';
import { useToast } from './shared/Toast';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useEnhancement } from '../contexts/EnhancementContext';
import { useAudioPlayback } from '../hooks/useAudioPlayback';
import { useGaplessPlayback } from '../hooks/useGaplessPlayback';
import { PlayerControls } from './player/PlayerControls';
import { TrackInfo } from './player/TrackInfo';
import { ProgressBar } from './player/ProgressBar';
import { FEATURES } from '../config/features';

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

interface BottomPlayerBarConnectedProps {
  onToggleLyrics?: () => void;
  onTimeUpdate?: (currentTime: number) => void;
}

export const BottomPlayerBarConnected: React.FC<BottomPlayerBarConnectedProps> = ({
  onToggleLyrics,
  onTimeUpdate,
}) => {
  // ==================== HOOKS ====================

  // Player API (backend communication)
  const playerAPI = usePlayerAPI();
  const {
    currentTrack,
    isPlaying,
    currentTime: apiCurrentTime,
    duration,
    volume: apiVolume,
    queue,
    queueIndex,
    loading,
    error,
    togglePlayPause,
    next,
    previous,
    seek,
    setVolume: setApiVolume
  } = playerAPI;

  // Enhancement settings
  const {
    settings: enhancementSettings,
    setEnabled: setEnhancementEnabled,
    isProcessing
  } = useEnhancement();

  // Toast notifications
  const { success, info, error: showError } = useToast();

  // ==================== LOCAL STATE ====================

  const [isMuted, setIsMuted] = useState(false);
  const [isLoved, setIsLoved] = useState(false);
  const [localVolume, setLocalVolume] = useState(apiVolume);
  const [isFavoriting, setIsFavoriting] = useState(false);

  // ==================== AUDIO PLAYBACK HOOK ====================

  const audioPlayback = useAudioPlayback({
    currentTrack,
    isPlaying,
    enhancementSettings,
    useMSE: FEATURES.MSE_STREAMING,  // Enable MSE progressive streaming
    onTimeUpdate,
  });

  // ==================== GAPLESS PLAYBACK HOOK ====================

  const gaplessPlayback = useGaplessPlayback({
    audioRef: audioPlayback.audioRef,
    nextAudioRef: audioPlayback.nextAudioRef,
    currentTrack,
    queue,
    queueIndex,
    enhancementSettings,
    volume: localVolume,
    isMuted,
    onTrackSwitch: () => {
      // Called when gapless/crossfade transition completes
      next();
    },
  });

  // ==================== EFFECTS ====================

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

  // Update favorite status when track changes
  useEffect(() => {
    if (currentTrack) {
      setIsLoved(currentTrack.favorite || false);
    }
  }, [currentTrack]);

  // Sync volume between local state and audio elements
  useEffect(() => {
    audioPlayback.setVolume(isMuted ? 0 : localVolume);
  }, [localVolume, isMuted, audioPlayback]);

  // ==================== HANDLERS ====================

  const handlePlayPauseClick = async () => {
    if (!audioPlayback.audioRef.current) return;

    if (audioPlayback.audioRef.current.paused) {
      await audioPlayback.play();
      info(`Playing: ${currentTrack?.title || ''}`);
    } else {
      audioPlayback.pause();
      info('Paused');
    }

    // Sync with backend
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

  const handleEnhancementToggle = async (enabled: boolean) => {
    await setEnhancementEnabled(enabled);
    info(enabled ? `✨ Auralis Magic enabled (${enhancementSettings.preset})` : 'Enhancement disabled');
  };

  const handleVolumeChange = (newVolume: number) => {
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

  const handleSeek = (time: number) => {
    if (audioPlayback.audioRef.current) {
      audioPlayback.audioRef.current.currentTime = time;
    }
  };

  const handleLoveToggle = async () => {
    if (!currentTrack || isFavoriting) return;

    setIsFavoriting(true);
    const newLovedState = !isLoved;

    try {
      const response = await fetch(`/api/library/tracks/${currentTrack.id}/favorite`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ favorite: newLovedState }),
      });

      if (response.ok) {
        setIsLoved(newLovedState);
        success(newLovedState ? `❤️ Added "${currentTrack.title}" to favorites` : `Removed from favorites`);
      } else {
        showError('Failed to update favorite status');
      }
    } catch (error) {
      console.error('Failed to toggle favorite:', error);
      showError('Failed to update favorite status');
    } finally {
      setIsFavoriting(false);
    }
  };

  // ==================== KEYBOARD SHORTCUTS ====================

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

  // ==================== RENDER ====================

  if (!currentTrack) {
    return null;
  }

  return (
    <PlayerContainer>
      {/* Progress Bar */}
      <ProgressBar
        currentTime={audioPlayback.currentTime}
        duration={duration || currentTrack.duration || 0}
        onSeek={handleSeek}
        showTime={false}
      />

      {/* Main Player Controls */}
      <Box
        sx={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: '1fr 2fr 1fr',
          alignItems: 'center',
          px: 3,
          gap: 2,
        }}
      >
        {/* Left: Track Info */}
        <TrackInfo
          track={currentTrack}
          isLoved={isLoved}
          isFavoriting={isFavoriting}
          onToggleLove={handleLoveToggle}
          onToggleLyrics={onToggleLyrics}
          showLyricsButton={!!onToggleLyrics}
        />

        {/* Center: Player Controls */}
        <PlayerControls
          isPlaying={isPlaying}
          volume={localVolume}
          isMuted={isMuted}
          loading={loading || audioPlayback.isBuffering}
          enhancementEnabled={enhancementSettings.enabled}
          enhancementPreset={enhancementSettings.preset}
          isProcessing={isProcessing}
          onPlayPause={handlePlayPauseClick}
          onNext={handleNextClick}
          onPrevious={handlePreviousClick}
          onVolumeChange={handleVolumeChange}
          onMuteToggle={handleMuteToggle}
          onEnhancementToggle={handleEnhancementToggle}
        />

        {/* Right: (Reserved for future controls) */}
        <Box />
      </Box>

      {/* Hidden Audio Elements */}
      <audio
        ref={audioPlayback.audioRef}
        style={{ display: 'none' }}
        onLoadStart={() => console.log('⏳ Audio loading started')}
        onCanPlay={() => console.log('✅ Audio can play')}
        onWaiting={() => console.log('⏳ Audio waiting')}
        onPlaying={() => console.log('▶️ Audio playing')}
        onError={(e) => {
          console.error('Audio playback error:', e);
          showError('Audio playback failed');
        }}
      />

      <audio
        ref={audioPlayback.nextAudioRef}
        style={{ display: 'none' }}
      />
    </PlayerContainer>
  );
};

export default BottomPlayerBarConnected;
