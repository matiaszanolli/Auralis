/**
 * usePlayerWithAudio - Unified Player Composition Hook
 *
 * Combines backend player API management with Web Audio API playback into a single hook.
 * Provides both queue/track management (usePlayerAPI) and audio playback control (useUnifiedWebMAudioPlayer).
 *
 * This consolidates usePlayerAPI and useUnifiedWebMAudioPlayer into a single composition,
 * simplifying player state management and reducing hook complexity.
 *
 * Features:
 * - Queue and playlist management (from usePlayerAPI)
 * - Real-time WebSocket state updates (from usePlayerAPI)
 * - Web Audio API playback (from useUnifiedWebMAudioPlayer)
 * - Enhanced audio processing support (presets, enhancement toggle)
 * - Unified loading and error state
 * - Automatic track loading and sync between backend and Web Audio
 *
 * Usage:
 * ```tsx
 * const {
 *   // Queue & Track Data
 *   currentTrack,
 *   queue,
 *   queueIndex,
 *
 *   // Playback State
 *   isPlaying,
 *   currentTime,
 *   duration,
 *   volume,
 *   loading,
 *   error,
 *
 *   // Playback Controls
 *   play,
 *   pause,
 *   togglePlayPause,
 *   next,
 *   previous,
 *   seek,
 *   setVolume,
 *   setQueue,
 *   playTrack,
 *
 *   // Enhanced Audio Controls
 *   setEnhanced,
 *   setPreset,
 *
 *   // Utilities
 *   refreshStatus,
 *   player
 * } = usePlayerWithAudio({ enhanced: true, preset: 'adaptive' });
 * ```
 *
 * @see usePlayerAPI.ts (deprecated, use this instead)
 * @see useUnifiedWebMAudioPlayer.ts (deprecated, use this instead)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { getApiUrl } from '../config/api';
import {
  UnifiedWebMAudioPlayer,
  UnifiedWebMAudioPlayerConfig,
  PlaybackState,
  StreamMetadata
} from '../services/UnifiedWebMAudioPlayer';

// ============================================================================
// Types
// ============================================================================

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  file_path?: string;
  album_id?: number;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

export interface PlayerState {
  currentTrack: Track | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  queue: Track[];
  queueIndex: number;
}

export interface UsePlayerWithAudioOptions extends UnifiedWebMAudioPlayerConfig {
  /** Auto-play after loading track */
  autoPlay?: boolean;
}

export interface UsePlayerWithAudioReturn {
  // Queue & Track Data
  currentTrack: Track | null;
  queue: Track[];
  queueIndex: number;

  // Playback State
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  loading: boolean;
  error: string | null;

  // Web Audio State
  audioState: PlaybackState;
  audioMetadata: StreamMetadata | null;
  audioError: Error | null;

  // Playback Controls
  play: () => Promise<void>;
  pause: () => Promise<void>;
  togglePlayPause: () => Promise<void>;
  next: () => Promise<void>;
  previous: () => Promise<void>;
  seek: (position: number) => Promise<void>;
  setVolume: (volume: number) => Promise<void>;
  setQueue: (tracks: Track[], startIndex?: number) => Promise<void>;
  playTrack: (track: Track) => Promise<void>;

  // Enhanced Audio Controls
  setEnhanced: (enhanced: boolean, preset?: string) => Promise<void>;
  setPreset: (preset: string) => Promise<void>;

  // Utilities
  refreshStatus: () => Promise<void>;
  player: UnifiedWebMAudioPlayer | null;
}

// ============================================================================
// Hook Implementation
// ============================================================================

