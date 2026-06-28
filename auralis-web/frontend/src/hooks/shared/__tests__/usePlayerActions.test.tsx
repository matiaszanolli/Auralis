/**
 * usePlayerActions stability (#4176)
 *
 * usePlayer() bundles currentTime in its memo deps, so it returns a new object
 * on every 1Hz position tick — re-rendering action-only consumers (e.g. a
 * context menu's "play") during playback. usePlayerActions() returns only stable
 * callbacks, so it does NOT change identity when currentTime ticks.
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { ReactNode, createElement } from 'react';
import { createTestStore } from '@/test/test-utils';
import { usePlayer, usePlayerActions } from '../useReduxState';
import { setCurrentTime, setIsPlaying, setDuration } from '@/store/slices/playerSlice';

function makeWrapper(store: ReturnType<typeof createTestStore>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(Provider, { store, children });
}

describe('usePlayerActions (#4176)', () => {
  it('keeps a stable object identity when currentTime ticks', () => {
    const store = createTestStore();
    const { result, rerender } = renderHook(() => usePlayerActions(), {
      wrapper: makeWrapper(store),
    });

    const first = result.current;

    // Simulate a 1Hz position tick, then a re-render.
    act(() => {
      store.dispatch(setCurrentTime(42));
    });
    rerender();

    // The actions object must be the SAME reference (no churn for consumers).
    expect(result.current).toBe(first);
  });

  it('by contrast, usePlayer() returns a new object when currentTime changes', () => {
    const store = createTestStore();
    const { result, rerender } = renderHook(() => usePlayer(), {
      wrapper: makeWrapper(store),
    });

    // Seed duration so setCurrentTime isn't clamped to [0, duration].
    act(() => {
      store.dispatch(setDuration(300));
    });
    rerender();
    const first = result.current;

    act(() => {
      store.dispatch(setCurrentTime(99));
    });
    rerender();

    expect(result.current).not.toBe(first);
    expect(result.current.currentTime).toBe(99);
  });

  it('play / pause / togglePlay dispatch correctly via the live store', () => {
    const store = createTestStore();
    const { result } = renderHook(() => usePlayerActions(), {
      wrapper: makeWrapper(store),
    });

    act(() => { result.current.play(); });
    expect(store.getState().player.isPlaying).toBe(true);

    act(() => { result.current.pause(); });
    expect(store.getState().player.isPlaying).toBe(false);

    // togglePlay reads live isPlaying via store.getState() (no subscription).
    act(() => { store.dispatch(setIsPlaying(true)); });
    act(() => { result.current.togglePlay(); });
    expect(store.getState().player.isPlaying).toBe(false);
  });
});
