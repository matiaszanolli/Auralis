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
    connState.streamActive = true;
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

  // #6050: overrides are typed, and the tracked track can no longer be replaced by one.
  it('carries preset and intensity overrides but never lets them replace the tracked track_id', async () => {
    const { mgr, result } = await connectWithActiveStream();

    act(() => {
      // The cast stands in for an untyped caller: the type forbids track_id here, the runtime must too.
      result.current.reissueActiveStreamAs('play_enhanced', { preset: 'adaptive', intensity: 0.4, track_id: 999 } as never);
    });

    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload).toEqual({
      type: 'play_enhanced',
      data: { track_id: 7, preset: 'adaptive', intensity: 0.4, start_position: 999 },
    });
  });

  it('re-issues as play_normal without enhancement fields', async () => {
    const { mgr, result } = await connectWithActiveStream();
    result.current.setResumePositionGetter('play_normal', () => 12);

    act(() => {
      result.current.reissueActiveStreamAs('play_normal', { preset: 'adaptive', intensity: 0.4 });
    });

    expect(JSON.parse(mgr.send.mock.calls[0][0])).toEqual({
      type: 'play_normal',
      data: { track_id: 7, start_position: 12 },
    });
  });

  // #6044: queued while the socket is down, the position must be re-read at replay.
  it('queues a disconnected re-issue whose position is refreshed when the queue replays', async () => {
    const { mgr, result } = await connectWithActiveStream();
    mgr.isConnected.mockReturnValue(false);

    act(() => {
      result.current.reissueActiveStreamAs('play_enhanced');
    });
    expect(mgr.send).not.toHaveBeenCalled();

    // The outage passes while the engine keeps playing buffered audio.
    result.current.setResumePositionGetter('play_enhanced', () => 1234);
    mgr.isConnected.mockReturnValue(true);
    const { replayQueueAndResume } = await import('../websocketConnectionCore');
    const queue = [connState.lastStreamCommand!];
    replayQueueAndResume(mgr as never, queue);

    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload.data.start_position).toBe(1234);
  });

  it('keeps an explicit recovery position when it was queued while disconnected', async () => {
    const { mgr, result } = await connectWithActiveStream();
    mgr.isConnected.mockReturnValue(false);

    act(() => {
      result.current.reissueActiveStreamAs('play_enhanced', {}, 42.5);
    });
    result.current.setResumePositionGetter('play_enhanced', () => 1234);
    const { replayQueueAndResume } = await import('../websocketConnectionCore');
    replayQueueAndResume(mgr as never, [connState.lastStreamCommand!]);

    const payload = JSON.parse(mgr.send.mock.calls[0][0]);
    expect(payload.data.start_position).toBe(42.5);
  });
});
