/**
 * A stop that no play follows reaches the backend (#6559); Clear Queue stops playback (#6561).
 *
 * stopPlayback() is client-only and only a following play_* cancels the server's
 * stream task, so removing the last (or a paused) playing track left the server
 * rendering the rest of the track and holding its stream slot. Clear Queue did not
 * stop the browser stream at all: audio played on under an empty queue.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { removeTrack } from '@/store/slices/queueSlice';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { useFollowRemovedTrack, useStopForClearedQueue } from '../useFollowRemovedTrack';

const track = (id: number) => ({ id, title: `Track ${id}`, artist: 'Artist', album: 'Album', duration: 180 });
const A = track(1);
const B = track(2);
const STOP = { type: 'stop', data: {} };

const gate = {
  runTransportCommand: async (command: () => void | Promise<void>) => {
    await command();
    return true;
  },
  pendingCommandRef: { current: null },
};

function send() {
  return vi.mocked(useWebSocketContext)().send as ReturnType<typeof vi.fn>;
}

function wrap(store: ReturnType<typeof createTestStore>) {
  return ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
}

function follow({ queue, isRunning }: { queue: (typeof A)[]; isRunning: boolean }) {
  const store = createTestStore({ queue: { tracks: queue, currentIndex: 0 }, player: { currentTrack: A } });
  const stopPlayback = vi.fn();
  const startTrackForSettings = vi.fn().mockResolvedValue(undefined);
  const { result } = renderHook(
    () => useFollowRemovedTrack({ gate, stopPlayback, startTrackForSettings, isRunning }),
    { wrapper: wrap(store) },
  );
  return { store, run: result.current };
}

beforeEach(() => send().mockClear());

describe('useFollowRemovedTrack notifies the backend only when no play follows (#6559)', () => {
  it('sends stop when the removed track has no successor', async () => {
    const { store, run } = follow({ queue: [A], isRunning: true });
    store.dispatch(removeTrack(0));
    await act(() => run(0, A.id));
    expect(send()).toHaveBeenCalledWith(STOP);
  });

  it('sends stop when the session was paused (the successor is only selected)', async () => {
    const { store, run } = follow({ queue: [A, B], isRunning: false });
    store.dispatch(removeTrack(0));
    await act(() => run(0, A.id));
    expect(send()).toHaveBeenCalledWith(STOP);
  });

  it('sends no redundant stop when the successor starts playing', async () => {
    const { store, run } = follow({ queue: [A, B], isRunning: true });
    store.dispatch(removeTrack(0));
    await act(() => run(0, A.id));
    expect(send()).not.toHaveBeenCalledWith(STOP);
  });
});

describe('useStopForClearedQueue (#6561)', () => {
  function cleared(isPlaybackActive: boolean) {
    // The player_state broadcast may already have nulled the track: the stop must not depend on it.
    const store = createTestStore({ queue: { tracks: [], currentIndex: 0 }, player: { currentTrack: null } });
    const stopPlayback = vi.fn();
    const { result } = renderHook(
      () => useStopForClearedQueue({ gate, stopPlayback, isPlaybackActive }),
      { wrapper: wrap(store) },
    );
    return { store, stopPlayback, run: result.current };
  }

  it('stops an active session on the client and the backend', async () => {
    const { stopPlayback, run } = cleared(true);
    await act(() => run());
    expect(stopPlayback).toHaveBeenCalledTimes(1);
    expect(send()).toHaveBeenCalledWith(STOP);
  });

  it('only clears the selection when nothing is playing', async () => {
    const { store, stopPlayback, run } = cleared(false);
    await act(() => run());
    expect(stopPlayback).not.toHaveBeenCalled();
    expect(send()).not.toHaveBeenCalled();
    expect(store.getState().player.currentTrack).toBeNull();
  });
});
