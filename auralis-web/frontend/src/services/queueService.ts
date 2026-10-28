/**
 * Queue Service
 *
 * The engine-queue calls that have a production caller: replace the queue and
 * append one or several tracks. Removing, reordering, shuffling and clearing go
 * through useQueueMutations (optimistic Redux update + rollback), and the
 * initial fetch through useQueueFetch, so this module carries none of them.
 */

import type { RepeatMode } from '@/types/domain';
import { ENDPOINTS } from '@/config/api';
import { post } from '@/utils/apiRequest';
import type { TrackInfo } from '@/types/websocket';

/**
 * Wire shape of `GET /api/player/queue` — the backend's QueueInfoResponse
 * (routers/player_models.py). The optional fields mirror its `| None = None`
 * members: consumers must treat everything below the first three as possibly
 * absent rather than relying on the server to populate it.
 */
export interface QueueResponse {
  // #5018: this used to declare its own local QueueTrack — filepath required,
  // artist/album optional, the exact inverse of the real backend contract
  // (player_state.py's TrackInfo: artist/album always present, filepath
  // Field(exclude=True) so it's never actually sent). Using the canonical
  // TrackInfo means a caller doesn't inherit a landmine.
  tracks: TrackInfo[];
  current_index: number;
  track_count: number | null;
  current_track?: TrackInfo | null;
  has_next?: boolean | null;
  has_previous?: boolean | null;
  // #4787: shuffle_enabled is the one true field name QueueManager emits —
  // is_shuffled/isShuffled were phantom keys the backend never sent.
  shuffle_enabled?: boolean | null;
  // repeat_mode, not the engine's repeat_enabled bool (#3896).
  repeat_mode?: RepeatMode | null;
}

/**
 * Set the queue with new tracks
 * @param trackIds Array of track IDs
 * @param startIndex Index to start playing from (default: 0)
 */
export async function setQueue(trackIds: number[], startIndex: number = 0): Promise<void> {
  await post(ENDPOINTS.QUEUE, {
    tracks: trackIds,
    start_index: startIndex,
  });
}

/**
 * Append a track to the engine queue (or insert it at `position`).
 *
 * The backend answers with a `queue_changed` broadcast, which
 * `useQueueSubscription` mirrors into Redux — callers must NOT also write the
 * Redux queue, or the track appears twice until the next snapshot (#5612).
 */
export async function addTrackToQueue(trackId: number, position?: number): Promise<void> {
  await post(ENDPOINTS.QUEUE_ADD_TRACK, {
    track_id: trackId,
    ...(position !== undefined && { position }),
  });
}

/**
 * Append multiple tracks to the engine queue in selection order (#5651).
 *
 * One batch request instead of N concurrent single-adds: the backend resolves
 * and appends under one engine lock, so the queue order is exactly
 * `trackIds`' order, and one `queue_changed` broadcast goes out. Like the
 * single add, callers must NOT also write the Redux queue (#5612).
 */
export async function addTracksToQueue(trackIds: number[]): Promise<{ added_count: number; requested_count: number; queue_size: number }> {
  return post(ENDPOINTS.QUEUE_ADD_TRACKS, { track_ids: trackIds });
}
