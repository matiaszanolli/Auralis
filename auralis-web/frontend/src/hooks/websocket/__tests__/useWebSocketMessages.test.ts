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
import { useWebSocketMessages } from '../useWebSocketMessages';
import type { WebSocketMessage } from '@/types/websocket';

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
    const received: WebSocketMessage[] = [];
    const { rerender } = renderHook(
      ({ cb }) => useWebSocketMessages(['error'], cb),
      { initialProps: { cb: (m: WebSocketMessage) => received.push(m) } }
    );

    const handler = subscribe.mock.calls[0][1] as (m: WebSocketMessage) => void;
    const msg = { type: 'error', data: {} } as unknown as WebSocketMessage;
    handler(msg);
    expect(received).toEqual([msg]);

    // Swapping the callback without changing types must NOT resubscribe, and
    // the new callback must receive subsequent messages (ref-stable delegation).
    const received2: WebSocketMessage[] = [];
    rerender({ cb: (m: WebSocketMessage) => received2.push(m) });
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
