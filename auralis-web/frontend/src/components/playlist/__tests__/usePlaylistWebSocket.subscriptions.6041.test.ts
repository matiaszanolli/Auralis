/**
 * usePlaylistWebSocket subscribes once per message type and survives inline handlers (#6041)
 *
 * It opened its own subscribe() calls in an effect that listed the four callbacks as dependencies, so a
 * caller passing fresh closures every render re-subscribed all three types every render. It now goes
 * through useMessageSubscriptions, which reads handlers through a ref.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

type Handler = (message: unknown) => void;

const { ws } = vi.hoisted(() => ({
  ws: { isConnected: true, subscribe: undefined as unknown },
}));

vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ws,
}));

import { usePlaylistWebSocket } from '../usePlaylistWebSocket';

function mountWithInlineHandlers(spies: { created: () => void; deleted: (id: number) => void }) {
  const handlers: Record<string, Handler> = {};
  const unsubscribe = vi.fn();
  ws.subscribe = vi.fn((type: string, handler: Handler) => {
    handlers[type] = handler;
    return unsubscribe;
  });
  const hook = renderHook(() =>
    usePlaylistWebSocket({
      onPlaylistCreated: () => spies.created(), // a fresh closure on every render
      onPlaylistUpdated: () => {},
      onPlaylistDeleted: (id) => spies.deleted(id),
      onPlaylistsRefresh: () => {},
    })
  );
  return { hook, handlers, unsubscribe };
}

describe('usePlaylistWebSocket subscriptions', () => {
  it('subscribes once per message type and not again when rerendered with new closures', () => {
    const { hook } = mountWithInlineHandlers({ created: vi.fn(), deleted: vi.fn() });
    expect((ws.subscribe as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]).sort()).toEqual([
      'playlist_created',
      'playlist_deleted',
      'playlist_updated',
    ]);

    hook.rerender();
    hook.rerender();

    expect(ws.subscribe).toHaveBeenCalledTimes(3);
  });

  it('delivers to the latest handler, and unsubscribes everything on unmount', () => {
    const created = vi.fn();
    const deleted = vi.fn();
    const { hook, handlers, unsubscribe } = mountWithInlineHandlers({ created, deleted });

    handlers.playlist_created({ type: 'playlist_created', data: {} });
    handlers.playlist_deleted({ type: 'playlist_deleted', data: { playlist_id: 9 } });
    expect(created).toHaveBeenCalledTimes(1);
    expect(deleted).toHaveBeenCalledWith(9);

    hook.unmount();

    expect(unsubscribe).toHaveBeenCalledTimes(3);
  });
});
