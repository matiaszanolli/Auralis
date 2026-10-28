/**
 * A finished, stopped or failed stream is never re-issued (#5876)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `lastStreamCommand` was cleared only when a WS stop/pause was sent, and the
 * client never sends either — stop, pause and track end are client-side — so
 * after the first play it stayed set for the session. Flipping the
 * enhancement toggle after a stop or a natural end re-issued play_* for the
 * last track (unrequested playback, or an out-of-range resume near the end),
 * and a reconnect restarted a finished track.
 */

vi.mock('@/utils/errorHandling', () => ({
  WebSocketManager: vi.fn(),
}));

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { WebSocketManager } from '@/utils/errorHandling';
import { useWebSocketConnection } from '../useWebSocketConnection';
import {
  connState,
  endActiveStream,
  replayQueueAndResume,
  resetConnectionSingletons,
} from '../websocketConnectionCore';

function makeMockManager() {
  return {
    isConnected: vi.fn().mockReturnValue(true),
    connect: vi.fn().mockResolvedValue(undefined),
    on: vi.fn(),
    send: vi.fn(),
    close: vi.fn(),
  };
}

async function connect() {
  const mgr = makeMockManager();
  vi.mocked(WebSocketManager).mockImplementation(function () {
    return mgr as any;
  });
  const { result } = renderHook(() => useWebSocketConnection({ url: 'ws://test/ws', dispatchMessage: vi.fn() }));
  await act(async () => { await result.current.connect(); });
  act(() => { result.current.send({ type: 'play_enhanced', data: { track_id: 7 } }); });
  mgr.send.mockClear();
  return { mgr, result };
}

const sentTypes = (mgr: ReturnType<typeof makeMockManager>) =>
  mgr.send.mock.calls.map(([raw]) => JSON.parse(raw).type);

describe('active stream session (#5876)', () => {
  beforeEach(() => {
    resetConnectionSingletons();
    vi.clearAllMocks();
  });
  afterEach(() => resetConnectionSingletons());

  it('re-issues while the stream is live', async () => {
    const { mgr, result } = await connect();

    let sent = false;
    act(() => { sent = result.current.reissueActiveStreamAs('play_normal'); });

    expect(sent).toBe(true);
    expect(sentTypes(mgr)).toEqual(['play_normal']);
  });

  it('does not re-issue once the session ended (stop, natural end, terminal error)', async () => {
    const { mgr, result } = await connect();
    endActiveStream(7);

    let sent = true;
    act(() => { sent = result.current.reissueActiveStreamAs('play_normal'); });

    expect(sent).toBe(false);
    expect(mgr.send).not.toHaveBeenCalled();
  });

  it('a superseded track ending does not end the current stream', async () => {
    const { result } = await connect();
    endActiveStream(3); // a late end frame for the previous track

    let sent = false;
    act(() => { sent = result.current.reissueActiveStreamAs('play_normal'); });
    expect(sent).toBe(true);
  });

  it('a seek after the end makes the track live again', async () => {
    const { mgr, result } = await connect();
    endActiveStream(7);
    act(() => { result.current.send({ type: 'seek', data: { track_id: 7, position: 30 } }); });
    mgr.send.mockClear();

    let sent = false;
    act(() => { sent = result.current.reissueActiveStreamAs('play_normal'); });
    expect(sent).toBe(true);
  });

  it('a reconnect resumes a live stream but not an ended one', () => {
    const mgr = makeMockManager();
    connState.lastStreamCommand = { type: 'play_enhanced', data: { track_id: 7 } };
    connState.streamActive = true;
    replayQueueAndResume(mgr as any, []);
    expect(sentTypes(mgr)).toEqual(['play_enhanced']);

    mgr.send.mockClear();
    endActiveStream();
    replayQueueAndResume(mgr as any, []);
    expect(mgr.send).not.toHaveBeenCalled();
  });
});
