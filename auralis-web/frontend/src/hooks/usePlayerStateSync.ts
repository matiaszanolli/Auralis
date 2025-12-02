/**
 * usePlayerStateSync - Synchronize WebSocket player_state with Redux
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * This hook ensures that Redux playerSlice stays in sync with the authoritative
 * backend player state received via WebSocket.
 *
 * It subscribes to 'player_state' WebSocket messages and dispatches Redux actions
 * to keep the store up to date. This is the single synchronization point between
 * WebSocket broadcasts and Redux.
 *
 * Usage: Call this hook once in a provider or root component (e.g., in App or ComfortableApp)
 *
 * @copyright (C) 2025 Auralis Team
 * @license GPLv3
 */

import { useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import {
  setCurrentTrack,
  setIsPlaying,
  setCurrentTime,
  setDuration,
  setVolume,
  setMuted,
  setPreset,
} from '../store/slices/playerSlice';

/**
 * Hook to sync WebSocket player_state messages to Redux
 *
 * This ensures Redux is the single source of truth for UI components
 * All player state updates come through this pipeline:
 * Backend → WebSocket broadcast → This hook → Redux dispatch
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
    const unsubscribe = subscribe('player_state', (message: any) => {
      try {
        const state = message.data;

        // Dispatch Redux actions for each state field
        if (state.current_track) {
          dispatch(
            setCurrentTrack({
              id: state.current_track.id,
              title: state.current_track.title,
              artist: state.current_track.artist,
              album: state.current_track.album || '',
              duration: state.current_track.duration || 0,
              coverUrl: state.current_track.album_art,
            })
          );
        } else if (state.current_track === null) {
          dispatch(setCurrentTrack(null));
        }

        if (state.is_playing !== undefined) {
          dispatch(setIsPlaying(state.is_playing));
        }

        if (state.current_time !== undefined) {
          dispatch(setCurrentTime(state.current_time));
        }

        if (state.duration !== undefined) {
          dispatch(setDuration(state.duration));
        }

        if (state.volume !== undefined) {
          dispatch(setVolume(state.volume));
        }

        if (state.is_muted !== undefined) {
          dispatch(setMuted(state.is_muted));
        }

        if (state.current_preset) {
          dispatch(setPreset(state.current_preset));
        }

        console.log('[usePlayerStateSync] Redux updated from WebSocket:', state);
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
