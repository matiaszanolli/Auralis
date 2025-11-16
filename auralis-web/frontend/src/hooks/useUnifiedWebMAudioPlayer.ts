/**
 * useUnifiedWebMAudioPlayer - React Hook for Unified Web Audio Player
 * =====================================================================
 *
 * React-friendly interface to UnifiedWebMAudioPlayer.
 * Manages lifecycle, state synchronization, and event handling.
 *
 * NEW ARCHITECTURE (Phase 2):
 * - Always uses Web Audio API
 * - Always fetches WebM/Opus from /api/stream endpoint
 * - Single player, single format, zero conflicts
 *
 * Usage:
 * ```tsx
 * const player = useUnifiedWebMAudioPlayer({
 *   enhanced: true,
 *   preset: 'adaptive',
 *   debug: true
 * });
 *
 * // Load and play track
 * await player.loadTrack(trackId);
 * await player.play();
 *
 * // Switch preset
 * await player.setPreset('warm');
 * ```
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  UnifiedWebMAudioPlayer,
  UnifiedWebMAudioPlayerConfig,
  PlaybackState,
  StreamMetadata
} from '../services/UnifiedWebMAudioPlayer';

export interface UseUnifiedWebMAudioPlayerConfig extends UnifiedWebMAudioPlayerConfig {
  /** Auto-play after loading track */
  autoPlay?: boolean;
}

export interface UseUnifiedWebMAudioPlayerResult {
  // State
  state: PlaybackState;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  isLoading: boolean;
  metadata: StreamMetadata | null;
  error: Error | null;

  // Controls
  loadTrack: (trackId: number) => Promise<void>;
  play: () => Promise<void>;
  pause: () => void;
  stop: () => void;
  seek: (time: number) => Promise<void>;
  setEnhanced: (enhanced: boolean, preset?: string) => Promise<void>;
  setPreset: (preset: string) => Promise<void>;
  setVolume: (volume: number) => void;

  // Player access
  player: UnifiedWebMAudioPlayer | null;
}

/**
 * React hook for UnifiedWebMAudioPlayer
 */
export function useUnifiedWebMAudioPlayer(
  config: UseUnifiedWebMAudioPlayerConfig = {}
): UseUnifiedWebMAudioPlayerResult {
  const playerRef = useRef<UnifiedWebMAudioPlayer | null>(null);

  // State
  const [state, setState] = useState<PlaybackState>('idle');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [metadata, setMetadata] = useState<StreamMetadata | null>(null);
  const [error, setError] = useState<Error | null>(null);

  // Initialize player on mount
  useEffect(() => {
    const player = new UnifiedWebMAudioPlayer({
      ...config,
      debug: true // Enable debug logging for investigation
    });
    playerRef.current = player;

    // Subscribe to state changes
    const unsubscribeState = player.on('statechange', ({ newState }) => {
      setState(newState);
    });

    const unsubscribeTime = player.on('timeupdate', ({ currentTime: time, duration: dur }) => {
      console.log(`[useUnifiedWebMAudioPlayer] timeupdate received: currentTime=${time.toFixed(2)}s`);
      setCurrentTime(time);
      setDuration(dur);
    });

    const unsubscribeError = player.on('error', (err) => {
      setError(err);
      console.error('[useUnifiedWebMAudioPlayer] Error:', err);
    });

    // Cleanup on unmount
    return () => {
      unsubscribeState();
      unsubscribeTime();
      unsubscribeError();

      player.cleanup();
      playerRef.current = null;
    };
  }, []); // Empty deps - only initialize once

  // Update metadata when track loads
  useEffect(() => {
    if (playerRef.current) {
      const meta = playerRef.current.getMetadata();
      setMetadata(meta);
      if (meta) {
        setDuration(meta.duration);
      }
    }
  }, [state]); // Update when state changes (track loaded)

  // Load track
  const loadTrack = useCallback(async (trackId: number) => {
    if (!playerRef.current) throw new Error('Player not initialized');

    setError(null);
    await playerRef.current.loadTrack(trackId);

    // Update metadata
    const meta = playerRef.current.getMetadata();
    setMetadata(meta);
    if (meta) {
      setDuration(meta.duration);
    }

    // Auto-play if enabled
    if (config.autoPlay) {
      await playerRef.current.play();
    }
  }, [config.autoPlay]);

  // Play
  const play = useCallback(async () => {
    if (!playerRef.current) throw new Error('Player not initialized');
    await playerRef.current.play();
  }, []);

  // Pause
  const pause = useCallback(() => {
    if (!playerRef.current) return;
    playerRef.current.pause();
  }, []);

  // Stop
  const stop = useCallback(() => {
    if (!playerRef.current) return;
    playerRef.current.stop();
  }, []);

  // Seek
  const seek = useCallback(async (time: number) => {
    if (!playerRef.current) return;
    await playerRef.current.seek(time);
  }, []);

  // Set enhanced mode
  const setEnhanced = useCallback(async (enhanced: boolean, preset?: string) => {
    if (!playerRef.current) return;
    await playerRef.current.setEnhanced(enhanced, preset);
  }, []);

  // Set preset
  const setPreset = useCallback(async (preset: string) => {
    if (!playerRef.current) return;
    await playerRef.current.setPreset(preset);
  }, []);

  // Set volume
  const setVolume = useCallback((volume: number) => {
    if (!playerRef.current) return;
    playerRef.current.setVolume(volume);
  }, []);

  // Derived state
  const isPlaying = state === 'playing';
  const isLoading = state === 'loading' || state === 'buffering' || state === 'seeking';

  return {
    // State
    state,
    currentTime,
    duration,
    isPlaying,
    isLoading,
    metadata,
    error,

    // Controls
    loadTrack,
    play,
    pause,
    stop,
    seek,
    setEnhanced,
    setPreset,
    setVolume,

    // Player access
    player: playerRef.current
  };
}

export default useUnifiedWebMAudioPlayer;
