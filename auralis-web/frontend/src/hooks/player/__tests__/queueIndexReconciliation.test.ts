/**
 * queueIndexReconciliation unit tests (#5601).
 *
 * Navigation is client-authoritative (local Next/Previous move only Redux and
 * restart the stream over WS), so every backend index applier reconciles the
 * engine's pointer against the track the session is playing. These tests pin
 * the shared rule the three appliers (queue_changed, player_state.queue_index,
 * track_changed) must agree on.
 */

import { describe, it, expect } from 'vitest';
import { reconcileQueueIndex } from '../queueIndexReconciliation';

const tracks = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 2 }];

describe('reconcileQueueIndex', () => {
  it('takes the engine index when it already points at the playing track', () => {
    expect(reconcileQueueIndex(tracks, 1, 2)).toBe(1);
  });

  it('resolves the playing track’s nearest slot when the engine pointer is stale', () => {
    // Local skip to track 3 (slot 2); the engine still points at slot 0
    // (track 1). The queue highlight follows the audio, not the engine.
    expect(reconcileQueueIndex(tracks, 0, 3)).toBe(2);
  });

  it('picks the nearest duplicate slot, not the first match', () => {
    // Playing track 2: it sits at slots 1 and 3. The engine pointer picks the
    // closer one; a tie keeps the earlier slot.
    expect(reconcileQueueIndex(tracks, 3, 2)).toBe(3);
    expect(reconcileQueueIndex(tracks, 0, 2)).toBe(1);
    expect(reconcileQueueIndex(tracks, 2, 2)).toBe(1);
  });

  it('returns null when the playing track is not in the snapshot’s queue', () => {
    // Caller keeps the local index rather than adopting an unusable snapshot.
    expect(reconcileQueueIndex(tracks, 0, 99)).toBeNull();
  });

  it('adopts the snapshot with no local track (cold start)', () => {
    expect(reconcileQueueIndex(tracks, 1, null)).toBe(1);
    expect(reconcileQueueIndex(tracks, 1, undefined)).toBe(1);
  });

  it('returns null for an out-of-range engine index', () => {
    expect(reconcileQueueIndex(tracks, 4, 1)).toBeNull();
    expect(reconcileQueueIndex(tracks, -1, 1)).toBeNull();
    expect(reconcileQueueIndex([], 0, 1)).toBeNull();
  });
});
