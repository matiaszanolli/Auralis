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

import React from 'react';
import { PlayerBarV2 } from './PlayerBarV2';
import { usePlayerAPI } from '@/hooks/usePlayerAPI';
import { useUnifiedWebMAudioPlayer } from '@/hooks/useUnifiedWebMAudioPlayer';
import { useEnhancement } from '@/contexts/EnhancementContext';
import { useToast } from '@/components/shared/ui/feedback';
import { usePlayerState } from './usePlayerState';
import { usePlayerFeatures } from './usePlayerFeatures';

const PlayerBarV2Connected: React.FC = () => {
  // ========== State Management ==========
  const {
    currentTrack,
    isPlaying,
    volume,
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

  const handlers = usePlayerFeatures({
    player,
    currentTrack,
    queue,
    queueIndex,
    enhancementSettings,
    callbacks: {
      play,
      pause,
      next,
      previous,
      setVolume: (vol) => {
        // TODO: connect to Redux volume setter
      },
      setEnhanced: (enabled, preset) => player.setEnhanced(enabled, preset),
      setEnhancementEnabled,
    },
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

  // ========== Render ==========

  return (
    <PlayerBarV2
      player={playerState}
      onPlay={handlers.onPlay}
      onPause={handlers.onPause}
      onSeek={handlers.onSeek}
      onVolumeChange={handlers.onVolumeChange}
      onEnhancementToggle={handlers.onEnhancementToggle}
      onPrevious={handlers.onPrevious}
      onNext={handlers.onNext}
    />
  );
};

export default PlayerBarV2Connected;
