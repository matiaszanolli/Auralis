/**
 * WebSocketContext - Stream Reconnect Tests (issue #2385)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Verifies that the last active streaming command (play_enhanced / play_normal)
 * is automatically re-issued after a WebSocket reconnect, restoring audio
 * playback that was silenced by an unexpected disconnect.
 *
 * Acceptance criteria:
 *  - After WS reconnect, play_enhanced / play_normal is re-sent automatically
 *  - Commands sent while disconnected (queued) are NOT re-issued a second time
 *  - Explicit stop / pause clears the re-issue candidate, even while disconnected
 *
 * NOTE: The global test setup (setup.ts) replaces WebSocketContext with a no-op
 * mock for all other tests. We reverse that here so we can test the real
 * implementation while still mocking only the WebSocketManager transport layer.
 */

// Undo the global mock applied in src/test/setup.ts so the real
// implementation is loaded and tested.
vi.unmock('../WebSocketContext');

// Mock only the transport layer (WebSocketManager) so we can control
// connection events without touching the network.
vi.mock('../../utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  WebSocketProvider,
  useWebSocketContext,
  resetWebSocketSingletons,
} from '../WebSocketContext';
import { WebSocketManager } from '../../utils/errorHandling';

// ============================================================================
// Mock WebSocketManager factory
// ============================================================================

type WSEvent = 'open' | 'close' | 'error' | 'message';

interface MockWSManager {
  isConnected: ReturnType<typeof vi.fn>;
  connect: ReturnType<typeof vi.fn>;
  on: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  /** Fire a registered event handler from the test. */
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

// ============================================================================
// Helpers
// ============================================================================

function wrapper({ children }: { children: React.ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

/** Parse all recorded manager.send() calls as JSON objects. */
function sentMessages(mgr: MockWSManager): any[] {
  return mgr.send.mock.calls.map(([raw]: [string]) => JSON.parse(raw));
}

// ============================================================================
// Suite
// ============================================================================

describe('WebSocketContext - stream reconnect (issue #2385)', () => {
  let mockMgr: MockWSManager;

  beforeEach(() => {
    resetWebSocketSingletons();
    mockMgr = makeMockManager();
    vi.mocked(WebSocketManager).mockImplementation(() => mockMgr as any);
  });

  afterEach(() => {
    resetWebSocketSingletons();
    vi.clearAllMocks();
  });

  // --------------------------------------------------------------------------
  // Helper: render the context and simulate an initial successful connection
  // --------------------------------------------------------------------------

  async function setup() {
    const ctx = renderHook(() => useWebSocketContext(), { wrapper });
    // Allow the async connect() to register event handlers
    await act(async () => {
      await Promise.resolve();
    });
    // Simulate backend accepting the connection
    await act(async () => {
      mockMgr.emit('open');
    });
    return ctx;
  }

  // --------------------------------------------------------------------------
  // Core reconnect scenarios
  // --------------------------------------------------------------------------

  it('re-issues play_enhanced after WebSocket reconnects', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 42, preset: 'adaptive' } });
    });

    // Disconnect then reconnect
    await act(async () => { mockMgr.emit('close'); });
    await act(async () => { mockMgr.emit('open'); });

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_enhanced');
    // 1 original send + 1 re-issue on reconnect
    expect(plays).toHaveLength(2);
    expect(plays[1].data.track_id).toBe(42);
    expect(plays[1].data.preset).toBe('adaptive');
  });

  it('re-issues play_normal after WebSocket reconnects', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_normal', data: { track_id: 7 } });
    });

    await act(async () => { mockMgr.emit('close'); });
    await act(async () => { mockMgr.emit('open'); });

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_normal');
    expect(plays).toHaveLength(2);
    expect(plays[1].data.track_id).toBe(7);
  });

  // --------------------------------------------------------------------------
  // Explicit stop / pause must suppress re-issue
  // --------------------------------------------------------------------------

  it('does not re-issue play_enhanced after explicit stop', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 99 } });
      result.current.send({ type: 'stop' });
    });

    await act(async () => { mockMgr.emit('close'); });
    await act(async () => { mockMgr.emit('open'); });

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_enhanced');
    // Only the original send; stop cleared the re-issue candidate
    expect(plays).toHaveLength(1);
  });

  it('does not re-issue play_enhanced after explicit pause', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 5 } });
      result.current.send({ type: 'pause' });
    });

    await act(async () => { mockMgr.emit('close'); });
    await act(async () => { mockMgr.emit('open'); });

    expect(sentMessages(mockMgr).filter(m => m.type === 'play_enhanced')).toHaveLength(1);
  });

  it('does not re-issue stream command when stop is sent while disconnected', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 11 } });
    });

    // WS goes down
    await act(async () => {
      mockMgr.isConnected.mockReturnValue(false);
      mockMgr.emit('close');
    });

    // User clicks stop while disconnected (goes to queue)
    act(() => {
      result.current.send({ type: 'stop' });
    });

    // WS comes back up
    await act(async () => {
      mockMgr.isConnected.mockReturnValue(true);
      mockMgr.emit('open');
    });

    const all = sentMessages(mockMgr);
    // stop is flushed from queue; play_enhanced must NOT be re-issued
    expect(all.filter(m => m.type === 'play_enhanced')).toHaveLength(1);
    expect(all.filter(m => m.type === 'stop')).toHaveLength(1);
  });

  // --------------------------------------------------------------------------
  // Queued stream commands must not be sent twice
  // --------------------------------------------------------------------------

  it('does not send play_enhanced twice when command was queued during disconnect', async () => {
    // WS is never connected before the play command
    mockMgr.isConnected.mockReturnValue(false);
    const { result } = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 3 } });
    });

    // WS comes up — queued command is flushed, singletonLastStreamCommand is null
    await act(async () => {
      mockMgr.isConnected.mockReturnValue(true);
      mockMgr.emit('open');
    });

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_enhanced');
    // Flushed exactly once from the queue — no duplicate via re-issue
    expect(plays).toHaveLength(1);
  });

  // --------------------------------------------------------------------------
  // Multiple reconnects
  // --------------------------------------------------------------------------

  it('re-issues stream command on each subsequent reconnect', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 77 } });
    });

    for (let i = 0; i < 2; i++) {
      await act(async () => { mockMgr.emit('close'); });
      await act(async () => { mockMgr.emit('open'); });
    }

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_enhanced');
    // 1 original + 2 re-issues
    expect(plays).toHaveLength(3);
    plays.forEach(m => expect(m.data.track_id).toBe(77));
  });

  it('uses the most recent stream command when track changes before disconnect', async () => {
    const { result } = await setup();

    act(() => {
      result.current.send({ type: 'play_enhanced', data: { track_id: 1 } });
      result.current.send({ type: 'play_enhanced', data: { track_id: 2 } });
    });

    await act(async () => { mockMgr.emit('close'); });
    await act(async () => { mockMgr.emit('open'); });

    const plays = sentMessages(mockMgr).filter(m => m.type === 'play_enhanced');
    // 2 originals + 1 re-issue (track_id=2, the most recent)
    expect(plays).toHaveLength(3);
    expect(plays[2].data.track_id).toBe(2);
  });
});
