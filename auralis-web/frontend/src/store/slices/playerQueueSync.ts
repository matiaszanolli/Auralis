/**
 * Player <-> queue synchronisation thunks
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Split out of playerSlice (#5042). Both thunks exist for the same reason:
 * `player` and `queue` hold two independent records of the same fact, and
 * neither slice's reducers can see the other's state, so the caller has to
 * move both. That makes them queue-synchronisation concerns rather than
 * player-state reducers, which is why they do not belong in the slice file.
 *
 * Importers point here directly rather than at a playerSlice re-export: this
 * module already imports playerSlice's action creators, so re-exporting from
 * there would make the two files circular.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import type { PlayerTrack } from '@/types/domain';
import { setCurrentIndex, updateTrackById } from '@/store/slices/queueSlice';
import { setCurrentTrack, setDuration } from '@/store/slices/playerSlice';

/**
 * #3587: dispatch `setCurrentTrack(track)` AND align `queue.currentIndex`
 * to the track's position in the queue (when it is present). Local
 * track-change paths (usePlayNormal, usePlayEnhanced, Player.next/prev)
 * previously updated only `player.currentTrack`, leaving consumers of
 * `selectCurrentQueueTrack` out of sync until the backend WebSocket
 * `player_state` confirmation arrived — or permanently, if it never did.
 *
 * If the track is not in the queue (e.g. ad-hoc play), the queue index
 * stays put and the desync window is moot (no queue-derived selector
 * matches anyway).
 */
export const setCurrentTrackAndSyncQueue =
  (track: PlayerTrack | null) =>
  (
    dispatch: (action: unknown) => unknown,
    getState: () => { queue?: { tracks: { id: number }[] } },
  ) => {
    dispatch(setCurrentTrack(track));
    if (track == null) return;
    const queue = getState().queue;
    if (!queue?.tracks?.length) return;
    const idx = queue.tracks.findIndex((t) => t.id === track.id);
    if (idx >= 0) {
      dispatch(setCurrentIndex(idx));
    }
  };

/**
 * #4580: dispatch `setDuration(duration)` AND patch the queue's copy of the
 * same track.
 *
 * `player.currentTrack` and `queue.tracks[currentIndex]` are two independent
 * records of the same fact. `setDuration` can only reach the player copy, so a
 * `player_state` snapshot carrying a re-analysed duration without a fresh
 * queue array left `selectRemainingTime` / `selectTotalQueueTime` / the queue
 * rows showing the pre-correction value indefinitely.
 *
 * Same shape as `setCurrentTrackAndSyncQueue` (#3587), which exists for the
 * same reason: the two slices must be moved together by the caller, because
 * neither reducer can see the other's state.
 *
 * Note this is a *duration* sync specifically. `artworkUrl` is the other field
 * that could in principle drift, but nothing patches it post-hoc today —
 * artwork refreshes go through a per-album version counter
 * (`useArtworkUpdates`), not through these track records — so there is no
 * one-sided write to mirror. `updateTrackById` takes a generic `changes` patch
 * so covering it later needs no new plumbing.
 */
export const setDurationAndSyncQueue =
  (duration: number) =>
  (
    dispatch: (action: unknown) => unknown,
    getState: () => { player?: { currentTrack?: { id: number } | null } },
  ) => {
    dispatch(setDuration(duration));
    const trackId = getState().player?.currentTrack?.id;
    if (trackId == null) return;
    dispatch(updateTrackById({ id: trackId, changes: { duration } }));
  };
