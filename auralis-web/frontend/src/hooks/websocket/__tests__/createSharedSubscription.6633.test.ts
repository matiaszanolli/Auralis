/**
 * createSharedSubscription (#6633): one WebSocket subscription for any number of mounted consumers,
 * the refcount useArtworkUpdates and useScanProgress each used to hand-roll.
 */

import { StrictMode, createElement, type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { createSharedSubscription } from '../useWebSocketMessages';
import type { WebSocketMessage } from '@/types/websocket';

vi.mock('@/contexts/WebSocketContext');

describe('createSharedSubscription', () => {
  let subscribe: ReturnType<typeof vi.fn>;
  let unsubscribe: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    unsubscribe = vi.fn();
    subscribe = vi.fn((_type: string, _handler: (m: WebSocketMessage) => void) => unsubscribe);
    vi.mocked(useWebSocketContext).mockReturnValue({ subscribe } as any);
  });

  it('subscribes once for many consumers and detaches when the last one leaves', () => {
    const onLastRelease = vi.fn();
    const shared = createSharedSubscription(['scan_progress', 'scan_complete'], vi.fn(), onLastRelease);

    const first = renderHook(() => shared.use());
    const second = renderHook(() => shared.use());
    expect(subscribe).toHaveBeenCalledTimes(2); // one per type, not per consumer
    expect(shared.refCount).toBe(2);

    first.unmount();
    expect(unsubscribe).not.toHaveBeenCalled();
    expect(onLastRelease).not.toHaveBeenCalled();

    second.unmount();
    expect(unsubscribe).toHaveBeenCalledTimes(2);
    expect(onLastRelease).toHaveBeenCalledTimes(1);
    expect(shared.refCount).toBe(0);
  });

  it('delivers frames to the handler it was created with', () => {
    const handler = vi.fn();
    const shared = createSharedSubscription(['artwork_updated'], handler);
    renderHook(() => shared.use());

    const delivered = subscribe.mock.calls[0][1];
    delivered({ type: 'artwork_updated', data: { album_id: 7 } });

    expect(handler).toHaveBeenCalledWith({ type: 'artwork_updated', data: { album_id: 7 } });
  });

  it("survives StrictMode's double mount with one live subscription", () => {
    const shared = createSharedSubscription(['artwork_updated'], vi.fn());
    const wrapper = ({ children }: { children: ReactNode }) => createElement(StrictMode, null, children);

    renderHook(() => shared.use(), { wrapper });

    expect(shared.refCount).toBe(1);
    expect(subscribe.mock.calls.length - unsubscribe.mock.calls.length).toBe(1);
  });

  it('keeps separate counts per instance', () => {
    const a = createSharedSubscription(['scan_progress'], vi.fn());
    const b = createSharedSubscription(['artwork_updated'], vi.fn());

    renderHook(() => a.use());

    expect(a.refCount).toBe(1);
    expect(b.refCount).toBe(0);
  });
});
