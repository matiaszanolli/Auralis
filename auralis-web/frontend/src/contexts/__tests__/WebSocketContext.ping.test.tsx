/**
 * WebSocketContext - Server Ping/Pong Heartbeat Reply (#4406)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The backend heartbeat loop sends `{"type":"ping"}` every ~30s and arms a
 * pending-pong that only a client `{"type":"pong"}` frame clears; if none
 * arrives within the timeout it force-closes the socket (~60s) with
 * `1001 Heartbeat timeout`. The client previously only sent an unsolicited
 * `{"type":"heartbeat"}` (routed to mark_alive, which is_stale never reads), so
 * the armed ping never cleared and every socket was torn down each minute.
 *
 * WebSocketContext must now reply `pong` to an incoming server `ping` and must
 * NOT leak that internal protocol frame to app subscribers.
 *
 * WIRING: the global test setup (setup.ts) auto-mocks WebSocketContext; we undo
 * that here so the REAL message handler runs, mocking only the transport layer.
 */

// Undo the global mock so the real implementation is loaded and tested.
vi.unmock('../WebSocketContext');

// Mock only the transport layer (WebSocketManager).
vi.mock('../../utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import { ReactNode } from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  WebSocketProvider,
  useWebSocketContext,
  resetWebSocketSingletons,
} from '../WebSocketContext';
import type { AnyWebSocketMessage, WebSocketMessage } from '../WebSocketContext';
import { WebSocketManager } from '../../utils/errorHandling';

type WSEvent = 'open' | 'close' | 'error' | 'message';

interface MockWSManager {
  isConnected: ReturnType<typeof vi.fn>;
  connect: ReturnType<typeof vi.fn>;
  on: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  emit: (event: WSEvent, arg?: any) => void;
}

function makeMockManager(): MockWSManager {
  const handlers: Partial<Record<WSEvent, Function>> = {};
  const mgr: MockWSManager = {
    isConnected: vi.fn().mockReturnValue(true),
    connect: vi.fn().mockResolvedValue(undefined),
    on: vi.fn((event: WSEvent, handler: Function) => {
      handlers[event] = handler;
    }),
    send: vi.fn(),
    close: vi.fn(),
    emit(event, arg?) {
      handlers[event]?.(arg);
    },
  };
  return mgr;
}

function wrapper({ children }: { children: ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

type Msg = AnyWebSocketMessage | WebSocketMessage;

describe('WebSocketContext - server ping/pong reply (#4406)', () => {
  let mockMgr: MockWSManager;

  beforeEach(() => {
    resetWebSocketSingletons();
    mockMgr = makeMockManager();
    vi.mocked(WebSocketManager).mockImplementation(function () { return mockMgr as any; });
  });

  afterEach(() => {
    resetWebSocketSingletons();
    vi.clearAllMocks();
  });

  async function setup() {
    const ctx = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { mockMgr.emit('open'); });
    // Drain the connect-time frames (enhancement_settings / re-issue) so the
    // assertions below only see what the ping triggers.
    mockMgr.send.mockClear();
    return ctx;
  }

  it('replies with a pong frame when the server sends a ping', async () => {
    await setup();

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify({ type: 'ping' }) });
    });

    expect(mockMgr.send).toHaveBeenCalledWith(JSON.stringify({ type: 'pong' }));
  });

  it('never dispatches the internal ping frame to app subscribers', async () => {
    const { result } = await setup();

    const seen: Msg[] = [];
    await act(async () => {
      result.current.subscribeAll((m) => seen.push(m));
    });

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify({ type: 'ping' }) });
    });

    // The ping is answered and swallowed — no subscriber ever sees it.
    expect(seen).toHaveLength(0);
    expect(seen.some((m) => (m.type as string) === 'ping')).toBe(false);
  });
});
