/**
 * useFingerprintStatus subscribe-effect regression test (#4668).
 *
 * The subscribe effect must key off `wsContext.subscribe` (identity-stable
 * across WS status transitions), not the whole `wsContext` object (whose
 * memoized identity changes on every connect/disconnect/reconnect/error).
 */

import { describe, it, expect, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useFingerprintStatus } from '../useFingerprintStatus';

function makeWsContext(isConnected: boolean, subscribe: ReturnType<typeof vi.fn>) {
  return { isConnected, connectionStatus: isConnected ? 'connected' : 'disconnected', subscribe } as any;
}

describe('useFingerprintStatus', () => {
  it('does not resubscribe when wsContext identity changes but subscribe does not (status flicker)', () => {
    const unsubscribe = vi.fn();
    const subscribe = vi.fn().mockReturnValue(unsubscribe);

    const { rerender } = renderHook(
      ({ ws }) => useFingerprintStatus(ws),
      { initialProps: { ws: makeWsContext(true, subscribe) } }
    );
    expect(subscribe).toHaveBeenCalledTimes(1);

    // Simulate connect -> disconnect -> reconnect: a new wsContext object each
    // time (as WebSocketContext's useMemo produces), but the SAME `subscribe`
    // function reference throughout.
    rerender({ ws: makeWsContext(false, subscribe) });
    rerender({ ws: makeWsContext(true, subscribe) });
    rerender({ ws: makeWsContext(false, subscribe) });

    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(unsubscribe).not.toHaveBeenCalled();
  });

  it('resubscribes when subscribe itself changes identity (genuine reconnect)', () => {
    const unsubscribeA = vi.fn();
    const subscribeA = vi.fn().mockReturnValue(unsubscribeA);
    const subscribeB = vi.fn().mockReturnValue(vi.fn());

    const { rerender } = renderHook(
      ({ ws }) => useFingerprintStatus(ws),
      { initialProps: { ws: makeWsContext(true, subscribeA) } }
    );
    expect(subscribeA).toHaveBeenCalledTimes(1);

    rerender({ ws: makeWsContext(true, subscribeB) });

    expect(unsubscribeA).toHaveBeenCalledTimes(1);
    expect(subscribeB).toHaveBeenCalledTimes(1);
  });

  it('still receives fingerprint_progress messages after a disconnect/reconnect cycle', () => {
    let handler: ((m: unknown) => void) | undefined;
    const subscribe = vi.fn((_type: string, h: (m: unknown) => void) => {
      handler = h;
      return vi.fn();
    });

    const { result, rerender } = renderHook(
      ({ ws }) => useFingerprintStatus(ws),
      { initialProps: { ws: makeWsContext(true, subscribe) } }
    );

    rerender({ ws: makeWsContext(false, subscribe) });
    rerender({ ws: makeWsContext(true, subscribe) });

    act(() => {
      handler?.({ data: { status: 'analyzing', message: 'Analyzing…' } });
    });

    expect(result.current.fingerprintStatus).toBe('analyzing');
    expect(result.current.fingerprintMessage).toBe('Analyzing…');
  });
});
