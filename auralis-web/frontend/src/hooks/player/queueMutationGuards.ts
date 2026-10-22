/**
 * Bookkeeping shared by the queue mutations: the in-flight counter, the
 * call-time store snapshot, and the per-field generation counters that stop a
 * stale rollback from undoing a newer mutation.
 *
 * Split out of useQueueMutations.ts (#5840).
 *
 * @module hooks/player/queueMutationGuards
 */

import { useCallback, useRef, useState } from 'react';
import { useStore } from 'react-redux';
import type { Store } from '@reduxjs/toolkit';
import {
  selectQueueTracks,
  selectCurrentIndex,
  selectIsShuffled,
  selectRepeatMode,
} from '@/store/slices/queueSlice';
import type { Track, QueueTrack } from '@/types/domain';
import type { RootState } from '@/store';

export interface RollbackState {
  tracks: (Track | QueueTrack)[];
  currentIndex: number;
  isShuffled: boolean;
  repeatMode: 'off' | 'all' | 'one';
}

export type MutationField = 'queue' | 'shuffle' | 'repeat';

export function useQueueMutationGuards() {
  // Same pattern as usePlayerStateSync: bare useStore() types getState() as
  // unknown, which the `{ queue: QueueState }`-typed selectors reject — the
  // call-time snapshot (#5624) shipped without this and broke type-check:prod.
  const store = useStore() as Store<RootState>;

  // In-flight count, not a boolean (#5624): one shared boolean was cleared by
  // whichever mutation finished first, so with two overlapping mutations the
  // spinner dropped while the second was still in flight.
  const [inFlight, setInFlight] = useState(0);
  const isLoading = inFlight > 0;
  const beginInFlight = useCallback(() => setInFlight((n) => n + 1), []);
  const endInFlight = useCallback(() => setInFlight((n) => n - 1), []);

  /**
   * Call-time snapshot of the queue fields (#5624).
   *
   * The snapshot used to come from a render-time ref, so two mutations
   * started in the same tick both captured the pre-first-mutation state: the
   * newest mutation's failure then rolled back past the earlier mutation's
   * already-applied-and-maybe-succeeded change. Reading the store at call
   * time sees every optimistically-applied mutation that preceded this one,
   * so a rollback restores exactly its own pre-state.
   */
  const snapshot = useCallback((): RollbackState => {
    const state = store.getState();
    return {
      tracks: selectQueueTracks(state),
      currentIndex: selectCurrentIndex(state),
      isShuffled: selectIsShuffled(state),
      repeatMode: selectRepeatMode(state),
    };
  }, [store]);

  /**
   * Per-field generation counters guarding stale rollbacks (#4836).
   *
   * A rollback restores a snapshot taken *before* its own mutation applied, so
   * if a later mutation has since applied (and possibly already succeeded), the
   * earlier mutation's failure would undo it too — for the queue that means a
   * whole-array overwrite discarding the later change entirely.
   *
   * Each mutation stamps its field's counter on entry and only rolls back if it
   * is still the newest mutation for that field. Counters are per-field rather
   * than global so a queue mutation cannot suppress a shuffle rollback, or vice
   * versa. A suppressed rollback still surfaces its error to the caller; the
   * server's `queue_changed` broadcast is what reconciles the state.
   */
  const generationRef = useRef({ queue: 0, shuffle: 0, repeat: 0 });

  const beginMutation = useCallback(
    (field: keyof typeof generationRef.current): number => (generationRef.current[field] += 1),
    []
  );

  const isNewestMutation = useCallback(
    (field: keyof typeof generationRef.current, generation: number): boolean =>
      generationRef.current[field] === generation,
    []
  );

  return { isLoading, beginInFlight, endInFlight, snapshot, beginMutation, isNewestMutation };
}
