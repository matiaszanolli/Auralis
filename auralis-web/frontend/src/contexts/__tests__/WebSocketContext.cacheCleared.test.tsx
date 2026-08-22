/**
 * WebSocketContext — `cache_cleared` delivery (#4585)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `POST /api/cache/clear` broadcasts `{type: 'cache_cleared', data: {...}}`,
 * but the type was never modelled on the frontend. `dispatchMessage` resolves
 * handlers from a `Map<type, Set<handler>>`, so an unregistered type resolved
 * to an empty set and the frame was discarded with no warning — the unfinished
 * half of #3545 (the `{type, data}` envelope half was fixed; the registration
 * half was not).
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
} from '../WebSocketContext';
import type { AnyWebSocketMessage, WebSocketMessage } from '../WebSocketContext';
import { WebSocketManager } from '@/utils/errorHandling';
import { ALL_MESSAGE_TYPES } from '@/types/websocket';

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

type Msg = AnyWebSocketMessage | WebSocketMessage;

const CACHE_CLEARED_FRAME = {
  type: 'cache_cleared',
  data: { message: 'All caches cleared' },
};

describe('WebSocketContext - cache_cleared delivery (#4585)', () => {
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
    return ctx;
  }

  it('registers cache_cleared as a first-class message type', () => {
    expect(ALL_MESSAGE_TYPES).toContain('cache_cleared');
  });

  it('delivers a cache_cleared frame to a type-scoped subscriber', async () => {
    const { result } = await setup();

    const seen: Msg[] = [];
    await act(async () => {
      result.current.subscribe('cache_cleared', (m) => seen.push(m));
    });

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(CACHE_CLEARED_FRAME) });
    });

    // Before the fix this array stayed empty — the frame was dropped silently.
    expect(seen).toHaveLength(1);
    expect(seen[0].type).toBe('cache_cleared');
    expect((seen[0] as { data: { message: string } }).data.message).toBe('All caches cleared');
  });

  it('is not classified as an unknown message', async () => {
    const { result } = await setup();

    const seen: Msg[] = [];
    await act(async () => {
      result.current.subscribeAll((m) => seen.push(m));
    });

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(CACHE_CLEARED_FRAME) });
    });

    expect(seen.some((m) => m.type === 'cache_cleared')).toBe(true);
  });
});
