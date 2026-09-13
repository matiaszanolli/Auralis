/**
 * Registration gating for useKeyboardShortcuts (#4692)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * The hook used to have two registration paths with different gating: a
 * `useEffect` gated on `serializedKey` (#2696), and a second `useLayoutEffect`
 * with no dep array that re-registered whenever
 * `shortcutsRef.current !== shortcutsToRegister`. That second path was
 * ungated specifically for the hook's now-deleted "config-object" input form
 * (#5231) — it built a fresh array every render, so the guard the comment
 * described ("only when the shortcut array identity changes") was a
 * condition that never failed to hold for that form.
 *
 * It could not simply be deleted: that ungated path was, accidentally, the only
 * thing keeping handler closures current, since the main effect does not re-run
 * on handler identity changes. Memoizing the array on `serializedKey` would
 * have frozen the handlers inside it.
 *
 * The fix registers a stable trampoline that reads the live handler out of a
 * ref, so registration is gated while handlers stay fresh. These tests pin
 * that behavior on the array form — the only input form the hook accepts
 * since #5231 — asserting the call count rather than inspecting the code,
 * since a `useMemo` with an unstable dep is a no-op that looks like a fix.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { keyboardShortcuts } from '@/services/keyboardShortcutsService';
import { useKeyboardShortcuts } from '../useKeyboardShortcuts';
import type { KeyboardShortcut } from '../useKeyboardShortcuts';

/** Dispatch a real keydown so the service's own matching runs. */
const press = (key: string) => {
  act(() => {
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
    );
  });
};

describe('useKeyboardShortcuts registration gating (#4692)', () => {
  let registerSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    keyboardShortcuts.clear();
    registerSpy = vi.spyOn(keyboardShortcuts, 'register');
  });

  describe('the array form (the hook\'s only input form since #5231)', () => {
    it('does not re-register when a memoized array is passed', () => {
      const shortcuts: KeyboardShortcut[] = [
        { key: 'x', description: 'X', handler: vi.fn() },
      ];

      const { rerender } = renderHook(() => useKeyboardShortcuts(shortcuts));
      const afterFirstRender = registerSpy.mock.calls.length;

      rerender();
      rerender();

      expect(registerSpy).toHaveBeenCalledTimes(afterFirstRender);
    });

    it('does not re-register when an unmemoized array is rebuilt each render', () => {
      // Previously this form was safe only because callers memoized. A fresh
      // array with the same structure must not re-register either.
      const { rerender } = renderHook(() =>
        useKeyboardShortcuts([{ key: 'x', description: 'X', handler: vi.fn() }])
      );
      const afterFirstRender = registerSpy.mock.calls.length;

      rerender();
      rerender();
      rerender();

      expect(registerSpy).toHaveBeenCalledTimes(afterFirstRender);
    });

    it('invokes the current handler from an unmemoized array', () => {
      let seen: number | null = null;
      const { rerender } = renderHook(
        ({ value }) =>
          useKeyboardShortcuts([
            {
              key: 'x',
              description: 'X',
              handler: () => {
                seen = value;
              },
            },
          ]),
        { initialProps: { value: 1 } }
      );

      rerender({ value: 7 });
      press('x');

      expect(seen).toBe(7);
    });

    it('routes each shortcut to its own handler', () => {
      // The trampoline resolves handlers by index; a mix-up would show here.
      const first = vi.fn();
      const second = vi.fn();
      renderHook(() =>
        useKeyboardShortcuts([
          { key: 'x', description: 'X', handler: first },
          { key: 'y', description: 'Y', handler: second },
        ])
      );

      press('y');

      expect(second).toHaveBeenCalledTimes(1);
      expect(first).not.toHaveBeenCalled();
    });

    it('re-registers when a shortcut structure actually changes', () => {
      const { rerender } = renderHook(
        ({ withSearch }) =>
          useKeyboardShortcuts(
            withSearch
              ? [
                  { key: 'x', description: 'X', handler: vi.fn() },
                  { key: '/', description: 'Focus search', handler: vi.fn() },
                ]
              : [{ key: 'x', description: 'X', handler: vi.fn() }]
          ),
        { initialProps: { withSearch: false } }
      );

      const beforeChange = registerSpy.mock.calls.length;
      rerender({ withSearch: true });

      expect(registerSpy.mock.calls.length).toBeGreaterThan(beforeChange);
    });
  });
});
