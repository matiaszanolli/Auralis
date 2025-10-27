/**
 * useUnifiedPlayer - React hook for UnifiedPlayerManager
 * ======================================================
 *
 * Provides a React-friendly interface to UnifiedPlayerManager.
 * Manages lifecycle, state synchronization, and event handling.
 *
 * Usage:
 * ```tsx
 * const player = useUnifiedPlayer({
 *   enhanced: false,
 *   preset: 'adaptive',
 *   debug: true
 * });
 *
 * // Load and play track
 * await player.loadTrack(trackId);
 * await player.play();
 *
 * // Switch to enhanced mode
 * await player.setEnhanced(true, 'warm');
 * ```
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { UnifiedPlayerManager, UnifiedPlayerConfig, PlayerState, PlayerMode } from '../services/UnifiedPlayerManager';

export interface UseUnifiedPlayerConfig extends UnifiedPlayerConfig {
  /** Auto-play after loading track */
  autoPlay?: boolean;
}

export interface UseUnifiedPlayerResult {
  // State
  state: PlayerState;
  mode: PlayerMode;
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  isLoading: boolean;
  error: Error | null;

  // Controls
  loadTrack: (trackId: number) => Promise<void>;
  play: () => Promise<void>;
  pause: () => void;
  seek: (time: number) => Promise<void>;
  setEnhanced: (enhanced: boolean, preset?: string) => Promise<void>;
  setPreset: (preset: string) => Promise<void>;
  setVolume: (volume: number) => void;

  // Manager access
  manager: UnifiedPlayerManager | null;
  audioElement: HTMLAudioElement | null;
}

/**
 * React hook for UnifiedPlayerManager
 */
export function useUnifiedPlayer(config: UseUnifiedPlayerConfig = {}): UseUnifiedPlayerResult {
  const managerRef = useRef<UnifiedPlayerManager | null>(null);
  const [state, setState] = useState<PlayerState>('idle');
  const [mode, setMode] = useState<PlayerMode>('mse');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<Error | null>(null);

  // Initialize manager on mount
  useEffect(() => {
    const manager = new UnifiedPlayerManager(config);
    managerRef.current = manager;

    // Subscribe to state changes
    const unsubscribeState = manager.on('statechange', ({ newState }) => {
      setState(newState);
    });

    const unsubscribeTime = manager.on('timeupdate', ({ currentTime: time, duration: dur }) => {
      setCurrentTime(time);
      setDuration(dur);
    });

    const unsubscribeMode = manager.on('modeswitched', ({ mode: newMode }) => {
      setMode(newMode);
    });

    const unsubscribeError = manager.on('error', (err) => {
      setError(err);
      console.error('[useUnifiedPlayer] Error:', err);
    });

    // Initial mode
    setMode(manager.getMode());

    return () => {
      // Cleanup subscriptions
      unsubscribeState();
      unsubscribeTime();
      unsubscribeMode();
      unsubscribeError();

      // Cleanup manager
      manager.cleanup();
      managerRef.current = null;
    };
  }, []); // Empty deps - only initialize once

  // Load track
  const loadTrack = useCallback(async (trackId: number) => {
    if (!managerRef.current) throw new Error('Manager not initialized');

    setError(null);
    await managerRef.current.loadTrack(trackId);

    if (config.autoPlay) {
      await managerRef.current.play();
    }
  }, [config.autoPlay]);

  // Play
  const play = useCallback(async () => {
    if (!managerRef.current) throw new Error('Manager not initialized');
    await managerRef.current.play();
  }, []);

  // Pause
  const pause = useCallback(() => {
    if (!managerRef.current) return;
    managerRef.current.pause();
  }, []);

  // Seek
  const seek = useCallback(async (time: number) => {
    if (!managerRef.current) return;
    await managerRef.current.seek(time);
  }, []);

  // Set enhanced mode
  const setEnhanced = useCallback(async (enhanced: boolean, preset?: string) => {
    if (!managerRef.current) return;
    await managerRef.current.setEnhanced(enhanced, preset);
  }, []);

  // Set preset
  const setPreset = useCallback(async (preset: string) => {
    if (!managerRef.current) return;
    await managerRef.current.setPreset(preset);
  }, []);

  // Set volume
  const setVolume = useCallback((volume: number) => {
    if (!managerRef.current) return;
    managerRef.current.setVolume(volume);
  }, []);

  // Get audio element
  const audioElement = managerRef.current?.getAudioElement() ?? null;

  // Derived state
  const isPlaying = state === 'playing';
  const isLoading = state === 'loading' || state === 'switching' || state === 'buffering';

  return {
    // State
    state,
    mode,
    currentTime,
    duration,
    isPlaying,
    isLoading,
    error,

    // Controls
    loadTrack,
    play,
    pause,
    seek,
    setEnhanced,
    setPreset,
    setVolume,

    // Manager access
    manager: managerRef.current,
    audioElement
  };
}

export default useUnifiedPlayer;
