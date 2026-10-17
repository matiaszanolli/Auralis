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
 * @license AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
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
 *
 * #5600: a queue may legitimately hold the same track more than once, and
 * `findIndex` by id always returns the first slot — Next from `[A, B, A, C]`
 * at B wrote index 0, looping Next/auto-advance and making C unreachable.
 * Callers that know the slot they are moving to (Next/Previous/auto-advance)
 * pass `index`; id-only callers (a library row click) fall back to the
 * matching slot nearest the current index, preferring the later one on a tie.
 */
export const setCurrentTrackAndSyncQueue =
  (track: PlayerTrack | null, index?: number) =>
  (
    dispatch: (action: unknown) => unknown,
    getState: () => { queue?: { tracks: { id: number }[]; currentIndex?: number } },
  ) => {
    dispatch(setCurrentTrack(track));
    if (track == null) return;
    const queue = getState().queue;
    if (!queue?.tracks?.length) return;
    const idx = resolveQueueIndex(queue.tracks, track.id, index, queue.currentIndex);
    if (idx >= 0) {
      dispatch(setCurrentIndex(idx));
    }
  };

/**
 * The slot of `trackId` in `tracks`: the caller's `index` when it really holds
 * that track, otherwise the matching slot nearest `currentIndex` (later wins a
 * tie), or -1 when the track is not queued.
 */
function resolveQueueIndex(
  tracks: { id: number }[],
  trackId: number,
  index: number | undefined,
  currentIndex: number | undefined,
): number {
  if (index !== undefined && tracks[index]?.id === trackId) return index;

  const anchor = currentIndex ?? 0;
  let best = -1;
  let bestDistance = Infinity;
  tracks.forEach((t, i) => {
    if (t.id !== trackId) return;
    const distance = Math.abs(i - anchor);
    if (distance < bestDistance || (distance === bestDistance && i > best)) {
      best = i;
      bestDistance = distance;
    }
  });
  return best;
}

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
