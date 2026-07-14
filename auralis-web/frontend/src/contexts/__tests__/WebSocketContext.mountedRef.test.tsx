/**
 * WebSocketContext - mountedRef reset after StrictMode remount (#4436)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `mountedRef` is set to false in the mount-effect cleanup. Under React 18
 * StrictMode (dev) the mount→cleanup→remount cycle previously left it false
 * forever, so the re-subscribed open/close/error handlers (all gated on
 * mountedRef) never updated isConnected/connectionStatus again. The mount
 * effect now resets it to true, so status updates resume after remount.
 */

// Undo the global mock so the real implementation runs.
vi.unmock('../WebSocketContext');

// Mock only the transport layer.
vi.mock('../../utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import { ReactNode, StrictMode } from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  WebSocketProvider,
  useWebSocketContext,
  resetWebSocketSingletons,
} from '../WebSocketContext';
import { WebSocketManager } from '../../utils/errorHandling';

type WSEvent = 'open' | 'close' | 'error' | 'message';

function makeMockManager() {
  const handlers: Partial<Record<WSEvent, Function>> = {};
  return {
    isConnected: vi.fn().mockReturnValue(true),
    connect: vi.fn().mockResolvedValue(undefined),
    on: vi.fn((event: WSEvent, handler: Function) => {
      handlers[event] = handler;
    }),
    send: vi.fn(),
    close: vi.fn(),
    emit(event: WSEvent, arg?: any) {
      handlers[event]?.(arg);
    },
  };
}

describe('WebSocketContext - mountedRef reset (#4436)', () => {
  let mockMgr: ReturnType<typeof makeMockManager>;

  beforeEach(() => {
    resetWebSocketSingletons();
    mockMgr = makeMockManager();
    vi.mocked(WebSocketManager).mockImplementation(function () { return mockMgr as any; });
  });

  afterEach(() => {
    resetWebSocketSingletons();
    vi.clearAllMocks();
  });

  it('updates connection status from the open handler after a StrictMode remount', async () => {
    // StrictMode double-invokes the mount effect (setup → cleanup → setup),
    // exercising the exact mount→cleanup→remount cycle that stranded mountedRef.
    const wrapper = ({ children }: { children: ReactNode }) => (
      <StrictMode>
        <WebSocketProvider>{children}</WebSocketProvider>
      </StrictMode>
    );

    const { result } = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });

    // Backend accepts the connection AFTER the StrictMode remount.
    await act(async () => { mockMgr.emit('open'); });

    // With mountedRef stranded at false this stays 'disconnected'/false.
    expect(result.current.isConnected).toBe(true);
    expect(result.current.connectionStatus).toBe('connected');
  });

  it('still reflects a later close after remount', async () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <StrictMode>
        <WebSocketProvider>{children}</WebSocketProvider>
      </StrictMode>
    );

    const { result } = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });

    await act(async () => { mockMgr.emit('open'); });
    expect(result.current.isConnected).toBe(true);

    await act(async () => { mockMgr.emit('close'); });
    expect(result.current.isConnected).toBe(false);
    expect(result.current.connectionStatus).toBe('disconnected');
  });
});
