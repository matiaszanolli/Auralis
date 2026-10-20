/**
 * Queue-index reconciliation (#5601)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Navigation is client-authoritative: Next/Previous move only Redux and
 * (re)start the stream over the WebSocket, so the backend engine's queue
 * pointer stays on the OLD track until the next play command (#5460 tracks
 * the backend half of that drift). Any backend snapshot that then carries
 * the engine's stale pointer — a queue_changed after a drag, a
 * player_state snapshot, a track_changed — would jump the UI back to a
 * track the audio left long ago.
 *
 * The rule every applier shares: when the engine index already points at
 * the track the session is playing, take it (the engine agrees); otherwise
 * resolve the *playing* track's slot nearest the engine pointer (the queue
 * may hold duplicate ids, #5600), and when the playing track is not in the
 * snapshot's queue at all, keep the local index (null → caller skips).
 *
 * @module hooks/player/queueIndexReconciliation
 */

export function reconcileQueueIndex(
  tracks: ReadonlyArray<{ id: number }>,
  engineIndex: number,
  playingTrackId: number | null | undefined,
): number | null {
  // An out-of-range engine index says nothing usable; keep the local value.
  if (!Number.isInteger(engineIndex) || engineIndex < 0 || engineIndex >= tracks.length) {
    return null;
  }
  // No local track to defend (cold start) — the snapshot is authoritative.
  if (playingTrackId == null) return engineIndex;
  if (tracks[engineIndex]?.id === playingTrackId) return engineIndex;

  let best: number | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let i = 0; i < tracks.length; i++) {
    if (tracks[i].id !== playingTrackId) continue;
    const distance = Math.abs(i - engineIndex);
    if (distance < bestDistance) {
      best = i;
      bestDistance = distance;
    }
  }
  return best;
}
