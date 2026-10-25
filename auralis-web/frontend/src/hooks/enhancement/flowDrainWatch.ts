/**
 * Flow-control drain watch (#5863)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The resume half of buffer flow control must not depend on the next chunk
 * arriving: after `buffer_full` the SERVER parks on its flow gate and sends
 * nothing, so `ingestChunk` (the only place that used to evaluate
 * `nextFlowControlSignal`) never runs again — the rest of the track was
 * never delivered and playback stalled with no error frame. This polls the
 * ring's fill from the playback side while flow is paused and emits
 * `buffer_ready` once it drains below the resume threshold.
 */

import { FLOW_RESUME_FILL_PCT } from './audioChunkIngest';
import type PCMStreamBuffer from '@/services/audio/PCMStreamBuffer';

export interface FlowDrainWatchDeps {
  flowPausedRef: React.MutableRefObject<boolean>;
  pcmBufferRef: React.MutableRefObject<PCMStreamBuffer | null>;
  send: (message: { type: string; data: Record<string, unknown> }) => void;
}

/** How often the fill level is sampled while flow is paused (#5863). */
export const FLOW_DRAIN_POLL_MS = 250;

/**
 * Start polling; returns a stop function. Registered for the lifetime of
 * the streaming core (one interval that no-ops while flow is not paused),
 * so the resume signal fires whenever the buffer drains — with or without
 * new chunks arriving.
 */
export function startFlowDrainWatch({
  flowPausedRef,
  pcmBufferRef,
  send,
}: FlowDrainWatchDeps): () => void {
  const id = window.setInterval(() => {
    if (!flowPausedRef.current) return;
    const buffer = pcmBufferRef.current;
    if (!buffer) return;
    if (buffer.getFillPercentage() < FLOW_RESUME_FILL_PCT) {
      flowPausedRef.current = false;
      send({ type: 'buffer_ready', data: {} });
    }
  }, FLOW_DRAIN_POLL_MS);
  return () => window.clearInterval(id);
}
