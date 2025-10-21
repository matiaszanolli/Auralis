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

import { useState, useEffect, useCallback } from 'react';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  file_path?: string;
}

interface PlayerState {
  currentTrack: Track | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  queue: Track[];
  queueIndex: number;
}

const API_BASE = 'http://localhost:8765/api';

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

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current player status
  const fetchPlayerStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/player/status`);
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
  const play = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/player/play`, {
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

  // Pause playback
  const pause = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/player/pause`, {
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

  // Play/pause toggle
  const togglePlayPause = useCallback(async () => {
    if (playerState.isPlaying) {
      await pause();
    } else {
      await play();
    }
  }, [playerState.isPlaying, play, pause]);

  // Next track
  const next = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/player/next`, {
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
  }, []);

  // Previous track
  const previous = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/player/previous`, {
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
  }, []);

  // Seek to position
  const seek = useCallback(async (position: number) => {
    try {
      const response = await fetch(`${API_BASE}/player/seek`, {
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
    } catch (err) {
      console.error('Seek error:', err);
    }
  }, []);

  // Set volume
  const setVolume = useCallback(async (volume: number) => {
    try {
      const response = await fetch(`${API_BASE}/player/volume`, {
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
    } catch (err) {
      console.error('Volume error:', err);
    }
  }, []);

  // Set queue and optionally start playing
  const setQueue = useCallback(async (tracks: Track[], startIndex: number = 0) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/player/queue`, {
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
  }, [play]);

  // Play specific track (convenience method)
  const playTrack = useCallback(async (track: Track) => {
    await setQueue([track], 0);
  }, [setQueue]);

  // WebSocket for real-time updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765/ws');

    ws.onopen = () => {
      console.log('Player WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        // Handle unified player state updates (single source of truth)
        if (message.type === 'player_state') {
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
        }
        // Fallback for legacy messages
        else if (message.type === 'player_update') {
          setPlayerState(prev => ({
            ...prev,
            currentTrack: message.current_track || prev.currentTrack,
            isPlaying: message.is_playing !== undefined ? message.is_playing : prev.isPlaying,
            currentTime: message.current_time !== undefined ? message.current_time : prev.currentTime,
            duration: message.duration !== undefined ? message.duration : prev.duration,
            volume: message.volume !== undefined ? message.volume : prev.volume
          }));
        }
      } catch (err) {
        console.error('WebSocket message error:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('Player WebSocket error:', err);
    };

    ws.onclose = () => {
      console.log('Player WebSocket disconnected');
    };

    // Fetch initial player status
    fetchPlayerStatus();

    // Cleanup
    return () => {
      ws.close();
    };
  }, [fetchPlayerStatus]);

  // Periodic status updates (fallback if WebSocket fails)
  useEffect(() => {
    const interval = setInterval(() => {
      if (playerState.isPlaying) {
        fetchPlayerStatus();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [playerState.isPlaying, fetchPlayerStatus]);

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
