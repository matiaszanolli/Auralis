/**
 * useWebSocketConnection - reissueActiveStreamAs startPositionOverride (#4655)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * reissueActiveStreamAs normally computes start_position from the live
 * resumeGetters lookup (current playback position) — the right quantity for
 * a preset/intensity change mid-playback (#3759/#3763). A chunk-failure
 * auto-resume (useAudioStreamingCore's handleStreamError, #4655) instead
 * needs to seed start_position from the backend's recovery_position, which
 * the client hasn't necessarily played up to yet — a different quantity the
 * live resumeGetters lookup cannot supply. startPositionOverride lets the
 * caller substitute it directly.
 */

vi.mock('@/utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketManager } from '@/utils/errorHandling';
import { useWebSocketConnection } from '../useWebSocketConnection';
import { connState, resetConnectionSingletons } from '../websocketConnectionCore';

function makeMockManager() {
  const handlers: Partial<Record<string, Function>> = {};
  return {
    isConnected: vi.fn().mockReturnValue(true),
    connect: vi.fn().mockResolvedValue(undefined),
    on: vi.fn((event: string, handler: Function) => { handlers[event] = handler; }),
    send: vi.fn(),
    close: vi.fn(),
  };
}

function renderConnection(url = 'ws://test/ws', dispatchMessage = vi.fn()) {
  return renderHook(() => useWebSocketConnection({ url, dispatchMessage }));
}

describe('useWebSocketConnection.reissueActiveStreamAs — startPositionOverride (#4655)', () => {
  beforeEach(() => {
    resetConnectionSingletons();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetConnectionSingletons();
    vi.clearAllMocks();
  });

  async function connectWithActiveStream() {
    const mgr = makeMockManager();
    // `function` form, not an arrow — arrows have no [[Construct]] and throw
    // "is not a constructor" when the source does `new WebSocketManager(...)`
    // (same #3933 hazard the singleton test file's own mocks work around).
    vi.mocked(WebSocketManager).mockImplementation(function () {
      return mgr as any;
    });

    const { result } = renderConnection();
    await act(async () => { await result.current.connect(); });

    // Seed an active stream command directly, mirroring what send() does
    // for a real play_enhanced/play_normal message (#3185 plumbing).
    connState.lastStreamCommand = { type: 'play_enhanced', data: { track_id: 7 } };
    // A live resumeGetters entry that must NOT win when an override is given.
    result.current.setResumePositionGetter('play_enhanced', () => 999);

    return { mgr, result };
  }

  it('uses startPositionOverride instead of the live resumeGetters position', async () => {
    const { mgr, result } = await connectWithActiveStream();

    let sent = false;
    act(() => {
      sent = result.current.reissueActiveStreamAs('play_enhanced', {}, 42.5);
    });

    expect(sent).toBe(true);
    expect(mgr.send).toHaveBeenCalledTimes(1);
    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload.data.start_position).toBe(42.5);
    expect(payload.data.track_id).toBe(7);
  });

  it('falls back to the live resumeGetters position when no override is given', async () => {
    const { mgr, result } = await connectWithActiveStream();

    act(() => {
      result.current.reissueActiveStreamAs('play_enhanced');
    });

    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload.data.start_position).toBe(999);
  });

  it('treats a startPositionOverride of 0 as an explicit value, not "no override"', async () => {
    const { mgr, result } = await connectWithActiveStream();

    act(() => {
      result.current.reissueActiveStreamAs('play_enhanced', {}, 0);
    });

    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload.data.start_position).toBe(0);
  });
});
