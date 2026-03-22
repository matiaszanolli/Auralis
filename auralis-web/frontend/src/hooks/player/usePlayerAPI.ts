/**
 * usePlayerAPI Hook
 *
 * Provides real audio playback functionality by connecting to the Auralis backend player API.
 * Handles playback control, queue management, and real-time state updates via WebSocket.
 *
 * Usage:
 * ```tsx
 * const {
 *   currentTrack,
 *   isPlaying,
 *   currentTime,
 *   duration,
 *   volume,
 *   play,
 *   pause,
 *   next,
 *   previous,
 *   seek,
 *   setVolume,
 *   setQueue
 * } = usePlayerAPI();
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';

import type { PlayerTrack } from '@/types/domain';

interface PlayerState {
  currentTrack: PlayerTrack | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  queue: PlayerTrack[];
  queueIndex: number;
}

// API_BASE removed - using getApiUrl() from config/api.ts for proper dev/prod handling

export const usePlayerAPI = () => {
  const [playerState, setPlayerState] = useState<PlayerState>({
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    volume: 80,
    queue: [],
    queueIndex: 0
  });

  // Refs for values used in callbacks to keep identity stable across playerState changes
  const currentTrackIdRef = useRef<number | null>(null);
  const isPlayingRef = useRef(false);
  currentTrackIdRef.current = playerState.currentTrack?.id ?? null;
  isPlayingRef.current = playerState.isPlaying;

  // Track in-flight commands so the WS handler can skip stale broadcasts that
  // would overwrite optimistic UI updates (fixes #2783).  We use a counter
  // (not a boolean) so concurrent commands are handled correctly.
  const pendingCommandsRef = useRef<number>(0);

  /** Wrap an async action so WS state updates are suppressed while it's in-flight. */
  const withCommandGuard = useCallback(<T,>(fn: () => Promise<T>): Promise<T> => {
    pendingCommandsRef.current++;
    return fn().finally(() => {
      // Small delay lets the server's confirmation broadcast arrive before
      // we re-enable WS state updates, preventing the stale-state flicker.
      setTimeout(() => { pendingCommandsRef.current = Math.max(0, pendingCommandsRef.current - 1); }, 150);
    });
  }, []);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current player status
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

  // Play current track or resume
  // NOTE: /api/player/play was deprecated and removed from the backend (fixes #2377).
  // Play control is now handled via WebSocket 'play_normal' messages in usePlaybackControl.
  // This implementation updates local optimistic state only.
  const play = useCallback(async () => {
    console.warn('[usePlayerAPI] play() is deprecated — use usePlaybackControl instead.');
    setPlayerState(prev => ({ ...prev, isPlaying: true }));
  }, []);

  // Pause playback
  // NOTE: /api/player/pause was deprecated and removed from the backend (fixes #2377).
  // Pause control is now handled via WebSocket 'pause' messages in usePlaybackControl.
  // This implementation updates local optimistic state only.
  const pause = useCallback(async () => {
    console.warn('[usePlayerAPI] pause() is deprecated — use usePlaybackControl instead.');
    setPlayerState(prev => ({ ...prev, isPlaying: false }));
  }, []);

  // Play/pause toggle
  const togglePlayPause = useCallback(async () => {
    if (isPlayingRef.current) {
      await pause();
    } else {
      await play();
    }
  }, [play, pause]);

  // Next track
  const next = useCallback(async () => {
    setLoading(true);
    setError(null);

    await withCommandGuard(async () => {
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
    });
  }, [withCommandGuard]);

  // Previous track
  const previous = useCallback(async () => {
    setLoading(true);
    setError(null);

    await withCommandGuard(async () => {
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
    });
  }, [withCommandGuard]);

  // Seek to position
  const seek = useCallback(async (position: number) => {
    setPlayerState(prev => ({ ...prev, currentTime: position }));

    await withCommandGuard(async () => {
      try {
        // Backend expects position as a query parameter, not a request body (fixes #2253)
        const response = await fetch(`/api/player/seek?position=${position}`, {
          method: 'POST',
        });

        if (!response.ok) {
          const errorData = await response.json();
          setError(errorData.detail || 'Failed to seek');
        }
      } catch (err) {
        setError('Network error');
        console.error('Seek error:', err);
      }
    });
  }, [withCommandGuard]);

  // Set volume
  const setVolume = useCallback(async (volume: number) => {
    setPlayerState(prev => ({ ...prev, volume }));

    await withCommandGuard(async () => {
      try {
        // Backend expects volume as query parameter
        const response = await fetch(`/api/player/volume?volume=${volume}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
          const errorData = await response.json();
          setError(errorData.detail || 'Failed to set volume');
        }
      } catch (err) {
        setError('Network error');
        console.error('Volume error:', err);
      }
    });
  }, [withCommandGuard]);

  // Set queue and optionally start playing
  const setQueue = useCallback(async (tracks: PlayerTrack[], startIndex: number = 0) => {
    setLoading(true);
    setError(null);

    await withCommandGuard(async () => {
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
          await response.json();
          setPlayerState(prev => ({
            ...prev,
            queue: tracks,
            queueIndex: startIndex,
            currentTrack: tracks[startIndex] || null
          }));

          // Auto-play first track
          if (tracks.length > 0) {
            await play();
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
    });
  }, [play, withCommandGuard]);

  // Play specific track (convenience method)
  const playTrack = useCallback(async (track: PlayerTrack) => {
    // Guard: Don't restart if same track is already playing
    if (currentTrackIdRef.current === track.id && isPlayingRef.current) {
      console.log('✋ Already playing this track, ignoring duplicate play request');
      return;
    }

    console.log('▶️ Playing track:', track.title);
    await setQueue([track], 0);
  }, [setQueue]);

  // WebSocket for real-time updates (using shared WebSocketContext)
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    console.log('🎵 usePlayerAPI: Setting up WebSocket subscriptions');

    // Subscribe to player_state messages.
    // Skip updates while a command is in-flight to avoid overwriting
    // optimistic state with stale server broadcasts (fixes #2783).
    const unsubscribePlayerState = subscribe('player_state', (message: any) => {
      if (pendingCommandsRef.current > 0) return;

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
      console.log('🎵 usePlayerAPI: Cleaning up WebSocket subscriptions');
      unsubscribePlayerState();
      unsubscribePlayerUpdate();
    };
  }, [subscribe, fetchPlayerStatus]);

  // NOTE: Periodic polling DISABLED - WebSocket provides real-time updates
  // The PlayerStateManager broadcasts player_state messages automatically:
  // - Every second during playback (position updates)
  // - On every state change (play, pause, seek, volume, track change)
  //
  // Polling was previously used as a fallback, but is no longer needed since
  // WebSocket communication is stable and reliable.
  //
  // If WebSocket fails, the connection will be re-established automatically
  // by the browser, and state will sync on reconnection via fetchPlayerStatus()
  // in the WebSocket onopen handler above.

  return {
    // State
    ...playerState,
    loading,
    error,

    // Actions
    play,
    pause,
    togglePlayPause,
    next,
    previous,
    seek,
    setVolume,
    setQueue,
    playTrack,
    refreshStatus: fetchPlayerStatus
  };
};

export default usePlayerAPI;
