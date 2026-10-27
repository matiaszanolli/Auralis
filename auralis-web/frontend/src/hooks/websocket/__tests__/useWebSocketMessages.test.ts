/**
 * useWebSocketMessages Hook Tests
 *
 * The context-backed replacement for the retired useWebSocketSubscription
 * singleton (#4380). Subscribes to each message type via WebSocketContext and
 * unsubscribes on unmount.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useMessageSubscriptions, useWebSocketMessages } from '../useWebSocketMessages';
import type { WebSocketErrorMessage, WebSocketMessage } from '@/types/websocket';

vi.mock('@/contexts/WebSocketContext');

describe('useWebSocketMessages', () => {
  let subscribe: ReturnType<typeof vi.fn>;
  const unsubscribes: ReturnType<typeof vi.fn>[] = [];

  beforeEach(() => {
    vi.clearAllMocks();
    unsubscribes.length = 0;
    subscribe = vi.fn((_type: string, _handler: (m: WebSocketMessage) => void) => {
      const unsub = vi.fn();
      unsubscribes.push(unsub);
      return unsub;
    });
    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe } as any);
  });

  it('subscribes to each message type in the array', () => {
    renderHook(() => useWebSocketMessages(['scan_progress', 'scan_complete'], () => {}));

    expect(subscribe).toHaveBeenCalledTimes(2);
    const types = subscribe.mock.calls.map((c) => c[0]).sort();
    expect(types).toEqual(['scan_complete', 'scan_progress']);
  });

  it('routes delivered messages to the latest callback', () => {
    const received: WebSocketErrorMessage[] = [];
    const { rerender } = renderHook(
      ({ cb }) => useWebSocketMessages(['error'], cb),
      { initialProps: { cb: (m: WebSocketErrorMessage) => received.push(m) } }
    );

    const handler = subscribe.mock.calls[0][1] as (m: WebSocketErrorMessage) => void;
    const msg: WebSocketErrorMessage = { type: 'error', error: 'rate_limit_exceeded', message: 'slow down' };
    handler(msg);
    expect(received).toEqual([msg]);

    // Swapping the callback without changing types must NOT resubscribe, and
    // the new callback must receive subsequent messages (ref-stable delegation).
    const received2: WebSocketErrorMessage[] = [];
    rerender({ cb: (m: WebSocketErrorMessage) => received2.push(m) });
    handler(msg);
    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(received2).toEqual([msg]);
  });

  it('unsubscribes every type on unmount', () => {
    const { unmount } = renderHook(() =>
      useWebSocketMessages(['a', 'b'] as any, () => {})
    );
    expect(unsubscribes).toHaveLength(2);

    unmount();
    for (const unsub of unsubscribes) {
      expect(unsub).toHaveBeenCalledTimes(1);
    }
  });

  it('does not resubscribe when the type array is reordered (order-independent key)', () => {
    const { rerender } = renderHook(
      ({ types }) => useWebSocketMessages(types, () => {}),
      { initialProps: { types: ['a', 'b'] as any } }
    );
    expect(subscribe).toHaveBeenCalledTimes(2);

    rerender({ types: ['b', 'a'] as any });
    // Same set, reordered → no teardown/rebuild.
    expect(subscribe).toHaveBeenCalledTimes(2);
  });
});

describe('useMessageSubscriptions (the shared core, #5789)', () => {
  const makeSubscribe = () => {
    const unsubscribes: ReturnType<typeof vi.fn>[] = [];
    const subscribe = vi.fn((_type: string, _handler: (m: WebSocketMessage) => void) => {
      const unsub = vi.fn();
      unsubscribes.push(unsub);
      return unsub;
    });
    return { subscribe, unsubscribes };
  };
  const msg = (type: string) => ({ type, data: {} }) as unknown as WebSocketMessage;

  it('subscribes once per key and routes each type to its own handler', () => {
    const { subscribe } = makeSubscribe();
    const a = vi.fn();
    const b = vi.fn();
    renderHook(() => useMessageSubscriptions(subscribe as any, { scan_progress: a, scan_complete: b } as any));

    expect(subscribe).toHaveBeenCalledTimes(2);
    for (const [type, handler] of subscribe.mock.calls) handler(msg(type));
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    expect(a.mock.calls[0][0].type).toBe('scan_progress');
  });

  it('does not resubscribe when only handler identities change, and calls the latest one', () => {
    const { subscribe } = makeSubscribe();
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(
      ({ h }) => useMessageSubscriptions(subscribe as any, { scan_progress: h } as any),
      { initialProps: { h: first } }
    );
    rerender({ h: second });

    expect(subscribe).toHaveBeenCalledTimes(1);
    subscribe.mock.calls[0][1](msg('scan_progress'));
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('resubscribes only when `subscribe` itself changes, and unsubscribes on unmount', () => {
    const A = makeSubscribe();
    const B = makeSubscribe();
    const { rerender, unmount } = renderHook(
      ({ sub }) => useMessageSubscriptions(sub as any, { error: () => {} } as any),
      { initialProps: { sub: A.subscribe } }
    );
    rerender({ sub: B.subscribe });
    expect(A.unsubscribes[0]).toHaveBeenCalledTimes(1);
    expect(B.subscribe).toHaveBeenCalledTimes(1);

    unmount();
    expect(B.unsubscribes[0]).toHaveBeenCalledTimes(1);
  });

  it('ignores a message type whose handler was removed on a later render', () => {
    const { subscribe } = makeSubscribe();
    const a = vi.fn();
    const { rerender } = renderHook(
      ({ handlers }) => useMessageSubscriptions(subscribe as any, handlers as any),
      { initialProps: { handlers: { error: a } as Record<string, () => void> } }
    );
    rerender({ handlers: {} });
    // Key changed -> torn down; a stale delivery must not reach the old handler.
    subscribe.mock.calls[0][1](msg('error'));
    expect(a).not.toHaveBeenCalled();
  });
});
