/**
 * usePlayerStateSync - Synchronize WebSocket player_state with Redux
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * This hook ensures that Redux playerSlice and queueSlice stay in sync with the authoritative
 * backend player state received via WebSocket.
 *
 * It subscribes to 'player_state' WebSocket messages and dispatches Redux actions
 * to keep both player and queue state up to date. This is the single synchronization point
 * between WebSocket broadcasts and Redux.
 *
 * State synchronized:
 * - Player: currentTrack, isPlaying, currentTime, duration, volume, isMuted, preset
 * - Queue: tracks, currentIndex (queue position)
 *
 * Architecture: Backend → WebSocket broadcast → This hook → Redux dispatch → UI
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  setCurrentTrack,
  setIsPlaying,
  setCurrentTime,
  setDuration,
  setVolume,
  setMuted,
  setPreset,
} from '@/store/slices/playerSlice';
import { setQueue, setCurrentIndex } from '@/store/slices/queueSlice';
import type { PresetName } from '@/store/slices/playerSlice';
import type { RawPlayerStateData, TrackInfo } from '@/types/websocket';

/**
 * Hook to sync WebSocket player_state messages to Redux (player + queue)
 *
 * Dispatches actions to keep both player and queue state synchronized
 * with the authoritative backend state.
 */
export function usePlayerStateSync() {
  const dispatch = useDispatch();
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    if (!subscribe) {
      console.warn('[usePlayerStateSync] WebSocket context not available');
      return;
    }

    // Subscribe to player_state messages from backend
    const unsubscribe = subscribe('player_state', (message) => {
      try {
        const state = (message as { data: RawPlayerStateData }).data;

        // ============================================================
        // PLAYER STATE SYNCHRONIZATION
        // ============================================================

        // Sync current track
        if (state.current_track) {
          const track: TrackInfo = state.current_track;
          dispatch(
            setCurrentTrack({
              id: track.id,
              title: track.title,
              artist: track.artist,
              album: track.album || '',
              duration: track.duration || 0,
              artworkUrl: track.artwork_url,
            })
          );
        } else if (state.current_track === null) {
          dispatch(setCurrentTrack(null));
        }

        // Sync playback state
        dispatch(setIsPlaying(state.is_playing));

        // Sync playback position
        dispatch(setCurrentTime(state.current_time));

        // Sync duration
        dispatch(setDuration(state.duration));

        // Sync volume
        dispatch(setVolume(state.volume));

        // Sync mute state
        dispatch(setMuted(state.is_muted));

        // Sync audio preset (validate before dispatching to prevent store corruption)
        const VALID_PRESETS: readonly string[] = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];
        if (state.current_preset && VALID_PRESETS.includes(state.current_preset)) {
          dispatch(setPreset(state.current_preset as PresetName));
        }

        // ============================================================
        // QUEUE STATE SYNCHRONIZATION
        // ============================================================

        // Sync queue tracks
        if (state.queue && Array.isArray(state.queue)) {
          const tracks = state.queue.map((t: TrackInfo) => ({
            id: t.id,
            title: t.title,
            artist: t.artist,
            album: t.album || '',
            duration: t.duration || 0,
            artworkUrl: t.artwork_url,
          }));
          dispatch(setQueue(tracks));
        }

        // Sync queue position (index)
        dispatch(setCurrentIndex(state.queue_index));

        if (process.env.NODE_ENV !== 'production') {
          console.log('[usePlayerStateSync] Redux updated from WebSocket:', state);
        }
      } catch (err) {
        console.error('[usePlayerStateSync] Error processing player_state:', err);
      }
    });

    // Cleanup: unsubscribe when component unmounts
    return () => {
      unsubscribe?.();
    };
  }, [subscribe, dispatch]);
}

export default usePlayerStateSync;
