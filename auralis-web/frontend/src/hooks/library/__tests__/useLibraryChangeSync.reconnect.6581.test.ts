/**
 * Library caches are revalidated after a WebSocket reconnect (#6581).
 *
 * Change frames emitted while the socket was down (a --dev backend reload, the reconnect backoff,
 * the give-up state) are never replayed, and nothing re-invalidated the library caches on
 * reconnect, so the album grid, artist list, track list and artwork stayed on pre-outage data.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ReactNode } from 'react';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';

vi.mock('@/hooks/websocket/useWebSocketMessages', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/hooks/websocket/useWebSocketMessages')>()),
  useWebSocketMessages: vi.fn(),
}));

import { useReconnected } from '@/hooks/websocket/useReconnected';
import { useLibraryChangeSync } from '../useLibraryChangeSync';
import { _internal as artwork } from '../useArtworkUpdates';

let connected = true;

beforeEach(() => {
  connected = true;
  artwork.reset();
  vi.spyOn(WebSocketContextModule, 'useWebSocketContext').mockImplementation(
    () => ({ isConnected: connected }) as unknown as ReturnType<typeof WebSocketContextModule.useWebSocketContext>
  );
});

describe('useReconnected (#6581)', () => {
  function mount(onReconnect: () => void) {
    return renderHook(() => useReconnected(onReconnect));
  }

  it('fires once when the socket comes back after a drop', () => {
    const onReconnect = vi.fn();
    const { rerender } = mount(onReconnect);

    connected = false;
    rerender();
    expect(onReconnect).not.toHaveBeenCalled();

    connected = true;
    rerender();
    rerender();
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it('does not fire on the first connect, whose data the consumer fetched itself', () => {
    connected = false;
    const onReconnect = vi.fn();
    const { rerender } = mount(onReconnect);

    connected = true;
    rerender();
    expect(onReconnect).not.toHaveBeenCalled();

    connected = false;
    rerender();
    connected = true;
    rerender();
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it('calls the latest callback without re-running on a new inline function', () => {
    const first = vi.fn();
    const second = vi.fn();
    let callback = first;
    const { rerender } = renderHook(() => useReconnected(callback));

    callback = second;
    connected = false;
    rerender();
    connected = true;
    rerender();

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});

describe('useLibraryChangeSync on reconnect (#6581)', () => {
  function mountSync() {
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children);
    const { rerender } = renderHook(() => useLibraryChangeSync(), { wrapper });
    return { invalidate, rerender };
  }

  it('re-invalidates the album caches and refreshes the artwork after an outage', () => {
    artwork.revisionMap.set(7, 2);
    artwork.albumListeners.set(9, new Set());
    const { invalidate, rerender } = mountSync();

    connected = false;
    rerender();
    connected = true;
    rerender();

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['albums'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['album-fingerprint'] });
    expect(artwork.revisionMap.get(7)).toBe(3);
    expect(artwork.revisionMap.get(9)).toBe(1);
  });

  it('does nothing while the connection simply stays up', () => {
    const { invalidate, rerender } = mountSync();

    rerender();

    expect(invalidate).not.toHaveBeenCalled();
  });
});
