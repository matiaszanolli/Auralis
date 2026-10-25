/**
 * Flow-control drain watch (#5863)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 * After `buffer_full` the server parks on its flow gate and sends no further
 * chunk, so the only code that used to evaluate the resume signal
 * (`ingestChunk`, on chunk arrival) could never run again — the rest of the
 * track was never delivered. The drain watch polls the ring's fill from the
 * playback side and emits `buffer_ready` below the resume threshold.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FLOW_DRAIN_POLL_MS, startFlowDrainWatch } from '../flowDrainWatch';

function makeBuffer(fill: number) {
  let current = fill;
  return {
    getFillPercentage: () => current,
    drainTo: (v: number) => { current = v; },
  };
}

describe('startFlowDrainWatch (#5863)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('sends buffer_ready once the fill drains below the resume threshold, with no new chunks', () => {
    const buffer = makeBuffer(80); // above FLOW_RESUME_FILL_PCT (50)
    const flowPausedRef = { current: true };
    const send = vi.fn();

    const stop = startFlowDrainWatch({
      flowPausedRef: flowPausedRef as never,
      pcmBufferRef: { current: buffer } as never,
      send,
    });
    try {
      vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS);
      expect(send).not.toHaveBeenCalled(); // still above the threshold

      buffer.drainTo(45);
      vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS);

      expect(send).toHaveBeenCalledTimes(1);
      expect(send).toHaveBeenCalledWith({ type: 'buffer_ready', data: {} });
      expect(flowPausedRef.current).toBe(false);
    } finally {
      stop();
    }
  });

  it('does nothing while flow is not paused', () => {
    const buffer = makeBuffer(10); // would resume, but flow is not paused
    const send = vi.fn();

    const stop = startFlowDrainWatch({
      flowPausedRef: { current: false } as never,
      pcmBufferRef: { current: buffer } as never,
      send,
    });
    try {
      vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS * 10);
      expect(send).not.toHaveBeenCalled();
    } finally {
      stop();
    }
  });

  it('sends buffer_ready only once per pause (the flag clears)', () => {
    const buffer = makeBuffer(30);
    const flowPausedRef = { current: true };
    const send = vi.fn();

    const stop = startFlowDrainWatch({
      flowPausedRef: flowPausedRef as never,
      pcmBufferRef: { current: buffer } as never,
      send,
    });
    try {
      vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS * 5);
      expect(send).toHaveBeenCalledTimes(1);
    } finally {
      stop();
    }
  });

  it('tolerates the buffer vanishing (cleanup between tracks)', () => {
    const send = vi.fn();
    const stop = startFlowDrainWatch({
      flowPausedRef: { current: true } as never,
      pcmBufferRef: { current: null } as never,
      send,
    });
    try {
      vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS * 5);
      expect(send).not.toHaveBeenCalled();
    } finally {
      stop();
    }
  });

  it('stops polling after the returned stop function runs', () => {
    const buffer = makeBuffer(30);
    const flowPausedRef = { current: true };
    const send = vi.fn();

    const stop = startFlowDrainWatch({
      flowPausedRef: flowPausedRef as never,
      pcmBufferRef: { current: buffer } as never,
      send,
    });
    stop();
    vi.advanceTimersByTime(FLOW_DRAIN_POLL_MS * 5);
    expect(send).not.toHaveBeenCalled();
    expect(flowPausedRef.current).toBe(true);
  });
});
