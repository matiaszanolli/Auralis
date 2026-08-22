/**
 * WebSocketContext — unregistered message types are no longer silent (#4617)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `dispatchMessage` resolves handlers from a `Map<type, Set<handler>>`. A type
 * that was never added to `ALL_MESSAGE_TYPES` can have no subscribers by
 * construction — `subscribe()` is typed on `WebSocketMessageType`, so the map
 * can never hold that key — and the frame was dropped with no trace at all.
 * That silence is how `cache_cleared` stayed dead from #3545 until #4585.
 *
 * A dev-mode warning makes the next omission visible on the first frame.
 *
 * WIRING: the global test setup auto-mocks WebSocketContext; undo that so the
 * real dispatcher runs, and mock only the transport.
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
  resetUnregisteredTypeWarnings,
} from '../WebSocketContext';
import { WebSocketManager } from '@/utils/errorHandling';

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
  return {
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
}

function wrapper({ children }: { children: ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

describe('WebSocketContext - unregistered message types (#4617)', () => {
  let mockMgr: MockWSManager;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    resetWebSocketSingletons();
    resetUnregisteredTypeWarnings();
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    mockMgr = makeMockManager();
    vi.mocked(WebSocketManager).mockImplementation(function () { return mockMgr as any; });
  });

  afterEach(() => {
    resetWebSocketSingletons();
    resetUnregisteredTypeWarnings();
    warnSpy.mockRestore();
    vi.clearAllMocks();
  });

  async function setup() {
    const ctx = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { mockMgr.emit('open'); });
    return ctx;
  }

  async function deliver(frame: Record<string, unknown>) {
    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(frame) });
    });
  }

  const warnings = () =>
    warnSpy.mock.calls.map((c) => String(c[0])).filter((m) => m.includes('[WebSocket]'));

  it('warns once for a type that is on no registry', async () => {
    await setup();
    await deliver({ type: 'totally_new_backend_event', data: {} });

    expect(warnings()).toHaveLength(1);
    expect(warnings()[0]).toContain('totally_new_backend_event');
    expect(warnings()[0]).toContain('ALL_MESSAGE_TYPES');
  });

  it('does not repeat the warning for every frame of the same type', async () => {
    await setup();
    await deliver({ type: 'totally_new_backend_event', data: {} });
    await deliver({ type: 'totally_new_backend_event', data: {} });
    await deliver({ type: 'totally_new_backend_event', data: {} });

    expect(warnings()).toHaveLength(1);
  });

  it('stays silent for a registered type with no current subscriber', async () => {
    await setup();
    // Registered, but nothing is subscribed right now — a normal situation,
    // not a contract gap.
    await deliver({ type: 'cache_cleared', data: { message: 'All caches cleared' } });

    expect(warnings()).toHaveLength(0);
  });

  it('stays silent for deliberately-internal control frames', async () => {
    await setup();
    // `audio_chunk_meta` is fused with the following binary frame inside the
    // connection hook and is intentionally absent from the public union (#4167).
    await deliver({ type: 'pong' });

    expect(warnings()).toHaveLength(0);
  });
});