export const usePlayerWithAudio = (
  config: UsePlayerWithAudioOptions = {}
): UsePlayerWithAudioReturn => {
  // Backend Player State
  const [playerState, setPlayerState] = useState<PlayerState>({
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 80,
    queue: [],
    queueIndex: 0
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Web Audio Player Reference
  const playerRef = useRef<UnifiedWebMAudioPlayer | null>(null);

  // Web Audio State
  const [audioState, setAudioState] = useState<PlaybackState>('idle');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [audioMetadata, setAudioMetadata] = useState<StreamMetadata | null>(null);
  const [audioError, setAudioError] = useState<Error | null>(null);

  const { subscribe } = useWebSocketContext();

  // ========================================================================
  // Web Audio Player Setup
  // ========================================================================

  useEffect(() => {
    const player = new UnifiedWebMAudioPlayer(config);
    playerRef.current = player;

    // Subscribe to state changes
    const unsubscribeState = player.on('statechange', ({ newState }) => {
      setAudioState(newState);
    });

    const unsubscribeTime = player.on('timeupdate', ({ currentTime: time, duration: dur }) => {
      setCurrentTime(time);
      setDuration(dur);
    });

    const unsubscribeError = player.on('error', (err) => {
      setAudioError(err);
      console.error('[usePlayerWithAudio] Audio error:', err);
    });

    // Cleanup on unmount
    return () => {
      unsubscribeState();
      unsubscribeTime();
      unsubscribeError();
      player.cleanup();
      playerRef.current = null;
    };
  }, []);

  // Update audio metadata when state changes
  useEffect(() => {
    if (playerRef.current) {
      const meta = playerRef.current.getMetadata();
      setAudioMetadata(meta);
      if (meta) {
        setDuration(meta.duration);
      }
    }
  }, [audioState]);

  // ========================================================================
  // Backend Player API Methods
  // ========================================================================

  const fetchPlayerStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/player/status`);
      if (response.ok) {
        const data = await response.json();
        setPlayerState(prev => ({
          ...prev,
          currentTrack: data.current_track || null,
          isPlaying: data.is_playing || false,
          currentTime: data.current_time || 0,
          duration: data.duration || 0,
          volume: data.volume !== undefined ? data.volume : prev.volume,
          queue: data.queue || [],
          queueIndex: data.queue_index || 0
        }));
      }
    } catch (err) {
      console.error('Failed to fetch player status:', err);
    }
  }, []);

  const apiPlay = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/player/play`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        setPlayerState(prev => ({
          ...prev,
          isPlaying: true,
          currentTrack: data.track || prev.currentTrack
        }));
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to play');
      }
    } catch (err) {
      setError('Network error');
      console.error('Play error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const apiPause = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/player/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        setPlayerState(prev => ({
          ...prev,
          isPlaying: false
        }));
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to pause');
      }
    } catch (err) {
      setError('Network error');
      console.error('Pause error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const play = useCallback(async () => {
    await apiPlay();
    if (playerRef.current) {
      await playerRef.current.play();
    }
  }, [apiPlay]);

  const pause = useCallback(async () => {
    await apiPause();
    if (playerRef.current) {
      playerRef.current.pause();
    }
  }, [apiPause]);

  const togglePlayPause = useCallback(async () => {
    if (playerState.isPlaying) {
      await pause();
    } else {
      await play();
    }
  }, [playerState.isPlaying, play, pause]);

  const next = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/player/next`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        setPlayerState(prev => ({
          ...prev,
          currentTrack: data.track || null,
          queueIndex: data.queue_index || prev.queueIndex + 1,
          currentTime: 0
        }));

        // Load track in Web Audio
        if (data.track && playerRef.current) {
          await playerRef.current.loadTrack(data.track.id);
          if (playerState.isPlaying) {
            await playerRef.current.play();
          }
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to skip to next');
      }
    } catch (err) {
      setError('Network error');
      console.error('Next error:', err);
    } finally {
      setLoading(false);
    }
  }, [playerState.isPlaying]);

  const previous = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/player/previous`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (response.ok) {
        const data = await response.json();
        setPlayerState(prev => ({
          ...prev,
          currentTrack: data.track || null,
          queueIndex: data.queue_index || Math.max(0, prev.queueIndex - 1),
          currentTime: 0
        }));

        // Load track in Web Audio
        if (data.track && playerRef.current) {
          await playerRef.current.loadTrack(data.track.id);
          if (playerState.isPlaying) {
            await playerRef.current.play();
          }
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to go to previous');
      }
    } catch (err) {
      setError('Network error');
      console.error('Previous error:', err);
    } finally {
      setLoading(false);
    }
  }, [playerState.isPlaying]);

  const seek = useCallback(async (position: number) => {
    try {
      const response = await fetch(`/api/player/seek`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position })
      });

      if (response.ok) {
        setPlayerState(prev => ({
          ...prev,
          currentTime: position
        }));
      }

      // Also seek in Web Audio
      if (playerRef.current) {
        await playerRef.current.seek(position);
      }
    } catch (err) {
      console.error('Seek error:', err);
    }
  }, []);

  const setVolume = useCallback(async (volume: number) => {
    try {
      const response = await fetch(`/api/player/volume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume })
      });

      if (response.ok) {
        setPlayerState(prev => ({
          ...prev,
          volume
        }));
      }

      // Also set volume in Web Audio
      if (playerRef.current) {
        playerRef.current.setVolume(volume / 100);
      }
    } catch (err) {
      console.error('Volume error:', err);
    }
  }, []);

  const setQueue = useCallback(async (tracks: Track[], startIndex: number = 0) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/player/queue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tracks: tracks.map(t => t.id),
          start_index: startIndex
        })
      });

      if (response.ok) {
        const data = await response.json();
        setPlayerState(prev => ({
          ...prev,
          queue: tracks,
          queueIndex: startIndex,
          currentTrack: tracks[startIndex] || null
        }));

        // Load first track in Web Audio
        if (tracks.length > 0 && playerRef.current) {
          await playerRef.current.loadTrack(tracks[startIndex].id);
          await apiPlay();
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to set queue');
      }
    } catch (err) {
      setError('Network error');
      console.error('Queue error:', err);
    } finally {
      setLoading(false);
    }
  }, [apiPlay]);

  const playTrack = useCallback(async (track: Track) => {
    // Guard: Don't restart if same track is already playing
    if (playerState.currentTrack?.id === track.id && playerState.isPlaying) {
      console.log('✋ Already playing this track, ignoring duplicate play request');
      return;
    }

    console.log('▶️ Playing track:', track.title);
    await setQueue([track], 0);
  }, [setQueue, playerState]);

  // ========================================================================
  // Enhanced Audio Controls
  // ========================================================================

  const setEnhanced = useCallback(async (enhanced: boolean, preset?: string) => {
    if (!playerRef.current) return;
    await playerRef.current.setEnhanced(enhanced, preset);
  }, []);

  const setPreset = useCallback(async (preset: string) => {
    if (!playerRef.current) return;
    await playerRef.current.setPreset(preset);
  }, []);

  // ========================================================================
  // WebSocket for Real-time Updates
  // ========================================================================

  useEffect(() => {
    console.log('🎵 usePlayerWithAudio: Setting up WebSocket subscriptions');

    // Subscribe to player_state messages
    const unsubscribePlayerState = subscribe('player_state', (message: any) => {
      try {
        const state = message.data;
        setPlayerState({
          currentTrack: state.current_track || null,
          isPlaying: state.is_playing || false,
          currentTime: state.current_time || 0,
          duration: state.duration || 0,
          volume: state.volume !== undefined ? state.volume : 80,
          queue: state.queue || [],
          queueIndex: state.queue_index || 0
        });
        console.log('Player state updated:', state);
      } catch (err) {
        console.error('Error handling player_state message:', err);
      }
    });

    // Subscribe to legacy player_update messages (fallback)
    const unsubscribePlayerUpdate = subscribe('player_update', (message: any) => {
      try {
        setPlayerState(prev => ({
          ...prev,
          currentTrack: message.current_track || prev.currentTrack,
          isPlaying: message.is_playing !== undefined ? message.is_playing : prev.isPlaying,
          currentTime: message.current_time !== undefined ? message.current_time : prev.currentTime,
          duration: message.duration !== undefined ? message.duration : prev.duration,
          volume: message.volume !== undefined ? message.volume : prev.volume
        }));
      } catch (err) {
        console.error('Error handling player_update message:', err);
      }
    });

    // Fetch initial player status
    fetchPlayerStatus();

    // Cleanup: unsubscribe from both message types
    return () => {
      console.log('🎵 usePlayerWithAudio: Cleaning up WebSocket subscriptions');
      unsubscribePlayerState();
      unsubscribePlayerUpdate();
    };
  }, [subscribe, fetchPlayerStatus]);

  // ========================================================================
  // Auto-load track when currentTrack changes
  // ========================================================================

  useEffect(() => {
    if (playerState.currentTrack && playerState.currentTrack.id && playerRef.current) {
      console.log(`[usePlayerWithAudio] Loading track ${playerState.currentTrack.id}: ${playerState.currentTrack.title}`);
      playerRef.current.loadTrack(playerState.currentTrack.id).catch((err) => {
        console.error('[usePlayerWithAudio] Failed to load track:', err);
        setAudioError(err);
      });
    }
  }, [playerState.currentTrack?.id]);

  // ========================================================================
  // Return
  // ========================================================================

  return {
    // Queue & Track Data
    currentTrack: playerState.currentTrack,
    queue: playerState.queue,
    queueIndex: playerState.queueIndex,

    // Playback State
    isPlaying: playerState.isPlaying,
    currentTime: playerState.currentTime,
    duration: playerState.duration,
    volume: playerState.volume,
    loading,
    error,

    // Web Audio State
    audioState,
    audioMetadata,
    audioError,

    // Playback Controls
    play,
    pause,
    togglePlayPause,
    next,
    previous,
    seek,
    setVolume,
    setQueue,
    playTrack,

    // Enhanced Audio Controls
    setEnhanced,
    setPreset,

    // Utilities
    refreshStatus: fetchPlayerStatus,
    player: playerRef.current
  };
};

export default usePlayerWithAudio;
