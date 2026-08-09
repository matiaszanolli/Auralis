/**
 * Regression tests for #3774: audio_chunk_meta.seq emitted but never
 * validated by the frontend.
 *
 * The backend stamps a monotonic `seq` on every `audio_chunk_meta` frame
 * specifically so the client can detect dropped/reordered WS frames (fixes
 * #3189) — but nothing read it, so the guarantee was nominal only. This
 * verifies `handleSocketFrame` now tracks the expected `seq` per stream
 * (reset on a new `stream_epoch`, #4563) and dispatches a synthetic
 * `audio_stream_error` on a gap, reusing the existing error-handling path
 * instead of a new parallel mechanism.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  connState,
  handleSocketFrame,
  resetConnectionSingletons,
} from '../websocketConnectionCore';
import type { WebSocketManager } from '@/utils/errorHandling';

const manager = {} as WebSocketManager;

function textEvent(payload: Record<string, unknown>): MessageEvent {
  return { data: JSON.stringify(payload) } as MessageEvent;
}

function metaFrame(seq: number, overrides: Record<string, unknown> = {}) {
  return textEvent({
    type: 'audio_chunk_meta',
    data: {
      seq,
      sample_count: 4,
      chunk_index: 0,
      chunk_count: 1,
      frame_index: 0,
      frame_count: 1,
      stream_type: 'enhanced',
      track_id: 1,
      stream_epoch: 1,
      ...overrides,
    },
  });
}

describe('websocketConnectionCore audio_chunk_meta.seq desync detection (#3774)', () => {
  beforeEach(() => {
    resetConnectionSingletons();
  });

  it('does not flag anything for a clean monotonic seq run', () => {
    const dispatch = vi.fn();

    handleSocketFrame(metaFrame(0), manager, dispatch);
    handleSocketFrame(metaFrame(1), manager, dispatch);
    handleSocketFrame(metaFrame(2), manager, dispatch);

    expect(dispatch).not.toHaveBeenCalled();
  });

  it('dispatches a synthetic audio_stream_error on a seq gap', () => {
    const dispatch = vi.fn();
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    handleSocketFrame(metaFrame(0), manager, dispatch);
    handleSocketFrame(metaFrame(1), manager, dispatch);
    // seq=3 skips seq=2 — a dropped frame.
    handleSocketFrame(metaFrame(3), manager, dispatch);

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'audio_stream_error',
        data: expect.objectContaining({ code: 'DESYNC', track_id: 1, stream_type: 'enhanced' }),
      })
    );
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it('detects a reordered (lower) seq as a desync too', () => {
    const dispatch = vi.fn();
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    handleSocketFrame(metaFrame(5), manager, dispatch);
    handleSocketFrame(metaFrame(4), manager, dispatch); // out of order

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'audio_stream_error', data: expect.objectContaining({ code: 'DESYNC' }) })
    );
  });

  it('resets tracking on a new stream_epoch instead of flagging a false desync', () => {
    const dispatch = vi.fn();

    handleSocketFrame(metaFrame(0), manager, dispatch);
    handleSocketFrame(metaFrame(1), manager, dispatch);
    // New stream (seek/track change): seq restarts at 0 under a new epoch.
    handleSocketFrame(metaFrame(0, { stream_epoch: 2 }), manager, dispatch);

    expect(dispatch).not.toHaveBeenCalled();
  });

  it('does not flag the very first frame of a stream (no prior expectation)', () => {
    const dispatch = vi.fn();

    handleSocketFrame(metaFrame(4), manager, dispatch); // stream starts mid-counter-ish, no baseline yet

    expect(dispatch).not.toHaveBeenCalled();
  });

  it('resyncs on the frame after a gap rather than re-firing every subsequent frame', () => {
    const dispatch = vi.fn();
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    handleSocketFrame(metaFrame(0), manager, dispatch);
    handleSocketFrame(metaFrame(2), manager, dispatch); // gap: fires once
    dispatch.mockClear();
    handleSocketFrame(metaFrame(3), manager, dispatch); // back on track

    expect(dispatch).not.toHaveBeenCalled();
  });

  it('still stashes pendingMeta normally even when a desync fires', () => {
    const dispatch = vi.fn();
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    handleSocketFrame(metaFrame(0), manager, dispatch);
    handleSocketFrame(metaFrame(5), manager, dispatch);

    expect(connState.pendingMeta).not.toBeNull();
    expect(connState.pendingMeta?.data.seq).toBe(5);
  });
});
