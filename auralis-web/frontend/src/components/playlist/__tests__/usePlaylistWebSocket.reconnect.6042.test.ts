/**
 * usePlaylistWebSocket re-reads the list when the socket reconnects (#6042)
 *
 * playlist_* events missed while the connection was down are never replayed, so a list that
 * changed in the meantime stayed stale until the next event or a reload.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

const { ws } = vi.hoisted(() => ({
  ws: { isConnected: true, subscribe: undefined as unknown },
}));

vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ws,
}));

import { usePlaylistWebSocket } from '../usePlaylistWebSocket';

function mount(connected: boolean) {
  ws.isConnected = connected;
  ws.subscribe = vi.fn(() => () => {});
  const onPlaylistsRefresh = vi.fn();
  const handlers = {
    onPlaylistCreated: vi.fn(),
    onPlaylistUpdated: vi.fn(),
    onPlaylistDeleted: vi.fn(),
    onPlaylistsRefresh,
  };
  const hook = renderHook(() => usePlaylistWebSocket(handlers));
  return { hook, onPlaylistsRefresh };
}

describe('usePlaylistWebSocket reconnect resync', () => {
  it('does not refresh just because it mounted connected', () => {
    const { onPlaylistsRefresh } = mount(true);

    expect(onPlaylistsRefresh).not.toHaveBeenCalled();
  });

  it('refreshes once when the connection comes back after a drop', () => {
    const { hook, onPlaylistsRefresh } = mount(true);

    ws.isConnected = false;
    hook.rerender();
    expect(onPlaylistsRefresh).not.toHaveBeenCalled();

    ws.isConnected = true;
    hook.rerender();
    expect(onPlaylistsRefresh).toHaveBeenCalledTimes(1);

    hook.rerender();
    expect(onPlaylistsRefresh).toHaveBeenCalledTimes(1);
  });

  it('refreshes when it mounts while disconnected and the socket then connects', () => {
    const { hook, onPlaylistsRefresh } = mount(false);

    ws.isConnected = true;
    hook.rerender();

    expect(onPlaylistsRefresh).toHaveBeenCalledTimes(1);
  });
});
