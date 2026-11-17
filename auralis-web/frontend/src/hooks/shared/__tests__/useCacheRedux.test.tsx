/**
 * Direct spec for useCacheRedux (#5683): imports the module itself, not the useReduxState barrel.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import type { ReactNode } from 'react';
import { createTestStore } from '@/test/test-utils';
import { setCacheStats } from '@/store/slices/cacheSlice';
import { useCacheState } from '../useCacheRedux';

describe('useCacheState', () => {
  it('starts from the slice defaults', () => {
    const store = createTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useCacheState(), { wrapper });

    expect(result.current).toEqual({ stats: null, health: null, lastUpdated: 0 });
  });

  it('follows the slice when cache stats are written', () => {
    const store = createTestStore();
    const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
    const { result } = renderHook(() => useCacheState(), { wrapper });
    const stats = { total_chunks: 4 } as never;

    act(() => { store.dispatch(setCacheStats(stats)); });

    expect(result.current.stats).toMatchObject({ total_chunks: 4 });
    expect(result.current.lastUpdated).toBeGreaterThan(0);
  });
});
