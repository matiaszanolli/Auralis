/**
 * usePlayerEventHandlers - Isolated playback event handlers hook
 *
 * Responsibility: Provide memoized callbacks for all player UI events
 *
 * Separated from PlayerBarV2Connected to:
 * - Make callbacks memoizable and stable
 * - Make event handling logic testable in isolation
 * - Prevent unnecessary re-renders of child components
 * - Organize all playback control handlers in one place
 */

import { useCallback } from 'react';
import type { UnifiedWebMAudioPlayer } from '@/services/UnifiedWebMAudioPlayer';

interface PlaybackState {
  queue?: any[];
  queueIndex: number;
}

interface PlaybackCallbacks {
  play: () => void;
  pause: () => void;
  next: () => Promise<void>;
  previous: () => Promise<void>;
  setVolume: (volume: number) => void;
  setEnhanced: (enabled: boolean, preset: string) => Promise<void>;
  setEnhancementEnabled: (enabled: boolean) => void;
}

interface EventHandlersOptions {
  player: UnifiedWebMAudioPlayer;
  playback: PlaybackState;
  callbacks: PlaybackCallbacks;
  enhancementEnabled: boolean;
  enhancementPreset: string;
  onInfo?: (message: string) => void;
  onError?: (message: string) => void;
}

export interface PlayerEventHandlers {
  onPlay: () => Promise<void>;
  onPause: () => void;
  onSeek: (time: number) => Promise<void>;
  onVolumeChange: (volume: number) => void;
  onEnhancementToggle: () => Promise<void>;
  onPrevious: () => Promise<void>;
  onNext: () => Promise<void>;
}

export function usePlayerEventHandlers({
  player,
  playback,
  callbacks,
  enhancementEnabled,
  enhancementPreset,
  onInfo,
  onError
}: EventHandlersOptions): PlayerEventHandlers {
  // Play handler
  const handlePlay = useCallback(async () => {
    console.log(`[usePlayerEventHandlers] Play`);
    try {
      await player.play();
      callbacks.play();
      console.log(`[usePlayerEventHandlers] Play completed successfully`);
    } catch (err: any) {
      console.error(`[usePlayerEventHandlers] Play failed:`, err);
      onError?.(`Playback failed: ${err.message}`);
    }
  }, [player, callbacks, onError]);

  // Pause handler
  const handlePause = useCallback(() => {
    console.log(`[usePlayerEventHandlers] Pause`);
    player.pause();
    callbacks.pause();
  }, [player, callbacks]);

  // Seek handler
  const handleSeek = useCallback(async (time: number) => {
    console.log(`[usePlayerEventHandlers] Seek to ${time.toFixed(2)}s`);
    try {
      await player.seek(time);
      console.log(`[usePlayerEventHandlers] Seek completed successfully`);
    } catch (err: any) {
      console.error(`[usePlayerEventHandlers] Seek failed:`, err);
      onError?.(`Seek failed: ${err.message}`);
    }
  }, [player, onError]);

  // Volume change handler
  const handleVolumeChange = useCallback((newVolume: number) => {
    console.log(`[usePlayerEventHandlers] Volume changed to ${newVolume.toFixed(2)}`);
    player.setVolume(newVolume);
  }, [player]);

  // Enhancement toggle handler
  const handleEnhancementToggle = useCallback(async () => {
    const newEnabled = !enhancementEnabled;
    console.log(`[usePlayerEventHandlers] Enhancement ${newEnabled ? 'enabled' : 'disabled'}`);
    try {
      await player.setEnhanced(newEnabled, enhancementPreset);
      callbacks.setEnhancementEnabled(newEnabled);
      onInfo?.(`Enhancement ${newEnabled ? 'enabled' : 'disabled'} (${enhancementPreset})`);
    } catch (err: any) {
      console.error(`[usePlayerEventHandlers] Failed to toggle enhancement:`, err);
      onError?.(`Failed to toggle enhancement: ${err.message}`);
    }
  }, [enhancementEnabled, enhancementPreset, player, callbacks, onInfo, onError]);

  // Previous handler
  const handlePrevious = useCallback(async () => {
    // Check if queue exists and current position allows going back
    if (!playback.queue || playback.queue.length === 0 || playback.queueIndex === 0) {
      console.log('[usePlayerEventHandlers] Cannot go to previous: at beginning of queue or no queue');
      return;
    }

    try {
      console.log(
        `[usePlayerEventHandlers] Navigating to previous track (index ${playback.queueIndex} -> ${playback.queueIndex - 1})`
      );
      await callbacks.previous();
      onInfo?.('Previous track');
    } catch (err: any) {
      console.error('[usePlayerEventHandlers] Failed to go to previous:', err);
      onError?.(`Failed to go to previous: ${err.message}`);
    }
  }, [playback.queue, playback.queueIndex, callbacks, onInfo, onError]);

  // Next handler
  const handleNext = useCallback(async () => {
    // Check if queue exists and current position allows going forward
    if (!playback.queue || playback.queue.length === 0 || playback.queueIndex >= playback.queue.length - 1) {
      console.log('[usePlayerEventHandlers] Cannot go to next: at end of queue or no queue');
      return;
    }

    try {
      console.log(
        `[usePlayerEventHandlers] Navigating to next track (index ${playback.queueIndex} -> ${playback.queueIndex + 1})`
      );
      await callbacks.next();
      onInfo?.('Next track');
    } catch (err: any) {
      console.error('[usePlayerEventHandlers] Failed to skip to next:', err);
      onError?.(`Failed to skip to next: ${err.message}`);
    }
  }, [playback.queue, playback.queueIndex, callbacks, onInfo, onError]);

  return {
    onPlay: handlePlay,
    onPause: handlePause,
    onSeek: handleSeek,
    onVolumeChange: handleVolumeChange,
    onEnhancementToggle: handleEnhancementToggle,
    onPrevious: handlePrevious,
    onNext: handleNext
  };
}
