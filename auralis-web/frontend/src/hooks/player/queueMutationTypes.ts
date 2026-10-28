/**
 * Public shape of the queue mutation actions.
 *
 * Split out of useQueueMutations.ts (#5840).
 *
 * @module hooks/player/queueMutationTypes
 */

import type { RepeatMode, Track } from '@/types/domain';
import type { ApiError } from '@/types/api';

export interface QueueMutations {
  /** Set entire queue and optional start position */
  setQueue: (tracks: Track[], startIndex?: number) => Promise<void>;
  /** Add single track to queue */
  addTrack: (track: Track, position?: number) => Promise<void>;
  /** Remove track at index */
  removeTrack: (index: number) => Promise<void>;
  /** Reorder track from one position to another */
  reorderTrack: (fromIndex: number, toIndex: number) => Promise<void>;
  /**
   * Reorder the entire queue.
   *
   * `newOrder` is a permutation of queue *indices*, not track IDs — the
   * backend validates `set(new_order) == set(range(queue_size))` and builds
   * the new queue as `[tracks[i] for i in new_order]`.
   */
  reorderQueue: (newOrder: number[]) => Promise<void>;
  /** Toggle shuffle mode */
  toggleShuffle: () => Promise<void>;
  /** Set repeat mode */
  setRepeatMode: (mode: RepeatMode) => Promise<void>;
  /** Clear entire queue */
  clearQueue: () => Promise<void>;
  /** True while a command is executing */
  isLoading: boolean;
  /** Last error from a command */
  error: ApiError | null;
  /** Clear error state */
  clearError: () => void;
}
