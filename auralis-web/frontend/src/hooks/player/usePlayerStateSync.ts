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
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
 */

import { useEffect } from 'react';
import { useDispatch, useStore } from 'react-redux';
import type { AppDispatch, RootState } from '@/store';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import {
  useMessageSubscriptions,
  type MessageHandlers,
  type SubscribeFn,
} from '@/hooks/websocket/useWebSocketMessages';
import { setCurrentTrack, setIsPlaying, setCurrentTime, setVolume } from '@/store/slices/playerSlice';
import { setCurrentIndex } from '@/store/slices/queueSlice';
import type { RawPlayerStateData } from '@/types/websocket';
import { applyPlayerStateSnapshot } from './playerStateSnapshot';
import { acceptSeq, isStaleSeq, useSyncWatermarks } from './playerSyncWatermarks';

/** Stands in for an absent context's `subscribe`: nothing to subscribe to, nothing to undo. */
const noopSubscribe = (() => () => undefined) as unknown as SubscribeFn;

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
  const store = useStore<RootState>();
  const { subscribe } = useWebSocketContext();
  const watermarks = useSyncWatermarks();

  // The handlers are rebuilt each render and read through useMessageSubscriptions' ref, so the eight
  // subscriptions are made once; everything they touch (dispatch, store, the watermark refs) is
  // stable (#6041).
  const shouldApplyTransportEvent = (message: { data?: { seq?: number } }): boolean =>
    acceptSeq(watermarks.transport, message.data?.seq);

  const handlers: MessageHandlers = {
    player_state: (message) => {
      try {
        const state: Partial<RawPlayerStateData> | undefined = message.data;
        if (!state || typeof state !== 'object') return;

        watermarks.observeServerInstance(state.server_instance_id);
        if (!acceptSeq(watermarks.state, state.seq)) return;

        applyPlayerStateSnapshot(state, dispatch, store);

        if (import.meta.env.DEV) {
          console.log('[usePlayerStateSync] Redux updated from WebSocket:', state);
        }
      } catch (err) {
        console.error('[usePlayerStateSync] Error processing player_state:', err);
      }
    },

    // Lightweight 1Hz position tick (fixes #3937 / RS-5). The backend emits a
    // `position_changed` message every second during playback instead of
    // re-broadcasting the full player_state; without this subscriber
    // redux.player.currentTime was frozen between state-change events.
    position_changed: (message) => {
      const data = message.data;
      if (!data || typeof data.position !== 'number' || !Number.isFinite(data.position)) {
        return;
      }

      // #4544: position_changed mutates the same current_time field that
      // player_state does, and the backend computes it under a lock but
      // broadcasts outside it — the exact shape the player_state seq guard
      // exists for (#3732). Without this check a stale pre-seek tick could land
      // after the post-seek snapshot and rewind the progress bar.
      //
      // The tick carries the CURRENT generation rather than a new one, so an equal seq is a
      // legitimate refinement and must be applied; only strictly older ticks are dropped, and
      // the dispatch is skipped entirely rather than clamped - a stale-but-finite position is
      // wrong, not merely out of range. The watermark is deliberately NOT advanced: a tick is
      // not a new state generation, only player_state moves it.
      if (isStaleSeq(watermarks.state, data.seq)) return;

      dispatch(setCurrentTime(data.position));
    },

    // Discrete player events (#4144). The periodic player_state snapshot is the
    // authoritative reconciler, but these give immediate, low-latency updates so
    // pause/stop/skip/volume reflect in Redux without waiting up to ~1s for the
    // next snapshot. Previously the command hooks claimed these messages
    // "update the Redux player slice" but no subscriber existed.
    playback_started: (message) => {
      if (!shouldApplyTransportEvent(message)) return;
      dispatch(setIsPlaying(true));
    },
    playback_resumed: (message) => {
      if (!shouldApplyTransportEvent(message)) return;
      dispatch(setIsPlaying(true));
    },
    playback_paused: (message) => {
      if (!shouldApplyTransportEvent(message)) return;
      dispatch(setIsPlaying(false));
    },
    playback_stopped: (message) => {
      if (!shouldApplyTransportEvent(message)) return;
      dispatch(setIsPlaying(false));
    },

    volume_changed: (message) => {
      // 0-100 integer scale — matches playerSlice.setVolume and the scale the
      // player_state snapshot uses.
      const data = message.data;
      if (data && typeof data.volume === 'number' && Number.isFinite(data.volume)) {
        if (!acceptSeq(watermarks.volume, data.seq)) return;
        dispatch(setVolume(data.volume));
      }
    },

    // track_changed carries the new queue position (#4144). next/previous
    // all include track_index now; resolve the track from the already-synced
    // queue rather than replicating backend shuffle/repeat ordering client-side.
    track_changed: (message) => {
      const data = message.data;
      if (!data || typeof data.track_index !== 'number' || !Number.isInteger(data.track_index)) {
        // No index in payload — let the next player_state snapshot reconcile.
        return;
      }

      // #4582: a rapid skip burst can interleave concurrent next/previous
      // broadcasts at the WS layer even though the backend now
      // serializes their engine mutation (NavigationService's
      // _TrackChangeSequencer). Drop anything older than the newest seq
      // already applied instead of regressing the queue position — same
      // shape as the player_state guard above, but its own watermark.
      if (!acceptSeq(watermarks.trackChanged, data.seq)) return;

      const index = data.track_index;
      const tracks = store.getState().queue.tracks;
      // Deliberately NOT #5601-reconciled: track_changed is a backend-driven
      // navigation event (NavigationService's next/previous), where the
      // ENGINE is the authority the client follows. Nothing emits it today
      // (PLAYER_NEXT/PREVIOUS have no frontend callers), but gating it would
      // break that contract for the day it is wired. The stale-pointer writers
      // are queue_changed and player_state, which both reconcile.
      if (index >= 0 && index < tracks.length) {
        dispatch(setCurrentIndex(index));
        dispatch(setCurrentTrack(tracks[index]));
      }
    },
  };

  useEffect(() => {
    if (!subscribe) console.warn('[usePlayerStateSync] WebSocket context not available');
  }, [subscribe]);

  useMessageSubscriptions(subscribe ?? noopSubscribe, handlers);
}

export default usePlayerStateSync;
