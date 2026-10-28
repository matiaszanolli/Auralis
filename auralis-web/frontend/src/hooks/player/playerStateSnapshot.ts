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

export function applyPlayerStateSnapshot(
  state: Partial<RawPlayerStateData>,
  dispatch: AppDispatch,
  store: Store<RootState>
): void {
  // Player state — guarded on field presence so partial messages do not
  // overwrite valid state with undefined/NaN. React 18 batches these.
  //
  // #5601: the engine's snapshot can lag a client-authoritative local
  // skip — the engine pointer only moves on the next play command
  // (#5460 tracks that backend drift). When the snapshot's track
  // differs from the track the session is playing, it is that stale
  // pointer speaking: keep the local track, and reconcile queue_index
  // below to the local track's slot instead of regressing both. A cold
  // start (no local track) adopts the snapshot as before. Position and
  // duration fields are deliberately untouched by this gate — their
  // staleness is pre-existing and self-limiting, not this issue.
  const playingTrackId = store.getState().player.currentTrack?.id ?? null;
  if ('current_track' in state) {
    const track = state.current_track;
    if (track && playingTrackId != null && track.id !== playingTrackId) {
      import.meta.env.DEV && console.log('[usePlayerStateSync] Ignoring stale engine track', track.id, '— playing', playingTrackId, '(#5601)');
    } else if (track) {
      dispatch(setCurrentTrack(mapTrackInfoToTrack(track)));
    } else {
      dispatch(setCurrentTrack(null));
    }
  }

  // #5898: while this browser session is playing a track it owns is_playing, duration,
  // current_time, volume and mute. The backend manager is never told about local
  // pause/resume/skip/volume, so its copy is whatever the last set_queue left (playing, 80 %,
  // first track's duration, a wall-clock position) - and any full snapshot (a repeat toggle,
  // Clear Queue, a reconnect push) overwrote the live values: volume jumped back to 80 %, a
  // paused session flipped to playing, the previous track's duration landed on the current one.
  // A cold start (no local track) adopts the snapshot as before.
  const sessionOwnsPlayback = playingTrackId != null;
  // A duration correction for the track being played is still welcome (#4580); one that comes with
  // another track's snapshot is the stale pointer speaking and would land on the wrong track.
  const durationIsForPlayingTrack =
    !sessionOwnsPlayback || !state.current_track || state.current_track.id === playingTrackId;

  if (!sessionOwnsPlayback && 'is_playing' in state && state.is_playing !== undefined) {
    dispatch(setIsPlaying(state.is_playing));
  }

  // setDuration BEFORE setCurrentTime: the setCurrentTime reducer clamps
  // to Math.min(payload, state.duration), so on cold start / reconnect a
  // stale duration (possibly 0) would silently clamp currentTime to the
  // wrong value if applied first (#3936).
  // Number.isFinite (not typeof === 'number', which admits NaN): a single
  // NaN duration permanently NaNs all progress/time UI until reload.
  // Matches the position_changed guard (#4158).
  if (durationIsForPlayingTrack && 'duration' in state && typeof state.duration === 'number' && Number.isFinite(state.duration)) {
    // #4580: the thunk patches the queue's copy of the same track too.
    // setDuration alone reaches only player.currentTrack, so a duration
    // correction that arrives without a fresh queue array left the two
    // records disagreeing.
    dispatch(setDurationAndSyncQueue(state.duration));
  }

  if (!sessionOwnsPlayback && 'current_time' in state && typeof state.current_time === 'number' && Number.isFinite(state.current_time)) {
    dispatch(setCurrentTime(state.current_time));
  }

  if (!sessionOwnsPlayback && 'volume' in state && typeof state.volume === 'number' && Number.isFinite(state.volume)) {
    dispatch(setVolume(state.volume));
  }

  if (!sessionOwnsPlayback && 'is_muted' in state && state.is_muted !== undefined) {
    dispatch(setMuted(state.is_muted));
  }

  // isEnhancementPreset narrows the wire string, so no `as` cast is
  // needed and the guard cannot drift from the canonical list (#5610).
  if (state.current_preset && isEnhancementPreset(state.current_preset)) {
    dispatch(setPreset(state.current_preset));
  }

  // Queue state
  if (state.queue && Array.isArray(state.queue)) {
    dispatch(setQueue(state.queue.map((t: TrackInfo) => mapTrackInfoToTrack(t))));
  }

  if ('queue_index' in state && typeof state.queue_index === 'number') {
    // #5601: reconcile the engine pointer against the playing track —
    // after a local skip it still points at the old one, and adopting
    // it raw jumped the queue highlight back while the audio continued.
    const reconciled = reconcileQueueIndex(
      store.getState().queue.tracks,
      state.queue_index,
      store.getState().player.currentTrack?.id ?? null,
    );
    if (reconciled != null) dispatch(setCurrentIndex(reconciled));
  }

  // #3586: sync shuffle/repeat from the reconnect snapshot.
  if ('shuffle_enabled' in state && state.shuffle_enabled !== undefined) {
    dispatch(setIsShuffled(state.shuffle_enabled));
  }

  if ('repeat_mode' in state && isRepeatMode(state.repeat_mode)) {
    dispatch(setRepeatMode(state.repeat_mode));
  }
}
