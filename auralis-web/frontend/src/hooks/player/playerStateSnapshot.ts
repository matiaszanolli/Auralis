/**
 * Applies a `player_state` snapshot to Redux (player + queue slices).
 *
 * Split out of usePlayerStateSync.ts (#5840): the per-field guards live here,
 * the subscription, the sequence watermarks and the reconnect reset stay in
 * the hook.
 *
 * @module hooks/player/playerStateSnapshot
 */

import type { Store } from '@reduxjs/toolkit';
import type { AppDispatch, RootState } from '@/store';
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
import type { RawPlayerStateData, TrackInfo } from '@/types/websocket';
import { isEnhancementPreset } from '@/types/domain';
import { mapTrackInfoToTrack } from './trackInfoMapper';
import { reconcileQueueIndex } from './queueIndexReconciliation';

type Snapshot = Partial<RawPlayerStateData>;

// Number.isFinite (not typeof === 'number', which admits NaN): a single NaN
// duration permanently NaNs all progress/time UI until reload (#4158).
const isFiniteNumber = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value);

/**
 * Apply a `player_state` snapshot to the player and queue slices, field by
 * field: guarded on presence so a partial message never overwrites valid state
 * with undefined/NaN (React 18 batches the dispatches). The three steps run in
 * this order on purpose: the queue index is reconciled against the track the
 * first step settled on.
 */
export function applyPlayerStateSnapshot(
  state: Snapshot,
  dispatch: AppDispatch,
  store: Store<RootState>
): void {
  const playingTrackId = store.getState().player.currentTrack?.id ?? null;
  applyTrack(state, dispatch, playingTrackId);
  applyPlaybackFields(state, dispatch, playingTrackId);
  applyQueueFields(state, dispatch, store);
}

/**
 * #5601: the engine's snapshot can lag a client-authoritative local skip — the
 * engine pointer only moves on the next play command (#5460 tracks that
 * backend drift). When the snapshot's track differs from the track the session
 * is playing, it is that stale pointer speaking: keep the local track (the
 * queue index is reconciled to its slot below). A cold start (no local track)
 * adopts the snapshot.
 */
function applyTrack(state: Snapshot, dispatch: AppDispatch, playingTrackId: number | null): void {
  if (!('current_track' in state)) return;
  const track = state.current_track;
  if (track && playingTrackId != null && track.id !== playingTrackId) {
    import.meta.env.DEV && console.log('[usePlayerStateSync] Ignoring stale engine track', track.id, '— playing', playingTrackId, '(#5601)');
  } else {
    dispatch(setCurrentTrack(track ? mapTrackInfoToTrack(track) : null));
  }
}

/**
 * #5898: while this browser session is playing a track it owns is_playing,
 * duration, current_time, volume and mute. The backend manager is never told
 * about local pause/resume/skip/volume, so its copy is whatever the last
 * set_queue left (playing, 80 %, the first track's duration, a wall-clock
 * position), and any full snapshot (a repeat toggle, Clear Queue, a reconnect
 * push) used to overwrite the live values. A cold start adopts the snapshot.
 */
function applyPlaybackFields(state: Snapshot, dispatch: AppDispatch, playingTrackId: number | null): void {
  const sessionOwnsPlayback = playingTrackId != null;
  // A duration correction for the track being played is still welcome (#4580); one that comes with
  // another track's snapshot is the stale pointer speaking and would land on the wrong track.
  const durationIsForPlayingTrack =
    !sessionOwnsPlayback || !state.current_track || state.current_track.id === playingTrackId;

  if (!sessionOwnsPlayback && state.is_playing !== undefined) {
    dispatch(setIsPlaying(state.is_playing));
  }
  // setDuration BEFORE setCurrentTime: the setCurrentTime reducer clamps to
  // Math.min(payload, state.duration), so a stale duration (possibly 0) applied
  // second would silently clamp currentTime on cold start / reconnect (#3936).
  // #4580: the thunk also patches the queue's copy of the same track, which
  // setDuration alone (player.currentTrack only) left disagreeing.
  if (durationIsForPlayingTrack && isFiniteNumber(state.duration)) {
    dispatch(setDurationAndSyncQueue(state.duration));
  }
  if (!sessionOwnsPlayback && isFiniteNumber(state.current_time)) {
    dispatch(setCurrentTime(state.current_time));
  }
  if (!sessionOwnsPlayback && isFiniteNumber(state.volume)) {
    dispatch(setVolume(state.volume));
  }
  if (!sessionOwnsPlayback && state.is_muted !== undefined) {
    dispatch(setMuted(state.is_muted));
  }
  // isEnhancementPreset narrows the wire string, so no `as` cast is needed
  // and the guard cannot drift from the canonical list (#5610).
  if (state.current_preset && isEnhancementPreset(state.current_preset)) {
    dispatch(setPreset(state.current_preset));
  }
}

function applyQueueFields(state: Snapshot, dispatch: AppDispatch, store: Store<RootState>): void {
  if (state.queue && Array.isArray(state.queue)) {
    dispatch(setQueue(state.queue.map((t: TrackInfo) => mapTrackInfoToTrack(t))));
  }
  if (typeof state.queue_index === 'number') {
    // #5601: reconcile the engine pointer against the playing track — after a
    // local skip it still points at the old one, and adopting it raw jumped
    // the queue highlight back while the audio continued.
    const reconciled = reconcileQueueIndex(
      store.getState().queue.tracks,
      state.queue_index,
      store.getState().player.currentTrack?.id ?? null,
    );
    if (reconciled != null) dispatch(setCurrentIndex(reconciled));
  }
  // #3586: sync shuffle/repeat from the reconnect snapshot.
  if (state.shuffle_enabled !== undefined) {
    dispatch(setIsShuffled(state.shuffle_enabled));
  }
  if ('repeat_mode' in state && isRepeatMode(state.repeat_mode)) {
    dispatch(setRepeatMode(state.repeat_mode));
  }
}
