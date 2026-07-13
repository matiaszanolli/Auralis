/**
 * WebSocketContext - Binary Audio-Chunk Pairing Tests (#4454)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The backend streams each PCM chunk as a text `audio_chunk_meta` JSON frame
 * immediately followed by a raw binary frame (ArrayBuffer, or Blob in some
 * browsers). WebSocketContext stashes the meta in `pendingAudioChunkMeta` and
 * fuses it with the next binary frame into a synthetic `audio_chunk` message
 * (with `pcm_binary`) for downstream subscribers. This pairing is the core of
 * the audio-streaming pipeline; before this file it had zero coverage (prior
 * bugs #3944 / #4167 lived in exactly this region).
 *
 * Covered:
 *  - meta frame + ArrayBuffer → one merged `audio_chunk` carrying pcm_binary + seq
 *  - meta frame + Blob        → same fusion via the async Blob.arrayBuffer() path
 *  - the raw `audio_chunk_meta` frame is NEVER dispatched to subscribers
 *  - a binary frame with no preceding meta is dropped (warned, not dispatched)
 *  - a throwing subscriber does not prevent other subscribers from receiving
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

// ============================================================================
// Mock WebSocketManager factory (mirrors WebSocketContext.reconnect.test.tsx)
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

function wrapper({ children }: { children: ReactNode }) {
  return <WebSocketProvider>{children}</WebSocketProvider>;
}

type Msg = AnyWebSocketMessage | WebSocketMessage;

/** A representative audio_chunk_meta text frame. */
function metaFrame(seq: number) {
  return {
    type: 'audio_chunk_meta' as const,
    data: {
      seq,
      chunk_index: 0,
      chunk_count: 1,
      frame_index: 0,
      frame_count: 1,
      sample_count: 4,
      crossfade_samples: 0,
      stream_type: 'enhanced' as const,
    },
  };
}

// ============================================================================
// Suite
// ============================================================================

describe('WebSocketContext - binary audio-chunk pairing (#4454)', () => {
  let mockMgr: MockWSManager;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    resetWebSocketSingletons();
    mockMgr = makeMockManager();
    // Regular function so the mock impl has [[Construct]] for `new WebSocketManager()`.
    vi.mocked(WebSocketManager).mockImplementation(function () { return mockMgr as any; });
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    resetWebSocketSingletons();
    vi.clearAllMocks();
    warnSpy.mockRestore();
  });

  async function setup() {
    const ctx = renderHook(() => useWebSocketContext(), { wrapper });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { mockMgr.emit('open'); });
    return ctx;
  }

  // --------------------------------------------------------------------------
  // meta + ArrayBuffer → merged audio_chunk
  // --------------------------------------------------------------------------

  it('fuses an audio_chunk_meta frame and the following ArrayBuffer into one audio_chunk', async () => {
    const { result } = await setup();

    const received: Msg[] = [];
    await act(async () => {
      result.current.subscribe('audio_chunk', (m) => received.push(m));
    });

    const pcm = new Uint8Array([1, 2, 3, 4]).buffer;

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(metaFrame(7)) });
      mockMgr.emit('message', { data: pcm });
    });

    expect(received).toHaveLength(1);
    const chunk = received[0] as any;
    expect(chunk.type).toBe('audio_chunk');
    // The binary payload is attached by reference, and meta fields carry over.
    expect(chunk.data.pcm_binary).toBe(pcm);
    expect(chunk.data.seq).toBe(7);
    expect(chunk.data.sample_count).toBe(4);
  });

  // --------------------------------------------------------------------------
  // The raw meta frame is never dispatched
  // --------------------------------------------------------------------------

  it('never dispatches the raw audio_chunk_meta frame to subscribers', async () => {
    const { result } = await setup();

    const allMessages: Msg[] = [];
    await act(async () => {
      result.current.subscribeAll((m) => allMessages.push(m));
    });

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(metaFrame(1)) });
    });

    // Meta alone (no binary yet) produces no dispatch at all.
    expect(allMessages).toHaveLength(0);

    await act(async () => {
      mockMgr.emit('message', { data: new Uint8Array([9]).buffer });
    });

    // Only the fused audio_chunk is ever seen — the meta type never leaks out.
    expect(allMessages).toHaveLength(1);
    expect(allMessages[0].type).toBe('audio_chunk');
    expect(allMessages.some((m) => (m.type as string) === 'audio_chunk_meta')).toBe(false);
  });

  // --------------------------------------------------------------------------
  // Blob transport path
  // --------------------------------------------------------------------------

  it('fuses meta with a Blob binary frame via the async arrayBuffer() path', async () => {
    const { result } = await setup();

    const received: Msg[] = [];
    await act(async () => {
      result.current.subscribe('audio_chunk', (m) => received.push(m));
    });

    const blob = new Blob([new Uint8Array([5, 6, 7, 8])]);

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(metaFrame(3)) });
      mockMgr.emit('message', { data: blob });
      // Blob.arrayBuffer() resolves asynchronously — let the microtask/task run.
      await new Promise((r) => setTimeout(r, 0));
    });

    expect(received).toHaveLength(1);
    const chunk = received[0] as any;
    expect(chunk.type).toBe('audio_chunk');
    expect(chunk.data.seq).toBe(3);
    // jsdom's Blob.arrayBuffer() returns a cross-realm ArrayBuffer, so assert on
    // the decoded bytes (realm-agnostic) rather than an instanceof check.
    expect(chunk.data.pcm_binary).toBeDefined();
    expect(Array.from(new Uint8Array(chunk.data.pcm_binary))).toEqual([5, 6, 7, 8]);
  });

  // --------------------------------------------------------------------------
  // Binary without preceding meta is dropped
  // --------------------------------------------------------------------------

  it('drops a binary frame that has no preceding audio_chunk_meta', async () => {
    const { result } = await setup();

    const received: Msg[] = [];
    await act(async () => {
      result.current.subscribeAll((m) => received.push(m));
    });

    await act(async () => {
      mockMgr.emit('message', { data: new Uint8Array([1, 2]).buffer });
    });

    expect(received).toHaveLength(0);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('binary frame without preceding audio_chunk_meta')
    );
  });

  // --------------------------------------------------------------------------
  // Per-handler isolation
  // --------------------------------------------------------------------------

  it('isolates a throwing subscriber so other subscribers still receive the chunk', async () => {
    const { result } = await setup();

    const good = vi.fn();
    await act(async () => {
      result.current.subscribe('audio_chunk', () => {
        throw new Error('subscriber blew up');
      });
      result.current.subscribe('audio_chunk', good);
    });

    await act(async () => {
      mockMgr.emit('message', { data: JSON.stringify(metaFrame(1)) });
      mockMgr.emit('message', { data: new Uint8Array([1]).buffer });
    });

    // The throwing handler is caught; the healthy handler still fires.
    expect(good).toHaveBeenCalledTimes(1);
    expect((good.mock.calls[0][0] as any).type).toBe('audio_chunk');
  });
});
