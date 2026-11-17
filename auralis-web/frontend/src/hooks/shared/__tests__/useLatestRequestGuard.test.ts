/**
 * useLatestRequestGuard: only the newest request is current (#6275).
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useLatestRequestGuard } from '../useLatestRequestGuard';

describe('useLatestRequestGuard', () => {
  it('a request is current until a later one begins', () => {
    const { result } = renderHook(() => useLatestRequestGuard());

    const first = result.current();
    expect(first()).toBe(false);

    const second = result.current();
    expect(first()).toBe(true);
    expect(second()).toBe(false);
  });

  it('keeps one counter across re-renders and gives a stable begin function', () => {
    const { result, rerender } = renderHook(() => useLatestRequestGuard());
    const begin = result.current;
    const first = begin();

    rerender();
    const second = result.current();

    expect(result.current).toBe(begin);
    expect(first()).toBe(true);
    expect(second()).toBe(false);
  });

  it('separate guards do not supersede each other', () => {
    const { result } = renderHook(() => ({ a: useLatestRequestGuard(), b: useLatestRequestGuard() }));
    const fromA = result.current.a();

    result.current.b();

    expect(fromA()).toBe(false);
  });
});
