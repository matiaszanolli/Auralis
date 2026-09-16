/**
 * TrackInfo -> QueueTrack mapping (#5009)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Shared by every call site that dispatches a backend `TrackInfo` (the
 * queue/player_state wire shape — snake_case `artwork_url`, etc.) into the
 * camelCase-typed Redux queue slice. Extracted from usePlayerStateSync.ts,
 * which had this exact mapping duplicated at two call sites (`current_track`
 * and `queue`); useQueueFetch.ts previously skipped it entirely via an
 * unsafe cast, so a `track_changed` WS event arriving before the first
 * `player_state` snapshot could dispatch an object with `.artwork_url`
 * where `TrackInfo`/`QueueTrack` consumers (e.g. TrackInfo.tsx) read
 * `.artworkUrl`, silently rendering blank album art.
 *
 * @module hooks/player/trackInfoMapper
 */

import type { TrackInfo } from '@/types/websocket';
import type { QueueTrack } from '@/types/domain';

export function mapTrackInfoToTrack(track: TrackInfo): QueueTrack {
  return {
    id: track.id,
    title: track.title,
    artist: track.artist,
    album: track.album || '',
    duration: track.duration || 0,
    artworkUrl: track.artwork_url,
  };
}
