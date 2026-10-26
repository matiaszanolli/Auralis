/**
 * useFingerprintStatus subscribe-effect regression test (#4668).
 *
 * The subscribe effect must key off `wsContext.subscribe` (identity-stable
 * across WS status transitions), not the whole `wsContext` object (whose
 * memoized identity changes on every connect/disconnect/reconnect/error).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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

  it("ignores a superseded track's fingerprint_progress after a track switch (#5380)", () => {
    let handler: ((m: unknown) => void) | undefined;
    const subscribe = vi.fn((_type: string, h: (m: unknown) => void) => {
      handler = h;
      return vi.fn();
    });
    const { result } = renderHook(() => useFingerprintStatus(makeWsContext(true, subscribe)));

    act(() => result.current.resetFingerprint(1));
    act(() => {
      handler?.({ data: { track_id: 1, status: 'analyzing', message: 'Analyzing track 1' } });
    });
    expect(result.current.fingerprintStatus).toBe('analyzing');

    // Skip to track 2; track 1's message was already in flight and lands late.
    act(() => result.current.resetFingerprint(2));
    act(() => {
      handler?.({ data: { track_id: 1, status: 'complete', message: 'Track 1 done' } });
    });
    expect(result.current.fingerprintStatus).toBe('idle');
    expect(result.current.fingerprintMessage).toBeNull();

    // The current track's own progress still applies.
    act(() => {
      handler?.({ data: { track_id: 2, status: 'cached', message: 'Track 2 cached' } });
    });
    expect(result.current.fingerprintStatus).toBe('cached');
    expect(result.current.fingerprintMessage).toBe('Track 2 cached');
  });

  describe('complete auto-clear timer (#6102)', () => {
    function setup() {
      let handler: ((m: unknown) => void) | undefined;
      const subscribe = vi.fn((_type: string, h: (m: unknown) => void) => {
        handler = h;
        return vi.fn();
      });
      const hook = renderHook(() => useFingerprintStatus(makeWsContext(true, subscribe)));
      return { ...hook, send: (data: object) => act(() => handler?.({ data })) };
    }

    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("A's timer does not clear B's analyzing status after resetFingerprint", () => {
      const { result, send } = setup();
      act(() => result.current.resetFingerprint(1));
      send({ track_id: 1, status: 'complete', message: 'A done' });

      act(() => result.current.resetFingerprint(2));
      send({ track_id: 2, status: 'analyzing', message: 'Analyzing B' });
      act(() => vi.advanceTimersByTime(2000));

      expect(result.current.fingerprintStatus).toBe('analyzing');
      expect(result.current.fingerprintMessage).toBe('Analyzing B');
    });

    it('a non-complete progress frame cancels a pending auto-clear', () => {
      const { result, send } = setup();
      send({ status: 'complete', message: 'done' });
      send({ status: 'analyzing', message: 'next' });
      act(() => vi.advanceTimersByTime(2000));

      expect(result.current.fingerprintStatus).toBe('analyzing');
    });

    it('still auto-clears a complete status after 2 s', () => {
      const { result, send } = setup();
      send({ status: 'complete', message: 'done' });
      act(() => vi.advanceTimersByTime(2000));

      expect(result.current.fingerprintStatus).toBe('idle');
      expect(result.current.fingerprintMessage).toBeNull();
    });
  });
});
