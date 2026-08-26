/**
 * useEnhancedSeek subscribe-effect regression test (#4668).
 *
 * Sibling of useFingerprintStatus: the `seek_started` subscribe effect must
 * key off `wsContext.subscribe` (identity-stable across WS status
 * transitions), not the whole `wsContext` object.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useEnhancedSeek } from '../useEnhancedSeek';
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
    expect(subscribe).toHaveBeenCalledTimes(1);

    rerender({ ws: makeWsContext(false, subscribe) });
    rerender({ ws: makeWsContext(true, subscribe) });
    rerender({ ws: makeWsContext(false, subscribe) });

    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(unsubscribe).not.toHaveBeenCalled();
  });

  it('still clears isSeeking on seek_started after a disconnect/reconnect cycle', () => {
    let handler: (() => void) | undefined;
    const subscribe = vi.fn((_type: string, h: () => void) => {
      handler = h;
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
