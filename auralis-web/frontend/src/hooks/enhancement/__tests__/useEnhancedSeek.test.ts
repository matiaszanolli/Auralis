/**
 * useEnhancedSeek subscribe-effect regression test (#4668).
 *
 * Sibling of useFingerprintStatus: the `seek_started` subscribe effect must
 * key off `wsContext.subscribe` (identity-stable across WS status
 * transitions), not the whole `wsContext` object.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { SEEK_RETRY_DELAY_MS, useEnhancedSeek } from '../useEnhancedSeek';
import type { StreamingCoreReturn } from '../useAudioStreamingCore';

function makeWsContext(isConnected: boolean, subscribe: ReturnType<typeof vi.fn>) {
  return {
    isConnected,
    connectionStatus: isConnected ? 'connected' : 'disconnected',
    subscribe,
    send: vi.fn(),
  } as any;
}

function makeCore(): StreamingCoreReturn {
  return {
    playbackEngineRef: { current: null },
    pcmBufferRef: { current: null },
    streamingMetadataRef: { current: null },
    pendingChunksRef: { current: [] },
    lastReceivedChunkIndexRef: { current: -1 },
  } as unknown as StreamingCoreReturn;
}

describe('useEnhancedSeek', () => {
  it('does not resubscribe when wsContext identity changes but subscribe does not (status flicker)', () => {
    const unsubscribe = vi.fn();
    const subscribe = vi.fn().mockReturnValue(unsubscribe);
    const currentTrackInfoRef = { current: null };
    const setIsSeeking = vi.fn();

    const { rerender } = renderHook(
      ({ ws }) =>
        useEnhancedSeek({
          wsContext: ws,
          core: makeCore(),
          currentTrackInfoRef,
          setIsSeeking,
        }),
      { initialProps: { ws: makeWsContext(true, subscribe) } }
    );
    // seek_started + error (#5885).
    expect(subscribe).toHaveBeenCalledTimes(2);

    rerender({ ws: makeWsContext(false, subscribe) });
    rerender({ ws: makeWsContext(true, subscribe) });
    rerender({ ws: makeWsContext(false, subscribe) });

    expect(subscribe).toHaveBeenCalledTimes(2);
    expect(unsubscribe).not.toHaveBeenCalled();
  });

  it('still clears isSeeking on seek_started after a disconnect/reconnect cycle', () => {
    let handler: (() => void) | undefined;
    const subscribe = vi.fn((type: string, h: () => void) => {
      if (type === 'seek_started') handler = h;
      return vi.fn();
    });
    const setIsSeeking = vi.fn();
    const currentTrackInfoRef = { current: null };

    const { rerender } = renderHook(
      ({ ws }) =>
        useEnhancedSeek({
          wsContext: ws,
          core: makeCore(),
          currentTrackInfoRef,
          setIsSeeking,
        }),
      { initialProps: { ws: makeWsContext(true, subscribe) } }
    );

    rerender({ ws: makeWsContext(false, subscribe) });
    rerender({ ws: makeWsContext(true, subscribe) });

    handler?.();

    expect(setIsSeeking).toHaveBeenCalledWith(false);
  });
});

// ---------------------------------------------------------------------------
// A rejected seek must not leave the client 'seeking' (#5885)
// ---------------------------------------------------------------------------

describe('useEnhancedSeek – rejected seek (#5885)', () => {
  function setup() {
    const handlers: Record<string, (message: any) => void> = {};
    const subscribe = vi.fn((type: string, h: (message: any) => void) => {
      handlers[type] = h;
      return vi.fn();
    });
    const ws = makeWsContext(true, subscribe);
    const setIsSeeking = vi.fn();
    const currentTrackInfoRef: { current: any } = { current: { trackId: 7 } };
    const { result } = renderHook(() =>
      useEnhancedSeek({ wsContext: ws, core: makeCore(), currentTrackInfoRef, setIsSeeking })
    );
    const reject = (error: string, command: string | null = 'seek') =>
      act(() => handlers.error!({ type: 'error', error, message: 'x', command }));
    const seekFrames = () => ws.send.mock.calls.filter(([m]: any[]) => m.type === 'seek').map(([m]: any[]) => m.data);
    return { result, handlers, setIsSeeking, currentTrackInfoRef, reject, seekFrames };
  }

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('clears isSeeking and re-sends the target once after a rate-limit rejection', () => {
    const { result, setIsSeeking, reject, seekFrames } = setup();
    act(() => result.current.seekTo(42));
    expect(setIsSeeking).toHaveBeenLastCalledWith(true);

    reject('rate_limit_exceeded');
    expect(setIsSeeking).toHaveBeenLastCalledWith(false);
    expect(seekFrames()).toHaveLength(1);

    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(seekFrames()).toEqual([
      { track_id: 7, position: 42 },
      { track_id: 7, position: 42 },
    ]);
    expect(setIsSeeking).toHaveBeenLastCalledWith(true);

    // A second rejection of the retry gives up instead of looping.
    reject('rate_limit_exceeded');
    expect(setIsSeeking).toHaveBeenLastCalledWith(false);
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 3));
    expect(seekFrames()).toHaveLength(2);
  });

  it('clears isSeeking without a retry when the seek handler itself failed', () => {
    const { result, setIsSeeking, reject, seekFrames } = setup();
    act(() => result.current.seekTo(10));
    reject('internal_error');
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS * 2));
    expect(setIsSeeking).toHaveBeenLastCalledWith(false);
    expect(seekFrames()).toHaveLength(1);
  });

  it('ignores errors for other commands and errors after the seek was acknowledged', () => {
    const { result, handlers, setIsSeeking, reject } = setup();
    act(() => result.current.seekTo(10));
    reject('rate_limit_exceeded', 'pause');
    reject('validation_error', null);
    expect(setIsSeeking).toHaveBeenLastCalledWith(true);

    act(() => handlers.seek_started!({ type: 'seek_started' }));
    setIsSeeking.mockClear();
    reject('rate_limit_exceeded');
    expect(setIsSeeking).not.toHaveBeenCalled();
  });

  it('drops the retry when a newer seek or a track change supersedes it', () => {
    const { result, reject, seekFrames, currentTrackInfoRef } = setup();
    act(() => result.current.seekTo(10));
    reject('rate_limit_exceeded');
    act(() => result.current.seekTo(20)); // newer target cancels the retry
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(seekFrames().map((d: any) => d.position)).toEqual([10, 20]);

    reject('rate_limit_exceeded');
    currentTrackInfoRef.current = { trackId: 8 };
    act(() => vi.advanceTimersByTime(SEEK_RETRY_DELAY_MS));
    expect(seekFrames().map((d: any) => d.position)).toEqual([10, 20]);
  });
});
