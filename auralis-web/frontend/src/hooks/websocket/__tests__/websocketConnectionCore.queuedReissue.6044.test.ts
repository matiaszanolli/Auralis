/**
 * A stream re-issue queued while disconnected is replayed from the live position (#6044)
 *
 * reissueActiveStreamAs, called with the socket down, computed start_position from the resume
 * getter at call time and queued the finished message. On reconnect the replay sent it verbatim
 * and, because the queue carried a stream command, skipped the re-issue that would recompute the
 * position. The player keeps playing buffered audio during an outage, so the restart point lagged
 * the real one by the outage length.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  connState,
  positionRefreshedOnReplay,
  replayQueueAndResume,
  resetConnectionSingletons,
  type OutgoingWebSocketMessage,
} from '../websocketConnectionCore';

function manager() {
  const sent: OutgoingWebSocketMessage[] = [];
  return {
    sent,
    send: vi.fn((raw: string) => sent.push(JSON.parse(raw))),
  };
}

const queued = (startPosition: number): OutgoingWebSocketMessage => ({
  type: 'play_enhanced',
  data: { track_id: 7, start_position: startPosition },
});

describe('replayQueueAndResume with a queued re-issue (#6044)', () => {
  beforeEach(() => resetConnectionSingletons());
  afterEach(() => resetConnectionSingletons());

  it('replaces a placeholder start_position with the position read at reconnect', () => {
    const message = queued(10);
    positionRefreshedOnReplay.add(message);
    connState.resumeGetters.play_enhanced = () => 95;
    const ws = manager();

    replayQueueAndResume(ws as never, [message]);

    expect(ws.sent).toHaveLength(1);
    expect(ws.sent[0].data).toMatchObject({ track_id: 7, start_position: 95 });
  });

  it('keeps an explicit recovery position (not registered for refresh)', () => {
    const message = queued(42);
    connState.resumeGetters.play_enhanced = () => 95;
    const ws = manager();

    replayQueueAndResume(ws as never, [message]);

    expect(ws.sent[0].data).toMatchObject({ start_position: 42 });
  });

  it('leaves unrelated queued commands untouched', () => {
    const ws = manager();
    const volume: OutgoingWebSocketMessage = { type: 'seek', data: { track_id: 7, position: 30 } };

    replayQueueAndResume(ws as never, [volume]);

    expect(ws.sent[0]).toEqual(volume);
  });

  it('does not mutate the queued message and still records it as the active stream command', () => {
    const message = queued(10);
    positionRefreshedOnReplay.add(message);
    connState.resumeGetters.play_enhanced = () => 95;

    replayQueueAndResume(manager() as never, [message]);

    expect((message.data as { start_position: number }).start_position).toBe(10);
    expect(connState.streamActive).toBe(true);
    expect((connState.lastStreamCommand?.data as { start_position: number }).start_position).toBe(95);
  });
});
