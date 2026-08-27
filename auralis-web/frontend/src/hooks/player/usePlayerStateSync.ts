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
 * Besides the authoritative `player_state` snapshot, it also applies the discrete
 * low-latency events the backend emits between snapshots — `position_changed`,
 * `playback_started`/`playback_resumed`/`playback_paused`/`playback_stopped`,
 * `volume_changed`, and `track_changed` — so pause/stop/skip/volume reflect in
 * Redux immediately instead of waiting up to ~1s for the next snapshot (#4144).
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

import { useEffect, useRef } from 'react';
import { useDispatch, useStore } from 'react-redux';
import type { Store } from '@reduxjs/toolkit';
import type { AppDispatch, RootState } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  setCurrentTrack,
  setIsPlaying,
  setCurrentTime,
  setVolume,
  setMuted,
  setPreset,
} from '@/store/slices/playerSlice';
import { setDurationAndSyncQueue } from '@/store/slices/playerQueueSync';
import {
  setQueue,
  setCurrentIndex,
  setIsShuffled,
  setRepeatMode,
  isRepeatMode,
} from '@/store/slices/queueSlice';
import type { PresetName } from '@/store/slices/playerSlice';
import type { RawPlayerStateData, TrackInfo } from '@/types/websocket';

const VALID_PRESETS: readonly string[] = ['adaptive', 'gentle', 'warm', 'bright', 'punchy'];

/**
 * Hook to sync WebSocket player_state messages to Redux (player + queue)
 */
