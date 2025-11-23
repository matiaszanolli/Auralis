/**
 * PlayerBarV2Connected - Connected version of PlayerBarV2
 *
 * Orchestrator component combining PlayerBarV2 UI with complete functionality.
 * Replaces BottomPlayerBarUnified with modern design token-based styling.
 *
 * Architecture: This component is now a thin orchestrator using focused hooks:
 * - usePlayerTrackLoader: Track loading and error handling
 * - usePlayerEnhancementSync: Enhancement settings synchronization
 * - usePlayerEventHandlers: Playback control event handlers
 *
 * Features:
 * - Modern PlayerBarV2 UI with design tokens
 * - Toast notifications for errors and user feedback
 * - Track loading with proper error handling
 * - Enhancement settings sync
 * - Single unified player instance (no duplicates)
 *
 * This is the ONLY player bar component - eliminates duplicate player instances.
 */

import React, { useCallback } from 'react';
import { PlayerBarV2 } from './PlayerBarV2';
import { usePlayerAPI } from '@/hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '@/hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '@/contexts/EnhancementContext';
import { useToast } from '@/components/shared/ui/feedback';
import { usePlayerState } from './usePlayerState';
import { usePlayerTrackLoader } from '@/hooks/usePlayerTrackLoader';
import { usePlayerEnhancementSync } from '@/hooks/usePlayerEnhancementSync';

const PlayerBarV2Connected: React.FC = () => {
  // ========== State Management ==========
  const {
    currentTrack,
    isPlaying,
    volume,
    setVolume,
    queue,
    queueIndex,
    play,
    pause,
    next,
    previous
  } = usePlayerAPI();

  const {
    settings: enhancementSettings,
    setEnabled: setEnhancementEnabled
  } = useEnhancement();

  const { info, error: showError } = useToast();

  // Initialize unified player with enhancement config
  // Use location.origin to get the current protocol + host:port
  // This works for both web and Electron (localhost:8765) access
  const apiBaseUrl = typeof window !== 'undefined'
    ? window.location.origin
    : 'http://localhost:8765';

  const player = useUnifiedWebMAudioPlayer({
    apiBaseUrl,
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: true,
    autoPlay: true
  });

  // ========== Feature Hooks ==========

  // Track loading with proper error handling
  usePlayerTrackLoader({
    player,
    trackId: currentTrack?.id,
    trackTitle: currentTrack?.title,
    onError: showError,
  });

  // Enhancement settings synchronization
  usePlayerEnhancementSync({
    player,
    settings: enhancementSettings,
    onError: showError,
  });

  // ========== UI State ==========

  const playerState = usePlayerState({
    currentTrack,
    unifiedPlayer: player,
    volume,
    enhancementSettings,
    queue,
    queueIndex,
  });

  // ========== Event Handlers ==========

  // Play handler - wraps async player play with Redux sync
  const handlePlay = useCallback(async () => {
    console.log('[PlayerBarV2Connected] Play');
    try {
      await player.play();
      play();
      info('Playing');
    } catch (err: any) {
      console.error('[PlayerBarV2Connected] Play failed:', err);
      showError(`Playback failed: ${err.message}`);
    }
  }, [player, play, info, showError]);

  // Pause handler - synchronous
  const handlePause = useCallback(() => {
    console.log('[PlayerBarV2Connected] Pause');
    player.pause();
    pause();
  }, [player, pause]);

  // Seek handler - wraps async player seek
  const handleSeek = useCallback(async (time: number) => {
    console.log('[PlayerBarV2Connected] Seek to', time.toFixed(2));
    try {
      await player.seek(time);
    } catch (err: any) {
      console.error('[PlayerBarV2Connected] Seek failed:', err);
      showError(`Seek failed: ${err.message}`);
    }
  }, [player, showError]);

  // Volume change handler - synchronous, syncs to both player and Redux
  const handleVolumeChange = useCallback((newVolume: number) => {
    console.log('[PlayerBarV2Connected] Volume changed to', newVolume.toFixed(2));
    player.setVolume(newVolume);
    setVolume(newVolume);
  }, [player, setVolume]);

  // Enhancement toggle handler - wraps async player enhancement change
  const handleEnhancementToggle = useCallback(async () => {
    const newEnabled = !enhancementSettings.enabled;
    console.log('[PlayerBarV2Connected] Enhancement', newEnabled ? 'enabled' : 'disabled');
    try {
      await player.setEnhanced(newEnabled, enhancementSettings.preset);
      setEnhancementEnabled(newEnabled);
      info(`Enhancement ${newEnabled ? 'enabled' : 'disabled'}`);
    } catch (err: any) {
      console.error('[PlayerBarV2Connected] Enhancement toggle failed:', err);
      showError(`Enhancement error: ${err.message}`);
    }
  }, [player, enhancementSettings, setEnhancementEnabled, info, showError]);

  // Previous handler - navigate to previous track in queue
  const handlePrevious = useCallback(async () => {
    console.log('[PlayerBarV2Connected] Previous');
    if (queue.length === 0 || queueIndex === 0) {
      console.log('[PlayerBarV2Connected] Cannot go previous: at start of queue');
      return;
    }
    try {
      await previous();
      info('Previous track');
    } catch (err: any) {
      console.error('[PlayerBarV2Connected] Previous failed:', err);
      showError(`Failed to go to previous: ${err.message}`);
    }
  }, [queue, queueIndex, previous, info, showError]);

  // Next handler - navigate to next track in queue
  const handleNext = useCallback(async () => {
    console.log('[PlayerBarV2Connected] Next');
    if (queue.length === 0 || queueIndex >= queue.length - 1) {
      console.log('[PlayerBarV2Connected] Cannot go next: at end of queue');
      return;
    }
    try {
      await next();
      info('Next track');
    } catch (err: any) {
      console.error('[PlayerBarV2Connected] Next failed:', err);
      showError(`Failed to go to next: ${err.message}`);
    }
  }, [queue, queueIndex, next, info, showError]);

  // ========== Render ==========

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
