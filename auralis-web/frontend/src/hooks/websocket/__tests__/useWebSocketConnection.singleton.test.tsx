/**
 * useWebSocketConnection - singleton reuse guard (issue #4522)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `connect()` guarded singleton reuse on `connState.manager?.isConnected()` — a
 * *fully connected* manager — rather than on the manager merely existing. Any
 * connect() landing while a manager existed but was still handshaking or in
 * reconnect backoff (up to 30 s per attempt, 10 attempts) built a second
 * WebSocketManager and overwrote the singleton reference.
 *
 * The orphan was unreachable from disconnect(), so nothing ever closed it: its
 * socket, its handlers and its reconnect timer stayed alive for the lifetime of
 * the renderer, and its message handler kept dispatching a duplicate copy of
 * every inbound frame into Redux.
 */

vi.mock('@/utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketManager } from '@/utils/errorHandling';
import { useWebSocketConnection } from '../useWebSocketConnection';
import { connState, resetConnectionSingletons } from '../websocketConnectionCore';

type WSEvent = 'open' | 'close' | 'error' | 'message';

interface MockWSManager {
  isConnected: ReturnType<typeof vi.fn>;
  connect: ReturnType<typeof vi.fn>;
  on: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  emit: (event: WSEvent, arg?: any) => void;
  ctorConfig?: any;
}

/**
 * `connected: false` + a `connect()` that never settles models the handshake
 * window; call `settle()` to complete it.
 */
function makeMockManager(opts: { connected?: boolean; deferConnect?: boolean } = {}) {
  const handlers: Partial<Record<WSEvent, Function>> = {};
  let settle: () => void = () => {};
  const connectPromise = opts.deferConnect
    ? new Promise<void>((resolve) => {
        settle = resolve;
      })
    : Promise.resolve();

  const mgr: MockWSManager = {
    isConnected: vi.fn().mockReturnValue(opts.connected ?? true),
    connect: vi.fn().mockReturnValue(connectPromise),
    on: vi.fn((event: WSEvent, handler: Function) => {
      // Mirrors the real WebSocketManager: ONE slot per event, assigned not
      // appended. Re-attaching therefore replaces and cannot duplicate.
      handlers[event] = handler;
    }),
    send: vi.fn(),
    close: vi.fn(),
    emit(event, arg?) {
      handlers[event]?.(arg);
    },
  };
  return { mgr, settle: () => settle(), handlers };
}

function renderConnection(url = 'ws://test/ws', dispatchMessage = vi.fn()) {
  return renderHook(() => useWebSocketConnection({ url, dispatchMessage }));
}

describe('useWebSocketConnection - singleton reuse (issue #4522)', () => {
  beforeEach(() => {
    resetConnectionSingletons();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetConnectionSingletons();
    vi.clearAllMocks();
  });

  it('builds exactly one manager when a second connect() lands mid-handshake', async () => {
    const { mgr, settle } = makeMockManager({ connected: false, deferConnect: true });
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    const first = renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    // The handshake has NOT resolved: isConnected() is false, which used to
    // send this second caller down the create branch.
    expect(connState.manager!.isConnected()).toBe(false);

    // Start the second connect WITHOUT awaiting it — it now blocks on the same
    // in-flight handshake, which is the whole point.
    let second!: Promise<void>;
    await act(async () => {
      second = first.result.current.connect();
      await Promise.resolve();
    });

    expect(WebSocketManager).toHaveBeenCalledTimes(1);
    expect(connState.manager).toBe(mgr);

    await act(async () => {
      settle();
      await second;
    });
  });

  it('does not replace a manager that is in reconnect backoff', async () => {
    const { mgr } = makeMockManager({ connected: true });
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    const { result } = renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    // Socket dropped; the manager is now backing off (non-null, not connected).
    mgr.isConnected.mockReturnValue(false);
    await act(async () => {
      mgr.emit('close');
    });

    await act(async () => {
      await result.current.connect();
    });

    expect(WebSocketManager).toHaveBeenCalledTimes(1);
    expect(connState.manager).toBe(mgr);
    expect(mgr.close).not.toHaveBeenCalled();
  });

  it('never orphans a manager: close() precedes every replacement', async () => {
    const managers: MockWSManager[] = [];
    vi.mocked(WebSocketManager).mockImplementation(function () {
      const { mgr } = makeMockManager({ connected: false, deferConnect: false });
      managers.push(mgr);
      return mgr as any;
    });

    const { result } = renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    // Several extra connect() calls during the not-connected window.
    for (let i = 0; i < 3; i++) {
      await act(async () => {
        await result.current.connect();
      });
    }

    expect(managers).toHaveLength(1);
    expect(connState.manager).toBe(managers[0]);
  });

  it('delivers inbound frames to a consumer that took the reuse path', async () => {
    const { mgr } = makeMockManager({ connected: true });
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    const firstDispatch = vi.fn();
    const first = renderHook(() =>
      useWebSocketConnection({ url: 'ws://test/ws', dispatchMessage: firstDispatch })
    );
    await act(async () => {
      await Promise.resolve();
    });

    // A second consumer joins and takes the reuse branch.
    const secondDispatch = vi.fn();
    renderHook(() =>
      useWebSocketConnection({ url: 'ws://test/ws', dispatchMessage: secondDispatch })
    );
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      mgr.emit('message', { data: JSON.stringify({ type: 'player_state', data: {} }) });
    });

    // One frame -> exactly one dispatch, to the consumer holding the slot.
    const total = firstDispatch.mock.calls.length + secondDispatch.mock.calls.length;
    expect(total).toBe(1);
    expect(secondDispatch).toHaveBeenCalledTimes(1);

    first.unmount();
  });

  it('reports connected on the reuse path', async () => {
    const { mgr } = makeMockManager({ connected: true });
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    const second = renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    expect(second.result.current.isConnected).toBe(true);
    expect(second.result.current.connectionStatus).toBe('connected');
  });

  it('closes the old manager when the URL changes', async () => {
    const managers: MockWSManager[] = [];
    vi.mocked(WebSocketManager).mockImplementation(function () {
      const { mgr } = makeMockManager({ connected: true });
      managers.push(mgr);
      return mgr as any;
    });

    const { rerender } = renderHook(
      ({ url }: { url: string }) =>
        useWebSocketConnection({ url, dispatchMessage: vi.fn() }),
      { initialProps: { url: 'ws://test/a' } }
    );
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      rerender({ url: 'ws://test/b' });
      await Promise.resolve();
    });

    expect(managers).toHaveLength(2);
    expect(managers[0].close).toHaveBeenCalled();
    expect(connState.url).toBe('ws://test/b');
  });

  it('retires an exhausted manager so a later connect() can rebuild', async () => {
    const managers: MockWSManager[] = [];
    let firstConfig: any;
    vi.mocked(WebSocketManager).mockImplementation(function (_url: string, config: any) {
      const { mgr } = makeMockManager({ connected: false });
      if (managers.length === 0) firstConfig = config;
      managers.push(mgr);
      return mgr as any;
    });

    const { result } = renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    // The manager gives up permanently.
    await act(async () => {
      firstConfig.onMaxAttemptsExceeded();
    });

    expect(managers[0].close).toHaveBeenCalled();
    expect(connState.manager).toBeNull();

    // A later connect() is free to build a fresh manager.
    await act(async () => {
      await result.current.connect();
    });
    expect(managers).toHaveLength(2);
  });

  it('resetConnectionSingletons clears url and connectPromise', async () => {
    const { mgr } = makeMockManager({ connected: false, deferConnect: true });
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    renderConnection();
    await act(async () => {
      await Promise.resolve();
    });

    expect(connState.url).toBe('ws://test/ws');
    expect(connState.connectPromise).not.toBeNull();

    resetConnectionSingletons();

    expect(connState.manager).toBeNull();
    expect(connState.url).toBeNull();
    expect(connState.connectPromise).toBeNull();
  });
});
