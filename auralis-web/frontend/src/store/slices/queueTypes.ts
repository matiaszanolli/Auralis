/**
 * Queue slice state shape and the repeat-mode allowlist.
 *
 * Split out of queueSlice.ts (#5841); the slice re-exports every name here.
 */

import type { QueueTrack as Track } from '@/types/domain';

import type { RepeatMode } from '@/types/domain';

export type { RepeatMode };

/** Allowlist for repeat_mode coming off the wire (#4159). An invalid value
 *  would enter queue.repeatMode and silently halt next/previous advancement. */
export const VALID_REPEAT_MODES: readonly RepeatMode[] = ['off', 'all', 'one'];

export const isRepeatMode = (value: unknown): value is RepeatMode =>
  typeof value === 'string' && (VALID_REPEAT_MODES as readonly string[]).includes(value);

export interface QueueState {
  tracks: Track[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: RepeatMode;
  lastUpdated: number;
}
