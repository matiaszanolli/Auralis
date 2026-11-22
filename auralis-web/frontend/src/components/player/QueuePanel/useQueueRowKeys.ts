import { useMemo } from 'react';
import type { QueueTrack, Track } from '@/types/domain';

/**
 * Stable per-row React keys for the queue list (#4428).
 *
 * The key used to be `${track.id}-${index}`, which made position part of a
 * row's identity: any reorder or mid-queue removal changed the key of every
 * shifted row, so React unmounted and remounted them — precisely what
 * QueueTrackItem's React.memo was added to avoid (#4177) — and each remount
 * dropped the row's internal isFocused/hover state.
 *
 * Keying on `track.id` alone is not safe: the backend queue does not dedupe
 * (QueueController.add_track appends unconditionally), so the same track can
 * legitimately appear twice and would collide. Duplicates are disambiguated by
 * occurrence ordinal instead of array index — a queue of unique tracks gets a
 * fully position-independent key, and in a queue with duplicates only the
 * duplicates' own relative order can change a key.
 */
export function queueRowKeys(queue: readonly Pick<Track | QueueTrack, 'id'>[]): string[] {
  const seen = new Map<number, number>();
  return queue.map((track) => {
    const occurrence = seen.get(track.id) ?? 0;
    seen.set(track.id, occurrence + 1);
    return occurrence === 0 ? `qt-${track.id}` : `qt-${track.id}#${occurrence}`;
  });
}

export function useQueueRowKeys(queue: readonly (Track | QueueTrack)[]): string[] {
  return useMemo(() => queueRowKeys(queue), [queue]);
}
