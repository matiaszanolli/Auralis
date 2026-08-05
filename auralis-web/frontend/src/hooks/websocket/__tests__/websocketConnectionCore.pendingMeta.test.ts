/**
 * Regression tests for #4782: audio_chunk_meta/PCM binary frame pair is not
 * atomic, permanently desyncing chunk pairing.
 *
 * The backend sends an `audio_chunk_meta` JSON frame followed by a binary
 * PCM frame. If the metadata send succeeds but the binary send then fails,
 * the client's `pendingMeta` is left set with nothing to clear it — the
 * next binary frame that arrives (from a later, unrelated chunk) gets
 * silently fused with the stale metadata. Every live chunk-delivery path
 * on the backend sends `audio_stream_error` whenever a chunk fails to
 * fully deliver, so `handleSocketFrame` treats that as the signal to drop
 * whatever frame pairing was in flight.
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

function binaryEvent(): MessageEvent {
  return { data: new ArrayBuffer(8) } as MessageEvent;
}

describe('websocketConnectionCore pendingMeta / audio_stream_error (#4782)', () => {
  beforeEach(() => {
    resetConnectionSingletons();
  });

  it('stashes audio_chunk_meta in pendingMeta without dispatching it', () => {
    const dispatch = vi.fn();

    handleSocketFrame(
      textEvent({ type: 'audio_chunk_meta', data: { seq: 1, sample_count: 4 } }),
      manager,
      dispatch
    );

    expect(connState.pendingMeta).not.toBeNull();
    expect(dispatch).not.toHaveBeenCalled();
  });

  it('fuses a binary frame with pendingMeta and dispatches audio_chunk, then clears pendingMeta', () => {
    const dispatch = vi.fn();
    handleSocketFrame(
      textEvent({ type: 'audio_chunk_meta', data: { seq: 1, sample_count: 4 } }),
      manager,
      dispatch
    );

    handleSocketFrame(binaryEvent(), manager, dispatch);

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'audio_chunk', data: expect.objectContaining({ seq: 1 }) })
    );
    expect(connState.pendingMeta).toBeNull();
  });

  it('clears a stale pendingMeta when audio_stream_error arrives (the #4782 fix)', () => {
    const dispatch = vi.fn();

    // Simulates: meta for chunk N sent successfully...
    handleSocketFrame(
      textEvent({ type: 'audio_chunk_meta', data: { seq: 7, sample_count: 4 } }),
      manager,
      dispatch
    );
    expect(connState.pendingMeta).not.toBeNull();

    // ...but the binary frame after it never arrives — instead the backend
    // reports the delivery failure.
    handleSocketFrame(
      textEvent({ type: 'audio_stream_error', data: { track_id: 1, error: 'boom' } }),
      manager,
      dispatch
    );

    expect(connState.pendingMeta).toBeNull();
  });

  it('does NOT fuse a later, unrelated binary frame with the stale meta after an error (regression)', () => {
    const dispatch = vi.fn();
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    // Chunk N: meta arrives, binary fails -> stream reports an error.
    handleSocketFrame(
      textEvent({ type: 'audio_chunk_meta', data: { seq: 7, sample_count: 4 } }),
      manager,
      dispatch
    );
    handleSocketFrame(
      textEvent({ type: 'audio_stream_error', data: { track_id: 1, error: 'boom' } }),
      manager,
      dispatch
    );
    dispatch.mockClear();

    // A later, unrelated binary frame arrives with no preceding meta (its
    // own audio_chunk_meta hasn't arrived yet, or this is simulating the
    // desync itself if the fix were absent).
    handleSocketFrame(binaryEvent(), manager, dispatch);

    // Must NOT be silently fused with chunk N's stale seq=7 metadata.
    expect(dispatch).not.toHaveBeenCalledWith(
      expect.objectContaining({ data: expect.objectContaining({ seq: 7 }) })
    );
    warnSpy.mockRestore();
  });

  it('is a no-op when audio_stream_error arrives with no pending meta', () => {
    const dispatch = vi.fn();

    handleSocketFrame(
      textEvent({ type: 'audio_stream_error', data: { track_id: 1, error: 'boom' } }),
      manager,
      dispatch
    );

    expect(connState.pendingMeta).toBeNull();
    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'audio_stream_error' })
    );
  });
});
