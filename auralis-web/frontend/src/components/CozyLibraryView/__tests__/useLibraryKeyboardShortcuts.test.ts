/**
 * useLibraryKeyboardShortcuts (#5804)
 *
 * onSelectAllInfo / onClearSelectionInfo are optional announcers. CozyLibraryView
 * used to pass `() => {}` for both; a fresh function each render is a new effect
 * dependency, so the window keydown listener was torn down and re-added on every
 * render. Omitting them must work, and keep the listener stable.
 */

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useLibraryKeyboardShortcuts } from '../useLibraryKeyboardShortcuts';

// Real key events target an element (the handler reads event.target.tagName), so
// dispatch from the body and let it bubble to the window listener.
function press(key: string, init: KeyboardEventInit = {}) {
  document.body.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init }));
}

describe('useLibraryKeyboardShortcuts without announcers', () => {
  it('selects all on Ctrl+A with no announcer supplied', () => {
    const onSelectAll = vi.fn();
    const { unmount } = renderHook(() =>
      useLibraryKeyboardShortcuts({
        filteredTracksCount: 3,
        hasSelection: false,
        onSelectAll,
        onClearSelection: vi.fn(),
      })
    );

    press('a', { ctrlKey: true });

    expect(onSelectAll).toHaveBeenCalledTimes(1);
    unmount();
  });

  it('clears the selection on Escape with no announcer supplied', () => {
    const onClearSelection = vi.fn();
    const { unmount } = renderHook(() =>
      useLibraryKeyboardShortcuts({
        filteredTracksCount: 3,
        hasSelection: true,
        onSelectAll: vi.fn(),
        onClearSelection,
      })
    );

    press('Escape');

    expect(onClearSelection).toHaveBeenCalledTimes(1);
    unmount();
  });

  it('still announces when an announcer is supplied', () => {
    const onSelectAllInfo = vi.fn();
    const { unmount } = renderHook(() =>
      useLibraryKeyboardShortcuts({
        filteredTracksCount: 5,
        hasSelection: false,
        onSelectAll: vi.fn(),
        onClearSelection: vi.fn(),
        onSelectAllInfo,
      })
    );

    press('a', { ctrlKey: true });

    expect(onSelectAllInfo).toHaveBeenCalledWith('Selected all 5 tracks');
    unmount();
  });

  it('keeps one keydown listener across re-renders when no announcers are passed', () => {
    const add = vi.spyOn(window, 'addEventListener');
    const props = {
      filteredTracksCount: 3,
      hasSelection: false,
      onSelectAll: vi.fn(),
      onClearSelection: vi.fn(),
    };
    const { rerender, unmount } = renderHook(() => useLibraryKeyboardShortcuts(props));
    const after = () => add.mock.calls.filter(([type]) => type === 'keydown').length;
    const initial = after();

    rerender();
    rerender();

    expect(after()).toBe(initial);
    unmount();
    add.mockRestore();
  });
});
