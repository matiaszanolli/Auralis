/**
 * Direct spec for useAppRedux (#5683): imports the module itself, not the useReduxState barrel.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { setVolume } from '@/store/slices/playerSlice';
import { useAppState } from '../useAppRedux';

describe('useAppState', () => {
  it('bundles the four state slices and no others', () => {
    const store = createTestStore({ player: { volume: 21 }, connection: { latency: 8 } });
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useAppState(), { wrapper });

    expect(Object.keys(result.current).sort()).toEqual(['cache', 'connection', 'player', 'queue']);
    expect(result.current.player.volume).toBe(21);
    expect(result.current.connection.latency).toBe(8);
    expect(result.current.queue.tracks).toEqual([]);
    expect(result.current.cache.stats).toBeNull();
  });

  it('re-renders with the slice that changed', () => {
    const store = createTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useAppState(), { wrapper });

    act(() => { store.dispatch(setVolume(10)); });
    expect(result.current.player.volume).toBe(10);
  });
});
