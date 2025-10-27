/**
 * useMSEPlayer Hook
 * ==================
 *
 * React hook for using MSEPlayer with automatic lifecycle management.
 *
 * Features:
 * - Automatic cleanup on unmount
 * - React-friendly event handling
 * - State management integration
 * - TypeScript support
 *
 * Usage:
 * ```tsx
 * const { player, state, play, pause, switchPreset } = useMSEPlayer({
 *   enhanced: true,
 *   preset: 'adaptive',
 *   debug: true
 * });
 * ```
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import MSEPlayer, {
  MSEPlayerConfig,
  MSEPlayerState,
  StreamMetadata,
  ChunkMetadata
} from '../services/MSEPlayer';

export interface UseMSEPlayerConfig extends MSEPlayerConfig {
  /** Audio element to use (if not provided, creates one) */
  audioElement?: HTMLAudioElement;

  /** Auto-play after initialization */
  autoPlay?: boolean;
}

export interface UseMSEPlayerReturn {
  /** MSEPlayer instance */
  player: MSEPlayer | null;

  /** Current player state */
  state: MSEPlayerState;

  /** Stream metadata */
  metadata: StreamMetadata | null;

  /** Current playback time */
  currentTime: number;

  /** Is MSE supported in this browser */
  isSupported: boolean;

  /** Initialize player with track */
  initialize: (trackId: number) => Promise<void>;

  /** Start playback */
  play: () => Promise<void>;

  /** Pause playback */
  pause: () => void;

  /** Seek to position */
  seek: (time: number) => void;

  /** Switch preset instantly */
  switchPreset: (preset: string) => Promise<void>;

  /** Update settings */
  updateSettings: (settings: Partial<MSEPlayerConfig>) => void;

  /** Get audio element */
  getAudioElement: () => HTMLAudioElement | null;

  /** Last loaded chunk metadata */
  lastChunk: ChunkMetadata | null;

  /** Preset switch statistics */
  presetSwitchStats: { count: number; avgLatencyMs: number };
}

export function useMSEPlayer(config: UseMSEPlayerConfig = {}): UseMSEPlayerReturn {
  // MSEPlayer instance
  const playerRef = useRef<MSEPlayer | null>(null);
  const audioElementRef = useRef<HTMLAudioElement | null>(null);

  // State
  const [state, setState] = useState<MSEPlayerState>('idle');
  const [metadata, setMetadata] = useState<StreamMetadata | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [lastChunk, setLastChunk] = useState<ChunkMetadata | null>(null);
  const [presetSwitchStats, setPresetSwitchStats] = useState({ count: 0, avgLatencyMs: 0 });

  // Check browser support
  const isSupported = MSEPlayer.isSupported();

  // Initialize audio element
  useEffect(() => {
    if (config.audioElement) {
      audioElementRef.current = config.audioElement;
    } else {
      // Create new audio element
      const audio = new Audio();
      audio.preload = 'auto';
      audioElementRef.current = audio;
    }

    return () => {
      // Cleanup: only destroy our own audio element
      if (!config.audioElement && audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current.src = '';
      }
    };
  }, [config.audioElement]);

  // Initialize MSEPlayer
  useEffect(() => {
    if (!audioElementRef.current || !isSupported) {
      return;
    }

    // Create player
    const player = new MSEPlayer(audioElementRef.current, config);
    playerRef.current = player;

    // Register event handlers
    player.on('statechange', ({ newState }: { newState: MSEPlayerState }) => {
      setState(newState);
    });

    player.on('timeupdate', ({ currentTime: time }: { currentTime: number }) => {
      setCurrentTime(time);
    });

    player.on('chunkloaded', (chunkMeta: ChunkMetadata) => {
      setLastChunk(chunkMeta);
    });

    player.on('presetswitched', ({ oldPreset, newPreset }: { oldPreset: string; newPreset: string }) => {
      console.log(`Preset switched: ${oldPreset} → ${newPreset}`);
      // Update stats
      setPresetSwitchStats(prev => ({
        count: prev.count + 1,
        avgLatencyMs: prev.avgLatencyMs // TODO: Calculate from chunk metadata
      }));
    });

    player.on('error', ({ error }: { error: any }) => {
      console.error('MSEPlayer error:', error);
    });

    return () => {
      // Cleanup: destroy player
      player.destroy();
      playerRef.current = null;
    };
  }, [isSupported]); // Only recreate if support changes

  // Initialize with track
  const initialize = useCallback(async (trackId: number) => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }

    await playerRef.current.initialize(trackId);
    setMetadata(playerRef.current.getMetadata());

    // Auto-play if configured
    if (config.autoPlay) {
      await playerRef.current.play();
    }
  }, [config.autoPlay]);

  // Play
  const play = useCallback(async () => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }
    await playerRef.current.play();
  }, []);

  // Pause
  const pause = useCallback(() => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }
    playerRef.current.pause();
  }, []);

  // Seek
  const seek = useCallback((time: number) => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }
    playerRef.current.seek(time);
  }, []);

  // Switch preset
  const switchPreset = useCallback(async (preset: string) => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }

    const startTime = performance.now();
    await playerRef.current.switchPreset(preset);
    const latency = performance.now() - startTime;

    // Update stats
    setPresetSwitchStats(prev => {
      const newCount = prev.count + 1;
      const newAvg = (prev.avgLatencyMs * prev.count + latency) / newCount;
      return { count: newCount, avgLatencyMs: newAvg };
    });

    console.log(`Preset switched in ${latency.toFixed(1)}ms`);
  }, []);

  // Update settings
  const updateSettings = useCallback((settings: Partial<MSEPlayerConfig>) => {
    if (!playerRef.current) {
      throw new Error('MSEPlayer not initialized');
    }
    playerRef.current.updateSettings(settings);
  }, []);

  // Get audio element
  const getAudioElement = useCallback(() => {
    return audioElementRef.current;
  }, []);

  return {
    player: playerRef.current,
    state,
    metadata,
    currentTime,
    isSupported,
    initialize,
    play,
    pause,
    seek,
    switchPreset,
    updateSettings,
    getAudioElement,
    lastChunk,
    presetSwitchStats
  };
}

export default useMSEPlayer;
