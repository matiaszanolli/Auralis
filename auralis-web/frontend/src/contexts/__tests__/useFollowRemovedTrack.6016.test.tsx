/**
 * Removing the playing row moves playback to the track that takes its slot (#6016).
 *
 * Queue [A, B, C] with A playing: deleting A used to keep A playing, highlight B,
 * and let Next / auto-advance (currentIndex + 1) play C, skipping B.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { removeTrack } from '@/store/slices/queueSlice';
import { useFollowRemovedTrack } from '../useFollowRemovedTrack';

const track = (id: number) => ({
  id, title: `Track ${id}`, artist: 'Artist', album: 'Album', duration: 180,
});
const A = track(1);
const B = track(2);
const C = track(3);

function setup({ isRunning = true, queue = [A, B, C], playing = A } = {}) {
  const store = createTestStore({
    queue: { tracks: queue, currentIndex: 0 },
    player: { currentTrack: playing },
  });
  const stopPlayback = vi.fn();
  const startTrackForSettings = vi.fn().mockResolvedValue(undefined);
  const gate = {
    runTransportCommand: async (command: () => void | Promise<void>) => {
      await command();
      return true;
    },
    pendingCommandRef: { current: null },
  };
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  const { result } = renderHook(
    () => useFollowRemovedTrack({ gate, stopPlayback, startTrackForSettings, isRunning }),
    { wrapper },
  );
  return { store, stopPlayback, startTrackForSettings, follow: result.current };
}

describe('useFollowRemovedTrack (#6016)', () => {
  it('plays the successor right away when the playing track is removed', async () => {
    const { store, stopPlayback, startTrackForSettings, follow } = setup();

    store.dispatch(removeTrack(0));
    await act(() => follow(0, A.id));

    expect(stopPlayback).toHaveBeenCalledTimes(1);
    expect(startTrackForSettings).toHaveBeenCalledWith(B.id);
    expect(store.getState().player.currentTrack?.id).toBe(B.id);
    expect(store.getState().queue.currentIndex).toBe(0);
  });

  it('only selects the successor when playback was paused', async () => {
    const { store, startTrackForSettings, follow } = setup({ isRunning: false });

    store.dispatch(removeTrack(0));
    await act(() => follow(0, A.id));

    expect(startTrackForSettings).not.toHaveBeenCalled();
    expect(store.getState().player.currentTrack?.id).toBe(B.id);
  });

  it('stops when nothing follows the removed track', async () => {
    const { store, stopPlayback, startTrackForSettings, follow } = setup({ queue: [B, A], playing: A });

    store.dispatch(removeTrack(1));
    await act(() => follow(1, A.id));

    expect(stopPlayback).toHaveBeenCalledTimes(1);
    expect(startTrackForSettings).not.toHaveBeenCalled();
    expect(store.getState().player.currentTrack).toBeNull();
  });

  it('does nothing when the removed track is not the one playing', async () => {
    const { store, stopPlayback, startTrackForSettings, follow } = setup({ playing: C });

    store.dispatch(removeTrack(0));
    await act(() => follow(0, A.id));

    expect(stopPlayback).not.toHaveBeenCalled();
    expect(startTrackForSettings).not.toHaveBeenCalled();
    expect(store.getState().player.currentTrack?.id).toBe(C.id);
  });
});
