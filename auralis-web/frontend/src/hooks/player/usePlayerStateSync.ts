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
 * - Queue: tracks, currentIndex, isShuffled, repeatMode
 *
 * Architecture: Backend → WebSocket broadcast → This hook → Redux dispatch → UI
 *
 * Dispatches are guarded with `in`-checks so partial WS messages (e.g., a queue-only
 * update missing `is_playing`) cannot overwrite valid Redux state with `undefined`/`NaN`.
 * Under React 18 + react-redux 8+, dispatches inside this callback are automatically
 * batched into a single render pass.
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
import {
  setQueue,
  setCurrentIndex,
  setIsShuffled,
  setRepeatMode,
} from '@/store/slices/queueSlice';
import type { PresetName } from '@/store/slices/playerSlice';
import type { RawPlayerStateData, TrackInfo } from '@/types/websocket';

const VALID_PRESETS: readonly string[] = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];

/**
 * Hook to sync WebSocket player_state messages to Redux (player + queue)
 */
export function usePlayerStateSync() {
  const dispatch = useDispatch();
  const { subscribe } = useWebSocketContext();

  useEffect(() => {
    if (!subscribe) {
      console.warn('[usePlayerStateSync] WebSocket context not available');
      return;
    }

    const unsubscribe = subscribe('player_state', (message) => {
      try {
        const state = (message as { data: Partial<RawPlayerStateData> }).data;
        if (!state || typeof state !== 'object') return;

        // Player state — guarded on field presence so partial messages do not
        // overwrite valid state with undefined/NaN. React 18 batches these.
        if ('current_track' in state) {
          const track = state.current_track;
          if (track) {
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
          } else {
            dispatch(setCurrentTrack(null));
          }
        }

        if ('is_playing' in state && state.is_playing !== undefined) {
          dispatch(setIsPlaying(state.is_playing));
        }

        // setDuration BEFORE setCurrentTime: the setCurrentTime reducer clamps
        // to Math.min(payload, state.duration), so on cold start / reconnect a
        // stale duration (possibly 0) would silently clamp currentTime to the
        // wrong value if applied first (#3936).
        // Number.isFinite (not typeof === 'number', which admits NaN): a single
        // NaN duration permanently NaNs all progress/time UI until reload.
        // Matches the position_changed guard (#4158).
        if ('duration' in state && typeof state.duration === 'number' && Number.isFinite(state.duration)) {
          dispatch(setDuration(state.duration));
        }

        if ('current_time' in state && typeof state.current_time === 'number' && Number.isFinite(state.current_time)) {
          dispatch(setCurrentTime(state.current_time));
        }

        if ('volume' in state && typeof state.volume === 'number' && Number.isFinite(state.volume)) {
          dispatch(setVolume(state.volume));
        }

        if ('is_muted' in state && state.is_muted !== undefined) {
          dispatch(setMuted(state.is_muted));
        }

        if (state.current_preset && VALID_PRESETS.includes(state.current_preset)) {
          dispatch(setPreset(state.current_preset as PresetName));
        }

        // Queue state
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

        if ('queue_index' in state && typeof state.queue_index === 'number') {
          dispatch(setCurrentIndex(state.queue_index));
        }

        // #3586: sync shuffle/repeat from the reconnect snapshot.
        if ('shuffle_enabled' in state && state.shuffle_enabled !== undefined) {
          dispatch(setIsShuffled(state.shuffle_enabled));
        }

        if ('repeat_mode' in state && state.repeat_mode) {
          dispatch(setRepeatMode(state.repeat_mode));
        }

        if (import.meta.env.DEV) {
          console.log('[usePlayerStateSync] Redux updated from WebSocket:', state);
        }
      } catch (err) {
        console.error('[usePlayerStateSync] Error processing player_state:', err);
      }
    });

    // Lightweight 1Hz position tick (fixes #3937 / RS-5). The backend emits a
    // `position_changed` message every second during playback instead of
    // re-broadcasting the full player_state; without this subscriber
    // redux.player.currentTime was frozen between state-change events.
    const unsubscribePosition = subscribe('position_changed', (message) => {
      const data = (message as { data?: { position?: number } }).data;
      if (data && typeof data.position === 'number' && Number.isFinite(data.position)) {
        dispatch(setCurrentTime(data.position));
      }
    });

    return () => {
      unsubscribe?.();
      unsubscribePosition?.();
    };
  }, [subscribe, dispatch]);
}

export default usePlayerStateSync;