export function usePlayerStateSync() {
  // Typed dispatch so the #4580 thunk is accepted, matching how the
  // sibling setCurrentTrackAndSyncQueue thunk (#3587) is dispatched.
  const dispatch = useDispatch<AppDispatch>();
  // Read-only access to current state inside WS callbacks (e.g. to resolve a
  // track_changed index against the synced queue) without re-subscribing on
  // every state change.
  const store = useStore() as Store<RootState>;
  const { subscribe, connectionStatus } = useWebSocketContext();
  // Highest `seq` applied so far (fixes #3732). The backend broadcasts
  // player_state outside its update lock, so concurrent update_state() calls
  // can deliver snapshots out of order; drop anything older than what we've
  // already applied instead of regressing the UI to stale state.
  const lastSeenSeqRef = useRef(0);

  // Highest track_changed `seq` applied so far (#4582). This is a SEPARATE
  // watermark from lastSeenSeqRef above, not a shared one: track_changed's
  // seq comes from NavigationService's own counter (it mutates the engine's
  // queue, not PlayerStateManager.state, so there is no shared generation to
  // draw from — see the backend's _TrackChangeSequencer). Comparing it
  // against lastSeenSeqRef would reject valid track_changed events any time
  // the two counters happened to disagree in magnitude.
  const lastSeenTrackChangedSeqRef = useRef(0);

  // A backend restart resets its StateManager seq counter to 0, but this ref
  // survives across reconnects — every post-restart snapshot would otherwise
  // be dropped as "older" until the counter climbs back past the pre-restart
  // max (#4338). Reset on every (re)connection: within one continuous
  // session connectionStatus never flips back to 'connected', so the #3732
  // out-of-order guard still holds there. Same rationale applies to the
  // NavigationService-side counter behind lastSeenTrackChangedSeqRef.
  useEffect(() => {
    if (connectionStatus === 'connected') {
      lastSeenSeqRef.current = 0;
      lastSeenTrackChangedSeqRef.current = 0;
    }
  }, [connectionStatus]);

  useEffect(() => {
    if (!subscribe) {
      console.warn('[usePlayerStateSync] WebSocket context not available');
      return;
    }

    const unsubscribe = subscribe('player_state', (message) => {
      try {
        const state = (message as { data: Partial<RawPlayerStateData> }).data;
        if (!state || typeof state !== 'object') return;

        if (typeof state.seq === 'number') {
          if (state.seq < lastSeenSeqRef.current) return;
          lastSeenSeqRef.current = state.seq;
        }

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
          // #4580: the thunk patches the queue's copy of the same track too.
          // setDuration alone reaches only player.currentTrack, so a duration
          // correction that arrives without a fresh queue array left the two
          // records disagreeing.
          dispatch(setDurationAndSyncQueue(state.duration));
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

        if ('repeat_mode' in state && isRepeatMode(state.repeat_mode)) {
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
      const data = (message as { data?: { position?: number; seq?: number } }).data;
      if (!data || typeof data.position !== 'number' || !Number.isFinite(data.position)) {
        return;
      }

      // #4544: position_changed mutates the same current_time field that
      // player_state does, and the backend computes it under a lock but
      // broadcasts outside it — the exact shape the player_state seq guard
      // exists for (#3732). Without this check a stale pre-seek tick could land
      // after the post-seek snapshot and rewind the progress bar.
      //
      // The tick carries the CURRENT generation rather than a new one, so
      // `seq === lastSeenSeqRef.current` is a legitimate refinement and must be
      // applied; only strictly older ticks are dropped. The dispatch is skipped
      // entirely rather than clamped — a stale-but-finite position is wrong,
      // not merely out of range.
      //
      // lastSeenSeqRef is deliberately NOT advanced here: a tick is not a new
      // state generation, and only player_state should move the watermark. The
      // reconnect reset (#4338) is shared automatically via the same ref.
      if (typeof data.seq === 'number' && data.seq < lastSeenSeqRef.current) {
        return;
      }

      dispatch(setCurrentTime(data.position));
    });

    // Discrete player events (#4144). The periodic player_state snapshot is the
    // authoritative reconciler, but these give immediate, low-latency updates so
    // pause/stop/skip/volume reflect in Redux without waiting up to ~1s for the
    // next snapshot. Previously the command hooks claimed these messages
    // "update the Redux player slice" but no subscriber existed.
    const unsubscribeStarted = subscribe('playback_started', () => {
      dispatch(setIsPlaying(true));
    });
    const unsubscribeResumed = subscribe('playback_resumed', () => {
      dispatch(setIsPlaying(true));
    });
    const unsubscribePaused = subscribe('playback_paused', () => {
      dispatch(setIsPlaying(false));
    });
    const unsubscribeStopped = subscribe('playback_stopped', () => {
      dispatch(setIsPlaying(false));
    });

    const unsubscribeVolume = subscribe('volume_changed', (message) => {
      // 0-100 integer scale — matches playerSlice.setVolume and the scale the
      // player_state snapshot uses.
      const data = (message as { data?: { volume?: number } }).data;
      if (data && typeof data.volume === 'number' && Number.isFinite(data.volume)) {
        dispatch(setVolume(data.volume));
      }
    });

    // track_changed carries the new queue position (#4144). next/previous/jumped
    // all include track_index now; resolve the track from the already-synced
    // queue rather than replicating backend shuffle/repeat ordering client-side.
    const unsubscribeTrackChanged = subscribe('track_changed', (message) => {
      const data = (message as { data?: { action?: string; track_index?: number; seq?: number } }).data;
      if (!data || typeof data.track_index !== 'number' || !Number.isInteger(data.track_index)) {
        // No index in payload — let the next player_state snapshot reconcile.
        return;
      }

      // #4582: a rapid skip burst can interleave concurrent next/previous/
      // jump broadcasts at the WS layer even though the backend now
      // serializes their engine mutation (NavigationService's
      // _TrackChangeSequencer). Drop anything older than the newest seq
      // already applied instead of regressing the queue position — same
      // shape as the player_state guard above, but its own watermark.
      if (typeof data.seq === 'number') {
        if (data.seq < lastSeenTrackChangedSeqRef.current) return;
        lastSeenTrackChangedSeqRef.current = data.seq;
      }

      const index = data.track_index;
      const tracks = store.getState().queue.tracks;
      if (index >= 0 && index < tracks.length) {
        dispatch(setCurrentIndex(index));
        dispatch(setCurrentTrack(tracks[index]));
      }
    });

    return () => {
      unsubscribe?.();
      unsubscribePosition?.();
      unsubscribeStarted?.();
      unsubscribeResumed?.();
      unsubscribePaused?.();
      unsubscribeStopped?.();
      unsubscribeVolume?.();
      unsubscribeTrackChanged?.();
    };
  }, [subscribe, dispatch, store]);
}

export default usePlayerStateSync;
