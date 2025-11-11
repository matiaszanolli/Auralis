/**
 * PlayerBarV2Connected - Connected version of PlayerBarV2
 *
 * Unified player bar combining PlayerBarV2 UI with complete functionality.
 * Replaces BottomPlayerBarUnified with modern design token-based styling.
 *
 * Features:
 * - Modern PlayerBarV2 UI with design tokens
 * - Toast notifications for errors and user feedback
 * - Volume control with mute and mouse wheel support
 * - Track loading with proper error handling
 * - Enhancement settings sync
 * - Single unified player instance (no duplicates)
 *
 * This is the ONLY player bar component - eliminates duplicate player instances.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { PlayerBarV2 } from './PlayerBarV2';
import { usePlayerAPI } from '@/hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '@/hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '@/contexts/EnhancementContext';
import { useToast } from '@/components/shared/Toast';

const PlayerBarV2Connected: React.FC = () => {
  // Get player state from hooks
  const {
    currentTrack,
    isPlaying,
    volume,
    queue,
    queueIndex,
    play,
    pause,
    next,
    previous,
    setVolume,
    togglePlayPause
  } = usePlayerAPI();

  const {
    settings: enhancementSettings,
    setEnabled: setEnhancementEnabled,
    setPreset: setEnhancementPreset
  } = useEnhancement();

  // Toast notifications
  const { success, info, error: showError } = useToast();

  // Initialize unified player with enhancement config
  const player = useUnifiedWebMAudioPlayer({
    apiBaseUrl: 'http://localhost:8765',
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: true,
    autoPlay: true
  });

  // Load track when currentTrack changes
  useEffect(() => {
    if (currentTrack && currentTrack.id) {
      console.log(`[PlayerBarV2] Loading track ${currentTrack.id}: ${currentTrack.title}`);
      player.loadTrack(currentTrack.id)
        .then(() => {
          console.log(`[PlayerBarV2] Track loaded successfully`);
          return player.play();
        })
        .catch((err) => {
          console.error(`[PlayerBarV2] Failed to load track:`, err);
          showError(`Playback error: ${err.message}`);
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTrack?.id]); // Only depend on track ID, not the entire object or player

  // Show error toast when player encounters errors
  useEffect(() => {
    if (player.error) {
      showError(`Playback error: ${player.error.message}`);
    }
  }, [player.error, showError]);

  // Sync enhancement settings with player when they change
  useEffect(() => {
    if (player.player) {
      console.log(`[PlayerBarV2] Enhancement settings changed: enabled=${enhancementSettings.enabled}, preset=${enhancementSettings.preset}`);
      player.setEnhanced(enhancementSettings.enabled, enhancementSettings.preset).catch((err) => {
        console.error(`[PlayerBarV2] Failed to sync enhancement settings:`, err);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enhancementSettings.enabled, enhancementSettings.preset, enhancementSettings.intensity]);

  // Callbacks - use player instance methods
  const handlePlay = useCallback(() => {
    player.play();
  }, [player]);

  const handlePause = useCallback(() => {
    player.pause();
  }, [player]);

  const handleSeek = useCallback((time: number) => {
    player.seek(time);
  }, [player]);

  const handleVolumeChange = useCallback((newVolume: number) => {
    player.setVolume(newVolume);
  }, [player]);

  const handleEnhancementToggle = useCallback(async () => {
    const newEnabled = !enhancementSettings.enabled;
    console.log(`[PlayerBarV2] Enhancement ${newEnabled ? 'enabled' : 'disabled'}`);
    try {
      await player.setEnhanced(newEnabled, enhancementSettings.preset);
      setEnhancementEnabled(newEnabled);
      info(newEnabled ? `Enhancement enabled (${enhancementSettings.preset})` : 'Enhancement disabled');
    } catch (err: any) {
      showError(`Failed to toggle enhancement: ${err.message}`);
    }
  }, [enhancementSettings.enabled, enhancementSettings.preset, player, setEnhancementEnabled, info, showError]);

  const handlePrevious = useCallback(async () => {
    // Check if queue exists and current position allows going back
    if (!queue || queue.length === 0 || queueIndex === 0) {
      console.log('[PlayerBarV2] Cannot go to previous: at beginning of queue or no queue');
      return;
    }

    try {
      console.log(`[PlayerBarV2] Navigating to previous track (index ${queueIndex} -> ${queueIndex - 1})`);
      await previous();
      info('Previous track');
    } catch (err: any) {
      console.error('[PlayerBarV2] Failed to go to previous:', err);
      showError(`Failed to go to previous: ${err.message}`);
    }
  }, [queue, queueIndex, previous, info, showError]);

  const handleNext = useCallback(async () => {
    // Check if queue exists and current position allows going forward
    if (!queue || queue.length === 0 || queueIndex >= queue.length - 1) {
      console.log('[PlayerBarV2] Cannot go to next: at end of queue or no queue');
      return;
    }

    try {
      console.log(`[PlayerBarV2] Navigating to next track (index ${queueIndex} -> ${queueIndex + 1})`);
      await next();
      info('Next track');
    } catch (err: any) {
      console.error('[PlayerBarV2] Failed to skip to next:', err);
      showError(`Failed to skip to next: ${err.message}`);
    }
  }, [queue, queueIndex, next, info, showError]);

  // Prepare player state for PlayerBarV2
  // IMPORTANT: Use player.isPlaying (unified player state) NOT Redux isPlaying
  // to avoid desync between play/pause button and actual playback
  const playerState = {
    currentTrack: currentTrack || null,
    isPlaying: player.isPlaying, // Use unified player's state
    currentTime: player.currentTime || 0,
    duration: player.duration || 0,
    volume: volume || 0.8,
    isEnhanced: enhancementSettings.enabled,
    queue: queue || [],
    queueIndex: queueIndex
  };

  return (
    <PlayerBarV2
      player={playerState}
      onPlay={handlePlay}
      onPause={handlePause}
      onSeek={handleSeek}
      onVolumeChange={handleVolumeChange}
      onEnhancementToggle={handleEnhancementToggle}
      onPrevious={handlePrevious}
      onNext={handleNext}
    />
  );
};

export default PlayerBarV2Connected;
