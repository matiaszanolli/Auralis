/**
 * useSearchInput debounce (#5660)
 *
 * The top-bar search used to call onSearch on every keystroke, re-rendering
 * the app shell and re-filtering the whole loaded library per character.
 * onSearch now fires once typing settles (300ms); the field echo stays
 * immediate.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSearchInput } from '../useSearchInput';

function changeEvent(value: string) {
  return { target: { value } } as React.ChangeEvent<HTMLInputElement>;
}

describe('useSearchInput debounce (#5660)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('fires onSearch once after rapid keystrokes settle, with the last query', () => {
    const onSearch = vi.fn();
    const { result } = renderHook(() => useSearchInput({ onSearch }));

    act(() => {
      result.current.handleSearchChange(changeEvent('d'));
      result.current.handleSearchChange(changeEvent('da'));
      result.current.handleSearchChange(changeEvent('daft'));
    });

    expect(onSearch).not.toHaveBeenCalled();
    expect(result.current.searchQuery).toBe('daft');

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(onSearch).toHaveBeenCalledTimes(1);
    expect(onSearch).toHaveBeenCalledWith('daft');
  });

  it('clearing fires onSearch immediately and cancels the pending debounce', () => {
    const onSearch = vi.fn();
    const onSearchClear = vi.fn();
    const { result } = renderHook(() => useSearchInput({ onSearch, onSearchClear }));

    act(() => {
      result.current.handleSearchChange(changeEvent('daft'));
    });
    act(() => {
      result.current.handleSearchClear();
    });

    expect(onSearch).toHaveBeenCalledWith('');
    expect(onSearchClear).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(onSearch).toHaveBeenCalledTimes(1);
  });
});
