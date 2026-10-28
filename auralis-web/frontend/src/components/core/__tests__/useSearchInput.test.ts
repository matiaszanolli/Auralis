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

describe('useSearchInput follows a parent reset (#6013)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  function setup(initialExternal: string) {
    const onSearch = vi.fn();
    const hook = renderHook(
      ({ externalQuery }) => useSearchInput({ onSearch, externalQuery }),
      { initialProps: { externalQuery: initialExternal } }
    );
    return { onSearch, ...hook };
  }

  it('empties the field when the parent clears its query (Escape)', () => {
    const { result, rerender } = setup('');
    act(() => result.current.handleSearchChange(changeEvent('daft')));
    act(() => { vi.advanceTimersByTime(400); });
    rerender({ externalQuery: 'daft' }); // the debounced echo reaches the parent
    expect(result.current.searchQuery).toBe('daft');

    rerender({ externalQuery: '' }); // Escape clears the app's query

    expect(result.current.searchQuery).toBe('');
  });

  it('cancels a pending debounce so it cannot restore the cleared text', () => {
    const { onSearch, result, rerender } = setup('old');
    act(() => result.current.handleSearchChange(changeEvent('new')));

    rerender({ externalQuery: '' });
    act(() => { vi.advanceTimersByTime(1000); });

    expect(onSearch).not.toHaveBeenCalled();
    expect(result.current.searchQuery).toBe('');
  });

  it('does not overwrite newer keystrokes with the debounced echo of older ones', () => {
    const { result, rerender } = setup('');
    act(() => result.current.handleSearchChange(changeEvent('ab')));
    act(() => { vi.advanceTimersByTime(400); });
    act(() => result.current.handleSearchChange(changeEvent('abc'))); // typed since

    rerender({ externalQuery: 'ab' }); // parent now receives the earlier value

    expect(result.current.searchQuery).toBe('abc');
  });

  it('is unchanged when the parent does not own a query', () => {
    const onSearch = vi.fn();
    const { result } = renderHook(() => useSearchInput({ onSearch }));
    act(() => result.current.handleSearchChange(changeEvent('x')));
    expect(result.current.searchQuery).toBe('x');
  });
});

