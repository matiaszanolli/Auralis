/**
 * Sequence watermarks for usePlayerStateSync (#6275).
 *
 * The backend broadcasts outside its locks, so frames can arrive out of order; each event family
 * keeps the highest `seq` it has applied and drops anything strictly older (#3732, #4544, #4582,
 * #5294). The four watermarks are SEPARATE counters because the backend draws them from separate
 * sequences: comparing track_changed's seq (NavigationService's own counter) against
 * player_state's would reject valid events whenever the two disagreed in magnitude.
 *
 *   state      player_state snapshots (position_changed ticks only read it, #4544)
 *   trackChanged  track_changed
 *   transport  playback_started/resumed/paused/stopped - ONE watermark across all four, so a
 *              delayed playback_started cannot overwrite a newer playback_paused
 *   volume     volume_changed (independent state, own sequence domain)
 */

import { useRef } from 'react';
import type { MutableRefObject } from 'react';

export type Watermark = MutableRefObject<number>;

/**
 * Accept `seq` unless it is strictly older than the watermark, and advance the watermark to it.
 * A message without a numeric seq (an older backend) is always accepted.
 */
export function acceptSeq(watermark: Watermark, seq: unknown): boolean {
  if (typeof seq !== 'number') return true;
  if (seq < watermark.current) return false;
  watermark.current = seq;
  return true;
}

/** True when `seq` is strictly older than the watermark. Does not advance it. */
export function isStaleSeq(watermark: Watermark, seq: unknown): boolean {
  return typeof seq === 'number' && seq < watermark.current;
}

export function useSyncWatermarks() {
  const state = useRef(0);
  const trackChanged = useRef(0);
  const transport = useRef(0);
  const volume = useRef(0);
  // Each player_state carries the backend's per-process server_instance_id. A backend restart
  // resets every counter (fresh process) while these refs survive the reconnect, so every
  // post-restart frame would be dropped as "older" until the counters climbed back (#4338).
  // Resetting on the id change, in the handler that applies the snapshot, cannot lose the race
  // the old useEffect([connectionStatus]) reset did (#5882). The same process keeps its counters.
  const serverInstanceId = useRef<string | null>(null);

  /** Call with each snapshot's instance id; resets the watermarks when the backend restarted. */
  const observeServerInstance = (instanceId: unknown): void => {
    if (typeof instanceId !== 'string' || instanceId === serverInstanceId.current) return;
    if (serverInstanceId.current !== null) {
      state.current = 0;
      trackChanged.current = 0;
      transport.current = 0;
      volume.current = 0;
    }
    serverInstanceId.current = instanceId;
  };

  return { state, trackChanged, transport, volume, observeServerInstance };
}
