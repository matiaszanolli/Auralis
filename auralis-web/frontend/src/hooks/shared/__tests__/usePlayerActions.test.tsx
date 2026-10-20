/**
 * usePlayerActions stability (#4176)
 *
 * The former usePlayer() bundled currentTime in its memo deps, so it returned
 * a new object on every 1Hz position tick — re-rendering action-only
 * consumers (e.g. a context menu's "play") during playback. usePlayerActions()
 * returns only stable callbacks, so it does NOT change identity when
 * currentTime ticks. (usePlayer was deleted in #5354 — zero production
 * callers — so only the stability half of the #4176 contract remains here.)
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { ReactNode, createElement } from 'react';
import { createTestStore } from '@/test/test-utils';
import { usePlayerActions } from '../useReduxState';
import { setCurrentTime, setIsPlaying } from '@/store/slices/playerSlice';

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
